# ytscript/tui.py
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
        yield Static("Downloading transcripts to current directory...", id="progress-header")
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
