import os

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

from yt_tool.core import (
    extract_playlist_id,
    fetch_channel_playlists,
    fetch_channel_videos,
    fetch_playlist_entries,
    is_playlist,
    sanitize_filename,
    save_transcript,
)


class InputScreen(Screen):
    """Screen for entering a YouTube channel URL/handle or playlist URL."""

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
                yield Label("YouTube Channel or Playlist URL")
                yield Input(
                    placeholder="@fireship, channel URL, or playlist URL",
                    id="channel-input",
                )
                yield Label("Number of latest videos/playlists to fetch")
                yield Input(
                    placeholder="30",
                    value="30",
                    id="count-input",
                )
                yield Button("Go", variant="primary", id="fetch-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fetch-btn":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
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

        if is_playlist(channel):
            playlist_id = extract_playlist_id(channel)
            self.app.push_screen(PlaylistVideoScreen(playlist_id))
        else:
            self.app.push_screen(ChannelModeScreen(channel, count))


class ChannelModeScreen(Screen):
    """Screen for choosing between browsing videos or playlists from a channel."""

    DEFAULT_CSS = """
    ChannelModeScreen {
        align: center middle;
    }

    #mode-container {
        width: 60;
        height: auto;
        padding: 2 4;
        border: solid $accent;
        background: $surface;
    }

    #mode-title {
        text-align: center;
        text-style: bold;
        margin: 0 0 1 0;
        color: $text;
    }

    #mode-channel {
        text-align: center;
        margin: 0 0 2 0;
        color: $text-muted;
    }

    .mode-btn {
        width: 100%;
        margin: 1 0 0 0;
    }

    #back-btn {
        width: 100%;
        margin: 2 0 0 0;
    }
    """

    def __init__(self, channel: str, count: int) -> None:
        super().__init__()
        self.channel = channel
        self.count = count

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="mode-container"):
                yield Static("What do you want to browse?", id="mode-title")
                yield Static(self.channel, id="mode-channel")
                yield Button(
                    "Browse Videos",
                    variant="primary",
                    id="videos-btn",
                    classes="mode-btn",
                )
                yield Button(
                    "Browse Playlists",
                    variant="primary",
                    id="playlists-btn",
                    classes="mode-btn",
                )
                yield Button("Back", id="back-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "videos-btn":
            self.app.push_screen(
                VideoSelectionScreen(self.channel, self.count)
            )
        elif event.button.id == "playlists-btn":
            self.app.push_screen(
                PlaylistSelectionScreen(self.channel, self.count)
            )
        elif event.button.id == "back-btn":
            self.app.pop_screen()


class VideoSelectionScreen(Screen):
    """Screen for selecting videos to download transcripts for, with sorting."""

    DEFAULT_CSS = """
    VideoSelectionScreen {
        layout: vertical;
    }

    #video-selection-header {
        margin: 1 2 0 2;
        text-style: bold;
    }

    #sort-bar {
        height: auto;
        margin: 0 2;
        layout: horizontal;
    }

    #sort-bar Button {
        margin: 0 1 0 0;
        min-width: 12;
    }

    #sort-bar .active-sort {
        text-style: bold;
    }

    #video-selection-container {
        height: 1fr;
        margin: 0 2;
    }

    #video-status-label {
        margin: 0 2;
        color: $text-muted;
    }

    #video-selection-footer {
        height: auto;
        margin: 0 2 1 2;
        layout: horizontal;
    }

    #video-selection-footer Button {
        margin: 0 1 0 0;
    }
    """

    SORT_OPTIONS = {
        "latest": ("date", True),
        "oldest": ("date", False),
        "longest": ("duration", True),
        "shortest": ("duration", False),
    }

    def __init__(self, channel: str, count: int) -> None:
        super().__init__()
        self.channel = channel
        self.count = count
        self.videos: list[dict] = []
        self.current_sort = "latest"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Fetching videos...", id="video-selection-header")
        with Horizontal(id="sort-bar"):
            yield Button("Latest", id="sort-latest", classes="active-sort")
            yield Button("Oldest", id="sort-oldest")
            yield Button("Longest", id="sort-longest")
            yield Button("Shortest", id="sort-shortest")
        yield SelectionList[str](id="video-selection-container")
        yield Label("", id="video-status-label")
        with Horizontal(id="video-selection-footer"):
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
        self.fetch_videos()

    @work(thread=True)
    def fetch_videos(self) -> None:
        videos = fetch_channel_videos(self.channel, self.count)
        self.app.call_from_thread(self._populate_list, videos)

    def _populate_list(self, videos: list[dict]) -> None:
        self.videos = videos
        header = self.query_one("#video-selection-header", Static)

        if not videos:
            header.update("No videos found.")
            return

        header.update(f"Found {len(videos)} videos")
        self._sort_and_display()
        self.query_one("#download-btn", Button).disabled = False

    def _sort_and_display(self, preserve_selection: bool = False) -> None:
        sel_list = self.query_one("#video-selection-container", SelectionList)

        selected_ids: set[str] = set()
        if preserve_selection:
            selected_ids = set(sel_list.selected)

        key, reverse = self.SORT_OPTIONS[self.current_sort]
        self.videos.sort(key=lambda v: v.get(key, ""), reverse=reverse)

        sel_list.clear_options()
        selections = []
        for v in self.videos:
            duration_min = v["duration"] // 60 if v["duration"] else 0
            date_str = (
                v["date"][:4] + "-" + v["date"][4:6] + "-" + v["date"][6:8]
                if len(v["date"]) == 8
                else v["date"]
            )
            label = f"{v['title']}  ({duration_min}m, {date_str})"
            initially_selected = (
                v["id"] in selected_ids if preserve_selection else True
            )
            selections.append(Selection(label, v["id"], initially_selected))
        sel_list.add_options(selections)
        self._update_status()

    def _update_status(self) -> None:
        sel_list = self.query_one("#video-selection-container", SelectionList)
        selected = len(sel_list.selected)
        total = len(self.videos)
        self.query_one("#video-status-label", Label).update(
            f"{selected} of {total} selected"
        )

    def on_selection_list_selected_changed(self) -> None:
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id and button_id.startswith("sort-"):
            sort_key = button_id.removeprefix("sort-")
            if sort_key in self.SORT_OPTIONS:
                self.current_sort = sort_key
                for btn in self.query("#sort-bar Button"):
                    btn.remove_class("active-sort")
                event.button.add_class("active-sort")
                self._sort_and_display(preserve_selection=True)
            return

        sel_list = self.query_one("#video-selection-container", SelectionList)
        if button_id == "select-all-btn":
            sel_list.select_all()
        elif button_id == "deselect-all-btn":
            sel_list.deselect_all()
        elif button_id == "download-btn":
            selected_ids = list(sel_list.selected)
            selected_videos = [v for v in self.videos if v["id"] in selected_ids]
            if not selected_videos:
                self.notify("No videos selected.", severity="warning")
                return
            self.app.push_screen(ProgressScreen(selected_videos))
        elif button_id == "back-btn":
            self.app.pop_screen()


class PlaylistSelectionScreen(Screen):
    """Screen for selecting playlists from a channel."""

    DEFAULT_CSS = """
    PlaylistSelectionScreen {
        layout: vertical;
    }

    #playlist-selection-header {
        margin: 1 2 0 2;
        text-style: bold;
    }

    #playlist-selection-container {
        height: 1fr;
        margin: 1 2;
    }

    #playlist-status-label {
        margin: 0 2;
        color: $text-muted;
    }

    #playlist-selection-footer {
        height: auto;
        margin: 0 2 1 2;
        layout: horizontal;
    }

    #playlist-selection-footer Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, channel: str, count: int) -> None:
        super().__init__()
        self.channel = channel
        self.count = count
        self.playlists: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Fetching playlists...", id="playlist-selection-header")
        yield SelectionList[str](id="playlist-selection-container")
        yield Label("", id="playlist-status-label")
        with Horizontal(id="playlist-selection-footer"):
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
        self.fetch_playlists()

    @work(thread=True)
    def fetch_playlists(self) -> None:
        playlists = fetch_channel_playlists(self.channel, self.count)
        self.app.call_from_thread(self._populate_list, playlists)

    def _populate_list(self, playlists: list[dict]) -> None:
        self.playlists = playlists
        sel_list = self.query_one("#playlist-selection-container", SelectionList)
        header = self.query_one("#playlist-selection-header", Static)

        if not playlists:
            header.update("No playlists found.")
            return

        header.update(f"Found {len(playlists)} playlists")
        selections = []
        for p in playlists:
            count = p["video_count"]
            label = f"{p['title']}  ({count} videos)"
            selections.append(Selection(label, p["id"], True))
        sel_list.add_options(selections)
        self.query_one("#download-btn", Button).disabled = False
        self._update_status()

    def _update_status(self) -> None:
        sel_list = self.query_one("#playlist-selection-container", SelectionList)
        selected = len(sel_list.selected)
        total = len(self.playlists)
        self.query_one("#playlist-status-label", Label).update(
            f"{selected} of {total} selected"
        )

    def on_selection_list_selected_changed(self) -> None:
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        sel_list = self.query_one("#playlist-selection-container", SelectionList)
        if event.button.id == "select-all-btn":
            sel_list.select_all()
        elif event.button.id == "deselect-all-btn":
            sel_list.deselect_all()
        elif event.button.id == "download-btn":
            selected_ids = list(sel_list.selected)
            selected_playlists = [
                p for p in self.playlists if p["id"] in selected_ids
            ]
            if not selected_playlists:
                self.notify("No playlists selected.", severity="warning")
                return
            self.query_one("#download-btn", Button).disabled = True
            self.query_one("#playlist-selection-header", Static).update(
                "Preparing downloads..."
            )
            self.prepare_downloads(selected_playlists)
        elif event.button.id == "back-btn":
            self.app.pop_screen()

    @work(thread=True)
    def prepare_downloads(self, playlists: list[dict]) -> None:
        all_videos = []
        for p in playlists:
            playlist_title, entries = fetch_playlist_entries(p["id"])
            output_dir = sanitize_filename(playlist_title)
            for entry in entries:
                all_videos.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "output_dir": output_dir,
                })
        self.app.call_from_thread(self._push_progress, all_videos)

    def _push_progress(self, videos: list[dict]) -> None:
        if not videos:
            self.notify("No videos found in selected playlists.", severity="warning")
            self.query_one("#download-btn", Button).disabled = False
            self.query_one("#playlist-selection-header", Static).update(
                f"Found {len(self.playlists)} playlists"
            )
            return
        self.app.push_screen(ProgressScreen(videos))


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
            # Pop all screens back to InputScreen
            while not isinstance(self.app.screen, InputScreen):
                self.app.pop_screen()


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
