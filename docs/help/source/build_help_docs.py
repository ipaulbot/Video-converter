#!/usr/bin/env python3
"""Build every manual, in every locale, as PDF and DOCX.

    python docs/help/source/build_help_docs.py
    python docs/help/source/build_help_docs.py --locale en
    python docs/help/source/build_help_docs.py --manual quickstart --format pdf

Content is validated before anything is rendered, so a structural problem
fails the build immediately rather than producing half a shelf of documents.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
# The modules import each other flatly (`import figures`), so this works when
# invoked by path as well as from the repository root.
sys.path.insert(0, str(SOURCE_DIR))

import content_loader  # noqa: E402
import doc_strings  # noqa: E402
import document_registry as registry  # noqa: E402
import manual_fonts  # noqa: E402
from docx_builder import build_docx  # noqa: E402
from pdf_builder import build_pdf  # noqa: E402

OUTPUT_DIR = SOURCE_DIR.parent
SCREENSHOTS_DIR = SOURCE_DIR.parent / "screenshots"


def _write(builder, output_path: Path, **kwargs) -> Path | None:
    """Render via a temp file then move into place.

    A PDF held open by a viewer cannot be overwritten on Windows. Writing to a
    sibling temp file and replacing means a locked output costs you one
    document, not the whole build.
    """
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    builder(tmp, **kwargs)
    try:
        tmp.replace(output_path)
        return output_path
    except PermissionError:
        print(f"  ! {output_path.name} is open in another program; "
              f"left the new version as {tmp.name}")
        return None


def build(locales, manuals, formats, *, version=registry.DOC_VERSION) -> list[Path]:
    # Validate everything up front: no rendering until the content is sound.
    content_loader.validate_all(tuple(locales))

    written: list[Path] = []
    for document_tag in locales:
        for manual_key in manuals:
            # The filename keeps the English title (the app looks manuals up by
            # it); the cover and heading carry the translated one.
            doc_title = doc_strings.strings(document_tag)["titles"][manual_key]
            chapters = content_loader.load_manual(manual_key, document_tag)
            shared = {
                "doc_title": doc_title,
                "chapters": chapters,
                "version": version,
                "document_tag": document_tag,
                "product_name": registry.PRODUCT_NAME,
                "screenshots_dir": SCREENSHOTS_DIR,
            }

            if "pdf" in formats:
                name = registry.manual_filename(manual_key, document_tag, "pdf", version)
                result = _write(build_pdf, OUTPUT_DIR / name, **shared)
                if result:
                    written.append(result)
                    print(f"  wrote {name}")
            if "docx" in formats:
                name = registry.manual_filename(manual_key, document_tag, "docx", version)
                result = _write(build_docx, OUTPUT_DIR / name, **shared)
                if result:
                    written.append(result)
                    print(f"  wrote {name}")
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--locale", action="append", dest="locales",
                        choices=registry.SUPPORTED_DOCUMENT_TAGS
                        + registry.DRAFT_DOCUMENT_TAGS,
                        help="build only this locale (repeatable)")
    parser.add_argument("--manual", action="append", dest="manuals",
                        choices=content_loader.manual_keys(),
                        help="build only this manual (repeatable)")
    parser.add_argument("--format", action="append", dest="formats",
                        choices=registry.SUPPORTED_EXTENSIONS,
                        help="build only this format (repeatable)")
    parser.add_argument("--version", default=registry.DOC_VERSION,
                        help=f"override the doc version (default {registry.DOC_VERSION})")
    args = parser.parse_args(argv)

    locales = args.locales or list(registry.SUPPORTED_DOCUMENT_TAGS)
    manuals = args.manuals or list(content_loader.manual_keys())
    formats = args.formats or list(registry.SUPPORTED_EXTENSIONS)

    print(f"{registry.PRODUCT_NAME} docs {args.version}: "
          f"{len(manuals)} manual(s) x {len(locales)} locale(s) x {len(formats)} format(s)")
    written = build(locales, manuals, formats, version=args.version)
    print(f"\n{len(written)} file(s) written to {OUTPUT_DIR}")
    if manual_fonts.cjk_font_source():
        print(f"zh-CN PDF font: {manual_fonts.cjk_font_source()}")

    uncaptured = _uncaptured_figures()
    if uncaptured:
        print(f"\n{len(uncaptured)} figure(s) still show a placeholder: "
              f"{', '.join(uncaptured)}")
        print("See docs/help/screenshots/SHOTLIST.md, or run capture_screenshots.py.")
    return 0


def _uncaptured_figures() -> list[str]:
    import figures
    return [f["id"] for f in figures.FIGURES
            if figures.resolve_figure_path(f["id"], SCREENSHOTS_DIR) is None]


if __name__ == "__main__":
    raise SystemExit(main())
