# Media Player: Inspect panel proportions, playlist below the video, first-frame thumbnail; RTSP address check

Date: 2026-09-26. Follows the tab merge (`2026-09-26-tab-merge-design.md`).

## What the user reported

1. The Inspect panel "looks odd in full screen": at 1920+ px wide the video
   grows and the panel stays a fixed 320-480 px strip with a large empty
   dashed box under a few lines of text.
2. The dashed "drop zone" frame around the ffprobe text should go.
3. Inspect should be open by default; the playlist should become a panel
   *below* the video instead of competing for the right-hand slot.
4. Dropping a video onto a panel is not visibly "loaded": the tile stays
   black until Play, and dragging the timeline before the first Play does
   not move the picture.
5. The sidebar preview on the left may be redundant now; keep it working
   for the moment.
6. The RTSP camera does not load.

## Decisions

### Stage layout

```
+----------------------------------------------+--------------------+
| video grid (1 / 2 / 4 panels)                | Inspect            |
|                                              |  Summary | JSON    |
|                                              |  text (scrolls)    |
+----------------------------------------------+                    |
| Playlist - Panel N   [list ......] [+][+][-][x]                   |
+----------------------------------------------+--------------------+
| transport bar                                                     |
```

- `MediaPlayerWidget.stage` becomes a horizontal `QSplitter`: left = a
  "video column" widget (grid on top, playlist strip below), right =
  `InspectionDock`. Stretch factors 3 : 1, `childrenCollapsible(False)`,
  Inspect minimum width 260, **no maximum** -- it scales with the window.
  Initial sizes are set once from the widget's width (72 % / 28 %).
- `InspectionDock` opens by default. Its state persists in
  `settings["media_player"]["inspect_visible"]` (bool, default True), the
  playlist strip in `"playlist_visible"` (bool, default False). Loading a
  saved value fires the same toggles as a click; `_restoring` keeps that
  from writing the settings file back (existing pattern).
- The Playlist button no longer unchecks Inspect and vice versa. The old
  "panel count 1 => playlist on" automation goes: the user decides.
- `PlaylistDock(horizontal=True)`: title on top, list beside a vertical
  button column, fixed height 150, no width limits. The vertical variant
  stays for anything else that uses the class (nothing today) and the tests.
- Fullscreen (`enter_fullscreen`) takes the stage as before but hides the
  Inspect dock and playlist strip for the duration; `exit_fullscreen`
  restores whatever was visible. Fullscreen is for the picture.

### Inspect text without the dashed frame

- `InspectionWidget(compact=True)` (the dock passes it): the two drop-zone
  wrappers get a plain style (no border, transparent), the text areas get
  `theme.inspect_text_style()` -- panel background, 1 px panel border,
  rounded, body text, default scroll bars -- and the empty-state labels read
  "Select a panel with a clip, or drop a file here." Drag-and-drop still
  works on both sub-tabs. The stand-alone widget (default `compact=False`)
  keeps its current look so the Converted Files / other callers are
  untouched.

### First frame on load

- `PlayerPanel.load_media` primes the Media Foundation session: when the
  status reaches `LoadedMedia` (or `BufferedMedia`) and the host is not
  playing, the panel calls `play()` then, on the first `positionChanged`
  (fallback: a parented 200 ms `QTimer`), `pause()` and `setPosition(0)`.
  Audio is muted during the prime and restored after. Result: the first
  frame is on the tile as soon as the file is loaded, and seeking while
  paused repaints because the session has started.
- The panel name label already changes; the tile briefly shows a
  "Loading ..." caption from the existing placeholder label until the
  prime finishes, so a dropped file is visibly acknowledged even before the
  first frame arrives.

### Sidebar preview

- The player emits `media_selected(str)` whenever the selected panel's clip
  changes (load, clear, panel switch). The main window connects it to
  `preview_file`, so the left-hand preview follows the player the way it
  followed the old inspection tab. Whether the sidebar preview should stay
  at all is a backlog question, not decided here.

### RTSP camera not loading

Root cause (from the app log and the saved recorder settings, values not
reproduced here): the current row's address has a **four-digit third
octet** -- not a valid IPv4 literal -- so ffmpeg treats it as a host name,
DNS fails ("Failed to resolve hostname"), and the preview retries every few
seconds with only a log line. The `Default` and `Custom_1` presets hold the
correct address.

- `conversion/recording_sources.py`: `stream_host_problem(host)` returns a
  message for hosts that look numeric but are not valid IPv4 (wrong octet
  count, octet > 255, empty octet), otherwise "".
- The RTSP/IP Camera Settings dialog checks the address on OK: a problem
  shows a warning box naming the issue and keeps the dialog open.
- `_preview_finished`: when a stream preview dies with "Failed to resolve
  hostname" in ffmpeg's stderr the tile reads "Video N / Cannot resolve the
  camera address / Check the IP in Video Settings" and **does not retry**;
  editing the source restarts the preview as before.
- The user's saved current settings are not edited by code. The report
  tells the user to re-enter the address or load the `Default` preset.

## Testing

- `tests/test_media_player_widget.py`: stage is a splitter with dock right
  and playlist under the grid; inspect on by default; both toggles
  independent; persistence of `inspect_visible` / `playlist_visible`;
  fullscreen hides and restores docks; splitter has no maximum width on the
  dock; `media_selected` emitted on load / clear / select.
- `tests/test_media_player_widget.py` (prime): with a fake player object,
  `LoadedMedia` -> `play()` then `pause()` + `setPosition(0)` and mute
  restored; no prime while the host is playing.
- `tests/test_media_player_parts.py`: `PlaylistDock(horizontal=True)`
  geometry; `InspectionWidget(compact=True)` has no dashed style and the
  compact empty-state text.
- `tests/test_config.py`: new defaults and normalisation.
- `tests/test_recording_sources.py`: `stream_host_problem` cases.
- `tests/test_multi_source_recorder_widget.py`: unresolved-host preview
  message and no retry scheduled; dialog refuses a bad address.
- `tests/test_main_window_media_player.py`: `media_selected` reaches
  `preview_file`.
