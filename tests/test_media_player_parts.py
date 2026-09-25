import unittest

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QLabel, QToolButton

from ui.media_player_parts import FullscreenHost, PlaylistDock, UnsupportedOverlay
from ui.media_player_support import PlaylistModel


class FullscreenHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_take_and_release_round_trip_widgets_in_order(self):
        host = FullscreenHost()
        self.addCleanup(host.close)
        first, second = QLabel("a"), QLabel("b")
        host.take(first)
        host.take(second)
        self.assertIs(first.parent(), host)
        released = host.release()
        self.assertEqual(released, [first, second])
        self.assertIsNone(first.parent())

    def test_escape_and_f_request_exit(self):
        host = FullscreenHost()
        self.addCleanup(host.close)
        requests = []
        host.exit_requested.connect(lambda: requests.append(1))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_F, Qt.NoModifier))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.NoModifier))
        self.assertEqual(len(requests), 2)


class PlaylistDockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dock(self):
        dock = PlaylistDock()
        self.addCleanup(dock.close)
        model = PlaylistModel()
        dock.set_model(model, "Panel 1")
        return dock, model

    def test_dock_actions_are_icon_buttons_that_fit(self):
        dock = PlaylistDock()
        self.addCleanup(dock.close)
        for button, tip in (
            (dock.add_files_btn, "Add files..."),
            (dock.add_folder_btn, "Add folder..."),
            (dock.remove_btn, "Remove selected"),
            (dock.clear_btn, "Clear playlist"),
        ):
            self.assertIsInstance(button, QToolButton, tip)
            self.assertEqual(button.toolTip(), tip)
        self.assertLessEqual(dock.sizeHint().width(), 320)

    def test_refresh_lists_model_items_and_title(self):
        dock, model = self._dock()
        model.add(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
        dock.refresh()
        self.assertEqual(dock.list.count(), 2)
        self.assertEqual(dock.list.item(0).text(), "a.mp4")
        self.assertEqual(dock.list.item(0).toolTip(), "C:\\Videos\\a.mp4")
        self.assertIn("Panel 1", dock.title_label.text())

    def test_remove_selected_and_clear_update_model(self):
        dock, model = self._dock()
        dock.add_paths(["a", "b", "c"])
        dock.list.setCurrentRow(1)
        dock.remove_selected()
        self.assertEqual(model.items, ["a", "c"])
        dock.clear()
        self.assertEqual(model.items, [])
        self.assertEqual(dock.list.count(), 0)

    def test_double_click_emits_activate_with_path(self):
        dock, _model = self._dock()
        dock.add_paths(["C:\\Videos\\a.mp4"])
        activated = []
        dock.activate_requested.connect(activated.append)
        dock.list.itemDoubleClicked.emit(dock.list.item(0))
        self.assertEqual(activated, ["C:\\Videos\\a.mp4"])

    def test_rows_moved_reorders_model(self):
        dock, model = self._dock()
        dock.add_paths(["a", "b", "c"])
        dock._on_rows_moved(None, 0, 0, None, 3)
        self.assertEqual(model.items, ["b", "c", "a"])


class UnsupportedOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_show_message_progress_and_error(self):
        overlay = UnsupportedOverlay()
        self.addCleanup(overlay.close)
        overlay.show_message("Windows cannot play x in y.")
        self.assertEqual(
            overlay.message_label.text(), "Windows cannot play x in y."
        )
        self.assertTrue(overlay.convert_btn.isEnabled())
        overlay.show_progress(42)
        self.assertIn("42", overlay.progress_label.text())
        self.assertFalse(overlay.convert_btn.isEnabled())
        overlay.show_error("boom")
        self.assertIn("boom", overlay.progress_label.text())
        self.assertTrue(overlay.convert_btn.isEnabled())

    def test_buttons_emit_signals(self):
        overlay = UnsupportedOverlay()
        self.addCleanup(overlay.close)
        events = []
        overlay.convert_requested.connect(lambda: events.append("convert"))
        overlay.dismissed.connect(lambda: events.append("dismiss"))
        overlay.convert_btn.click()
        overlay.dismiss_btn.click()
        self.assertEqual(events, ["convert", "dismiss"])
