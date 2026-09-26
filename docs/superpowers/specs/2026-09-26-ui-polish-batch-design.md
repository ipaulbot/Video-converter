# UI polish batch: player title/playlist/blank tile, recorder alignment and tile scaling, converter menu, movable tabs

Date: 2026-09-26 (10:36 feedback). Follows `2026-09-26-player-inspect-layout-design.md`.

## Requests and decisions

### Media Player

1. **No "Inspect - Panel 1: file" title.** The dock title label goes. The
   panel's own caption under the tile already names the file, and the
   playlist (below) lists it.
2. **Dropped/loaded files go into the playlist.** `PlayerPanel.load_media`
   adds the path to that panel's `PlaylistModel` (duplicate-free) and the
   playlist strip selects it. So the playlist is where you see what a
   panel holds. Applies to drops, Load, Converted Files -> Play/Inspect and
   the command line alike.
3. **Blank tile after leaving and returning to the tab.** Media Foundation
   drops the presented frame when the native surface is hidden; a paused
   player shows black again until something repaints. Fix: the first-frame
   prime becomes a general "present a frame" nudge with a target position.
   `MediaPlayerWidget.showEvent` (and `PlayerPanel.showEvent`) run it for
   every loaded, paused panel with `target = player.position()`, so the
   tile returns showing the frame it was on. Nothing runs while playing.

### Multi-Source Recorder

4. **Group boxes align.** `QHBoxLayout` centres items of different heights;
   the Output settings group (taller, with the copy note) was centred and
   the properties table sat lower. Both are now added with `Qt.AlignTop`.
5. **Output fields the same width.** The per-field maximum widths
   (140 / 120 / 140 / 140 and the 320 folder cap) go; every field is
   `Expanding` inside the form and the *group* is capped at 380 px, so the
   fields share one width. The folder row keeps its open-folder button on
   the right; the edit is that button narrower.
6. **Tiles fill the window.** Preview tiles change from
   `(Ignored, Fixed)` with a per-mode maximum height to `(Ignored,
   Expanding)` with no maximum, and the preview grid gets stretch 1 in the
   recorder's column while the groups keep `Fixed`. The tiles take whatever
   height the tab has left in either mode. `recorder_tile_max_h` stays in
   `LayoutMetrics` but is no longer applied (kept so the dataclass order and
   existing tests' `replace()` calls hold).

### Video Converter file list

7. **Right-click menu works on empty space too**, and gains:
   - "Add videos to convert..." -> the main window's `open_file_dialog`
     (same as the footer file picker).
   - "Monitor a folder..." -> directory picker -> `set_monitored_folder`
     (saves `source_folder`; if monitoring is running it restarts on the
     new folder).
   - On a row: "Monitor this file's folder" (the row's containing folder)
     and an **Open in** submenu: Media Player, Lossless Editor (fills the
     editor's input field and shows that tab for the session), Default
     Windows app (`QDesktopServices.openUrl`).
   The widget emits `add_files_requested()`, `monitor_folder_requested(str)`
   and `open_in_requested(str, str)`; the main window wires them. The
   existing Play / Inspect / folder / log / copy / settings items stay.

### Tabs

8. **Drag tabs into any order.** `QTabWidget.setMovable(True)`. The order
   of the five tool tabs persists as `settings["tool_tab_order"]` (list of
   keys; unknown keys dropped, missing keys appended in default order) and
   is applied on start with `tabBar().moveTab`. The one index assumption in
   the code (`setCurrentIndex(0)` for the BallBuster banner) becomes
   `indexOf(converter_tab_scroll)`.

### Not now (recorded for later)

The landing-page website, the product rename ("Media Multitool"?) and the
GitHub tidy-up are planning items: `docs/planning/2026-09-26-product-
naming-website-and-github.md`.

## Testing

- Player: title label absent from the dock; `load_media` adds to the
  playlist and selects; `showEvent` primes paused loaded panels at their
  current position and not playing ones; real-backend smoke: hide/show the
  widget after load leaves the panel paused at the same position.
- Recorder: layout items carry `AlignTop`; tile policy Expanding, no max,
  preview grid stretch 1; output fields' maximum widths equal to the
  default (unbounded) and the group capped.
- Converter: menu on empty space; new signals emitted; main window
  `set_monitored_folder` saves and restarts monitoring when running;
  "Open in Lossless Editor" fills `input_edit` and shows the tab.
- Tabs: `isMovable()`; `normalize_tool_tab_order`; moving a tab persists;
  saved order applied at start.
