# Media Player: complete — design

Date: 2026-09-25. Status: approved in brainstorming (scope, QMediaPlayer backend,
error-driven convert offer, playlist rule).

## Goal

Turn the Media Player tab from a synchronized multi-panel viewer with a bare transport
bar into a usable review player: sound, fullscreen, keyboard control, frame-accurate
stepping, a playlist, a way in from the Converted Files tab, and a sensible answer when
Windows cannot decode a file. Backend stays `QMediaPlayer`/`QVideoWidget`
(`ui/media_player_widget.py`); the sidebar `PreviewController` is a different feature
and is untouched.

## Current state (facts)

`MediaPlayerWidget` hosts up to 4 `PlayerPanel`s (`PANEL_COUNT_OPTIONS = [1, 2, 4]`),
each with a lazily created `QMediaPlayer`, Load/Clear, drag-drop and a sync-offset
spin box. Shared transport: Play all / Pause all, Stop all, Restart, seek slider,
speed 0.25–2×, drift correction (`DRIFT_CORRECTION_MS = 250`). No volume, fullscreen,
frame step, shortcuts, snapshot, playlist, persistence, or Converted-tab hookup.
`visible_tool_tabs.media_player` defaults to `False` (stays so). No help chapter.

## Non-goals

FFmpeg-decoded playback, snapshot to PNG, subtitles, per-panel independent transport,
audio track selection, turning the tab on by default.

## Design

### 1. Transport basics

- **Volume / mute.** One slider (0–100) and a mute toggle in the transport bar, applied
  to every panel's player (`setVolume`, `setMuted`). Per-panel volume is not offered;
  in a synchronized review all panels share one sound level.
- **Fullscreen.** A *Fullscreen* button and `F` toggle the panel grid (not the whole
  window) fullscreen via a top-level frameless `QWidget` that re-parents the grid;
  `Esc` or `F` or double-clicking a video surface returns it. The transport bar stays
  visible at the bottom in fullscreen (auto-hides after 3 s of no mouse movement,
  reappears on movement).
- **Shortcuts** (when the tab has focus): `Space` play/pause, `Home` restart, `←/→`
  one frame back/forward, `Shift+←/→` 5 s, `↑/↓` volume ±5, `M` mute, `F` fullscreen,
  `Esc` leave fullscreen, `N`/`P` playlist next/previous. Implemented with
  `QShortcut`s on the widget with `Qt.WidgetWithChildrenShortcut` context.

### 2. Frame step and readout

- Frame rate per loaded file comes from `ffprobe -select_streams v:0 -show_entries
  stream=r_frame_rate,nb_frames,duration` (existing FFprobe helper/timeouts in
  `conversion/ffmpeg_utils.py`), run once per load in a `QThread` worker, cached on the
  panel. Until it arrives, and if it fails, the fallback is 25 fps and the readout
  omits the frame number.
- Stepping pauses all panels, then seeks the shared timeline by `round(1000 / fps)` ms
  of the reference panel (the first panel with media; today's `_reference_panel`).
  Other panels follow through the existing `seek_all` + offset mapping.
- Readout replaces the `M:SS / M:SS` label with
  `H:MM:SS.mmm / H:MM:SS.mmm · frame N / total` for the reference panel. `format_timecode`
  gains a milliseconds variant; the frame index is `floor(position_ms * fps / 1000)`.

### 3. Playlist

- A collapsible list to the right of the panel grid (`QListWidget`, toggle button
  *Playlist* in the transport bar; hidden by default in 2/4-panel mode, shown in
  1-panel mode). The list belongs to the *selected* panel (click a panel to select it;
  a thin accent border marks it). Entries: Add files…, Add folder… (recursively picks
  files matching `VIDEO_NAME_FILTER`), Remove, Clear, drag to reorder, drag files from
  Explorer to append, double-click to load into the selected panel.
- Auto-advance: when the selected panel reaches `EndOfMedia` **and the panel count is
  1**, load the next entry and keep playing. With 2 or 4 panels, nothing advances on
  its own (a synchronized comparison must not have one tile jump ahead); *Next* /
  *Previous* buttons and `N`/`P` do it on request.
- The playlist is not persisted between sessions (YAGNI); it is per panel in memory.

### 4. Converted Files tab → player

- `ConvertedFilesWidget` context menu gains *Play in Media Player* (first item) and
  emits a new `play_requested = pyqtSignal(str)`; a *Play* button appears in the
  actions row when a row is selected (matching existing button style).
- `main_window` connects it to `_ensure_media_player_widget()`, shows the Media Player
  tab for the session if it is hidden (without changing the saved
  `visible_tool_tabs`), switches to it, and calls `load_media(path)` on the selected
  panel (panel 1 if none selected), then `play_all()`.
- Files dropped on the Converted table already flow to conversion; dropping onto the
  player panels keeps loading them (existing behaviour).

### 5. Unsupported formats

- Detection is error-driven, not probe-driven: on
  `QMediaPlayer.error` with `FormatError`, `ResourceError` or `AccessDeniedError`, or on
  `mediaStatus == InvalidMedia`, the panel runs `ffprobe` (same worker as §2) to get
  container, video codec and audio codec.
- The panel shows an inline message in the tile (not a modal):
  `Windows cannot play <vcodec>/<acodec> in <container>.` with two buttons:
  **Convert to MP4 (H.264) and play** and **Dismiss**. Convert queues the file in the
  converter with a fixed preset (H.264 CRF 20 `veryfast`, AAC 160 k, `+faststart`,
  destination = the converter's configured output folder) through the existing
  conversion queue API; the tile shows `Converting… n%` from the queue's progress
  signal and loads the result on success. Failure shows the converter's error text
  in the tile.
- If `ffprobe` itself fails, the message is generic (`Windows cannot play this file.`)
  and the convert offer is still made.

### 6. Persistence

`utils/config.py` gains a `media_player` group: `last_folder` (used by every file
dialog in the player), `panel_count` (1/2/4), `volume` (0–100), `muted`. Saved on
change through the existing settings save path; loaded when the widget is created.

### 7. Tests (headless, `QT_QPA_PLATFORM=offscreen`, no real media required)

- Pure functions: `format_timecode_ms`, frame index / step size for 23.976, 25, 29.97,
  60 fps; playlist model (add/remove/reorder/next/prev wrap rules); unsupported
  message text from probe dicts and from a failed probe.
- Widget: shortcuts reach the right slots (stubbed players); volume/mute propagate to
  every panel; fullscreen toggle re-parents and restores; playlist auto-advance only
  at panel count 1; `play_requested` from the Converted widget reaches
  `load_media` on the selected panel and unhides the tab for the session; the
  error path shows the tile message and, on Convert, enqueues one job with the fixed
  preset (converter stubbed); config round-trip of the `media_player` group.
- Real-file smoke: if `tests/` already has a sample MP4 (or `ffmpeg -f lavfi` can
  make a 2 s clip during the test), load it, assert duration reported and one frame
  step moves the position by `1000/fps` ± 1 frame.

### 8. Docs

CHANGELOG entry; BACKLOG: remove the player items from Feature Ideas that this covers,
add the non-goals as follow-ups; a new help chapter `media-player` (written in the
documentation sub-project).
