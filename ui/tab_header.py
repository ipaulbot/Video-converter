"""The one header every tool tab starts with: a glyph, the tab's title and a line
of description. Before 2026-09-26 each tab had its own -- the PC Report a logo,
the Media Player a plain title, the recorder nothing at all."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.glyph_icons import glyph_icon


class TabHeader(QWidget):
    """Callers pass already-translated title / description strings."""

    GLYPH_PX = 36

    def __init__(self, glyph: str, title: str, description: str = "", parent=None):
        super().__init__(parent)
        self.glyph_name = glyph
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        # A stack so a tab can slide something under the glyph (the PC
        # Report's pulsing heart shows through the monitor's screen).
        self.glyph_stack = QGridLayout()
        self.glyph_stack.setContentsMargins(0, 0, 0, 0)
        self.glyph_label = QLabel()
        self.glyph_label.setFixedSize(self.GLYPH_PX, self.GLYPH_PX)
        self.glyph_label.setAlignment(Qt.AlignCenter)
        self.glyph_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.glyph_stack.addWidget(self.glyph_label, 0, 0, Qt.AlignCenter)
        # Top-aligned, not centred: a description that wraps to two lines
        # must not push this tab's glyph lower than the other tabs'.
        layout.addLayout(self.glyph_stack, 0)
        layout.setAlignment(self.glyph_stack, Qt.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        self.title_label = QLabel(title)
        text.addWidget(self.title_label)
        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        text.addWidget(self.description_label)
        layout.addLayout(text, 1)
        self.reskin()

    def reskin(self, accent: str | None = None):
        """Repaint the glyph and title in the current skin's accent (or `accent`)."""
        accent = accent or theme.skin().accent
        self.glyph_label.setPixmap(
            glyph_icon(self.glyph_name, accent, self.GLYPH_PX).pixmap(self.GLYPH_PX, self.GLYPH_PX)
        )
        self.title_label.setStyleSheet(
            theme.tab_title_style().replace(theme.skin().accent, accent)
        )
        self.description_label.setStyleSheet(theme.tab_description_style())

    def set_description(self, text: str):
        self.description_label.setText(text)
        self.description_label.setVisible(bool(text))

    def add_layer_under_glyph(self, widget):
        """Stack `widget` beneath the glyph (same cell, drawn first)."""
        self.glyph_stack.addWidget(widget, 0, 0, Qt.AlignCenter)
        self.glyph_label.raise_()
