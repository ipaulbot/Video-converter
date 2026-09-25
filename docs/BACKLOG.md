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

- Converted Files has a Clear button (`ui/converted_files_widget.py:135`) that
  is hidden at construction and never shown, so the table cannot be cleared
  from the UI. Show it alongside Play, or remove it. The manual does not list
  it.

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
- The elevated (administrator) live run has not been done yet: start NVC as
  administrator once and confirm TPM, BitLocker, SMART reliability counters and
  the SMB server rows fill in.

Out of scope in the current design, kept for later:

- UAC-elevated collection (relaunch elevated, or an elevated helper) so that
  TPM, BitLocker, SMART and SMB server fields fill in without running NVC as
  administrator.
- Quick/Full profiles (skip the slow DirectShow, dxdiag and process-owner
  sections for a 15-second report).
- PDF export of the report.
- Report comparison (diff two saved reports).
- PC Report dialog redesign (section picker per group, live section list).

## Recorder follow-ups

- Timer-dialog fields: time format, decimals, maximum time. Found while
  documenting (2026-09-25): the Video Settings "Timer settings" group (Time
  format, Decimals, Use maximum recording time) is not read anywhere — wire it
  or remove it, then document it.
- Video Settings "Output quality" combo is not wired to the encoder; every
  recording uses the same encoder settings regardless of the choice. Wire it or
  remove it, then document it.
- DirectShow (USB) cameras are always re-encoded, even in copy mode
  (`conversion/recording_commands.py`); the manual states this. Decide whether
  copy mode should refuse USB sources or the label should say so.
- Screen capture through FFmpeg gdigrab.
- Picture-in-picture recording.
- Source type and address columns in the main grid.
- Splitting the 2,900-line recorder widget into modules.
- Wiring `build_multi_source_record_command` into the live recorder.
- Live verification on Axis, Basler and Daheng hardware using the lab checklist.
- Preview-pipeline changes.
- Combined grid mixes only one microphone; per-source embedded audio is not mixed.

## Media player follow-ups

- FFmpeg-decoded playback (play anything without converting).
- Snapshot current frame to PNG.
- Subtitle tracks and audio track selection.
- Per-panel independent transport (today every panel shares one timeline).
- Persist playlists between sessions.
- Turning the Media Player tab on by default.
- Playlist dock buttons (Add file / Add folder / Remove / Clear) overflow the dock
  width and are clipped at the right edge, visible in the manual's FIG-08.

## Help documentation follow-ups

- Dutch and Simplified Chinese manuals. The pipeline supports it: add the tags
  to `SUPPORTED_DOCUMENT_TAGS` / `_LOCALE_PACKAGES` in
  `docs/help/source/document_registry.py` and translate `locales/en` into
  `locales/nl` and `locales/zh_CN`. The PDF builder uses Helvetica, which has
  no CJK glyphs; a CJK-capable font must be registered before a zh-CN PDF can
  render.
- `ui/main_window.py` `open_help_document` does not pass the active locale to
  `resolve_help_document`, so a localized manual would never be opened even if
  it existed.
- A Developer Guide (architecture, module map, test layout, how the manuals are
  built).
- Settings → Folders "Log Folder" is saved (`ui/settings_dialog.py`) but never
  read: `ui/main_window.py` hard-codes `get_data_dir("logs")`. The manual says
  logs are always under `%APPDATA%\NVC\logs`. Wire the setting or remove it.
- `pyproject.toml` says version 2.2.0 while `utils/version.py` says 2.3.0; pick
  one source of truth.

## Done

- Help documentation is now generated from `docs/help/source/` rather than
  hand-maintained. Edit the content bundles and run
  `python docs/help/source/build_help_docs.py`. See `docs/help/README.md`.

## Feature Ideas

- Lossless split, audio replace, chapter/segment export, snapshot, and timeline UI.
- Multi-source live preview tiles, device discovery, source health indicators, synchronized start/stop~~, and recording presets~~ (presets done 2026-09-25).
