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
| FIG-07 | `fig-07-multi-source-recorder.png` | The Multi-Source Recorder tab with two sources enabled. | Fill rows 1–2, enable both. Do not start recording. |
| FIG-08 | `fig-08-media-player.png` | The Media Player tab with a clip loaded in a single panel. | Media Player tab, Panels = 1, a short generated test clip loaded and paused at ~1 s. Real display only: the video surface is native, so the script grabs the screen region under the window (1600 px wide, so the transport row is not clipped). Keep the display unobstructed while the script runs. |
| FIG-09 | `fig-09-recorder-video-settings.png` | The recorder's Video Settings dialog with two camera rows configured. | Recorder tab → Video Settings. Rows 1–2 as USB cameras with stand-in names. Run the capture script with `NVC_SHOTS_STUB_DEVICES=1`. |

## Automated capture

```bash
python docs/help/source/capture_screenshots.py
```

This drives the real application and saves what it can. It cannot reach
everything — anything behind a burger menu, or a view that needs real media or
real hardware, still wants a manual capture on a real display. The script
reports which ids it produced and which it skipped.

Device names: set `NVC_SHOTS_STUB_DEVICES=1` so DirectShow discovery returns
`Camera A` / `Camera B` and `Microphone A` / `Microphone B` instead of the
devices attached to your PC. Personal device names must never be committed.

Privacy note: FIG-05 is captured before a report is generated. A generated
report shows the machine name, hardware and user account (redaction is always
on, but it masks values, not the fact that they exist), so never capture the
tab with a report in it.
