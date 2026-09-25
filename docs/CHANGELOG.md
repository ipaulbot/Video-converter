# NVC Change Log

Use this file to track user-visible fixes, improvements, and feature work.

## 2026-05-22

- Added browser-style output naming so converted files are not overwritten.
- Fixed HEVC CPU/GPU codec selection.
- Added output validation before reporting conversion success.
- Added unique GIF palette temp files.
- Hardened retention-day settings.
- Added PC report redaction for JSON and HTML exports.
- Added detailed HTML help documentation.
- Started stabilization work for tab layout, folder drop conversion, and preview theming.
- Added PC Report as a first-class tab.
- Added recursive folder drag/drop for supported media files.
- Added a Lossless Editor tab for FFmpeg stream-copy trim, remux, audio extract/remove, and merge.
- Added a first Multi-Source Recorder tab for up to four FFmpeg recording sources.
- Expanded PC report parity toward SIW with environment variables, codecs/MMC/sensors visibility, Noldus drivers, imaging devices, richer video, drivers, services, and process detail.

## 2026-09-03

- Put the project under version control, with a dependency manifest, ruff and
  pytest configuration, and a `conftest.py` so `python -m pytest` works with no
  environment setup.
- Fixed GPU encoder detection running a synchronous, un-timed `ffmpeg` probe at
  import time, which could hang startup before any window appeared. It is now
  cached and lazy.
- Added timeouts to every FFmpeg and FFprobe call, so a wedged binary can no
  longer freeze the window indefinitely.
- Replaced 125 silent exception handlers with logged ones. Set
  `NVC_LOG_LEVEL=DEBUG` to see the tracebacks behind an otherwise silent
  failure.
- Fixed scheduled deletions, unwritable configured folders, and a failed
  pending-deletion write all failing without any message.
- Fixed asset paths that resolved only because Windows filenames are
  case-insensitive.
- Replaced the hand-written help document with generated Help and Quick Start
  manuals, in PDF and DOCX, built from a single content source with
  screenshots. The Help menu opens the newest generated manual.
- Added a theme layer (`ui/theme.py`). The app's three visual states -- idle
  (teal), active (green) and locked (grayscale) -- are now named skins with one
  definition each, instead of the same colours repeated across four separate
  if/elif chains. Appearance is unchanged.
- Removed the superseded hand-written help document; the generated manuals are
  now the only help.
- Split the sidebar video preview, the easter-egg game and the conversion-queue
  bookkeeping out of the main window into their own modules, and added tests
  for the conversion worker. No user-visible change intended.
- Fixed closing NVC hanging after a conversion with a retention period set: the
  deletion timer was blocking interpreter exit for up to 30 days.
- Fixed two files with the same name in different folders writing each other's
  conversion log.
- The interface is now translatable: 367 user-facing strings are extracted into
  Qt catalogues under `translations/`. English is unchanged. Dutch and
  Simplified Chinese exist as draft catalogues awaiting translation, hidden
  unless `NVC_I18N_PREVIEW=1`. See `translations/README.md`.
- Moved the remaining stylesheet colours onto theme tokens. Changing the brand
  accent is now a single edit in `ui/theme.py`.
- Fixed the Settings dialog not showing its green active state while a
  conversion ran with monitoring stopped.
- Fixed a corrupted scheduled-deletion list silently stopping all retention.
  One malformed record used to block every pending deletion, permanently.
- "Check for Updates" no longer reports a fake update and no longer offers to
  open a placeholder download page. It now says update checking is not
  configured for this build. See `utils/update_checker.py` to enable it.
- Dutch and Simplified Chinese are now selectable from the Language menu,
  covering the core interface. Anything not yet translated shows English.
- The Info window now reports the real version and build date; it had been
  showing 2.1.160 / July 2025.
- Fixed the test suite reading and writing the real user's settings, which
  could change which tool tabs the app showed.
- Fixed NVC being able to abort on exit shortly after using the recorder. The
  terminate and kill escalations that follow Stop Recording were scheduled on
  timers owned by nothing, so they still fired 1.5 and 3 seconds later against
  a destroyed window; the same applied to the preview retry timers. They are
  owned by the recorder now and cancelled with it.
