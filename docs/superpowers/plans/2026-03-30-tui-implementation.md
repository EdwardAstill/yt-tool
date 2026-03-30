# ytscript TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Textual-based TUI to ytscript that lets users fetch latest videos from a YouTube channel, select which ones to download transcripts for, and watch progress live.

**Architecture:** Extract business logic from `cli.py` into `core.py`, keep CLI as a thin wrapper, add `tui.py` with three screens (Input, Selection, Progress). The TUI uses Textual's `push_screen` for navigation and worker threads for background I/O.

**Tech Stack:** Python 3.14, Textual, yt-dlp, youtube-transcript-api, Click

---

### Task 1: Extract core logic from cli.py into core.py

**Files:**
- Create: `ytscript/core.py`
- Modify: `ytscript/cli.py`

- [ ] **Step 1: Create core.py with all business logic functions**

Move all non-Click functions from `cli.py` into `core.py`. The `save_transcript` function must not use `click.echo` — return the filepath instead.

```python
# ytscript/core.py
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
```

- [ ] **Step 2: Refactor cli.py to import from core.py**

Replace all function definitions in `cli.py` with imports from `core.py`. Keep only the Click command.

```python
# ytscript/cli.py
import os

import click
import yt_dlp

from ytscript.core import (
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
```

- [ ] **Step 3: Verify CLI still works**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript --help`
Expected: Help text prints without import errors.

- [ ] **Step 4: Commit**

```bash
git add ytscript/core.py ytscript/cli.py
git commit -m "refactor: extract business logic into core.py"
```

---

### Task 2: Add fetch_channel_videos to core.py

**Files:**
- Modify: `ytscript/core.py`

- [ ] **Step 1: Add fetch_channel_videos function**

Append this function to `ytscript/core.py`:

```python
def fetch_channel_videos(channel_url, limit=30):
    """Fetch the latest N videos from a YouTube channel.

    Returns a list of dicts with keys: id, title, date, duration.
    """
    # Normalize channel URL — handle @handle format
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
```

- [ ] **Step 2: Quick manual test**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.core import fetch_channel_videos; vids = fetch_channel_videos('@fireship', limit=3); print(len(vids), vids[0]['title'] if vids else 'empty')"`
Expected: Prints 3 and a video title.

- [ ] **Step 3: Commit**

```bash
git add ytscript/core.py
git commit -m "feat: add fetch_channel_videos for retrieving latest N videos from a channel"
```

---

### Task 3: Add textual dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add textual to dependencies and add tui entry point**

Edit `pyproject.toml` to add `textual` to the dependencies list and a new script entry point:

```toml
[project]
name = "ytscript"
version = "0.1.0"
description = "A CLI tool for getting YouTube video transcripts into txt files"
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "click",
    "textual",
    "youtube-transcript-api",
    "yt-dlp",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
ytscript = "ytscript.cli:main"
ytscript-tui = "ytscript.tui:main"
```

- [ ] **Step 2: Install dependencies**

Run: `cd /home/eastill/projects/ytscript && uv sync`
Expected: Installs textual successfully.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add textual dependency and ytscript-tui entry point"
```

---

### Task 4: Build the TUI app with Input Screen

**Files:**
- Create: `ytscript/tui.py`

- [ ] **Step 1: Create the TUI app with InputScreen**

```python
# ytscript/tui.py
from textual.app import App, ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static


class InputScreen(Screen):
    """Screen for entering a YouTube channel URL and video count."""

    DEFAULT_CSS = """
    InputScreen {
        align: center middle;
    }

    #form-container {
        width: 80;
        height: auto;
        padding: 2 4;
        border: solid $accent;
        background: $surface;
    }

    #form-container Label {
        margin: 1 0 0 0;
    }

    #form-container Input {
        margin: 0 0 1 0;
    }

    #fetch-btn {
        margin: 1 0 0 0;
        width: 100%;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin: 0 0 1 0;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="form-container"):
                yield Static("ytscript", id="title")
                yield Label("YouTube Channel (URL or @handle)")
                yield Input(
                    placeholder="@fireship or https://youtube.com/@fireship",
                    id="channel-input",
                )
                yield Label("Number of latest videos")
                yield Input(
                    placeholder="30",
                    value="30",
                    id="count-input",
                )
                yield Button("Fetch Videos", variant="primary", id="fetch-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fetch-btn":
            channel = self.query_one("#channel-input", Input).value.strip()
            count_str = self.query_one("#count-input", Input).value.strip()

            if not channel:
                self.notify("Please enter a channel URL or handle.", severity="error")
                return

            try:
                count = int(count_str)
                if count < 1:
                    raise ValueError()
            except ValueError:
                self.notify("Please enter a valid number.", severity="error")
                return

            self.app.push_screen(SelectionScreen(channel, count))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow pressing Enter to submit the form."""
        self.query_one("#fetch-btn", Button).press()
