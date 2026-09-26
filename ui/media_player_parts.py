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
from ui.glyph_icons import make_icon_button
from ui.inspection_widget import InspectionWidget


def _tr(source: str) -> str:
    """Translate under the stable "MediaPlayer" context (plain literals only)."""
    return QCoreApplication.translate("MediaPlayer", source)


class InspectionDock(QWidget):
    """ffprobe details for the selected panel's clip, in the slot the Playlist dock uses.

    This is where the Video Inspection Tool tab went on 2026-09-26: the same
    `InspectionWidget` (Summary / Detailed JSON, drag-and-drop) next to the
    video it describes instead of on a tab of its own.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""
        # A floor so the JSON stays readable; no ceiling -- the dock lives in
        # a splitter and scales with the window.
        self.setMinimumWidth(260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.title_label = QLabel(_tr("Inspect"))
        self.title_label.setStyleSheet(theme.group_title_style())
        layout.addWidget(self.title_label)
        self.inspector = InspectionWidget(self, notify_preview=False, compact=True)
        self.inspector.layout().setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.inspector, 1)

    def set_panel_title(self, panel_title):
        self.title_label.setText(_tr("Inspect - %(panel)s") % {"panel": panel_title})

    def inspect_path(self, path):
        """Run ffprobe for `path` unless it is already shown; an empty path clears the dock."""
        path = path or ""
        if path == self.current_path:
            return
        self.current_path = path
        if path:
            self.inspector.inspect_file(path)
        else:
            self.inspector.reset()


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
    """Playlist for one panel: a reorderable list plus Add/Remove/Clear controls.

    Vertical (default): a side column with the buttons in a row underneath.
    `horizontal=True`: a short strip for under the video -- title on top, the
    list beside a column of buttons -- with no width limits.
    """

    activate_requested = pyqtSignal(str)
    files_requested = pyqtSignal()
    folder_requested = pyqtSignal()
    STRIP_HEIGHT = 150

    def __init__(self, parent=None, horizontal=False):
        super().__init__(parent)
        self.model = None
        self.horizontal = bool(horizontal)
        self.setAcceptDrops(True)
        if self.horizontal:
            self.setMaximumHeight(self.STRIP_HEIGHT)
        else:
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
        if self.horizontal:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(self.list, 1)
            buttons = QVBoxLayout()
            row.addLayout(buttons)
            layout.addLayout(row, 1)
        else:
            layout.addWidget(self.list, 1)
            buttons = QHBoxLayout()
        buttons.setSpacing(4)
        accent = theme.skin().accent
        self.add_files_btn = make_icon_button(
            "add_file", _tr("Add files..."), accent, size=24
        )
        self.add_folder_btn = make_icon_button(
            "add_folder", _tr("Add folder..."), accent, size=24
        )
        self.remove_btn = make_icon_button(
            "remove", _tr("Remove selected"), accent, size=24
        )
        self.clear_btn = make_icon_button(
            "clear", _tr("Clear playlist"), accent, size=24
        )
        if not self.horizontal:
            buttons.addStretch(1)
        for button in (
            self.add_files_btn,
            self.add_folder_btn,
            self.remove_btn,
            self.clear_btn,
        ):
            buttons.addWidget(button)
        if self.horizontal:
            buttons.addStretch(1)
        else:
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


class UnsupportedOverlay(QWidget):
    """Inline message shown when the Windows backend cannot decode a file."""

    convert_requested = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            theme.qss(
                "background: rgba(0, 0, 0, 180); color: white; "
                "border-radius: 6px;"
            )
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet(
            "color: white; font-size: 12px; background: transparent;"
        )
        layout.addWidget(self.message_label)
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet(
            "color: white; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self.progress_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.convert_btn = QPushButton(
            _tr("Convert to MP4 (H.264) and play")
        )
        self.convert_btn.setStyleSheet(theme.accent_button_style())
        self.convert_btn.setCursor(Qt.PointingHandCursor)
        self.convert_btn.clicked.connect(self.convert_requested.emit)
        self.dismiss_btn = QPushButton(_tr("Dismiss"))
        self.dismiss_btn.setStyleSheet(theme.secondary_button_style())
        self.dismiss_btn.setCursor(Qt.PointingHandCursor)
        self.dismiss_btn.clicked.connect(self.dismissed.emit)
        buttons.addWidget(self.convert_btn)
        buttons.addWidget(self.dismiss_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.hide()

    def reset(self):
        self.progress_label.setText("")
        self.convert_btn.setEnabled(True)

    def show_message(self, text):
        self.reset()
        self.message_label.setText(text)
        self.show()
        self.raise_()

    def show_progress(self, percent):
        self.convert_btn.setEnabled(False)
        self.progress_label.setText(
            _tr("Converting... %(percent)s%%") % {"percent": int(percent)}
        )

    def show_error(self, text):
        self.convert_btn.setEnabled(True)
        self.progress_label.setText(
            _tr("Conversion failed: %(error)s") % {"error": text}
        )
