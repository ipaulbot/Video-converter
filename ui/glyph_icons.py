"""Small vector glyphs painted at runtime so they tint with the skin.

The repository ships only skin-prefixed .ico files (bare / GREEN / GRAYSCALE)
for its big chrome icons; tool-tab controls need a dozen tiny glyphs in the
accent colour, which is cheaper to paint than to maintain as 36 bitmaps.
"""
from __future__ import annotations

from math import cos, radians, sin

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QToolButton

from ui import theme

GLYPHS: tuple[str, ...] = (
    "play",
    "pause",
    "stop",
    "restart",
    "fullscreen",
    "playlist",
    "volume",
    "muted",
    "add_file",
    "add_folder",
    "remove",
    "clear",
    "folder_open",
    "report",
    "shield",
    "refresh",
    "settings",
    "log",
    "camera",
    "inspect",
)


def _pen(color: QColor, width: float = 1.8) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _paint(name: str, painter: QPainter, s: float, color: QColor) -> None:
    """Draw `name` into a s x s box. Coordinates are fractions of s."""

    def P(x, y):
        return QPointF(x * s, y * s)

    def R(x, y, w, h):
        return QRectF(x * s, y * s, w * s, h * s)

    painter.setPen(_pen(color, max(1.4, s * 0.09)))
    painter.setBrush(color)
    if name == "play":
        painter.drawPolygon(
            QPolygonF([P(0.28, 0.18), P(0.80, 0.50), P(0.28, 0.82)])
        )
    elif name == "pause":
        painter.drawRoundedRect(R(0.24, 0.20, 0.18, 0.60), 1.5, 1.5)
        painter.drawRoundedRect(R(0.58, 0.20, 0.18, 0.60), 1.5, 1.5)
    elif name == "stop":
        painter.drawRoundedRect(R(0.24, 0.24, 0.52, 0.52), 2, 2)
    elif name == "restart":
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(R(0.22, 0.22, 0.56, 0.56), 40 * 16, 280 * 16)
        painter.setBrush(color)
        painter.drawPolygon(
            QPolygonF([P(0.66, 0.12), P(0.84, 0.30), P(0.60, 0.34)])
        )
    elif name == "fullscreen":
        painter.setBrush(Qt.NoBrush)
        corners = (
            (0.2, 0.2, 1, 1),
            (0.8, 0.2, -1, 1),
            (0.2, 0.8, 1, -1),
            (0.8, 0.8, -1, -1),
        )
        for x, y, dx, dy in corners:
            painter.drawLine(P(x, y), P(x + 0.18 * dx, y))
            painter.drawLine(P(x, y), P(x, y + 0.18 * dy))
    elif name == "playlist":
        painter.setBrush(Qt.NoBrush)
        for y in (0.28, 0.50, 0.72):
            painter.drawLine(P(0.22, y), P(0.62, y))
        painter.setBrush(color)
        painter.drawPolygon(
            QPolygonF([P(0.68, 0.40), P(0.84, 0.50), P(0.68, 0.60)])
        )
    elif name in ("volume", "muted"):
        painter.drawPolygon(
            QPolygonF(
                [
                    P(0.18, 0.40),
                    P(0.34, 0.40),
                    P(0.50, 0.24),
                    P(0.50, 0.76),
                    P(0.34, 0.60),
                    P(0.18, 0.60),
                ]
            )
        )
        painter.setBrush(Qt.NoBrush)
        if name == "volume":
            painter.drawArc(R(0.40, 0.30, 0.40, 0.40), -60 * 16, 120 * 16)
            painter.drawArc(R(0.34, 0.20, 0.60, 0.60), -60 * 16, 120 * 16)
        else:
            painter.drawLine(P(0.62, 0.38), P(0.84, 0.62))
            painter.drawLine(P(0.84, 0.38), P(0.62, 0.62))
    elif name in ("add_file", "add_folder"):
        painter.setBrush(Qt.NoBrush)
        if name == "add_file":
            path = QPainterPath(P(0.28, 0.16))
            path.lineTo(P(0.60, 0.16))
            path.lineTo(P(0.74, 0.30))
            path.lineTo(P(0.74, 0.84))
            path.lineTo(P(0.28, 0.84))
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(R(0.14, 0.30, 0.72, 0.50), 2, 2)
            painter.drawLine(P(0.14, 0.30), P(0.30, 0.20))
            painter.drawLine(P(0.30, 0.20), P(0.46, 0.20))
            painter.drawLine(P(0.46, 0.20), P(0.52, 0.30))
        painter.drawLine(P(0.50, 0.46), P(0.50, 0.70))
        painter.drawLine(P(0.38, 0.58), P(0.62, 0.58))
    elif name == "remove":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(P(0.26, 0.50), P(0.74, 0.50))
    elif name == "clear":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(P(0.22, 0.30), P(0.78, 0.30))
        painter.drawLine(P(0.42, 0.30), P(0.42, 0.20))
        painter.drawLine(P(0.42, 0.20), P(0.58, 0.20))
        painter.drawLine(P(0.58, 0.20), P(0.58, 0.30))
        painter.drawRect(R(0.28, 0.30, 0.44, 0.52))
        painter.drawLine(P(0.42, 0.42), P(0.42, 0.72))
        painter.drawLine(P(0.58, 0.42), P(0.58, 0.72))
    elif name == "folder_open":
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(R(0.14, 0.30, 0.72, 0.50), 2, 2)
        painter.drawLine(P(0.14, 0.30), P(0.30, 0.20))
        painter.drawLine(P(0.30, 0.20), P(0.46, 0.20))
        painter.drawLine(P(0.46, 0.20), P(0.52, 0.30))
        painter.drawLine(P(0.14, 0.48), P(0.86, 0.48))
    elif name == "report":
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(R(0.26, 0.14, 0.48, 0.72), 2, 2)
        for y in (0.36, 0.50, 0.64):
            painter.drawLine(P(0.36, y), P(0.64, y))
    elif name == "shield":
        path = QPainterPath(P(0.50, 0.12))
        path.lineTo(P(0.80, 0.24))
        path.lineTo(P(0.76, 0.58))
        path.quadTo(P(0.70, 0.78), P(0.50, 0.88))
        path.quadTo(P(0.30, 0.78), P(0.24, 0.58))
        path.lineTo(P(0.20, 0.24))
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "refresh":
        # Two half-arcs chasing each other, each with an arrowhead.
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(R(0.20, 0.20, 0.60, 0.60), 30 * 16, 130 * 16)
        painter.drawArc(R(0.20, 0.20, 0.60, 0.60), 210 * 16, 130 * 16)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([P(0.74, 0.14), P(0.86, 0.36), P(0.62, 0.34)]))
        painter.drawPolygon(QPolygonF([P(0.26, 0.86), P(0.14, 0.64), P(0.38, 0.66)]))
    elif name == "settings":
        # A gear: ring plus eight teeth.
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(R(0.32, 0.32, 0.36, 0.36))
        for i in range(8):
            rad = radians(i * 45.0)
            painter.drawLine(
                P(0.5 + 0.30 * cos(rad), 0.5 + 0.30 * sin(rad)),
                P(0.5 + 0.42 * cos(rad), 0.5 + 0.42 * sin(rad)),
            )
    elif name == "log":
        # A bulleted list.
        painter.setBrush(color)
        for y in (0.28, 0.50, 0.72):
            painter.drawEllipse(R(0.18, y - 0.05, 0.10, 0.10))
            painter.drawLine(P(0.38, y), P(0.82, y))
    elif name == "camera":
        # A camera body with a lens and a viewfinder bump.
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(R(0.14, 0.32, 0.72, 0.46), 2, 2)
        painter.drawLine(P(0.34, 0.32), P(0.40, 0.22))
        painter.drawLine(P(0.40, 0.22), P(0.60, 0.22))
        painter.drawLine(P(0.60, 0.22), P(0.66, 0.32))
        painter.drawEllipse(R(0.38, 0.42, 0.24, 0.24))
    elif name == "inspect":
        # A magnifier: lens with a handle to the lower right.
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(R(0.18, 0.18, 0.44, 0.44))
        painter.setPen(_pen(color, max(1.8, s * 0.13)))
        painter.drawLine(P(0.58, 0.58), P(0.82, 0.82))
    else:
        raise KeyError(name)


