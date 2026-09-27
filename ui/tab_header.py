"""The one header every tool tab starts with: a glyph, the tab's title and a line
of description. Before 2026-09-26 each tab had its own -- the PC Report a logo,
the Media Player a plain title, the recorder nothing at all."""
from __future__ import annotations

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.glyph_icons import glyph_icon


class TabHeader(QWidget):
    """Callers pass already-translated title / description strings."""

    GLYPH_PX = 36
    COMPACT_WIDTH = 180
    COMPACT_SPACING = 4
    COMPACT_TITLE_PX = 16
    COMPACT_DESCRIPTION_MIN_H = 42  # three lines of the 9 pt description

    def __init__(self, glyph: str, title: str, description: str = "", parent=None,
                 compact: bool = False):
        """`compact` is the sidebar variant: glyph beside the title, the
        description wrapped underneath, at the sidebar's 180 px width (since
        2026-09-27 the one header lives there and describes the current tab,
        instead of one per tab). Call reserve_for() with every heading it
        may show so its height is fixed."""
        super().__init__(parent)
        self.glyph_name = glyph
        self.compact = compact
        self.reserved = False
        # A stack so something can slide under the glyph (drawn first).
        self.glyph_stack = QGridLayout()
        self.glyph_stack.setContentsMargins(0, 0, 0, 0)
        self.glyph_label = QLabel()
        self.glyph_label.setFixedSize(self.GLYPH_PX, self.GLYPH_PX)
        self.glyph_label.setAlignment(Qt.AlignCenter)
        self.glyph_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.glyph_stack.addWidget(self.glyph_label, 0, 0, Qt.AlignCenter)

        self.title_label = QLabel(title)
        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))

        if compact:
            # Glyph and title share the top line; the description wraps
            # underneath, left-aligned. The reserve_for() call fixes the
            # heights so the preview leaf below never moves between tabs.
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(self.COMPACT_SPACING)
            top_line = QHBoxLayout()
            top_line.setContentsMargins(0, 0, 0, 0)
            top_line.setSpacing(self.COMPACT_SPACING * 2)
            top_line.addLayout(self.glyph_stack, 0)
            top_line.setAlignment(self.glyph_stack, Qt.AlignVCenter)
            self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.title_label.setWordWrap(True)
            top_line.addWidget(self.title_label, 1)
            layout.addLayout(top_line)
            self.description_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.description_label.setMinimumHeight(self.COMPACT_DESCRIPTION_MIN_H)
            layout.addWidget(self.description_label)
            self.setFixedWidth(self.COMPACT_WIDTH)
        else:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            # Top-aligned, not centred: a description that wraps to two lines
            # must not push the glyph lower.
            layout.addLayout(self.glyph_stack, 0)
            layout.setAlignment(self.glyph_stack, Qt.AlignTop)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(1)
            text.addWidget(self.title_label)
            text.addWidget(self.description_label)
            layout.addLayout(text, 1)
        self.reskin()

    def reskin(self, accent: str | None = None):
        """Repaint the glyph and title in the current skin's accent (or `accent`)."""
        accent = accent or theme.skin().accent
        self.glyph_label.setPixmap(
            glyph_icon(self.glyph_name, accent, self.GLYPH_PX).pixmap(self.GLYPH_PX, self.GLYPH_PX)
        )
        title_style = theme.tab_title_style().replace(theme.skin().accent, accent)
        if self.compact:
            # One step smaller beside the glyph so most titles fit the line.
            title_style = title_style.replace("font-size: 18px", f"font-size: {self.COMPACT_TITLE_PX}px")
        self.title_label.setStyleSheet(title_style)
        self.description_label.setStyleSheet(theme.tab_description_style())

    def reserve_for(self, headings):
        """Compact only: fix the title and description heights to the tallest
        of `headings` (pairs of title, description) so swapping headings never
        changes the header's height -- the preview leaf under it stays put."""
        if not self.compact:
            return
        self.ensurePolished()
        self.title_label.ensurePolished()
        self.description_label.ensurePolished()
        title_w = self.COMPACT_WIDTH - self.GLYPH_PX - self.COMPACT_SPACING * 2
        title_h = max(
            [self._wrapped_height(self.title_label, title, title_w) for title, _ in headings]
            + [self.GLYPH_PX]
        )
        description_h = max(
            [self._wrapped_height(self.description_label, text, self.COMPACT_WIDTH) for _, text in headings]
            + [self.COMPACT_DESCRIPTION_MIN_H]
        )
        self.title_label.setFixedHeight(title_h)
        self.description_label.setFixedHeight(description_h)
        self.description_label.setVisible(True)
        self.reserved = True
        self.setFixedHeight(title_h + self.COMPACT_SPACING + description_h)

    @staticmethod
    def _wrapped_height(label, text: str, width: int) -> int:
        metrics = label.fontMetrics()
        flags = Qt.TextWordWrap | int(label.alignment())
        return metrics.boundingRect(QRect(0, 0, width, 4000), flags, text).height()

    def set_description(self, text: str):
        self.description_label.setText(text)
        # A reserved header keeps the (blank) label so the layout holds.
        self.description_label.setVisible(bool(text) or self.reserved)

    def set_heading(self, glyph: str, title: str, description: str = ""):
        """Swap glyph, title and description at once (a tab lending its
        header to something else, e.g. the converter to BallBuster)."""
        self.glyph_name = glyph
        self.title_label.setText(title)
        self.set_description(description)
        self.reskin()

    def add_layer_under_glyph(self, widget):
        """Stack `widget` beneath the glyph (same cell, drawn first)."""
        self.glyph_stack.addWidget(widget, 0, 0, Qt.AlignCenter)
        self.glyph_label.raise_()
