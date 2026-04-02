import os

import click
import yt_dlp

from ytscript.core import (
    _YDL_FLAT_OPTS,
    extract_playlist_id,
    extract_video_id,
    is_playlist,
    sanitize_filename,
    save_transcript,
)


@click.command()
@click.argument("link")
def main(link):
    """Get YouTube video transcripts as txt files."""
    if is_playlist(link):
        playlist_id = extract_playlist_id(link)

        with yt_dlp.YoutubeDL(_YDL_FLAT_OPTS) as ydl:
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
                filepath = save_transcript(video_id, title=title, output_dir=folder_name)
                click.echo(f"Saved: {filepath}")
            except Exception as e:
                click.echo(f"Skipping '{title}': {e}")
    else:
        video_id = extract_video_id(link)
        if not video_id:
            click.echo("Invalid YouTube URL.")
            raise SystemExit(1)
        try:
            filepath = save_transcript(video_id)
            click.echo(f"Saved: {filepath}")
        except Exception as e:
            click.echo(f"Error: {e}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
