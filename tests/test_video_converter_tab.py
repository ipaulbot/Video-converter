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
        # Since 2026-09-26 the table has no Clear button of its own: the broom
        # empties the list together with the log.
        self.assertEqual(window.converted_files_widget.table_widget.rowCount(), 0)

    def test_game_takes_the_whole_card_and_gives_it_back(self):
        window = self._window()
        window.hide_files_table_for_game()
        self.assertTrue(window.converted_files_widget.isHidden())
        window.restore_files_table_after_game()
        self.assertFalse(window.converted_files_widget.isHidden())

    def test_game_borrows_the_tab_header_and_returns_it(self):
        window = self._window()
        header = window.converter_header
        window.launch_ballbuster_game()
        try:
            self.assertEqual(header.glyph_name, "balls")
            self.assertEqual(header.title_label.text(), "BallBuster XT")
            self.assertIn("balls", header.description_label.text().lower())
        finally:
            window.restore_log_view()
        self.assertEqual(header.glyph_name, "convert")
        self.assertEqual(header.title_label.text(), "Video Converter")
        self.assertTrue(header.description_label.text().startswith("Drop files"))


if __name__ == "__main__":
    unittest.main()
