"""Hairlines where rows will appear, so an empty list reads as a list.

Used by the Video Converter file table and the Media Player playlist. One
thin rule under every empty row slot, all the way down the view -- the look
of an old spreadsheet's grid, deliberately plain -- and gone as soon as the
first real row lands. (The first cut used fat, rounded, fading bars; the
owner asked for something thinner and less modern.)
"""
from __future__ import annotations

from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QListWidget, QTableWidget

PLACEHOLDER_ROW_H = 24
PLACEHOLDER_COLOR = "#dde1e5"
PLACEHOLDER_LINE_W = 1


def placeholder_rules(width: int, height: int, row_height: int = PLACEHOLDER_ROW_H):
    """y of the hairline under each empty row slot of a `width` x `height` view."""
    if width <= 0 or height <= 0 or row_height <= 0:
        return []
    return [row * row_height + row_height - 1 for row in range(height // row_height)]


def paint_placeholder_rules(viewport, row_height: int = PLACEHOLDER_ROW_H):
    painter = QPainter(viewport)
    painter.setRenderHint(QPainter.Antialiasing, False)
    pen = QPen(QColor(PLACEHOLDER_COLOR))
    pen.setWidth(PLACEHOLDER_LINE_W)
    painter.setPen(pen)
    right = viewport.width() - 1
    for y in placeholder_rules(viewport.width(), viewport.height(), row_height):
        painter.drawLine(0, y, right, y)
    painter.end()


class PlaceholderTableWidget(QTableWidget):
    """QTableWidget that rules its empty rows."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() > 0:
            return
        row_height = self.verticalHeader().defaultSectionSize() or PLACEHOLDER_ROW_H
        paint_placeholder_rules(self.viewport(), row_height)


class PlaceholderListWidget(QListWidget):
    """QListWidget that rules its empty rows."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() > 0:
            return
        paint_placeholder_rules(self.viewport())
