import shutil
import tempfile
import unittest

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication, QToolButton

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


class ActionRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_no_clear_button_the_footer_broom_does_that(self):
        # The green Clear / Play / Inspect push buttons read as a second
        # toolbar next to the footer's icons; Clear is gone (the broom clears
        # the list with the log) and Play / Inspect are quiet glyph buttons.
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        self.assertFalse(hasattr(widget, "clear_button"))
        widget.add_queued_file("Session 1.mp4", r"C:\Videos")
        widget.clear_table()
        self.assertEqual(widget.table_widget.rowCount(), 0)

    def test_play_and_inspect_are_glyph_buttons(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        for button in (widget.play_button, widget.inspect_button):
            self.assertIsInstance(button, QToolButton)
            self.assertFalse(button.icon().isNull())
            self.assertEqual(button.text(), "")
            self.assertLessEqual(button.iconSize().width(), 24)
        self.assertEqual(widget.play_button.property("glyph"), "play")
        self.assertEqual(widget.inspect_button.property("glyph"), "inspect")

    def test_row_numbers_are_hidden_and_the_frame_style_stays_on_the_frame(self):
        # The container's `QFrame { border-radius }` rule leaked onto the
        # vertical header (a QFrame too) and drew a rounded box down the
        # row-number column; the header is hidden and the rule is scoped.
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        self.assertTrue(widget.table_widget.verticalHeader().isHidden())
        self.assertIn("#", widget.table_container.styleSheet().split("{")[0])
        self.assertNotEqual(widget.table_container.objectName(), "")
