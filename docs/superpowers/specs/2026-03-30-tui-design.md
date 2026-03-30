# ytscript TUI Design

## Goal

Convert ytscript from a CLI-only tool into a TUI (Terminal User Interface) using Textual, making it easier to use interactively. The primary use case is fetching the latest N videos from a YouTube channel, selecting which ones to download transcripts for, and watching progress live.

## Screen Flow

### 1. Input Screen

- Text input for YouTube channel URL or handle (e.g. `@fireship`, full channel URL)
- Number input for how many latest videos to fetch (default: 30)
- "Fetch" button to proceed
- Validation: ensure the input looks like a channel reference before proceeding

### 2. Video Selection Screen

- Table listing fetched videos: title, upload date, duration
- All videos selected by default (checkboxes)
- Toggle individual videos on/off
- "Select All" / "Deselect All" buttons
- "Download Transcripts" button to proceed
- Video count shown (e.g. "24 of 30 selected")

### 3. Progress Screen

- List of videos being processed
- Per-video status indicator: pending, downloading, done, failed
- Failed videos show error message inline
- Overall progress counter (e.g. "12/30 complete")
- Output directory shown at top
- "Done" button appears when all complete, returns to input screen

## Architecture

### File Structure

- `ytscript/core.py` — Reusable business logic extracted from cli.py
  - `extract_video_id(url)` (moved from cli.py)
  - `extract_playlist_id(url)` (moved from cli.py)
  - `is_playlist(url)` (moved from cli.py)
  - `sanitize_filename(name)` (moved from cli.py)
  - `fetch_transcript(video_id)` (moved from cli.py)
  - `get_video_title(video_id)` (moved from cli.py)
  - `save_transcript(video_id, title, output_dir)` (moved from cli.py, no click dependency)
  - `fetch_channel_videos(channel_url, limit=30)` — NEW: returns list of dicts with id, title, date, duration
- `ytscript/cli.py` — Existing CLI, refactored to import from core.py
- `ytscript/tui.py` — Textual app with three screens

### Entry Point

New script entry point `ytscript-tui` pointing to `ytscript.tui:main`.

The existing `ytscript` CLI command remains unchanged.

### Channel Video Fetching

Uses yt-dlp with the channel's videos URL (`https://www.youtube.com/@handle/videos`) and `playlistend: N` to limit results. Returns a list of video metadata dicts.

### Concurrency

Transcript downloads run in a Textual worker thread so the UI stays responsive. Videos are processed sequentially within the worker to avoid rate limiting.

### Dependencies

Add `textual` to project dependencies.

## What Stays the Same

- The `ytscript` CLI command is unchanged in behavior
- All existing functions are preserved (just moved to core.py)
- Output format (`.txt` files with video title as filename) stays the same
