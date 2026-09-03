from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QMessageBox, QHeaderView,
    QTextEdit, QDialog, QHBoxLayout, QPushButton, QLabel, QAbstractItemView, QStyledItemDelegate,
    QStyleOptionViewItem, QApplication, QStyle
)
from PyQt5.QtCore import pyqtSignal, Qt
import os
import subprocess


class _NoElideDelegate(QStyledItemDelegate):
    """Force no text eliding so full paths stay visible (clip instead of 'C...')."""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.textElideMode = Qt.ElideNone

    def paint(self, painter, option, index):
        option.textElideMode = Qt.ElideNone
        super().paint(painter, option, index)

class _ClipPrefixDelegate(QStyledItemDelegate):
    """Render the first characters that fit (no ellipsis), while preserving selection styling."""

    @staticmethod
    def _fit_prefix(text: str, fm, max_width: int) -> str:
        if max_width <= 0 or not text:
            return ""
        # Fast path
        if fm.horizontalAdvance(text) <= max_width:
            return text
        # Binary search for max prefix that fits
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fm.horizontalAdvance(text[:mid]) <= max_width:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo]

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # Get the actual text data from the model
        display_text = index.data(Qt.DisplayRole) or ""

        # Estimate available width for text inside the item rect
        # Account for padding (left + right margins + selection indicator space)
        padding = 24
        avail = max(0, opt.rect.width() - padding)

        # Manually truncate to fit
        fitted_text = self._fit_prefix(display_text, opt.fontMetrics, avail)

        # CRITICAL: Clear the text from opt so Qt doesn't draw it
        opt.text = ""
        opt.features &= ~QStyleOptionViewItem.HasDisplay

        # Draw the control with selection/background first (without text)
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        # Now draw the fitted text manually on top
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget)
        painter.save()
        painter.setPen(opt.palette.color(opt.palette.Text if not (opt.state & QStyle.State_Selected) else opt.palette.HighlightedText))
        painter.drawText(text_rect, opt.displayAlignment, fitted_text)
        painter.restore()

