"""Loading content bundles, and validating non-English ones against English.

A locale bundle is all-or-nothing. There is no per-string fallback to English:
a half-translated manual that silently mixes languages is worse than a build
that refuses to run, because nobody notices the former until it ships.
"""
from __future__ import annotations

import importlib
from typing import Final

from document_registry import REFERENCE_TAG
from figures import KNOWN_FIGURE_IDS

# manual key -> (module stem within the locale package, exported symbol)
MANUAL_SPECS: Final[dict[str, tuple[str, str]]] = {
    "help": ("help", "CHAPTERS"),
    "quickstart": ("quickstart", "CHAPTERS"),
}

# Language tag -> locale package directory. They differ where a tag contains a
# hyphen, which is not legal in a Python package name (zh-CN -> zh_CN).
_LOCALE_PACKAGES: Final[dict[str, str]] = {
    "en": "en",
    "nl": "nl",
    "zh-CN": "zh_CN",
}

VALID_BLOCK_TYPES: Final[frozenset[str]] = frozenset(
    {"para", "steps", "note", "figure", "code", "table"}
)


def locale_package(locale: str) -> str:
    try:
        return _LOCALE_PACKAGES[locale]
    except KeyError:
        raise ValueError(
            f"unknown locale {locale!r}; known locales are {sorted(_LOCALE_PACKAGES)}"
        ) from None


def manual_keys() -> tuple[str, ...]:
    return tuple(MANUAL_SPECS)


def load_manual(manual_key: str, locale: str = REFERENCE_TAG) -> list[dict]:
    """Import and return the chapter list for one manual in one locale."""
    try:
        stem, attr = MANUAL_SPECS[manual_key]
    except KeyError:
        raise ValueError(
            f"unknown manual {manual_key!r}; known manuals are {sorted(MANUAL_SPECS)}"
        ) from None
    module = importlib.import_module(f"locales.{locale_package(locale)}.{stem}")
    try:
        return getattr(module, attr)
    except AttributeError:
        raise ValueError(
            f"locales.{locale_package(locale)}.{stem} does not export {attr}"
        ) from None


def block_shape_signature(block: dict) -> tuple:
    """A translation-independent fingerprint of one block.

    Captures structure but not wording, so two locales can be compared without
    caring what language they are in. Item and row counts are included because
    a translator dropping a bullet is exactly the kind of drift worth catching.
    """
    btype = block.get("type")
    if btype in ("steps", "note"):
        return (btype, len(block.get("items", ())))
    if btype == "figure":
        return (btype, block.get("fig_id"))
    if btype == "code":
        return (btype, len(block.get("lines", ())))
    if btype == "table":
        rows = block.get("rows", ())
        headers = block.get("headers", ())
        widths = {len(r) for r in rows}
        return (btype, len(headers), len(rows), tuple(sorted(widths)))
    return (btype,)


def validate_bundle(manual_key: str, locale: str) -> None:
    """Check one bundle is internally well formed. Raises on the first problem."""
    chapters = load_manual(manual_key, locale)
    if not chapters:
        raise ValueError(f"{manual_key}/{locale}: no chapters")

    seen: set[str] = set()
    for chapter in chapters:
        chapter_id = chapter.get("id")
        if not chapter_id:
            raise ValueError(f"{manual_key}/{locale}: a chapter has no id")
        if not chapter.get("title"):
            raise ValueError(f"{manual_key}/{locale}: chapter {chapter_id!r} has no title")
        if chapter_id in seen:
            raise ValueError(f"{manual_key}/{locale}: duplicate chapter id {chapter_id!r}")
        seen.add(chapter_id)

        for block in chapter.get("blocks", ()):
            btype = block.get("type")
            if btype not in VALID_BLOCK_TYPES:
                raise ValueError(
                    f"{manual_key}/{locale}: chapter {chapter_id!r} has unknown block "
                    f"type {btype!r}; valid types are {sorted(VALID_BLOCK_TYPES)}"
                )
            if btype == "figure":
                fig_id = block.get("fig_id")
                if fig_id not in KNOWN_FIGURE_IDS:
                    raise ValueError(
                        f"{manual_key}/{locale}: chapter {chapter_id!r} references unknown "
                        f"figure {fig_id!r}"
                    )
            if btype == "table":
                headers = block.get("headers", ())
                for row in block.get("rows", ()):
                    if len(row) != len(headers):
                        raise ValueError(
                            f"{manual_key}/{locale}: chapter {chapter_id!r} has a table row "
                            f"with {len(row)} cells but {len(headers)} headers"
                        )


def validate_bundle_parity(manual_key: str, locale: str) -> None:
    """Check a locale bundle matches the English one structurally."""
    validate_bundle(manual_key, locale)
    if locale == REFERENCE_TAG:
        return

    reference = load_manual(manual_key, REFERENCE_TAG)
    translated = load_manual(manual_key, locale)

    ref_ids = [c["id"] for c in reference]
    loc_ids = [c["id"] for c in translated]
    if ref_ids != loc_ids:
        raise ValueError(
            f"{manual_key}/{locale}: chapter ids {loc_ids!r} do not match "
            f"English {ref_ids!r}"
        )

    for ref_chapter, loc_chapter in zip(reference, translated, strict=True):
        ref_shapes = [block_shape_signature(b) for b in ref_chapter.get("blocks", ())]
        loc_shapes = [block_shape_signature(b) for b in loc_chapter.get("blocks", ())]
        if ref_shapes != loc_shapes:
            raise ValueError(
                f"{manual_key}/{locale}: block layout mismatch in chapter "
                f"{ref_chapter['id']!r}\n  English:    {ref_shapes}\n"
                f"  {locale}: {loc_shapes}"
            )


def validate_all(locales: tuple[str, ...]) -> None:
    """Validate every manual in every given locale before any rendering starts."""
    for locale in locales:
        for manual_key in MANUAL_SPECS:
            validate_bundle_parity(manual_key, locale)
