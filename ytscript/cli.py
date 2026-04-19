"""ytscript — transcripts, audio, summaries, and search for YouTube URLs.

Subcommands:
  transcript  Fetch one video or a whole playlist as .txt
  audio       Download video audio as MP3 or WAV (any ffmpeg format)
  summary     Fetch transcript, produce a structured summary
  channel     List a channel's recent videos (metadata only)
  playlists   List a channel's playlists (metadata only)
  search      Search YouTube and list matching videos

Runtime deps (lazy-installed on first run):
  yt-dlp                 — URL resolution, audio extraction, channel / playlist walk
  youtube-transcript-api — transcript text

System deps:
  ffmpeg — required for audio extraction
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import typer

app = typer.Typer(help="YouTube: transcripts, audio, and summaries.")


# ── Dependency bootstrap ──────────────────────────────────────────────────────

_PIP_DEPS = ("yt-dlp", "youtube-transcript-api")


def _ensure_deps() -> None:
    """Install yt-dlp + youtube-transcript-api on first run if missing."""
    missing = []
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        missing.append("yt-dlp")
    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        missing.append("youtube-transcript-api")

    if not missing:
        return

    typer.echo(f"[youtube] installing {', '.join(missing)}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *missing],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"[youtube] ERROR: pip install failed: {e}", err=True)
        typer.echo(f"  Run manually: pip install {' '.join(missing)}", err=True)
        raise typer.Exit(1)


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        typer.echo("[youtube] ERROR: ffmpeg not found on PATH.", err=True)
        typer.echo("  Install: pacman -S ffmpeg | apt install ffmpeg | brew install ffmpeg", err=True)
        raise typer.Exit(1)


# ── URL helpers (adapted from ~/projects/ytscript/ytscript/core.py) ──────────

def _extract_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/") or None
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    m = re.match(r"^/(embed|shorts|live)/([^/?&]+)", parsed.path)
    if m:
        return m.group(2)
    return None


def _extract_playlist_id(url: str) -> Optional[str]:
    qs = parse_qs(urlparse(url).query)
    return qs.get("list", [None])[0]


def _is_playlist(url: str) -> bool:
    qs = parse_qs(urlparse(url).query)
    if "v" in qs and "list" in qs:
        return False
    return _extract_playlist_id(url) is not None


def _is_channel(url: str) -> bool:
    if url.startswith("@"):
        return True
    path = urlparse(url).path
    return bool(re.match(r"^/(@|c/|channel/|user/)", path))


def _hms_to_seconds(s: str) -> int:
    """Convert 'HH:MM:SS', 'MM:SS', or 'SS' to integer seconds."""
    parts = [int(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + sec


def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name.strip()[:200] or "untitled"


_YDL_FLAT: dict[str, Any] = {"quiet": True, "no_warnings": True, "extract_flat": True}


# ── Core operations ──────────────────────────────────────────────────────────

def _fetch_transcript_text(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    snippets = api.fetch(video_id)
    return " ".join(s.text for s in snippets)


def _get_video_title(video_id: str) -> str:
    import yt_dlp

    opts: dict[str, Any] = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )
    if not info:
        return video_id
    return info.get("title") or video_id


def _save_transcript(video_id: str, output_dir: Path, title: Optional[str] = None) -> Path:
    if title is None:
        title = _get_video_title(video_id)
    text = _fetch_transcript_text(video_id)
    path = output_dir / (_sanitize(title) + ".txt")
    path.write_text(text, encoding="utf-8")
    return path


def _walk_playlist(playlist_id: str):
    import yt_dlp

    with yt_dlp.YoutubeDL(_YDL_FLAT) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(
            f"https://www.youtube.com/playlist?list={playlist_id}", download=False
        ) or {}
    title = info.get("title") or f"playlist-{playlist_id}"
    entries = info.get("entries") or []
    return title, entries


def _walk_channel_videos(channel: str, limit: int):
    import yt_dlp

    if channel.startswith("@"):
        url = f"https://www.youtube.com/{channel}/videos"
    else:
        path = urlparse(channel).path.rstrip("/")
        url = channel if path.endswith("/videos") else channel.rstrip("/") + "/videos"

    opts: dict[str, Any] = {**_YDL_FLAT, "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False) or {}
    return info.get("entries") or []


def _search(query: str, limit: int):
    """Search YouTube via yt-dlp's ytsearch extractor. Flat listing, no downloads."""
    import yt_dlp

    opts: dict[str, Any] = {**_YDL_FLAT, "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False) or {}
    return info.get("entries") or []


def _walk_channel_playlists(channel: str, limit: int):
    import yt_dlp

    if channel.startswith("@"):
        url = f"https://www.youtube.com/{channel}/playlists"
    else:
        path = urlparse(channel).path.rstrip("/")
        url = channel if path.endswith("/playlists") else channel.rstrip("/") + "/playlists"

    opts: dict[str, Any] = {**_YDL_FLAT, "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False) or {}
    return info.get("entries") or []


# ── Subcommands ──────────────────────────────────────────────────────────────

@app.command()
def transcript(
    url: str = typer.Argument(..., help="Video, playlist, or channel URL / @handle"),
    output_dir: Path = typer.Option(
        Path.cwd(), "--out", "-o", help="Where to write .txt files"
    ),
    limit: int = typer.Option(
        30, "--limit", "-n", help="Max videos when URL is a channel"
    ),
):
    """Fetch transcript(s) as .txt files."""
    _ensure_deps()
    output_dir.mkdir(parents=True, exist_ok=True)

    if _is_channel(url):
        entries = _walk_channel_videos(url, limit)
        if not entries:
            typer.echo("No videos found on channel.", err=True)
            raise typer.Exit(1)
        _batch(entries, output_dir)
        return

    if _is_playlist(url):
        pid = _extract_playlist_id(url)
        if not pid:
            typer.echo("Could not parse playlist id.", err=True)
            raise typer.Exit(1)
        ptitle, entries = _walk_playlist(pid)
        if not entries:
            typer.echo("No videos in playlist.", err=True)
            raise typer.Exit(1)
        sub = output_dir / _sanitize(ptitle)
        sub.mkdir(exist_ok=True)
        typer.echo(f"Saving playlist to: {sub}/")
        _batch(entries, sub)
        return

    vid = _extract_video_id(url)
    if not vid:
        typer.echo("Invalid YouTube URL.", err=True)
        raise typer.Exit(1)
    try:
        path = _save_transcript(vid, output_dir)
        typer.echo(f"Saved: {path}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


def _batch(entries, output_dir: Path) -> None:
    for entry in entries:
        vid = entry.get("id") or entry.get("url")
        title = entry.get("title", vid)
        if not vid:
            continue
        try:
            path = _save_transcript(vid, output_dir, title=title)
            typer.echo(f"OK   {path}")
        except Exception as e:
            typer.echo(f"SKIP {title}: {e}")


@app.command()
def audio(
    url: str = typer.Argument(..., help="Video or playlist URL"),
    format: str = typer.Option(
        "mp3", "--format", "-f", help="ffmpeg audio format: mp3, wav, m4a, opus, flac, ogg"
    ),
    quality: str = typer.Option(
        "0", "--quality", "-q", help="yt-dlp --audio-quality (0=best VBR, 9=worst)"
    ),
    output_dir: Path = typer.Option(Path.cwd(), "--out", "-o"),
    start: Optional[str] = typer.Option(None, "--start", help="Clip start HH:MM:SS"),
    end: Optional[str] = typer.Option(None, "--end", help="Clip end HH:MM:SS"),
    embed_thumbnail: bool = typer.Option(False, "--embed-thumbnail"),
    add_metadata: bool = typer.Option(True, "--metadata/--no-metadata"),
):
    """Download audio as MP3, WAV, or any ffmpeg format."""
    _ensure_deps()
    _require_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)

    import yt_dlp

    postprocessors = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": format,
            "preferredquality": quality,
        }
    ]
    if add_metadata:
        postprocessors.append({"key": "FFmpegMetadata"})
    if embed_thumbnail:
        postprocessors.append({"key": "EmbedThumbnail"})

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "postprocessors": postprocessors,
        "quiet": False,
        "noprogress": False,
        "writethumbnail": embed_thumbnail,
        "retries": 5,
        "fragment_retries": 10,
    }
    if start and end:
        from yt_dlp.utils import download_range_func

        opts["download_ranges"] = download_range_func(
            [], [(_hms_to_seconds(start), _hms_to_seconds(end))]
        )
        opts["force_keyframes_at_cuts"] = True

    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        ydl.download([url])

    typer.echo(f"Audio written to: {output_dir}")


