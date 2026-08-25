# yt-tool

`yt-tool` is a command-line utility for YouTube transcripts, audio, video,
summaries, channel and playlist metadata, and search. It is CLI-only; there is
no interactive TUI.

## Install

Install the CLI directly from GitHub:

```bash
uv tool install git+https://github.com/EdwardAstill/yt-tool
```

If you will use API-backed summaries, include the optional Anthropic client at
install time:

```bash
uv tool install --with anthropic git+https://github.com/EdwardAstill/yt-tool
```

Audio and video commands also require `ffmpeg`:

```bash
sudo pacman -S ffmpeg       # Arch Linux
sudo apt install ffmpeg     # Debian / Ubuntu
brew install ffmpeg         # macOS
```

Confirm the installation:

```bash
yt-tool --help
```

To work from a clone instead:

```bash
uv sync
uv run yt-tool --help
```

## Command overview

```text
yt-tool <command> [options]

transcript  Fetch one video, a playlist, or a channel as .txt files
audio       Extract audio as MP3, WAV, M4A, OPUS, FLAC, or OGG
video       Download video as MP4, MKV, or WebM
summary     Fetch a transcript and create a structured summary
channel     List a channel's recent videos as TSV
playlists   List a channel's playlists as TSV
search      Search YouTube and print matching videos as TSV
```

Run `yt-tool <command> --help` at any time for the installed command's exact
options.

## Transcripts

```bash
yt-tool transcript <video-or-collection> [options]
```

Examples:

```bash
# One video; writes a title-named .txt file in the current directory
yt-tool transcript 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

# Choose an output directory
yt-tool transcript 'https://youtu.be/dQw4w9WgXcQ' --out ./transcripts

# A playlist; creates a playlist-named folder under --out
yt-tool transcript 'https://www.youtube.com/playlist?list=PLxxxxx' --out ./transcripts

# The 30 most recent videos from a channel
yt-tool transcript @veritasium --limit 30 --out ./transcripts
```

Transcript options:

| Option | Meaning |
| --- | --- |
| `--out`, `-o PATH` | Output directory; defaults to the current directory. |
| `--limit`, `-n N` | Maximum videos for a channel; defaults to `30`. |
| `--delay SECONDS` | Pause between videos in a batch. |
| `--max-retries N` | Rate-limit retry attempts per video; defaults to `3`. |
| `--backend auto\|api\|ytdlp` | Select the transcript backend; defaults to `auto`. |
| `--cookies PATH` | Use a Netscape-format `cookies.txt` with the `ytdlp` backend. |
| `--cookies-from-browser BROWSER` | Read a logged-in profile from `firefox`, `chrome`, `brave`, `chromium`, `edge`, or `safari`. |
| `--proxy URLS` | Use one proxy, or comma-separated proxies for rotation. |
| `--source-address IP` | Bind outbound requests to a local IP. |
| `--impersonate TARGET` | Select a `curl-cffi` TLS fingerprint such as `chrome-136`. |
| `--player-client CLIENTS` | Set the comma-separated yt-dlp YouTube player-client chain. |
| `--sleep-subtitles SECONDS` | Pause between yt-dlp subtitle URL requests. |
| `--manifest PATH` | Write a JSON record of successes and failures. |
| `--continue-on-error` | Keep processing a batch after a failure; this is the default. |
| `--stop-on-error` | Stop a batch at its first failure. |

The `auto` backend first tries `youtube-transcript-api`, then falls back to
yt-dlp subtitles. Batch manifests contain a total/ok/fail summary and one
result per video, including its output path or error.

## Audio

```bash
yt-tool audio <video-or-playlist> [options]
```

Examples:

```bash
yt-tool audio <url> --format mp3
yt-tool audio <url> --format wav --out /tmp/audio
yt-tool audio <url> --start 1:30 --end 2:45
yt-tool audio <url> --embed-thumbnail
yt-tool audio <url> --no-metadata
```

Audio options:

| Option | Meaning |
| --- | --- |
| `--format`, `-f FORMAT` | `mp3`, `wav`, `m4a`, `opus`, `flac`, or `ogg`; defaults to `mp3`. |
| `--quality`, `-q VALUE` | yt-dlp audio quality from `0` (best VBR) to `9`; defaults to `0`. |
| `--out`, `-o PATH` | Output directory; defaults to the current directory. |
| `--start TIME` | Clip start as seconds, `MM:SS`, or `HH:MM:SS`. |
| `--end TIME` | Clip end in the same format. Audio clipping requires both start and end. |
| `--embed-thumbnail` | Write the video thumbnail into the audio file. |
| `--metadata` / `--no-metadata` | Enable or disable metadata; enabled by default. |

## Video

```bash
yt-tool video <video-or-playlist> [options]
```

Examples:

```bash
yt-tool video <url>
yt-tool video <url> --quality 720
yt-tool video <url> --quality 'bestvideo[height<=1080]+bestaudio'
yt-tool video <url> --format mkv --out ./video
yt-tool video <url> --format webm --embed-thumbnail
yt-tool video <url> --start 0:30 --end 1:45
yt-tool video <url> --subs
```

Video options:

| Option | Meaning |
| --- | --- |
| `--format`, `-f FORMAT` | Output container: `mp4`, `mkv`, or `webm`; defaults to `mp4`. |
| `--quality`, `-q VALUE` | A height such as `720`, or any yt-dlp format selector. |
| `--out`, `-o PATH` | Output directory; defaults to the current directory. |
| `--start TIME` | Optional clip start as seconds, `MM:SS`, or `HH:MM:SS`. |
| `--end TIME` | Optional clip end in the same format. |
| `--metadata` / `--no-metadata` | Enable or disable metadata; enabled by default. |
| `--embed-thumbnail` | Embed the source thumbnail. |
| `--subs` | Download and embed available English subtitles. |

