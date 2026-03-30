# ytscript TUI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the TUI with smart URL routing, a tabbed channel browser with paginated videos (sort/filter/search) and expandable playlists with tri-state checkboxes.

**Architecture:** Convert `tui.py` into a `tui/` package with focused modules. InputScreen detects URL type and routes to the right screen. ChannelBrowserScreen uses Textual's TabbedContent with a VideosTab (pagination, sort, filter, search) and PlaylistsTab (Tree widget with tri-state checkboxes and lazy-loaded expansion). FilterModal uses Textual's ModalScreen.

**Tech Stack:** Python 3.14, Textual (TabbedContent, TabPane, Tree, ModalScreen, SelectionList, Input), yt-dlp, youtube-transcript-api

---

## File Structure

```
ytscript/
  core.py                  — Add pagination to fetch_channel_videos (modify)
  tui/                     — NEW package (replaces tui.py)
    __init__.py            — YtscriptApp, main()
    input_screen.py        — InputScreen with URL type detection
    channel_browser.py     — ChannelBrowserScreen with TabbedContent
    videos_tab.py          — VideosTab widget (sort, filter, search, pagination)
    playlists_tab.py       — PlaylistsTab widget (Tree + tri-state checkboxes)
    filter_modal.py        — FilterModal (ModalScreen with date range + duration)
    playlist_video.py      — PlaylistVideoScreen (direct playlist URL entry)
    progress_screen.py     — ProgressScreen (unchanged logic, moved here)
```

---

### Task 1: Add pagination to fetch_channel_videos in core.py

**Files:**
- Modify: `ytscript/core.py:58-91`

- [ ] **Step 1: Update fetch_channel_videos signature and logic**

Add a `page` parameter. Use `playliststart` and `playlistend` for pagination.

```python
def fetch_channel_videos(channel_url, limit=30, page=1):
    """Fetch videos from a YouTube channel with pagination.

    Returns a list of dicts with keys: id, title, date, duration.
    """
    if channel_url.startswith("@"):
        channel_url = f"https://www.youtube.com/{channel_url}/videos"
    elif "/videos" not in channel_url:
        channel_url = channel_url.rstrip("/") + "/videos"

    start = (page - 1) * limit + 1
    end = page * limit

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playliststart": start,
        "playlistend": end,
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

- [ ] **Step 2: Verify existing CLI still works**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript --help`
Expected: Help text prints. The CLI calls `fetch_channel_videos` without `page` so the default `page=1` preserves behavior.

- [ ] **Step 3: Commit**

```bash
git add ytscript/core.py
git commit -m "feat: add pagination support to fetch_channel_videos"
```

---

### Task 2: Convert tui.py to tui/ package with ProgressScreen and PlaylistVideoScreen

**Files:**
- Delete: `ytscript/tui.py`
- Create: `ytscript/tui/__init__.py`
- Create: `ytscript/tui/progress_screen.py`
- Create: `ytscript/tui/playlist_video.py`

These two screens are largely unchanged from the current code, just moved.

- [ ] **Step 1: Create tui/ package directory**

```bash
cd /home/eastill/projects/ytscript
rm ytscript/tui.py
mkdir -p ytscript/tui
```

- [ ] **Step 2: Create progress_screen.py**

This is the existing ProgressScreen moved to its own file. The only change: import `InputScreen` lazily to avoid circular imports (used in the "Done" button handler).

```python
# ytscript/tui/progress_screen.py
import os

from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    ProgressBar,
    Static,
)

from ytscript.core import save_transcript


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
        yield Static(
            f"Downloading {len(self.videos)} transcripts...", id="progress-header"
        )
        yield DataTable(id="progress-table")
        yield ProgressBar(total=len(self.videos), id="progress-bar")
        yield Label(f"0/{len(self.videos)} complete", id="progress-status")
        yield Button(
            "Done — Back to Start",
            variant="primary",
            id="done-btn",
            disabled=True,
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#progress-table", DataTable)
        table.add_columns("Title", "Status")
        for v in self.videos:
            table.add_row(v["title"][:60], "Pending", key=v["id"])
        self.download_all()

    @work(thread=True)
    def download_all(self) -> None:
        for v in self.videos:
            self.app.call_from_thread(self._update_row, v["id"], "Downloading...")
            output_dir = v.get("output_dir", ".")
            if output_dir != ".":
                os.makedirs(output_dir, exist_ok=True)
            try:
                save_transcript(v["id"], title=v["title"], output_dir=output_dir)
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
            from ytscript.tui.input_screen import InputScreen

            while not isinstance(self.app.screen, InputScreen):
                self.app.pop_screen()
```

- [ ] **Step 3: Create playlist_video.py**

The existing PlaylistVideoScreen for direct playlist URLs, moved to its own file.