@app.command()
def summary(
    url: str = typer.Argument(..., help="Video URL"),
    output: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write summary to file (default: stdout)"
    ),
    model: str = typer.Option(
        "claude-haiku-4-5", "--model", help="Anthropic model id"
    ),
    max_tokens: int = typer.Option(1200, "--max-tokens"),
    keep_transcript: bool = typer.Option(
        False, "--keep-transcript", help="Also save the raw .txt alongside the summary"
    ),
):
    """Fetch transcript and produce a structured summary via Anthropic API.

    Requires ANTHROPIC_API_KEY. If unset, prints the raw transcript prefixed with
    a summarisation prompt so the calling agent can summarise in-context instead.
    """
    _ensure_deps()

    vid = _extract_video_id(url)
    if not vid:
        typer.echo("summary only supports single-video URLs.", err=True)
        raise typer.Exit(1)

    title = _get_video_title(vid)
    text = _fetch_transcript_text(vid)

    if keep_transcript:
        dest = (output.parent if output else Path.cwd()) / (_sanitize(title) + ".txt")
        dest.write_text(text, encoding="utf-8")
        typer.echo(f"Transcript: {dest}", err=True)

    prompt = (
        f"Summarise the YouTube video below as structured markdown.\n\n"
        f"Use this template exactly:\n\n"
        f"## {title}\n"
        f"**URL:** {url}\n\n"
        f"### TL;DR\n<one or two sentences>\n\n"
        f"### Key points\n- ...\n\n"
        f"### Notable claims / quotes\n- ...\n\n"
        f"### Open questions\n- ...\n\n"
        f"Transcript:\n{text}"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        out = (
            f"# NO ANTHROPIC_API_KEY SET — transcript + prompt follow.\n"
            f"# Feed this to the calling agent for in-context summarisation.\n\n{prompt}\n"
        )
        if output:
            output.write_text(out, encoding="utf-8")
            typer.echo(f"Wrote: {output}")
        else:
            typer.echo(out)
        return

    try:
        import anthropic
    except ImportError:
        typer.echo("[youtube] installing anthropic SDK...", err=True)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "anthropic"], check=True
        )
        import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    body = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )

    if output:
        output.write_text(body, encoding="utf-8")
        typer.echo(f"Summary: {output}")
    else:
        typer.echo(body)


