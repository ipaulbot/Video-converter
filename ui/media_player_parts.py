"""Small Qt building blocks for the Media Player tab."""
import os

from PyQt5.QtCore import QCoreApplication, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui import theme
from ui.glyph_icons import make_icon_button
from ui.inspection_widget import InspectionWidget
from ui.list_placeholder import PlaceholderTableWidget
from ui.media_player_support import PlaylistModel


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
        # No title row: the panel caption under the tile already names the
        # clip, so the dock is just the Summary / JSON data.
        self.inspector = InspectionWidget(self, notify_preview=False, compact=True)
        self.inspector.layout().setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.inspector, 1)

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


class _OffsetDelegate(QStyledItemDelegate):
    """Edits the Offset column with a seconds spin box."""

    def createEditor(self, parent, _option, _index):
        spin = QDoubleSpinBox(parent)
        spin.setRange(-PlaylistModel.OFFSET_LIMIT_S, PlaylistModel.OFFSET_LIMIT_S)
        spin.setSingleStep(0.1)
        spin.setDecimals(1)
        spin.setSuffix(_tr(" s"))
        return spin

    def setEditorData(self, editor, index):
        editor.setValue(float(index.data(Qt.UserRole) or 0.0))

    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, float(editor.value()), Qt.UserRole)


class PlaylistTable(PlaceholderTableWidget):
    """Columns Clip, Panel, Offset with drag-to-reorder rows.

    The path rides on the clip cell's UserRole, the offset (seconds) on the
    offset cell's. Panel lists the panels currently showing the clip and is
    hidden while only one panel is on screen. `rows_moved(source_row,
    destination_row)` fires on an internal drop; `offset_edited(path,
    seconds)` when the Offset cell commits.
    """

    rows_moved = pyqtSignal(int, int)
    offset_edited = pyqtSignal(str, float)
    CLIP, PANEL, OFFSET = 0, 1, 2

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels([_tr("Clip"), _tr("Panel"), _tr("Offset")])
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.CLIP, QHeaderView.Stretch)
        header.setSectionResizeMode(self.PANEL, QHeaderView.Fixed)
        header.resizeSection(self.PANEL, 56)
        header.setSectionResizeMode(self.OFFSET, QHeaderView.Fixed)
        header.resizeSection(self.OFFSET, 76)
        self.setColumnHidden(self.PANEL, True)
        self.setStyleSheet(theme.list_box_style())   # grey box, not Qt's black frame
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(24)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.setItemDelegateForColumn(self.OFFSET, _OffsetDelegate(self))
        self.itemChanged.connect(self._on_item_changed)

    # -- QListWidget-shaped helpers the dock and its tests lean on -----------
    def count(self):
        return self.rowCount()

    def item(self, row, column=0):
        return super().item(row, column)

    def setCurrentRow(self, row):
        self.setCurrentCell(row, self.CLIP)

    def add_row(self, path, offset_s, panels=()):
        row = self.rowCount()
        self.insertRow(row)
        clip = QTableWidgetItem(os.path.basename(path) or path)
        clip.setToolTip(path)
        clip.setData(Qt.UserRole, path)
        clip.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
        panel = QTableWidgetItem(", ".join(str(number) for number in panels))
        panel.setTextAlignment(Qt.AlignCenter)
        panel.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        panel.setToolTip(_tr("Panels showing this clip right now."))
        offset = QTableWidgetItem(format_offset_seconds(offset_s))
        offset.setData(Qt.UserRole, float(offset_s))
        offset.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        offset.setToolTip(_tr("Sync offset: shift this clip earlier (negative) or later "
                              "(positive) against the other panels. Double-click to edit."))
        self.setItem(row, self.CLIP, clip)
        self.setItem(row, self.PANEL, panel)
        self.setItem(row, self.OFFSET, offset)

    def _on_item_changed(self, item):
        if item.column() != self.OFFSET or self.signalsBlocked():
            return
        clip = self.item(item.row(), self.CLIP)
        if clip is None:
            return
        self.offset_edited.emit(str(clip.data(Qt.UserRole)), float(item.data(Qt.UserRole) or 0.0))

    def dropEvent(self, event):
        if event.source() is not self or not event.mimeData().hasFormat(
            "application/x-qabstractitemmodeldatalist"
        ):
            super().dropEvent(event)
            return
        rows = sorted({index.row() for index in self.selectedIndexes()})
        if len(rows) != 1:
            event.ignore()
            return
        target = self.indexAt(event.pos()).row()
        if target < 0:
            target = self.rowCount() - 1
        elif self.dropIndicatorPosition() == QAbstractItemView.BelowItem and target < rows[0]:
            target += 1
        elif self.dropIndicatorPosition() == QAbstractItemView.AboveItem and target > rows[0]:
            target -= 1
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        if target != rows[0]:
            self.rows_moved.emit(rows[0], target)


