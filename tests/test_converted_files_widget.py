import shutil
import tempfile
import unittest

from PyQt5.QtCore import Qt
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
