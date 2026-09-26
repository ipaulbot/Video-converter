"""PDF output, drawn directly on a ReportLab canvas.

No Platypus flowables: this is a small hand-rolled layout engine (_Layout)
tracking a y cursor, which is what makes the two-pass table of contents
possible. The document is rendered twice -- once to a throwaway buffer to
measure which page each chapter lands on, then for real with those page
numbers -- because a TOC cannot know its own page numbers before layout.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import doc_strings
import manual_fonts
from document_navigation import chapter_destination, chapters_with_glossary
from figures import figure_label, resolve_figure_path
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MARGIN = 25 * 72 / 25.4          # 25 mm
CONTENT_W = PAGE_W - 2 * MARGIN

# The Latin defaults. A build for zh-CN swaps in a CJK face per document
# (see manual_fonts); these module names stay for the Latin locales and tests.
BODY_FONT = manual_fonts.LATIN.body
BOLD_FONT = manual_fonts.LATIN.bold
ITALIC_FONT = manual_fonts.LATIN.italic
MONO_FONT = manual_fonts.LATIN.mono

BODY_SIZE = 10.5
HEADING_SIZE = 17
LINE_H = 14
CODE_SIZE = 9
CAPTION_SIZE = 8.5

FIGURE_BOX_H = 70 * 72 / 25.4    # 70 mm
FOOTER_Y = 15 * 72 / 25.4


def _brand_colours():
    """Read the brand colours from the app's theme, if it is importable.

    The docs build runs standalone (and in CI without PyQt5), so this falls
    back to the same literals rather than making reportlab depend on Qt. The
    fallback is asserted against ui/theme.py by test_help_docs.py, so the two
    cannot drift silently.
    """
    try:
        import sys
        from pathlib import Path as _Path
        root = _Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.theme import IDLE
        return IDLE.accent, IDLE.text_primary, IDLE.text_body, IDLE.text_muted
    except Exception:
        return "#43a296", "#2d7d6f", "#333333", "#6c757d"


_ACCENT, _HEADING, _BODY, _MUTED = _brand_colours()

ACCENT = HexColor(_HEADING)
INK = HexColor(_BODY)
MUTED = HexColor(_MUTED)
RULE = HexColor("#C8DEDC")
CODE_BG = Color(0.94, 0.96, 0.96)
PLACEHOLDER_BG = Color(0.92, 0.92, 0.92)


_CJK = re.compile(r"[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF\u3000-\u303F]")
# Punctuation that must not start a line in Chinese typesetting (kinsoku).
_NO_LINE_START = set("。,、;:!?”’)》」』】〕〉…—,.;:!?)")


def _tokens(text: str) -> list[tuple[str, bool]]:
    """Break text into (unit, space_before) pairs.

    Latin words are units separated by spaces. Every CJK character is its own
    unit with no space around it, so a Chinese sentence -- which has no
    spaces -- can break after any character instead of being one giant word.
    """
    out: list[tuple[str, bool]] = []
    for word in str(text).split():
        space_before = bool(out)
        latin = ""
        for char in word:
            if _CJK.match(char):
                if latin:
                    out.append((latin, space_before))
                    latin, space_before = "", False
                out.append((char, space_before))
                space_before = False
            else:
                latin += char
        if latin:
            out.append((latin, space_before))
    return out


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Greedy wrap over words (Latin) and characters (CJK).

    A single unit wider than the measure -- a long path or identifier -- is
    split per character so nothing runs off the page.
    """
    tokens = _tokens(text)
    if not tokens:
        return [""]
    lines: list[str] = []
    current = ""
    for unit, space_before in tokens:
        candidate = current + (" " if space_before and current else "") + unit
        if stringWidth(candidate, font, size) <= width:
            current = candidate
            continue
        if current and unit in _NO_LINE_START:
            current = candidate          # let the comma hang rather than lead
            continue
        if current:
            lines.append(current)
        if stringWidth(unit, font, size) > width:
            piece = ""
            for char in unit:
                if piece and stringWidth(piece + char, font, size) > width:
                    lines.append(piece)
                    piece = ""
                piece += char
            unit = piece
        current = unit
    if current:
        lines.append(current)
    return lines


