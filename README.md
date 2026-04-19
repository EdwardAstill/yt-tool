# ytscript

YouTube CLI for transcripts, audio extraction, summaries, channel / playlist
browsing, and search. Also ships an interactive Textual TUI.

Extracted from [agentfiles](https://github.com/EdwardAstill/agentfiles) v0.2
with a bigger CLI surface. The original transcript-only flow still works.

## Install

```bash
uv pip install -e .        # from source
# or once published:
# pipx install ytscript
```

Optional: install ffmpeg for audio extraction.

```bash
pacman -S ffmpeg   # or: apt install ffmpeg | brew install ffmpeg
```

## CLI

```
ytscript <subcommand> [args]

Subcommands:
  transcript  Fetch transcript(s) as .txt files
  audio       Download audio as MP3 / WAV / any ffmpeg format
  summary     Fetch transcript and produce a structured summary (needs ANTHROPIC_API_KEY)
  channel     List a channel's recent videos (id, title, date, duration)
  playlists   List a channel's playlists (id, video_count, title)
  search      Search YouTube and print TSV matches: id, duration, uploader, title
```

### Examples

```bash
# one video
ytscript transcript 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

# a whole playlist → creates a subfolder with one .txt per video
ytscript transcript 'https://www.youtube.com/playlist?list=PLxxxxx'

# a channel — most recent 30 videos
ytscript transcript @veritasium --limit 30

# audio as MP3
ytscript audio 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' --format mp3

# audio as WAV, clipped to [1:30 → 2:45]
ytscript audio <url> --format wav --start 1:30 --end 2:45

# summarize a video via Claude
ANTHROPIC_API_KEY=sk-ant-... ytscript summary <url>

# what did this channel upload lately?
ytscript channel @twocentsoninstruction --limit 10

# what playlists does it have?
ytscript playlists @veritasium

# search
ytscript search "best bass lessons" --limit 20
```

### Interactive TUI

```bash
ytscript-tui
```

Textual-based UI for browsing transcripts without typing URLs. The TUI
shares helpers with `ytscript.core` and predates the modern CLI surface.

## Deps

- `yt-dlp` — URL resolution, audio extraction, channel/playlist walks, search
- `youtube-transcript-api` — transcript text
- `typer` / `click` — CLI framework
- `textual` — TUI
- `anthropic` — optional, for `summary` subcommand
- `ffmpeg` — system tool, for audio extraction

## Status

Active. Part of the [EdwardAstill/eastill](https://github.com/EdwardAstill/eastill)
repo index.
