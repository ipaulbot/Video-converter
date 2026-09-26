"""Drag-to-select overlay for choosing a screen region to record.

The overlay covers the whole virtual desktop (every monitor), dims it, and
lets the user drag a rectangle. The result is reported in global (virtual
screen) coordinates, which are also what gdigrab's -offset_x/-offset_y
expect; `region_source_value_for` turns that into the `region=X,Y,WxH` value
the screen source understands.
"""

from PyQt5.QtCore import QCoreApplication, QEventLoop, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QGuiApplication, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from conversion.recording_sources import build_region_source_value


def _tr(source: str) -> str:
    return QCoreApplication.translate("Recorder", source)


class ScreenRegionPicker(QWidget):
    region_selected = pyqtSignal(QRect)   # global coordinates
    cancelled = pyqtSignal()

    MIN_SIZE = 8                          # smaller drags count as a click

    def __init__(self, virtual_geometry, parent=None):
        super().__init__(parent)
        self._virtual_geometry = QRect(virtual_geometry)
        self._origin = None
        self._current = None
        self._done = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(self._virtual_geometry)
        self.setWindowTitle(_tr("Select a screen region"))

    # -- geometry -----------------------------------------------------------

    def _local_selection(self):
        # Width/height are the dragged distance, not QRect's inclusive corner-to-corner span.
        left = min(self._origin.x(), self._current.x())
        top = min(self._origin.y(), self._current.y())
        width = abs(self._current.x() - self._origin.x())
        height = abs(self._current.y() - self._origin.y())
        return QRect(left, top, width, height)

    def selection(self):
        """Current drag rectangle in global coordinates (empty before a drag)."""
        if self._origin is None or self._current is None:
            return QRect()
        return self._local_selection().translated(self._virtual_geometry.topLeft())

    # -- events -------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.pos()
        self._current = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        if self._origin is None:
            return
        self._current = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if self._origin is None or self._done:
            return
        self._current = event.pos()
        region = self.selection()
        self._done = True
        if region.width() < self.MIN_SIZE or region.height() < self.MIN_SIZE:
            self.cancelled.emit()
        else:
            self.region_selected.emit(region)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and not self._done:
            self._done = True
            self.cancelled.emit()
            self.close()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 96))
        if self._origin is not None and self._current is not None:
            local = self._local_selection()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(local, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#92cb4f"), 2))
            painter.drawRect(local)
            label = f"{local.width()} x {local.height()}"
            painter.setPen(QColor("#ffffff"))
            painter.drawText(local.bottomLeft() + QPoint(4, 18), label)
        painter.end()


def region_source_value_for(region):
    """`region=X,Y,WxH` for a global rectangle.

    gdigrab's -offset_x/-offset_y are absolute virtual-screen coordinates (a
    monitor left of the primary one has negative x), which is exactly what Qt's
    global coordinates are, so the rectangle is passed through. Sizes are
    rounded down to even numbers so the 4:2:0 encode needs no padding.
    """
    width = max(2, region.width() // 2 * 2)
    height = max(2, region.height() // 2 * 2)
    return build_region_source_value(region.left(), region.top(), width, height)


def virtual_desktop_geometry():
    screens = QGuiApplication.screens()
    if not screens:
        return QRect(0, 0, 1, 1)
    geometry = QRect(screens[0].geometry())
    for screen in screens[1:]:
        geometry = geometry.united(screen.geometry())
    return geometry


def pick_screen_region_value():
    """Show the overlay and return `region=X,Y,WxH`, or "" if the user cancelled."""
    geometry = virtual_desktop_geometry()
    picker = ScreenRegionPicker(geometry)
    result = {"value": ""}
    loop = QEventLoop()

    def selected(region):
        result["value"] = region_source_value_for(region)
        loop.quit()

    picker.region_selected.connect(selected)
    picker.cancelled.connect(loop.quit)
    picker.show()
    picker.raise_()
    picker.activateWindow()
    picker.setFocus()
    loop.exec_()
    picker.setParent(None)
    picker.deleteLater()
    return result["value"]
