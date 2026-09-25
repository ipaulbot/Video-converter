"""Small Qt building blocks for the Media Player tab."""
import os

from PyQt5.QtCore import QCoreApplication, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui import theme


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


class PlaylistDock(QWidget):
    """Playlist for one panel: a reorderable list plus Add/Remove/Clear controls."""

    activate_requested = pyqtSignal(str)
    files_requested = pyqtSignal()
    folder_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.setAcceptDrops(True)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.title_label = QLabel(_tr("Playlist"))
        self.title_label.setStyleSheet(theme.group_title_style())
        layout.addWidget(self.title_label)
        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self.add_files_btn = QPushButton(_tr("Add files..."))
        self.add_folder_btn = QPushButton(_tr("Add folder..."))
        self.remove_btn = QPushButton(_tr("Remove"))
        self.clear_btn = QPushButton(_tr("Clear"))
        for button in (
            self.add_files_btn,
            self.add_folder_btn,
            self.remove_btn,
            self.clear_btn,
        ):
            button.setCursor(Qt.PointingHandCursor)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.add_files_btn.clicked.connect(self.files_requested.emit)
        self.add_folder_btn.clicked.connect(self.folder_requested.emit)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear)

    def set_model(self, model, title):
        self.model = model
        self.title_label.setText(
            _tr("Playlist - %(panel)s") % {"panel": title}
        )
        self.refresh()

    def refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for path in (self.model.items if self.model else []):
            item = QListWidgetItem(os.path.basename(path) or path)
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def add_paths(self, paths):
        if self.model is None:
            return 0
        added = self.model.add(paths)
        self.refresh()
        return added

    def remove_selected(self):
        if self.model is None:
            return
        rows = sorted(
            {index.row() for index in self.list.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self.model.remove(row)
        self.refresh()

    def clear(self):
        if self.model is not None:
            self.model.clear()
        self.refresh()

    def select_path(self, path):
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.UserRole) == path:
                self.list.setCurrentRow(row)
                return

    def _on_item_double_clicked(self, item):
        self.activate_requested.emit(str(item.data(Qt.UserRole)))

    def _on_rows_moved(self, _parent, start, _end, _destination, row):
        if self.model is None:
            return
        destination = row - 1 if row > start else row
        self.model.move(start, destination)
        self.refresh()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.add_paths(
                [
                    url.toLocalFile()
                    for url in event.mimeData().urls()
                    if url.toLocalFile()
                ]
            )
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
