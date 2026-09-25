"""Small Qt building blocks for the Media Player tab."""
from PyQt5.QtCore import QCoreApplication, Qt, pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget


def _tr(source: str) -> str:
    """Translate under the stable "MediaPlayer" context (plain literals only)."""
    return QCoreApplication.translate("MediaPlayer", source)


class FullscreenHost(QWidget):
    """A frameless top-level window that temporarily hosts the player's stage and bar."""

    mouse_moved = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._taken = []

    def take(self, widget):
        self._taken.append(widget)
        stretch = 1 if not self._taken[:-1] else 0
        self._layout.addWidget(widget, stretch)
        widget.setMouseTracking(True)

    def release(self):
        released = list(self._taken)
        for widget in released:
            self._layout.removeWidget(widget)
            widget.setParent(None)
        self._taken = []
        return released

    def mouseMoveEvent(self, event):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.exit_requested.emit()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_F):
            self.exit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
