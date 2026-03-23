import os
import re
from urllib.parse import parse_qs, urlparse

import click
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
    click.echo(f"Saved: {filepath}")


@click.command()
@click.argument("link")
def main(link):
    """Get YouTube video transcripts as txt files."""
    if is_playlist(link):
        playlist_id = extract_playlist_id(link)

        with yt_dlp.YoutubeDL(
            {"quiet": True, "no_warnings": True, "extract_flat": True}
        ) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/playlist?list={playlist_id}",
                download=False,
            )

        playlist_title = info.get("title", f"playlist-{playlist_id}")
        folder_name = sanitize_filename(playlist_title)
        os.makedirs(folder_name, exist_ok=True)
        click.echo(f"Saving playlist to: {folder_name}/")

        entries = info.get("entries", [])
        if not entries:
            click.echo("No videos found in playlist.")
            return

        for entry in entries:
            video_id = entry.get("id") or entry.get("url")
            title = entry.get("title", video_id)
            try:
                save_transcript(video_id, title=title, output_dir=folder_name)
            except Exception as e:
                click.echo(f"Skipping '{title}': {e}")
    else:
        video_id = extract_video_id(link)
        if not video_id:
            click.echo("Invalid YouTube URL.")
            raise SystemExit(1)
        try:
            save_transcript(video_id)
        except Exception as e:
            click.echo(f"Error: {e}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
