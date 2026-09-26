import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QWIDGETSIZE_MAX,
    QApplication,
    QDoubleSpinBox,
    QLabel,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
)

from ui import inspection_widget as inspection_module
from ui.inspection_widget import InspectionWidget
from ui.media_player_parts import (
    FullscreenHost,
    InspectionDock,
    PlaylistDock,
    PlaylistTable,
    UnsupportedOverlay,
    format_offset_seconds,
)
from ui.media_player_support import PlaylistModel


class InspectionDockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dock_embeds_the_inspection_widget_without_driving_the_sidebar_preview(self):
        dock = InspectionDock()
        self.addCleanup(dock.close)
        self.assertIsInstance(dock.inspector, InspectionWidget)
        self.assertFalse(dock.inspector.notify_preview)
        self.assertGreaterEqual(dock.minimumWidth(), 260)
        self.assertEqual(dock.maximumWidth(), QWIDGETSIZE_MAX)     # scales with the window

    def test_dock_uses_the_compact_inspector_without_dashed_drop_frames(self):
        dock = InspectionDock()
        self.addCleanup(dock.close)
        inspector = dock.inspector
        self.assertTrue(inspector.compact)
        for zone in (inspector.summary_drag_drop, inspector.json_drag_drop):
            self.assertNotIn("dashed", zone.styleSheet())
        # Real scroll bars: the old style hid them (width 0 / transparent handle).
        for text in (inspector.summary_text, inspector.info_display):
            self.assertNotIn("width: 0px", text.styleSheet())
            self.assertNotIn("QScrollBar::handle", text.styleSheet())
        self.assertIn("drop a file here", inspector.summary_drag_text.text())
        # Drag feedback must not bring the dashed frame back.
        inspector.summary_drag_leave(None)
        self.assertNotIn("dashed", inspector.summary_drag_drop.styleSheet())

    def test_stop_inspection_kills_a_running_probe_and_joins_the_thread(self):
        # Destroying a QThread that is still running aborts the process; a
        # probe on a slow drive must not be able to take NVC down at exit.
        inspector = InspectionWidget(compact=True)
        self.addCleanup(inspector.close)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]

        def slow_run(self):
            try:
                self._run_probe(sleeper, 60)
            except InterruptedError:
                return

        with patch.object(inspection_module.InspectionWorker, "run", slow_run):
            inspector.inspect_file(path)
            worker = inspector._inspection_worker
            deadline = time.monotonic() + 3
            while worker._process is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertIsNotNone(worker._process)
            started = time.monotonic()
            inspector.stop_inspection()
        self.assertIsNone(inspector._inspection_worker)
        self.assertFalse(worker.isRunning())
        self.assertLess(time.monotonic() - started, 3)

    def test_stand_alone_inspector_keeps_its_drop_zone_look(self):
        inspector = InspectionWidget()
        self.addCleanup(inspector.close)
        self.assertFalse(inspector.compact)
        self.assertIn("dashed", inspector.summary_drag_drop.styleSheet())

    def test_inspect_path_runs_ffprobe_once_per_path_and_clears_on_empty(self):
        dock = InspectionDock()
        self.addCleanup(dock.close)
        runs = []
        dock.inspector.inspect_file = lambda path: runs.append(path)
        dock.inspect_path("C:/Videos/a.mp4")
        dock.inspect_path("C:/Videos/a.mp4")          # same file: no second ffprobe
        dock.inspect_path("")
        self.assertEqual(runs, ["C:/Videos/a.mp4"])
        self.assertEqual(dock.current_path, "")
        self.assertTrue(dock.inspector.summary_text.isHidden())
        self.assertFalse(dock.inspector.summary_drag_text.isHidden())

    def test_dock_is_the_inspector_alone_with_no_title_row(self):
        dock = InspectionDock()
        self.addCleanup(dock.close)
        self.assertFalse(hasattr(dock, "title_label"))
        self.assertFalse(hasattr(dock, "set_panel_title"))
        self.assertIs(dock.layout().itemAt(0).widget(), dock.inspector)


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

    def test_horizontal_dock_is_a_short_strip_with_buttons_beside_the_list(self):
        dock = PlaylistDock(horizontal=True)
        self.addCleanup(dock.close)
        self.assertTrue(dock.horizontal)
        self.assertLessEqual(dock.maximumHeight(), 160)
        self.assertEqual(dock.maximumWidth(), QWIDGETSIZE_MAX)
        self.assertEqual(dock.minimumWidth(), 0)
        row = dock.layout().itemAt(1).layout()          # title above; list + buttons below
        self.assertIs(row.itemAt(0).widget(), dock.list)
        self.assertIsInstance(row.itemAt(1).layout(), QVBoxLayout)

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
        dock.list.rows_moved.emit(0, 2)
        self.assertEqual(model.items, ["b", "c", "a"])
        self.assertEqual(dock.list.currentRow(), 2)

    def test_playlist_has_a_clip_column_and_an_offset_column(self):
        dock, model = self._dock()
        self.assertEqual(dock.list.columnCount(), 2)
        self.assertEqual(
            [dock.list.horizontalHeaderItem(c).text() for c in range(2)], ["Clip", "Offset"]
        )
        dock.add_paths(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
        model.set_offset("C:\\Videos\\b.mp4", -1.25)
        dock.refresh()
        self.assertEqual(dock.list.item(0, PlaylistTable.OFFSET).text(), "0.0 s")
        self.assertEqual(dock.list.item(1, PlaylistTable.OFFSET).text(), "-1.2 s")
        self.assertEqual(dock.list.item(1, PlaylistTable.OFFSET).data(Qt.UserRole), -1.25)
        # The clip cell is not editable; the offset cell is.
        self.assertFalse(dock.list.item(0, PlaylistTable.CLIP).flags() & Qt.ItemIsEditable)
        self.assertTrue(dock.list.item(0, PlaylistTable.OFFSET).flags() & Qt.ItemIsEditable)
        self.assertIsInstance(
            dock.list.itemDelegateForColumn(PlaylistTable.OFFSET), QStyledItemDelegate
        )

    def test_editing_the_offset_cell_updates_the_model_and_announces_it(self):
        dock, model = self._dock()
        dock.add_paths(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
        changes = []
        dock.offset_changed.connect(lambda path, secs: changes.append((path, secs)))
        # What the delegate's setModelData does when the spin box commits.
        dock.list.item(1, PlaylistTable.OFFSET).setData(Qt.UserRole, 2.5)
        self.assertEqual(model.offset_for("C:\\Videos\\b.mp4"), 2.5)
        self.assertEqual(changes, [("C:\\Videos\\b.mp4", 2.5)])
        self.assertEqual(dock.list.item(1, PlaylistTable.OFFSET).text(), "+2.5 s")
        self.assertEqual(dock.list.currentRow(), 1)

    def test_offset_editor_is_a_seconds_spin_box_bound_to_the_cell(self):
        dock, _model = self._dock()
        dock.add_paths(["C:\\Videos\\a.mp4"])
        index = dock.list.model().index(0, PlaylistTable.OFFSET)
        delegate = dock.list.itemDelegateForColumn(PlaylistTable.OFFSET)
        editor = delegate.createEditor(dock.list, None, index)
        self.assertIsInstance(editor, QDoubleSpinBox)
        self.assertEqual(editor.maximum(), PlaylistModel.OFFSET_LIMIT_S)
        self.assertEqual(editor.suffix(), " s")
        editor.setValue(-3.0)
        delegate.setModelData(editor, dock.list.model(), index)
        self.assertEqual(dock.list.item(0, PlaylistTable.OFFSET).data(Qt.UserRole), -3.0)

    def test_double_clicking_the_offset_cell_does_not_activate_the_clip(self):
        dock, _model = self._dock()
        dock.add_paths(["C:\\Videos\\a.mp4"])
        activated = []
        dock.activate_requested.connect(activated.append)
        dock.list.itemDoubleClicked.emit(dock.list.item(0, PlaylistTable.OFFSET))
        self.assertEqual(activated, [])

    def test_offset_text_is_signed_and_one_decimal(self):
        self.assertEqual(format_offset_seconds(0), "0.0 s")
        self.assertEqual(format_offset_seconds(1.25), "+1.2 s")
        self.assertEqual(format_offset_seconds(-0.5), "-0.5 s")


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
