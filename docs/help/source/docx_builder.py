"""Word output, built programmatically with python-docx.

There is no .dotx template: everything hangs off python-docx's default
template and Word's built-in style names, so the file opens correctly on any
Word install without shipping a theme.

Where python-docx has no API -- bookmarks, internal hyperlinks, the table of
contents field -- this drops to raw OOXML via OxmlElement.
"""
from __future__ import annotations

from pathlib import Path

from document_navigation import chapter_destination, chapters_with_glossary, word_bookmark_name
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from figures import figure_label, resolve_figure_path

BODY_PT = 11
CODE_PT = 9.5
CODE_FONT = "Consolas"
ACCENT = RGBColor(0x2F, 0x8F, 0x86)   # NVC teal, matching the app chrome
MUTED = RGBColor(0x55, 0x60, 0x60)


def _set_run_font(run, name: str) -> None:
    """Set a run's font on all three script slots.

    run.font.name alone only sets w:ascii, which leaves CJK text falling back
    to whatever Word picks. Setting eastAsia too keeps a translated build
    consistent once non-Latin locales are added.
    """
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for slot in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        rfonts.set(qn(slot), name)


def _ensure_hyperlink_style(doc) -> None:
    """Make sure a 'Hyperlink' character style exists and is the built-in one."""
    styles = doc.styles
    try:
        style = styles["Hyperlink"]
    except KeyError:
        from docx.enum.style import WD_STYLE_TYPE
        style = styles.add_style("Hyperlink", WD_STYLE_TYPE.CHARACTER)
        style.font.color.rgb = RGBColor(0x05, 0x63, 0xC1)
        style.font.underline = True
    # A style python-docx created is marked customStyle, which stops Word
    # treating it as the real Hyperlink style.
    element = style.element
    if element.get(qn("w:customStyle")) == "1":
        element.set(qn("w:customStyle"), "0")


def _add_bookmark(paragraph, name: str, bookmark_id: int) -> None:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    # After pPr so the bookmark wraps the paragraph's content, not its properties.
    ppr = paragraph._p.find(qn("w:pPr"))
    if ppr is not None:
        ppr.addnext(start)
    else:
        paragraph._p.insert(0, start)
    paragraph._p.append(end)


def _add_toc(doc) -> None:
    """Insert a real Word TOC field, restricted to Heading 1.

    Word populates this on open because _enable_field_updates sets
    updateFields in settings.xml. The placeholder text is what a reader sees if
    they open the file in something that does not evaluate fields.
    """
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()

    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = r'TOC \o "1-1" \h \z \u'
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Open this document in Word to build the table of contents."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")

    for node in (begin, instr, separate, placeholder, end):
        run._r.append(node)


def _enable_field_updates(doc) -> None:
    settings = doc.settings.element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def _add_para(doc, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(text)
    run.font.size = Pt(BODY_PT)


def _add_steps(doc, items) -> None:
    for item in items:
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(4)
        run = paragraph.add_run(item)
        run.font.size = Pt(BODY_PT)


def _add_note(doc, items) -> None:
    heading = doc.add_paragraph()
    heading.paragraph_format.space_after = Pt(2)
    run = heading.add_run("Note")
    run.bold = True
    run.font.size = Pt(BODY_PT)
    run.font.color.rgb = ACCENT
    for item in items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(4)
        item_run = paragraph.add_run(item)
        item_run.font.size = Pt(BODY_PT)


def _add_code(doc, lines) -> None:
    for line in lines:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.left_indent = Inches(0.25)
        run = paragraph.add_run(line)
        run.font.size = Pt(CODE_PT)
        _set_run_font(run, CODE_FONT)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def _add_table(doc, headers, rows) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, header in zip(table.rows[0].cells, headers, strict=True):
        cell.text = ""
        run = cell.paragraphs[0].add_run(str(header))
        run.bold = True
        run.font.size = Pt(BODY_PT - 1)
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row, strict=True):
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(value))
            run.font.size = Pt(BODY_PT - 1)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def _add_figure(doc, fig_id: str, screenshots_dir: Path | None) -> None:
    """Insert the screenshot, or a visible placeholder naming the shot list."""
    path = resolve_figure_path(fig_id, screenshots_dir)
    if path is not None:
        doc.add_picture(str(path), width=Inches(6.0))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    else:
        placeholder = doc.add_paragraph()
        placeholder.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = placeholder.add_run(
            f"[{fig_id} -- screenshot not captured; see "
            f"docs/help/screenshots/SHOTLIST.md]"
        )
        run.italic = True
        run.font.size = Pt(BODY_PT - 1)
        run.font.color.rgb = MUTED

    caption = doc.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_after = Pt(8)
    caption_run = caption.add_run(figure_label(fig_id))
    caption_run.italic = True
    caption_run.font.size = Pt(BODY_PT - 2)
    caption_run.font.color.rgb = MUTED


def build_docx(output_path, *, doc_title: str, chapters: list[dict], version: str,
               document_tag: str, product_name: str = "NVC",
               screenshots_dir: Path | None = None) -> Path:
    """Render one manual to .docx. Returns the written path."""
    doc = Document()
    _ensure_hyperlink_style(doc)

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.size = Pt(BODY_PT)

    doc.add_heading(f"{product_name} {doc_title}", level=0)
    subtitle = doc.add_paragraph()
    subtitle_run = subtitle.add_run(f"{product_name} {version} -- {document_tag}")
    subtitle_run.font.size = Pt(BODY_PT)
    subtitle_run.font.color.rgb = MUTED

    # "Contents" is deliberately not a Heading 1: the TOC field is scoped to
    # \o "1-1", so a Heading 1 here would list the contents inside itself.
    contents = doc.add_paragraph()
    contents_run = contents.add_run("Contents")
    contents_run.bold = True
    contents_run.font.size = Pt(BODY_PT + 3)
    contents_run.font.color.rgb = ACCENT
    _add_toc(doc)
    doc.add_page_break()

    all_chapters = chapters_with_glossary(chapters, document_tag)
    defined: set[str] = set()
    bookmark_id = 1

    for chapter in all_chapters:
        heading = doc.add_heading(chapter["title"], level=1)
        destination = chapter_destination(chapter)
        if destination in defined:
            raise ValueError(f"duplicate anchor {destination!r}")
        _add_bookmark(heading, word_bookmark_name(destination), bookmark_id)
        defined.add(destination)
        bookmark_id += 1

        for block in chapter.get("blocks", ()):
            btype = block.get("type")
            if btype == "para":
                _add_para(doc, block["text"])
            elif btype == "steps":
                _add_steps(doc, block["items"])
            elif btype == "note":
                _add_note(doc, block["items"])
            elif btype == "figure":
                _add_figure(doc, block["fig_id"], screenshots_dir)
            elif btype == "code":
                _add_code(doc, block["lines"])
            elif btype == "table":
                _add_table(doc, block["headers"], block["rows"])
            else:
                # Strict, matching the PDF walker. A block type that renders in
                # one format but is silently dropped in the other is the kind of
                # divergence nobody notices until a reader does.
                raise ValueError(f"unknown block type: {btype!r}")

    _enable_field_updates(doc)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path