```

- [ ] **Step 2: Verify it loads without errors**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui import InputScreen; print('OK')"`
Expected: Prints OK (will fail on missing SelectionScreen import, that's fine — we just check syntax).

Actually, this will fail because `SelectionScreen` doesn't exist yet. We'll add a placeholder and fill it in the next task. For now, add the full file in subsequent steps.

---

### Task 5: Build SelectionScreen

**Files:**
- Modify: `ytscript/tui.py`

- [ ] **Step 1: Add SelectionScreen to tui.py**

Add the SelectionScreen class to `ytscript/tui.py`. This screen fetches videos in a worker and displays them with checkboxes using `SelectionList`.

```python
from textual import work
from textual.widgets import SelectionList
from textual.widgets.selection_list import Selection

class SelectionScreen(Screen):
    """Screen for selecting which videos to download transcripts for."""

    DEFAULT_CSS = """
    SelectionScreen {
        layout: vertical;
    }

    #selection-container {
        height: 1fr;
        margin: 1 2;
    }

    #selection-header {
        margin: 1 2 0 2;
        text-style: bold;
    }

    #selection-footer {
        height: auto;
        margin: 0 2 1 2;
        layout: horizontal;
    }

    #selection-footer Button {
        margin: 0 1 0 0;
    }

    #status-label {
        margin: 0 2;
        color: $text-muted;
    }
    """

    def __init__(self, channel: str, count: int) -> None:
        super().__init__()
        self.channel = channel
        self.count = count
        self.videos: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Fetching videos...", id="selection-header")
        yield SelectionList[str](id="selection-container")
        yield Label("", id="status-label")
        with Horizontal(id="selection-footer"):
            yield Button("Select All", id="select-all-btn")
            yield Button("Deselect All", id="deselect-all-btn")
            yield Button("Download Transcripts", variant="primary", id="download-btn")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#download-btn", Button).disabled = True
        self.fetch_videos()

    @work(thread=True)
    def fetch_videos(self) -> None:
        from ytscript.core import fetch_channel_videos

        videos = fetch_channel_videos(self.channel, self.count)
        self.app.call_from_thread(self._populate_list, videos)

    def _populate_list(self, videos: list[dict]) -> None:
        self.videos = videos
        sel_list = self.query_one("#selection-container", SelectionList)
        header = self.query_one("#selection-header", Static)

        if not videos:
            header.update("No videos found.")
            return

        header.update(f"Found {len(videos)} videos from channel")
        selections = []
        for v in videos:
            duration_min = v["duration"] // 60 if v["duration"] else 0
            date_str = v["date"][:4] + "-" + v["date"][4:6] + "-" + v["date"][6:8] if len(v["date"]) == 8 else v["date"]
            label = f"{v['title']}  ({duration_min}m, {date_str})"
            selections.append(Selection(label, v["id"], True))
        sel_list.add_options(selections)
        self.query_one("#download-btn", Button).disabled = False
        self._update_status()

    def _update_status(self) -> None:
        sel_list = self.query_one("#selection-container", SelectionList)
        selected = len(sel_list.selected)
        total = len(self.videos)
        self.query_one("#status-label", Label).update(f"{selected} of {total} selected")

    def on_selection_list_selected_changed(self) -> None:
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        sel_list = self.query_one("#selection-container", SelectionList)
        if event.button.id == "select-all-btn":
            sel_list.select_all()
        elif event.button.id == "deselect-all-btn":
            sel_list.deselect_all()
        elif event.button.id == "download-btn":
            selected_ids = list(sel_list.selected)
            selected_videos = [v for v in self.videos if v["id"] in selected_ids]
            if not selected_videos:
                self.notify("No videos selected.", severity="warning")
                return
            self.app.push_screen(ProgressScreen(selected_videos))
```

---

### Task 6: Build ProgressScreen

**Files:**
- Modify: `ytscript/tui.py`

- [ ] **Step 1: Add ProgressScreen to tui.py**

```python
from textual.widgets import DataTable, ProgressBar
from textual.containers import Horizontal

class ProgressScreen(Screen):
    """Screen showing download progress for selected videos."""

    DEFAULT_CSS = """
    ProgressScreen {
        layout: vertical;
    }

    #progress-header {
        margin: 1 2;
        text-style: bold;
    }

    #progress-table {
        height: 1fr;
        margin: 0 2;
    }

    #progress-bar {
        margin: 1 2;
        height: 3;
    }

    #progress-status {
        margin: 0 2 1 2;
        color: $text-muted;
    }

    #done-btn {
        margin: 1 2;
        width: auto;
    }
    """

    def __init__(self, videos: list[dict]) -> None:
        super().__init__()
        self.videos = videos
        self.completed = 0
        self.failed = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Downloading transcripts to current directory...", id="progress-header")
        yield DataTable(id="progress-table")
        yield ProgressBar(total=len(self.videos), id="progress-bar")
        yield Label(f"0/{len(self.videos)} complete", id="progress-status")
        yield Button("Done — Back to Start", variant="primary", id="done-btn", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#progress-table", DataTable)
        table.add_columns("Title", "Status")
        for v in self.videos:
            table.add_row(v["title"][:60], "Pending", key=v["id"])
        self.download_all()

    @work(thread=True)
    def download_all(self) -> None:
        from ytscript.core import save_transcript

        for v in self.videos:
            self.app.call_from_thread(self._update_row, v["id"], "Downloading...")
            try:
                save_transcript(v["id"], title=v["title"])
                self.app.call_from_thread(self._mark_done, v["id"])
            except Exception as e:
                self.app.call_from_thread(self._mark_failed, v["id"], str(e))

        self.app.call_from_thread(self._all_complete)

    def _update_row(self, video_id: str, status: str) -> None:
        table = self.query_one("#progress-table", DataTable)
        row_idx = table.get_row_index(video_id)
        table.update_cell_at((row_idx, 1), status)

    def _mark_done(self, video_id: str) -> None:
        self.completed += 1
        self._update_row(video_id, "Done ✓")
        self._update_progress()

    def _mark_failed(self, video_id: str, error: str) -> None:
        self.failed += 1
        self._update_row(video_id, f"Failed: {error[:40]}")
        self._update_progress()

    def _update_progress(self) -> None:
        total = len(self.videos)
        done = self.completed + self.failed
        self.query_one("#progress-bar", ProgressBar).update(progress=done)
        self.query_one("#progress-status", Label).update(
            f"{done}/{total} complete ({self.failed} failed)"
        )

    def _all_complete(self) -> None:
        self.query_one("#done-btn", Button).disabled = False
        self.notify(f"Done! {self.completed} saved, {self.failed} failed.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done-btn":
            self.app.pop_screen()
            self.app.pop_screen()
```

---

### Task 7: Wire up the App and main entry point

**Files:**
- Modify: `ytscript/tui.py`

- [ ] **Step 1: Add the YtscriptApp class and main function at the top/bottom of tui.py**

The App class should install InputScreen as the default screen.

```python
class YtscriptApp(App):
    """ytscript TUI — fetch YouTube transcripts interactively."""

    TITLE = "ytscript"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen(InputScreen())


def main():
    app = YtscriptApp()
    app.run()
```

- [ ] **Step 2: Verify the TUI launches**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript-tui`
Expected: TUI launches with the input screen. Press `q` to quit.

- [ ] **Step 3: Commit**

```bash
git add ytscript/tui.py
git commit -m "feat: add Textual TUI with input, selection, and progress screens"
```

---

### Task 8: End-to-end test

- [ ] **Step 1: Run the full flow manually**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript-tui`

1. Enter `@fireship` and count `3`
2. Click "Fetch Videos" — verify video list loads
3. Toggle some checkboxes, verify count updates
4. Click "Download Transcripts" — verify progress screen shows status
5. Verify `.txt` files are created in the current directory
6. Press "Done" to go back to start

- [ ] **Step 2: Verify CLI still works**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript --help`
Expected: Prints help text, no import errors.

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end testing"
```
