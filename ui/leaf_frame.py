"""A card with VIO's leaf silhouette: rounded top-left and bottom-right corners."""

from PyQt5.QtWidgets import QFrame, QVBoxLayout

from ui import theme


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
