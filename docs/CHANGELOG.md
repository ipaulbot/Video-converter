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