def glyph_icon(name: str, color: str, size: int = 20) -> QIcon:
    """A QIcon of `name` in `color`. Raises KeyError for unknown names."""
    if name not in GLYPHS:
        raise KeyError(name)
    qcolor = QColor(color)
    icon = QIcon()
    for px in (size, size * 2):  # a 2x pixmap keeps high-DPI screens crisp
        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        _paint(name, painter, float(px), qcolor)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def make_icon_button(
    name: str,
    tooltip: str,
    color: str,
    size: int = 28,
    parent=None,
) -> QToolButton:
    """A flat square QToolButton carrying `glyph_icon(name)` and `tooltip`."""
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setProperty("glyph", name)
    button.setIcon(glyph_icon(name, color, size - 8))
    button.setIconSize(QSize(size - 8, size - 8))
    button.setFixedSize(size, size)
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet(theme.icon_button_style(size))
    button.setProperty("glyph_size", size)
    return button


def set_link_glyph(button, name: str, color: str, size: int = 16) -> None:
    """Put a small glyph in front of a text button or link (PC Report links,
    the recorder's Video Settings / recording log links). Re-call on reskin."""
    button.setProperty("glyph", name)
    button.setIcon(glyph_icon(name, color, size))
    button.setIconSize(QSize(size, size))


def set_button_glyph(button: QToolButton, name: str, color: str) -> None:
    """Swap the glyph on a button made by `make_icon_button` (play/pause, mute)."""
    size = int(button.property("glyph_size") or 28)
    button.setProperty("glyph", name)
    button.setIcon(glyph_icon(name, color, size - 8))


def reskin_icon_buttons(root, color: str) -> list[QToolButton]:
    """Repaint every glyph button under `root` in `color` (lock / converting skins).

    Returns the buttons touched so callers can restore state-dependent glyphs
    (a playing transport shows pause, a muted one shows the muted speaker).
    """
    touched = []
    for button in root.findChildren(QToolButton):
        name = button.property("glyph")
        if not name:
            continue
        size = int(button.property("glyph_size") or 28)
        button.setIcon(glyph_icon(name, color, size - 8))
        button.setStyleSheet(theme.icon_button_style(size))
        touched.append(button)
    return touched
