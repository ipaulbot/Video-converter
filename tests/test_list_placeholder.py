import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from ui.converted_files_widget import ConvertedFilesWidget
from ui.list_placeholder import (
    PLACEHOLDER_MAX_ROWS,
    PlaceholderListWidget,
    PlaceholderTableWidget,
    placeholder_bars,
)
from ui.media_player_parts import PlaylistDock


def _first_bar_pixel(view):
    """Colour at the centre of the first placeholder bar, rendered off-screen."""
    image = view.viewport().grab().toImage()
    bars = placeholder_bars(view.viewport().width(), view.viewport().height())
    rect = bars[0][0]
    return QColor(image.pixel(rect.center()))


class PlaceholderBarTests(unittest.TestCase):
    def test_bars_fill_rows_and_fade_down_the_view(self):
        bars = placeholder_bars(300, 26 * 10)
        self.assertEqual(len(bars), PLACEHOLDER_MAX_ROWS)
        alphas = [alpha for _rect, alpha in bars]
        self.assertEqual(alphas, sorted(alphas, reverse=True))
        self.assertEqual(alphas[0], 1.0)
        self.assertGreater(alphas[-1], 0.2)
        self.assertLess(bars[0][0].width(), 300)

    def test_columns_get_one_bar_each_and_tiny_or_empty_views_get_none(self):
        bars = placeholder_bars(400, 26, columns=[(0, 200), (200, 200)])
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0][0].left(), 10)
        self.assertEqual(bars[1][0].left(), 210)
        self.assertEqual(placeholder_bars(0, 100), [])
        self.assertEqual(placeholder_bars(400, 10), [])


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

    def test_empty_table_shows_grey_bars_and_a_row_clears_them(self):
        table = self._shown(PlaceholderTableWidget(0, 2))
        table.setStyleSheet("QTableWidget { background: white; }")
        grey = _first_bar_pixel(table)
        self.assertNotEqual(grey.name(), "#ffffff")
        table.insertRow(0)
        self.app.processEvents()
        self.assertEqual(_first_bar_pixel(table).name(), "#ffffff")

    def test_empty_list_shows_grey_bars(self):
        view = self._shown(PlaceholderListWidget())
        view.setStyleSheet("QListWidget { background: white; }")
        self.assertNotEqual(_first_bar_pixel(view).name(), "#ffffff")

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
