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
| FIG-01 | `fig-01-settings-general.png` | Settings, General tab: source and destination folders. | Menu → Settings, General tab. Both folder fields populated. |
| FIG-02 | `fig-02-settings-video.png` | Settings, Format tab: output format, codec and bitrate. | Menu → Settings, Format tab, output format `mp4`. |
| FIG-03 | `fig-03-converted-files.png` | The Converted Files tab tracking queued and finished jobs. | Convert two short clips first so the list has rows. |
| FIG-04 | `fig-04-inspection.png` | The Inspection tab showing an FFprobe summary. | Drop a short MP4 on the Inspection tab; capture the Summary sub-tab. |
| FIG-05 | `fig-05-pc-report.png` | The PC Report tab after generating a report. | PC Report tab, generate with redaction enabled, then capture. |
| FIG-06 | `fig-06-lossless-editor.png` | The Lossless Editor tab with a trim range set. | Load a clip, set start and end timestamps. Do not run it. |
| FIG-07 | `fig-07-multi-source-recorder.png` | The Multi-Source Recorder tab with two sources enabled. | Fill rows 1–2, enable both. Do not start recording. |
| FIG-08 | `fig-08-media-player.png` | The Media Player tab with a clip loaded in a single panel. | Media Player tab, Panels = 1, a short generated test clip loaded and paused at ~1 s. Real display only. |
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

Redaction note: FIG-05 shows a PC report, which can contain machine details.
Generate it with redaction enabled and check the visible fields before
committing the PNG.
