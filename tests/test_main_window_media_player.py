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