```python
# ytscript/tui/playlist_video.py
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

from ytscript.core import fetch_playlist_entries, sanitize_filename
from ytscript.tui.progress_screen import ProgressScreen


class PlaylistVideoScreen(Screen):
    """Screen for selecting videos from a direct playlist URL."""

    DEFAULT_CSS = """
    PlaylistVideoScreen {
        layout: vertical;
    }

    #pv-header {
        margin: 1 2 0 2;
        text-style: bold;
    }

    #pv-container {
        height: 1fr;
        margin: 1 2;
    }

    #pv-status-label {
        margin: 0 2;
        color: $text-muted;
    }

    #pv-footer {
        height: auto;
        margin: 0 2 1 2;
        layout: horizontal;
    }

    #pv-footer Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, playlist_id: str) -> None:
        super().__init__()
        self.playlist_id = playlist_id
        self.playlist_title = ""
        self.videos: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Fetching playlist...", id="pv-header")
        yield SelectionList[str](id="pv-container")
        yield Label("", id="pv-status-label")
        with Horizontal(id="pv-footer"):
            yield Button("Select All", id="select-all-btn")
            yield Button("Deselect All", id="deselect-all-btn")
            yield Button(
                "Download Transcripts",
                variant="primary",
                id="download-btn",
            )
            yield Button("Back", id="back-btn")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#download-btn", Button).disabled = True
        self.fetch_entries()

    @work(thread=True)
    def fetch_entries(self) -> None:
        playlist_title, entries = fetch_playlist_entries(self.playlist_id)
        self.app.call_from_thread(self._populate_list, playlist_title, entries)

    def _populate_list(self, title: str, entries: list[dict]) -> None:
        self.playlist_title = title
        self.videos = entries
        sel_list = self.query_one("#pv-container", SelectionList)
        header = self.query_one("#pv-header", Static)

        if not entries:
            header.update("No videos found in playlist.")
            return

        header.update(f"{title} — {len(entries)} videos")
        selections = []
        for v in entries:
            selections.append(Selection(v["title"], v["id"], True))
        sel_list.add_options(selections)
        self.query_one("#download-btn", Button).disabled = False
        self._update_status()

    def _update_status(self) -> None:
        sel_list = self.query_one("#pv-container", SelectionList)
        selected = len(sel_list.selected)
        total = len(self.videos)
        self.query_one("#pv-status-label", Label).update(
            f"{selected} of {total} selected"
        )

    def on_selection_list_selected_changed(self) -> None:
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        sel_list = self.query_one("#pv-container", SelectionList)
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
            output_dir = sanitize_filename(self.playlist_title)
            download_list = [
                {"id": v["id"], "title": v["title"], "output_dir": output_dir}
                for v in selected_videos
            ]
            self.app.push_screen(ProgressScreen(download_list))
        elif event.button.id == "back-btn":
            self.app.pop_screen()
```

- [ ] **Step 4: Create minimal __init__.py with App stub**

```python
# ytscript/tui/__init__.py
from textual.app import App

from ytscript.tui.input_screen import InputScreen


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

Note: `input_screen.py` doesn't exist yet — we'll create it in the next task. For now this file defines the app structure.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: convert tui.py to tui/ package with progress and playlist screens"
```

---

### Task 3: Build InputScreen with smart URL routing

**Files:**
- Create: `ytscript/tui/input_screen.py`

The InputScreen detects the URL type on submit:
- Video URL → push ProgressScreen directly (single video download)
- Playlist URL → push PlaylistVideoScreen
- Channel/@handle → push ChannelBrowserScreen

- [ ] **Step 1: Create input_screen.py**

```python
# ytscript/tui/input_screen.py
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from ytscript.core import extract_playlist_id, extract_video_id, is_playlist


class InputScreen(Screen):
    """Screen for entering a YouTube URL or @handle."""

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
                yield Label("YouTube URL or @handle")
                yield Input(
                    placeholder="@handle, video URL, playlist URL, or channel URL",
                    id="url-input",
                )
                yield Button("Go", variant="primary", id="fetch-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fetch-btn":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        url = self.query_one("#url-input", Input).value.strip()

        if not url:
            self.notify("Please enter a URL or @handle.", severity="error")
            return

        video_id = extract_video_id(url)
        if video_id and not is_playlist(url):
            # Single video — download immediately
            from ytscript.tui.progress_screen import ProgressScreen

            self.app.push_screen(
                ProgressScreen([{"id": video_id, "title": video_id}])
            )
            return

        if is_playlist(url):
            # Playlist URL — show video selection
            from ytscript.tui.playlist_video import PlaylistVideoScreen

            playlist_id = extract_playlist_id(url)
            self.app.push_screen(PlaylistVideoScreen(playlist_id))
            return

        # Channel or @handle — show channel browser
        from ytscript.tui.channel_browser import ChannelBrowserScreen

        self.app.push_screen(ChannelBrowserScreen(url))
```

