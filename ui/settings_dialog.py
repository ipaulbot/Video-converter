import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QCheckBox,
    QComboBox, QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox,
    QScrollArea, QTabWidget, QTimeEdit, QSpacerItem, QSizePolicy, QWidget, QLayout,
    QSpinBox, QSlider, QToolButton, QStyle
)
from PyQt5.QtCore import QCoreApplication, pyqtSignal, Qt, QTime, QLocale, QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap

from utils.config import default_settings, coerce_retention_days
from utils.logger import logger
from utils.resources import resource_path
from ui.dialogs import EasterEggDialog
from ui.glyph_icons import set_link_glyph
from utils.paths import get_data_dir
from ui import theme



def _tr(source: str) -> str:
    """Translate this module's strings under the stable "SettingsDialog" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("SettingsDialog", source)

class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)
    backup_usage_changed = pyqtSignal(bool)

    def __init__(self, current_settings, parent=None, button_style=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Settings"))
        # Use fixed-size dialog hint (Windows) and compute final size from content later
        self.setWindowFlag(Qt.MSWindowsFixedSizeDialogHint, True)

        # Get the appropriate gear icon based on parent's state
        if parent and hasattr(parent, 'get_icon_path'):
            gear_icon_path = parent.get_icon_path('GEAR')
        else:
            gear_icon_path = resource_path('graphics/GEAR.ico')

        if os.path.exists(gear_icon_path):
            self.setWindowIcon(QIcon(gear_icon_path))
        else:
            self.setWindowIcon(QIcon(resource_path('graphics/GEAR.ico')))

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.current_settings = current_settings
        self.easter_egg_dialog = None
        self.button_style = button_style
        # Derive info icon based on parent state (idle/monitoring/locked)
        self.info_icon_path = self._compute_info_icon_path(parent)

        # Apply modern clean style
        button_style = self.button_style if self.button_style else """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #43a296, stop:1 #3a9284);
                border: 1px solid #2d7d6f;
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 80px;
                min-height: 21px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4bb3a7, stop:1 #43a296);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a9284, stop:1 #2d7d6f);
            }
        """

        # Match the app's state (teal idle, green running, grey locked). This
        # was an eighth copy of that chain, and it asked the parent for
        # `active_conversion_count`, which no longer exists -- the queue owns
        # the count now. The getattr default of 0 meant the green state simply
        # stopped being detected rather than failing, so ask the parent's own
        # predicate instead of re-deriving it here.
        highlight_color = theme.skin_for_state(
            locked=bool(parent is not None and getattr(parent, 'locked', False)),
            active=bool(parent is not None
                        and parent.is_active_workflow_visual_state()),
        ).accent

        modern_stylesheet = f"""
            QWidget {{
                background: #F5F5F5;
                color: #333333;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
            }}
            QDialog {{
                background: #F5F5F5;
            }}
            {button_style}
            QTabWidget::pane {{
                border: 1px solid #E0E0E0;
                background: white;
                border-radius: 8px;
                margin-top: 4px;
            }}
            QTabBar::tab {{
                background: #F0F0F0;
                border: 1px solid #E0E0E0;
                border-bottom: none;
                padding: 4px 8px;
                margin-right: 2px;
                font-weight: normal;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 60px;
            }}
            QTabBar::tab:selected {{
                background: white;
                border-bottom: 2px solid {highlight_color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QCheckBox {{
                background: white;
                border: none;
                padding: 2px;
            }}
            QCheckBox::indicator {{
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 3px;
                width: 16px;
                height: 16px;
            }}
            QCheckBox::indicator:checked {{
                background: {highlight_color};
                border: 1px solid {highlight_color};
            }}
            QCheckBox::indicator:unchecked {{
                background: white;
                border: 1px solid #E0E0E0;
            }}
            QLineEdit, QComboBox {{
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px;
            }}
            QGroupBox {{
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 8px;
                background: white;
                font-size: 9pt;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                color: #333;
            }}
        """
        self.setStyleSheet(modern_stylesheet)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        # Removed custom tab stylesheet since it's now in the main stylesheet

        self.create_general_tab()
        self.create_folders_tab()
        self.create_deletion_tab()
        self.create_conversion_tab()
        self.create_time_tab()
        self.create_tools_tab()

        self.tabs.addTab(self.general_tab, _tr("General"))
        self.tabs.addTab(self.folders_tab, _tr("Folders"))
        self.tabs.addTab(self.deletion_tab, _tr("Deletion"))
        self.tabs.addTab(self.conversion_tab, _tr("Format"))
        self.tabs.addTab(self.time_tab, _tr("Time"))
        self.tabs.addTab(self.tools_tab, _tr("Tools"))

        main_layout.addWidget(self.tabs)
        # Normalize tab heights to avoid pixel drift when switching tabs
        self._normalize_tab_heights(include_conversion_expanded=False)

        # Auto-collapse advanced options when switching away from Format tab
        self.tabs.currentChanged.connect(self._on_tab_changed)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.default_button = QPushButton(_tr("Default"))
        self.default_button.setToolTip(_tr("Reset settings to their default values."))
        self.default_button.setCursor(Qt.PointingHandCursor)
        self.default_button.clicked.connect(self.set_defaults)
        self.default_button.setFixedWidth(90)
        button_layout.addWidget(self.default_button)

        self.ok_button = QPushButton(_tr("OK"))
        self.ok_button.setToolTip(_tr("Save current settings."))
        self.ok_button.setCursor(Qt.PointingHandCursor)
        self.ok_button.clicked.connect(self.save_settings)
        self.ok_button.setFixedWidth(90)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton(_tr("Cancel"))
        self.cancel_button.setToolTip(_tr("Discard changes and close dialog."))
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setFixedWidth(90)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        # Lock dialog size to its sizeHint to avoid tiny size oscillations while dragging
        try:
            main_layout.setSizeConstraint(QLayout.SetFixedSize)
            self.adjustSize()
            self.setFixedSize(self.size())
        except Exception:
            logger.debug("SettingsDialog.init_ui: suppressed error", exc_info=True)

        # Apply button style to all buttons if provided
        if self.button_style:
            self.apply_button_style_to_all_buttons()

    def apply_button_style_to_all_buttons(self):
        """Apply the host's button style to every button in the dialog.

        This used to style default/ok/cancel explicitly and then walk the tree
        and style them a second time. Its walker also had no opt-out at all,
        so any button here with a purpose-built look would have been
        overwritten -- the same defect that was live in the main window.
        """
        return theme.apply_to_buttons(self, self.button_style)

    def apply_button_style_recursively(self, widget):
        """Kept for callers; the traversal lives in theme.apply_to_buttons."""
        return theme.apply_to_buttons(widget, self.button_style)

    def create_general_tab(self):
        self.general_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # General Settings Group
        general_group = QGroupBox(_tr("General Settings"))
        general_layout = QVBoxLayout()
        general_layout.setSpacing(8)
        general_layout.setContentsMargins(10, 10, 10, 10)

        # Add spacing after the group box title
        general_layout.addSpacing(6)

        self.auto_run_checkbox = QCheckBox(_tr("Auto Run on Startup"))
        self.auto_run_checkbox.setToolTip(_tr("Run the application automatically with the previous settings at startup."))
        self.auto_run_checkbox.setChecked(self.current_settings.get('auto_run', False))
        auto_run_info = QLabel(_tr("Automatically start the application with previous settings."))
        auto_run_info.setWordWrap(True)
        auto_run_info.setIndent(20)
        general_layout.addWidget(self.auto_run_checkbox)
        general_layout.addWidget(auto_run_info)

        general_layout.addSpacing(8)

        self.copy_only_checkbox = QCheckBox(_tr("Copy Only"))
        self.copy_only_checkbox.setToolTip(_tr("If enabled, files are copied without converting them."))
        self.copy_only_checkbox.setChecked(self.current_settings.get('copy_only', False))
        self.copy_only_checkbox.stateChanged.connect(self.toggle_copy_only)
        copy_only_info = QLabel(_tr("Copy files without converting them."))
        copy_only_info.setWordWrap(True)
        copy_only_info.setIndent(20)
        general_layout.addWidget(self.copy_only_checkbox)
        general_layout.addWidget(copy_only_info)

        general_layout.addSpacing(8)

        # Close behavior option
        self.close_on_x_checkbox = QCheckBox(_tr("Close on X (don't minimize to tray)"))
        self.close_on_x_checkbox.setToolTip(_tr("Close the application when clicking the window X button instead of minimizing to the system tray."))
        self.close_on_x_checkbox.setChecked(self.current_settings.get('close_on_x', False))
        close_on_x_info = QLabel(_tr("Close the app completely when clicking X."))
        close_on_x_info.setWordWrap(True)
        close_on_x_info.setIndent(20)
        general_layout.addWidget(self.close_on_x_checkbox)
        general_layout.addWidget(close_on_x_info)

        general_layout.addSpacing(8)

        # Startup (All users) option
        self.startup_common_checkbox = QCheckBox(_tr("Launch at Windows startup (All Users)"))
        self.startup_common_checkbox.setToolTip(_tr("Launch the application automatically when Windows starts for all users."))
        self.startup_common_checkbox.setChecked(self.current_settings.get('startup_common', False))
        startup_common_info = QLabel(_tr("Start the app automatically when Windows starts (requires permissions)."))
        startup_common_info.setWordWrap(True)
        startup_common_info.setIndent(20)
        general_layout.addWidget(self.startup_common_checkbox)
        general_layout.addWidget(startup_common_info)

        general_layout.addSpacing(8)

        # GPU Acceleration option
        self.use_gpu_checkbox = QCheckBox(_tr("Use GPU Acceleration"))
        self.use_gpu_checkbox.setToolTip(_tr("Enable GPU acceleration if available."))
        self.use_gpu_checkbox.setChecked(self.current_settings.get('use_gpu', False))
        self.use_gpu_checkbox.stateChanged.connect(self.toggle_gpu_options)
        gpu_info = QLabel(_tr("Enable GPU acceleration for faster encoding (if supported)."))
        gpu_info.setWordWrap(True)
        gpu_info.setIndent(20)
        general_layout.addWidget(self.use_gpu_checkbox)
        general_layout.addWidget(gpu_info)

        # GPU Encoder Dropdown
        gpu_form_layout = QFormLayout()
        gpu_form_layout.setSpacing(8)
        gpu_form_layout.setVerticalSpacing(6)
        gpu_form_layout.setContentsMargins(10, 10, 10, 10)

        # Add spacing after the group box title
        gpu_form_layout.addItem(QSpacerItem(0, 6))

        self.gpu_encoder_combo = QComboBox()
        self.gpu_encoder_combo.addItems(["Auto", "nvidia", "intel", "amd"])
        self.gpu_encoder_combo.setCurrentText(self.current_settings.get('gpu_encoder', "Auto"))
        self.gpu_encoder_combo.setEnabled(self.use_gpu_checkbox.isChecked())
        # Set consistent width for all dropdowns
        self.gpu_encoder_combo.setFixedWidth(90)  # Reduced from 180 to 90 (half width)
        self.gpu_encoder_combo.setStyleSheet("QComboBox { padding: 4px; }")  # Add more padding
        gpu_form_layout.addRow(QLabel(_tr("GPU Encoder:")), self.gpu_encoder_combo)

        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # GPU Settings Group
        gpu_group = QGroupBox(_tr("GPU Settings"))
        gpu_group.setLayout(gpu_form_layout)
        layout.addWidget(gpu_group)

        layout.addStretch()
        self.general_tab.setLayout(layout)

    def create_folders_tab(self):
        self.folders_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Folder Settings Group
        folders_group = QGroupBox(_tr("Folder Settings"))
        folders_layout = QVBoxLayout()
        folders_layout.setSpacing(8)
        folders_layout.setContentsMargins(10, 10, 10, 10)

        # Add spacing after the group box title
        folders_layout.addSpacing(6)

        # Source Folder
        source_layout = QHBoxLayout()
        self.source_label = QLabel(_tr("Source Folder:"))
        self.source_label.setMinimumWidth(100)
        self.source_display = QLineEdit(self.current_settings.get('source_folder', ''))
        self.source_display.setReadOnly(True)
        # Remove gray background styling - use default white background
        self.source_display.setStyleSheet(theme.qss("padding: 4px; background: white; border: 1px solid $separator; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 9pt;"))
        self.source_button = QPushButton(_tr("Change"))
        self.source_button.setFixedWidth(80)
        self.source_button.setCursor(Qt.PointingHandCursor)
        self.source_button.clicked.connect(self.change_source_folder)
        source_layout.addWidget(self.source_label)
        source_layout.addWidget(self.source_display, 1)
        source_layout.addWidget(self.source_button)

        folders_layout.addLayout(source_layout)

        # Destination Folder
        dest_layout = QHBoxLayout()
        self.destination_label = QLabel(_tr("Destination Folder:"))
        self.destination_label.setMinimumWidth(100)
        self.destination_display = QLineEdit(self.current_settings.get('destination_folder', ''))
        self.destination_display.setReadOnly(True)
        # Remove gray background styling - use default white background
        self.destination_display.setStyleSheet(theme.qss("padding: 4px; background: white; border: 1px solid $separator; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 9pt;"))
        self.destination_button = QPushButton(_tr("Change"))
        self.destination_button.setFixedWidth(80)
        self.destination_button.setCursor(Qt.PointingHandCursor)
        self.destination_button.clicked.connect(self.change_destination_folder)
        dest_layout.addWidget(self.destination_label)
        dest_layout.addWidget(self.destination_display, 1)
        dest_layout.addWidget(self.destination_button)

        folders_layout.addLayout(dest_layout)

        # Backup Folder
        backup_layout = QHBoxLayout()
        self.backup_label = QLabel(_tr("Backup Folder:"))
        self.backup_label.setMinimumWidth(100)
        self.backup_display = QLineEdit(self.current_settings.get('backup_folder', ''))
        self.backup_display.setReadOnly(True)
        # Remove gray background styling - use default white background
        self.backup_display.setStyleSheet(theme.qss("padding: 4px; background: white; border: 1px solid $separator; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 9pt;"))
        self.backup_button = QPushButton(_tr("Change"))
        self.backup_button.setFixedWidth(80)
        self.backup_button.setCursor(Qt.PointingHandCursor)
        self.backup_button.clicked.connect(self.change_backup_folder)
        backup_layout.addWidget(self.backup_label)
        backup_layout.addWidget(self.backup_display, 1)
        backup_layout.addWidget(self.backup_button)

        folders_layout.addLayout(backup_layout)

        # Log Folder
        log_layout = QHBoxLayout()
        self.log_label = QLabel(_tr("Log Folder:"))
        self.log_label.setMinimumWidth(100)
        self.log_display = QLineEdit(self.current_settings.get('log_folder', get_data_dir("logs")))
        self.log_display.setReadOnly(True)
        # Remove gray background styling - use default white background
        self.log_display.setStyleSheet(theme.qss("padding: 4px; background: white; border: 1px solid $separator; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 9pt;"))
        self.log_button = QPushButton(_tr("Change"))
        self.log_button.setFixedWidth(80)
        self.log_button.setCursor(Qt.PointingHandCursor)
        self.log_button.clicked.connect(self.change_log_folder)
        log_layout.addWidget(self.log_label)
        log_layout.addWidget(self.log_display, 1)
        log_layout.addWidget(self.log_button)

        folders_layout.addLayout(log_layout)

        # Four identical "Change" bubbles read better with a folder glyph; the
        # text stays because the buttons sit in a form, not a toolbar.
        self.folder_change_buttons = (
            self.source_button, self.destination_button, self.backup_button, self.log_button,
        )
        for button in self.folder_change_buttons:
            set_link_glyph(button, "folder_open", theme.skin().text_on_accent, size=14)
            # The glyph needs room next to the label; keep the four buttons equal.
            button.setFixedWidth(max(80, button.sizeHint().width() + 12))

        folders_group.setLayout(folders_layout)
        layout.addWidget(folders_group)

        layout.addStretch()
        self.folders_tab.setLayout(layout)

    def change_source_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder",
            self.current_settings.get('source_folder', '') or os.path.expanduser("~")
        )
        if folder:
            self.source_display.setText(folder)

    def change_destination_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Destination Folder",
            self.current_settings.get('destination_folder', '') or os.path.expanduser("~")
        )
        if folder:
            self.destination_display.setText(folder)

    def change_backup_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Backup Folder",
            self.current_settings.get('backup_folder', '') or os.path.expanduser("~")
        )
        if folder:
            self.backup_display.setText(folder)

    def change_log_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Log Folder",
            self.current_settings.get('log_folder', get_data_dir("logs")) or os.path.expanduser("~")
        )
        if folder:
            self.log_display.setText(folder)

    def create_deletion_tab(self):
        self.deletion_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Deletion Settings Group
        deletion_group = QGroupBox(_tr("Deletion Settings"))
        deletion_layout = QVBoxLayout()
        deletion_layout.setSpacing(8)
        deletion_layout.setContentsMargins(10, 10, 10, 10)

        # Add spacing after the group box title
        deletion_layout.addSpacing(6)

        self.delete_after_checkbox = QCheckBox(_tr("Delete files after conversion"))
        self.delete_after_checkbox.setToolTip(_tr("If enabled, original files will be deleted after a retention period."))
        self.delete_after_checkbox.setChecked(self.current_settings.get('delete_after_conversion', False))
        self.delete_after_checkbox.stateChanged.connect(self.toggle_retention)
        delete_info = QLabel(_tr("Delete original files after successful conversion."))
        delete_info.setWordWrap(True)
        delete_info.setIndent(20)
        deletion_layout.addWidget(self.delete_after_checkbox)
        deletion_layout.addWidget(delete_info)

        deletion_layout.addSpacing(8)

        retention_form_layout = QFormLayout()
        retention_form_layout.setSpacing(8)
        retention_form_layout.setVerticalSpacing(6)
        retention_form_layout.setContentsMargins(10, 10, 10, 10)

        # Add spacing after the group box title
        retention_form_layout.addItem(QSpacerItem(0, 6))

        self.retention_label = QLabel(_tr("Retention time (days):"))
        self.retention_input = QSpinBox()
        self.retention_input.setRange(0, 30)
        self.retention_input.setValue(coerce_retention_days(self.current_settings.get('retention_time', 0)))
        self.retention_input.setToolTip(_tr("Number of days to keep the original file before deletion."))
        self.retention_label.setEnabled(self.delete_after_checkbox.isChecked())
        self.retention_input.setEnabled(self.delete_after_checkbox.isChecked())
        self.retention_input.valueChanged.connect(self.retention_time_changed)
        self.retention_input.setFixedWidth(80)
        retention_form_layout.addRow(self.retention_label, self.retention_input)
        retention_info = QLabel(_tr("Time in days to retain original files before deletion (0-30)."))
        retention_info.setWordWrap(True)
        retention_info.setIndent(20)
        deletion_layout.addLayout(retention_form_layout)
        deletion_layout.addWidget(retention_info)

        deletion_layout.addSpacing(8)

        self.use_backup_checkbox = QCheckBox(_tr("Use Backup Folder"))
        self.use_backup_checkbox.setToolTip(_tr("If enabled, original files are moved to the backup folder instead of deletion."))
        self.use_backup_checkbox.setChecked(self.current_settings.get('use_backup', False))
        self.use_backup_checkbox.setEnabled(
            not (self.delete_after_checkbox.isChecked() and self.retention_input.value() == 0)
        )
        self.use_backup_checkbox.stateChanged.connect(self.toggle_backup)
        backup_info = QLabel(_tr("Move original files to a backup folder after conversion."))
        backup_info.setWordWrap(True)
        backup_info.setIndent(20)
        deletion_layout.addWidget(self.use_backup_checkbox)
        deletion_layout.addWidget(backup_info)

        deletion_group.setLayout(deletion_layout)
        layout.addWidget(deletion_group)

        layout.addStretch()
        self.deletion_tab.setLayout(layout)

    def toggle_retention(self, state):
        enabled = (state == Qt.Checked)
        self.retention_label.setEnabled(enabled)
        self.retention_input.setEnabled(enabled)
        self.retention_time_changed(self.retention_input.value())

    def retention_time_changed(self, value):
        retention_time = coerce_retention_days(value)
        if self.delete_after_checkbox.isChecked():
            if retention_time == 0:
                self.use_backup_checkbox.setEnabled(False)
                self.use_backup_checkbox.setChecked(False)
                self.backup_usage_changed.emit(False)
            else:
                if not self.use_backup_checkbox.isEnabled():
                    self.use_backup_checkbox.setEnabled(True)
        else:
            if not self.use_backup_checkbox.isEnabled():
                self.use_backup_checkbox.setEnabled(True)

    def trigger_easter_egg(self):
        self.easter_egg_dialog = EasterEggDialog()
        self.easter_egg_dialog.show()
        self.easter_egg_dialog.activateWindow()
        self.easter_egg_dialog.setFocus()

    def toggle_backup(self, state):
        enabled = (state == Qt.Checked)
        self.backup_usage_changed.emit(enabled)

    def create_conversion_tab(self):
        self.conversion_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Increased from 4 to 8 for better separation
        layout.setContentsMargins(12, 12, 12, 12)  # Increased from 8 to 12

        # Basic Format Settings Group
        basic_group = QGroupBox(_tr("Basic Format Settings"))
        basic_layout = QVBoxLayout()
        basic_layout.setSpacing(8)  # Increased from 4 to 8
        basic_layout.setContentsMargins(10, 10, 10, 10)  # Increased from 6 to 10

        # Left column: basic format controls
        basic_form_layout = QFormLayout()
        basic_form_layout.setSpacing(8)
        basic_form_layout.setVerticalSpacing(6)
        basic_form_layout.setContentsMargins(10, 10, 10, 10)
        basic_form_layout.addItem(QSpacerItem(0, 6))

        output_format_label = QLabel(_tr("Output Format:"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(['mp4', 'mov', 'avi', 'mkv', 'flv', 'webm', 'mpeg', 'mpg', '3gp', 'ogg', 'wmv', 'm4v', 'mp3', 'gif'])
        self.output_format_combo.setCurrentText(self.current_settings.get('output_format', 'mp4'))
        self.output_format_combo.currentTextChanged.connect(self.update_codecs)
        self.output_format_combo.setFixedWidth(90)
        self.output_format_combo.setStyleSheet("QComboBox { padding: 4px; }")
        basic_form_layout.addRow(output_format_label, self.output_format_combo)

        video_codec_label = QLabel(_tr("Video Codec:"))
        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(['libx264', 'mpeg4', 'libvpx', 'hevc', 'flv', 'libtheora', 'wmv2'])
        self.video_codec_combo.setCurrentText(self.current_settings.get('video_codec', 'libx264'))
        self.video_codec_combo.setFixedWidth(90)
        self.video_codec_combo.setStyleSheet("QComboBox { padding: 4px; }")
        basic_form_layout.addRow(video_codec_label, self.video_codec_combo)

        audio_codec_label = QLabel(_tr("Audio Codec:"))
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(['aac', 'mp3', 'ac3', 'opus', 'vorbis'])
        self.audio_codec_combo.setCurrentText(self.current_settings.get('audio_codec', 'aac'))
        self.audio_codec_combo.setFixedWidth(90)
        self.audio_codec_combo.setStyleSheet("QComboBox { padding: 4px; }")
        basic_form_layout.addRow(audio_codec_label, self.audio_codec_combo)

        # Right column: GIF options (shown only when GIF is selected)
        from PyQt5.QtWidgets import QSpinBox
        self.gif_panel = QWidget()
        gif_layout = QFormLayout()
        gif_layout.setSpacing(8)
        gif_layout.setVerticalSpacing(6)
        gif_layout.setContentsMargins(0, 0, 0, 0)
        self.gif_fps_spin = QSpinBox()
        self.gif_fps_spin.setRange(1, 60)
        # Safely coerce stored value (may be string like "Auto") to int
        def _coerce_int(value, default_value):
            try:
                return int(value)
            except Exception:
                try:
                    return int(float(str(value).strip()))
                except Exception:
                    return default_value
        self.gif_fps_spin.setValue(_coerce_int(self.current_settings.get('gif_fps', 10), 10))
        self.gif_width_spin = QSpinBox()
        self.gif_width_spin.setRange(64, 4096)
        self.gif_width_spin.setSingleStep(16)
        self.gif_width_spin.setValue(_coerce_int(self.current_settings.get('gif_max_width', 640), 640))
        self.gif_loop_checkbox = QCheckBox(_tr("Loop"))
        self.gif_loop_checkbox.setChecked(self.current_settings.get('gif_loop', True))
        self.gif_quick_checkbox = QCheckBox(_tr("Quick GIF (no palette)"))
        self.gif_quick_checkbox.setChecked(self.current_settings.get('gif_quick', False))
        gif_layout.addRow(QLabel(_tr("FPS:")), self.gif_fps_spin)
        gif_layout.addRow(QLabel(_tr("Max Width:")), self.gif_width_spin)
        gif_layout.addRow(self.gif_loop_checkbox)
        gif_layout.addRow(self.gif_quick_checkbox)
        self.gif_panel.setLayout(gif_layout)

        # Combine into a two-column layout inside the Basic group
        basic_hbox = QHBoxLayout()
        basic_hbox.setSpacing(12)
        basic_hbox.setContentsMargins(10, 10, 10, 10)
        basic_hbox.addLayout(basic_form_layout, 1)
        basic_hbox.addWidget(self.gif_panel, 1)
        self.gif_panel.setVisible(self.output_format_combo.currentText().lower() == 'gif')

        # React to output format change to show/hide GIF options
        def _update_gif_visibility(fmt):
            is_gif = (fmt.lower() == 'gif')
            self.gif_panel.setVisible(is_gif)
        self.output_format_combo.currentTextChanged.connect(_update_gif_visibility)

        basic_group.setLayout(basic_hbox)
        layout.addWidget(basic_group)

        layout.addSpacing(6)  # Increased from 2 to 6

        # Advanced Options Group
        self.advanced_group = QGroupBox(_tr("Advanced Options"))
        advanced_layout = QFormLayout()
        advanced_layout.setSpacing(8)  # Increased from 4 to 8
        advanced_layout.setVerticalSpacing(6)  # Increased from 2 to 6
        advanced_layout.setContentsMargins(10, 10, 10, 10)  # Increased from 6 to 10

        # Add spacing after the group box title
        advanced_layout.addItem(QSpacerItem(0, 6))  # Increased from 4 to 6

        size_label = QLabel(_tr("Video Size:"))
        self.video_size_combo = QComboBox()
        video_sizes = ["Auto", "640x480", "1280x720", "1920x1080", "3840x2160"]
        self.video_size_combo.addItems(video_sizes)
        current_size = self.current_settings.get('video_size', None)
        self.video_size_combo.setCurrentText(current_size if current_size else "Auto")
        self.video_size_combo.setFixedWidth(90)  # Reduced from 180 to 90 (half width)
        self.video_size_combo.setStyleSheet("QComboBox { padding: 4px; }")  # Add more padding
        advanced_layout.addRow(size_label, self.video_size_combo)

        bitrate_label = QLabel(_tr("Bitrate:"))
        self.video_bitrate_combo = QComboBox()
        bitrates = ["Auto", "512k", "1000k", "1200k", "1500k", "2000k", "3000k"]
        self.video_bitrate_combo.addItems(bitrates)
        current_bitrate = self.current_settings.get('video_bitrate', "Auto")
        self.video_bitrate_combo.setCurrentText(current_bitrate)
        self.video_bitrate_combo.setFixedWidth(90)  # Reduced from 180 to 90 (half width)
        self.video_bitrate_combo.setStyleSheet("QComboBox { padding: 4px; }")  # Add more padding
        advanced_layout.addRow(bitrate_label, self.video_bitrate_combo)

        fr_label = QLabel(_tr("Frame Rate:"))
        self.framerate_combo = QComboBox()
        frame_rates = ["Auto", "8", "10", "15", "20", "23.98", "24", "25", "29.97", "30", "60"]
        self.framerate_combo.addItems(frame_rates)
        current_fr = self.current_settings.get('framerate', "Auto")
        self.framerate_combo.setCurrentText(current_fr)
        self.framerate_combo.setFixedWidth(90)  # Reduced from 180 to 90 (half width)
        self.framerate_combo.setStyleSheet("QComboBox { padding: 4px; }")  # Add more padding
        advanced_layout.addRow(fr_label, self.framerate_combo)

        # Keyframe Interval (GOP)
        gop_label = QLabel(_tr("Keyframe Interval (GOP):"))
        self.gop_spin = QSpinBox()
        self.gop_spin.setRange(0, 300)
        self.gop_spin.setSpecialValueText("Auto")
        self.gop_spin.setValue(int(self.current_settings.get('keyframe_interval', 0)))
        self.gop_spin.setToolTip(_tr("Set the Group of Pictures (GOP) size. 0 = Auto. Lower values = better seeking/quality, Higher = better compression."))
        self.gop_spin.setFixedWidth(90)
        advanced_layout.addRow(gop_label, self.gop_spin)

        # Volume Control (spin only to reduce width)
        volume_label = QLabel(_tr("Volume:"))
        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(0, 500)
        self.volume_spin.setValue(int(self.current_settings.get('volume_percentage', 100)))
        self.volume_spin.setSuffix(_tr("%"))
        self.volume_spin.setFixedWidth(90)
        self.volume_spin.setToolTip(_tr("Output audio volume. 100% is unchanged."))
        advanced_layout.addRow(volume_label, self.volume_spin)

        # Text Overlay
        overlay_label = QLabel(_tr("Text Overlay:"))
        self.text_overlay_combo = QComboBox()
        self.text_overlay_combo.addItems([
            "None",
            "Elapsed Time",
            "Recorded Time",
            "Recorded Date/Time",
            "Recorded Date/Time + Remaining",
            "CRTV Cam"
        ])
        # Backwards-compatibility: map old stored values to new labels
        _overlay_old_to_new = {
            "Timestamp": "Elapsed Time",
            "Date/Time": "Recorded Date/Time",
            "CRTV Style": "CRTV Cam",
            "Elapsed Timestamp (top-left)": "Elapsed Time",
            "Recorded Time (top-left)": "Recorded Time",
            "Recorded Date/Time (top-left)": "Recorded Date/Time",
            "Recorded Date/Time + Remaining (top-left)": "Recorded Date/Time + Remaining",
            "CRTV Cam (Recorded, top-left)": "CRTV Cam",
        }
        current_overlay = self.current_settings.get('text_overlay', "None")
        current_overlay = _overlay_old_to_new.get(current_overlay, current_overlay)
        self.text_overlay_combo.setCurrentText(current_overlay)
        self.text_overlay_combo.setToolTip(
            _tr("Burns text onto the output video.\n"
            "Recorded options use the file's recorded time if present; otherwise file modified time.")
        )
        self.text_overlay_combo.setFixedWidth(150)
        try:
            self.text_overlay_combo.view().setMinimumWidth(180)
        except Exception:
            logger.debug("SettingsDialog.create_conversion_tab: suppressed error", exc_info=True)
        advanced_layout.addRow(overlay_label, self.text_overlay_combo)

        # Console Integration (moved into Advanced)
        console_group = QGroupBox(_tr("Console Integration"))
        console_layout = QVBoxLayout()
        console_layout.setContentsMargins(10, 10, 10, 10)

        console_info = QLabel(_tr("Custom FFmpeg flags (for advanced users):"))
        console_info.setStyleSheet(theme.qss("color: $grey_650; font-style: italic;"))

        # Row for input + help button
        cmd_layout = QHBoxLayout()
        cmd_layout.setContentsMargins(0,0,0,0)

        self.custom_command_edit = QLineEdit(self.current_settings.get('custom_console_command', ''))
        self.custom_command_edit.setPlaceholderText(_tr("-preset slow -profile:v high"))
        self.custom_command_edit.setToolTip(_tr("Enter raw FFmpeg arguments here. These will be appended to the command."))

        self.console_help_btn = QToolButton()
        self.console_help_btn.setIcon(QIcon(self.info_icon_path))
        self.console_help_btn.setIconSize(QSize(18, 18))
        self.console_help_btn.setFixedSize(28, 28)  # match main window icon buttons
        self.console_help_btn.setCursor(Qt.PointingHandCursor)
        self.console_help_btn.setToolTip(_tr("Show help for custom commands"))
        self.console_help_btn.clicked.connect(self.show_console_help)
        # Borderless to match main window icon buttons
        self.console_help_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QToolButton:hover {
                background: rgba(0,0,0,0.04);
            }
            QToolButton:pressed {
                background: rgba(0,0,0,0.08);
            }
        """)
        # Exclude from global button styling
        self.console_help_btn.setProperty('skipGlobalStyle', True)

        cmd_layout.addWidget(self.custom_command_edit)
        cmd_layout.addWidget(self.console_help_btn)

        console_layout.addWidget(console_info)
        console_layout.addLayout(cmd_layout)
        console_group.setLayout(console_layout)
        advanced_layout.addRow(console_group)

        self.advanced_group.setLayout(advanced_layout)
        # Collapsible advanced section to keep dialog compact
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText(_tr("Show Advanced Options"))
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setArrowType(Qt.RightArrow)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_toggle.clicked.connect(lambda checked: self._toggle_advanced(checked))
        layout.addWidget(self.advanced_toggle)
        self.advanced_group.setVisible(False)
        layout.addWidget(self.advanced_group)

        # Preset Management Group - compact layout
        preset_group = QGroupBox(_tr("Presets"))
        preset_layout = QVBoxLayout()
        preset_layout.setSpacing(6)
        preset_layout.setContentsMargins(10, 10, 10, 10)
        preset_layout.addSpacing(4)

        # Horizontal layout for preset buttons to save space
        preset_buttons_layout = QHBoxLayout()
        preset_buttons_layout.setSpacing(6)

        # Ethovision preset button
        ethovision_button = QPushButton(_tr("Ethovision"))
        ethovision_button.setCursor(Qt.PointingHandCursor)
        ethovision_button.clicked.connect(self.apply_ethovision_preset)
        ethovision_button.setToolTip(_tr("Apply Ethovision-optimized settings (MP4, H.264, 1920x1080, 25fps)"))
        preset_buttons_layout.addWidget(ethovision_button)

        # Custom preset 1 button
        self.custom1_button = QPushButton(_tr("Custom 1"))
        self.custom1_button.setCursor(Qt.PointingHandCursor)
        self.custom1_button.clicked.connect(lambda: self.apply_custom_preset(1))
        self.custom1_button.setToolTip(_tr("Apply Custom Preset 1"))
        preset_buttons_layout.addWidget(self.custom1_button)

        # Custom preset 2 button
        self.custom2_button = QPushButton(_tr("Custom 2"))
        self.custom2_button.setCursor(Qt.PointingHandCursor)
        self.custom2_button.clicked.connect(lambda: self.apply_custom_preset(2))
        self.custom2_button.setToolTip(_tr("Apply Custom Preset 2"))
        preset_buttons_layout.addWidget(self.custom2_button)

        preset_layout.addLayout(preset_buttons_layout)

        # Save preset buttons layout
        save_preset_layout = QHBoxLayout()
        save_preset_layout.setSpacing(6)

        save1_button = QPushButton(_tr("Save to 1"))
        save1_button.setCursor(Qt.PointingHandCursor)
        save1_button.clicked.connect(lambda: self.save_custom_preset(1))
        save1_button.setToolTip(_tr("Save current settings to Custom Preset 1"))
        save_preset_layout.addWidget(save1_button)

        save2_button = QPushButton(_tr("Save to 2"))
        save2_button.setCursor(Qt.PointingHandCursor)
        save2_button.clicked.connect(lambda: self.save_custom_preset(2))
        save2_button.setToolTip(_tr("Save current settings to Custom Preset 2"))
        save_preset_layout.addWidget(save2_button)

        preset_layout.addLayout(save_preset_layout)

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        self.toggle_copy_only(self.copy_only_checkbox.isChecked())
        layout.addStretch()

        self.conversion_tab.setLayout(layout)

    def show_console_help(self):
        msg = QMessageBox(self)
        msg.setWindowTitle(_tr("Console Command Help"))
        msg.setText(
            _tr("Custom FFmpeg Flags Tutorial:\n\n"
            "You can enter raw FFmpeg flags here to override or extend defaults.\n\n"
            "Examples:\n"
            "• -preset slow  (Better compression, slower speed)\n"
            "• -tune animation  (Optimize for cartoons/screencasts)\n"
            "• -movflags +faststart  (Optimize MP4 for web streaming)\n"
            "• -metadata title=\"My Video\"  (Add metadata)\n\n"
            "Note: These flags are appended to the command. "
            "Conflicts with other settings may cause conversion failure.")
        )
        msg.setIconPixmap(QPixmap(self.info_icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        msg.setWindowIcon(QIcon(self.info_icon_path))
        msg.exec_()

    def create_time_tab(self):
        self.time_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Time Settings Group
        time_group = QGroupBox(_tr("Time Settings"))
        time_layout = QVBoxLayout()
        time_layout.setSpacing(8)
        time_layout.setContentsMargins(10, 10, 10, 10)

        # Add spacing after the group box title
        time_layout.addSpacing(6)

        time_info = QLabel(_tr("Restrict conversion to specific times of the day."))
        time_info.setWordWrap(True)
        time_info.setIndent(20)

        self.no_time_restrictions_checkbox = QCheckBox(_tr("No Time Restrictions"))
        self.no_time_restrictions_checkbox.setChecked(self.current_settings.get('no_time_restrictions', True))
        self.no_time_restrictions_checkbox.setToolTip(_tr("If enabled, conversions can occur at any time."))
        self.no_time_restrictions_checkbox.toggled.connect(self.toggle_time_restrictions)

        locale = QLocale()
        system_time_format = locale.timeFormat(QLocale.ShortFormat)
        time_display_format = 'hh:mm AP' if 'AP' in system_time_format or 'ap' in system_time_format else 'HH:mm'

        time_selection_layout = QHBoxLayout()
        start_time_label = QLabel(_tr("Start Time:"))
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat(time_display_format)
        self.start_time_edit.setTime(QTime.fromString(self.current_settings.get('start_time', '00:00'), "HH:mm"))
        self.start_time_edit.setToolTip(_tr("Conversions will not start before this time if restrictions enabled."))
        end_time_label = QLabel(_tr("End Time:"))
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat(time_display_format)
        self.end_time_edit.setTime(QTime.fromString(self.current_settings.get('end_time', '23:59'), "HH:mm"))
        self.end_time_edit.setToolTip(_tr("Conversions will not occur after this time if restrictions enabled."))

        time_selection_layout.addWidget(start_time_label)
        time_selection_layout.addWidget(self.start_time_edit)
        time_selection_layout.addSpacing(20)
        time_selection_layout.addWidget(end_time_label)
        time_selection_layout.addWidget(self.end_time_edit)
        time_selection_layout.addStretch()

        time_layout.addWidget(time_info)
        time_layout.addWidget(self.no_time_restrictions_checkbox)
        time_layout.addLayout(time_selection_layout)
        self.toggle_time_restrictions(self.no_time_restrictions_checkbox.isChecked())

        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        # Spacer to push image to the bottom area of the tab
        layout.addStretch()

        # Add time image below the group box, over the gray area, at full image size
        try:
            parent = self.parent()
            is_monitoring = False
            if parent is not None:
                # Same stale attribute as above; use the parent's predicate.
                is_monitoring = bool(parent is not None
                                     and parent.is_active_workflow_visual_state())
            image_path = resource_path('graphics/greentime.png') if is_monitoring else resource_path('graphics/tealtime.png')
            if os.path.exists(image_path):
                self.time_image_label = QLabel()
                pix = QPixmap(image_path)  # full size
                self.time_image_label.setPixmap(pix)
                self.time_image_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
                self.time_image_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.time_image_label.setStyleSheet("background: transparent; border: none;")
                layout.addWidget(self.time_image_label, 0, Qt.AlignRight | Qt.AlignBottom)
        except Exception:
            logger.debug("SettingsDialog.create_time_tab: suppressed error", exc_info=True)

        self.time_tab.setLayout(layout)

    def create_tools_tab(self):
        self.tools_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        group = QGroupBox(_tr("Main Window Tool Tabs"))
        group_layout = QVBoxLayout()
        group_layout.setSpacing(8)
        group_layout.setContentsMargins(10, 14, 10, 10)

        intro = QLabel(
            _tr("Choose which tools appear as tabs in the main window. Hidden tools stay available here and can be shown again any time.")
        )
        intro.setWordWrap(True)
        group_layout.addWidget(intro)

        visible_tabs = self.current_settings.get('visible_tool_tabs', default_settings.get('visible_tool_tabs', {}))
        self.tool_tab_checkboxes = {}
        labels = [
            ("video_converter", _tr("Video Converter")),
            ("media_player", _tr("Media Player")),
            ("multi_source_recorder", _tr("Multi-Source Recorder")),
            ("lossless_editor", _tr("Lossless Editor")),
            ("pc_report", _tr("PC Report")),
        ]
        for key, label in labels:
            checkbox = QCheckBox(label)
            checkbox.setChecked(bool(visible_tabs.get(key, default_settings["visible_tool_tabs"].get(key, False))))
            if key in ("video_converter", "media_player"):
                checkbox.setToolTip(_tr("Visible by default. You can hide it, but keeping core workflow tabs visible is recommended."))
            else:
                checkbox.setToolTip(_tr("Show this optional tool as a main-window tab."))
            self.tool_tab_checkboxes[key] = checkbox
            group_layout.addWidget(checkbox)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        self.tools_tab.setLayout(layout)

    def create_behavior_tab(self):
        from PyQt5.QtWidgets import QFormLayout
        self.behavior_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        group = QGroupBox(_tr("Behavior"))
        form = QFormLayout()
        form.setSpacing(8)
        form.setVerticalSpacing(6)
        form.setContentsMargins(10, 10, 10, 10)
        form.addItem(QSpacerItem(0, 6))
        # Close behavior
        self.close_on_x_checkbox = QCheckBox(_tr("Close on X (don't minimize to tray)"))
        self.close_on_x_checkbox.setChecked(self.current_settings.get('close_on_x', False))
        form.addRow(self.close_on_x_checkbox)
        # Startup (All users)
        self.startup_common_checkbox = QCheckBox(_tr("Launch at Windows startup (All Users)"))
        self.startup_common_checkbox.setChecked(self.current_settings.get('startup_common', False))
        form.addRow(self.startup_common_checkbox)
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        self.behavior_tab.setLayout(layout)

    def _toggle_advanced(self, checked):
        """Show/hide advanced options. When shown, allow the tab height to grow."""
        if hasattr(self, 'advanced_group'):
            self.advanced_group.setVisible(checked)
        if hasattr(self, 'advanced_toggle'):
            self.advanced_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            self.advanced_toggle.setText(
                _tr("Hide Advanced Options") if checked
                else _tr("Show Advanced Options"))
        # Recompute tab heights to allow growth when expanded
        self._normalize_tab_heights(include_conversion_expanded=checked)

    def _on_tab_changed(self, index):
        """Collapse advanced options when switching away from the Format tab."""
        try:
            # Check if we have the advanced toggle and if it's currently expanded
            if hasattr(self, 'advanced_toggle') and self.advanced_toggle.isChecked():
                # Get the Format tab index (should be index 3: General, Folders, Deletion, Format, Time)
                format_tab_index = 3
                # If switching away from Format tab, collapse advanced options
                if index != format_tab_index:
                    self.advanced_toggle.setChecked(False)
                    self._toggle_advanced(False)
        except Exception:
            logger.debug("SettingsDialog._on_tab_changed: suppressed error", exc_info=True)

    def toggle_copy_only(self, state):
        # Placeholder: Add any UI changes if "Copy Only" is enabled.
        pass

    def toggle_time_restrictions(self, enabled):
        self.start_time_edit.setEnabled(not enabled)
        self.end_time_edit.setEnabled(not enabled)

    def update_codecs(self, output_format):
        """
        Update the video and audio codec selections based on the chosen output format.
        """
        codec_defaults = {
            'mp4': {'video': 'libx264', 'audio': 'aac'},
            'mov': {'video': 'libx264', 'audio': 'aac'},
            'avi': {'video': 'mpeg4',  'audio': 'mp3'},
            'mkv': {'video': 'libx264', 'audio': 'aac'},
            'flv': {'video': 'libx264', 'audio': 'aac'},
            'webm': {'video': 'libvpx',  'audio': 'vorbis'},
            'mpeg': {'video': 'mpeg4',  'audio': 'mp3'},
            'mpg':  {'video': 'mpeg4',  'audio': 'mp3'},
            '3gp':  {'video': 'mpeg4',  'audio': 'aac'},
            'ogg':  {'video': 'libtheora', 'audio': 'vorbis'},
            'wmv':  {'video': 'wmv2',   'audio': 'wmav2'},
            'm4v':  {'video': 'libx264', 'audio': 'aac'},
            'mp3':  {'video': '',         'audio': 'mp3'}
        }
        fmt = output_format.lower()
        defaults = codec_defaults.get(fmt, {'video': 'libx264', 'audio': 'aac'})
        self.video_codec_combo.setCurrentText(defaults['video'])
        self.audio_codec_combo.setCurrentText(defaults['audio'])

    def toggle_gpu_options(self, state):
        enabled = (state == Qt.Checked)
        self.gpu_encoder_combo.setEnabled(enabled)

    def apply_ethovision_preset(self):
        """Apply optimized settings for Ethovision video analysis."""
        # Set Ethovision-optimized settings
        self.output_format_combo.setCurrentText('mp4')
        self.video_codec_combo.setCurrentText('libx264')
        self.audio_codec_combo.setCurrentText('aac')
        self.video_size_combo.setCurrentText('1920x1080')
        self.video_bitrate_combo.setCurrentText('2000k')
        self.framerate_combo.setCurrentText('25')
        self.text_overlay_combo.setCurrentText('None')

    def get_current_format_settings(self):
        """Get current format settings as a dictionary."""
        settings = {
            'output_format': self.output_format_combo.currentText(),
            'video_codec': self.video_codec_combo.currentText(),
            'audio_codec': self.audio_codec_combo.currentText(),
            'video_size': self.video_size_combo.currentText(),
            'video_bitrate': self.video_bitrate_combo.currentText(),
            'framerate': self.framerate_combo.currentText(),
            'keyframe_interval': self.gop_spin.value(),
            'volume_percentage': self.volume_spin.value(),
            'text_overlay': self.text_overlay_combo.currentText(),
        }
        # Include GIF settings
        try:
            settings['gif_fps'] = int(self.gif_fps_spin.value())
            settings['gif_max_width'] = int(self.gif_width_spin.value())
            settings['gif_loop'] = bool(self.gif_loop_checkbox.isChecked())
            settings['gif_quick'] = bool(self.gif_quick_checkbox.isChecked())
        except Exception:
            logger.debug("SettingsDialog.get_current_format_settings: suppressed error", exc_info=True)
        return settings

    def apply_format_settings(self, settings):
        """Apply format settings from a dictionary."""
        if 'output_format' in settings:
            self.output_format_combo.setCurrentText(settings['output_format'])
        if 'video_codec' in settings:
            self.video_codec_combo.setCurrentText(settings['video_codec'])
        if 'audio_codec' in settings:
            self.audio_codec_combo.setCurrentText(settings['audio_codec'])
        if 'video_size' in settings:
            self.video_size_combo.setCurrentText(settings['video_size'])
        if 'video_bitrate' in settings:
            self.video_bitrate_combo.setCurrentText(settings['video_bitrate'])
        if 'framerate' in settings:
            self.framerate_combo.setCurrentText(settings['framerate'])
        if 'keyframe_interval' in settings:
            self.gop_spin.setValue(int(settings['keyframe_interval']))
        if 'volume_percentage' in settings:
            self.volume_spin.setValue(int(settings['volume_percentage']))
        if 'text_overlay' in settings:
            self.text_overlay_combo.setCurrentText(settings['text_overlay'])
        # GIF settings
        try:
            if 'gif_fps' in settings:
                self.gif_fps_spin.setValue(int(settings['gif_fps']))
            if 'gif_max_width' in settings:
                self.gif_width_spin.setValue(int(settings['gif_max_width']))
            if 'gif_loop' in settings:
                self.gif_loop_checkbox.setChecked(bool(settings['gif_loop']))
            if 'gif_quick' in settings:
                self.gif_quick_checkbox.setChecked(bool(settings['gif_quick']))
        except Exception:
            logger.debug("SettingsDialog.apply_format_settings: suppressed error", exc_info=True)

    def save_custom_preset(self, preset_num):
        """Save current format settings to a custom preset."""
        settings = self.get_current_format_settings()
        # Store in current_settings for persistence
        preset_key = f'custom_preset_{preset_num}'
        self.current_settings[preset_key] = settings
        QMessageBox.information(self, _tr("Preset Saved"),
                               _tr("Current format settings saved to Custom Preset %(number)s.")
                               % {"number": preset_num})

    def apply_custom_preset(self, preset_num):
        """Apply a custom preset."""
        preset_key = f'custom_preset_{preset_num}'
        preset_settings = self.current_settings.get(preset_key)
        if preset_settings:
            self.apply_format_settings(preset_settings)
        else:
            QMessageBox.information(self, _tr("No Preset"),
                                   _tr("Custom Preset %(number)s has not been saved yet.\n\n"
                                       "Configure your desired settings and click 'Save to %(number)s' "
                                       "to create it.")
                                   % {"number": preset_num})

    def set_defaults(self):
        from utils.config import default_settings
        self.current_settings = default_settings.copy()
        self.settings_saved.emit(self.current_settings)
        self.accept()

    def _normalize_tab_heights(self, include_conversion_expanded=False):
        """
        Force all tabs to a common fixed height to prevent subtle resizing when
        switching tabs (especially tabs with extra buttons).
        """
        try:
            tabs = [self.general_tab, self.folders_tab, self.deletion_tab, self.conversion_tab, self.time_tab]
            # Optionally measure conversion tab with advanced shown to allow enough height
            conv_extra = 0
            if include_conversion_expanded and hasattr(self, 'advanced_group'):
                prev = self.advanced_group.isVisible()
                self.advanced_group.setVisible(True)
                conv_extra = self.conversion_tab.sizeHint().height()
                self.advanced_group.setVisible(prev)
            max_h = max([t.sizeHint().height() for t in tabs] + ([conv_extra] if conv_extra else []))
            for t in tabs:
                t.setMinimumHeight(max_h)
                t.setMaximumHeight(max_h)
                t.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # Include tab bar height and a small margin and fix the tab widget height
            tabbar_h = self.tabs.tabBar().sizeHint().height() if hasattr(self.tabs, 'tabBar') else 0
            total_h = max_h + tabbar_h + 8
            self.tabs.setMinimumHeight(total_h)
            self.tabs.setMaximumHeight(total_h)
            self.tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        except Exception:
            logger.debug("SettingsDialog._normalize_tab_heights: suppressed error", exc_info=True)

    def _compute_info_icon_path(self, parent=None):
        """
        Pick the correct info icon based on app state:
        - Locked  -> GRAYSCALEINFO.ico
        - Running/monitoring -> GREENINFO.ico
        - Idle/default -> INFO.ico
        """
        try:
            if parent and hasattr(parent, 'get_icon_path'):
                return parent.get_icon_path('INFO')
        except Exception:
            logger.debug("SettingsDialog._compute_info_icon_path: suppressed error", exc_info=True)
        return resource_path('graphics/INFO.ico')

    def save_settings(self):
        self.current_settings['auto_run'] = self.auto_run_checkbox.isChecked()
        self.current_settings['copy_only'] = self.copy_only_checkbox.isChecked()
        self.current_settings['source_folder'] = self.source_display.text()
        self.current_settings['destination_folder'] = self.destination_display.text()
        self.current_settings['backup_folder'] = self.backup_display.text()
        # Persist displayed log folder for UI, though the location is fixed under AppData
        self.current_settings['log_folder'] = self.log_display.text()
        self.current_settings['delete_after_conversion'] = self.delete_after_checkbox.isChecked()
        self.current_settings['retention_time'] = self.retention_input.value()
        self.current_settings['use_backup'] = self.use_backup_checkbox.isChecked()
        self.current_settings['output_format'] = self.output_format_combo.currentText()
        self.current_settings['video_codec'] = self.video_codec_combo.currentText()
        self.current_settings['audio_codec'] = self.audio_codec_combo.currentText()
        self.current_settings['video_size'] = self.video_size_combo.currentText()
        self.current_settings['video_bitrate'] = self.video_bitrate_combo.currentText()
        self.current_settings['framerate'] = self.framerate_combo.currentText()
        # Keyframe Interval
        self.current_settings['keyframe_interval'] = self.gop_spin.value()
        # GIF options
        try:
            self.current_settings['gif_fps'] = int(self.gif_fps_spin.value())
            self.current_settings['gif_max_width'] = int(self.gif_width_spin.value())
            self.current_settings['gif_loop'] = bool(self.gif_loop_checkbox.isChecked())
            self.current_settings['gif_quick'] = bool(self.gif_quick_checkbox.isChecked())
        except Exception:
            logger.debug("SettingsDialog.save_settings: suppressed error", exc_info=True)
        self.current_settings['no_time_restrictions'] = self.no_time_restrictions_checkbox.isChecked()
        self.current_settings['start_time'] = self.start_time_edit.time().toString("HH:mm")
        self.current_settings['end_time'] = self.end_time_edit.time().toString("HH:mm")
        # Behavior
        try:
            self.current_settings['close_on_x'] = bool(self.close_on_x_checkbox.isChecked())
            self.current_settings['startup_common'] = bool(self.startup_common_checkbox.isChecked())
        except Exception:
            logger.debug("SettingsDialog.save_settings: suppressed error", exc_info=True)
        # Save GPU settings
        self.current_settings['use_gpu'] = self.use_gpu_checkbox.isChecked()
        self.current_settings['gpu_encoder'] = self.gpu_encoder_combo.currentText()
        self.current_settings['custom_console_command'] = self.custom_command_edit.text()

        # Save Volume
        try:
            vol = int(self.volume_spin.value())
            self.current_settings['volume_percentage'] = max(0, min(500, vol))  # Cap at 500%
        except Exception:
            self.current_settings['volume_percentage'] = 100

        # Save Overlay
        self.current_settings['text_overlay'] = self.text_overlay_combo.currentText()

        # Save custom presets (already stored in current_settings by save_custom_preset)
        # They will be persisted automatically
        if hasattr(self, 'tool_tab_checkboxes'):
            self.current_settings['visible_tool_tabs'] = {
                key: checkbox.isChecked()
                for key, checkbox in self.tool_tab_checkboxes.items()
            }

        self.settings_saved.emit(self.current_settings)
        self.accept()
