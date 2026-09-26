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
        for name in ("convert", "pc", "scissors", "record", "player"):
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

    def test_a_layer_can_sit_under_the_glyph(self):
        header = TabHeader("pc", "PC Report")
        self.addCleanup(header.close)
        heart = QLabel()
        header.add_layer_under_glyph(heart)
        self.assertIs(heart.parentWidget(), header)
        self.assertEqual(header.glyph_stack.count(), 2)