class _Layout:
    """A y-cursor over a ReportLab canvas, with page breaks and footers."""

    def __init__(self, c, doc_title: str, page_map: dict, create_destinations: bool,
                 start_page: int, *, locale: str = "en",
                 fonts: manual_fonts.FontSet = manual_fonts.LATIN):
        self.c = c
        self.doc_title = doc_title
        self.locale = locale
        self.f = fonts
        self.page_map = page_map
        self.create_destinations = create_destinations
        # The canvas is already sitting on this physical page: the cover and the
        # table of contents each ended with showPage(), so the body starts here
        # and must not break again before its first heading.
        self.page = start_page
        self.y = PAGE_H - MARGIN
        self.chapter_title = ""
        self.measured: dict[str, int] = {}
        self._started = False

    # -- page mechanics -------------------------------------------------
    def _footer(self) -> None:
        self.c.setFont(self.f.body, 8)
        self.c.setFillColor(MUTED)
        if self.chapter_title:
            self.c.drawString(MARGIN, FOOTER_Y, self.chapter_title)
        self.c.drawRightString(PAGE_W - MARGIN, FOOTER_Y, str(self.page))
        self.c.setFillColor(INK)

    def new_page(self) -> None:
        self._footer()
        self.c.showPage()
        self.page += 1
        self.y = PAGE_H - MARGIN

    def ensure(self, needed: float) -> None:
        if self.y - needed < MARGIN + 2 * LINE_H:
            self.new_page()

    def finish(self) -> None:
        self._footer()
        self.c.showPage()

    # -- blocks ---------------------------------------------------------
    def chapter_heading(self, chapter: dict) -> None:
        if self._started:
            self.new_page()
        self._started = True
        self.chapter_title = chapter["title"]
        self.measured[chapter_destination(chapter)] = self.page

        if self.create_destinations:
            self.c.bookmarkHorizontalAbsolute(chapter_destination(chapter), self.y + 4)
            self.c.addOutlineEntry(chapter["title"], chapter_destination(chapter), 0)

        self.c.setFont(self.f.bold, HEADING_SIZE)
        self.c.setFillColor(ACCENT)
        self.c.drawString(MARGIN, self.y - HEADING_SIZE, chapter["title"])
        self.y -= HEADING_SIZE + 6
        self.c.setStrokeColor(RULE)
        self.c.setLineWidth(1)
        self.c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= LINE_H
        self.c.setFillColor(INK)

    def para(self, text: str, *, font: str | None = None, size: float = BODY_SIZE,
             indent: float = 0.0, color=None) -> None:
        font = font or self.f.body
        lines = _wrap(text, font, size, CONTENT_W - indent)
        for line in lines:
            self.ensure(LINE_H)
            self.c.setFont(font, size)
            self.c.setFillColor(color or INK)
            self.c.drawString(MARGIN + indent, self.y - size, line)
            self.y -= LINE_H
        self.y -= 4
        self.c.setFillColor(INK)

    def steps(self, items) -> None:
        for n, item in enumerate(items, start=1):
            marker = f"{n}."
            marker_w = stringWidth("00. ", self.f.body, BODY_SIZE)
            lines = _wrap(item, self.f.body, BODY_SIZE, CONTENT_W - marker_w)
            for i, line in enumerate(lines):
                self.ensure(LINE_H)
                self.c.setFont(self.f.bold if i == 0 else self.f.body, BODY_SIZE)
                if i == 0:
                    self.c.setFillColor(ACCENT)
                    self.c.drawString(MARGIN, self.y - BODY_SIZE, marker)
                self.c.setFont(self.f.body, BODY_SIZE)
                self.c.setFillColor(INK)
                self.c.drawString(MARGIN + marker_w, self.y - BODY_SIZE, line)
                self.y -= LINE_H
            self.y -= 2
        self.y -= 4

    def note(self, items) -> None:
        self.ensure(LINE_H * 2)
        self.c.setFont(self.f.bold, BODY_SIZE)
        self.c.setFillColor(ACCENT)
        self.c.drawString(MARGIN, self.y - BODY_SIZE, doc_strings.text(self.locale, "note"))
        self.y -= LINE_H
        bullet_w = stringWidth("-  ", self.f.body, BODY_SIZE)
        for item in items:
            lines = _wrap(item, self.f.body, BODY_SIZE, CONTENT_W - bullet_w - 6)
            for i, line in enumerate(lines):
                self.ensure(LINE_H)
                self.c.setFont(self.f.body, BODY_SIZE)
                self.c.setFillColor(ACCENT if i == 0 else INK)
                if i == 0:
                    self.c.drawString(MARGIN + 6, self.y - BODY_SIZE, "-")
                self.c.setFillColor(INK)
                self.c.drawString(MARGIN + 6 + bullet_w, self.y - BODY_SIZE, line)
                self.y -= LINE_H
            self.y -= 2
        self.y -= 4

    def code(self, lines) -> None:
        height = len(lines) * (CODE_SIZE + 3) + 8
        self.ensure(height)
        self.c.setFillColor(CODE_BG)
        self.c.rect(MARGIN, self.y - height + 4, CONTENT_W, height, stroke=0, fill=1)
        self.c.setFillColor(INK)
        y = self.y - 4
        for line in lines:
            y -= CODE_SIZE + 3
            self.c.setFont(self.f.mono, CODE_SIZE)
            self.c.drawString(MARGIN + 6, y, str(line))
        self.y -= height + 4

    def table(self, headers, rows) -> None:
        col1 = CONTENT_W * 0.32
        col2 = CONTENT_W - col1

        def row_height(cells, font, size):
            a = _wrap(cells[0], font, size, col1 - 8)
            b = _wrap(cells[1], font, size, col2 - 8)
            return max(len(a), len(b)) * (size + 3) + 6, a, b

        header_h, ha, hb = row_height(headers, self.f.bold, BODY_SIZE - 1)
        self.ensure(header_h + LINE_H)
        self.c.setFillColor(CODE_BG)
        self.c.rect(MARGIN, self.y - header_h, CONTENT_W, header_h, stroke=0, fill=1)
        self.c.setFillColor(INK)
        self._table_row(ha, hb, col1, self.f.bold, BODY_SIZE - 1, header_h)

        for row in rows:
            h, a, b = row_height(row, self.f.body, BODY_SIZE - 1)
            self.ensure(h + 4)
            self._table_row(a, b, col1, self.f.body, BODY_SIZE - 1, h)
            self.c.setStrokeColor(RULE)
            self.c.setLineWidth(0.5)
            self.c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= 6

    def _table_row(self, left_lines, right_lines, col1, font, size, height) -> None:
        top = self.y
        self.c.setFont(font, size)
        self.c.setFillColor(INK)
        y = top - 3
        for line in left_lines:
            y -= size + 3
            self.c.drawString(MARGIN + 4, y, line)
        y = top - 3
        for line in right_lines:
            y -= size + 3
            self.c.drawString(MARGIN + col1 + 4, y, line)
        self.y = top - height

    def figure(self, fig_id: str, screenshots_dir: Path | None) -> None:
        self.ensure(FIGURE_BOX_H + LINE_H * 2)
        path = resolve_figure_path(fig_id, screenshots_dir)
        box_top = self.y
        if path is not None:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(str(path))
            iw, ih = img.getSize()
            scale = min(CONTENT_W / iw, FIGURE_BOX_H / ih)
            w, h = iw * scale, ih * scale
            self.c.drawImage(str(path), MARGIN + (CONTENT_W - w) / 2,
                             box_top - h, width=w, height=h,
                             preserveAspectRatio=True, anchor="c")
            self.y = box_top - h - 4
        else:
            self.c.setFillColor(PLACEHOLDER_BG)
            self.c.rect(MARGIN, box_top - FIGURE_BOX_H, CONTENT_W, FIGURE_BOX_H,
                        stroke=0, fill=1)
            self.c.setFillColor(MUTED)
            self.c.setFont(self.f.italic, BODY_SIZE - 1)
            msg = doc_strings.text(self.locale, "missing_figure", fig_id=fig_id)
            self.c.drawCentredString(PAGE_W / 2, box_top - FIGURE_BOX_H / 2, msg)
            self.y = box_top - FIGURE_BOX_H - 4
            self.c.setFillColor(INK)

        label = figure_label(fig_id, self.locale)
        for line in _wrap(label, self.f.italic, CAPTION_SIZE, CONTENT_W):
            self.c.setFont(self.f.italic, CAPTION_SIZE)
            self.c.setFillColor(MUTED)
            self.c.drawCentredString(PAGE_W / 2, self.y - CAPTION_SIZE, line)
            self.y -= CAPTION_SIZE + 3
        self.c.setFillColor(INK)
        self.y -= 6


