"""Cards and labels with VIO's leaf silhouette: rounded top-left and bottom-right corners."""

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter, QPainterPath
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from ui import theme


def leaf_path(rect, radius: float) -> QPainterPath:
    """The leaf outline for `rect`: top-left and bottom-right corners rounded."""
    r = QRectF(rect)
    radius = max(0.0, min(float(radius), r.width() / 2, r.height() / 2))
    path = QPainterPath()
    path.moveTo(r.left() + radius, r.top())
    path.lineTo(r.right(), r.top())
    path.lineTo(r.right(), r.bottom() - radius)
    path.arcTo(r.right() - 2 * radius, r.bottom() - 2 * radius, 2 * radius, 2 * radius, 0, -90)
    path.lineTo(r.left(), r.bottom())
    path.lineTo(r.left(), r.top() + radius)
    path.arcTo(r.left(), r.top(), 2 * radius, 2 * radius, 180, -90)
    path.closeSubpath()
    return path


class LeafFrame(QFrame):
    def __init__(self, parent=None, radius: int = 28, dashed: bool = False):
        super().__init__(parent)
        self.radius = radius
        self.dashed = dashed
        self.setObjectName("leaf")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(12, 12, 12, 12)
        self.body.setSpacing(6)
        self.reskin()

    def reskin(self) -> None:
        """Re-read the skin; call after theme changes."""
        self.setStyleSheet(theme.leaf_style(self.radius, self.dashed))


class LeafPixmapLabel(QLabel):
    """A QLabel whose pixmap is clipped to the leaf outline.

    QLabel paints a pixmap as a plain rectangle, which covers the rounded
    corners of the leaf-styled frame behind it the moment a thumbnail or a
    decoded frame arrives. Text (a placeholder caption) is left to QLabel.
    """

    def __init__(self, text: str = "", parent=None, radius: int = 18):
        super().__init__(text, parent)
        self.radius = radius

    def paintEvent(self, event):
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = self.contentsRect()
        painter.setClipPath(leaf_path(rect, self.radius))
        # Callers pre-fit thumbnails; decoded frames are the container's full
        # 180x101 while this label sits inside a 2px border. Trim those few
        # edge pixels rather than letterboxing the whole frame.
        scaled = pixmap
        if pixmap.width() > rect.width() or pixmap.height() > rect.height():
            scaled = pixmap.scaled(rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = rect.x() + (rect.width() - scaled.width()) // 2
        y = rect.y() + (rect.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
