# Help documentation refresh — design

Date: 2026-09-25. Third and last sub-project of the "PC report / recorder /
media player / help docs" request. The docs come last so they describe the
finished features.

## Problem

The generated manuals (`docs/help/NVC 2.3.0 - Help - en.*`, `... - Quick Start
Guide - en.*`) were written before the PC report rebuild, the recorder button-up
and the media player work. Checked against the code today they are wrong or
silent in these places:

| Manual says | Code does |
|---|---|
| PC report "with redaction enabled" (a checkbox) | Redaction is always on; there is no checkbox. Report goes to `Desktop\PC_Report_<stamp>.html`. |
| Settings has a "Video" tab (SHOTLIST) | Tabs are General, Folders, Deletion, Format, Time, Tools. |
| Recorder: "Enter one source per row" as free text | Sources are chosen in the **Video Settings** dialog (source type, device, frame rate, resolution, audio device, sync offset); the main tab shows Nr/Use/Video name/Audio name/Mute/Volume. |
| Nothing about the Media Player | A whole tab: 1/2/4 panels, transport, shortcuts, fullscreen, playlist, unsupported-format fallback, hand-off from Converted Files. |
| Nothing about tool-tab visibility, Language menu, Check for Updates, time restrictions, system tray, lock | All exist. |
| README table names `NVC 2.2.0 - ...` | `DOC_VERSION` is `2.3.0`; the shipped files are 2.3.0. |

Discovered while auditing and **deliberately not documented** (they do
nothing): the Video Settings dialog's "Output quality" combo and the whole
"Timer settings" group are built but never read by the recorder. They go to
the BACKLOG as recorder follow-ups; the manual describes only controls that
work.

## Scope

In:

1. Rewrite `docs/help/source/locales/en/help.py` so every chapter matches the
   application as of master today, and add the missing chapters.
2. Extend `docs/help/source/locales/en/quickstart.py` with two task chapters:
   record from a webcam, review a recording.
3. Extend `docs/help/source/locales/en/glossary.py` with the new terms the
   chapters use.
4. Figures: correct FIG-02's caption/shot list ("Format" tab), add FIG-08
   (Media Player) and FIG-09 (recorder Video Settings dialog), teach
   `capture_screenshots.py` to take them, and recapture every figure on a real
   display with stand-in device names.
5. Regenerate all manuals (PDF + DOCX) and replace the shipped 2.3.0 files.
6. `docs/help/README.md` version fix; tests that pin the new invariants;
   CHANGELOG and BACKLOG entries.

Out (recorded in BACKLOG, not done here):

- Dutch and Chinese manuals. The app ships `nl` and `zh-CN` as production
  locales but the manual pipeline has only `en`. Translating ~400 lines of
  reference prose is a separate project with its own review; note also that
  `VideoConverterApp.open_help_document` calls `resolve_help_document()` with
  the default language, so a translated manual would not be picked up until
  the active locale is passed through.
- A Developer Guide / Technical Spec (the VIO project has them; NVC never has).
- Wiring or removing the inert recorder controls named above.
- `pyproject.toml` still says `2.2.0` while `utils/version.py` says `2.3.0`.
  That is an application-version drift, not a docs one.

## Decisions

- **`DOC_VERSION` stays `2.3.0`.** It matches `APP_VERSION`; the rewritten
  manuals replace the shipped 2.3.0 files in place (same filenames), so nothing
  else has to learn a new name. `docs/help/README.md` is corrected to 2.3.0.
- **Chapter ids are stable.** Existing ids are never renamed (anchors derive
  from them). New chapters get new ids. Chapter order may change.
- **Describe only what works.** Every statement in the manual must be traceable
  to a control or behaviour in the code inventory below. No feature is
  described from memory of an older version.
