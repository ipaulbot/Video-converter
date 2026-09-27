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

- ~~A deselected webcam stays on (light lit) and the desktop capture keeps
  showing after every row is set to "No source selected...".~~ Fixed
  2026-09-26 (18:16): previews are `kill()`ed (terminate is a no-op for a
  windowless ffmpeg), a row that no longer previews anything stops its old
  process, and "USB / DirectShow" no longer pre-fills the first camera.
  Follow-ups: `release_preview_processes_for_recording` still calls
  `terminate()` then waits up to 750 ms per camera before `kill()`; on
  Windows that wait always expires, so Start Recording could be ~0.75 s
  faster per USB row by killing directly. Document in Help that the tile
  says "Configure the source" until a camera is chosen.
- ~~Row 1's Use box could not be unticked, so a saved desktop capture in row
  1 always came back.~~ Fixed 2026-09-27: every row is ordinary; Start is
  disabled with "Enable at least one source" when no row is enabled.
- The recorder's status label ("Enable at least one source", "Not
  recording") is on the widget's hidden internal status row; the footer
  status line the user actually sees does not carry it yet.
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
- Persist playlists between sessions (one shared list since 2026-09-27, so a
  single `media_player.playlist` key with `items` and `offsets` suffices).
- ~~The playlist strip showed only the selected panel's clips, and with it
  open compact mode had to scroll.~~ Fixed 2026-09-27: one list shared by
  every panel (Panel column says where each clip shows); strip capped per
  window mode and compact panels at 136 px.
- Turning the Media Player tab on by default.
- ~~Playlist dock buttons overflow the dock width and are clipped.~~ Fixed
  2026-09-25: the dock uses four 24 px glyph buttons.

## Help documentation follow-ups

- ~~Dutch and Simplified Chinese manuals.~~ Done 2026-09-26 (`locales/nl`,
  `locales/zh_CN`, `doc_strings.py`, `manual_fonts.py`). Follow-ups:
  - The zh-CN PDF embeds Microsoft YaHei from the Windows font folder. A
    build machine without it falls back to the STSong-Light CID font (thin,
    not embedded). Drop a licensed Noto Sans SC / Source Han Sans TTF into
    `docs/help/source/fonts/` so the build is reproducible anywhere.
  - `requirements-help.txt` pins `pypdf`; the tests import `PyPDF2` because
    only that is installed here. Install `pypdf` and switch the import.
  - The manuals were translated in one pass; a native-speaker read of the nl
    and zh-CN text before the exe ships.
  - A Language chapter screenshot (Settings with the Language combo) is not
    in the figure catalogue.
- ~~`open_help_document` does not pass the active locale to
  `resolve_help_document`.~~ Fixed 2026-09-25.
- A Developer Guide (architecture, module map, test layout, how the manuals are
  built).
- ~~Settings → Folders "Log Folder" is saved but never read.~~ Fixed
  2026-09-25 (`utils.paths.log_dir`); manual text updated 2026-09-26.
- ~~`pyproject.toml` says 2.2.0 while `utils/version.py` says 2.3.0.~~ Fixed
  2026-09-25; `tests/test_version.py` keeps them equal.

## UI follow-ups

Deferred from UI iteration 2 (2026-09-25) until the feature set settles:

- ~~Regenerate the Help manual and its screenshots: window modes, leaf cards, the
  new PC Report / Media Player / Lossless Editor / Recorder controls, Output
  quality, Timer binding, Log Folder.~~ Done 2026-09-26.
- ~~Translate the new UI strings (Window menu, tooltips, copy-mode note, PC Report
  copy) in `translations/`.~~ Done 2026-09-26 (nl and zh-CN at 462/462).
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

Tab merge follow-ups (2026-09-26):

- Remember the Video Converter splitter position (files table vs log) between
  sessions; today it starts at the 2:3 default every launch.
- Inspect panel: remember its splitter width per session (open/closed is
  remembered since the second pass on 2026-09-26; the width still starts at
  28 % of the stage).