def _draw_cover(c, product_name: str, doc_title: str, version: str, tag: str,
                fonts: manual_fonts.FontSet) -> None:
    c.setFillColor(ACCENT)
    c.setFont(fonts.bold, 40)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, product_name)
    c.setFillColor(INK)
    c.setFont(fonts.body, 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62 - 38, doc_title)
    c.setStrokeColor(RULE)
    c.setLineWidth(2)
    c.line(PAGE_W * 0.3, PAGE_H * 0.62 - 60, PAGE_W * 0.7, PAGE_H * 0.62 - 60)
    c.setFillColor(MUTED)
    c.setFont(fonts.body, 12)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62 - 84,
                        doc_strings.text(tag, "version", version=version))
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62 - 102,
                        doc_strings.text(tag, "language", tag=tag))
    c.showPage()


def _draw_toc(c, chapters, page_map, create_destinations, *, locale: str,
              fonts: manual_fonts.FontSet) -> int:
    """Draw the contents list. Returns the number of pages it used."""
    pages_used = 1
    c.setFillColor(ACCENT)
    c.setFont(fonts.bold, HEADING_SIZE)
    c.drawString(MARGIN, PAGE_H - MARGIN - HEADING_SIZE, doc_strings.text(locale, "contents"))
    c.setFillColor(INK)
    y = PAGE_H - MARGIN - HEADING_SIZE - LINE_H * 1.6

    dot_w = stringWidth(".", fonts.body, BODY_SIZE)
    for chapter in chapters:
        destination = chapter_destination(chapter)
        if create_destinations and destination not in page_map:
            raise ValueError(
                f"chapter {destination!r} was never measured; the measuring pass "
                "and the final pass disagree"
            )
        page_no = str(page_map.get(destination, ""))
        title = chapter["title"]
        c.setFont(fonts.body, BODY_SIZE)
        c.drawString(MARGIN, y, title)
        title_w = stringWidth(title, fonts.body, BODY_SIZE)
        page_w = stringWidth(page_no, fonts.body, BODY_SIZE)
        gap = CONTENT_W - title_w - page_w - 8
        if gap > dot_w:
            dots = "." * int(gap / dot_w)
            c.setFillColor(RULE)
            c.drawString(MARGIN + title_w + 4, y, dots)
            c.setFillColor(INK)
        c.drawRightString(PAGE_W - MARGIN, y, page_no)
        if create_destinations:
            c.linkRect("", destination,
                       (MARGIN, y - 2, PAGE_W - MARGIN, y + BODY_SIZE),
                       relative=0, thickness=0)
        y -= LINE_H
        if y < MARGIN + LINE_H * 2:
            c.showPage()
            pages_used += 1
            y = PAGE_H - MARGIN
    c.showPage()
    return pages_used


