import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication, QLabel

from ui import theme
from ui.glyph_icons import GLYPHS, glyph_icon
from ui.tab_header import TabHeader


class TabHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_header_is_glyph_then_title_then_description(self):
        header = TabHeader("convert", "Video Converter", "Watches a folder.")
        self.addCleanup(header.close)
        self.assertEqual(header.glyph_label.width(), TabHeader.GLYPH_PX)
        self.assertFalse(header.glyph_label.pixmap().isNull())
        self.assertEqual(header.title_label.text(), "Video Converter")
        self.assertEqual(header.description_label.text(), "Watches a folder.")
        self.assertEqual(header.title_label.styleSheet(), theme.tab_title_style())
        self.assertEqual(header.description_label.styleSheet(), theme.tab_description_style())

    def test_empty_description_hides_its_line(self):
        header = TabHeader("pc", "PC Report")
        self.addCleanup(header.close)
        self.assertTrue(header.description_label.isHidden())
        header.set_description("Now with text")
        self.assertFalse(header.description_label.isHidden())

    def test_every_tab_glyph_paints(self):
        for name in ("convert", "pc", "scissors", "record", "player", "balls"):
            self.assertIn(name, GLYPHS)
            icon = glyph_icon(name, "#43a296", TabHeader.GLYPH_PX)
            self.assertFalse(icon.pixmap(TabHeader.GLYPH_PX).isNull(), name)

    def test_reskin_follows_the_skin_accent(self):
        header = TabHeader("record", "Multi-Source Recorder")
        self.addCleanup(header.close)
        before = header.glyph_label.pixmap().toImage()
        fake = theme.skin().__class__(**{**theme.skin().__dict__, "accent": "#ff0000"})
        with patch.object(theme, "skin", return_value=fake):
            header.reskin()
        self.assertNotEqual(header.glyph_label.pixmap().toImage(), before)
        self.assertIn("#ff0000", header.title_label.styleSheet())

    def test_glyph_stays_at_the_top_when_the_description_wraps(self):
        # A long description wrapping to two lines used to push the centred
        # glyph down, so that tab's glyph sat lower than every other tab's.
        header = TabHeader("player", "Media Player", "word " * 60)
        header.move(-7000, -7000)
        header.resize(320, header.sizeHint().height())
        header.show()
        try:
            for _ in range(4):
                self.app.processEvents()
            self.assertGreater(header.description_label.height(), header.title_label.height() * 2)
            self.assertLessEqual(header.glyph_label.y(), header.title_label.y() + 1)
        finally:
            header.close()

    def test_set_heading_swaps_glyph_title_and_description_and_back(self):
        # The Video Converter tab lends its header to BallBuster while the
        # game runs, then takes it back.
        header = TabHeader("convert", "Video Converter", "Watches a folder.")
        self.addCleanup(header.close)
        before = header.glyph_label.pixmap().toImage()
        header.set_heading("balls", "BallBuster XT", "Pop balls.")
        self.assertEqual(header.glyph_name, "balls")
        self.assertEqual(header.title_label.text(), "BallBuster XT")
        self.assertEqual(header.description_label.text(), "Pop balls.")
        self.assertNotEqual(header.glyph_label.pixmap().toImage(), before)
        header.set_heading("convert", "Video Converter", "Watches a folder.")
        self.assertEqual(header.glyph_label.pixmap().toImage(), before)
        self.assertEqual(header.title_label.text(), "Video Converter")

    def test_a_layer_can_sit_under_the_glyph(self):
        header = TabHeader("pc", "PC Report")
        self.addCleanup(header.close)
        heart = QLabel()
        header.add_layer_under_glyph(heart)
        self.assertIs(heart.parentWidget(), header)
        self.assertEqual(header.glyph_stack.count(), 2)
