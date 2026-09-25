import unittest

from PyQt5.QtWidgets import QToolButton

from ui.lossless_editor_widget import LosslessEditorWidget


class LosslessEditorLayoutTests(unittest.TestCase):
    def setUp(self):
        self.widget = LosslessEditorWidget(["mp4", "mkv"])

    def test_tool_buttons_are_compact_and_opt_out_of_global_style(self):
        for button in (
            self.widget.trim_btn,
            self.widget.remux_btn,
            self.widget.extract_audio_btn,
            self.widget.remove_audio_btn,
            self.widget.merge_btn,
        ):
            self.assertTrue(button.property("skipGlobalStyle"), button.text())
            self.assertLessEqual(button.sizeHint().height(), 28, button.text())
        self.assertEqual(self.widget.trim_btn.text(), "Trim")
        self.assertEqual(self.widget.extract_audio_btn.text(), "Extract audio")
        self.assertEqual(self.widget.remove_audio_btn.text(), "Remove audio")
        self.assertEqual(self.widget.merge_btn.text(), "Merge")

    def test_browse_is_a_folder_glyph_button(self):
        self.assertIsInstance(self.widget.browse_btn, QToolButton)
        self.assertEqual(self.widget.browse_btn.property("glyph"), "folder_open")
        self.assertEqual(self.widget.browse_btn.toolTip(), "Choose a source media file")
        self.assertFalse(self.widget.browse_btn.icon().isNull())

    def test_merge_list_actions_are_icon_buttons_with_tooltips(self):
        self.assertIsInstance(self.widget.add_merge_btn, QToolButton)
        self.assertIsInstance(self.widget.clear_merge_btn, QToolButton)
        self.assertEqual(
            self.widget.add_merge_btn.toolTip(), "Add files to the merge list"
        )
        self.assertEqual(self.widget.clear_merge_btn.toolTip(), "Clear the merge list")

    def test_update_button_style_keeps_compact_tier(self):
        self.widget.update_button_style("QPushButton { min-height: 32px; }")
        self.assertNotIn("32px", self.widget.trim_btn.styleSheet())
        self.assertIn("min-height: 24px", self.widget.trim_btn.styleSheet())
