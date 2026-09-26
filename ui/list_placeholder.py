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
PLACEHOLDER_INSET = 8      # the rule stops short of the view edge and of each column edge


def placeholder_rule_rows(height: int, row_height: int = PLACEHOLDER_ROW_H):
    """y of the hairline under each empty row slot of a view `height` tall."""
    if height <= 0 or row_height <= 0:
        return []
    return [row * row_height + row_height - 1 for row in range(height // row_height)]


def placeholder_rules(
    width: int,
    height: int,
    row_height: int = PLACEHOLDER_ROW_H,
    columns=None,
    inset: int = PLACEHOLDER_INSET,
):
    """(x1, x2, y) segments for a `width` x `height` view: one per column per
    empty row slot, each stopping `inset` px short of its column's edges so the
    rules break at the column boundaries and before the view edge.

    `columns` is a list of (x, width) spans; None means one span across the view.
    """
    if width <= 0:
        return []
    spans = columns or [(0, width)]
    segments = []
    for y in placeholder_rule_rows(height, row_height):
        for x, span in spans:
            x1, x2 = x + inset, x + span - inset - 1
            if x2 - x1 >= 4:
                segments.append((x1, x2, y))
    return segments


def paint_placeholder_rules(viewport, row_height: int = PLACEHOLDER_ROW_H, columns=None):
    painter = QPainter(viewport)
    painter.setRenderHint(QPainter.Antialiasing, False)
    pen = QPen(QColor(PLACEHOLDER_COLOR))
    pen.setWidth(PLACEHOLDER_LINE_W)
    painter.setPen(pen)
    for x1, x2, y in placeholder_rules(viewport.width(), viewport.height(), row_height, columns):
        painter.drawLine(x1, y, x2, y)
    painter.end()


class PlaceholderTableWidget(QTableWidget):
    """QTableWidget that rules its empty rows, column by column."""

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
        paint_placeholder_rules(self.viewport(), row_height, columns)


class PlaceholderListWidget(QListWidget):
    """QListWidget that rules its empty rows."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() > 0:
            return
        paint_placeholder_rules(self.viewport())
