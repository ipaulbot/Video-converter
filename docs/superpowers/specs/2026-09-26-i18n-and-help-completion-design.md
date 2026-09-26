# Translations, localised manuals and figure recapture (2026-09-26, 16:14 pass)

Request: drop the "Playlist - Panel N" title above the Media Player playlist,
head its first column "File Name" like the Video Converter, finish the Dutch
and Chinese translations, finish the Help, and list what is still missing
before the exe build and the portfolio site.

## Decisions

1. **Playlist strip.** The title row is removed; the panel name survives as
   the list's tooltip so a user with several panels can still tell which list
   they are looking at. Header: File Name | Panel | Offset.

2. **UI catalogues.** nl and zh-CN are translated to 462/462. The `.ts`
   writer used `minidom.toprettyxml`, which folds the blank line inside a
   `"\n\n"` source string; those eight strings never matched at runtime.
   Switched to `ElementTree.indent`, with a round-trip test.

3. **Manuals.** Each locale is a package under `docs/help/source/locales/`
   with the same keys as `en` (parity is validated at build time). The
   builder's own words -- Contents, Note, Figure N., the missing-figure text,
   document titles -- come from `doc_strings.py` so they are not hard-coded
   English. Output **file names keep the English title** because
   `utils/help_resolution.find_generated_manual` looks manuals up by title
   and falls back to `en`; the cover and headings are translated.

4. **CJK rendering.** ReportLab's Helvetica has no CJK glyphs.
   `manual_fonts.py` embeds Microsoft YaHei from the Windows font folder
   (candidate chain, then STSong-Light CID). The wrapper tokenises spaceless
   text per character and keeps closing punctuation off the line start.
   Code blocks and glossary keys stay English in every locale.

5. **Figures without a display.** Rule: never read the operator's screen,
   never open their devices. The capture script parks every window at
   (-7000, -7000) and only calls `widget.grab()`. Recorder widgets are built
   with `auto_preview=False` for the run and the FIG-07 tiles are fed ffmpeg
   test patterns through `_render_pending_preview_frames()`. The Media
   Player's native surface is black to `grab()`, so the frame ffmpeg
   extracts at the paused position is composited into the tile. The test
   clip lives under the Public Videos folder for the run because the Inspect
   panel prints the clip's full path; `%TEMP%` would print the user name.

6. **Stale text fixed while there.** Settings -- Folders -- Log Folder has
   been honoured since 2026-09-25; the manuals said it had no effect.

## Not done (deliberately)

- The exe build and the website: after the user's review. The pre-flight
  list is in `docs/BACKLOG.md`, "Release readiness".
- Bundled CJK font, `pypdf`, native-speaker read of nl / zh-CN.
