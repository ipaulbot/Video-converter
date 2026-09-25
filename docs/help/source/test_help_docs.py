"""Tests for the help-documentation pipeline.

Run from the repository root:

    python -m pytest docs/help/source/test_help_docs.py -q

These are the pipeline's spec. They cover the invariants that are expensive to
notice by eye in a rendered document: that every figure reference resolves,
that a locale bundle cannot drift from English, that the PDF's table of
contents cites the page each chapter is actually on, and that both builders
reject a block type rather than silently dropping it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

import content_loader as cl  # noqa: E402
import document_navigation as nav  # noqa: E402
import document_registry as registry  # noqa: E402
import figures  # noqa: E402


def _has(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


# The builders need reportlab / python-docx, which live in
# requirements-help.txt rather than requirements.txt. A lean install that only
# runs the app should skip these rather than fail.
HAS_DOCX = _has("docx")
HAS_REPORTLAB = _has("reportlab")
HAS_PDF_READER = _has("pypdf") or _has("PyPDF2")


class RegistryTests(unittest.TestCase):
    def test_filename_grammar_round_trips(self):
        for manual_key in cl.manual_keys():
            for ext in registry.SUPPORTED_EXTENSIONS:
                name = registry.manual_filename(manual_key, "en", ext)
                parsed = registry.parse_manual_filename(name)
                self.assertIsNotNone(parsed, name)
                self.assertEqual(parsed["manual_key"], manual_key)
                self.assertEqual(parsed["tag"], "en")
                self.assertEqual(parsed["ext"], ext)
                self.assertEqual(parsed["version"], registry.DOC_VERSION)

    def test_unrelated_filename_is_not_parsed(self):
        for name in ("notes.pdf", "NVC - Help - en.pdf", "NVC 2.2.0 - Nope - en.pdf"):
            self.assertIsNone(registry.parse_manual_filename(name), name)

    def test_unknown_manual_and_extension_are_rejected(self):
        with self.assertRaises(ValueError):
            registry.manual_filename("nope", "en", "pdf")
        with self.assertRaises(ValueError):
            registry.manual_filename("help", "en", "txt")
        with self.assertRaises(ValueError):
            registry.manual_filename("help", "kr", "pdf")

    def test_every_manual_has_a_title(self):
        for manual_key in cl.manual_keys():
            self.assertTrue(registry.manual_title(manual_key))

    def test_reference_tag_is_supported(self):
        self.assertIn(registry.REFERENCE_TAG, registry.SUPPORTED_DOCUMENT_TAGS)


class FigureTests(unittest.TestCase):
    def test_ids_are_contiguous_and_well_formed(self):
        ids = [f["id"] for f in figures.FIGURES]
        self.assertEqual(ids, [f"FIG-{i:02d}" for i in range(len(ids))])

    def test_number_is_derived_from_id(self):
        self.assertEqual(figures.figure_number("FIG-00"), 0)
        self.assertEqual(figures.figure_number("FIG-09"), 9)
        with self.assertRaises(ValueError):
            figures.figure_number("FIG-7")

    def test_catalog_has_the_media_player_and_video_settings_figures(self):
        by_id = {f["id"]: f for f in figures.FIGURES}
        self.assertEqual(by_id["FIG-08"]["filename"], "fig-08-media-player.png")
        self.assertEqual(by_id["FIG-09"]["filename"], "fig-09-recorder-video-settings.png")
        self.assertIn("Media Player", by_id["FIG-08"]["caption"])
        self.assertIn("Video Settings", by_id["FIG-09"]["caption"])

    def test_filenames_are_unique(self):
        names = [f["filename"] for f in figures.FIGURES]
        self.assertEqual(len(names), len(set(names)))

    def test_every_figure_declares_capture_steps(self):
        # Without these, a screenshot cannot be reproduced consistently.
        for entry in figures.FIGURES:
            self.assertTrue(entry["capture_steps"].strip(), entry["id"])
            self.assertTrue(entry["caption"].strip(), entry["id"])

    def test_unknown_id_raises_but_missing_file_does_not(self):
        with self.assertRaises(KeyError):
            figures.resolve_figure_path("FIG-99")
        # Pointing at an empty directory must return None, not raise: a shot
        # that has not been taken should render a placeholder, not fail a build.
        self.assertIsNone(
            figures.resolve_figure_path("FIG-00", Path(__file__).parent / "_nonexistent")
        )

    def test_shotlist_mentions_every_figure(self):
        shotlist = (SOURCE_DIR.parent / "screenshots" / "SHOTLIST.md").read_text(
            encoding="utf-8")
        for entry in figures.FIGURES:
            self.assertIn(entry["id"], shotlist)
            self.assertIn(entry["filename"], shotlist)


class ContentTests(unittest.TestCase):
    TOOL_TAB_LABELS = (
        "Conversion Log", "Converted Files", "Video Inspection Tool", "PC Report",
        "Lossless Editor", "Multi-Source Recorder", "Media Player",
    )

    def _chapter(self, manual_key, chapter_id):
        for chapter in cl.load_manual(manual_key, "en"):
            if chapter["id"] == chapter_id:
                return chapter
        self.fail(f"{manual_key} has no chapter {chapter_id!r}")

    def _chapter_text(self, manual_key, chapter_id):
        parts = []
        for block in self._chapter(manual_key, chapter_id)["blocks"]:
            if block["type"] == "para":
                parts.append(block["text"])
            elif block["type"] in ("steps", "note", "code"):
                parts.extend(block.get("items", block.get("lines", [])))
            elif block["type"] == "table":
                parts.extend(cell for row in block["rows"] for cell in row)
        return "\n".join(parts)

    def test_help_covers_every_tool_tab(self):
        text = self._chapter_text("help", "main-window")
        for label in self.TOOL_TAB_LABELS:
            self.assertIn(label, text, label)

    def test_help_settings_chapter_names_every_settings_tab(self):
        text = self._chapter_text("help", "conversion-settings")
        for tab in ("General", "Folders", "Deletion", "Format", "Time", "Tools"):
            self.assertIn(tab, text, tab)

    def test_help_has_time_restrictions_and_converted_files_chapters(self):
        ids = [c["id"] for c in cl.load_manual("help", "en")]
        self.assertIn("time-restrictions", ids)
        self.assertIn("converted-files", ids)

    def test_help_has_a_chapter_per_tool_tab(self):
        ids = [c["id"] for c in cl.load_manual("help", "en")]
        for chapter_id in ("converted-files", "media-inspection", "pc-report",
                           "lossless-editor", "multi-source-recorder", "media-player"):
            self.assertIn(chapter_id, ids)

    def test_help_has_language_and_updates_chapters(self):
        ids = [c["id"] for c in cl.load_manual("help", "en")]
        self.assertIn("language", ids)
        self.assertIn("updates-and-logs", ids)
        text = self._chapter_text("help", "language")
        for name in ("English", "Nederlands", "Simplified Chinese"):
            self.assertIn(name, text, name)

    def test_quickstart_has_record_and_review_chapters(self):
        ids = [c["id"] for c in cl.load_manual("quickstart", "en")]
        self.assertEqual(ids[:4], ["before-you-start", "first-conversion",
                                   "record-a-webcam", "review-a-recording"])
        record = self._chapter_text("quickstart", "record-a-webcam")
        for needle in ("Video Settings", "Start Recording", "Stop Recording"):
            self.assertIn(needle, record, needle)
        review = self._chapter_text("quickstart", "review-a-recording")
        for needle in ("Play in Media Player", "Space", "F"):
            self.assertIn(needle, review, needle)

    def test_troubleshooting_covers_recorder_and_player(self):
        text = self._chapter_text("help", "troubleshooting")
        for needle in ("Could not find video device", "(not found)",
                       "Windows cannot play this file", "Settings", "NVC_LOG_LEVEL"):
            self.assertIn(needle, text, needle)

    def test_glossary_defines_the_new_terms(self):
        import importlib

        package = cl.locale_package("en")
        glossary = importlib.import_module(f"locales.{package}.glossary")
        terms = {row[0] for row in glossary.GLOSSARY_ROWS}
        for term in ("Media Foundation", "GenICam", "Preset", "Sync offset",
                     "Frame step", "Playlist", "Administrator (elevation)", "Tool tab"):
            self.assertIn(term, terms, term)

    def test_recorder_chapter_covers_video_settings_and_presets(self):
        text = self._chapter_text("help", "multi-source-recorder")
        for needle in (
            "Video Settings",
            "RTSP/IP Camera",
            "Refresh USB devices",
            "Separate videos",
            "Combined grid",
            "Save as",
            "(not found)",
            "Sync offset",
            "Start Recording",
        ):
            self.assertIn(needle, text, needle)
        fig_ids = [
            block["fig_id"]
            for block in self._chapter("help", "multi-source-recorder")["blocks"]
            if block["type"] == "figure"
        ]
        self.assertEqual(fig_ids, ["FIG-07", "FIG-09"])
        for forbidden in ("Output quality", "Timer settings", "Time format"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_pc_report_chapter_lists_every_section_in_registry_order(self):
        import importlib

        pc_registry = importlib.import_module("pc_report.registry")
        titles = [pc_registry.by_key(key).title for key in pc_registry.ORDER]
        text = self._chapter_text("help", "pc-report")
        for title in titles:
            self.assertIn(title, text, title)
        self.assertNotIn("redaction enabled", text.lower())

    def test_every_supported_locale_validates(self):
        cl.validate_all(registry.SUPPORTED_DOCUMENT_TAGS)

    def test_every_manual_loads_and_is_non_empty(self):
        for manual_key in cl.manual_keys():
            chapters = cl.load_manual(manual_key, "en")
            self.assertTrue(chapters, manual_key)
            for chapter in chapters:
                self.assertTrue(chapter["id"])
                self.assertTrue(chapter["title"])

    def test_unknown_manual_or_locale_raises(self):
        with self.assertRaises(ValueError):
            cl.load_manual("nope", "en")
        with self.assertRaises(ValueError):
            cl.load_manual("help", "kr")

    def test_all_figure_references_are_known(self):
        for manual_key in cl.manual_keys():
            for chapter in cl.load_manual(manual_key, "en"):
                for block in chapter["blocks"]:
                    if block["type"] == "figure":
                        self.assertIn(block["fig_id"], figures.KNOWN_FIGURE_IDS)

    def test_validator_rejects_unknown_block_type(self):
        self._assert_rejects([{"id": "a", "title": "A",
                               "blocks": [{"type": "bogus"}]}])

    def test_validator_rejects_unknown_figure(self):
        self._assert_rejects([{"id": "a", "title": "A",
                               "blocks": [{"type": "figure", "fig_id": "FIG-99"}]}])

    def test_validator_rejects_ragged_table(self):
        self._assert_rejects([{"id": "a", "title": "A", "blocks": [
            {"type": "table", "headers": ("x", "y"), "rows": [("one",)]}]}])

    def test_validator_rejects_duplicate_chapter_ids(self):
        self._assert_rejects([{"id": "a", "title": "A", "blocks": []},
                              {"id": "a", "title": "B", "blocks": []}])

    def test_validator_rejects_chapter_without_id(self):
        self._assert_rejects([{"title": "A", "blocks": []}])

    def _assert_rejects(self, chapters):
        original = cl.load_manual
        cl.load_manual = lambda m, loc="en": chapters
        try:
            with self.assertRaises(ValueError):
                cl.validate_bundle("help", "en")
        finally:
            cl.load_manual = original

    def test_block_shape_signature_ignores_wording(self):
        a = {"type": "para", "text": "hello"}
        b = {"type": "para", "text": "totally different words"}
        self.assertEqual(cl.block_shape_signature(a), cl.block_shape_signature(b))

    def test_block_shape_signature_notices_dropped_item(self):
        a = {"type": "steps", "items": ["one", "two", "three"]}
        b = {"type": "steps", "items": ["one", "two"]}
        self.assertNotEqual(cl.block_shape_signature(a), cl.block_shape_signature(b))

    def test_block_shape_signature_notices_swapped_figure(self):
        a = {"type": "figure", "fig_id": "FIG-00"}
        b = {"type": "figure", "fig_id": "FIG-01"}
        self.assertNotEqual(cl.block_shape_signature(a), cl.block_shape_signature(b))


class NavigationTests(unittest.TestCase):
    def test_anchor_comes_from_id_not_title(self):
        a = {"id": "same", "title": "One Title"}
        b = {"id": "same", "title": "A Completely Different Title"}
        self.assertEqual(nav.chapter_destination(a), nav.chapter_destination(b))

    def test_chapter_without_id_raises(self):
        with self.assertRaises(ValueError):
            nav.chapter_destination({"title": "No id"})

    def test_glossary_is_appended_last(self):
        chapters = cl.load_manual("help", "en")
        result = nav.chapters_with_glossary(chapters, "en")
        self.assertEqual(result[-1]["id"], nav.GLOSSARY_CHAPTER_ID)
        self.assertEqual(len(result), len(chapters) + 1)

    def test_existing_glossary_is_moved_not_duplicated(self):
        chapters = [{"id": "glossary", "title": "G", "blocks": []},
                    {"id": "intro", "title": "I", "blocks": []}]
        result = nav.chapters_with_glossary(chapters, "en")
        self.assertEqual([c["id"] for c in result], ["intro", "glossary"])

    def test_duplicate_ids_raise(self):
        with self.assertRaises(ValueError):
            nav.chapters_with_glossary(
                [{"id": "x", "title": "A", "blocks": []},
                 {"id": "x", "title": "B", "blocks": []}], "en")

    def test_word_bookmark_names_are_legal(self):
        for chapter in nav.chapters_with_glossary(cl.load_manual("help", "en"), "en"):
            name = nav.word_bookmark_name(nav.chapter_destination(chapter))
            self.assertLessEqual(len(name), 40, name)
            self.assertTrue(name[0].isalpha(), name)
            self.assertTrue(all(c.isalnum() or c == "_" for c in name), name)

    def test_long_anchors_stay_unique_after_truncation(self):
        a = nav.word_bookmark_name("chapter-" + "x" * 80 + "-one")
        b = nav.word_bookmark_name("chapter-" + "x" * 80 + "-two")
        self.assertNotEqual(a, b)
        self.assertLessEqual(len(a), 40)


@unittest.skipUnless(HAS_DOCX, "python-docx not installed")
class DocxBuildTests(unittest.TestCase):
    def test_builds_with_a_heading_and_bookmark_per_chapter(self):
        import tempfile

        from docx import Document
        from docx_builder import build_docx

        chapters = cl.load_manual("help", "en")
        expected = len(nav.chapters_with_glossary(chapters, "en"))
        with tempfile.TemporaryDirectory() as tmp:
            out = build_docx(Path(tmp) / "h.docx", doc_title="Help",
                             chapters=chapters, version="9.9.9", document_tag="en")
            doc = Document(str(out))
            headings = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
            self.assertEqual(len(headings), expected)
            xml = doc.element.xml
            self.assertEqual(xml.count("bookmarkStart"), expected)
            self.assertIn("TOC", xml)
            # "Contents" must not itself be a Heading 1, or the TOC field
            # (scoped \o "1-1") lists the contents inside the contents.
            self.assertNotIn("Contents", headings)

    def test_unknown_block_type_raises(self):
        import tempfile

        from docx_builder import build_docx
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_docx(Path(tmp) / "x.docx", doc_title="Help", version="1",
                           document_tag="en",
                           chapters=[{"id": "a", "title": "A",
                                      "blocks": [{"type": "bogus"}]}])


@unittest.skipUnless(HAS_REPORTLAB, "reportlab not installed")
class PdfBuildTests(unittest.TestCase):
    @unittest.skipUnless(HAS_PDF_READER, "no PDF reader installed")
    def test_toc_page_numbers_match_the_real_pages(self):
        """The point of the two-pass render. Regression-guards an off-by-one."""
        import re
        import tempfile

        from pdf_builder import build_pdf
        try:
            from pypdf import PdfReader
        except ImportError:  # pragma: no cover - older environments
            from PyPDF2 import PdfReader

        chapters = cl.load_manual("help", "en")
        titles = [c["title"] for c in nav.chapters_with_glossary(chapters, "en")]

        with tempfile.TemporaryDirectory() as tmp:
            out = build_pdf(Path(tmp) / "h.pdf", doc_title="Help",
                            chapters=chapters, version="9.9.9", document_tag="en")
            reader = PdfReader(str(out))
            toc_text = reader.pages[1].extract_text()

            lines = [ln.strip() for ln in toc_text.splitlines() if ln.strip()]
            claimed: dict[str, int] = {}
            for i, line in enumerate(lines):
                if line in titles:
                    for j in range(i + 1, min(i + 4, len(lines))):
                        if lines[j].isdigit():
                            claimed[line] = int(lines[j])
                            break

            self.assertEqual(set(claimed), set(titles),
                             "every chapter should appear in the contents")
            for title, page_no in claimed.items():
                text = reader.pages[page_no - 1].extract_text()
                head = re.sub(r"\s+", " ", text[:200]).lower()
                self.assertIn(title.split()[0].lower(), head,
                              f"contents says {title!r} is on page {page_no}")

    def test_unknown_block_type_raises(self):
        import tempfile

        from pdf_builder import build_pdf
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_pdf(Path(tmp) / "x.pdf", doc_title="Help", version="1",
                          document_tag="en",
                          chapters=[{"id": "a", "title": "A",
                                     "blocks": [{"type": "bogus"}]}])

    def test_long_unbroken_token_still_wraps(self):
        from pdf_builder import BODY_FONT, BODY_SIZE, _wrap
        lines = _wrap("x" * 400, BODY_FONT, BODY_SIZE, 200)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(lines))


class BrandColourTests(unittest.TestCase):
    """The manuals take their accent from the app's theme.

    Each builder carries a hardcoded fallback so the docs can build without
    PyQt5 installed. That fallback is the thing that can silently drift, so it
    is asserted against ui/theme.py here.
    """

    @unittest.skipUnless(_has("PyQt5"), "PyQt5 not installed")
    def test_builders_resolve_the_theme_colours(self):
        import docx_builder
        import pdf_builder

        from ui.theme import IDLE
        for module in (pdf_builder, docx_builder):
            self.assertEqual(module._HEADING, IDLE.text_primary, module.__name__)
            self.assertEqual(module._BODY, IDLE.text_body, module.__name__)
            self.assertEqual(module._MUTED, IDLE.text_muted, module.__name__)

    @unittest.skipUnless(_has("PyQt5"), "PyQt5 not installed")
    def test_hardcoded_fallbacks_match_the_theme(self):
        """Read the literal fallbacks out of the source and compare."""
        import re

        from ui.theme import IDLE
        expected = (IDLE.accent, IDLE.text_primary, IDLE.text_body, IDLE.text_muted)
        for name in ("pdf_builder.py", "docx_builder.py"):
            text = (SOURCE_DIR / name).read_text(encoding="utf-8")
            match = re.search(r'return "#[0-9a-fA-F]{6}", "#[0-9a-fA-F]{6}", '
                              r'"#[0-9a-fA-F]{6}", "#[0-9a-fA-F]{6}"', text)
            self.assertIsNotNone(match, f"{name}: fallback tuple not found")
            found = tuple(re.findall(r"#[0-9a-fA-F]{6}", match.group(0)))
            self.assertEqual(found, expected,
                             f"{name}'s fallback has drifted from ui/theme.py")


class ShippedOutputTests(unittest.TestCase):
    def test_generated_files_are_named_by_the_registry(self):
        """Whatever is committed under docs/help must match the grammar."""
        docs_dir = SOURCE_DIR.parent
        shipped = [p.name for p in docs_dir.iterdir()
                   if p.suffix in (".pdf", ".docx")]
        self.assertTrue(shipped, "no generated documents found; run build_help_docs.py")
        for name in shipped:
            self.assertIsNotNone(registry.parse_manual_filename(name),
                                 f"{name} does not match the filename grammar")

    def test_readme_names_the_current_doc_version(self):
        """The README's filename table must follow DOC_VERSION, not lag behind it."""
        readme = (SOURCE_DIR.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn(registry.manual_filename("help", "en", "pdf"), readme)
        self.assertIn(registry.manual_filename("quickstart", "en", "pdf"), readme)


if __name__ == "__main__":
    unittest.main()
