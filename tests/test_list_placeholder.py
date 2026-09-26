import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from ui.converted_files_widget import ConvertedFilesWidget
from ui.list_placeholder import (
    PLACEHOLDER_INSET,
    PLACEHOLDER_ROW_H,
    PlaceholderListWidget,
    PlaceholderTableWidget,
    placeholder_rule_rows,
    placeholder_rules,
)
from ui.media_player_parts import PlaylistDock


def _pixel(view, x, y):
    """Colour at viewport pixel (x, y), rendered off-screen."""
    image = view.viewport().grab().toImage()
    return QColor(image.pixel(x, y))


def _first_rule_y(view, row_height=PLACEHOLDER_ROW_H):
    return placeholder_rule_rows(view.viewport().height(), row_height)[0]


class PlaceholderRuleTests(unittest.TestCase):
    def test_one_hairline_under_every_row_slot_all_the_way_down(self):
        rows = placeholder_rule_rows(24 * 10 + 7)
        self.assertEqual(len(rows), 10)                        # fills the view, no cap
        self.assertEqual(rows[0], 23)                          # bottom pixel of the first slot
        self.assertEqual(rows[1] - rows[0], 24)                # evenly spaced
        self.assertEqual(placeholder_rule_rows(100, row_height=26)[:2], [25, 51])

    def test_rules_stop_short_of_the_view_edges(self):
        segments = placeholder_rules(300, 24)
        self.assertEqual(segments, [(PLACEHOLDER_INSET, 300 - PLACEHOLDER_INSET - 1, 23)])

    def test_rules_break_at_column_boundaries(self):
        segments = placeholder_rules(400, 24, columns=[(0, 150), (150, 250)])
        self.assertEqual(
            segments,
            [(8, 141, 23), (158, 391, 23)],
        )
        # A column too narrow for a visible rule gets none.
        self.assertEqual(placeholder_rules(400, 24, columns=[(0, 18), (18, 382)]),
                         [(26, 391, 23)])

    def test_tiny_or_empty_views_get_none(self):
        self.assertEqual(placeholder_rules(0, 100), [])
        self.assertEqual(placeholder_rules(400, 10), [])
        self.assertEqual(placeholder_rules(400, 100, row_height=0), [])


class PlaceholderViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _shown(self, view):
        view.resize(400, 200)
        view.move(-7000, -7000)
        view.show()
        self.app.processEvents()
        self.addCleanup(view.close)
        return view

    def test_empty_table_rules_each_column_with_gaps_and_a_row_clears_them(self):
        table = self._shown(PlaceholderTableWidget(0, 2))
        table.setStyleSheet("QTableWidget { background: white; }")
        table.verticalHeader().setDefaultSectionSize(24)
        table.setColumnWidth(0, 150)
        self.app.processEvents()
        y = _first_rule_y(table)
        header = table.horizontalHeader()
        boundary = header.sectionViewportPosition(1)
        self.assertEqual(_pixel(table, 2, y).name(), "#ffffff")              # inset at the left edge
        self.assertNotEqual(_pixel(table, 60, y).name(), "#ffffff")          # inside column 0
        self.assertEqual(_pixel(table, boundary - 3, y).name(), "#ffffff")   # gap before the boundary
        self.assertEqual(_pixel(table, boundary + 3, y).name(), "#ffffff")   # gap after the boundary
        self.assertNotEqual(_pixel(table, boundary + 40, y).name(), "#ffffff")  # inside column 1
        self.assertEqual(_pixel(table, 60, y - 1).name(), "#ffffff")         # one pixel thin
        self.assertEqual(_pixel(table, 60, y - 10).name(), "#ffffff")        # no fat bar
        table.insertRow(0)
        self.app.processEvents()
        # The real row draws its own grid line at y; the slot below it is now plain.
        self.assertEqual(_pixel(table, 60, y + 24).name(), "#ffffff")

    def test_empty_list_rules_its_rows_inset_from_the_edges(self):
        view = self._shown(PlaceholderListWidget())
        view.setStyleSheet("QListWidget { background: white; }")
        y = _first_rule_y(view)
        self.assertEqual(_pixel(view, 2, y).name(), "#ffffff")
        self.assertNotEqual(_pixel(view, 40, y).name(), "#ffffff")
        self.assertEqual(_pixel(view, 40, y - 1).name(), "#ffffff")

    def test_converter_table_and_playlist_use_the_placeholder_views(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        self.assertIsInstance(widget.table_widget, PlaceholderTableWidget)
        dock = PlaylistDock()
        self.addCleanup(dock.close)
        self.assertIsInstance(dock.list, PlaceholderTableWidget)   # Clip | Panel | Offset columns
        self.assertEqual(dock.list.selectionMode(), dock.list.ExtendedSelection)
        self.assertEqual(dock.list.selectionBehavior(), dock.list.SelectRows)
        self.assertEqual(dock.list.dragDropMode(), dock.list.InternalMove)
        self.assertEqual(int(dock.list.focusPolicy()) & int(Qt.ClickFocus), int(Qt.ClickFocus))
