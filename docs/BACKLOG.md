# NVC Backlog

Use this file as the shared parking lot for bugs, refactors, and new features.

## Current Build Order

1. Stabilize current app behavior.
2. ~~Compare NVC PC Report against SIW and close parity gaps.~~ Done 2026-09-24; see "PC report follow-ups".
3. Add a lossless FFmpeg editing tab.
4. ~~Add a multi-source video recording tab.~~ Done 2026-09-25; see "Recorder follow-ups".

## Bugs / Fixes

- Keep testing preview play overlay theme changes on real drag/drop conversions.
- Validate the PC report on lab PCs (GigE cameras, dongles, domain-joined,
  elevated) — the live smoke test (`NVC_PC_REPORT_LIVE=1 python -m pytest
  tests/pc_report/test_live_report.py -s`) has only been run on one developer
  laptop, unelevated.
- Repository-wide `ruff check .` has ~200 pre-existing findings in
  `ui/main_window.py`, `ui/extras/snood_widget.py`, `utils/system_state.py`
  and a few others (import order, `datetime.UTC`, `capture_output`). The
  `pc_report` package and its tests are clean; fix the rest in a dedicated
  lint pass.

- ~~Converted Files has a Clear button that is hidden at construction and never
  shown.~~ Fixed 2026-09-25: shown next to Play whenever the table has rows.

## PC report follow-ups

Remaining gaps against the SIW export, found by a section-by-section
comparison of the live report (2026-09-24):

- Operating System: Edition ID, Key Type (Volume:GVLK/OEM/Retail), Genuine
  flag, KernelBase version, Test Mode, Windows Sandbox, Device Guard summary.
- Security: local audit policy (`auditpol /get /category:*`, administrator
  only) and Windows Update autoupdate settings.
- CPU: code name, TDP, bus speed, hybrid P/E-core layout, per-core current
  clocks. SIW gets these from its own CPUID database; WMI does not expose
  them. Would need a small CPUID reader via ctypes.
- Memory: SPD detail (JEDEC/XMP profiles, timings, manufacturing date) needs
  SMBus access and is out of reach for a built-in-sources report.
- Sensors: min/max over a sampling window; ACPI thermal zones only appear
  elevated on this hardware. Storage power-on hours and power-cycle counts
  (SMART) already appear elevated.
- Network Information: Winsock catalogue (`netsh winsock show catalog`), MTU
  and operational status per interface.
- Regional Settings: the installed code-page list (SIW shows ~450 rows) is
  omitted deliberately.
- Performance: Codecs (DirectShow enumeration, ~85 s), Processes (one
  `GetOwner` call per process, ~50 s) and Logical Disks (Get-Volume /
  Get-Partition, ~45 s) dominate wall time. Options: cache DirectShow results
  per session, use `Get-Process -IncludeUserName` when elevated, and merge the
  volume/partition scripts.
- Windows perf-counter library was partially broken on the developer laptop
  (Memory, PhysicalDisk, Network Interface sets missing); the report notes this
  and falls back to GlobalMemoryStatusEx / WMI. Consider a `lodctr /R` hint in
  the Noldus Summary.

Deferred from the final code review (all Minor):

- Windows Update history: read `IUpdateHistoryEntry2.Categories` so security /
  driver / definition updates can be told apart without parsing titles.
- Query scripts use `-ErrorAction SilentlyContinue` widely; a missing provider
  can still look like a genuinely empty machine. Move to `-ErrorAction Stop` at
  query boundaries with narrow per-item catches (stderr is now kept as a note,
  which covers the common cases).
- `pc_report/noldus_terms.py` still carries the legacy filesystem scanners
  (`scan_codec_files`, `scan_nvc_filter_files`, …) that nothing in production
  calls; remove with their tests or wire into an explicit fallback.
- No wall-clock deadline for a whole run (only per-query timeouts) and no job
  object around `powershell.exe`/`dxdiag.exe`, so a timed-out child can leave
  grandchildren behind. `dxdiag_xml` should write into a private temp directory.