- ~~Sidebar preview: the left-hand box mostly duplicates what is on screen;
  reclaim the sidebar or drop it.~~ Resolved 2026-09-27 (option A): the
  sidebar is a context panel (current tab's glyph, title, description over
  the preview leaf); the settings text moved into the Video Converter tab
  as a table; the leaf is blank when idle and pulses a heart for PC Report.
  Still open: the Lossless Editor leaves the leaf blank (its input clip
  could show there like the player's selected clip does).
- Sidebar context header: the tab-bar right-click "Hide" menu closes
  BallBuster only if the Video Converter is at index 0 (`on_tab_changed`
  still hard-codes index 0 for the game check); make it key-based.
- Inspect from a playlist row (right-click) without loading the clip into the
  panel first.
- The Inspect panel re-runs ffprobe when the selected panel changes; cache the
  last few results per path so switching between four loaded panels is instant.
- Media Player replaces the standalone Video Inspection Tool; if anyone still
  wants a full-width inspector, a "Pop out" on the Inspect panel would be
  cheaper than bringing the tab back.
- ~~Translations: the new strings (Video Converter, Inspect, Inspect in Media
  Player, Inspect - %(panel)s, the Inspect tooltip) need nl / zh-CN entries.~~
  Done 2026-09-26.

UI polish batch follow-ups (2026-09-26, later):

- ~~Re-capture the Help figures in a dedicated session: FIG-00 / FIG-03,
  FIG-08 and FIG-09.~~ Done 2026-09-26; `capture_screenshots.py` now runs
  parked off-screen with `grab()` only, previews off and synthetic frames,
  so it can run while the operator's own NVC and desktop are in use.
- ~~Translations for the new strings: tab header descriptions, "Clip",
  "Offset", "Add videos to convert...", "Monitor a folder...", "Monitor this
  file's folder", "Open in" and its entries, "Choose the folder to monitor".~~
  Done 2026-09-26.
- Playlist offset: only one row can be dragged at a time (multi-row drops are
  ignored); the offset is not yet persisted with the (not yet persisted)
  playlist. When playlists persist, store `offsets` beside `items`.
- The sync-offset concept exists twice -- per recorder source in Video
  Settings and per clip in the player playlist -- with the same name and
  different units of storage (seconds both, but recorder rows are strings).
  Fine for now; a shared "Sync offset" glossary entry in Help would tie them.
- Recorder Output settings group is capped at 380 px; on Full window the
  Recording properties group takes the rest. Revisit if the folder path
  field feels cramped at compact size.
- `set_window_mode` holds repaints for the switch; Windows still animates
  the maximise / restore itself. If the OS animation reads as a flash,
  disable it via `WS_EX` / DWM attributes per window (not done).
- Planning doc `docs/planning/2026-09-26-product-naming-website-and-github.md`
  needs the owner's decisions: public name, what goes public on GitHub, and
  the purchase route (blocked on the licensing plan).
- Four test files carry a literal RTSP URL with embedded credentials as a
  fixture (pre-existing; flagged 2026-09-26). Replace with an obviously
  fake host such as `rtsp://user:pass@camera.example/stream`.

Workflow rules / player pass follow-ups (2026-09-26, 15:32):

- "Overlay of the Video Converter table" on the player after a tab switch:
  not reproducible headless (grab() paints correctly), so it is attributed
  to the native Media Foundation window painting nothing until a frame
  lands. The surface is now parked while its panel is hidden. If it still
  shows, capture it on screen and check whether it sits exactly in a tile
  (surface) or elsewhere (a layout problem) before changing anything else.
- The recorder's own `status_label` still carries "Unavailable while
  conversion is running" / "Not recording" wording; the footer no longer
  does. Consider folding the recorder line into the shared status too.
- ~~Translations for the new "Workflow" context (rule reasons, status words)
  and "ElidedLabel" (no strings yet), plus the Media Player help additions.~~
  Done 2026-09-26.
- Rule 4 allows lossless edits during a conversion. If both prove to
  compete on disk, make `lossless_edit` follow `record` in
  `blocked_reason()`; it is a one-line change with a test to flip.

## Release readiness (before the 2.3.0 exe and the portfolio site)

Collected 2026-09-26 for the review -> exe -> website sequence. The exe build
is scheduled for 2026-09-27 (owner's call, 18:16); the portfolio site started
2026-09-26 (see the last item).

- Packaging: `NVC.spec` already bundles `ffmpeg.exe` / `ffprobe.exe`,
  `translations/*.qm` and `docs/help/NVC *.pdf`; check it also picks up the
  `.docx` manuals if they should ship, `graphics/`, and that
  `utils.resources.resource_path` resolves every asset in a frozen run.
  Smoke-test the frozen exe on a clean Windows VM (no Python, no Visual C++
  redistributable assumptions).
- Installer: Inno Setup script with per-user/all-users choice, Start Menu
  entry, optional "Launch at Windows startup", and the `NVC.exe /R /S ...`
  command-line contract documented in the installer's readme.
- Code signing: an unsigned exe trips SmartScreen; budget a certificate or
  document the "More info -> Run anyway" step for the site.
- Version bump: `utils/version.py` + `pyproject.toml` (test keeps them
  equal), `DOC_VERSION` in `build_help_docs.py`, manual file names, and a
  dated release-notes section cut from `docs/CHANGELOG.md`.
- Update check: `get_update_url()` must point at the real release feed (or
  the build keeps answering "Updates Not Configured"); decide the feed
  format (GitHub Releases JSON is enough).
- Repository hygiene before anything goes public: remove the literal RTSP
  URL with credentials from the four test files that carry it
  (`test_recording_sources`, `test_recording_commands`, `test_ptz_controls`,
  `test_multi_source_recorder_widget`); scan the tree for machine names,
  user names and camera addresses; `.gitignore` already covers build output
  and the ledger -- add local settings files if any are ever written into
  the tree; add `LICENSE` and a top-level `README.md` with screenshots (the
  help figures are already clean and can be reused).
- Bundled settings: the installer must not ship a `config.json` or
  `Current Settings.json` from this machine.
- Third-party notices: ffmpeg (LGPL/GPL build?), PyQt5 (GPL/commercial),
  Microsoft YaHei is not redistributable -- the zh-CN manual is fine as a
  PDF, but the build machine needs the bundled font follow-up above.
- Dependencies: `pypdf` install (see Help follow-ups); pin `requirements*.txt`
  to the versions the exe is built with.
- Portfolio site: ~~reuse the help figures and the executive-overview style;
  each project gets a one-paragraph brief, a feature list, a screenshot strip
  and a download / GitHub link. Host on GitHub Pages (static) unless a CMS is
  wanted.~~ Skeleton built 2026-09-26 at `D:\Python Projects\portfolio-site`
  (own repo; `docs/superpowers/specs/2026-09-26-portfolio-site-design.md`).
  Remaining: owner fills the `TODO` placeholders in `content.py` (name,
  contact, current role, resume entries, extra projects), decides whether
  the employer branding visible in both products' screenshots may appear
  publicly, picks hosting (GitHub Pages `/docs`) and a domain, supplies a
  resume PDF; add download / source links once the GitHub decision in
  `docs/planning/2026-09-26-product-naming-website-and-github.md` is made;
  re-copy the screenshots after each product release.

## Done

- Help documentation is now generated from `docs/help/source/` rather than
  hand-maintained. Edit the content bundles and run
  `python docs/help/source/build_help_docs.py`. See `docs/help/README.md`.

## Feature Ideas

- Lossless split, audio replace, chapter/segment export, snapshot, and timeline UI.
- Multi-source live preview tiles, device discovery, source health indicators, synchronized start/stop~~, and recording presets~~ (presets done 2026-09-25).