def _render(c, *, product_name, doc_title, chapters, version, document_tag,
            page_map, create_destinations, screenshots_dir) -> dict[str, int]:
    fonts = manual_fonts.pdf_fonts(document_tag)
    _draw_cover(c, product_name, doc_title, version, document_tag, fonts)
    toc_pages = _draw_toc(c, chapters, page_map, create_destinations,
                          locale=document_tag, fonts=fonts)

    # Cover is page 1, the contents take toc_pages after it, so the body's
    # first chapter lands on the page right after those.
    layout = _Layout(c, doc_title, page_map, create_destinations,
                     start_page=1 + toc_pages + 1, locale=document_tag, fonts=fonts)
    for chapter in chapters:
        layout.chapter_heading(chapter)
        for block in chapter.get("blocks", ()):
            btype = block.get("type")
            if btype == "para":
                layout.para(block["text"])
            elif btype == "steps":
                layout.steps(block["items"])
            elif btype == "note":
                layout.note(block["items"])
            elif btype == "figure":
                layout.figure(block["fig_id"], screenshots_dir)
            elif btype == "code":
                layout.code(block["lines"])
            elif btype == "table":
                layout.table(block["headers"], block["rows"])
            else:
                raise ValueError(f"unknown block type: {btype!r}")
    layout.finish()
    return layout.measured


def build_pdf(output_path, *, doc_title: str, chapters: list[dict], version: str,
              document_tag: str, product_name: str = "NVC",
              screenshots_dir: Path | None = None) -> Path:
    """Render one manual to .pdf using a measure pass then a final pass."""
    all_chapters = chapters_with_glossary(chapters, document_tag)

    shared = {
        "product_name": product_name,
        "doc_title": doc_title,
        "chapters": all_chapters,
        "version": version,
        "document_tag": document_tag,
        "screenshots_dir": screenshots_dir,
    }

    # Pass 1: lay the document out into a throwaway buffer purely to learn
    # which page each chapter starts on.
    measuring = canvas.Canvas(io.BytesIO(), pagesize=A4)
    page_map = _render(measuring, page_map={}, create_destinations=False, **shared)

    # Pass 2: the real file, now able to print correct TOC page numbers.
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final = canvas.Canvas(str(output_path), pagesize=A4)
    final.setTitle(f"{product_name} {doc_title}")
    _render(final, page_map=page_map, create_destinations=True, **shared)
    final.save()
    return output_path