- `redact_text` (fixture recorder only) matches the English `Proxy Server(s)`
  label; capture on a localised machine would need the host-based rule.
- The elevated (administrator) live run has not been done yet: use the PC
  Report tab's "Run as administrator" link (added 2026-09-25) and confirm TPM,
  BitLocker, SMART reliability counters and the SMB server rows fill in.

Out of scope in the current design, kept for later:

- ~~UAC-elevated collection (relaunch elevated).~~ The tab now offers a
  relaunch link; an elevated *helper* that fills the admin-only fields without
  restarting NVC is still open.
- Quick/Full profiles (skip the slow DirectShow, dxdiag and process-owner
  sections for a 15-second report).
- PDF export of the report.
- Report comparison (diff two saved reports).
- PC Report dialog redesign (section picker per group, live section list).

## Recorder follow-ups

- ~~Timer-dialog fields: time format, decimals, maximum time not read
  anywhere.~~ Fixed 2026-09-25: Time format / Decimals removed; "Use maximum
  recording time" is bound to the tab's Timer field. Document it.
- ~~Video Settings "Output quality" combo is not wired to the encoder.~~ Fixed
  2026-09-25: drives the x264 preset/CRF and is saved with presets. Document it.
- ~~DirectShow (USB) cameras are always re-encoded, even in copy mode; decide
  whether the label should say so.~~ Fixed 2026-09-25: a note under Output
  settings appears when "copy" is selected with a USB source enabled.
- ~~Screen capture through FFmpeg gdigrab.~~ Done 2026-09-25 (`screen=desktop`
  / `screen=title=…` source type); 2026-09-26 added `screen=monitor=N` through
  the Desktop Duplication API with a GDI fallback, `screen=region=X,Y,WxH`
  with a drag-to-select overlay, a live window list, all behind the camera
  settings gear of one "Screen capture" device entry, and NVENC/QSV/AMF
  encoding for screen rows (probed at scan time, libx264 rung on failure).
  Follow-ups: system audio for a screen source (WASAPI loopback has no
  DirectShow input; the open-source `virtual-audio-capturer` filter would
  do), hardware encoding for camera rows and composites (only screen rows use
  it today; the probe is a 256x256 clip so large frames can still be refused
  — QSV refuses a 5120-wide desktop — hence the software rung), a region
  picker that snaps to window edges, and a live thumbnail per window in the
  picker. The monitor numbering follows DXGI output order, which is normally
  but not always the Windows display order. A picked region is not
  re-validated when the monitor layout changes; gdigrab then fails with
  "extends outside window area" and the row needs re-picking.
- ~~Command-line control for The Observer XT (MRCmd-style `/E /R /S /X /C=
  /B=`).~~ Done 2026-09-26 on `NVC.exe` itself over a `QLocalServer` pipe.
  Follow-ups: `/F=<folder>` for the output folder and `/T=<seconds>` for the
  timer (both are one step each in `run_command_request`); a status query
  (`/Q` printing recording / idle / file being written) so Observer's wait
  time can be replaced by polling; a `NVCCmd.exe` stub for sites that must
  not have a second `NVC.exe` in the path; a `--no-gui` start for `/R` so the
  recorder can run headless; and, if Noldus grants SDK access, an N-Linx
  agent (RabbitMQ + Thrift) so Observer can also import the finished videos
  the way it does from MediaRecorder.
- ~~Picture-in-picture recording.~~ Done 2026-09-25. Follow-ups: choose which
  source is the main frame and the inset corner/size; the geometry is the
  fixed set in `_pip_preview_rects`.
- Combined grid / PiP canvas is fixed at 1280x720 (grid tiles 640x360); a
  "composite resolution" setting would let 4K sources keep more detail.
