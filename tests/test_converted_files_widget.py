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
