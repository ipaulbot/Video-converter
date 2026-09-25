import unittest

from ui import glyph_icons


def _opaque_pixels(pixmap):
    image = pixmap.toImage()
    return sum(
        1
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 0
    )


class GlyphIconTests(unittest.TestCase):
    def test_every_glyph_renders_something(self):
        for name in glyph_icons.GLYPHS:
            pixmap = glyph_icons.glyph_icon(name, "#43a296", 20).pixmap(20, 20)
            self.assertFalse(pixmap.isNull(), name)
            self.assertGreater(_opaque_pixels(pixmap), 8, name)

    def test_unknown_glyph_raises(self):
        with self.assertRaises(KeyError):
            glyph_icons.glyph_icon("banana", "#000000")

    def test_make_icon_button_is_square_tool_button(self):
        button = glyph_icons.make_icon_button("play", "Play all", "#43a296", size=28)
        self.assertEqual(button.toolTip(), "Play all")
        self.assertFalse(button.icon().isNull())
        self.assertEqual(button.text(), "")
        self.assertEqual(button.property("glyph"), "play")
        self.assertIn("QToolButton", button.styleSheet())
