import os
import tempfile
import unittest
from unittest import mock

from PyQt5.QtWidgets import QApplication

import ui.main_window as main_window_module
from ui.main_window import VideoConverterApp


class PlayInMediaPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_play_requested_shows_tab_for_session_and_loads_selected_panel(self):
        window = VideoConverterApp()
        window.settings.setdefault("visible_tool_tabs", {})["media_player"] = False
        window.apply_tool_tab_visibility()
        index = window.tabs.indexOf(window.media_player_tab_scroll)
        self.assertFalse(window.tabs.isTabVisible(index))
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name

        def cleanup():
            window.shutdown()
            if os.path.exists(path):
                os.remove(path)

        self.addCleanup(cleanup)
        with mock.patch.object(main_window_module, "save_settings") as save:
            window.converted_files_widget.play_requested.emit(path)
            self.assertFalse(save.called)
        self.assertTrue(window.tabs.isTabVisible(index))
        self.assertEqual(window.tabs.currentIndex(), index)
        widget = window.media_player_widget
        self.assertIsNotNone(widget)
        self.assertEqual(widget.selected_panel()._media_path, path)
        self.assertFalse(window.settings["visible_tool_tabs"]["media_player"])

    def test_inspect_requested_opens_the_players_inspect_dock_on_that_file(self):
        window = VideoConverterApp()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name

        def cleanup():
            window.shutdown()
            if os.path.exists(path):
                os.remove(path)

        self.addCleanup(cleanup)
        widget = window._ensure_media_player_widget()
        inspected = []
        widget.inspect_dock.inspect_path = lambda p: inspected.append(p)
        window.converted_files_widget.inspect_requested.emit(path)
        self.assertEqual(window.tabs.currentWidget(), window.media_player_tab_scroll)
        self.assertTrue(widget.inspect_btn.isChecked())
        self.assertEqual(inspected[-1], path)
        self.assertEqual(widget.selected_panel()._media_path, path)

    def test_the_sidebar_preview_follows_the_players_selected_clip(self):
        window = VideoConverterApp()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name

        def cleanup():
            window.shutdown()
            if os.path.exists(path):
                os.remove(path)

        self.addCleanup(cleanup)
        previewed = []
        window.preview_file = lambda p: previewed.append(p)
        widget = window._ensure_media_player_widget()
        widget.selected_panel().load_media(path)
        self.assertEqual(previewed, [path])
        widget.selected_panel().clear_media()
        self.assertEqual(previewed, [path])          # nothing to preview: left alone


class ConverterContextMenuWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        window = VideoConverterApp()
        self.addCleanup(window.shutdown)
        return window

    def test_the_footer_broom_clears_the_file_list_with_the_log(self):
        window = self._window()
        table = window.converted_files_widget
        table.add_queued_file("Session 1.mp4", r"C:\Videos")
        window.console_output.appendPlainText("converting...")
        window.clear_log_tab()
        self.assertEqual(table.table_widget.rowCount(), 0)
        self.assertEqual(window.console_output.toPlainText(), "")
        self.assertIn("file list", window.broom_label_log_tab.toolTip())

    def test_splitter_handles_are_transparent(self):
        # The default handle painted a grey band above the log and beside the
        # player's Inspect panel, which read as a stray background.
        window = self._window()
        self.assertIn("QSplitter::handle", window.styleSheet())
        rule = window.styleSheet().split("QSplitter::handle", 1)[1].split("}", 1)[0]
        self.assertIn("transparent", rule)

    def test_add_videos_opens_the_windows_file_picker(self):
        window = self._window()
        with mock.patch.object(window, "open_file_dialog") as picker:
            window.converted_files_widget.add_files_requested.emit()
        picker.assert_called_once_with()

    def test_monitor_folder_saves_the_source_folder_and_restarts_a_running_watch(self):
        window = self._window()
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(main_window_module, "save_settings"):
                window.converted_files_widget.monitor_folder_requested.emit(folder)
                self.assertEqual(os.path.normcase(window.source_folder), os.path.normcase(folder))
                self.assertEqual(window.settings["source_folder"], folder)
                # While monitoring, switching folders means stop + start on the new one.
                window.running = True
                calls = []
                window.stop_conversion = lambda: calls.append("stop")
                window.start_conversion = lambda: calls.append("start")
                window.converted_files_widget.monitor_folder_requested.emit(folder)
                self.assertEqual(calls, ["stop", "start"])

    def test_monitor_folder_with_no_path_asks_which_folder(self):
        window = self._window()
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(main_window_module.QFileDialog, "getExistingDirectory", return_value=folder), \
                mock.patch.object(main_window_module, "save_settings"):
            window.converted_files_widget.monitor_folder_requested.emit("")
            self.assertEqual(window.settings["source_folder"], folder)
        with mock.patch.object(main_window_module.QFileDialog, "getExistingDirectory", return_value=""), \
                mock.patch.object(main_window_module, "save_settings") as save:
            window.converted_files_widget.monitor_folder_requested.emit("")
            self.assertFalse(save.called)                # cancelled: nothing changes

    def test_open_in_routes_to_the_player_the_editor_or_the_system(self):
        window = self._window()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with mock.patch.object(window, "play_in_media_player") as play:
            window.converted_files_widget.open_in_requested.emit("media_player", path)
        play.assert_called_once_with(path)
        window.converted_files_widget.open_in_requested.emit("lossless_editor", path)
        self.assertEqual(window.lossless_editor_widget.input_edit.text(), path)
        self.assertEqual(window.tabs.currentWidget(), window.lossless_editor_tab_scroll)
        with mock.patch.object(main_window_module.QDesktopServices, "openUrl") as open_url:
            window.converted_files_widget.open_in_requested.emit("system", path)
        self.assertTrue(open_url.called)
        self.assertEqual(open_url.call_args[0][0].toLocalFile(), path.replace("\\", "/"))
