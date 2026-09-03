"""Document identity: version, locales, and the output filename grammar.

This is the only place the filename convention exists. Everything else asks
this module rather than formatting names itself.
"""
from __future__ import annotations

import re
from typing import Final

# Documentation version, bumped by hand when the manuals are regenerated for
# release. Deliberately separate from the application version in
# utils/version.py: the docs and the app do not have to ship in lockstep, and
# a docs-only correction should not imply a new build.
DOC_VERSION: Final[str] = "2.2.0"

# Locale tags the manuals can be built for. "en" is the reference locale that
# every other bundle is validated against.
REFERENCE_TAG: Final[str] = "en"
SUPPORTED_DOCUMENT_TAGS: Final[tuple[str, ...]] = ("en",)

# Tags that have a content bundle but are not yet complete enough to ship.
# Kept separate so a draft translation can be built and reviewed without
# appearing in a release.
DRAFT_DOCUMENT_TAGS: Final[tuple[str, ...]] = ()

PRODUCT_NAME: Final[str] = "NVC"

# manual key -> display title used in the filename and on the cover.
MANUAL_TITLES: Final[dict[str, str]] = {
    "help": "Help",
    "quickstart": "Quick Start Guide",
}

SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = ("pdf", "docx")

_FILENAME_RE = re.compile(
    r"^(?P<product>[A-Za-z0-9]+) (?P<version>[0-9][0-9.]*) - "
    r"(?P<title>.+?) - (?P<tag>[A-Za-z-]+)\.(?P<ext>pdf|docx)$"
)


def manual_title(manual_key: str) -> str:
    try:
        return MANUAL_TITLES[manual_key]
    except KeyError:
        raise ValueError(
            f"unknown manual {manual_key!r}; expected one of "
            f"{sorted(MANUAL_TITLES)}"
        ) from None


def manual_filename(manual_key: str, document_tag: str, ext: str,
                    version: str = DOC_VERSION) -> str:
    """Return e.g. 'NVC 2.2.0 - Help - en.pdf'."""
    title = manual_title(manual_key)
    if document_tag not in SUPPORTED_DOCUMENT_TAGS + DRAFT_DOCUMENT_TAGS:
        raise ValueError(f"unsupported document tag {document_tag!r}")
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported extension {ext!r}")
    return f"{PRODUCT_NAME} {version} - {title} - {document_tag}.{ext}"


def parse_manual_filename(filename: str) -> dict[str, str] | None:
    """Inverse of manual_filename. Returns None if the name does not match."""
    m = _FILENAME_RE.match(filename)
    if not m:
        return None
    parts = m.groupdict()
    titles = {v: k for k, v in MANUAL_TITLES.items()}
    manual_key = titles.get(parts["title"])
    if manual_key is None:
        return None
    parts["manual_key"] = manual_key
    return parts


def version_tuple(version: str) -> tuple[int, ...]:
    """Sortable form of a dotted version, for picking the newest shipped file."""
    out = []
    for piece in version.split("."):
        try:
            out.append(int(piece))
        except ValueError:
            out.append(0)
    return tuple(out)
