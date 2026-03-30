import os
import re
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
    return None


def extract_playlist_id(url):
    qs = parse_qs(urlparse(url).query)
    return qs.get("list", [None])[0]


def is_playlist(url):
    return extract_playlist_id(url) is not None


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name.strip()[:200]


def fetch_transcript(video_id):
    ytt_api = YouTubeTranscriptApi()
    transcript = ytt_api.fetch(video_id)
    return " ".join(snippet.text for snippet in transcript)


def get_video_title(video_id):
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )
        return info.get("title", video_id)


def save_transcript(video_id, title=None, output_dir="."):
    if title is None:
        title = get_video_title(video_id)
    text = fetch_transcript(video_id)
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
    elif "/videos" not in channel_url:
        channel_url = channel_url.rstrip("/") + "/videos"

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
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
    elif "/playlists" not in channel_url:
        channel_url = channel_url.rstrip("/") + "/playlists"

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
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
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
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
