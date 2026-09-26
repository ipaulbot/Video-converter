import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from ui.converted_files_widget import ConvertedFilesWidget
from ui.list_placeholder import (
    PLACEHOLDER_ROW_H,
    PlaceholderListWidget,
    PlaceholderTableWidget,
    placeholder_rules,
)
from ui.media_player_parts import PlaylistDock


def _pixel(view, x, y):
    """Colour at viewport pixel (x, y), rendered off-screen."""
    image = view.viewport().grab().toImage()
    return QColor(image.pixel(x, y))


def _first_rule_y(view, row_height=PLACEHOLDER_ROW_H):
    return placeholder_rules(view.viewport().width(), view.viewport().height(), row_height)[0]


class PlaceholderRuleTests(unittest.TestCase):
    def test_one_hairline_under_every_row_slot_all_the_way_down(self):
        rules = placeholder_rules(300, 24 * 10 + 7)
        self.assertEqual(len(rules), 10)                       # fills the view, no cap
        self.assertEqual(rules[0], 23)                         # bottom pixel of the first slot
        self.assertEqual(rules[1] - rules[0], 24)              # evenly spaced
        self.assertEqual(placeholder_rules(300, 100, row_height=26)[:2], [25, 51])

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

    def test_empty_table_rules_its_rows_edge_to_edge_and_a_row_clears_them(self):
        table = self._shown(PlaceholderTableWidget(0, 2))
        table.setStyleSheet("QTableWidget { background: white; }")
        table.verticalHeader().setDefaultSectionSize(24)
        self.app.processEvents()
        y = _first_rule_y(table)
        width = table.viewport().width()
        # Grey on the rule, from the left edge to the right edge; white just above it.
        self.assertNotEqual(_pixel(table, 0, y).name(), "#ffffff")
        self.assertNotEqual(_pixel(table, width // 2, y).name(), "#ffffff")
        self.assertNotEqual(_pixel(table, width - 1, y).name(), "#ffffff")
        self.assertEqual(_pixel(table, width // 2, y - 1).name(), "#ffffff")   # one pixel thin
        self.assertEqual(_pixel(table, width // 2, y - 10).name(), "#ffffff")  # no fat bar
        table.insertRow(0)
        self.app.processEvents()
        # The real row draws its own grid line at y; the slot below it is now plain.
        self.assertEqual(_pixel(table, width // 2, y + 24).name(), "#ffffff")

    def test_empty_list_rules_its_rows(self):
        view = self._shown(PlaceholderListWidget())
        view.setStyleSheet("QListWidget { background: white; }")
        y = _first_rule_y(view)
        self.assertNotEqual(_pixel(view, 5, y).name(), "#ffffff")
        self.assertEqual(_pixel(view, 5, y - 1).name(), "#ffffff")

    def test_converter_table_and_playlist_use_the_placeholder_views(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        self.assertIsInstance(widget.table_widget, PlaceholderTableWidget)
        dock = PlaylistDock()
        self.addCleanup(dock.close)
        self.assertIsInstance(dock.list, PlaceholderTableWidget)   # Clip | Offset columns
        self.assertEqual(dock.list.selectionMode(), dock.list.ExtendedSelection)
        self.assertEqual(dock.list.selectionBehavior(), dock.list.SelectRows)
        self.assertEqual(dock.list.dragDropMode(), dock.list.InternalMove)
        self.assertEqual(int(dock.list.focusPolicy()) & int(Qt.ClickFocus), int(Qt.ClickFocus))
