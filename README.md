# yt-tool

One-stop YouTube CLI: transcripts, audio, **video (MP4)**, summaries,
channel / playlist listing, and search. Also ships a Textual TUI.

Formerly `ytscript` — renamed 2026-04-19 when the video subcommand
landed and the scope outgrew its old name. The `ytscript` GitHub URL
redirects here.

## Install

```bash
uv pip install -e .        # from source
# once published:
# pipx install yt-tool
```

Install ffmpeg for audio + video extraction.

```bash
pacman -S ffmpeg   # or: apt install ffmpeg | brew install ffmpeg
```

## CLI

```
yt-tool <subcommand> [args]

Subcommands:
  transcript  Fetch transcript(s) as .txt files
  audio       Extract audio: MP3 / WAV / FLAC / M4A / OPUS / OGG (with clip trim)
  video       Download video: MP4 / MKV / WebM (with clip trim, subs)
  summary     Transcript → structured summary via Anthropic (needs ANTHROPIC_API_KEY)
  channel     List a channel's recent videos (id, title, date, duration)
  playlists   List a channel's playlists (id, title, video_count)
  search      Search YouTube and print TSV: id, duration, uploader, title
```

## Examples

### Transcripts

```bash
# one video
yt-tool transcript 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

# a whole playlist → folder with one .txt per video
yt-tool transcript 'https://www.youtube.com/playlist?list=PLxxxxx'

# 30 most recent from a channel
yt-tool transcript @veritasium --limit 30
```

### Audio

```bash
yt-tool audio <url> --format mp3              # best VBR MP3
yt-tool audio <url> --format wav --out /tmp   # WAV for ASR pipeline
yt-tool audio <url> --start 1:30 --end 2:45   # trim to clip
yt-tool audio <url> --embed-thumbnail         # music-library friendly
```

### Video (MP4, MKV, WebM)

```bash
yt-tool video <url>                           # best quality MP4
yt-tool video <url> --quality 720             # cap at 720p (shorthand)
yt-tool video <url> --quality 'bestvideo[height<=1080]+bestaudio'
yt-tool video <url> --format mkv              # MKV container
yt-tool video <url> --format webm --embed-thumbnail
yt-tool video <url> --start 0:30 --end 1:45   # clip a segment
yt-tool video <url> --subs                    # embed English subtitles
```

### Search → audio (the "I only have a name" flow)

```bash
yt-tool search 'radiohead creep' --limit 5
# id            duration  uploader       title
# XFkzRNyygfk   237s      Radiohead      Radiohead - Creep
# ...

yt-tool audio 'https://www.youtube.com/watch?v=XFkzRNyygfk' --format mp3
```

### Summaries

```bash
export ANTHROPIC_API_KEY=sk-ant-...
yt-tool summary <url>                         # writes summary.md in CWD
yt-tool summary <url> --keep-transcript       # also save raw transcript
```

### Channel / playlist metadata

```bash
yt-tool channel @veritasium --limit 10
yt-tool playlists @veritasium
```

## Interactive TUI

```bash
yt-tool-tui
```

Textual-based UI for browsing. Shares helpers with `yt_tool.core`.

## URL shapes accepted

Any YouTube URL pattern: `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`,
`/live/`, `/playlist?list=`, `/@handle`, `/channel/UC…`, `/c/name`,
`/user/name`, or a bare `@handle`.

## Deps

- `yt-dlp` — URL resolution + audio/video extraction + channel/playlist walk + search
- `youtube-transcript-api` — transcript text
- `typer` / `click` — CLI framework
- `textual` — TUI
- `anthropic` — optional, for `summary`
- `ffmpeg` — system tool, for audio + video post-processing

## Status

Active — tracked in the [EdwardAstill/eastill](https://github.com/EdwardAstill/eastill)
repo index.