class ConvertedFilesWidget(QWidget):
    file_converted_signal = pyqtSignal(str, dict, str, bool)  # file_name, deletion_info, destination_folder, success
    preview_requested = pyqtSignal(str)  # emit file path when selection changes
    drop_files_signal = pyqtSignal(list)  # emit list of file paths dropped onto the table

    def __init__(self, parent=None, button_style=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Store per-file logs under the unified AppData\NVC\logs folder
        try:
            from utils.paths import get_data_dir
            self.log_folder = get_data_dir("logs")
        except Exception:
            self.log_folder = os.path.expanduser("~")
        self.button_style = button_style
        self.init_ui()

    def set_log_folder(self, folder):
        self.log_folder = folder

    def init_ui(self):
        layout = QVBoxLayout()
        # No margins - they are set at the tab level
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create a container widget similar to conversion log
        from PyQt5.QtWidgets import QFrame
        self.table_container = QFrame()
        self.table_container.setFrameStyle(QFrame.Box)
        self.table_container.setStyleSheet("QFrame { border: 1px solid #E0E0E0; border-radius: 6px; background: white; }")

        # Create a layout for the container
        container_layout = QVBoxLayout(self.table_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Create clear button
        self.clear_button = QPushButton("Clear")
        clear_button = self.clear_button
        clear_button.setFixedSize(60, 24)
        clear_button.setCursor(Qt.PointingHandCursor)

        # Use provided button style or default transparent style
        if self.button_style:
            clear_button.setStyleSheet(self.button_style)
        else:
            clear_button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    font-size: 12px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: #f8f9fa;
                }
            """)
        clear_button.clicked.connect(self.clear_table)
        clear_button.setProperty('skipGlobalStyle', True)
        clear_button.hide()

        self.table_widget = QTableWidget(0, 3)
        self.table_widget.setHorizontalHeaderLabels(["File Name", "Destination Folder", "Date Modified"])
        self.table_widget.setSelectionBehavior(self.table_widget.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_widget.setEditTriggers(self.table_widget.NoEditTriggers)
        # We do our own path shortening; disable automatic elide
        self.table_widget.setTextElideMode(Qt.ElideNone)
        # Render the first characters that fit (no ellipsis) for both filename + destination columns
        self._clip_prefix_delegate = _ClipPrefixDelegate(self.table_widget)
        self.table_widget.setItemDelegate(self._clip_prefix_delegate)
        self.table_widget.setItemDelegateForColumn(0, self._clip_prefix_delegate)
        self.table_widget.setItemDelegateForColumn(1, self._clip_prefix_delegate)

        # Make table more compact by setting size policy
        from PyQt5.QtWidgets import QSizePolicy
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Set minimum height to make table more compact
        self.table_widget.setMinimumHeight(50)
        header = self.table_widget.horizontalHeader()
        # Don't let long filenames steal all width and force the destination into "C:..."
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(140)
        try:
            header.resizeSection(0, 240)
            header.resizeSection(1, 420)
        except Exception:
            pass

        # Add clear button to table corner widget to eliminate spacing
        # self.table_widget.setCornerWidget(clear_button)

        # Style the table with minimal internal spacing
        self.table_widget.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
                border-radius: 0px;
                gridline-color: #dee2e6;
                margin: 0px;
                padding: 0px;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #dee2e6;
            }
            QTableWidget::item:selected {
                background: #e9ecef;
            }
            QHeaderView::section {
                background: #f8f9fa;
                padding: 4px 12px;
                border: 1px solid #dee2e6;
                font-weight: bold;
                font-size: 12px;
                color: #6c757d;
            }
            QAbstractScrollArea::corner {
                background: white;
            }
        """)

        # Add table to container
        container_layout.addWidget(self.table_widget)

        # Add container to main layout
        layout.addWidget(self.table_container)
        self.setLayout(layout)
        self.file_converted_signal.connect(self.add_converted_file)
        self.table_widget.doubleClicked.connect(self.open_file_location)
        self.table_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.table_widget.selectionModel().selectionChanged.connect(self._handle_selection_changed)

    # Basic drag-and-drop support; parent handles the actual conversion logic.
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        file_paths = [url.toLocalFile() for url in urls]
        self.drop_files_signal.emit(file_paths)
        event.acceptProposedAction()

    def add_queued_file(self, file_name, destination_folder=None):
        """Add a file to the table as queued (⏳)."""
        if destination_folder is None:
            destination_folder = os.getcwd()
        file_name_only = os.path.basename(file_name)
        row = self.find_row_by_file_name(file_name_only)
        if row is not None:
            # Already in table, just update status
            self.update_file_status(file_name_only, 'queued')
            return
        row = self.table_widget.rowCount()
        self.table_widget.insertRow(row)
        status_icon = "⏳"
        file_item = QTableWidgetItem(f"{status_icon} {file_name_only}")
        file_item.setToolTip(file_name_only)
        file_item.setForeground(Qt.darkYellow)
        self.table_widget.setItem(row, 0, file_item)
        dest_item = QTableWidgetItem(destination_folder)
        dest_item.setToolTip(destination_folder)
        self.table_widget.setItem(row, 1, dest_item)
        self.table_widget.setItem(row, 2, QTableWidgetItem("-"))
        self.table_widget.item(row, 0).setData(Qt.UserRole, os.path.join(destination_folder, file_name_only))

    def update_file_status(self, file_name, status, date_str=None):
        """Update the status icon for a file in the table. Status: 'queued', 'processing', 'success', 'failure'.
        Should only be called from the main thread or via Qt signals."""
        try:
            file_name_only = os.path.basename(file_name)
            # Try exact (case-insensitive) match first; fallback to base-name match
            row = self.find_row_by_file_name(file_name_only)
            if row is None:
                row = self._find_row_by_base_name(os.path.splitext(file_name_only)[0])
            if row is None:
                return
            if status == 'queued':
                icon = "⏳"
                color = Qt.darkYellow
            elif status == 'processing':
                icon = "🔄"
                color = Qt.blue
            elif status == 'success':
                icon = "✅"
                color = Qt.darkGreen
            elif status == 'failure':
                icon = "❌"
                color = Qt.darkRed
            else:
                icon = ""
                color = Qt.black
            file_item = self.table_widget.item(row, 0)
            # For completion, show the output filename to normalize extension/case; otherwise keep existing label
            if status in ("success", "failure"):
                rest = file_name_only
            else:
                old_text = file_item.text()
                if ' ' in old_text:
                    _, rest = old_text.split(' ', 1)
                else:
                    rest = old_text
            file_item.setText(f"{icon} {rest}")
            # Always show full filename on hover (exclude icon)
            file_item.setToolTip(rest)
            file_item.setForeground(color)
            if date_str is not None:
                self.table_widget.setItem(row, 2, QTableWidgetItem(date_str))
            # Force table refresh
            self.table_widget.viewport().update()
        except Exception as e:
            import traceback
            print(f"Exception in update_file_status: {e}\n{traceback.format_exc()}")

    def find_row_by_file_name(self, file_name):
        # Perform case-insensitive comparison to avoid duplicate rows for
        # names that differ only by extension/file name casing (e.g., .MP4 vs .mp4)
        target = (file_name or "").lower()
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 0)
            if item is None:
                continue
            text = item.text()
            # Remove icon if present
            if ' ' in text:
                _, name = text.split(' ', 1)
            else:
                name = text
            if name.lower() == target:
                return row
        return None

    def _find_row_by_base_name(self, base_name):
        """Find a row by base name (filename without extension), case-insensitive.
        Useful when input and output extensions differ (e.g., MOV -> MP4).
        """
        target = (base_name or "").lower()
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 0)
            if item is None:
                continue
            text = item.text()
            if ' ' in text:
                _, name = text.split(' ', 1)
            else:
                name = text
            root, _ext = os.path.splitext(name)
            if root.lower() == target:
                return row
        return None

    def add_converted_file(self, file_name, deletion_info, destination_folder=None, success=True):
        """Add or update a file in the table as converted. Should only be called from the main thread or via Qt signals."""
        try:
            output_file = file_name
            if destination_folder is None:
                destination_folder = os.getcwd()
            output_file_path = os.path.join(destination_folder, output_file)
            file_name_only = os.path.basename(output_file)
            # Get date modified
            if os.path.exists(output_file_path):
                date_modified = os.path.getmtime(output_file_path)
                from datetime import datetime
                date_str = datetime.fromtimestamp(date_modified).strftime('%Y-%m-%d %H:%M')
            else:
                date_str = "N/A"
            # Try exact match; if not found, match by base name (handles MOV->MP4, case)
            row = self.find_row_by_file_name(file_name_only)
            if row is None:
                row = self._find_row_by_base_name(os.path.splitext(file_name_only)[0])
            if row is not None:
                # Update status/icon in place
                self.update_file_status(file_name_only, 'success' if success else 'failure', date_str)
                # Ensure the stored file path points to the actual output file location
                self.table_widget.item(row, 0).setData(Qt.UserRole, output_file_path)
                try:
                    self.table_widget.item(row, 0).setToolTip(file_name_only)
                except Exception:
                    pass
                # Refresh destination/path display
                try:
                    dest_item = self.table_widget.item(row, 1)
                    if dest_item:
                        dest_item.setText(destination_folder)
                        dest_item.setToolTip(destination_folder)
                except Exception:
                    pass
            else:
                row = self.table_widget.rowCount()
                self.table_widget.insertRow(row)
                status_icon = "✅" if success else "❌"
                file_name_with_icon = f"{status_icon} {file_name_only}"
                file_item = QTableWidgetItem(file_name_with_icon)
                file_item.setToolTip(file_name_only)
                if success:
                    file_item.setForeground(Qt.darkGreen)
                else:
                    file_item.setForeground(Qt.darkRed)
                self.table_widget.setItem(row, 0, file_item)
                dest_item = QTableWidgetItem(destination_folder)
                dest_item.setToolTip(destination_folder)
                self.table_widget.setItem(row, 1, dest_item)
                date_item = QTableWidgetItem(date_str)
                date_item.setToolTip(date_str)
                self.table_widget.setItem(row, 2, date_item)
                self.table_widget.item(row, 0).setData(Qt.UserRole, output_file_path)
                # Force table refresh
                self.table_widget.viewport().update()
            # Write per-file log
            if not os.path.exists(self.log_folder):
                os.makedirs(self.log_folder, exist_ok=True)
            log_path = os.path.join(self.log_folder, file_name + '.txt')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f'File Name: {file_name_only}\n')
                f.write(f'Destination Folder: {destination_folder}\n')
                f.write(f'Date Modified: {date_str}\n')
                f.write(f'Status: {"Success" if success else "Failed"}\n')
        except Exception as e:
            import traceback
            print(f"Exception in add_converted_file: {e}\n{traceback.format_exc()}")

    def open_file_location(self, index):
        row = index.row()
        file_item = self.table_widget.item(row, 0)
        file_path = file_item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            folder = os.path.dirname(os.path.abspath(file_path))
            try:
                if os.name == 'nt':
                    subprocess.Popen(['explorer', '/select,', os.path.abspath(file_path)])
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', folder])
            except Exception as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Could not open file location: {e}")
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "File Not Found", f"File does not exist: {file_path}")

    def show_context_menu(self, pos):
        index = self.table_widget.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        file_item = self.table_widget.item(row, 0)
        file_path = file_item.data(Qt.UserRole)
        dest_folder = self.table_widget.item(row, 1).text()
        menu = QMenu(self)
        open_folder_action = menu.addAction("Open Containing Folder")
        open_log_action = menu.addAction("Open Log File")
        copy_action = menu.addAction("Copy File Path")
        menu.addSeparator()
        settings_action = menu.addAction("Settings")
        action = menu.exec_(self.table_widget.viewport().mapToGlobal(pos))
        if action == open_folder_action:
            self.open_folder(dest_folder)
        elif action == open_log_action:
            self.open_log_file(file_path)
        elif action == copy_action:
            try:
                from PyQt5.QtWidgets import QApplication
                QApplication.clipboard().setText(file_path or "")
            except Exception:
                pass
        elif action == settings_action:
            # Access parent window's show_settings method
            parent_window = self.parent()
            while parent_window is not None:
                if hasattr(parent_window, 'show_settings') and callable(parent_window.show_settings):
                    parent_window.show_settings()
                    break
                parent_window = parent_window.parent()

    def open_folder(self, folder_path):
        if os.path.exists(folder_path):
            try:
                if os.name == 'nt':
                    subprocess.Popen(['explorer', folder_path])
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', folder_path])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open folder: {e}")
        else:
            QMessageBox.warning(self, "Folder Not Found", f"Folder does not exist: {folder_path}")

    def open_log_file(self, file_path):
        # Look for log in self.log_folder
        import os
        file_name_only = os.path.basename(file_path)
        log_txt = os.path.join(self.log_folder, file_name_only + '.txt')
        log_log = os.path.join(self.log_folder, file_name_only + '.log')
        log_file = None
        if os.path.exists(log_txt):
            log_file = log_txt
        elif os.path.exists(log_log):
            log_file = log_log
        if log_file:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Log for {os.path.basename(file_path)}")
            dlg.resize(600, 400)
            layout = QVBoxLayout(dlg)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(content)
            layout.addWidget(text_edit)
            btn_box = QHBoxLayout()
            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(dlg.accept)
            btn_box.addStretch()
            btn_box.addWidget(ok_btn)
            layout.addLayout(btn_box)
            dlg.exec_()
        else:
            QMessageBox.information(self, "Log Not Found", f"No log file found for {os.path.basename(file_path)}.")

    def clear_table(self):
        """Clear the converted files table."""
        self.table_widget.setRowCount(0)
        self.preview_requested.emit("")  # Clear preview on table clear

    def update_button_style(self, new_style):
        """Update the clear button style"""
        if hasattr(self, 'table_widget') and self.table_widget.cornerWidget():
            self.table_widget.cornerWidget().setStyleSheet(new_style)

    def clear_logs(self):
        # Delete all .txt logs in the log folder
        if os.path.exists(self.log_folder):
            for fname in os.listdir(self.log_folder):
                if fname.endswith('.txt'):
                    try:
                        os.remove(os.path.join(self.log_folder, fname))
                    except Exception:
                        pass

    def closeEvent(self, event):
        self.clear_logs()
        event.accept()

    def _handle_selection_changed(self, selected, deselected):
        """Emit preview signal when a row is selected."""
        try:
            indexes = self.table_widget.selectionModel().selectedRows()
            if not indexes:
                self.preview_requested.emit("")
                return
            row = indexes[0].row()
            file_item = self.table_widget.item(row, 0)
            file_path = file_item.data(Qt.UserRole)
            if file_path:
                self.preview_requested.emit(file_path)
        except Exception:
            pass

    def _format_path_for_display(self, path, max_chars=0):
        """Return full path; kept for future custom formatting."""
        return path or ""