- Source type and address columns in the main grid.
- Splitting the 2,900-line recorder widget into modules.
- Wiring `build_multi_source_record_command` into the live recorder.
- Live verification on Axis, Basler and Daheng hardware using the lab checklist.
- Preview-pipeline changes.
- Combined grid mixes only one microphone; per-source embedded audio is not mixed.
- Device listing still takes ~6 s per pass on a machine with ten DirectShow
  devices (ffmpeg enumerates every device's formats). A cheaper first pass
  (names only, via the Windows device enumeration APIs) would make the Video
  Settings dialog feel instant; ffmpeg would then only be asked for modes.
- The 45 s freshness window for device scans is a constant
  (`DEVICE_SCAN_TTL_S`); consider invalidating on WM_DEVICECHANGE instead so a
  camera plugged in mid-session shows up without a manual rescan.

## Media player follow-ups

- FFmpeg-decoded playback (play anything without converting).
- Snapshot current frame to PNG.
- Subtitle tracks and audio track selection.
- Per-panel independent transport (today every panel shares one timeline).
- Persist playlists between sessions.
- Turning the Media Player tab on by default.
- ~~Playlist dock buttons overflow the dock width and are clipped.~~ Fixed
  2026-09-25: the dock uses four 24 px glyph buttons.

## Help documentation follow-ups

- Dutch and Simplified Chinese manuals. The pipeline supports it: add the tags
  to `SUPPORTED_DOCUMENT_TAGS` / `_LOCALE_PACKAGES` in
  `docs/help/source/document_registry.py` and translate `locales/en` into
  `locales/nl` and `locales/zh_CN`. The PDF builder uses Helvetica, which has
  no CJK glyphs; a CJK-capable font must be registered before a zh-CN PDF can
  render.
- ~~`open_help_document` does not pass the active locale to
  `resolve_help_document`.~~ Fixed 2026-09-25.
- A Developer Guide (architecture, module map, test layout, how the manuals are
  built).
- ~~Settings → Folders "Log Folder" is saved but never read.~~ Fixed
  2026-09-25 (`utils.paths.log_dir`); the manual still says logs are always
  under `%APPDATA%\NVC\logs` — update it with the next manual regeneration.
- ~~`pyproject.toml` says 2.2.0 while `utils/version.py` says 2.3.0.~~ Fixed
  2026-09-25; `tests/test_version.py` keeps them equal.

## UI follow-ups

Deferred from UI iteration 2 (2026-09-25) until the feature set settles:

- Regenerate the Help manual and its screenshots: window modes, leaf cards, the
  new PC Report / Media Player / Lossless Editor / Recorder controls, Output
  quality, Timer binding, Log Folder.
- Translate the new UI strings (Window menu, tooltips, copy-mode note, PC Report
  copy) in `translations/`.
- Compact mode always resizes to 1024x640 when chosen from the burger menu;
  consider remembering a user-resized compact geometry (the title-bar Restore
  button already keeps whatever size the window had).
- Full window mode still leaves the recorder and PC Report with empty space
  below the groups on very large screens; a Full-only two-column arrangement
  (e.g. recording log beside the previews) would use it.
- Media Player and Lossless Editor stay separate tabs; consider linking them
  ("Set trim start/end from the player position", "Open in editor") rather
  than merging the windows, which would crowd Compact mode.
- The Recording properties grid still hides source type/address behind the
  per-row Video Settings dialog; a Full-mode variant could show them inline.
- Glyph pass (2026-09-25) covered the player dock, editor browse, PC Report
  links, recorder links, Video Settings camera/refresh and Settings folder
  buttons. Still text-only: the recorder preset row (Load / Set / Save as /
  Delete), the Lossless Editor action buttons, and the converter's
  Add/Clear/Start row. Keep text on Start/Stop/Convert; glyph-plus-text on
  the rest.
- `ui/settings_dialog.py` carries six pre-existing unused imports (ruff F401 /
  I001); clean up in a dedicated commit.

## Done

- Help documentation is now generated from `docs/help/source/` rather than
  hand-maintained. Edit the content bundles and run
  `python docs/help/source/build_help_docs.py`. See `docs/help/README.md`.

## Feature Ideas

- Lossless split, audio replace, chapter/segment export, snapshot, and timeline UI.
- Multi-source live preview tiles, device discovery, source health indicators, synchronized start/stop~~, and recording presets~~ (presets done 2026-09-25).
