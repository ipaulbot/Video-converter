# Tab merge: Video Converter, and inspection inside the Media Player

Date: 2026-09-26. Decided with the owner: "files table above, log below; one
toggle; you name it" and "fewer tabs, but also the ffprobe data next to the
video -- it can replace where the video list is; build the version you would
build."

## Before

Seven tabs, each with its own footer (lock, file, broom, status):
Conversion Log, Converted Files, Video Inspection Tool, PC Report, Lossless
Editor, Multi-Source Recorder, Media Player. The first three are visible by
default, the Media Player is hidden by default and built lazily.

## After

Five tabs. Two are new shapes:

### Video Converter (replaces Conversion Log + Converted Files)

- One `LeafFrame` card holding a vertical `QSplitter`: the Converted Files
  table on top (its own Clear / Play buttons stay), the conversion log with
  its drag-and-drop overlay below. Initial split about 40 / 60; the user can
  drag it. One footer: lock, file picker, broom (clears the log; the table has
  its own Clear), status.
- Setting key `visible_tool_tabs["video_converter"]`, default on. The old
  `conversion_log` and `converted_files` keys are migrated in
  `normalize_settings`: on if either was on. Settings -> Tools shows one
  checkbox, "Video Converter".
- The easter-egg game still replaces the log pane; while it runs the files
  table is hidden so the game has the whole card.
- Tab title: "Video Converter". It is the product's name for the workflow and
  matches the About dialog ("About Video Converter").

### Media Player with an Inspect panel (absorbs Video Inspection Tool)

- The player's right-hand slot, where the Playlist dock sits, gains a second
  dock: **Inspect**. A checkable transport button next to Playlist toggles it;
  Playlist and Inspect are mutually exclusive so the slot shows one or the
  other.
- The Inspect dock embeds the existing `InspectionWidget` (Summary / Detailed
  JSON tabs, drag-and-drop onto it inspects that file). It follows the
  **selected panel**: selecting a panel or loading media into the selected
  panel re-runs ffprobe for that file while the dock is visible; opening the
  dock inspects the current selection. Clearing the panel clears the dock.
- The dock is wider than the playlist (320-480 px) because JSON needs room.
- `visible_tool_tabs["media_player"]` default becomes on, since it now holds
  a default-visible tool. Migration: a saved `video_inspection: true` turns
  `media_player` on. The `video_inspection` key is dropped.
- The main window's inspection footer, context-menu wiring and
  `open_inspection_file_dialog` are removed or redirected: "inspect a file"
  now means show the Media Player tab, open the Inspect dock, load the file
  into the selected panel.
- Lazy construction of the player is kept; the tab being visible by default
  only means it is built on first show, as today.

## Not changing

- Conversion, watch-folder, preview sidebar, recorder, lossless editor, PC
  Report.
- `InspectionWidget` internals (ffprobe worker, summary generation).
- The command-line control added earlier today.

## Tests

- `normalize_settings` migration for both merges.
- Video Converter tab: splitter order (table above log), one footer, tab
  title, `tool_tab_cards` keys, the game hides and restores the table.
- Media Player: Inspect button toggles the dock and unchecks Playlist and
  vice versa; selecting a panel with media inspects it; loading media into the
  selected panel while the dock is open inspects it; the dock clears with the
  panel.
- Main window: `play_in_media_player` still works; inspecting from the
  Converted Files table lands in the player with the dock open.
- Help bundle validation (`docs/help/source/test_help_docs.py`) after the
  content edit.
