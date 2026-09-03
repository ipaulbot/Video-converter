"""PDF output, drawn directly on a ReportLab canvas.

No Platypus flowables: this is a small hand-rolled layout engine (_Layout)
tracking a y cursor, which is what makes the two-pass table of contents
possible. The document is rendered twice -- once to a throwaway buffer to
measure which page each chapter lands on, then for real with those page
numbers -- because a TOC cannot know its own page numbers before layout.
"""
from __future__ import annotations

import io
from pathlib import Path

from document_navigation import chapter_destination, chapters_with_glossary
from figures import figure_label, resolve_figure_path
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MARGIN = 25 * 72 / 25.4          # 25 mm
CONTENT_W = PAGE_W - 2 * MARGIN

BODY_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"
ITALIC_FONT = "Helvetica-Oblique"
MONO_FONT = "Courier"

BODY_SIZE = 10.5
HEADING_SIZE = 17
LINE_H = 14
CODE_SIZE = 9
CAPTION_SIZE = 8.5

FIGURE_BOX_H = 70 * 72 / 25.4    # 70 mm
FOOTER_Y = 15 * 72 / 25.4

ACCENT = HexColor("#2F8F86")
INK = HexColor("#1F2A2A")
MUTED = HexColor("#556060")
RULE = HexColor("#C8DEDC")
CODE_BG = Color(0.94, 0.96, 0.96)
PLACEHOLDER_BG = Color(0.92, 0.92, 0.92)


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Greedy word wrap, splitting any single word too wide to fit.

    The per-character split matters for long paths and identifiers, and is
    what would let a non-spaced script wrap at all once one is added.
    """
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        # The word alone may still be too wide.
        while stringWidth(word, font, size) > width and len(word) > 1:
            cut = len(word)
            while cut > 1 and stringWidth(word[:cut], font, size) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


class _Layout:
    """A y-cursor over a ReportLab canvas, with page breaks and footers."""

    def __init__(self, c, doc_title: str, page_map: dict, create_destinations: bool,
                 start_page: int):
        self.c = c
        self.doc_title = doc_title
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
        self.c.setFont(BODY_FONT, 8)
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

        self.c.setFont(BOLD_FONT, HEADING_SIZE)
        self.c.setFillColor(ACCENT)
        self.c.drawString(MARGIN, self.y - HEADING_SIZE, chapter["title"])
        self.y -= HEADING_SIZE + 6
        self.c.setStrokeColor(RULE)
        self.c.setLineWidth(1)
        self.c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= LINE_H
        self.c.setFillColor(INK)

    def para(self, text: str, *, font: str = BODY_FONT, size: float = BODY_SIZE,
             indent: float = 0.0, color=None) -> None:
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
            marker_w = stringWidth("00. ", BODY_FONT, BODY_SIZE)
            lines = _wrap(item, BODY_FONT, BODY_SIZE, CONTENT_W - marker_w)
            for i, line in enumerate(lines):
                self.ensure(LINE_H)
                self.c.setFont(BOLD_FONT if i == 0 else BODY_FONT, BODY_SIZE)
                if i == 0:
                    self.c.setFillColor(ACCENT)
                    self.c.drawString(MARGIN, self.y - BODY_SIZE, marker)
                self.c.setFont(BODY_FONT, BODY_SIZE)
                self.c.setFillColor(INK)
                self.c.drawString(MARGIN + marker_w, self.y - BODY_SIZE, line)
                self.y -= LINE_H
            self.y -= 2
        self.y -= 4

    def note(self, items) -> None:
        self.ensure(LINE_H * 2)
        self.c.setFont(BOLD_FONT, BODY_SIZE)
        self.c.setFillColor(ACCENT)
        self.c.drawString(MARGIN, self.y - BODY_SIZE, "Note")
        self.y -= LINE_H
        bullet_w = stringWidth("-  ", BODY_FONT, BODY_SIZE)
        for item in items:
            lines = _wrap(item, BODY_FONT, BODY_SIZE, CONTENT_W - bullet_w - 6)
            for i, line in enumerate(lines):
                self.ensure(LINE_H)
                self.c.setFont(BODY_FONT, BODY_SIZE)
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
            self.c.setFont(MONO_FONT, CODE_SIZE)
            self.c.drawString(MARGIN + 6, y, str(line))
        self.y -= height + 4

    def table(self, headers, rows) -> None:
        col1 = CONTENT_W * 0.32
        col2 = CONTENT_W - col1

        def row_height(cells, font, size):
            a = _wrap(cells[0], font, size, col1 - 8)
            b = _wrap(cells[1], font, size, col2 - 8)
            return max(len(a), len(b)) * (size + 3) + 6, a, b

        header_h, ha, hb = row_height(headers, BOLD_FONT, BODY_SIZE - 1)
        self.ensure(header_h + LINE_H)
        self.c.setFillColor(CODE_BG)
        self.c.rect(MARGIN, self.y - header_h, CONTENT_W, header_h, stroke=0, fill=1)
        self.c.setFillColor(INK)
        self._table_row(ha, hb, col1, BOLD_FONT, BODY_SIZE - 1, header_h)

        for row in rows:
            h, a, b = row_height(row, BODY_FONT, BODY_SIZE - 1)
            self.ensure(h + 4)
            self._table_row(a, b, col1, BODY_FONT, BODY_SIZE - 1, h)
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
            self.c.setFont(ITALIC_FONT, BODY_SIZE - 1)
            msg = f"{fig_id} -- screenshot not captured (see SHOTLIST.md)"
            self.c.drawCentredString(PAGE_W / 2, box_top - FIGURE_BOX_H / 2, msg)
            self.y = box_top - FIGURE_BOX_H - 4
            self.c.setFillColor(INK)

        for line in _wrap(figure_label(fig_id), ITALIC_FONT, CAPTION_SIZE, CONTENT_W):
            self.c.setFont(ITALIC_FONT, CAPTION_SIZE)
            self.c.setFillColor(MUTED)
            self.c.drawCentredString(PAGE_W / 2, self.y - CAPTION_SIZE, line)
            self.y -= CAPTION_SIZE + 3
        self.c.setFillColor(INK)
        self.y -= 6


def _draw_cover(c, product_name: str, doc_title: str, version: str, tag: str) -> None:
    c.setFillColor(ACCENT)
    c.setFont(BOLD_FONT, 40)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, product_name)
    c.setFillColor(INK)
    c.setFont(BODY_FONT, 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62 - 38, doc_title)
    c.setStrokeColor(RULE)
    c.setLineWidth(2)
    c.line(PAGE_W * 0.3, PAGE_H * 0.62 - 60, PAGE_W * 0.7, PAGE_H * 0.62 - 60)
    c.setFillColor(MUTED)
    c.setFont(BODY_FONT, 12)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62 - 84, f"Version {version}")
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62 - 102, f"Language: {tag}")
    c.showPage()


def _draw_toc(c, chapters, page_map, create_destinations) -> int:
    """Draw the contents list. Returns the number of pages it used."""
    pages_used = 1
    c.setFillColor(ACCENT)
    c.setFont(BOLD_FONT, HEADING_SIZE)
    c.drawString(MARGIN, PAGE_H - MARGIN - HEADING_SIZE, "Contents")
    c.setFillColor(INK)
    y = PAGE_H - MARGIN - HEADING_SIZE - LINE_H * 1.6

    dot_w = stringWidth(".", BODY_FONT, BODY_SIZE)
    for chapter in chapters:
        destination = chapter_destination(chapter)
        if create_destinations and destination not in page_map:
            raise ValueError(
                f"chapter {destination!r} was never measured; the measuring pass "
                "and the final pass disagree"
            )
        page_no = str(page_map.get(destination, ""))
        title = chapter["title"]
        c.setFont(BODY_FONT, BODY_SIZE)
        c.drawString(MARGIN, y, title)
        title_w = stringWidth(title, BODY_FONT, BODY_SIZE)
        page_w = stringWidth(page_no, BODY_FONT, BODY_SIZE)
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
    _draw_cover(c, product_name, doc_title, version, document_tag)
    toc_pages = _draw_toc(c, chapters, page_map, create_destinations)

    # Cover is page 1, the contents take toc_pages after it, so the body's
    # first chapter lands on the page right after those.
    layout = _Layout(c, doc_title, page_map, create_destinations,
                     start_page=1 + toc_pages + 1)
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
