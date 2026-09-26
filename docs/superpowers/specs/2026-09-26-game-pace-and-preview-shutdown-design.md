# BallBuster pace at any size; recorder previews that really stop

Date: 2026-09-26 (18:16 pass). Branch `game-recorder-1816`.

## 1. BallBuster slows down when the window grows

### Root cause (measured)

`paintEvent` rescaled the full background and every ball with
`Qt.SmoothTransformation` on every frame and re-read the white halo PNG from
disk per frame. At 1920x1080 a paint took ~20 ms, at 800x600 ~12.8 ms; the
16 ms `QTimer` loop advanced the simulation exactly one fixed step per tick,
so when paint overran the tick the game ran in slow motion.

### Design

- **Pixmap cache** keyed by `(name, w, h)`, cleared in `recalculate_geometry`
  (which every resize reaches; `resizeEvent` alone is deferred for hidden
  widgets). Paint drops to ~3.2 ms / ~0.9 ms.
- **Wall-clock fixed steps**: `game_tick` measures elapsed time since the last
  tick and runs `round(elapsed / STEP_S)` simulation steps (`STEP_S = 1/60`,
  capped at `MAX_STEPS_PER_TICK = 4` so a stall never turns into a teleport).
  Ball speed is therefore pixels per real second, independent of paint cost.
- **Header**: while the game runs the Video Converter tab header becomes
  glyph `balls` + "BallBuster XT" + a one-line joke; `restore_log_view()`
  puts the converter heading back. `TabHeader.set_heading()` added for this.

## 2. Camera light stays on / old preview keeps showing

User report: a webcam not selected for viewing stays on; setting every row to
"No source selected..." and returning to the recorder still shows the desktop
capture in the tile.

### Root causes (three, all confirmed by reading + a live probe)

1. **`QProcess.terminate()` is a no-op for ffmpeg on Windows.** It posts
   `WM_CLOSE` to the process's top-level windows; `ffmpeg.exe` has none.
   `stop_preview_for_row` called `terminate()` only, then dropped the process
   from `preview_processes`, so an unchecked row's preview kept running (camera
   open, light on) with nothing left that could ever stop it. A probe with the
   bundled ffmpeg confirmed: state still `Running` 1.5 s after `terminate()`,
   gone immediately after `kill()`.
2. **A row that stops describing a previewable source kept its old preview.**
   `start_directshow_preview` / `start_stream_preview` return early on an empty
   device/source without stopping whatever the row was previewing before, so
   "desktop -> USB camera with No source selected" left the desktop preview
   running.
3. **`populate_directshow_devices` auto-filled the first known camera into an
   empty field.** Video Settings writes `""` for "No source selected..."; the
   type-change path then wrote the first camera straight back in and started
   its preview. "No device" silently became "the webcam".

### Design

- `_kill_preview_process(row, process)`: `kill()` directly (a preview writes
  JPEGs to a pipe, nothing to flush), used by `stop_preview_for_row` and
  `stop_preview_processes` (which also loses its 1.5 s blocking wait).
  `release_preview_processes_for_recording` already escalated to `kill()` and
  is untouched.
- `_row_wants_preview(type, text)`: `screen` always, `directshow`/`rtsp_ip`
  only with text, everything else never. `update_source_placeholder` stops the
  row's preview when this is false, before any start.
- `populate_directshow_devices` uses `auto_select=False`: the drop-down still
  offers the cameras, the field stays empty until the user picks one.
- `_preview_finished` for an already-dropped process now consumes the row's
  `preview_stopping_rows` mark so the next preview on that row keeps its retry.

### Behaviour change to note

Choosing "USB / DirectShow" no longer pre-fills the first camera. The tile
says "Configure the source" until a camera is chosen in Video Settings.

## Tests

`tests/test_ballbuster_pace.py` (new), `tests/test_tab_header.py`,
`tests/test_video_converter_tab.py`; recorder: six new cases in
`tests/test_multi_source_recorder_widget.py` (uncheck kills a terminate-proof
process; cleared device stops the old preview; type without preview stops it;
"No source selected" is not replaced by the first camera; killed preview
clears the stopping mark; `stop_preview_processes` kills without blocking),
three existing cases updated to the no-auto-fill contract.
