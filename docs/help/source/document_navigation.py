"""Format-agnostic navigation: anchors, and the appended glossary chapter.

Both builders share this so a PDF link and a Word bookmark always point at the
same place. Nothing here knows about ReportLab or python-docx.
"""
from __future__ import annotations

import hashlib
import re

CHAPTER_ANCHOR_PREFIX = "chapter-"
GLOSSARY_CHAPTER_ID = "glossary"


def chapter_destination(chapter: dict) -> str:
    """Anchor name for a chapter, derived from its stable id.

    Never from the title: titles get reworded and translated, and a link that
    moves when prose changes is worse than no link.
    """
    chapter_id = chapter.get("id")
    if not chapter_id:
        raise ValueError(f"chapter has no id: {chapter.get('title')!r}")
    return f"{CHAPTER_ANCHOR_PREFIX}{chapter_id}"


def word_bookmark_name(destination: str) -> str:
    """Coerce an anchor into a name Word will accept.

    Word bookmarks must start with a letter, contain only letters, digits and
    underscores, and be at most 40 characters. Over-long names are truncated
    and given a short digest so two long anchors cannot collide.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", destination)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"b_{cleaned}"
    if len(cleaned) <= 40:
        return cleaned
    digest = hashlib.sha256(destination.encode("utf-8")).hexdigest()[:10]
    return f"{cleaned[:29]}_{digest}"


def glossary_chapter(locale: str = "en") -> dict:
    """Build the glossary as a normal chapter, so both builders just render it."""
    module = _glossary_module(locale)
    return {
        "id": GLOSSARY_CHAPTER_ID,
        "title": module.GLOSSARY_TITLE,
        "blocks": [
            {"type": "para", "text": module.GLOSSARY_INTRO},
            {"type": "table",
             "headers": tuple(module.GLOSSARY_HEADERS),
             "rows": [tuple(row) for row in module.GLOSSARY_ROWS]},
        ],
    }


def chapters_with_glossary(chapters: list[dict], locale: str = "en") -> list[dict]:
    """Return chapters with the glossary last.

    If the manual already declares a glossary chapter it is moved to the end
    rather than duplicated. Raises on duplicate ids, since two chapters sharing
    an id would silently collapse two anchors into one.
    """
    out = [c for c in chapters if c.get("id") != GLOSSARY_CHAPTER_ID]
    existing = [c for c in chapters if c.get("id") == GLOSSARY_CHAPTER_ID]
    out.append(existing[0] if existing else glossary_chapter(locale))

    seen: set[str] = set()
    for chapter in out:
        chapter_id = chapter.get("id")
        if chapter_id in seen:
            raise ValueError(f"duplicate chapter id {chapter_id!r}")
        seen.add(chapter_id)
    return out


def _glossary_module(locale: str):
    from content_loader import locale_package
    package = locale_package(locale)
    return __import__(f"locales.{package}.glossary", fromlist=["GLOSSARY_TITLE"])
