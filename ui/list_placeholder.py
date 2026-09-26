"""Faint bars where rows will appear, so an empty list reads as a list.

Used by the Video Converter file table and the Media Player playlist. The
bars fade out down the view and vanish as soon as the first real row lands.
"""
from __future__ import annotations

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QListWidget, QTableWidget

PLACEHOLDER_ROW_H = 26
PLACEHOLDER_BAR_H = 8
PLACEHOLDER_MAX_ROWS = 6
PLACEHOLDER_INSET = 10
PLACEHOLDER_COLOR = "#d7dbdf"
# Bar length as a share of the column, per row, so the block reads as text
# lines of different lengths rather than a grid.
_LENGTHS = (0.62, 0.48, 0.70, 0.40, 0.56, 0.66)


def placeholder_bars(width: int, height: int, columns=None, row_height: int = PLACEHOLDER_ROW_H):
    """Bar rectangles for an empty view of `width` x `height`.

    `columns` is a list of (x, width) spans; None means one span across the view.
    Returns (rect, alpha) pairs, alpha in 0..1 fading down the view.
    """
    if width <= 0 or height <= 0:
        return []
    spans = columns or [(0, width)]
    rows = min(PLACEHOLDER_MAX_ROWS, max(0, height // row_height))
    bars = []
    for row in range(rows):
        alpha = 1.0 - row * (0.75 / max(1, PLACEHOLDER_MAX_ROWS - 1))
        y = row * row_height + (row_height - PLACEHOLDER_BAR_H) // 2
        for col, (x, span) in enumerate(spans):
            usable = span - 2 * PLACEHOLDER_INSET
            if usable <= 12:
                continue
            length = int(usable * _LENGTHS[(row + col) % len(_LENGTHS)])
            bars.append((QRect(x + PLACEHOLDER_INSET, y, length, PLACEHOLDER_BAR_H), alpha))
    return bars


def paint_placeholder_bars(viewport, columns=None, row_height: int = PLACEHOLDER_ROW_H):
    painter = QPainter(viewport)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    base = QColor(PLACEHOLDER_COLOR)
    for rect, alpha in placeholder_bars(viewport.width(), viewport.height(), columns, row_height):
        color = QColor(base)
        color.setAlphaF(alpha)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, PLACEHOLDER_BAR_H / 2, PLACEHOLDER_BAR_H / 2)
    painter.end()


class PlaceholderTableWidget(QTableWidget):
    """QTableWidget that sketches rows while it has none."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() > 0:
            return
        header = self.horizontalHeader()
        columns = [
            (header.sectionViewportPosition(col), header.sectionSize(col))
            for col in range(self.columnCount())
            if not self.isColumnHidden(col)
        ]
        row_height = self.verticalHeader().defaultSectionSize() or PLACEHOLDER_ROW_H
        paint_placeholder_bars(self.viewport(), columns, row_height)


class PlaceholderListWidget(QListWidget):
    """QListWidget that sketches rows while it has none."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() > 0:
            return
        paint_placeholder_bars(self.viewport())
