import glob
import os
import random
import re
import tempfile
import time
from urllib.parse import parse_qs, urlparse

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url):
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    # Handle /embed/, /shorts/, /live/ paths
    path_match = re.match(r"^/(embed|shorts|live)/([^/?&]+)", parsed.path)
    if path_match:
        return path_match.group(2)
    return None


def extract_playlist_id(url):
    qs = parse_qs(urlparse(url).query)
    return qs.get("list", [None])[0]


def is_playlist(url):
    qs = parse_qs(urlparse(url).query)
    # If both v= and list= are present, treat as single video
    if "v" in qs and "list" in qs:
        return False
    return extract_playlist_id(url) is not None


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name.strip()[:200]


class TranscriptError(RuntimeError):
    pass


_BACKENDS = ("api", "ytdlp")
_RATE_LIMIT_HINTS = ("429", "too many requests", "blocking requests", "ipblocked")
DEFAULT_PLAYER_CLIENTS = "tv_simply,web_safari,web_embedded,ios"


def _looks_rate_limited(err):
    msg = str(err).lower()
    return any(h in msg for h in _RATE_LIMIT_HINTS)


def _curl_cffi_available():
    try:
        from yt_dlp.networking._curlcffi import CurlCFFIRH  # noqa: F401

        return True
    except Exception:
        return False


class FetchConfig:
    """Bundles transcript-fetch tunables. All fields optional.

    `proxies` accepts a list — yt-dlp + youtube-transcript-api retry through
    each entry on rate-limit errors (proxy rotation). A leading None entry
    means "try direct first".
    """

    __slots__ = (
        "backend",
        "cookies",
        "cookies_from_browser",
        "max_retries",
        "base_delay",
        "proxies",
        "source_address",
        "impersonate",
        "player_client",
        "sleep_subtitles",
    )

    def __init__(
        self,
        *,
        backend: str = "auto",
        cookies=None,
        cookies_from_browser: "str | None" = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        proxies: "list[str | None] | list[str] | None" = None,
        source_address: "str | None" = None,
        impersonate: "str | None" = None,
        player_client: str = DEFAULT_PLAYER_CLIENTS,
        sleep_subtitles: float = 0.0,
    ):
        self.backend = backend
        self.cookies = cookies
        self.cookies_from_browser = cookies_from_browser
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.proxies = list(proxies) if proxies else [None]
        self.source_address = source_address
        self.impersonate = impersonate or (
            "chrome-136" if _curl_cffi_available() else None
        )
        self.player_client = player_client
        self.sleep_subtitles = sleep_subtitles


def _vtt_to_text(content):
    """Strip VTT/SRT cue metadata + decode HTML + collapse adjacent duplicates."""
    import html as _html

    lines = []
    for raw in content.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("WEBVTT") or s.startswith("Kind:") or s.startswith("Language:"):
            continue
        if "-->" in s:
            continue
        if re.fullmatch(r"\d+", s):
            continue
        s = re.sub(r"<[^>]+>", "", s)
        s = _html.unescape(s).strip()
        if s:
            lines.append(s)
    out = []
    for s in lines:
        if not out or out[-1] != s:
            out.append(s)
    return " ".join(out)


def _fetch_via_api(video_id, cfg, proxy=None):
    from youtube_transcript_api.proxies import GenericProxyConfig

    proxy_cfg = None
    if proxy:
        proxy_cfg = GenericProxyConfig(http_url=proxy, https_url=proxy)
    api = YouTubeTranscriptApi(proxy_config=proxy_cfg) if proxy_cfg else YouTubeTranscriptApi()
    snippets = api.fetch(video_id)
    return " ".join(s.text for s in snippets)


def _fetch_via_ytdlp(video_id, cfg, proxy=None):
    with tempfile.TemporaryDirectory() as td:
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB", "en.*"],
            "subtitlesformat": "vtt/srt/best",
            "outtmpl": os.path.join(td, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 2,
            "extractor_retries": 2,
            "ignore_no_formats_error": True,
            "extractor_args": {
                "youtube": {"player_client": cfg.player_client.split(",")},
            },
        }
        if cfg.impersonate:
            try:
                from yt_dlp.networking.impersonate import ImpersonateTarget

                opts["impersonate"] = ImpersonateTarget.from_str(cfg.impersonate)
            except Exception:
                pass
        if cfg.cookies:
            opts["cookiefile"] = str(cfg.cookies)
        if cfg.cookies_from_browser:
            opts["cookiesfrombrowser"] = (cfg.cookies_from_browser,)
        if proxy:
            opts["proxy"] = proxy
        if cfg.source_address:
            opts["source_address"] = cfg.source_address
        if cfg.sleep_subtitles > 0:
            opts["sleep_interval_subtitles"] = cfg.sleep_subtitles

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        files = sorted(
            glob.glob(os.path.join(td, f"{video_id}*.vtt"))
            + glob.glob(os.path.join(td, f"{video_id}*.srt"))
        )
        if not files:
            raise TranscriptError(f"yt-dlp: no subtitle track for {video_id}")
        with open(files[0], "r", encoding="utf-8") as f:
            text = _vtt_to_text(f.read())
        if not text.strip():
            raise TranscriptError(f"yt-dlp: empty subtitle file for {video_id}")
        return text


