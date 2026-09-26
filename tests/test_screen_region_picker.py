import unittest

from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent

from ui.screen_region_picker import ScreenRegionPicker, region_source_value_for


def _mouse(kind, pos):
    return QMouseEvent(kind, QPointF(pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


class ScreenRegionPickerTests(unittest.TestCase):
    def _picker(self):
        # A two-monitor desktop whose left display sits at negative x.
        return ScreenRegionPicker(QRect(-1920, 0, 3840, 1080))

    def test_drag_reports_the_rectangle_in_virtual_desktop_coordinates(self):
        picker = self._picker()
        selected = []
        picker.region_selected.connect(selected.append)

        picker.mousePressEvent(_mouse(QEvent.MouseButtonPress, QPoint(100, 100)))
        picker.mouseMoveEvent(_mouse(QEvent.MouseMove, QPoint(500, 400)))
        self.assertEqual(picker.selection(), QRect(-1820, 100, 400, 300))
        picker.mouseReleaseEvent(_mouse(QEvent.MouseButtonRelease, QPoint(500, 400)))

        self.assertEqual(selected, [QRect(-1820, 100, 400, 300)])

    def test_drag_in_any_direction_is_normalised(self):
        picker = self._picker()
        selected = []
        picker.region_selected.connect(selected.append)

        picker.mousePressEvent(_mouse(QEvent.MouseButtonPress, QPoint(500, 400)))
        picker.mouseReleaseEvent(_mouse(QEvent.MouseButtonRelease, QPoint(100, 100)))

        self.assertEqual(selected, [QRect(-1820, 100, 400, 300)])

    def test_a_click_without_a_drag_cancels(self):
        picker = self._picker()
        selected, cancelled = [], []
        picker.region_selected.connect(selected.append)
        picker.cancelled.connect(lambda: cancelled.append(True))

        picker.mousePressEvent(_mouse(QEvent.MouseButtonPress, QPoint(100, 100)))
        picker.mouseReleaseEvent(_mouse(QEvent.MouseButtonRelease, QPoint(103, 102)))

        self.assertEqual(selected, [])
        self.assertEqual(cancelled, [True])

    def test_escape_cancels(self):
        picker = self._picker()
        cancelled = []
        picker.cancelled.connect(lambda: cancelled.append(True))

        picker.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))

        self.assertEqual(cancelled, [True])

    def test_region_source_value_keeps_absolute_virtual_screen_coordinates(self):
        # gdigrab's -offset_x/-offset_y are absolute virtual-screen coordinates
        # (verified: on a desktop spanning -2560..2560 an offset of 2600 is
        # rejected as outside the window area, -800 is accepted), so a monitor
        # left of the primary one keeps its negative x.
        value = region_source_value_for(QRect(-1820, 100, 401, 301))
        self.assertEqual(value, "region=-1820,100,400x300")   # even sizes for yuv420p


if __name__ == "__main__":
    unittest.main()
