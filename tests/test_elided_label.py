import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ui.elided_label import ElidedLabel


class ElidedLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_minimum_width_does_not_follow_the_text(self):
        label = ElidedLabel("Panel 1: Video_Video_1_20260925_202215_a_very_long_name.mp4")
        self.assertLessEqual(label.minimumSizeHint().width(), ElidedLabel.MIN_W)
        label.setText("x" * 300)
        self.assertLessEqual(label.minimumSizeHint().width(), ElidedLabel.MIN_W)

    def test_size_hint_still_asks_for_the_full_text_when_there_is_room(self):
        label = ElidedLabel("short")
        self.assertGreaterEqual(label.sizeHint().width(), label.fontMetrics().horizontalAdvance("short"))

    def test_text_is_elided_in_the_middle_to_the_available_width(self):
        label = ElidedLabel("Panel 1: Video_Video_1_20260925_202215.mp4")
        # Half the text's width (the offscreen platform's fallback font is wide).
        width = label.fontMetrics().horizontalAdvance(label.text()) // 2
        label.resize(width, 20)
        shown = label.elided_text()
        self.assertIn("…", shown)
        self.assertTrue(shown.startswith("Panel"), shown)
        self.assertTrue(shown.endswith(".mp4"), shown)
        self.assertLessEqual(label.fontMetrics().horizontalAdvance(shown), width)

    def test_full_text_is_the_tooltip_only_when_elided(self):
        label = ElidedLabel("short")
        label.resize(200, 20)
        self.assertEqual(label.toolTip(), "")
        label.setText("Panel 1: Video_Video_1_20260925_202215.mp4")
        label.resize(80, 20)
        self.assertEqual(label.toolTip(), "Panel 1: Video_Video_1_20260925_202215.mp4")

    def test_text_and_alignment_round_trip(self):
        label = ElidedLabel("a")
        label.setText("b")
        self.assertEqual(label.text(), "b")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.assertEqual(label.alignment(), Qt.AlignRight | Qt.AlignVCenter)


if __name__ == "__main__":
    unittest.main()
