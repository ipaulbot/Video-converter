"""A label that elides instead of widening its parent.

A plain QLabel's minimum width is the width of its whole text, so a long clip
name under a Media Player tile forces the tab wider than the window (the
Inspect dock then hides behind a horizontal scroll bar). This label paints its
text elided in the middle to whatever width the layout gives it, reports a
small minimum, and offers the full text as tooltip while anything is cut.
"""
from PyQt5.QtCore import QCoreApplication, QSize, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QSizePolicy, QWidget


def _tr(source: str) -> str:
    """Translate under the stable "ElidedLabel" context (plain literals only)."""
    return QCoreApplication.translate("ElidedLabel", source)


class ElidedLabel(QWidget):
    MIN_W = 48

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = str(text)
        self._alignment = Qt.AlignLeft | Qt.AlignVCenter
        self._explicit_tooltip = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._sync_tooltip()

    # --- QLabel-like API -------------------------------------------------------
    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)
        self.updateGeometry()
        self._sync_tooltip()
        self.update()

    def alignment(self):
        return self._alignment

    def setAlignment(self, alignment):
        self._alignment = alignment
        self.update()

    def setToolTip(self, text):
        """An explicit tooltip wins; otherwise the full text shows while elided."""
        self._explicit_tooltip = str(text or "")
        self._sync_tooltip()

    # --- sizing ------------------------------------------------------------------
    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self._text) + 4, metrics.height() + 2)

    def minimumSizeHint(self):
        return QSize(self.MIN_W, self.fontMetrics().height() + 2)

    def elided_text(self):
        return self.fontMetrics().elidedText(
            self._text, Qt.ElideMiddle, max(0, self.contentsRect().width())
        )

    def _sync_tooltip(self):
        if self._explicit_tooltip:
            tooltip = self._explicit_tooltip
        elif self.elided_text() != self._text:
            tooltip = self._text
        else:
            tooltip = ""
        super().setToolTip(tooltip)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_tooltip()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.contentsRect(), int(self._alignment), self.elided_text())