- Fixed the ffmpeg camera-mode probe that Video Settings starts when a camera
  is picked outliving both the dialog and the recorder. It is stopped on
  shutdown, and its result is discarded harmlessly if the dialog has since
  been closed.
- Fixed one unreadable row in the saved state discarding every high score.
- Added tests for the paths, resources, subprocess, system-state, log-bus and
  GPU-encoder helpers, which had none.
- Fixed the same class of unowned timer in the main window and the easter-egg
  game: the Converted-tab wiggle, the game launch three seconds after the
  intro, and the game's level transitions up to ten seconds out could all fire
  against a closed window. A source guard now fails the suite if a
  `QTimer.singleShot` is reintroduced anywhere.
- Dutch and Simplified Chinese now ship as they stand, without waiting for a
  native-speaker review. Both cover the core interface (146 of 365 strings);
  Qt shows the English source for the rest. A review pass is still worth
  doing, but it is no longer treated as a release blocker — an unreviewed
  Dutch or Chinese interface is better than an entirely English one.

## 2026-09-24

### PC Report

- Rebuilt on a section registry: 40 sections in NVC / Software / Hardware /
  Network groups, matching SIW's layout, each with a grouped Contents entry and
  a Top link. Sections collect in parallel; a failure in one section marks it
  partial instead of losing the report.
- Depth parity with SIW: operating system (activation, boot, policies), update
  history, licences, security (Defender, firewall, VBS, TPM, BitLocker),
  processes with owners, services, drivers by class, autorun with
  StartupApproved state, codecs across DirectShow/VCM/ACM/MFT, motherboard,
  BIOS characteristics, CPU caches and features, memory modules, sensors,
  devices, PCI, slots, adapters with advanced properties, video with corrected
  memory, monitors, sound endpoints, storage with partitions and reliability
  counters, logical disks, ports, USB, printers, VM detection, cameras (Frame
  Server, consent store, GenICam), network information, shares, connections.
- New Noldus Summary first: attention items (pending reboot, UAC, low disk,
  problem devices, USB selective suspend, Frame Server, camera consent,
  hasplms, jumbo frames), specs, Noldus software/drivers/filters/environment,
  cameras, dongles, GigE settings.
- Redaction extended: normalised label matching, IPs masked to two octets, MACs
  to the vendor prefix, hardware instance IDs, account names, SSIDs, DNS
  suffixes, proxy and UNC host names, personal device names; Name/Value rows.
- Admin-only fields show "Requires administrator" instead of failing; no UAC
  prompt.
- Report Health block: partial/empty sections, notes, elapsed time per section.
- The PC Report tab's progress text now names the section being collected and
  the running count.

## 2026-09-25

### Multi-Source Recorder

- Added per-source DirectShow audio selection, mute and volume control, including
  AAC audio for stream-copy video and automatic video-only retry when a selected
  microphone is unavailable. Without a microphone, file and RTSP (H.264 mode)
  sources keep their own sound track; Mute or Volume 0 records silent video.
- Recorder presets now load from and save to the MediaRecorder Presets folder,
  with Load, Set, Save as and Delete actions plus unsaved-change indication.
- Removed the non-functional Picture-in-picture choice, retained Separate videos
  and Combined grid, and made the recorder tab visible by default for fresh
  settings.
- DirectShow device names with accented or curly-quote characters are now listed
  correctly instead of as garbled text.

### Media Player

- Added volume and mute for all panels, fullscreen (F / Esc / double-click, auto-hiding
  transport bar), and keyboard shortcuts: Space, Home, Left/Right frame step,
  Shift+Left/Right 5 s, Up/Down volume, M, F, N/P.
- Frame-accurate stepping using the clip's real frame rate (ffprobe), with a
  H:MM:SS.mmm and frame N / total readout.
- Per-panel playlist (add files or a folder, reorder, drag from Explorer); auto-advance
  only in single-panel mode.
- Converted Files gains "Play in Media Player" (context menu and Play button); the tab is
  shown for the session even if hidden in settings.
- Files Windows cannot decode show an inline "Convert to MP4 (H.264) and play" offer
  instead of a blank tile.
- Player settings (last folder, panel count, volume, mute) persist between sessions.
