# NVC help documentation

Generated manuals live in this folder. **They are build output — do not edit
them.** Edit the content bundles under `source/locales/` and rebuild.

## Build

```bash
pip install -r docs/help/source/requirements-help.txt
python docs/help/source/build_help_docs.py
```

That writes every manual, in every supported locale (`en`, `nl`, `zh-CN`), as
both PDF and DOCX:

| Manual | Filename |
|---|---|
| Help | `NVC 2.3.0 - Help - en.pdf` / `.docx`, `- nl.`, `- zh-CN.` |
| Quick Start Guide | `NVC 2.3.0 - Quick Start Guide - en.pdf` / `.docx`, `- nl.`, `- zh-CN.` |

The filename keeps the English title in every locale — the app's Help menu
looks the manual up by it (`utils/help_resolution.py`) and picks the file for
the saved UI language, falling back to `en`. The cover and headings carry the
translated title.

The zh-CN PDF embeds a TrueType face with Chinese glyphs: a font dropped into
`source/fonts/` first (Noto Sans SC), then the Windows system fonts (Microsoft
YaHei, SimHei, SimSun). With none of those present it falls back to ReportLab's
STSong-Light CID font, which renders in every mainstream viewer without
embedding. The build prints which one it used.

Narrower builds:

```bash
python docs/help/source/build_help_docs.py --manual quickstart --format pdf
```

## Where things live

| File | Responsibility |
|---|---|
| `source/document_registry.py` | `DOC_VERSION`, supported locales, and the **only** definition of the output filename grammar |
| `source/content_loader.py` | Loads bundles; validates structure and cross-locale parity |
| `source/document_navigation.py` | Anchors, Word bookmark names, the appended glossary chapter |
| `source/figures.py` | The figure catalog; figure numbers are derived from ids |
| `source/doc_strings.py` | The builders' own words per locale ("Contents", "Note", figure captions, cover titles) |
| `source/manual_fonts.py` | Fonts per locale; finds and registers a CJK face for zh-CN |
| `source/pdf_builder.py` | PDF via ReportLab, two-pass for real TOC page numbers |
| `source/docx_builder.py` | DOCX via python-docx, with a live Word TOC field |
| `source/build_help_docs.py` | Entry point |
| `source/capture_screenshots.py` | Drives the app to capture figures |
| `source/locales/<tag>/` | The content itself, one module per manual |
| `screenshots/SHOTLIST.md` | The human contract for each screenshot |

## Editing content

Content is nested `list[dict]` chapters. Seven keys, six block types:

```python
{
    "id": "gpu-encoding",          # stable; anchors derive from this
    "title": "GPU Encoding",       # display only; safe to reword
    "blocks": [
        {"type": "para",   "text": "..."},
        {"type": "steps",  "items": ["...", "..."]},        # auto-numbered
        {"type": "note",   "items": ["..."]},               # callout
        {"type": "figure", "fig_id": "FIG-03"},
        {"type": "code",   "lines": ["...", "..."]},
        {"type": "table",  "headers": ("A", "B"), "rows": [("a", "b")]},
    ],
}
```

Two rules worth knowing:

- **Never change a chapter `id`** once it ships. Anchors and cross-references
  are built from it, and the `title` exists precisely so you can reword the
  heading without moving links.
- **Both builders reject an unknown block type.** They are deliberately strict
  and symmetrical — a block that renders in the PDF but is silently dropped
  from the DOCX is the kind of divergence nobody notices until a reader does.

## Screenshots

```bash
python docs/help/source/capture_screenshots.py
```

Drives the real application and saves what it can reach. It forces every tool
tab visible for the run **without saving your settings** — otherwise a tab
switched off in Settings is `setTabVisible(False)`, and Qt silently refuses to
make a hidden tab current, which produces duplicate screenshots.

It also refuses to keep a byte-identical render, since that means a view switch
failed rather than that two views look alike.

A missing screenshot does not break the build: the PDF draws a grey
placeholder and the DOCX inserts an italic `[FIG-NN — screenshot not captured]`
line, so gaps show up in the output. `screenshots/SHOTLIST.md` records how each
shot is framed.

## Adding a language

1. Add the tag to `SUPPORTED_DOCUMENT_TAGS` in `document_registry.py` and to
   `_LOCALE_PACKAGES` in `content_loader.py`. Use `zh_CN` as the directory when
   the tag is `zh-CN` — hyphens are not legal in package names.
2. Copy `locales/en/` to `locales/<dir>/` and translate the strings, leaving
   every `id`, `fig_id` and block `type` untouched. Keep `code` lines and the
   glossary's term keys in English; translate `strings.py` too (same keys).
3. If the script needs glyphs Helvetica lacks, teach `manual_fonts.pdf_fonts`
   which face to register for the tag.
4. Rebuild. `validate_bundle_parity` compares chapter ids and per-block shape
   signatures against English and **fails the build** on any drift.

There is deliberately no per-string fallback to English. A bundle is
all-or-nothing, because a half-translated manual that quietly mixes languages
is worse than a build that refuses to run.

## Versioning

`DOC_VERSION` in `document_registry.py` is the single source. It feeds the
filenames, the cover page and the DOCX subtitle. It is intentionally separate
from `APP_VERSION` in `utils/version.py`: a documentation correction should not
imply a new application build.

## Tests

```bash
python -m pytest docs/help/source -q
```

These run as part of the normal suite. They cover the invariants that are hard
to spot by eye in a rendered document — every figure reference resolving, Word
bookmark names staying inside the 40-character limit, and the PDF's contents
citing the page each chapter is actually on.