- **No identifying values in screenshots.** The capture script is run with
  `NVC_SHOTS_STUB_DEVICES=1`, which replaces DirectShow discovery with
  stand-in names ("Camera A", "Camera B", "Microphone A", "Microphone B") before
  the window is built, and every PNG is inspected for user names, machine names
  and personal device names before it is committed. `SHOTLIST.md` already
  requires this; the stub makes it deterministic.
- **Screenshots are taken from the real display**, not offscreen, so the
  Media Player figure shows a rendered frame (offscreen renders a black
  video surface). The clip is a generated `testsrc` MP4 written to `%TEMP%`.

## Help manual — chapter plan

Ids marked *new* are added; all others exist and keep their id.

| Order | id | Title | Content (from the code inventory) |
|---|---|---|---|
| 1 | `introduction` | Introduction | What NVC is (FFmpeg-based converter, folder watcher, inspector, recorder, player, PC report). FIG-00. Overwrite policy note. |
| 2 | `quick-start` | Quick Start | Six steps as now, corrected: Settings → Folders tab for folders, Format tab for format. FIG-01. |
| 3 | `main-window` | Main Window Overview | Table of the seven tabs in order with the exact labels ("Conversion Log", "Converted Files", "Video Inspection Tool", "PC Report", "Lossless Editor", "Multi-Source Recorder", "Media Player") plus Preview Panel and Menu. Which tabs are hidden by default (PC Report, Lossless Editor, Media Player) and where to turn them on (Settings → Tools). Burger menu items: Info, Help, Open Source/Destination/Backup Folder, Settings, Language, Check for Updates, Quit. Footer controls: Start/Stop button (becomes Start Recording / Stop Recording on the recorder tab), lock icon, file picker, clear-log broom, status label. System tray: minimise to tray on X unless "Close on X" is set; tray menu Show/Quit. Single instance. |
| 4 | `converting-files` | Converting Files | Monitoring, drag-and-drop onto the Conversion Log / Converted Files / Inspection, force-convert via the footer file picker, numbering rule with code block, the full supported extension list from `main_window.py`. FIG-03. |
| 5 | `conversion-settings` | Conversion Settings | One table per Settings tab, in dialog order: General (Auto Run on Startup, Copy Only, Close on X, Launch at Windows startup (All Users), Use GPU Acceleration, GPU Encoder Auto/nvidia/intel/amd); Folders (Source, Destination, Backup, Log); Deletion (see `original-files`, cross-reference); Format (Output Format list, Video Codec list, Audio Codec list, GIF options when format is gif, Show Advanced Options → Video Size, Bitrate, Frame Rate, Keyframe Interval (GOP), Volume 0–500 %, Text Overlay, Console Integration custom flags, presets Ethovision / Custom 1 / Custom 2 / Save to 1 / Save to 2); Time (No Time Restrictions, Start Time, End Time); Tools (one checkbox per tool tab). Footer Default / OK / Cancel. FIG-02. |
| 6 | `gpu-encoding` | GPU Encoding | As now; encoder names unchanged. |
| 7 | `gif-export` | GIF Export | As now, using the real control names (FPS, Max Width, Loop, Quick GIF (no palette)). |
| 8 | `text-overlays` | Text Overlays | The six real options: None, Elapsed Time, Recorded Time, Recorded Date/Time, Recorded Date/Time + Remaining, CRTV Cam. |
| 9 | `original-files` | Original File Handling | Deletion tab controls: Delete files after conversion, Retention time (days) 0–30, Use Backup Folder; pending deletions survive restart. |
| 10 | `time-restrictions` *new* | Time Restrictions | Time tab: No Time Restrictions vs Start/End Time window. A file detected outside the window is **skipped** with a "Current time outside allowed range" line in the Conversion Log; it is not queued for later, so drop or re-detect it inside the window. An end time earlier than the start time means an overnight window. |
| 11 | `converted-files` *new* | Converted Files | Columns (File Name, Destination Folder, Date Modified), status icons (queued, processing, success, failure), Clear and Play buttons, context menu (Play in Media Player, Open Containing Folder, Open Log File, Copy File Path, Settings), per-file log dialog. |
| 12 | `media-inspection` | Media Inspection | Summary / Detailed JSON sub-tabs, the summary fields, keyframe analysis of the first 30 s. FIG-04. |
| 13 | `pc-report` | PC Report Tool | Generate PC Report / Open Report / Open Folder; output `PC_Report_YYYYMMDD_HHMMSS.html` on the Desktop, never overwritten; Report Health at the top; the section list in order (40 sections, from `pc_report/registry.py`); what redaction masks (serials, licence keys, passwords/tokens, user and machine names, hostnames, IPs, MACs, proxies, UNC paths, user profile paths) and that it is always on; fields that need administrator show "Requires administrator" and how to run elevated; collectors that take time. FIG-05. |
| 14 | `lossless-editor` | Lossless Editor | As now, with the real button labels and output containers (mp4, mkv, mov, avi, m4a). FIG-06. |
| 15 | `multi-source-recorder` | Multi-Source Recorder | Rewritten. Main tab table (Nr, Use, Video name, Audio name, Mute, Volume 100/75/50/25/0), Encoding copy/h264, Output mode Separate videos / Combined grid, File location (default `Videos`), File base name → `<base>_<label>_<timestamp>.mp4` or `<base>_Combined_<timestamp>.mp4`, Timer field (blank = until stopped), Show recording log, Start Recording from the footer button. Video Settings dialog (FIG-09), one row per source with: Use, Video name, an editable **Video device** combo listing "No source selected...", "RTSP/IP Camera", every discovered USB / DirectShow camera by its Windows name, and "Refresh USB devices..." — a typed `rtsp://`, `http(s)://` URL, file path or Basler / GenICam source string is accepted as well; a camera gear button (for "RTSP/IP Camera" it opens the RTSP/IP Camera Settings dialog with Address / URL, Username, Password, Port and Stream path and writes the URL into the row; for a USB camera and for Basler it shows an information message); Frame rate and Resolution (30.00 / 25.00 / 15.00 and 1920 x 1080 / 1280 x 720 / 640 x 480 / Auto by default, replaced by the modes the camera driver reports once a USB camera is selected, with Auto when detection fails); Audio name; Audio device (No Audio, discovered microphones, "(not found)" marker, Refresh devices button); Sync offset for Combined grid. Audio rules (mute/volume 0 = no audio; no microphone keeps a file or RTSP source's own audio in h264 mode; copy mode drops RTSP audio; DirectShow without microphone is silent). Video Preset group: Load / Set / Save as… / Delete, `*` dirty marker, stored under `Public\Documents\Noldus\NVC\MediaRecorder\Presets`. Video-only retry note. FIG-07. |
| 16 | `media-player` *new* | Media Player | Hidden by default (Settings → Tools, or shown for the session by Play in Media Player). Panels 1/2/4 with Load / Clear / offset; transport (Play all / Pause all, Stop all, Restart, seek slider, Speed 0.25×–2×, Panels, Volume, Mute, Fullscreen, Playlist); readout `H:MM:SS.mmm / H:MM:SS.mmm · frame N / M` using the clip's real frame rate; shortcuts table (Space, Home, Left/Right, Shift+Left/Right, Up/Down, M, F, Esc, N/P); fullscreen (F, Esc, double-click; bar hides after 3 s); playlist dock (Add files…, Add folder…, Remove, Clear, reorder, drop from Explorer; auto-advance only with one panel); unsupported files ("Windows cannot play …", Convert to MP4 (H.264) and play → written to the Destination Folder with a unique name, then loaded); what persists (last folder, panel count, volume, mute); backend note (Media Foundation; MP4/MOV/MKV/AVI/WMV play, other containers or codecs use the convert offer). FIG-08. |
| 17 | `language` *new* | Language | Menu → Language lists English, Nederlands, 简体中文; the choice is saved and applies after restart. |
| 18 | `updates-and-logs` *new* | Updates and Logs | Check for Updates (shows "Updates Not Configured" until an update URL is configured in a build; when configured, "Update Available!" appears in the sidebar); log folder `%APPDATA%\NVC\logs\conversion_log.txt` unless changed in Settings → Folders; `NVC_LOG_LEVEL`; settings stored in `%APPDATA%\NVC\config.json`. |
| 19 | `troubleshooting` | Troubleshooting | Existing rows corrected, plus: camera "Could not find video device" (exact Windows name, close other apps using it); microphone "(not found)"; recorder recorded video only (audio device failed, see log); Media Player shows "Windows cannot play this file" (use the convert offer); Media Player tab missing (Settings → Tools); Help menu says document not found. |
| 20 | `best-practices` | Best Practices | As now plus: save a recorder preset per setup; use one panel in the player when you want playlist auto-advance. |
| 21 | `faq` | Frequently Asked Questions | Existing rows plus: Where do recordings go? Why does my MKV not play in the Media Player? Can I record without a microphone? Why is the PC report missing values ("Requires administrator")? |

The glossary chapter is appended by `document_navigation.py` as today.

## Quick Start Guide — additions

Two chapters after `first-conversion`, before `safe-defaults`:

| id | Title | Steps |
|---|---|---|
| `record-a-webcam` *new* | Record From a Webcam | Multi-Source Recorder tab → Video Settings → row 1: USB / DirectShow Camera, pick the camera, pick a microphone or No Audio → OK → choose Separate videos and a File location → leave Timer blank → Start Recording → Stop Recording. Where the file lands. |
| `review-a-recording` *new* | Review a Recording | Converted Files → right-click → Play in Media Player (or Media Player tab → Load). Space, Left/Right to step, F for fullscreen. Note: the tab appears for the session even when hidden in Settings. |

## Glossary additions

DirectShow, Media Foundation, RTSP, GenICam / Basler pylon, stream copy,
preset, sync offset, frame step, playlist, redaction, elevation
(administrator), tool tab. Existing entries stay.

## Figures

| id | filename | caption | capture |
|---|---|---|---|
| FIG-02 | unchanged | "Settings, Format tab: output format, codec and bitrate." (already correct in `figures.py`; **SHOTLIST.md** still says "Video tab" — fix) | Settings → Format |
| FIG-08 *new* | `fig-08-media-player.png` | "The Media Player tab with a clip loaded in a single panel." | Media Player tab, one panel, a generated test clip loaded and paused at ~1 s; real display. |
| FIG-09 *new* | `fig-09-recorder-video-settings.png` | "The recorder's Video Settings dialog with two camera rows configured." | Open `VideoSettingsDialog` non-modally (same technique as the settings dialog shots), rows 1–2 set to USB / DirectShow with stand-in devices. |

`capture_screenshots.py` changes:

- `NVC_SHOTS_STUB_DEVICES=1` monkeypatches
  `conversion.recording_sources.discover_directshow_video_devices` and
  `discover_directshow_audio_devices` (and the widget-level names that import
  them) to return `["Camera A", "Camera B"]` / `["Microphone A", "Microphone B"]`
  before `VideoConverterApp` is constructed.
- FIG-08: switch to the Media Player tab, build a `testsrc` MP4 in `%TEMP%`
  with the bundled `ffmpeg.exe`, load it into panel 1, pause at 1000 ms, grab.
  Skip with a message when running offscreen (`NVC_SHOTS_OFFSCREEN=1`), since
  the video surface renders black there.
- FIG-09: construct the recorder's `VideoSettingsDialog` from the recorder
  widget, fill rows 1–2, show non-modally, grab, close.

## Tests

`docs/help/source/test_help_docs.py` gains:

- `test_readme_names_the_current_doc_version` — the README's filename table
  contains `manual_filename("help", "en", "pdf")` for the current
  `DOC_VERSION` (catches the 2.2.0 drift).
- `test_help_covers_every_tool_tab` — the `main-window` chapter's table
  contains each of the seven tab labels (literal list in the test; the app
  strings are `_tr` literals and the docs must quote them exactly).
- `test_help_has_a_chapter_per_tool_tab` — chapter ids include
  `converted-files`, `media-inspection`, `pc-report`, `lossless-editor`,
  `multi-source-recorder`, `media-player`.
- `test_quickstart_has_record_and_review_chapters`.

`tests/test_media_player_widget.py` gains
`test_help_documents_every_shortcut`: instantiates `MediaPlayerWidget`, and
for every key sequence in `widget.shortcuts` asserts its portable text (e.g.
`Shift+Right`) appears in the `media-player` chapter's shortcuts table. Keeps
the manual honest when a shortcut is added or changed.

Existing tests (`FigureTests.test_ids_are_contiguous_and_well_formed`,
`test_shotlist_mentions_every_figure`, parity validation, PDF TOC page check,
`ShippedOutputTests`) cover the rest.

## Build and ship

1. `python docs/help/source/capture_screenshots.py` with
   `NVC_SHOTS_STUB_DEVICES=1`, on the real display. Inspect each PNG.
2. `python docs/help/source/build_help_docs.py` — writes the four 2.3.0 files
   over the shipped ones.
3. `python -m pytest -q -p no:cacheprovider` exit 0; ruff clean on touched
   files; `git diff --check`.
4. CHANGELOG `## 2026-09-25` gains `### Help documentation`. BACKLOG gains a
   "Help documentation follow-ups" list (translated manuals + help-menu
   locale pass-through, Developer Guide) and two recorder follow-ups (inert
   Output quality combo; inert Timer settings group).

## Code inventory used for the content

Kept here so a reviewer can check the prose against the same facts.

- Tabs and defaults: `ui/main_window.py` 522–729; `utils/config.py` 61–75.
- Burger menu: `ui/main_window.py` 822–834, 2475–2514. Tray 1542–1546.
- Settings dialog tabs and controls: `ui/settings_dialog.py` 180–185,
  260–334 (General), 364–424 (Folders), 487–532 (Deletion), 593–874 (Format),
  924–943 (Time), 1004–1021 (Tools).
- Converted Files: `ui/converted_files_widget.py` 135, 161, 234–238, 309–320,
  484–490, 544–561.
- Inspection: `ui/inspection_widget.py` 90–206, 356–360, 465–529.
- PC report: `ui/pc_report_dialog.py` 128–175, 215–265; `pc_report/registry.py`
  14–23; `pc_report/privacy.py` 18–47; `pc_report/render_html.py` 111–142.
- Lossless editor: `ui/lossless_editor_widget.py` 77–134.
- Recorder: `ui/multi_source_recorder_widget.py` 233–300 (dialog rows),
  355–415 (presets), 1011–1124 (main tab), 1182–1201 (output controls), 1400
  ("(not found)"), 2030–2037 (preset folder), 2435/2579 (file names),
  2794–2853 (video-only retry); `conversion/recording_sources.py` 7–33;
  `conversion/recording_commands.py` (audio rules).
- Media player: `ui/media_player_widget.py` 69, 165–183, 484–587, 656–663,
  870–879, 1018–1028; `ui/media_player_parts.py` 58–65, 98–101, 225;
  `ui/media_player_support.py` 25–38, 162–181; `utils/config.py` 70–75;
  `ui/main_window.py` 1393–1407.
- Locales: `utils/localization.py` 54–83. Updates: `utils/update_checker.py`
  25–35. Logs: `utils/logger.py` 9–17. Settings path: `utils/paths.py` 8.
  Extensions: `ui/main_window.py` 62–65. Numbering: `utils/file_naming.py`.
