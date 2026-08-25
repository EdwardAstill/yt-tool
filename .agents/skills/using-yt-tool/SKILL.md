---
name: using-yt-tool
description: Use when an agent needs to discover YouTube videos, inspect channel or playlist metadata, fetch transcripts, download media, or summarize a YouTube video with the yt-tool CLI.
---

# Using yt-tool

Use the non-interactive `yt-tool` CLI. Run `yt-tool <command> --help` before
using an unfamiliar option; the installed help is authoritative.

## Quick reference

| Goal | Command |
| --- | --- |
| Find videos | `yt-tool search 'query' --limit 10` |
| List channel videos | `yt-tool channel @handle --limit 30` |
| List channel playlists | `yt-tool playlists @handle --limit 30` |
| Fetch transcripts | `yt-tool transcript <url-or-handle> --out <dir>` |
| Extract audio | `yt-tool audio <url> --format mp3 --out <dir>` |
| Download video | `yt-tool video <url> --format mp4 --out <dir>` |
| Summarize one video | `yt-tool summary <url> --out summary.md` |

`search`, `channel`, and `playlists` print tab-separated records. Transcript,
audio, and video commands report their output paths. `summary` writes to stdout
unless `--out` is provided.

## Reliable transcript batches

Use a bounded limit, pacing, and a manifest so partial success is observable:

```bash
yt-tool transcript @handle --limit 20 --out ./transcripts \
  --delay 5 --sleep-subtitles 2 \
  --manifest ./transcripts/results.json --continue-on-error
```

If YouTube returns HTTP 429 or IP-blocking errors, do not retry rapidly. Try a
logged-in profile with `--cookies-from-browser firefox`, or pin the fallback
with `--backend ytdlp`. Use `--proxy` only with proxy URLs the user supplied.
Never expose or commit cookie files, proxy credentials, or API keys.

## Summaries

With `ANTHROPIC_API_KEY`, `summary` calls Anthropic. Without it, the command
returns a summarization prompt plus transcript; summarize that content in
context rather than treating the fallback as an error.

## Constraints and common mistakes

- There is no TUI or `yt-tool-tui` command.
- `ffmpeg` is required for `audio` and `video`, but not metadata or transcripts.
- Quote URLs containing `&` and search queries containing spaces.
- Do not download an unbounded playlist or channel when the user requested a
  sample; use `--limit` where supported.
- A no-subtitle result is not fixed by repeated retries. Try `auto`, then
  `ytdlp` with authorized cookies; the tool has no speech-to-text fallback.
- Read the JSON manifest before retrying a batch so successful videos are not
  needlessly requested again.