def fetch_transcript(video_id, cfg=None, **kwargs):
    """Fetch transcript text with retry/backoff, backend fallback, proxy rotation.

    Pass `cfg=FetchConfig(...)` for full control. Bare kwargs (`backend=`,
    `cookies=`, `max_retries=`, `base_delay=`, etc.) accepted for back-compat.
    """
    if cfg is None:
        cfg = FetchConfig(**kwargs)

    if cfg.backend == "auto":
        order = list(_BACKENDS)
    elif cfg.backend in _BACKENDS:
        order = [cfg.backend]
    else:
        raise ValueError(f"backend must be auto|api|ytdlp, got {cfg.backend!r}")

    last_err = None
    for be in order:
        for proxy in cfg.proxies:
            for attempt in range(max(1, cfg.max_retries)):
                try:
                    if be == "api":
                        return _fetch_via_api(video_id, cfg, proxy=proxy)
                    return _fetch_via_ytdlp(video_id, cfg, proxy=proxy)
                except Exception as e:
                    last_err = e
                    if attempt < cfg.max_retries - 1 and _looks_rate_limited(e):
                        time.sleep(cfg.base_delay * (2 ** attempt) + random.uniform(0, cfg.base_delay))
                        continue
                    break
    raise TranscriptError(f"all backends failed for {video_id}: {last_err}") from last_err


_YDL_FLAT_OPTS = {"quiet": True, "no_warnings": True, "extract_flat": True}


def get_video_title(video_id):
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )
        return info.get("title", video_id)


def save_transcript(video_id, title=None, output_dir=".", *, cfg=None, **kwargs):
    """Fetch + save a single transcript .txt.

    Pass `cfg=FetchConfig(...)` or any FetchConfig kwargs for bypass tuning.
    """
    if title is None:
        title = get_video_title(video_id)
    text = fetch_transcript(video_id, cfg=cfg, **kwargs)
    filename = sanitize_filename(title) + ".txt"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        f.write(text)
    return filepath


def fetch_channel_videos(channel_url, limit=30):
    """Fetch the latest N videos from a YouTube channel.

    Returns a list of dicts with keys: id, title, date, duration.
    """
    if channel_url.startswith("@"):
        channel_url = f"https://www.youtube.com/{channel_url}/videos"
    else:
        parsed_path = urlparse(channel_url).path.rstrip("/")
        if not parsed_path.endswith("/videos"):
            channel_url = channel_url.rstrip("/") + "/videos"

    opts = {
        **_YDL_FLAT_OPTS,
        "playlistend": limit,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries", [])
    videos = []
    for entry in entries:
        video_id = entry.get("id") or entry.get("url")
        if not video_id:
            continue
        videos.append({
            "id": video_id,
            "title": entry.get("title", video_id),
            "date": entry.get("upload_date", ""),
            "duration": entry.get("duration") or 0,
        })

    return videos


def fetch_channel_playlists(channel_url, limit=30):
    """Fetch playlists from a YouTube channel.

    Returns a list of dicts with keys: id, title, video_count.
    """
    if channel_url.startswith("@"):
        channel_url = f"https://www.youtube.com/{channel_url}/playlists"
    else:
        parsed_path = urlparse(channel_url).path.rstrip("/")
        if not parsed_path.endswith("/playlists"):
            channel_url = channel_url.rstrip("/") + "/playlists"

    opts = {
        **_YDL_FLAT_OPTS,
        "playlistend": limit,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries", [])
    playlists = []
    for entry in entries:
        playlist_id = entry.get("id") or entry.get("url")
        if not playlist_id:
            continue
        playlists.append({
            "id": playlist_id,
            "title": entry.get("title", playlist_id),
            "video_count": entry.get("playlist_count") or entry.get("n_entries") or 0,
        })

    return playlists


def fetch_playlist_entries(playlist_id):
    """Fetch all video entries from a playlist.

    Returns (playlist_title, [{id, title}]).
    """
    with yt_dlp.YoutubeDL(_YDL_FLAT_OPTS) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/playlist?list={playlist_id}",
            download=False,
        )

    playlist_title = info.get("title", f"playlist-{playlist_id}")
    entries = info.get("entries", [])
    videos = []
    for entry in entries:
        video_id = entry.get("id") or entry.get("url")
        if not video_id:
            continue
        videos.append({
            "id": video_id,
            "title": entry.get("title", video_id),
        })

    return playlist_title, videos
