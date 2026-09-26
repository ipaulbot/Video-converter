import shutil
import tempfile
import unittest

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication

from ui.converted_files_widget import ConvertedFilesWidget


class ConvertedFilesPlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _widget_with_row(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        # add_converted_file writes a per-file log; keep it out of the real AppData logs folder.
        log_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(log_dir, ignore_errors=True))
        widget.set_log_folder(log_dir)
        widget.add_converted_file(
            "clip.mp4",
            {"output_file": "C:\\Videos\\Out\\clip.mp4"},
            "C:\\Videos\\Out",
            True,
        )
        return widget

    def test_play_button_hidden_until_a_row_is_selected(self):
        widget = self._widget_with_row()
        widget.show()
        self.assertFalse(widget.play_button.isVisibleTo(widget))
        widget.table_widget.selectRow(0)
        self.assertTrue(widget.play_button.isVisibleTo(widget))
        widget.table_widget.clearSelection()
        self.assertFalse(widget.play_button.isVisibleTo(widget))

    def test_play_button_emits_selected_path(self):
        widget = self._widget_with_row()
        widget.table_widget.selectRow(0)
        received = []
        widget.play_requested.connect(received.append)
        widget.play_button.click()
        self.assertEqual(
            received,
            [widget.table_widget.item(0, 0).data(Qt.UserRole)],
        )
        self.assertTrue(received[0].endswith("clip.mp4"))

    def test_inspect_button_follows_the_selection_and_emits_the_path(self):
        widget = self._widget_with_row()
        widget.show()
        self.assertFalse(widget.inspect_button.isVisibleTo(widget))
        widget.table_widget.selectRow(0)
        self.assertTrue(widget.inspect_button.isVisibleTo(widget))
        received = []
        widget.inspect_requested.connect(received.append)
        widget.inspect_button.click()
        self.assertEqual(received, [widget.table_widget.item(0, 0).data(Qt.UserRole)])


def _action(menu, text):
    for action in menu.actions():
        if action.text() == text:
            return action
        if action.menu() is not None:
            found = _action(action.menu(), text)
            if found is not None:
                return found
    return None


class ContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _widget_with_row(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        log_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(log_dir, ignore_errors=True))
        widget.set_log_folder(log_dir)
        widget.add_converted_file(
            "clip.mp4", {"output_file": "C:\\Videos\\Out\\clip.mp4"}, "C:\\Videos\\Out", True,
        )
        return widget

    def test_empty_space_offers_add_and_monitor_only(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        menu = widget.build_context_menu(QPoint(5, 5))
        texts = [a.text() for a in menu.actions() if not a.isSeparator()]
        self.assertEqual(texts, ["Add videos to convert...", "Monitor a folder..."])
        received = []
        widget.add_files_requested.connect(lambda: received.append("add"))
        widget.monitor_folder_requested.connect(received.append)
        _action(menu, "Add videos to convert...").trigger()
        _action(menu, "Monitor a folder...").trigger()
        self.assertEqual(received, ["add", ""])      # "" = let the window ask which folder

    def test_a_row_adds_monitor_this_folder_and_open_in(self):
        widget = self._widget_with_row()
        rect = widget.table_widget.visualItemRect(widget.table_widget.item(0, 0))
        menu = widget.build_context_menu(rect.center())
        texts = [a.text() for a in menu.actions() if not a.isSeparator()]
        self.assertIn("Monitor this file's folder", texts)
        self.assertIn("Open in", texts)
        self.assertIn("Play in Media Player", texts)
        submenu = _action(menu, "Open in").menu()
        self.assertEqual(
            [a.text() for a in submenu.actions()],
            ["Media Player", "Lossless Editor", "Default app"],
        )
        received = []
        widget.monitor_folder_requested.connect(received.append)
        widget.open_in_requested.connect(lambda target, path: received.append((target, path)))
        _action(menu, "Monitor this file's folder").trigger()
        _action(submenu, "Lossless Editor").trigger()
        _action(submenu, "Default app").trigger()
        _action(submenu, "Media Player").trigger()
        self.assertEqual(received, [
            "C:\\Videos\\Out",
            ("lossless_editor", "C:\\Videos\\Out\\clip.mp4"),
            ("system", "C:\\Videos\\Out\\clip.mp4"),
            ("media_player", "C:\\Videos\\Out\\clip.mp4"),
        ])


class ClearButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_clear_button_tracks_row_count(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)

        self.assertTrue(widget.clear_button.isHidden())
        widget.add_queued_file("Session 1.mp4", r"C:\Videos")
        self.assertFalse(widget.clear_button.isHidden())
        widget.clear_table()
        self.assertTrue(widget.clear_button.isHidden())
