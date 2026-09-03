"""Finding the help document to open from the Help menu.

The generated manuals are named `NVC <version> - <Title> - <tag>.pdf` by
docs/help/source/document_registry.py. This module deliberately does NOT
import that module: it lives in the docs tree, which is not present in a
frozen build. The filename pattern is duplicated here instead, so keep the two
in sync -- the pipeline's own tests pin the grammar on that side.

The manuals are the only help documents; the hand-written
help_document.pdf/.html they replaced were removed in favour of generated
output.
"""
from __future__ import annotations

import re
from pathlib import Path

from utils.resources import resource_path

PRODUCT_NAME = "NVC"
DEFAULT_TITLE = "Help"
DEFAULT_LANGUAGE = "en"

# Mirrors document_registry._FILENAME_RE.
_FILENAME_RE = re.compile(
    r"^(?P<product>[A-Za-z0-9]+) (?P<version>[0-9][0-9.]*) - "
    r"(?P<title>.+?) - (?P<tag>[A-Za-z-]+)\.(?P<ext>pdf|docx)$"
)

# Places a generated manual may sit: beside a frozen executable, or in the
# repository layout when running from source.
_SEARCH_DIRS = ("docs/help", "help", ".")


def _version_tuple(version: str) -> tuple[int, ...]:
    out = []
    for piece in version.split("."):
        try:
            out.append(int(piece))
        except ValueError:
            out.append(0)
    return tuple(out)


def find_generated_manual(title: str = DEFAULT_TITLE,
                          language: str = DEFAULT_LANGUAGE,
                          ext: str = "pdf") -> Path | None:
    """Return the newest matching generated manual, or None.

    Falls back to English when the requested language has not been shipped,
    which is what makes adding a locale a non-breaking change.
    """
    candidates: list[tuple[tuple[int, ...], float, Path]] = []
    for rel in _SEARCH_DIRS:
        directory = Path(resource_path(rel))
        if not directory.is_dir():
            continue
        for path in directory.glob(f"*.{ext}"):
            match = _FILENAME_RE.match(path.name)
            if not match:
                continue
            parts = match.groupdict()
            if parts["product"] != PRODUCT_NAME or parts["title"] != title:
                continue
            if parts["tag"] not in (language, DEFAULT_LANGUAGE):
                continue
            # Prefer the requested language over the English fallback.
            language_rank = 1 if parts["tag"] == language else 0
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append(
                ((language_rank,) + _version_tuple(parts["version"]), mtime, path)
            )

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[-1][2]


def resolve_help_document(language: str = DEFAULT_LANGUAGE) -> Path | None:
    """Return the generated help manual, or None when none has been built."""
    return find_generated_manual(language=language)