def format_offset_seconds(seconds):
    value = float(seconds or 0.0)
    return f"{value:+.1f} s" if value else "0.0 s"


class PlaylistDock(QWidget):
    """Playlist for one panel: a reorderable list plus Add/Remove/Clear controls.

    Vertical (default): a side column with the buttons in a row underneath.
    `horizontal=True`: a short strip for under the video -- title on top, the
    list beside a column of buttons -- with no width limits.
    """

    activate_requested = pyqtSignal(str)
    files_requested = pyqtSignal()
    folder_requested = pyqtSignal()
    offset_changed = pyqtSignal(str, float)
    current_changed = pyqtSignal(str)       # highlighted row's path ("" when none)
    STRIP_HEIGHT = 150

    def __init__(self, parent=None, horizontal=False):
        super().__init__(parent)
        self.model = None
        self.panel_lookup = None            # path -> [panel numbers showing it]
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
        self.list = PlaylistTable(self)      # Clip | Offset, faint rows while empty
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list.rows_moved.connect(self._on_row_moved)
        self.list.offset_edited.connect(self._on_offset_edited)
        self.list.currentCellChanged.connect(self._on_current_cell_changed)
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

    def set_panel_lookup(self, lookup):
        """`lookup(path)` -> panel numbers showing that clip; fills the Panel column."""
        self.panel_lookup = lookup
        self.refresh()

    def set_panel_column_visible(self, visible):
        self.list.setColumnHidden(PlaylistTable.PANEL, not visible)

    def refresh(self):
        had_current = self.list.currentRow() >= 0
        self.list.blockSignals(True)
        self.list.setRowCount(0)
        for path in (self.model.items if self.model else []):
            panels = self.panel_lookup(path) if callable(self.panel_lookup) else ()
            self.list.add_row(path, self.model.offset_for(path), panels)
        self.list.blockSignals(False)
        if had_current and self.list.currentRow() < 0:
            self.current_changed.emit("")

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

    def current_path(self):
        row = self.list.currentRow()
        item = self.list.item(row, PlaylistTable.CLIP) if row >= 0 else None
        return str(item.data(Qt.UserRole)) if item is not None else ""

    def _on_current_cell_changed(self, row, _col, previous_row, _prev_col):
        if row != previous_row:
            self.current_changed.emit(self.current_path())

    def _on_item_double_clicked(self, item):
        if item.column() != PlaylistTable.CLIP:
            return          # the Offset cell opens its editor instead
        self.activate_requested.emit(str(item.data(Qt.UserRole)))

    def _on_row_moved(self, source, destination):
        if self.model is None:
            return
        self.model.move(source, destination)
        self.refresh()
        self.list.setCurrentRow(destination)

    def _on_offset_edited(self, path, seconds):
        if self.model is None:
            return
        self.model.set_offset(path, seconds)
        self.refresh()
        self.select_path(path)
        self.offset_changed.emit(path, self.model.offset_for(path))

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
