# Screenshot shot list

The contract between the figure catalog and whoever takes the screenshots.
Every id here must exist in `docs/help/source/figures.py`, and every
`{"type": "figure"}` block must reference an id from this list — the build
fails otherwise.

A figure whose PNG is missing does **not** break the build. The PDF draws a
grey placeholder box and the DOCX inserts an italic `[FIG-NN — screenshot not
captured]` line, so an incomplete shot list is visible in the output rather
than silent.

## Capture settings

| Setting | Value |
|---|---|
| Target size | 1890 × 827 px (fills the 160 × 70 mm figure box at 300 dpi) |
| Window state | Default launch size, not maximised |
| Theme | Default teal |
| Content | Real but disposable files — no customer names, no real paths |

Save each file into this folder using exactly the filename in the table.

## Shots

| ID | Filename | Caption | How to frame it |
|---|---|---|---|
| FIG-00 | `fig-00-main-window.png` | The NVC main window, with the conversion log and preview panel. | Launch NVC with no job running. Full window, default size. |
| FIG-01 | `fig-01-settings-general.png` | Settings, General tab: startup, Copy Only, tray and GPU options. | Menu → Settings, General tab as shipped. The Folders tab is not captured: it shows the operator's own paths. |
| FIG-02 | `fig-02-settings-video.png` | Settings, Format tab: output format, codecs and presets. | Menu → Settings, Format tab, output format `mp4`. |
| FIG-03 | `fig-03-converted-files.png` | The Video Converter tab: the Converted Files table above the conversion log. | The capture script adds three stand-in rows (`Session 1.mp4` success, `Session 2.mp4` processing, `Session 3.mp4` queued) so the status icons show without listing real files. |
| FIG-04 | `fig-04-inspection.png` | The Media Player's Inspect panel beside the video, Summary sub-tab. | Media Player tab, Inspect button on the transport bar, no file loaded. |
| FIG-05 | `fig-05-pc-report.png` | The PC Report tab before a report is generated. | PC Report tab as opened. Do not generate: a real report shows this machine's name and hardware. |
| FIG-06 | `fig-06-lossless-editor.png` | The Lossless Editor tab with its trim, remux and merge tools. | Lossless Editor tab as opened, no clip loaded. |
| FIG-07 | `fig-07-multi-source-recorder.png` | The Multi-Source Recorder tab with two sources enabled. | Rows 1–2 enabled, do not start recording. Live previews are off during the run (the recorder is built with `auto_preview=False`) so no real camera or desktop appears; the tiles are filled with ffmpeg test patterns through the widget's own frame path. File location shows `C:\Videos`. |
| FIG-08 | `fig-08-media-player.png` | The Media Player tab with a clip loaded in a single panel. | Media Player tab, Panels = 1, a short colour-bar clip (`Session 1.mp4` in the Public Videos folder, removed after the run) loaded and paused at ~1 s. The video surface is native and `grab()` sees it black, so the script composites the frame ffmpeg extracts at the paused position into the tile. Window is 1600 px wide so the transport row is not clipped. No screen read, no display needed. |
| FIG-09 | `fig-09-recorder-video-settings.png` | The recorder's Video Settings dialog with two camera rows configured. | Recorder tab → Video Settings. Rows 1–2 as USB cameras with stand-in names. Run the capture script with `NVC_SHOTS_STUB_DEVICES=1`. |

## Automated capture

```bash
python docs/help/source/capture_screenshots.py
```

This drives the real application and saves what it can. The window is parked
off-screen (moved to -7000,-7000) and every shot is a `widget.grab()`, so the
run never reads pixels from the display and other windows can stay open on top
of it. Views that need real media get synthetic content: FIG-08 plays a
generated colour-bar clip and FIG-07's tiles receive ffmpeg test patterns. The
script reports which ids it produced and which it skipped. Set
`NVC_SHOTS_ONSCREEN=1` only if you want to watch the run; nothing needs it.

Device names: set `NVC_SHOTS_STUB_DEVICES=1` so DirectShow discovery returns
`Camera A` / `Camera B` and `Microphone A` / `Microphone B` instead of the
devices attached to your PC. Personal device names must never be committed.
Live recorder previews are always off during a capture run, so the operator's
saved sources (cameras, screen capture) are never opened or shown.

Before committing, open every PNG and check for user names, machine names,
personal device names and personal paths. The Inspect panel prints a clip's
full path, which is why the FIG-08 clip lives under the Public Videos folder
rather than `%TEMP%`.

Privacy note: FIG-05 is captured before a report is generated. A generated
report shows the machine name, hardware and user account (redaction is always
on, but it masks values, not the fact that they exist), so never capture the
tab with a report in it.