- [ ] **Step 2: Verify imports work**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui.input_screen import InputScreen; print('OK')"`
Expected: Prints OK.

- [ ] **Step 3: Commit**

```bash
git add ytscript/tui/input_screen.py
git commit -m "feat: add InputScreen with smart URL type detection and routing"
```

---

### Task 4: Build FilterModal

**Files:**
- Create: `ytscript/tui/filter_modal.py`

A ModalScreen that returns a dict with `date_range` and `duration` filter values.

- [ ] **Step 1: Create filter_modal.py**

```python
# ytscript/tui/filter_modal.py
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet, Static


class FilterModal(ModalScreen[dict | None]):
    """Modal dialog for filtering videos by date range and duration."""

    DEFAULT_CSS = """
    FilterModal {
        align: center middle;
    }

    #filter-dialog {
        width: 50;
        height: auto;
        padding: 2 4;
        border: solid $accent;
        background: $surface;
    }

    #filter-title {
        text-align: center;
        text-style: bold;
        margin: 0 0 1 0;
    }

    .filter-section-label {
        margin: 1 0 0 0;
        text-style: bold;
        color: $text-muted;
    }

    RadioSet {
        margin: 0 0 1 0;
        height: auto;
    }

    #filter-buttons {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }

    #filter-buttons Button {
        margin: 0 1 0 0;
    }
    """

    DATE_OPTIONS = [
        ("Last week", 7),
        ("Last month", 30),
        ("Last 6 months", 180),
        ("Last year", 365),
        ("All time", 0),
    ]

    DURATION_OPTIONS = [
        ("Under 5 min", (0, 300)),
        ("5–20 min", (300, 1200)),
        ("Over 20 min", (1200, None)),
        ("Any duration", (0, None)),
    ]

    def __init__(
        self,
        current_date_idx: int = 4,
        current_duration_idx: int = 3,
    ) -> None:
        super().__init__()
        self.current_date_idx = current_date_idx
        self.current_duration_idx = current_duration_idx

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-dialog"):
            yield Static("Filters", id="filter-title")
            yield Label("Date Range", classes="filter-section-label")
            with RadioSet(id="date-range-set"):
                for i, (label, _) in enumerate(self.DATE_OPTIONS):
                    yield RadioButton(label, value=i == self.current_date_idx)
            yield Label("Duration", classes="filter-section-label")
            with RadioSet(id="duration-set"):
                for i, (label, _) in enumerate(self.DURATION_OPTIONS):
                    yield RadioButton(label, value=i == self.current_duration_idx)
            with Vertical(id="filter-buttons"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Clear", id="clear-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-btn":
            date_set = self.query_one("#date-range-set", RadioSet)
            duration_set = self.query_one("#duration-set", RadioSet)
            date_idx = date_set.pressed_index
            duration_idx = duration_set.pressed_index
            self.dismiss({
                "date_idx": date_idx,
                "date_days": self.DATE_OPTIONS[date_idx][1],
                "duration_idx": duration_idx,
                "duration_range": self.DURATION_OPTIONS[duration_idx][1],
            })
        elif event.button.id == "clear-btn":
            self.dismiss({
                "date_idx": 4,
                "date_days": 0,
                "duration_idx": 3,
                "duration_range": (0, None),
            })
        elif event.button.id == "cancel-btn":
            self.dismiss(None)
```

- [ ] **Step 2: Verify imports**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui.filter_modal import FilterModal; print('OK')"`
Expected: Prints OK.

- [ ] **Step 3: Commit**

```bash
git add ytscript/tui/filter_modal.py
git commit -m "feat: add FilterModal with date range and duration filters"
```

---

### Task 5: Build VideosTab widget

**Files:**
- Create: `ytscript/tui/videos_tab.py`

A widget composable into a TabPane. Has sort toggle, filter button, search input, paginated SelectionList, and page navigation. Tracks selections across pages.

- [ ] **Step 1: Create videos_tab.py**

