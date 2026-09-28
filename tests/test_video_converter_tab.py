"""The merged Video Converter tab: Converted Files table above the conversion log."""

import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QSplitter

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

    def test_ballbuster_banner_lines_do_not_wrap_in_the_narrower_log(self):
        # Since the settings table sits beside the log, the compact log is
        # ~490 px wide and the 104-column banner at Courier 7 pt (520 px)
        # wrapped every row onto a second line. The banner now hides the
        # table for the intro (the game hides it anyway) and picks a font
        # size that fits the viewport.
        window = self._window()
        window.set_window_mode("compact", persist=False)
        window.tabs.setCurrentWidget(window.converter_tab_scroll)
        window.move(-7000, -7000)
        window.show()
        try:
            for _ in range(6):
                self.app.processEvents()
            lines = ["#" * 103] * 6
            with patch("time.sleep"):
                window._append_ballbuster_banner(lines)
            for _ in range(6):
                self.app.processEvents()
            self.assertTrue(window.settings_table_box.isHidden())
            doc = window.console_output.document()
            block = doc.begin()
            wrapped = []
            while block.isValid():
                if block.text().startswith(">###"):
                    wrapped.append(block.layout().lineCount())
                block = block.next()
            self.assertEqual(len(wrapped), 18)  # the banner scrolls past three times
            self.assertEqual(set(wrapped), {1})
        finally:
            window.hide()

    def test_banner_point_size_shrinks_only_when_the_line_will_not_fit(self):
        window = self._window()
        line = ">" + "#" * 103
        self.assertEqual(window._banner_point_size(line, 2000), 7.0)
        small = window._banner_point_size(line, 300)
        self.assertLess(small, 7.0)
        self.assertGreaterEqual(small, 4.0)

    def test_game_gets_sounds_that_follow_the_setting_and_auto_mute_while_converting(self):
        window = self._window()
        window.settings["game_sound"] = False
        window.tabs.setCurrentWidget(window.converter_tab_scroll)
        with patch("ui.main_window.save_settings") as save:
            window.launch_ballbuster_game()
            try:
                game = window.ballbuster_widget
                self.assertIsNotNone(game.sounds)
                self.assertFalse(game.sounds.enabled)
                game.toggle_sound()
                self.assertTrue(window.settings["game_sound"])
                save.assert_called()
                self.assertFalse(game.sounds.auto_muted)
                window.is_converting = True
                window.update_game_progress()
                self.assertTrue(game.sounds.auto_muted)
                window.is_converting = False
                window.update_game_progress()
                self.assertFalse(game.sounds.auto_muted)
            finally:
                window.restore_log_view()

    def test_game_borrows_the_sidebar_context_header_and_returns_it(self):
        window = self._window()
        header = window.context_header
        window.tabs.setCurrentWidget(window.converter_tab_scroll)
        window.launch_ballbuster_game()
        try:
            self.assertEqual(header.glyph_name, "balls")
            self.assertEqual(header.title_label.text(), "BallBuster XT")
            self.assertIn("balls", header.description_label.text().lower())
            # The game also takes the settings table's spot in the card.
            self.assertTrue(window.settings_table_box.isHidden())
        finally:
            window.restore_log_view()
        self.assertEqual(header.glyph_name, "convert")
        self.assertEqual(header.title_label.text(), "Video Converter")
        self.assertTrue(header.description_label.text().startswith("Drop files"))
        self.assertFalse(window.settings_table_box.isHidden())

    def test_game_progress_is_reported_in_the_converter_status_line(self):
        window = self._window()
        window.tabs.setCurrentWidget(window.converter_tab_scroll)
        window.launch_ballbuster_game()
        try:
            window.ballbuster_widget.score = 1234
            window.update_game_progress()
            text = window.status_label_log_tab.text()
            self.assertIn("1234", text)
            self.assertIn("Level", text)
        finally:
            window.restore_log_view()
        self.assertNotIn("1234", window.status_label_log_tab.text())

    # -- Current Video Settings table ------------------------------------
    def test_current_video_settings_is_a_table_beside_the_log(self):
        window = self._window()
        table = window.settings_table
        self.assertTrue(window.converter_tab.isAncestorOf(table))
        lower = window.converter_lower_splitter
        self.assertIsInstance(lower, QSplitter)
        self.assertEqual(lower.orientation(), Qt.Horizontal)
        self.assertTrue(lower.widget(0).isAncestorOf(window.log_container))
        self.assertTrue(lower.widget(1).isAncestorOf(table))
        self.assertIs(window.converter_splitter.widget(1), lower)
        self.assertEqual(table.columnCount(), 2)
        labels = [table.item(r, 0).text() for r in range(table.rowCount())]
        self.assertEqual(labels[:6], ["Format", "Video codec", "Audio codec", "Resolution", "Bitrate", "Frame rate"])
        self.assertEqual(table.editTriggers(), QAbstractItemView.NoEditTriggers)

    def test_settings_table_reflects_the_current_settings(self):
        window = self._window()
        window.settings.update({
            "output_format": "mkv", "video_codec": "H.265", "audio_codec": "Opus",
            "video_size": "1280x720", "video_bitrate": "3500k", "framerate": "30",
            "no_time_restrictions": False, "start_time": "08:00", "end_time": "17:00",
            "copy_only": True,
        })
        window.update_settings_display()
        table = window.settings_table
        values = {table.item(r, 0).text(): table.item(r, 1).text() for r in range(table.rowCount())}
        self.assertEqual(values["Format"], "MKV")
        self.assertEqual(values["Video codec"], "H.265")
        self.assertEqual(values["Audio codec"], "Opus")
        self.assertEqual(values["Resolution"], "1280x720")
        self.assertEqual(values["Bitrate"], "3500k")
        self.assertEqual(values["Frame rate"], "30 fps")
        self.assertEqual(values["Time window"], "08:00 - 17:00")
        self.assertEqual(values["Mode"], "Copy only")
        window.settings.update({"no_time_restrictions": True, "copy_only": False})
        window.update_settings_display()
        labels = [table.item(r, 0).text() for r in range(table.rowCount())]
        self.assertNotIn("Time window", labels)
        self.assertNotIn("Mode", labels)

    def test_clicking_the_settings_table_opens_the_format_settings(self):
        window = self._window()
        with patch.object(window, "show_settings") as show:
            window._settings_table_clicked(0, 1)
        show.assert_called_once_with(tab_index=3)


if __name__ == "__main__":
    unittest.main()
