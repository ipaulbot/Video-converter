# Help Documentation Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the generated NVC Help and Quick Start manuals into line with the application as it exists on master today, add the missing Media Player and recorder material, recapture the figures, and ship regenerated 2.3.0 PDFs/DOCX.

**Architecture:** Content is Python data (`docs/help/source/locales/en/*.py`, one `CHAPTERS: list[dict]` per manual, six block types). Two builders render it to PDF and DOCX; `figures.py` is the figure catalog; `capture_screenshots.py` drives the real app for PNGs. This plan edits only content, the figure catalog, the capture script, tests and the two docs ledgers. No application behaviour changes.

**Tech Stack:** Python 3.12, PyQt5 (capture only), reportlab + python-docx (build, from `docs/help/source/requirements-help.txt`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-25-help-docs-refresh-design.md`. Its "Help manual — chapter plan" table and "Code inventory" section are the source of truth for every sentence written here. Read them first.

## Global Constraints

- Work in `D:\Python Projects\NVC 4`, branch `help-docs-refresh`. Commit after every task; do not push.
- **Never change an existing chapter `id`.** New chapters get new ids. Titles may be reworded.
- **Describe only what the code does.** Before writing a chapter, open the files/lines cited for it in the spec's inventory and quote UI strings exactly (`"Video Inspection Tool"`, not "Inspection"). Do not describe the recorder's "Output quality" combo or "Timer settings" group: they are inert.
- Block grammar is fixed: `para` (`text`), `steps` (`items`), `note` (`items`), `figure` (`fig_id`), `code` (`lines`), `table` (`headers`, `rows` of equal width). Both builders reject anything else.
- Plain ASCII in content; the PDF body font is Helvetica, which has no CJK glyphs, so the Chinese menu entry is written as "Simplified Chinese" (the menu itself shows it in Chinese). The Unicode middle dot in the player readout is fine. Use `--` for dashes as the existing content does. Write `%APPDATA%` style paths, never a real user's path.
- **Privacy:** no real user names, machine names, serials or personal device names anywhere — content, tests, screenshots. Stand-ins are "Camera A", "Camera B", "Microphone A", "Microphone B". After Task 8: `rg -i -c -f %TEMP%\nvc_leak_patterns.txt docs/help/source docs/help/screenshots/SHOTLIST.md tests/` must print nothing (exit 1).
- Tests: `python -m pytest -q -p no:cacheprovider <paths>`; exit code 0 is the pass signal. Docs tests live in `docs/help/source/test_help_docs.py` and run as part of the normal suite.
- Lint: `python -m ruff check <touched files>` clean on files you touched.
- No `QTimer.singleShot` anywhere (repo guard). The capture script uses `_pump()`.
- Do not run `build_help_docs.py` or `capture_screenshots.py` in Tasks 1–7; Task 8 does both once.

---

### Task 1: Figure catalog, shot list and capture script

**Files:**
- Modify: `docs/help/source/figures.py` (FIGURES list)
- Modify: `docs/help/screenshots/SHOTLIST.md`
- Modify: `docs/help/source/capture_screenshots.py`
- Test: `docs/help/source/test_help_docs.py` (`FigureTests`)

**Interfaces:**
- Produces figure ids `FIG-08` (`fig-08-media-player.png`) and `FIG-09` (`fig-09-recorder-video-settings.png`) that Tasks 4 and 5 reference.
- Produces env switch `NVC_SHOTS_STUB_DEVICES=1` used in Task 8.

- [ ] **Step 1: Extend the figure test**

In `docs/help/source/test_help_docs.py`, class `FigureTests`, change `test_number_is_derived_from_id` and add a catalog test:

```python
    def test_number_is_derived_from_id(self):
        self.assertEqual(figures.figure_number("FIG-00"), 0)
        self.assertEqual(figures.figure_number("FIG-09"), 9)
        with self.assertRaises(ValueError):
            figures.figure_number("FIG-7")

    def test_catalog_has_the_media_player_and_video_settings_figures(self):
        by_id = {f["id"]: f for f in figures.FIGURES}
        self.assertEqual(by_id["FIG-08"]["filename"], "fig-08-media-player.png")
        self.assertEqual(by_id["FIG-09"]["filename"], "fig-09-recorder-video-settings.png")
        self.assertIn("Media Player", by_id["FIG-08"]["caption"])
        self.assertIn("Video Settings", by_id["FIG-09"]["caption"])
```

- [ ] **Step 2: Run it, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k "catalog_has or number_is_derived"`
Expected: 1 failed (KeyError `FIG-08`), 1 passed or failed on FIG-09 — either way non-zero exit.

- [ ] **Step 3: Add the two figures**

Append to `FIGURES` in `docs/help/source/figures.py` after the FIG-07 entry:

```python
    {
        "id": "FIG-08",
        "filename": "fig-08-media-player.png",
        "caption": "The Media Player tab with a clip loaded in a single panel.",
        "capture_steps": ("Media Player tab, Panels set to 1, a short test clip loaded and "
                          "paused at about one second. Needs a real display; offscreen "
                          "renders the video surface black."),
    },
    {
        "id": "FIG-09",
        "filename": "fig-09-recorder-video-settings.png",
        "caption": "The recorder's Video Settings dialog with two camera rows configured.",
        "capture_steps": ("Multi-Source Recorder tab -> Video Settings. Rows 1-2 set to USB "
                          "cameras with stand-in names (Camera A, Camera B; Microphone A, "
                          "Microphone B). Do not use real device names."),
    },
```

- [ ] **Step 4: Update SHOTLIST.md**

In `docs/help/screenshots/SHOTLIST.md`:
- FIG-02 row: replace `Settings, Video tab: format, codec, bitrate and size.` with `Settings, Format tab: output format, codec and bitrate.` and `Menu → Settings, Video tab, output format \`mp4\`.` with `Menu → Settings, Format tab, output format \`mp4\`.`
- Add two rows after FIG-07:

```
| FIG-08 | `fig-08-media-player.png` | The Media Player tab with a clip loaded in a single panel. | Media Player tab, Panels = 1, a short generated test clip loaded and paused at ~1 s. Real display only. |
| FIG-09 | `fig-09-recorder-video-settings.png` | The recorder's Video Settings dialog with two camera rows configured. | Recorder tab → Video Settings. Rows 1–2 as USB cameras with stand-in names. Run the capture script with `NVC_SHOTS_STUB_DEVICES=1`. |
```

- Under "Automated capture", add a paragraph:

```
Device names: set `NVC_SHOTS_STUB_DEVICES=1` so DirectShow discovery returns
`Camera A` / `Camera B` and `Microphone A` / `Microphone B` instead of the
devices attached to your PC. Personal device names must never be committed.
```

Also fix the mojibake dashes/arrows in the file (`�?"` → `—`, `�+'` → `→`, `A-` → `×`) so the file is clean UTF-8.

- [ ] **Step 5: Run the figure tests, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k FigureTests`
Expected: all pass (contiguity, uniqueness, shotlist mentions, the new catalog test).

- [ ] **Step 6: Add the device stub and the two new shots to the capture script**

In `docs/help/source/capture_screenshots.py`:

(a) After `sys.path.insert(0, str(ROOT))` and before the PyQt import, add:

```python
STUB_DEVICES = os.environ.get("NVC_SHOTS_STUB_DEVICES") == "1"
STUB_CAMERAS = ["Camera A", "Camera B"]
STUB_MICROPHONES = ["Microphone A", "Microphone B"]


def _stub_device_discovery() -> None:
    """Replace DirectShow discovery so screenshots never show real device names.

    The recorder widget imports the discovery functions by name, so the patch
    has to land on the widget module, not just on conversion.recording_sources.
    """
    import conversion.recording_sources as sources
    import ui.multi_source_recorder_widget as recorder

    def cameras(*_args, **_kwargs):
        return list(STUB_CAMERAS)

    def microphones(*_args, **_kwargs):
        return list(STUB_MICROPHONES)

    for module in (sources, recorder):
        module.discover_directshow_video_devices = cameras
        module.discover_directshow_audio_devices = microphones
```

(b) In `main()`, right after `app = QApplication.instance() or QApplication([])` and before `from ui.main_window import VideoConverterApp`, add:

```python
    if STUB_DEVICES:
        _stub_device_discovery()
        print("  (DirectShow discovery stubbed: stand-in camera and microphone names)")
```

(c) After `attempt("FIG-07", lambda: show_tab("Multi-Source Recorder"))`, add the two shots:

```python
    # FIG-08: the Media Player with a clip. The widget is built lazily by the
    # main window, so ask the window for it rather than reaching into the tab.
    def media_player_with_clip():
        if os.environ.get("NVC_SHOTS_OFFSCREEN") == "1":
            print("  -- FIG-08: needs a real display (video surface is black offscreen)")
            return None
        if show_tab("Media Player") is None:
            return None
        widget = window._ensure_media_player_widget()
        _pump(app, 10)
        clip = _make_test_clip()
        if clip is None:
            return None
        widget.set_visible_panel_count(1)
        panel = widget.panels[0]
        if not panel.load_media(clip):
            return None
        # Let the backend report duration, then park on a visible frame.
        for _ in range(60):
            _pump(app, 4)
            if panel.player is not None and panel.player.duration() > 0:
                break
        widget.play_all()
        for _ in range(30):
            _pump(app, 4)
            if panel.player is not None and panel.player.position() >= 1000:
                break
        widget.pause_all()
        _pump(app, 10)
        return window

    attempt("FIG-08", media_player_with_clip)

    # FIG-09: the recorder's Video Settings dialog, shown non-modally like the
    # settings dialog above, with rows 1-2 filled from the stub device list.
    def recorder_video_settings():
        if show_tab("Multi-Source Recorder") is None:
            return None
        from ui.multi_source_recorder_widget import VideoSettingsDialog
        recorder = window.multi_source_recorder_widget
        recorder.directshow_devices = list(STUB_CAMERAS) if STUB_DEVICES else recorder.discover_directshow_devices()
        dialog = VideoSettingsDialog(recorder.source_rows, recorder.output_controls(),
                                     recorder, recorder.button_style)
        dialog.setModal(False)
        dialog.show()
        _pump(app, 12)
        cameras = recorder.directshow_devices[:2]
        for index, camera in enumerate(cameras):
            row_enabled, row_label, _type, row_device, _fps, _res, row_audio_name, row_audio, _off = dialog.dialog_rows[index]
            row_enabled.setChecked(True)
            row_label.setText(f"Video {index + 1}")
            row_device.setText(camera)
            row_audio_name.setText(f"Audio {index + 1}")
            if STUB_DEVICES:
                mic_index = row_audio.findText(STUB_MICROPHONES[index % len(STUB_MICROPHONES)])
                if mic_index >= 0:
                    row_audio.setCurrentIndex(mic_index)
        _pump(app, 12)
        return dialog

    attempt("FIG-09", recorder_video_settings)
```

(d) Add the clip helper at module level (above `main()`):

```python
def _make_test_clip():
    """A 6 s colour-bar MP4 in %TEMP%, made with the bundled ffmpeg. None on failure."""
    import subprocess
    import tempfile

    from utils.resources import resource_path

    out = Path(tempfile.gettempdir()) / "nvc_help_fig08_clip.mp4"
    cmd = [resource_path("ffmpeg.exe"), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=25",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  -- FIG-08: could not make a test clip: {exc}")
        return None
    return str(out)
```

`set_visible_panel_count(count)` is the method the Panels combo calls (`ui/media_player_widget.py:804`); do not add a method to the widget. If `row_audio.findText` does not find the stub name because discovery is asynchronous, call `recorder._apply_audio_devices(STUB_MICROPHONES)` before constructing the dialog (the method exists; see `start_audio_device_discovery`).

- [ ] **Step 7: Offscreen dry run of the capture script**

Run: `$env:NVC_SHOTS_OFFSCREEN="1"; $env:NVC_SHOTS_STUB_DEVICES="1"; python docs/help/source/capture_screenshots.py; Remove-Item Env:NVC_SHOTS_OFFSCREEN; Remove-Item Env:NVC_SHOTS_STUB_DEVICES`
Expected: script exits 0, prints `FIG-08: needs a real display`, and either `ok FIG-09 -> fig-09-recorder-video-settings.png` or a clear reason. Then **discard the PNGs it wrote**: `git checkout -- docs/help/screenshots/` and delete any new untracked PNG (`git clean -n docs/help/screenshots` to list, then `git clean -f docs/help/screenshots/*.png`). Task 8 captures for real.

- [ ] **Step 8: Lint and commit**

Run: `python -m ruff check docs/help/source/figures.py docs/help/source/capture_screenshots.py docs/help/source/test_help_docs.py`
Expected: `All checks passed!`

```bash
git add docs/help/source/figures.py docs/help/screenshots/SHOTLIST.md docs/help/source/capture_screenshots.py docs/help/source/test_help_docs.py
git commit -m "docs(help): add Media Player and Video Settings figures; stub device names in capture"
```

---

### Task 2: Help chapters 1–11 (introduction through converted-files)

**Files:**
- Modify: `docs/help/source/locales/en/help.py` — chapters `introduction`, `quick-start`, `main-window`, `converting-files`, `conversion-settings`, `gpu-encoding`, `gif-export`, `text-overlays`, `original-files`; add `time-restrictions`, `converted-files`
- Test: `docs/help/source/test_help_docs.py` (`ContentTests`)

**Interfaces:**
- Consumes: spec chapter-plan rows 1–11 and inventory lines for `ui/main_window.py`, `ui/settings_dialog.py`, `ui/converted_files_widget.py`, `utils/config.py`, `utils/file_naming.py`, `conversion/ffmpeg_utils.py:29-50`.
- Produces: chapter ids `time-restrictions`, `converted-files` (Task 6's troubleshooting rows refer to them by name only).

- [ ] **Step 1: Write the failing tests**

Add to `ContentTests` in `docs/help/source/test_help_docs.py`:

```python
    TOOL_TAB_LABELS = (
        "Conversion Log", "Converted Files", "Video Inspection Tool", "PC Report",
        "Lossless Editor", "Multi-Source Recorder", "Media Player",
    )

    def _chapter(self, manual_key, chapter_id):
        for chapter in cl.load_manual(manual_key, "en"):
            if chapter["id"] == chapter_id:
                return chapter
        self.fail(f"{manual_key} has no chapter {chapter_id!r}")

    def _chapter_text(self, manual_key, chapter_id):
        parts = []
        for block in self._chapter(manual_key, chapter_id)["blocks"]:
            if block["type"] == "para":
                parts.append(block["text"])
            elif block["type"] in ("steps", "note", "code"):
                parts.extend(block.get("items", block.get("lines", [])))
            elif block["type"] == "table":
                parts.extend(cell for row in block["rows"] for cell in row)
        return "\n".join(parts)

    def test_help_covers_every_tool_tab(self):
        text = self._chapter_text("help", "main-window")
        for label in self.TOOL_TAB_LABELS:
            self.assertIn(label, text, label)

    def test_help_settings_chapter_names_every_settings_tab(self):
        text = self._chapter_text("help", "conversion-settings")
        for tab in ("General", "Folders", "Deletion", "Format", "Time", "Tools"):
            self.assertIn(tab, text, tab)

    def test_help_has_time_restrictions_and_converted_files_chapters(self):
        ids = [c["id"] for c in cl.load_manual("help", "en")]
        self.assertIn("time-restrictions", ids)
        self.assertIn("converted-files", ids)
```

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k "tool_tab or settings_tab or time_restrictions"`
Expected: 3 failed ("Video Inspection Tool" missing, "Folders" missing, ids missing).

- [ ] **Step 3: Rewrite chapters 1–11**

Edit `CHAPTERS` in `docs/help/source/locales/en/help.py`. Keep ids. Required content per chapter (write full sentences; every claim must match the cited code):

`introduction` — one `para` (converter around FFmpeg; watches a source folder; inspects media; records up to four sources; plays back side by side; generates a PC report; can clean up originals), `figure` FIG-00, `note` with the overwrite policy (unchanged wording is fine).

`quick-start` — `para` + `steps` (6): Open Settings from the menu → Folders tab: Source Folder → Folders tab: Destination Folder → Format tab: Output Format / Video Codec / Audio Codec (defaults suit most cases) → OK, then Start → drop videos into the source folder. `figure` FIG-01.

`main-window` — `para`; `table` ("Area", "What it does") with rows for exactly these labels in this order: "Conversion Log", "Converted Files", "Video Inspection Tool", "PC Report", "Lossless Editor", "Multi-Source Recorder", "Media Player", "Preview Panel", "Menu". Then a `note`:
  - Hidden by default: PC Report, Lossless Editor and Media Player. Turn them on in Settings → Tools. Play in Media Player shows the Media Player tab for the current session even when it is switched off.
  - Menu items: Info, Help, Open Source Folder, Open Destination Folder, Open Backup Folder, Settings, Language, Check for Updates, Quit.
  - Footer: Start/Stop button (reads Start Recording / Stop Recording on the recorder tab), lock icon (locks settings; the Start button then reads Locked), file picker (select media files to convert), broom (clear log), status label.
  - Closing the window minimises NVC to the system tray unless "Close on X (don't minimize to tray)" is set in Settings → General; the tray menu has Show and Quit. Only one copy of NVC can run at a time.

`converting-files` — `para` monitoring/scan on start; `para` drag-and-drop onto Conversion Log, Converted Files or Video Inspection Tool, or the footer file picker; `para` + `code` numbering (Session.mp4 / Session (1).mp4 / Session (2).mp4); `para` listing the extensions from `ui/main_window.py:62-65` in upper case: MP4, AVI, WMV, MKV, FLV, WebM, MOV, MPEG, MPG, M4V, 3GP, TS, VOB, RM, RMVB, ASF, M2TS, MTS, OGV, DIVX, DV, F4V; `figure` FIG-03.

`conversion-settings` — `para` ("Settings has six tabs: General, Folders, Deletion, Format, Time and Tools. Default restores every value; OK saves; Cancel discards."); `figure` FIG-02; then one `table` ("Setting", "Guidance") per tab, each preceded by a short `para` naming the tab. Rows:
  - General: "Auto Run on Startup", "Copy Only", "Close on X (don't minimize to tray)", "Launch at Windows startup (All Users)", "Use GPU Acceleration", "GPU Encoder" (Auto, nvidia, intel, amd).
  - Folders: "Source Folder", "Destination Folder", "Backup Folder", "Log Folder" (each with Change).
  - Deletion: one `para` pointing to the Original File Handling chapter (no table).
  - Format: "Output Format" (mp4, mov, avi, mkv, flv, webm, mpeg, mpg, 3gp, ogg, wmv, m4v, mp3, gif), "Video Codec" (libx264, mpeg4, libvpx, hevc, flv, libtheora, wmv2), "Audio Codec" (aac, mp3, ac3, opus, vorbis), "GIF options" (FPS, Max Width, Loop, Quick GIF (no palette); shown when Output Format is gif), "Show Advanced Options", "Video Size" (Auto, 640x480, 1280x720, 1920x1080, 3840x2160), "Bitrate" (Auto or 512k–3000k), "Frame Rate" (Auto or 8–60), "Keyframe Interval (GOP)" (0 = Auto, up to 300), "Volume" (0–500 %), "Text Overlay" (see Text Overlays), "Console Integration" (custom FFmpeg flags), "Presets" (Ethovision, Custom 1, Custom 2, Save to 1, Save to 2).
  - Time: "No Time Restrictions", "Start Time", "End Time" (see Time Restrictions).
  - Tools: one checkbox per tool tab; unticked tabs are hidden from the main window.

`gpu-encoding` — keep as is.

`gif-export` — `para` using the real names FPS, Max Width, Loop, Quick GIF (no palette); keep the `note`.

`text-overlays` — `para` + `table` ("Overlay", "Shows") for None, Elapsed Time, Recorded Time, Recorded Date/Time, Recorded Date/Time + Remaining, CRTV Cam. Keep the caveat about filtering and GPU compatibility.

`original-files` — `table` ("Option", "Behaviour") for "Delete files after conversion", "Retention time (days)" (0–30; pending deletions are stored on disk and processed after a restart), "Use Backup Folder" (moves originals to the Backup Folder instead of deleting); `note` keep originals until you trust the output.

`time-restrictions` (new, after `original-files`) — title "Time Restrictions"; `para` explaining Settings → Time; `note` items: a file detected outside the window is skipped with "Current time outside allowed range" in the Conversion Log and is not queued for later; an End Time earlier than the Start Time means an overnight window; the default is No Time Restrictions.

`converted-files` (new, after `time-restrictions`) — title "Converted Files"; `para` (columns File Name, Destination Folder, Date Modified; status icons for queued, processing, success, failure); `table` ("Control", "What it does"): "Play" (opens the selected file in the Media Player tab), "Clear", "Play in Media Player" (context menu), "Open Containing Folder", "Open Log File" (per-file conversion log dialog), "Copy File Path", "Settings"; `figure` FIG-03 may stay in `converting-files` — do not reference it twice.

- [ ] **Step 4: Run the content tests, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k "ContentTests or NavigationTests"`
Expected: all pass (parity validation, figure references, new tests).

- [ ] **Step 5: Lint and commit**

Run: `python -m ruff check docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py`

```bash
git add docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py
git commit -m "docs(help): rewrite main window, settings and conversion chapters to match the app"
```

---

### Task 3: Help chapters — media-inspection, pc-report, lossless-editor

**Files:**
- Modify: `docs/help/source/locales/en/help.py` — chapters `media-inspection`, `pc-report`, `lossless-editor`
- Test: `docs/help/source/test_help_docs.py`

**Interfaces:**
- Consumes: `pc_report/registry.py:14-23` (`ORDER`), `pc_report/privacy.py:18-47`, `pc_report/render_html.py:111-142`, `pc_report/section.py:130-135`, `ui/pc_report_dialog.py:128-175,215-265`, `ui/inspection_widget.py`, `ui/lossless_editor_widget.py:77-134`.

- [ ] **Step 1: Write the failing test**

Add to `ContentTests`:

```python
    def test_pc_report_chapter_lists_every_section_in_registry_order(self):
        import importlib
        registry = importlib.import_module("pc_report.registry")
        titles = [getattr(s, "title", s) if not isinstance(s, str) else s
                  for s in registry.ORDER]
        text = self._chapter_text("help", "pc-report")
        for title in titles:
            self.assertIn(str(title), text, title)
        self.assertNotIn("redaction enabled", text.lower())
```

Open `pc_report/registry.py` first: if `ORDER` holds section keys rather than titles, resolve titles the way `render_html.py` does and adapt the test accordingly (the assertion is "every rendered section title appears in the chapter").

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k pc_report_chapter`
Expected: FAIL (section titles missing / "redaction enabled" present).

- [ ] **Step 3: Rewrite the three chapters**

`media-inspection` — `para`: the "Video Inspection Tool" tab has "Summary" and "Detailed JSON" sub-tabs; drop a file on either; Summary lists File, Container, Duration, Size, Bitrate, Number of Streams, then each video/audio/subtitle stream (codec, resolution, frame rate, channels) and a "Keyframe Analysis (First 30s)" block; Detailed JSON is the raw `ffprobe -print_format json` output. `figure` FIG-04.

`pc-report` — `para` (what it is for); `steps`: click "Generate PC Report"; wait (some collectors take a while); "Open Report" opens the HTML, "Open Folder" opens the Desktop; the file is `PC_Report_YYYYMMDD_HHMMSS.html` and an existing file is never overwritten. `figure` FIG-05. `para` "The report opens with Report Health (timing, empty sections, warnings) and then these sections:" followed by a `code` block listing every title from `pc_report/registry.py` `ORDER`, in order, one per line (Noldus Summary first, Network Connections last). `note` items:
  - Redaction is always on. Masked: serial numbers, licence keys, passwords and tokens, user and machine names, hostnames, IP and MAC addresses, proxy settings, UNC paths and user profile paths. Review a report before sharing it anyway.
  - Some values need administrator rights and show "Requires administrator" when NVC runs normally. Right-click NVC and choose Run as administrator for a complete report.
  - Drivers, devices, network connections and processes are the slow collectors on large systems.

`lossless-editor` — keep the structure; use the real labels "Trim Losslessly", "Remux", "Extract Audio", "Remove Audio", "Merge Losslessly", "Add Files", "Clear"; output containers mp4, mkv, mov, avi and m4a (audio). Keep both notes (compatibility; keyframe shift). `figure` FIG-06.

- [ ] **Step 4: Run, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py`
Expected: all pass.

- [ ] **Step 5: Lint and commit**

```bash
python -m ruff check docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py
git add docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py
git commit -m "docs(help): rewrite inspection, PC report and lossless editor chapters"
```

---

### Task 4: Help chapter — multi-source-recorder

**Files:**
- Modify: `docs/help/source/locales/en/help.py` — chapter `multi-source-recorder`
- Test: `docs/help/source/test_help_docs.py`

**Interfaces:**
- Consumes: FIG-07, FIG-09 from Task 1; spec chapter-plan row 15 and inventory for `ui/multi_source_recorder_widget.py`, `conversion/recording_sources.py:7-33`, `conversion/recording_commands.py`.

- [ ] **Step 1: Write the failing test**

```python
    def test_recorder_chapter_covers_video_settings_and_presets(self):
        text = self._chapter_text("help", "multi-source-recorder")
        for needle in ("Video Settings", "RTSP/IP Camera", "Refresh USB devices",
                       "Separate videos", "Combined grid", "Save as", "(not found)",
                       "Sync offset", "Start Recording"):
            self.assertIn(needle, text, needle)
        fig_ids = [b["fig_id"] for b in self._chapter("help", "multi-source-recorder")["blocks"]
                   if b["type"] == "figure"]
        self.assertEqual(fig_ids, ["FIG-07", "FIG-09"])
        for forbidden in ("Output quality", "Timer settings", "Time format"):
            self.assertNotIn(forbidden, text, forbidden)
```

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k recorder_chapter`
Expected: FAIL.

- [ ] **Step 3: Rewrite the chapter**

Blocks, in order:
1. `para` — up to four sources recorded at once with FFmpeg; the tab shows one row per source; sources are configured in the Video Settings dialog.
2. `figure` FIG-07.
3. `para` "The recorder tab" + `table` ("Control", "What it does"): "Use" (record this row), "Video name" (label used in the file name), "Audio name", "Mute", "Volume" (100, 75, 50, 25, 0 %), "Encoding" (copy keeps the camera or stream's own compressed video; h264 re-encodes), "Output mode" ("Separate videos" = one file per row; "Combined grid" = one file with all sources tiled), "File location" (default: your Videos folder), "File base name" (default Video; files are named `<base>_<Video name>_<timestamp>.mp4`, or `<base>_Combined_<timestamp>.mp4`), "Timer" (blank = record until you press Stop Recording), "Show recording log", "Start Recording / Stop Recording" (the footer button).
4. `para` "Video Settings" + `figure` FIG-09 + `steps`:
   - Open Video Settings. Each row has Use, Video name, Video device, a camera settings button, Frame rate, Resolution, Audio name, Audio device and Sync offset.
   - In Video device choose a USB camera by its Windows name, choose "RTSP/IP Camera" and click the camera button to enter Address / URL, Username, Password, Port and Stream path, or type an rtsp://, http:// or https:// URL, a file path, or a Basler / GenICam source string directly. "Refresh USB devices..." rescans.
   - For a USB camera NVC reads the frame rates and resolutions the driver reports and offers those; if detection fails, leave both at Auto.
   - Choose an Audio device per row, or No Audio. "Refresh devices" rescans microphones. Mute or Volume 0 on the tab records that row without sound.
   - Sync offset shifts a source earlier or later in a Combined grid recording so clips that started at slightly different times line up.
   - Apply keeps the dialog open; OK applies and closes.
5. `para` "Presets" + `steps`: Load applies the selected preset; Set overwrites it with the current settings; "Save as..." creates a new one; Delete removes it. An asterisk after the name marks unsaved changes. Presets are JSON files under `Public\Documents\Noldus\NVC\MediaRecorder\Presets`.
6. `note` items:
   - Audio rules: without a microphone, a file or RTSP source in h264 mode keeps its own sound track; in copy mode an RTSP source is recorded without audio; a USB camera without a microphone is silent. Combined grid takes its audio from the first enabled, unmuted row with a microphone.
   - A saved microphone that is not connected shows as "(not found)". If the audio device fails as recording starts, NVC restarts that row as video only and says so in the recording log, so the camera recording is not lost.
   - FFmpeg needs the exact Windows camera name; close other applications that may be using the camera.

- [ ] **Step 4: Run, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py`

- [ ] **Step 5: Lint and commit**

```bash
python -m ruff check docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py
git add docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py
git commit -m "docs(help): rewrite the Multi-Source Recorder chapter around Video Settings and presets"
```

---

### Task 5: Help chapter — media-player, with shortcut coverage test

**Files:**
- Modify: `docs/help/source/locales/en/help.py` — add chapter `media-player` after `multi-source-recorder`
- Test: `docs/help/source/test_help_docs.py`; `tests/test_media_player_widget.py`

**Interfaces:**
- Consumes: FIG-08 from Task 1; `MediaPlayerWidget._shortcut_table()` keys (`ui/media_player_widget.py:572-587`); `ui/media_player_parts.py:225` overlay text; `ui/media_player_support.py:162-181` (`unsupported_message`, `player_convert_settings`); `utils/config.py:70-75`.
- Produces: chapter id `media-player`; a `table` block with headers `("Keys", "Action")` that the widget test reads.

- [ ] **Step 1: Write the failing tests**

In `docs/help/source/test_help_docs.py` `ContentTests`:

```python
    def test_help_has_a_chapter_per_tool_tab(self):
        ids = [c["id"] for c in cl.load_manual("help", "en")]
        for chapter_id in ("converted-files", "media-inspection", "pc-report",
                           "lossless-editor", "multi-source-recorder", "media-player"):
            self.assertIn(chapter_id, ids)
```

In `tests/test_media_player_widget.py`, inside `MediaPlayerWidgetTests`:

```python
    def test_help_documents_every_shortcut(self):
        import sys
        from pathlib import Path

        source_dir = Path(__file__).resolve().parents[1] / "docs" / "help" / "source"
        if str(source_dir) not in sys.path:
            sys.path.insert(0, str(source_dir))
        import content_loader

        chapter = next(c for c in content_loader.load_manual("help", "en")
                       if c["id"] == "media-player")
        tables = [b for b in chapter["blocks"]
                  if b["type"] == "table" and b["headers"][0] == "Keys"]
        self.assertEqual(len(tables), 1, "media-player needs exactly one Keys/Action table")
        documented = "\n".join(cell for row in tables[0]["rows"] for cell in row)
        widget = self._widget()
        for key in widget.shortcuts:
            self.assertIn(key, documented, f"shortcut {key} is not in the manual")
```

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k chapter_per_tool_tab tests/test_media_player_widget.py -k documents_every_shortcut`
Expected: both FAIL (no `media-player` chapter).

- [ ] **Step 3: Write the chapter**

Insert after `multi-source-recorder`:

```python
    {
        "id": "media-player",
        "title": "Media Player",
        "blocks": [
            {"type": "para", "text": (...)},   # what it is; hidden by default; Settings -> Tools; Play in Media Player shows it for the session
            {"type": "figure", "fig_id": "FIG-08"},
            {"type": "table", "headers": ("Control", "What it does"), "rows": [...]},
            {"type": "para", "text": (...)},   # readout format and frame-accurate stepping
            {"type": "table", "headers": ("Keys", "Action"), "rows": [...]},
            {"type": "para", "text": (...)},   # fullscreen
            {"type": "para", "text": (...)},   # playlist
            {"type": "note", "items": [...]},  # unsupported files, persistence, backend
        ],
    },
```

Fill the placeholders (the `...` above are for the plan only; the file must contain finished prose):

- Controls table rows: "Load" / "Clear" (per panel), "offset" (seconds; shifts that panel relative to the shared seek position), "Play all" (reads Pause all while playing), "Stop all", "Restart", seek slider, "Speed" (0.25x, 0.5x, 1x, 1.5x, 2x — `PLAYBACK_SPEEDS` in `ui/media_player_widget.py:65`), "Panels" (1, 2 or 4), "Volume", "Mute", "Fullscreen", "Playlist".
- Readout para: `H:MM:SS.mmm / H:MM:SS.mmm · frame N / M`; NVC reads the clip's real frame rate with FFprobe so Left/Right step exactly one frame; stepping pauses playback.
- Keys table rows, exactly these key spellings (they are the `QKeySequence` strings): ("Space", "Play or pause"), ("Home", "Restart from the beginning"), ("Left", "Step back one frame"), ("Right", "Step forward one frame"), ("Shift+Left", "Seek back 5 seconds"), ("Shift+Right", "Seek forward 5 seconds"), ("Up", "Volume up 5"), ("Down", "Volume down 5"), ("M", "Mute or unmute"), ("F", "Toggle fullscreen"), ("Escape", "Leave fullscreen"), ("N", "Next playlist item"), ("P", "Previous playlist item"). Shortcuts work while the Media Player tab has focus.
- Fullscreen para: F, the Fullscreen button, or double-click a panel; the transport bar hides three seconds after the mouse stops moving and returns on movement; Esc, F or double-click leaves.
- Playlist para: the Playlist button opens a dock for the selected panel with "Add files...", "Add folder...", "Remove", "Clear"; drag to reorder; drop files from Explorer; N/P move through it; with Panels set to 1 the next item starts automatically when a clip ends.
- Note items: (1) a file Windows cannot decode shows "Windows cannot play this file." (or names the codec and container) with "Convert to MP4 (H.264) and play"; the converted copy is written to your Destination Folder with a unique name and then loaded; (2) NVC remembers the last folder, panel count, volume and mute between sessions; (3) playback uses Windows Media Foundation, so MP4, MOV, MKV, AVI and WMV files with common codecs play directly; use the convert offer for anything else.

- [ ] **Step 4: Run, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py tests/test_media_player_widget.py`
Expected: all pass.

- [ ] **Step 5: Lint and commit**

```bash
python -m ruff check docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py tests/test_media_player_widget.py
git add docs/help/source/locales/en/help.py docs/help/source/test_help_docs.py tests/test_media_player_widget.py
git commit -m "docs(help): add the Media Player chapter; pin every shortcut to the manual"
```

---

### Task 6: Help chapters — language, updates-and-logs, troubleshooting, best-practices, faq; glossary

**Files:**
- Modify: `docs/help/source/locales/en/help.py` — add `language`, `updates-and-logs` after `media-player`; revise `troubleshooting`, `best-practices`, `faq`
- Modify: `docs/help/source/locales/en/glossary.py`
- Test: `docs/help/source/test_help_docs.py`

**Interfaces:**
- Consumes: `utils/localization.py:54-83`, `utils/update_checker.py:25-35`, `ui/main_window.py:2946-2951`, `utils/logger.py:9-17`, `utils/paths.py:8`, `utils/config.py:78`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_help_has_language_and_updates_chapters(self):
        ids = [c["id"] for c in cl.load_manual("help", "en")]
        self.assertIn("language", ids)
        self.assertIn("updates-and-logs", ids)
        text = self._chapter_text("help", "language")
        for name in ("English", "Nederlands", "Simplified Chinese"):
            self.assertIn(name, text, name)

    def test_troubleshooting_covers_recorder_and_player(self):
        text = self._chapter_text("help", "troubleshooting")
        for needle in ("Could not find video device", "(not found)",
                       "Windows cannot play this file", "Settings", "NVC_LOG_LEVEL"):
            self.assertIn(needle, text, needle)

    def test_glossary_defines_the_new_terms(self):
        import importlib
        glossary = importlib.import_module("locales.en.glossary")
        terms = {row[0] for row in glossary.GLOSSARY_ROWS}
        for term in ("Media Foundation", "GenICam", "Preset", "Sync offset",
                     "Frame step", "Playlist", "Administrator (elevation)", "Tool tab"):
            self.assertIn(term, terms, term)
```

Check how `content_loader.py` imports locale packages (`_LOCALE_PACKAGES`) and use the same import path in the glossary test if `locales.en.glossary` does not resolve.

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k "language_and_updates or troubleshooting_covers or glossary_defines"`
Expected: 3 FAIL.

- [ ] **Step 3: Write and revise the chapters**

`language` (new) — `para`: Menu → Language lists English, Nederlands and Simplified Chinese (the last entry appears in the menu in Chinese characters); the choice is saved and NVC asks you to restart so every window is retranslated; the manuals are in English.

`updates-and-logs` (new) — `table` ("Item", "Where / what"): "Check for Updates" (menu; a build without an update address answers "Updates Not Configured"; when one is configured and a newer version exists, "Update Available!" appears in the sidebar), "Log file" (`%APPDATA%\NVC\logs\conversion_log.txt` unless Settings → Folders → Log Folder points elsewhere; rotates), "NVC_LOG_LEVEL" (environment variable; set to DEBUG to record full tracebacks), "Settings file" (`%APPDATA%\NVC\config.json`), "Default media folders" (`Public\Documents\Noldus\NVC\Source`, `Destination`, `Backup`), "Recorder presets" (`Public\Documents\Noldus\NVC\MediaRecorder\Presets`).

`troubleshooting` — keep existing rows but change "PC report is slow" wording to name the slow collectors, and add rows: ("Camera: Could not find video device", "FFmpeg needs the exact Windows camera name. Pick it from the Video device list rather than typing it, and close other applications that may hold the camera."), ("Microphone shows (not found)", "The saved microphone is not connected. Plug it in and click Refresh devices, or choose another device or No Audio."), ("Recording has no sound", "Check Mute and Volume on the tab and the Audio device in Video Settings. If the audio device failed at start, NVC recorded video only and says so in the recording log."), ("Media Player says Windows cannot play this file", "The codec or container is not supported by Windows Media Foundation. Click Convert to MP4 (H.264) and play."), ("A tool tab is missing", "Open Settings, Tools tab, and tick it."), ("Help menu says the document was not found", "The generated manual must sit in docs/help (or next to the executable). Rebuild it with python docs/help/source/build_help_docs.py."). Keep the NVC_LOG_LEVEL row and the closing `para`.

`best-practices` — add two `steps` items: "Save a recorder preset for each camera setup so a session starts with one Load." and "Review recordings with Panels set to 1 when you want the playlist to advance automatically."

`faq` — add rows: ("Where do recordings go?", "The File location on the recorder tab, your Videos folder by default, named <base>_<Video name>_<timestamp>.mp4 or <base>_Combined_<timestamp>.mp4."), ("Why does my MKV not play in the Media Player?", "Windows Media Foundation does not decode every codec. Use Convert to MP4 (H.264) and play; the copy goes to your Destination Folder."), ("Can I record without a microphone?", "Yes. Choose No Audio, or Mute the row. A file or RTSP source in h264 mode keeps its own sound track."), ("Why does the PC report say Requires administrator?", "Some Windows data is only readable elevated. Run NVC as administrator for a complete report; redaction still applies.").

`glossary.py` — append rows (keep existing): ("Media Foundation", ...Windows playback framework the Media Player uses...), ("GenICam", ...generic camera interface used by Basler and other industrial cameras; configured in Basler pylon Viewer...), ("Preset", ...saved recorder configuration, stored as JSON under Public\Documents\Noldus\NVC\MediaRecorder\Presets...), ("Sync offset", ...), ("Frame step", ...moving exactly one frame using the clip's frame rate...), ("Playlist", ...), ("Administrator (elevation)", ...running NVC with administrator rights so the PC report can read protected data...), ("Tool tab", ...a main-window tab that can be hidden in Settings → Tools...). Update the existing "Redaction" row to say it is always on.

- [ ] **Step 4: Run all docs tests, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py`

- [ ] **Step 5: Lint and commit**

```bash
python -m ruff check docs/help/source/locales/en/help.py docs/help/source/locales/en/glossary.py docs/help/source/test_help_docs.py
git add docs/help/source/locales/en/help.py docs/help/source/locales/en/glossary.py docs/help/source/test_help_docs.py
git commit -m "docs(help): language, updates and logs, troubleshooting, FAQ and glossary for the new features"
```

---

### Task 7: Quick Start Guide — record and review chapters

**Files:**
- Modify: `docs/help/source/locales/en/quickstart.py`
- Test: `docs/help/source/test_help_docs.py`

**Interfaces:** none beyond the shared block grammar. Independent of Tasks 2–6 (different file).

- [ ] **Step 1: Write the failing test**

```python
    def test_quickstart_has_record_and_review_chapters(self):
        ids = [c["id"] for c in cl.load_manual("quickstart", "en")]
        self.assertEqual(ids[:4], ["before-you-start", "first-conversion",
                                   "record-a-webcam", "review-a-recording"])
        record = self._chapter_text("quickstart", "record-a-webcam")
        for needle in ("Video Settings", "Start Recording", "Stop Recording"):
            self.assertIn(needle, record, needle)
        review = self._chapter_text("quickstart", "review-a-recording")
        for needle in ("Play in Media Player", "Space", "F"):
            self.assertIn(needle, review, needle)
```

(`_chapter_text` comes from Task 2. If Task 7 runs before Task 2 lands, copy the helper into the test class; the second copy is removed when the branches meet.)

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k quickstart_has`

- [ ] **Step 3: Add the chapters**

Insert after `first-conversion`, before `safe-defaults`:

```python
    {
        "id": "record-a-webcam",
        "title": "Record From a Webcam",
        "blocks": [
            {"type": "para", "text": (
                "The Multi-Source Recorder captures up to four cameras or streams. One USB "
                "webcam is the simplest case.")},
            {"type": "steps", "items": [
                "Open the Multi-Source Recorder tab and click Video Settings.",
                "In row 1, open the Video device list and pick your camera by its Windows "
                "name. If it is missing, choose Refresh USB devices...",
                "Pick a microphone in Audio device, or No Audio. Leave Frame rate and "
                "Resolution at the values NVC detected, or Auto.",
                "Click OK. Back on the tab, choose Separate videos and a File location.",
                "Leave Timer blank, then click Start Recording in the footer. Click Stop "
                "Recording when you are done.",
            ]},
            {"type": "para", "text": (
                "The file is written to the File location as Video_<name>_<timestamp>.mp4. "
                "Save the setup as a preset in Video Settings so the next session is one "
                "Load away.")},
        ],
    },
    {
        "id": "review-a-recording",
        "title": "Review a Recording",
        "blocks": [
            {"type": "steps", "items": [
                "In Converted Files, right-click a file and choose Play in Media Player. "
                "Or open the Media Player tab and click Load on a panel.",
                "Press Space to play or pause, Left and Right to step one frame, "
                "Shift+Left and Shift+Right to jump 5 seconds.",
                "Press F for fullscreen and Esc to come back.",
                "Set Panels to 2 or 4 to compare recordings side by side; each panel has "
                "its own offset to line up clips that started at different times.",
            ]},
            {"type": "note", "items": [
                "The Media Player tab is hidden by default. Play in Media Player shows it "
                "for this session; tick it in Settings, Tools tab, to keep it.",
            ]},
        ],
    },
```

- [ ] **Step 4: Run, expect pass**

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py`

- [ ] **Step 5: Lint and commit**

```bash
python -m ruff check docs/help/source/locales/en/quickstart.py docs/help/source/test_help_docs.py
git add docs/help/source/locales/en/quickstart.py docs/help/source/test_help_docs.py
git commit -m "docs(quickstart): add record-a-webcam and review-a-recording chapters"
```

---

### Task 8: README version, capture, build, ship, ledgers (lead runs this — needs the real display)

**Files:**
- Modify: `docs/help/README.md`
- Test: `docs/help/source/test_help_docs.py` (`ShippedOutputTests`)
- Regenerate: `docs/help/screenshots/fig-*.png`, `docs/help/NVC 2.3.0 - Help - en.{pdf,docx}`, `docs/help/NVC 2.3.0 - Quick Start Guide - en.{pdf,docx}`
- Modify: `docs/CHANGELOG.md`, `docs/BACKLOG.md`

- [ ] **Step 1: Failing README test**

```python
    def test_readme_names_the_current_doc_version(self):
        readme = (SOURCE_DIR.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn(registry.manual_filename("help", "en", "pdf"), readme)
        self.assertIn(registry.manual_filename("quickstart", "en", "pdf"), readme)
```

Run: `python -m pytest -q -p no:cacheprovider docs/help/source/test_help_docs.py -k readme_names` → FAIL (README says 2.2.0).

- [ ] **Step 2: Fix README**

In `docs/help/README.md` replace both `NVC 2.2.0 - ` occurrences with `NVC 2.3.0 - `. Re-run the test → PASS.

- [ ] **Step 3: Capture screenshots on the real display**

Run (PowerShell): `$env:NVC_SHOTS_STUB_DEVICES="1"; python docs/help/source/capture_screenshots.py; Remove-Item Env:NVC_SHOTS_STUB_DEVICES`
Expected: `ok` lines for FIG-00 … FIG-09. Open every PNG and check: no user name, machine name, real device name, or personal folder path is visible. If FIG-01 (Folders) shows a non-default path, temporarily point the folders at the defaults in Settings, recapture, and restore.

- [ ] **Step 4: Build**

Run: `python docs/help/source/build_help_docs.py`
Expected: four files written under `docs/help/` with the 2.3.0 names. Open the Help PDF and spot-check: contents page numbers, FIG-08/FIG-09 present (not grey placeholders), tables not clipped.

- [ ] **Step 5: Ledgers**

`docs/CHANGELOG.md`, under `## 2026-09-25`, add:

```
### Help documentation

- Rewrote the Help manual against the current application: every Settings tab,
  the seven main tabs and their default visibility, Converted Files, Time
  Restrictions, Language, Updates and Logs.
- New Media Player chapter (controls, shortcut table pinned by a test, fullscreen,
  playlist, unsupported-format fallback) and a rewritten Multi-Source Recorder
  chapter built around the Video Settings dialog and presets.
- PC Report chapter lists every section in report order and describes the
  always-on redaction and administrator-only fields.
- Quick Start gains "Record From a Webcam" and "Review a Recording".
- Two new figures (Media Player, Video Settings); all figures recaptured with
  stand-in device names. Regenerated the 2.3.0 PDF and DOCX manuals.
```

`docs/BACKLOG.md`: add a "Help documentation follow-ups" list — Dutch and Chinese manuals (pipeline supports it: add tags to `SUPPORTED_DOCUMENT_TAGS`/`_LOCALE_PACKAGES`, translate `locales/en`); `open_help_document` should pass the active locale to `resolve_help_document`; a Developer Guide. Under "Recorder follow-ups" add: Video Settings "Output quality" combo is not wired to the encoder; "Timer settings" group (Time format, Decimals, Use maximum recording time) is not read anywhere — wire or remove, then document.

- [ ] **Step 6: Full verification**

```
python -m pytest -q -p no:cacheprovider
python -m ruff check docs/help/source docs/help/source/locales tests/test_media_player_widget.py
git diff --check
rg -i -c -f %TEMP%\nvc_leak_patterns.txt docs/help/source docs/help/screenshots/SHOTLIST.md tests/
```

Expected: suite exit 0; ruff clean; diff --check exit 0; rg exit 1 (no matches).

- [ ] **Step 7: Commit and merge**

```bash
git add docs/help docs/CHANGELOG.md docs/BACKLOG.md
git commit -m "docs(help): regenerate 2.3.0 manuals with recaptured figures; README version; ledgers"
git checkout master
git merge --no-ff help-docs-refresh -m "Merge help-docs-refresh: manuals rewritten for the current app, Media Player and recorder chapters, new figures"
python -m pytest -q -p no:cacheprovider
git branch -d help-docs-refresh
```

---

## Self-review

- Spec coverage: chapter plan rows 1–11 → Task 2; 12–14 → Task 3; 15 → Task 4; 16 → Task 5; 17–21 → Task 6; glossary → Task 6; quickstart → Task 7; figures/SHOTLIST/capture → Task 1; README/build/ship/ledgers/BACKLOG items → Task 8; tests named in the spec → Tasks 1, 2, 5, 7, 8 (the spec's `test_help_covers_every_tool_tab`, `test_help_has_a_chapter_per_tool_tab`, `test_quickstart_has_record_and_review_chapters`, `test_readme_names_the_current_doc_version`, `test_help_documents_every_shortcut` all appear by name).
- Ordering: Task 1 and Task 7 touch files disjoint from Tasks 2–6 and may run in parallel with Task 2. Tasks 2→3→4→5→6 are serial (same file). Task 8 last.
- Names used consistently: `_chapter`, `_chapter_text`, `TOOL_TAB_LABELS` (Task 2, reused in 3–7); `STUB_CAMERAS`, `STUB_MICROPHONES`, `_stub_device_discovery`, `_make_test_clip` (Task 1 only); figure ids FIG-08/FIG-09 (Tasks 1, 4, 5).
