"""Fonts per locale.

The Latin manuals use ReportLab's built-in Helvetica family, which has no CJK
glyphs: a Chinese build with it draws every character as a black box. For
zh-CN the PDF embeds a TrueType face with Chinese coverage -- a font dropped
into docs/help/source/fonts/ first, then the Windows system fonts (Microsoft
YaHei, SimHei, SimSun). If none is found the build falls back to ReportLab's
STSong-Light CID font, which every PDF viewer can display without embedding.

Word documents do not embed fonts, so for zh-CN the .docx only names an East
Asian font for Word to pick up.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PDF_CJK_FONT_NAME = "NVC-CJK"
PDF_CJK_BOLD_FONT_NAME = "NVC-CJK-Bold"
DOCX_CJK_FONT_NAME = "Microsoft YaHei"

FONTS_DIR = Path(__file__).resolve().parent / "fonts"

# (regular, bold) candidates, tried in order. A .ttc is a collection; face 0
# is the regular family member in every file listed here.
_CJK_CANDIDATES: tuple[tuple[str, str | None], ...] = (
    ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"),
    ("NotoSansCJKsc-Regular.ttf", "NotoSansCJKsc-Bold.ttf"),
    ("msyh.ttc", "msyhbd.ttc"),
    ("simhei.ttf", None),
    ("simsun.ttc", None),
)

_registered: dict[str, str] = {}


@dataclass(frozen=True)
class FontSet:
    body: str
    bold: str
    italic: str
    mono: str


LATIN = FontSet("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier")


def _font_dirs() -> list[Path]:
    dirs = [FONTS_DIR]
    windir = os.environ.get("WINDIR")
    if windir:
        dirs.append(Path(windir) / "Fonts")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return dirs


def _find(filename: str) -> Path | None:
    for directory in _font_dirs():
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def _register_ttf(name: str, path: Path) -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if path.suffix.lower() == ".ttc":
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
    else:
        pdfmetrics.registerFont(TTFont(name, str(path)))


def register_pdf_cjk_fonts() -> tuple[str, str]:
    """Register a CJK regular and bold face; returns their ReportLab names."""
    if "body" in _registered:
        return _registered["body"], _registered["bold"]

    for regular, bold in _CJK_CANDIDATES:
        regular_path = _find(regular)
        if regular_path is None:
            continue
        _register_ttf(PDF_CJK_FONT_NAME, regular_path)
        bold_path = _find(bold) if bold else None
        if bold_path is not None:
            _register_ttf(PDF_CJK_BOLD_FONT_NAME, bold_path)
            bold_name = PDF_CJK_BOLD_FONT_NAME
        else:
            bold_name = PDF_CJK_FONT_NAME
        _registered.update(body=PDF_CJK_FONT_NAME, bold=bold_name, source=str(regular_path))
        return PDF_CJK_FONT_NAME, bold_name

    # No TrueType face available: fall back to the Adobe CID font ReportLab
    # knows about. Not embedded, but Chinese renders in every mainstream viewer.
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _registered.update(body="STSong-Light", bold="STSong-Light", source="STSong-Light (CID)")
    return "STSong-Light", "STSong-Light"


def pdf_fonts(locale: str) -> FontSet:
    if locale == "zh-CN":
        body, bold = register_pdf_cjk_fonts()
        # No italic CJK face: captions use the regular face. Code lines stay
        # ASCII in every locale, so Courier is still right for them.
        return FontSet(body, bold, body, LATIN.mono)
    return LATIN


def cjk_font_source() -> str | None:
    """Where the CJK face came from, for the build log."""
    return _registered.get("source")


def docx_east_asian_font(locale: str) -> str | None:
    return DOCX_CJK_FONT_NAME if locale == "zh-CN" else None