```python
# ytscript/tui/videos_tab.py
from datetime import datetime, timedelta

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Input, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

from ytscript.core import fetch_channel_videos
from ytscript.tui.filter_modal import FilterModal

PAGE_SIZE = 30

SORT_MODES = ["Latest", "Oldest", "Longest", "Shortest"]
SORT_KEYS = {
    "Latest": ("date", True),
    "Oldest": ("date", False),
    "Longest": ("duration", True),
    "Shortest": ("duration", False),
}


class VideosTab(Widget):
    """Videos tab content with sort, filter, search, and pagination."""

    DEFAULT_CSS = """
    VideosTab {
        layout: vertical;
        height: 1fr;
    }

    #vt-header {
        margin: 1 0 0 0;
        text-style: bold;
    }

    #vt-toolbar {
        height: auto;
        layout: horizontal;
        margin: 0 0 1 0;
    }

    #vt-toolbar Button {
        margin: 0 1 0 0;
        min-width: 16;
    }

    #vt-search {
        width: 1fr;
    }

    #vt-list {
        height: 1fr;
    }

    #vt-page-bar {
        height: auto;
        layout: horizontal;
        margin: 1 0 0 0;
    }

    #vt-page-bar Button {
        margin: 0 1 0 0;
    }

    #vt-page-info {
        margin: 0 1;
        content-align: right middle;
    }

    #vt-status {
        color: $text-muted;
    }
    """

    def __init__(self, channel: str) -> None:
        super().__init__()
        self.channel = channel
        self.current_page = 1
        self.pages: dict[int, list[dict]] = {}
        self.selected_ids: set[str] = set()
        self.sort_mode_idx = 0
        self.filter_date_idx = 4  # All time
        self.filter_date_days = 0
        self.filter_duration_idx = 3  # Any duration
        self.filter_duration_range: tuple[int, int | None] = (0, None)
        self.search_text = ""
        self.no_more_pages = False

    def compose(self) -> ComposeResult:
        yield Static("Loading videos...", id="vt-header")
        with Horizontal(id="vt-toolbar"):
            yield Button(f"Sort: {SORT_MODES[0]} ↓", id="vt-sort-btn")
            yield Button("Filter", id="vt-filter-btn")
            yield Input(placeholder="Search by title...", id="vt-search")
        yield SelectionList[str](id="vt-list")
        yield Label("", id="vt-status")
        with Horizontal(id="vt-page-bar"):
            yield Button("◀ Prev", id="vt-prev-btn", disabled=True)
            yield Static("Page 1", id="vt-page-info")
            yield Button("Next ▶", id="vt-next-btn")

    def on_mount(self) -> None:
        self._load_page(1)

    @work(thread=True)
    def _load_page(self, page: int) -> None:
        videos = fetch_channel_videos(self.channel, limit=PAGE_SIZE, page=page)
        self.app.call_from_thread(self._on_page_loaded, page, videos)

    def _on_page_loaded(self, page: int, videos: list[dict]) -> None:
        self.pages[page] = videos
        if len(videos) < PAGE_SIZE:
            self.no_more_pages = True
        self.current_page = page
        self._display_current_page()
        self.query_one("#vt-header", Static).update(f"Videos from {self.channel}")

    def _get_filtered_videos(self, videos: list[dict]) -> list[dict]:
        result = videos

        # Apply date filter
        if self.filter_date_days > 0:
            cutoff = datetime.now() - timedelta(days=self.filter_date_days)
            cutoff_str = cutoff.strftime("%Y%m%d")
            result = [v for v in result if v.get("date", "") >= cutoff_str]

        # Apply duration filter
        min_dur, max_dur = self.filter_duration_range
        if min_dur > 0 or max_dur is not None:
            def dur_match(v):
                d = v.get("duration", 0)
                if d < min_dur:
                    return False
                if max_dur is not None and d >= max_dur:
                    return False
                return True
            result = [v for v in result if dur_match(v)]

        # Apply search filter
        if self.search_text:
            query = self.search_text.lower()
            result = [v for v in result if query in v.get("title", "").lower()]

        return result

    def _sort_videos(self, videos: list[dict]) -> list[dict]:
        mode = SORT_MODES[self.sort_mode_idx]
        key, reverse = SORT_KEYS[mode]
        return sorted(videos, key=lambda v: v.get(key, ""), reverse=reverse)

    def _display_current_page(self) -> None:
        videos = self.pages.get(self.current_page, [])
        filtered = self._get_filtered_videos(videos)
        sorted_vids = self._sort_videos(filtered)

        sel_list = self.query_one("#vt-list", SelectionList)
        sel_list.clear_options()

        selections = []
        for v in sorted_vids:
            duration_min = v["duration"] // 60 if v["duration"] else 0
            date_str = (
                v["date"][:4] + "-" + v["date"][4:6] + "-" + v["date"][6:8]
                if len(v["date"]) == 8
                else v["date"]
            )
            label = f"{v['title']}  ({duration_min}m, {date_str})"
            selected = v["id"] in self.selected_ids
            selections.append(Selection(label, v["id"], selected))
        sel_list.add_options(selections)

        # Update page controls
        self.query_one("#vt-prev-btn", Button).disabled = self.current_page <= 1
        self.query_one("#vt-next-btn", Button).disabled = self.no_more_pages and self.current_page >= max(self.pages.keys())
        self.query_one("#vt-page-info", Static).update(f"Page {self.current_page}")
        self._update_status()

    def _sync_selections_from_list(self) -> None:
        """Sync the SelectionList state back to our persistent selected_ids set."""
        sel_list = self.query_one("#vt-list", SelectionList)
        page_videos = self.pages.get(self.current_page, [])
        filtered = self._get_filtered_videos(page_videos)
        page_video_ids = {v["id"] for v in filtered}

        # Remove all current page IDs, then re-add the selected ones
        self.selected_ids -= page_video_ids
        self.selected_ids |= set(sel_list.selected)

    def _update_status(self) -> None:
        self.query_one("#vt-status", Label).update(
            f"{len(self.selected_ids)} selected"
        )

    def on_selection_list_selected_changed(self) -> None:
        self._sync_selections_from_list()
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "vt-sort-btn":
            self._sync_selections_from_list()
            self.sort_mode_idx = (self.sort_mode_idx + 1) % len(SORT_MODES)
            mode = SORT_MODES[self.sort_mode_idx]
            event.button.label = f"Sort: {mode} ↓"
            self._display_current_page()

        elif event.button.id == "vt-filter-btn":
            self._sync_selections_from_list()
            self.app.push_screen(
                FilterModal(self.filter_date_idx, self.filter_duration_idx),
                callback=self._on_filter_result,
            )

        elif event.button.id == "vt-prev-btn":
            if self.current_page > 1:
                self._sync_selections_from_list()
                page = self.current_page - 1
                if page in self.pages:
                    self.current_page = page
                    self._display_current_page()
                else:
                    self._load_page(page)

        elif event.button.id == "vt-next-btn":
            self._sync_selections_from_list()
            page = self.current_page + 1
            if page in self.pages:
                self.current_page = page
                self._display_current_page()
            else:
                self._load_page(page)

    def _on_filter_result(self, result: dict | None) -> None:
        if result is None:
            return
        self.filter_date_idx = result["date_idx"]
        self.filter_date_days = result["date_days"]
        self.filter_duration_idx = result["duration_idx"]
        self.filter_duration_range = result["duration_range"]

        has_filters = self.filter_date_idx != 4 or self.filter_duration_idx != 3
        self.query_one("#vt-filter-btn", Button).label = (
            "Filter ●" if has_filters else "Filter"
        )
        self._display_current_page()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "vt-search":
            self._sync_selections_from_list()
            self.search_text = event.value
            self._display_current_page()

    def get_selected_videos(self) -> list[dict]:
        """Return all selected videos across all pages."""
        self._sync_selections_from_list()
        result = []
        for page_videos in self.pages.values():
            for v in page_videos:
                if v["id"] in self.selected_ids:
                    result.append(v)
        return result
```

