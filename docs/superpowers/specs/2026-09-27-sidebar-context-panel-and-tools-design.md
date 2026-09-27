# Sidebar as context panel, hideable tools, shared playlist, recorder row 1

Date: 2026-09-27. Branch `sidebar-tools-1733`. Approved by the owner in chat
("A. yes lets unlock row 1") after a written comparison of three sidebar
options.

## 1. Recorder: row 1 is no longer locked on

Today row 1's "Use" box is disabled and re-checks itself, so a saved
"Screen capture" source on row 1 previews the desktop on every launch and
cannot be switched off. All four rows now behave the same. When no row is
enabled, Start Recording is disabled and the status line reads "Enable at
least one source". `VideoSettingsDialog.apply_to_sources` stops forcing row 1
on; a row with a source keeps being enabled automatically, a row without one
is disabled (row 1 included).

## 2. Sidebar becomes the context panel

Order top to bottom: logo (unchanged) → **context header** → leaf preview →
stretch → Start. The context header is a `TabHeader` in a narrow variant
(`TabHeader(compact=True)`: glyph above title, description in small wrapped
type, `setFixedWidth(180)`). `on_tab_changed` calls
`self.context_header.set_heading(glyph, title, description)` from a
per-tool table; BallBuster's `launch_ballbuster_game` / `restore_log_view`
keep swapping the converter heading, now on the context header.

Removed: the `TabHeader` at the top of each tab (converter's
`converter_header` and the ones inside the recorder / player / editor / PC
report widgets) and the sidebar's "Current Video Settings" text label
(`settings_display`, its hover-underline handlers and click-to-open-settings).
`tab_headers()` returns the single context header under every tool key so
existing reskin code keeps working.

## 3. Current Video Settings table in the Video Converter tab

The converter tab's lower area becomes a horizontal splitter: log on the
left (stretch 3), a compact two-column `QTableWidget` "Current Video
Settings" on the right (Format, Video codec, Audio codec, Resolution, Bitrate,
Frame rate; fixed width ~200 px, no header row, read-only, click opens
Settings like the old label did). `update_settings_display()` now fills this
table; the game-progress text that used to hijack the sidebar label goes to
the converter status line instead.

## 4. Hide / show tools

- Right-click a tab → context menu "Hide *Tool name*". Refused (greyed) when
  it is the last visible tool.
- Burger menu gains a **Tools** submenu: one checkable action per tool in
  the saved order, plus "Show all". Toggling writes
  `settings["visible_tool_tabs"]` and calls `apply_tool_tab_visibility()`.
- The Settings dialog's existing Tools tab is the third place; it already
  reads the same key.
- Hiding the current tab selects the nearest visible one.

## 5. Sidebar preview keeps the leaf shape; blank placeholder; PC Report heart

- `PreviewController.preview_label` becomes a `LeafPixmapLabel` that paints
  its pixmap through `theme.leaf_path(rect, radius)` with anti-aliasing, so
  thumbnails, decoded frames, the star field and the recorder schematic all
  keep the rounded top-left / bottom-right corners. The frame's stylesheet
  stays as the background.
- The placeholder text "No Preview" is removed; an empty leaf is the idle
  state. `_set_preview_placeholder(text)` still shows explicit text when a
  caller passes one.
- PC Report: while `_PCReportWorker` runs, the sidebar shows a red heart
  pulsing (scale 0.9→1.1 on a 900 ms cycle, parented `QTimer`); it stops and
  stays still when the worker finishes. `PCReportWidget` emits
  `report_running(bool)`; the main window connects it to
  `PreviewController.show_heartbeat(bool)`. Only shown while the PC Report
  tab is active; switching tabs restores that tab's preview.

## 6. Media Player: one playlist for all panels

`MediaPlayerWidget` owns a single `PlaylistModel`; each `PlayerPanel` refers
to it. The dock always shows that list (title stays "Playlist"); the Panel
column lists the panels currently showing each clip (`panels_showing`),
blank when none. Double-click loads the clip into the selected panel;
next/previous walk the shared list from the selected panel's clip. Adding
files/folders adds to the shared list. Persistence key stays
`media_player.playlist` (one list).

Compact mode: the dock gets `setMaximumHeight(theme.COMPACT.playlist_height)`
(≈ 5 rows + header) with its own vertical scrollbar, and the panel grid keeps
its minimum, so the tab's outer scroll area no longer scrolls at
`theme.COMPACT.window_size`.

## 7. i18n and help

New strings ("Hide %(tool)s", "Tools", "Show all", "Enable at least one
source", "Current Video Settings" table labels) go into nl / zh-CN
catalogues; `.qm` rebuilt. Help text: sidebar description, hiding tools,
shared playlist, recorder rows.

## Tests (written first, per item)

- Recorder: row 1 can be unchecked; Start disabled + hint with no rows;
  dialog apply no longer forces row 1.
- Main window: context header follows tab changes and the game swap; no
  `TabHeader` inside tool tabs; settings table shows the six values and
  updates on settings change; right-click hide, Tools submenu toggling,
  last-tab refusal; tab visibility persisted.
- Preview: pixmap pixels outside the leaf path are transparent; idle label
  text is empty; heartbeat timer runs only while `report_running(True)`.
- Player: one model shared by panels; Panel column values; next/previous
  across the shared list; dock height cap in compact mode.
