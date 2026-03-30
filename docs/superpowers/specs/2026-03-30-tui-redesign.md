# ytscript TUI Redesign

## Goal

Redesign the TUI to be smart about URL type and provide a rich channel browser with tabbed video/playlist navigation, sorting, filtering, search, pagination, and inline playlist expansion with tri-state checkboxes.

## Smart URL Routing

The InputScreen accepts any YouTube URL or `@handle`. On submit, it detects the URL type and routes accordingly:

- **Single video URL** (contains `watch?v=` or `youtu.be/`): Skip selection entirely. Push ProgressScreen and download the transcript immediately to the current directory.
- **Playlist URL** (contains `list=`): Push PlaylistVideoScreen showing all videos in that playlist, pre-selected. Downloads save to a folder named after the playlist.
- **Channel URL or @handle**: Push ChannelBrowserScreen with Videos and Playlists tabs.

## Channel Browser Screen

A single screen using Textual's `TabbedContent` with two tabs.

### Videos Tab

**Toolbar row:**
- **Sort button**: Toggles through sort modes — Latest (default) → Oldest → Longest → Shortest. Button label shows current mode with arrow (e.g. "Sort: Latest ↓").
- **Filter button**: Opens a modal dialog (see Filter Modal below).
- **Search input**: Text input that filters the current video list by title substring match. Filters in real-time as you type.

**Video list:**
- SelectionList with checkboxes, 30 videos per page.
- Each entry shows: title, duration, date.
- All deselected by default.
- Selections persist across pages — tracked by video ID in a set.

**Pagination:**
- "Page X/Y" label with Prev/Next buttons.
- Prev disabled on page 1, Next disabled on last page.
- Fetches next batch from yt-dlp when navigating forward (lazy fetch, not all upfront).

**Status bar:**
- Shows "X selected" (total across all pages).

**Action buttons:**
- Select All / Deselect All (applies to visible page only).
- Download Selected (pushes ProgressScreen with all selected videos across all pages).
- Back.

### Filter Modal

Centered modal overlay triggered by the Filter button. Contains:

**Date Range** (radio buttons, one active at a time):
- Last week
- Last month
- Last 6 months
- Last year
- All time (default)

**Duration** (radio buttons, one active at a time):
- Under 5 min
- 5–20 min
- Over 20 min
- Any duration (default)

**Buttons:** Apply, Clear (resets to defaults).

Filtering is applied client-side to the already-fetched videos. Videos that don't match are hidden from the list. Selections on hidden videos are preserved.

### Playlists Tab

**Playlist list:**
- Each row: tri-state checkbox + expand arrow (▶/▼) + playlist title + video count.
- Checkboxes have three states:
  - `[x]` — all videos in playlist selected
  - `[-]` — some videos selected (indeterminate)
  - `[ ]` — no videos selected

**Expand behavior:**
- Clicking ▶ expands the playlist inline, showing indented video entries underneath.
- First expand triggers a worker thread fetch via `fetch_playlist_entries()`.
- Subsequent expands use cached data.
- Each video has its own checkbox.

**Tri-state logic:**
- Checking a collapsed playlist selects all its videos.
- Unchecking a collapsed playlist deselects all its videos.
- Expanding and deselecting one video changes the playlist checkbox to `[-]`.
- Expanding and deselecting all videos changes the playlist checkbox to `[ ]`.
- Expanding and selecting all videos changes the playlist checkbox to `[x]`.

**Downloads:**
- Each selected playlist's videos download to a folder named `sanitize_filename(playlist_title)`.
- Individually selected videos from expanded playlists also go to their playlist's folder.

**Action buttons:**
- Select All / Deselect All (all playlists).
- Download Selected (pushes ProgressScreen).
- Back.

## PlaylistVideoScreen (direct playlist URL)

Shown when user pastes a playlist URL directly:
- Fetches playlist entries via worker.
- Shows all videos in a SelectionList, all pre-selected.
- Downloads save to a folder named after the playlist.
- Select All / Deselect All / Download / Back buttons.

## ProgressScreen

- DataTable with Title and Status columns.
- ProgressBar tracking completion.
- Status label: "X/Y complete (Z failed)".
- Per-video `output_dir` support — calls `os.makedirs(output_dir, exist_ok=True)` before saving.
- "Done" button pops all screens back to InputScreen.

## Architecture

### Files

- `ytscript/core.py` — Business logic. Existing functions stay. Existing `fetch_channel_videos` gains `offset` parameter for pagination. No other changes to existing functions.
- `ytscript/tui.py` — Complete rewrite of screens. Will be larger due to channel browser complexity. May split into `tui/` package if it exceeds ~500 lines.
- `ytscript/cli.py` — Unchanged.

### New/Modified Core Functions

- `fetch_channel_videos(channel_url, limit=30, offset=0)` — Add `offset` param. Uses yt-dlp `playliststart` and `playlistend` options for pagination.
- `fetch_channel_playlists(channel_url, limit=30)` — Already exists.
- `fetch_playlist_entries(playlist_id)` — Already exists.

### Key Textual Widgets

- `TabbedContent` with `TabPane` for Videos/Playlists tabs.
- `SelectionList` for video lists.
- Custom `PlaylistTree` widget (or similar) for the expandable playlist list with tri-state checkboxes — likely built on `Tree` widget.
- `Screen` subclass for filter modal (Textual's `ModalScreen`).
- `Input` for search.
- `Button` for sort toggle, pagination, actions.
