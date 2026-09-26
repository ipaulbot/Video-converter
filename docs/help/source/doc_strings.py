"""The builders' own words, per locale: "Contents", "Note", "Figure 3." and so on.

Chapter prose lives in the locale bundles; these are the few strings the PDF
and Word builders print themselves. Each locale package exports a STRINGS
dict from its strings.py, and test_help_docs.py asserts every locale has the
same keys as English so a missing entry cannot fall back to English quietly.
"""
from __future__ import annotations

import importlib
from functools import cache
from typing import Final

from document_registry import REFERENCE_TAG

REQUIRED_KEYS: Final[frozenset[str]] = frozenset({
    "contents",         # heading of the table of contents
    "note",             # heading of a note callout
    "figure_label",     # "Figure %(n)d. %(caption)s"
    "version",          # "Version %(version)s" on the cover
    "language",         # "Language: %(tag)s" on the cover
    "missing_figure",   # placeholder drawn when a screenshot has not been captured
    "toc_placeholder",  # Word: text shown until the TOC field is updated
    "titles",           # manual key -> display title on the cover / heading
    "figure_captions",  # figure id -> caption
})


@cache
def strings(locale: str = REFERENCE_TAG) -> dict:
    from content_loader import locale_package
    module = importlib.import_module(f"locales.{locale_package(locale)}.strings")
    table = dict(module.STRINGS)
    missing = REQUIRED_KEYS - set(table)
    extra = set(table) - REQUIRED_KEYS
    if missing or extra:
        raise ValueError(
            f"locales/{locale_package(locale)}/strings.py: missing {sorted(missing)}, "
            f"unexpected {sorted(extra)}"
        )
    return table


def text(locale: str, key: str, **values) -> str:
    """One builder string, with its placeholders filled in."""
    template = strings(locale)[key]
    return template % values if values else template
