# NVC Backlog

Use this file as the shared parking lot for bugs, refactors, and new features.

## Current Build Order

1. Stabilize current app behavior.
2. Compare NVC PC Report against SIW and close parity gaps.
3. Add a lossless FFmpeg editing tab.
4. Add a multi-source video recording tab.

## Bugs / Fixes

- Keep testing preview play overlay theme changes on real drag/drop conversions.
- Continue PC report SIW parity work with deeper codec, camera, and driver validation on lab PCs.

## Done

- Help documentation is now generated from `docs/help/source/` rather than
  hand-maintained. Edit the content bundles and run
  `python docs/help/source/build_help_docs.py`. See `docs/help/README.md`.

## Feature Ideas

- Lossless split, audio replace, chapter/segment export, snapshot, and timeline UI.
- Multi-source live preview tiles, device discovery, source health indicators, synchronized start/stop, and recording presets.
- PC report parity dashboard against SIW sections and fields.