@app.command()
def channel(
    handle: str = typer.Argument(..., help="@handle or channel URL"),
    limit: int = typer.Option(30, "--limit", "-n"),
):
    """List a channel's recent videos (id, title, date, duration)."""
    _ensure_deps()
    entries = _walk_channel_videos(handle, limit)
    for e in entries:
        vid = e.get("id") or e.get("url", "?")
        title = e.get("title", "?")
        date = e.get("upload_date", "")
        dur = e.get("duration") or 0
        typer.echo(f"{vid}\t{date}\t{int(dur)}s\t{title}")


@app.command()
def playlists(
    handle: str = typer.Argument(..., help="@handle or channel URL"),
    limit: int = typer.Option(30, "--limit", "-n"),
):
    """List a channel's playlists (id, video_count, title)."""
    _ensure_deps()
    entries = _walk_channel_playlists(handle, limit)
    for e in entries:
        pid = e.get("id") or e.get("url", "?")
        title = e.get("title", "?")
        count = e.get("playlist_count") or e.get("n_entries") or 0
        typer.echo(f"{pid}\t{count}\t{title}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query — artist name, song title, topic, etc."),
    limit: int = typer.Option(10, "--limit", "-n"),
):
    """Search YouTube and print matches as TSV: id, duration, uploader, title."""
    _ensure_deps()
    entries = _search(query, limit)
    for e in entries:
        vid = e.get("id") or e.get("url", "?")
        title = e.get("title", "?")
        uploader = e.get("uploader") or e.get("channel") or ""
        dur = e.get("duration") or 0
        typer.echo(f"{vid}\t{int(dur)}s\t{uploader}\t{title}")


def main() -> None:
    """Entry point for the `ytscript` console script."""
    app()


if __name__ == "__main__":
    main()