- [ ] **Step 2: Verify imports**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui.videos_tab import VideosTab; print('OK')"`
Expected: Prints OK.

- [ ] **Step 3: Commit**

```bash
git add ytscript/tui/videos_tab.py
git commit -m "feat: add VideosTab with sort, filter, search, and pagination"
```

---

### Task 6: Build PlaylistsTab widget

**Files:**
- Create: `ytscript/tui/playlists_tab.py`

Uses Textual's `Tree` widget. Each playlist is a tree node. Expanding fetches video entries. Tri-state checkboxes rendered in labels.

- [ ] **Step 1: Create playlists_tab.py**

```python
# ytscript/tui/playlists_tab.py
from textual import work
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static, Tree
from textual.widgets.tree import TreeNode

from ytscript.core import fetch_channel_playlists, fetch_playlist_entries


class PlaylistsTab(Widget):
    """Playlists tab with expandable tree and tri-state checkboxes."""

    DEFAULT_CSS = """
    PlaylistsTab {
        layout: vertical;
        height: 1fr;
    }

    #pt-header {
        margin: 1 0 0 0;
        text-style: bold;
    }

    #pt-tree {
        height: 1fr;
    }

    #pt-status {
        color: $text-muted;
    }
    """

    def __init__(self, channel: str) -> None:
        super().__init__()
        self.channel = channel
        # playlist_id -> {title, video_count, state, videos, loaded}
        self.playlist_data: dict[str, dict] = {}
        # playlist_id -> {video_id -> selected}
        self.video_selections: dict[str, dict[str, bool]] = {}

    def compose(self) -> ComposeResult:
        yield Static("Loading playlists...", id="pt-header")
        yield Tree("Playlists", id="pt-tree")
        yield Label("", id="pt-status")

    def on_mount(self) -> None:
        tree = self.query_one("#pt-tree", Tree)
        tree.show_root = False
        tree.guide_depth = 2
        self._fetch_playlists()

    @work(thread=True)
    def _fetch_playlists(self) -> None:
        playlists = fetch_channel_playlists(self.channel)
        self.app.call_from_thread(self._populate_tree, playlists)

    def _populate_tree(self, playlists: list[dict]) -> None:
        tree = self.query_one("#pt-tree", Tree)

        if not playlists:
            self.query_one("#pt-header", Static).update("No playlists found.")
            return

        self.query_one("#pt-header", Static).update(
            f"Found {len(playlists)} playlists"
        )

        for p in playlists:
            pid = p["id"]
            self.playlist_data[pid] = {
                "title": p["title"],
                "video_count": p["video_count"],
                "state": "none",
                "loaded": False,
            }
            self.video_selections[pid] = {}

            label = self._playlist_label(pid)
            node = tree.root.add(label, data={"type": "playlist", "id": pid})
            # Add a placeholder child so the expand arrow shows
            node.add_leaf("Loading...", data={"type": "placeholder"})

        self._update_status()

    def _playlist_label(self, playlist_id: str) -> str:
        data = self.playlist_data[playlist_id]
        state = data["state"]
        checkbox = {"all": "[x]", "some": "[-]", "none": "[ ]"}[state]
        return f"{checkbox} {data['title']}  ({data['video_count']} videos)"

    def _video_label(self, playlist_id: str, video_id: str, title: str) -> str:
        selected = self.video_selections.get(playlist_id, {}).get(video_id, False)
        checkbox = "[x]" if selected else "[ ]"
        return f"    {checkbox} {title}"

    def _recalculate_playlist_state(self, playlist_id: str) -> None:
        selections = self.video_selections.get(playlist_id, {})
        if not selections:
            self.playlist_data[playlist_id]["state"] = "none"
            return
        selected_count = sum(1 for v in selections.values() if v)
        total = len(selections)
        if selected_count == 0:
            self.playlist_data[playlist_id]["state"] = "none"
        elif selected_count == total:
            self.playlist_data[playlist_id]["state"] = "all"
        else:
            self.playlist_data[playlist_id]["state"] = "some"

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        node_data = node.data
        if node_data is None or node_data.get("type") != "playlist":
            return

        playlist_id = node_data["id"]
        if self.playlist_data[playlist_id]["loaded"]:
            return

        # Fetch entries in background
        self._fetch_entries(playlist_id, node)

    @work(thread=True)
    def _fetch_entries(self, playlist_id: str, node: TreeNode) -> None:
        _, entries = fetch_playlist_entries(playlist_id)
        self.app.call_from_thread(self._populate_entries, playlist_id, node, entries)

    def _populate_entries(
        self, playlist_id: str, node: TreeNode, entries: list[dict]
    ) -> None:
        self.playlist_data[playlist_id]["loaded"] = True

        # Remove placeholder
        node.remove_children()

        # Initialize selections based on current playlist state
        is_selected = self.playlist_data[playlist_id]["state"] == "all"
        for entry in entries:
            vid = entry["id"]
            self.video_selections[playlist_id][vid] = is_selected
            label = self._video_label(playlist_id, vid, entry["title"])
            node.add_leaf(label, data={
                "type": "video",
                "id": vid,
                "title": entry["title"],
                "playlist_id": playlist_id,
            })

        self._recalculate_playlist_state(playlist_id)
        node.set_label(self._playlist_label(playlist_id))
        self._update_status()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        node_data = node.data
        if node_data is None:
            return

        if node_data.get("type") == "playlist":
            self._toggle_playlist(node, node_data["id"])
        elif node_data.get("type") == "video":
            self._toggle_video(node, node_data)

    def _toggle_playlist(self, node: TreeNode, playlist_id: str) -> None:
        current_state = self.playlist_data[playlist_id]["state"]
        # Toggle: none/some -> all, all -> none
        new_selected = current_state != "all"
        self.playlist_data[playlist_id]["state"] = "all" if new_selected else "none"

        # Update all video selections for this playlist
        for vid in self.video_selections.get(playlist_id, {}):
            self.video_selections[playlist_id][vid] = new_selected

        # Update node label
        node.set_label(self._playlist_label(playlist_id))

        # Update child labels if expanded
        if node.is_expanded:
            for child in node.children:
                child_data = child.data
                if child_data and child_data.get("type") == "video":
                    child.set_label(self._video_label(
                        playlist_id, child_data["id"], child_data["title"]
                    ))

        self._update_status()

    def _toggle_video(self, node: TreeNode, node_data: dict) -> None:
        vid = node_data["id"]
        playlist_id = node_data["playlist_id"]
        title = node_data["title"]

        # Toggle selection
        current = self.video_selections[playlist_id].get(vid, False)
        self.video_selections[playlist_id][vid] = not current

        # Update video label
        node.set_label(self._video_label(playlist_id, vid, title))

        # Recalculate parent state
        self._recalculate_playlist_state(playlist_id)

        # Update parent label
        parent = node.parent
        if parent and parent.data and parent.data.get("type") == "playlist":
            parent.set_label(self._playlist_label(playlist_id))

        self._update_status()

    def _update_status(self) -> None:
        total_playlists = 0
        total_videos = 0
        for pid, selections in self.video_selections.items():
            state = self.playlist_data[pid]["state"]
            if state == "all":
                total_playlists += 1
            selected_count = sum(1 for v in selections.values() if v)
            total_videos += selected_count

        parts = []
        if total_playlists:
            parts.append(f"{total_playlists} full playlists")
        if total_videos:
            parts.append(f"{total_videos} videos")
        status = " + ".join(parts) + " selected" if parts else "Nothing selected"
        self.query_one("#pt-status", Label).update(status)

    def get_selected_videos(self) -> list[dict]:
        """Return all selected videos with output_dir set per playlist."""
        from ytscript.core import sanitize_filename

        result = []

        for pid, selections in self.video_selections.items():
            playlist_title = self.playlist_data[pid]["title"]
            output_dir = sanitize_filename(playlist_title)

            # If playlist is fully selected but not loaded, we need entries
            if (
                self.playlist_data[pid]["state"] == "all"
                and not self.playlist_data[pid]["loaded"]
            ):
                # This will be handled in the browser screen's prepare step
                result.append({
                    "playlist_id": pid,
                    "playlist_title": playlist_title,
                    "needs_fetch": True,
                    "output_dir": output_dir,
                })
                continue

            for vid, selected in selections.items():
                if selected:
                    # Find the title from tree nodes
                    title = vid  # fallback
                    tree = self.query_one("#pt-tree", Tree)
                    for node in tree.root.children:
                        if node.data and node.data.get("id") == pid:
                            for child in node.children:
                                if child.data and child.data.get("id") == vid:
                                    title = child.data.get("title", vid)
                                    break
                            break
                    result.append({
                        "id": vid,
                        "title": title,
                        "output_dir": output_dir,
                    })

        return result
```

