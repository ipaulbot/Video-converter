"""The merged Video Converter tab: Converted Files table above the conversion log."""

import unittest

from PyQt5.QtWidgets import QApplication, QSplitter

from ui.main_window import VideoConverterApp


class VideoConverterTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        window = VideoConverterApp()
        self.addCleanup(window.shutdown)
        return window

    def test_tab_is_titled_video_converter_and_replaces_the_two_old_tabs(self):
        window = self._window()
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        self.assertIn("Video Converter", titles)
        self.assertNotIn("Conversion Log", titles)
        self.assertNotIn("Converted Files", titles)
        self.assertNotIn("Video Inspection Tool", titles)
        self.assertEqual(window.tabs.indexOf(window.converter_tab_scroll), 0)
        self.assertIs(window.tool_tab_widgets["video_converter"], window.converter_tab_scroll)

    def test_files_table_sits_above_the_log_in_a_splitter(self):
        window = self._window()
        splitter = window.converter_splitter
        self.assertIsInstance(splitter, QSplitter)
        self.assertEqual(splitter.count(), 2)
        self.assertIs(splitter.widget(0), window.converted_files_widget)
        self.assertTrue(splitter.widget(1).isAncestorOf(window.log_container))
        self.assertFalse(splitter.childrenCollapsible())

    def test_the_merged_tab_has_one_footer_whose_broom_clears_the_log(self):
        window = self._window()
        self.assertFalse(hasattr(window, "status_label_converted_tab"))
        self.assertFalse(hasattr(window, "status_label_inspection_tab"))
        window.console_output.appendPlainText("hello")
        window.converted_files_widget.add_queued_file("clip.mp4", "C:/Videos")
        window.clear_log_tab()
        self.assertEqual(window.console_output.toPlainText(), "")
        # The table has its own Clear button; the broom leaves it alone.
        self.assertEqual(window.converted_files_widget.table_widget.rowCount(), 1)

    def test_game_takes_the_whole_card_and_gives_it_back(self):
        window = self._window()
        window.hide_files_table_for_game()
        self.assertTrue(window.converted_files_widget.isHidden())
        window.restore_files_table_after_game()
        self.assertFalse(window.converted_files_widget.isHidden())


if __name__ == "__main__":
    unittest.main()
