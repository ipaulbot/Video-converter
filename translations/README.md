# Translations

`.ts` files are the editable source; `.qm` files are what NVC loads at
runtime. Both are generated — see below — but the `.ts` files also hold the
translated text, so **they are committed and must not be deleted**.

## Current state

| Locale | File | Status |
|---|---|---|
| English | `nvc_en.ts` | Source language. Needs no translation and no `.qm`. |
| Dutch | `nvc_nl.ts` | **Draft.** 2 of 200 strings translated, as a worked example. |
| Simplified Chinese | `nvc_zh_CN.ts` | **Draft.** Not started. |

Draft locales are hidden from the Language menu unless you set
`NVC_I18N_PREVIEW=1`, so unreviewed strings cannot reach someone who did not
ask to see them. A locale becomes selectable by changing its `review_status`
to `"production"` in `utils/localization.py`, which is a deliberate decision
for a human to make after reviewing the file — not something the build does.

## Translating

1. Open the `.ts` file in **Qt Linguist** (`pip install qt5-tools`, then
   `qt5_applications/Qt/bin/linguist.exe`), or edit the XML directly.
2. Fill in each `<translation>` element. Untranslated entries are marked
   `type="unfinished"`; Qt falls back to the English source for those, so a
   partial translation is safe to ship — it just shows English where it has
   nothing.
3. Rebuild:
   ```bash
   python scripts/build_translations.py
   ```
   That re-extracts the strings, **merges** them into the existing `.ts`
   (never overwriting your work), and compiles a `.qm`.

### Placeholders

Interpolated values appear as `%(name)s`:

```
Converted %(count)s of %(total)s files
```

Keep every placeholder, spelled exactly. You may **reorder** them freely —
that is the whole reason they are named rather than positional, since word
order differs between languages.

### What not to translate

Leave alone: FFmpeg encoder names (`libx264`, `h264_nvenc`), file extensions,
`video=Camera Name` DirectShow syntax, URL schemes, and environment variable
names like `NVC_LOG_LEVEL`. These are things a user types or reads back from
the app, not prose.

## For developers

Every user-facing string goes through the module's own `_tr()`:

```python
label.setText(_tr("No Preview"))
```

The argument must be a **plain literal** — never an f-string, a variable, or a
concatenation. `tests/test_i18n.py` scans the AST and fails with the file and
line if a bare literal reaches a Qt text setter, so coverage cannot decay
quietly. `python scripts/build_translations.py --check` reports the same
problems without writing anything.

Extraction walks the AST rather than using `pylupdate5`, because `pylupdate5`
matches call names textually and so cannot see a string passed through a
wrapper like `_tr()`. Compiling `.qm` needs `lrelease`, which ships with
`qt5-tools` rather than PyQt5.

A string that disappears from the code is marked `vanished` in the `.ts`
rather than deleted, so rewording an English string does not throw away its
existing translations.

## Adding a language

1. Add a `LocaleSpec` to `utils/localization.py` with `review_status="draft"`
   and a `document_tag` matching a manual in `docs/help`.
2. Run `python scripts/build_translations.py` to create the `.ts`.
3. Translate, review, then set `review_status="production"`.