- [ ] **Step 2: Verify imports**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui.playlists_tab import PlaylistsTab; print('OK')"`
Expected: Prints OK.

- [ ] **Step 3: Commit**

```bash
git add ytscript/tui/playlists_tab.py
git commit -m "feat: add PlaylistsTab with tree, tri-state checkboxes, and lazy expansion"
```

---

### Task 7: Build ChannelBrowserScreen

**Files:**
- Create: `ytscript/tui/channel_browser.py`

Combines VideosTab and PlaylistsTab in a TabbedContent. Has shared Download/Back buttons at the bottom.

- [ ] **Step 1: Create channel_browser.py**

```python
# ytscript/tui/channel_browser.py
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from ytscript.core import fetch_playlist_entries, sanitize_filename
from ytscript.tui.playlists_tab import PlaylistsTab
from ytscript.tui.progress_screen import ProgressScreen
from ytscript.tui.videos_tab import VideosTab


class ChannelBrowserScreen(Screen):
    """Tabbed channel browser with Videos and Playlists tabs."""

    DEFAULT_CSS = """
    ChannelBrowserScreen {
        layout: vertical;
    }

    #cb-header {
        margin: 1 2 0 2;
        text-style: bold;
    }

    #cb-tabs {
        height: 1fr;
        margin: 0 2;
    }

    #cb-footer {
        height: auto;
        margin: 0 2 1 2;
        layout: horizontal;
    }

    #cb-footer Button {
        margin: 0 1 0 0;
    }

    #cb-status {
        margin: 0 2;
        color: $text-muted;
    }
    """

    def __init__(self, channel: str) -> None:
        super().__init__()
        self.channel = channel

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"ytscript — {self.channel}", id="cb-header")
        with TabbedContent(id="cb-tabs"):
            with TabPane("Videos", id="videos-pane"):
                yield VideosTab(self.channel)
            with TabPane("Playlists", id="playlists-pane"):
                yield PlaylistsTab(self.channel)
        yield Label("", id="cb-status")
        with Horizontal(id="cb-footer"):
            yield Button("Select All", id="select-all-btn")
            yield Button("Deselect All", id="deselect-all-btn")
            yield Button(
                "Download Selected",
                variant="primary",
                id="download-btn",
            )
            yield Button("Back", id="back-btn")
        yield Footer()

    def _get_active_tab(self) -> str:
        tabs = self.query_one("#cb-tabs", TabbedContent)
        return tabs.active or "videos-pane"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select-all-btn":
            active = self._get_active_tab()
            if active == "videos-pane":
                vt = self.query_one(VideosTab)
                sel_list = vt.query_one("#vt-list")
                sel_list.select_all()
            # For playlists, select all is complex — toggle all playlist states
            elif active == "playlists-pane":
                pt = self.query_one(PlaylistsTab)
                tree = pt.query_one("#pt-tree")
                for node in tree.root.children:
                    if node.data and node.data.get("type") == "playlist":
                        pid = node.data["id"]
                        if pt.playlist_data[pid]["state"] != "all":
                            pt._toggle_playlist(node, pid)

        elif event.button.id == "deselect-all-btn":
            active = self._get_active_tab()
            if active == "videos-pane":
                vt = self.query_one(VideosTab)
                sel_list = vt.query_one("#vt-list")
                sel_list.deselect_all()
            elif active == "playlists-pane":
                pt = self.query_one(PlaylistsTab)
                tree = pt.query_one("#pt-tree")
                for node in tree.root.children:
                    if node.data and node.data.get("type") == "playlist":
                        pid = node.data["id"]
                        if pt.playlist_data[pid]["state"] != "none":
                            pt._toggle_playlist(node, pid)

        elif event.button.id == "download-btn":
            self._start_download()

        elif event.button.id == "back-btn":
            self.app.pop_screen()

    def _start_download(self) -> None:
        # Collect from both tabs
        vt = self.query_one(VideosTab)
        pt = self.query_one(PlaylistsTab)

        video_selections = vt.get_selected_videos()
        playlist_selections = pt.get_selected_videos()

        # Check if any playlist selections need fetching
        needs_fetch = [s for s in playlist_selections if s.get("needs_fetch")]
        ready = [s for s in playlist_selections if not s.get("needs_fetch")]

        all_videos = video_selections + ready

        if needs_fetch:
            self.query_one("#cb-status", Label).update("Preparing playlist downloads...")
            self.query_one("#download-btn", Button).disabled = True
            self._resolve_and_download(needs_fetch, all_videos)
        elif all_videos:
            self.app.push_screen(ProgressScreen(all_videos))
        else:
            self.notify("Nothing selected.", severity="warning")

    @work(thread=True)
    def _resolve_and_download(
        self, needs_fetch: list[dict], ready: list[dict]
    ) -> None:
        resolved = []
        for item in needs_fetch:
            _, entries = fetch_playlist_entries(item["playlist_id"])
            output_dir = item["output_dir"]
            for entry in entries:
                resolved.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "output_dir": output_dir,
                })

        all_videos = ready + resolved
        self.app.call_from_thread(self._push_progress, all_videos)

    def _push_progress(self, videos: list[dict]) -> None:
        self.query_one("#download-btn", Button).disabled = False
        self.query_one("#cb-status", Label).update("")
        if videos:
            self.app.push_screen(ProgressScreen(videos))
        else:
            self.notify("No videos found in selected playlists.", severity="warning")
```

