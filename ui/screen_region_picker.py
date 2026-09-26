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
        # The picker opens on top of Video Settings and Screen Capture Settings,
        # both modal dialogs in exec_(). Qt delivers input to the newest modal
        # window only, so the overlay must be modal itself or it cannot be
        # clicked until both dialogs are closed.
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setGeometry(self._virtual_geometry)
        self.setWindowTitle(_tr("Select a screen region"))

    @staticmethod
    def instruction_text():
        return _tr("Drag to select the area to record. Press Esc to cancel.")

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

    def _banner_anchors(self):
        """Top-centre of every monitor covered by the overlay, in local coordinates."""
        anchors = []
        for screen in QGuiApplication.screens():
            geometry = screen.geometry()
            if geometry.intersects(self._virtual_geometry):
                anchors.append(geometry.translated(-self._virtual_geometry.topLeft()))
        return anchors or [self.rect()]

    def _paint_banner(self, painter):
        text = self.instruction_text()
        font = painter.font()
        font.setPointSize(14)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        box_height = metrics.height() + 20
        for screen_rect in self._banner_anchors():
            box = QRect(0, 0, text_width + 40, box_height)
            box.moveCenter(QPoint(screen_rect.center().x(), screen_rect.top() + 60))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 200))
            painter.drawRoundedRect(box, 8, 8)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(box, Qt.AlignCenter, text)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 96))
        self._paint_banner(painter)
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


def pick_screen_region_value(fade_windows=()):
    """Show the overlay and return `region=X,Y,WxH`, or "" if the user cancelled.

    `fade_windows` are the settings dialogs the picker was opened from. They
    are made fully transparent while the overlay is up so they do not cover the
    area being chosen; hiding them is not an option because hiding a dialog
    that is inside exec_() ends its event loop.
    """
    geometry = virtual_desktop_geometry()
    picker = ScreenRegionPicker(geometry)
    result = {"value": ""}
    loop = QEventLoop()

    def selected(region):
        result["value"] = region_source_value_for(region)
        loop.quit()

    picker.region_selected.connect(selected)
    picker.cancelled.connect(loop.quit)
    faded = [(window, window.windowOpacity()) for window in fade_windows if window is not None]
    for window, _opacity in faded:
        window.setWindowOpacity(0.0)
    try:
        picker.show()
        picker.raise_()
        picker.activateWindow()
        picker.setFocus()
        loop.exec_()
    finally:
        for window, opacity in faded:
            window.setWindowOpacity(opacity)
    picker.setParent(None)
    picker.deleteLater()
    return result["value"]