## Summaries

`summary` accepts a single-video URL. With `ANTHROPIC_API_KEY` set, it sends
the transcript to Anthropic and prints the structured Markdown summary to
stdout unless `--out` is supplied. Install the tool with `--with anthropic` as
shown above before using this mode.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
yt-tool summary <url>
yt-tool summary <url> --out summary.md --keep-transcript
yt-tool summary <url> --model claude-haiku-4-5 --max-tokens 1200
```

Without `ANTHROPIC_API_KEY`, the command prints or writes the transcript with a
ready-to-use summarization prompt so a calling agent can summarize it.

Summary options:

| Option | Meaning |
| --- | --- |
| `--out`, `-o PATH` | Write output to a file instead of stdout. |
| `--model MODEL` | Anthropic model ID; defaults to `claude-haiku-4-5`. |
| `--max-tokens N` | Maximum summary tokens; defaults to `1200`. |
| `--keep-transcript` | Save the raw transcript beside the summary output. |
| `--backend auto\|api\|ytdlp` | Select the transcript backend. |
| `--cookies PATH` | Use a Netscape-format cookies file. |
| `--cookies-from-browser BROWSER` | Read cookies from a local browser profile. |
| `--proxy URLS` | Use one proxy, or a comma-separated rotation list. |
| `--impersonate TARGET` | Select a `curl-cffi` TLS fingerprint. |

## Discover videos and playlists

Search results are tab-separated: video ID, duration, uploader, and title.

```bash
yt-tool search 'radiohead creep' --limit 5
```

Channel results are tab-separated: video ID, upload date, duration, and title.

```bash
yt-tool channel @veritasium --limit 10
```

Playlist results are tab-separated: playlist ID, video count, and title.

```bash
yt-tool playlists @veritasium --limit 30
```

`search` defaults to 10 results. `channel` and `playlists` default to 30. All
three commands accept `--limit N` or `-n N`.

A common search-to-download flow is:

```bash
yt-tool search 'radiohead creep' --limit 5
yt-tool audio 'https://www.youtube.com/watch?v=XFkzRNyygfk' --format mp3
```

## Accepted YouTube targets

The CLI accepts normal `watch?v=` links, `youtu.be` links, `/shorts/`,
`/embed/`, and `/live/` video links; `/playlist?list=` playlist links; and
`/@handle`, `/channel/UC…`, `/c/name`, `/user/name`, or bare `@handle` channel
references. A watch URL containing both `v=` and `list=` is treated as one
video.

## Troubleshooting

### HTTP 429, IP blocking, or repeated transcript failures

YouTube can rate-limit transcript and timed-text requests even when a video and
its caption track are visible in a browser. This is normally an anti-automation
response, not evidence that the video has no captions.

Start with pacing and a partial-success manifest:

```bash
yt-tool transcript @channel \
  --limit 30 \
  --delay 5 \
  --sleep-subtitles 2 \
  --manifest results.json \
  --continue-on-error
```

Then use a logged-in browser profile or cookies file:

```bash
yt-tool transcript <url> --cookies-from-browser firefox
yt-tool transcript <url> --cookies ./cookies.txt --backend ytdlp
```

Other available controls:

```bash
# Rotate proxies after failures
yt-tool transcript <url> --proxy 'http://a:1080,http://b:1080'

# Pin the fallback backend
yt-tool transcript <url> --backend ytdlp

# Change TLS fingerprint or YouTube player clients
yt-tool transcript <url> --impersonate chrome-136
yt-tool transcript <url> --player-client 'tv_simply,web_safari,ios'

# Bind requests to another local address
yt-tool transcript <url> --source-address 10.0.0.42
```

Avoid immediately hammering the same video after a block. Slow the batch,
allow a cooldown, and inspect `results.json` to identify what must be retried.
Cookies and proxy URLs may contain credentials; do not paste them into logs or
commit them to the repository.

### No subtitle track

Try the automatic backend first, then explicitly try yt-dlp with authenticated
cookies:

```bash
yt-tool transcript <url> --backend auto
yt-tool transcript <url> --backend ytdlp --cookies-from-browser firefox
```

If both fail with a no-subtitle error, the video may not expose a usable
caption track. `yt-tool` does not perform speech-to-text transcription.

### `ffmpeg not found on PATH`

Install `ffmpeg` using the command in the Install section and confirm it is
available:

```bash
ffmpeg -version
```

Transcript listing and search do not require `ffmpeg`; audio and video do.

### Summary returns a prompt and transcript

This is the expected fallback when `ANTHROPIC_API_KEY` is unset. Either let a
calling agent summarize that output or export the key and run the command
again.

### Command or dependency problems

Check the installed command and update the tool:

```bash
yt-tool --help
uv tool upgrade yt-tool
```

For a development checkout, refresh dependencies and run through uv:

```bash
uv sync
uv run yt-tool --help
```

## Agent skill

Agents can load [`.agents/skills/using-yt-tool/SKILL.md`](.agents/skills/using-yt-tool/SKILL.md)
for a concise, operational guide to choosing commands, handling outputs, and
responding to rate limits.

## Dependencies

- `yt-dlp` resolves YouTube targets, downloads media, walks collections, and searches.
- `youtube-transcript-api` provides the primary transcript backend.
- `curl-cffi` supports TLS fingerprint impersonation.
- `typer` and `click` provide the CLI.
- `anthropic` is optional and used by `summary` when an API key is present.
- `ffmpeg` is a system dependency for audio and video post-processing.

## Status

Active — tracked in the [EdwardAstill/eastill](https://github.com/EdwardAstill/eastill)
repository index.