- [ ] **Step 2: Verify imports**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui.channel_browser import ChannelBrowserScreen; print('OK')"`
Expected: Prints OK.

- [ ] **Step 3: Commit**

```bash
git add ytscript/tui/channel_browser.py
git commit -m "feat: add ChannelBrowserScreen with tabbed Videos and Playlists"
```

---

### Task 8: Wire up __init__.py and verify full app

**Files:**
- Modify: `ytscript/tui/__init__.py`

The __init__.py was already created in Task 2 with the correct content. Now verify everything works end to end.

- [ ] **Step 1: Verify all imports resolve**

Run: `cd /home/eastill/projects/ytscript && uv run python -c "from ytscript.tui import main; print('OK')"`
Expected: Prints OK.

- [ ] **Step 2: Verify CLI is unaffected**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript --help`
Expected: Help text prints.

- [ ] **Step 3: Launch TUI and verify input screen appears**

Run: `cd /home/eastill/projects/ytscript && uv run ytscript-tui`
Expected: TUI launches with input screen. Press `q` to quit.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete TUI redesign with channel browser, filters, and playlist tree"
```

---

### Task 9: End-to-end manual test

- [ ] **Step 1: Test single video URL**

Run: `cd /tmp && uv run --project /home/eastill/projects/ytscript ytscript-tui`
Enter a YouTube video URL (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`).
Expected: Goes directly to ProgressScreen and downloads the transcript.

- [ ] **Step 2: Test playlist URL**

Enter a YouTube playlist URL.
Expected: Shows PlaylistVideoScreen with all videos pre-selected. Download creates a folder.

- [ ] **Step 3: Test channel — Videos tab**

Enter `@fireship`.
Expected: ChannelBrowserScreen with Videos and Playlists tabs. Videos tab shows 30 videos.
Test sort toggle, filter modal, search, and page navigation.

- [ ] **Step 4: Test channel — Playlists tab**

Switch to Playlists tab.
Expected: Shows playlists with expand arrows. Click a playlist to expand — videos appear underneath.
Test tri-state checkboxes: select all, expand, deselect one video — playlist shows `[-]`.

- [ ] **Step 5: Test download from channel browser**

Select some videos and/or playlists, click Download Selected.
Expected: ProgressScreen shows progress. Playlist downloads go to folders. Done button returns to InputScreen.

- [ ] **Step 6: Fix any issues found, commit**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end testing"
```
