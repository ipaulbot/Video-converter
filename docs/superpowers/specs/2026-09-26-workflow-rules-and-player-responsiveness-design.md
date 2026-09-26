# Workflow rules, one status line, and Media Player responsiveness (2026-09-26, 15:32)

Requests from the 15:32 review, with the decisions taken under the standing
"build the version you would build" waiver. Everything here is built with
tests first on branch `ui-polish-1532` and merged `--no-ff`.

## 1. Inspect dock: a box even when empty

The Summary / Detailed JSON dock has no frame until a clip is inspected (the
text panel brings its own border; the empty drop hint floats on white).

Decision: in the compact (dock) mode the `QTabWidget` pane wears the same thin
grey box as every other list on the tab (`1px solid separator`, 4 px radius,
white), and the text panels inside lose their own border so there is one
frame, not two. The empty hint sits centred inside the frame.

## 2. Media Player responsiveness (drop into panel 2, playlist not filling)

Cause: the dock and Inspect follow the *selected* panel, and a drop on an
unselected panel did not select it. The clip went into panel 2's playlist,
which is not the one on screen, and Inspect stayed on panel 1's clip (or
empty) -- so nothing visible happened.

Decision: any load into a panel -- drop, the panel's Load button, the Files
menu -- selects that panel first. The playlist dock switches to that panel's
list (the row is there and highlighted) and Inspect shows the clip's ffprobe
details. Loading into the already-selected panel keeps doing what it did.
Programmatic loads from Converted Files (`play_in_media_player`) target the
selected panel, so nothing changes there.

## 3. Transport bar order

Panels, Speed and Volume (+ mute) move left, right after the view buttons
(Fullscreen, Playlist, Inspect), separated by the same 12 px gap; the stretch
goes at the end. Order: `Play Stop Restart | Fullscreen Playlist Inspect |
Panels Speed Volume Mute ... (stretch)`.

## 4. Compact window: the dock was cut off

Reproduced: the panel caption `Panel 1: <file name>` is a plain `QLabel`, and
a QLabel's minimum width is its full text. Two long clip names (33 characters
each in the report) push the tab's minimum width to ~820 px; the tab scroll
area shows a horizontal bar and the Inspect dock is clipped.

Decision: a small `ElidedLabel` (`ui/elided_label.py`) that paints its text
elided in the middle to whatever width it gets, reports a 48 px minimum, and
keeps the full text as tooltip. The panel captions use it. Acceptance: with
two 40-character clip names loaded, the video column's minimum width is no
wider than with empty panels plus 40 px, and the tab page's minimum width
stays under 760 px.

## 5. "Overlay of the Video Converter table" on the player after a tab switch

Not reproducible in a headless `grab()` (widgets paint correctly), which
points at the native Media Foundation video window: after a tab switch it has
no frame to paint and shows whatever the screen held in that rectangle -- the
converter table -- until the first frame lands (up to ~200 ms, the
re-present nudge).

Decision: the video surface is hidden while its panel is hidden. On re-show
the dark tile paints first (a plain widget), the re-present nudge runs
against the hidden surface, and the surface is shown again at the moment the
nudge pauses -- so anything stale underneath is the black tile, never another
tab. The surface is also revealed when Play is pressed or when a re-present
is not needed (nothing loaded, or the host is already playing). Verified
headless with a stand-in player: hidden after `hide()`, visible again once
the nudge finishes.

## 6. Which jobs may run together (assessment)

Today: while recording, every other tab is greyed out (you cannot even open
the Media Player); while converting, the whole recorder widget is disabled.
Nothing stops on a tab switch in the current code, but the two rules above
are blunt and inconsistent with each other.

Rules adopted (`ui/workflow_rules.py`, pure functions, tested):

1. **Switching tabs never stops or pauses anything.** Recording, conversion,
   folder monitoring, media playback and camera previews carry on whatever
   tab is in front. Tabs are never disabled.
2. **Recording is exclusive with other ffmpeg jobs.** While a recording is
   starting, running or stopping: the sidebar Start button on the converter
   tab is disabled and reads "Recording..." with the reason as tooltip;
   Lossless Editor Trim and Merge are disabled with the same reason.
3. **Conversion or monitoring blocks recording only.** While converting or
   monitoring, Start Recording is unavailable (sidebar button reads
   "Converting...", as today) but the rest of the recorder -- previews,
   settings, device management -- stays usable. The recorder's own status
   line says why.
4. **Viewing never blocks and is never blocked.** Media Player and PC Report
   work during any job. Lossless edits are allowed alongside conversions
   (they are `-c copy` jobs and short).
5. **Locked blocks every start action**, as before.

`blocked_reason(activity, action)` returns `""` or the reason for `"convert"`,
`"record"` and `"lossless_edit"`; the main window turns the reason into the
disabled button + tooltip. The old `_apply_recording_tab_lock` is removed.

## 7. One status line on every tab

The five footers each had their own status label; only the converter's and
recorder's were ever written. Now every footer shows the same text, built by
`status_markup(activity)` from whatever is active, joined by " · ":
Locked / Starting recording / Recording / Stopping recording / Recording
failed / Converting / Monitoring; nothing active reads "Idle". The dot is
grey when locked, red for a failed recording, green when a job is active,
teal when idle. `update_status_labels()` writes all five.
