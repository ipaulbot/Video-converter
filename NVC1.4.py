import os
import subprocess
import threading
import json
import sys
import time
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QAction,
    QDialog, QCheckBox, QLineEdit, QComboBox, QSystemTrayIcon, QStyle, QMenu,
    QPlainTextEdit, QFrame, QSizePolicy, QGroupBox, QFormLayout, QScrollArea
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer

# -------------------- Global Variables and Functions -------------------- #

# Define paths and ensure necessary directories exist
app_data_folder = os.path.join(
    os.getenv('APPDATA', os.path.expanduser("~")),
    'VideoConverterApp'
)
os.makedirs(app_data_folder, exist_ok=True)

settings_file = 'settings.json'
settings_path = os.path.join(app_data_folder, settings_file)
log_file_path = os.path.join(app_data_folder, 'conversion_log.txt')

# Setup rotating log file
logger = logging.getLogger('VideoConverterLogger')
logger.setLevel(logging.INFO)
log_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5)  # 5 MB max size, 5 backups
formatter = logging.Formatter('%(asctime)s - %(message)s')
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        logger.warning(f"Resource file '{relative_path}' not found at path '{full_path}'.")
    return full_path

def save_settings(settings):
    """
    Save settings to a JSON file.
    """
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=4)

def load_settings():
    """
    Load settings from a JSON file. Return default settings if file doesn't exist.
    """
    default_settings = {
        'source_folder': '',
        'destination_folder': '',
        'backup_folder': '',
        'auto_run': False,
        'delete_after_conversion': False,
        'retention_time': 0,
        'use_backup': False,
        'output_format': 'mp4',
        'video_codec': 'libx264',
        'audio_codec': 'aac'
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Settings file is corrupted. Loading default settings.")
            return default_settings
    else:
        return default_settings

class LogEmitter(QObject):
    """
    Emits log messages to be displayed in the GUI.
    """
    log_signal = pyqtSignal(str)

def log_message(message, emitter=None):
    """
    Log messages to both the log file and emit to the GUI (if emitter is provided).
    """
    logger.info(message)
    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    if emitter:
        emitter.log_signal.emit(log_entry)
    else:
        print(log_entry)

def get_supported_encoders():
    """
    Detect supported GPU encoders available in the current FFMPEG build.
    Returns a dictionary with encoder information.
    """
    try:
        # Retrieve the list of supported encoders
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        else:
            startupinfo = None
            creationflags = 0

        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        encoders = result.stdout.lower()
        supported = {}

        # Check for NVIDIA NVENC
        if 'h264_nvenc' in encoders or 'hevc_nvenc' in encoders:
            supported['nvidia'] = {'h264': 'h264_nvenc', 'hevc': 'hevc_nvenc'}

        # Check for Intel QSV
        if 'h264_qsv' in encoders or 'hevc_qsv' in encoders:
            supported['intel'] = {'h264': 'h264_qsv', 'hevc': 'hevc_qsv'}

        # Check for AMD VCE/VCN
        if 'h264_amf' in encoders or 'hevc_amf' in encoders:
            supported['amd'] = {'h264': 'h264_amf', 'hevc': 'hevc_amf'}

        return supported
    except subprocess.CalledProcessError as e:
        logger.error(f"Error detecting supported encoders: {e.stderr}")
        return {}

# -------------------- Settings Dialog -------------------- #

class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)
    backup_usage_changed = pyqtSignal(bool)  # Signal to inform main window of backup usage change

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        # Set the window size to 350x520 pixels as per your request
        self.setFixedSize(350, 520)
        self.setWindowIcon(QIcon(resource_path('settings_logo.ico')))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove question mark
        self.current_settings = current_settings
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # General Settings Group
        general_groupbox = QGroupBox("General Settings")
        general_layout = QVBoxLayout()
        general_layout.setSpacing(10)
        general_layout.setContentsMargins(10, 10, 10, 10)

        # Auto Run on Startup
        self.auto_run_checkbox = QCheckBox("Auto Run on Startup")
        self.auto_run_checkbox.setChecked(self.current_settings.get('auto_run', False))

        auto_run_info = QLabel("Automatically start the application with previous settings.")
        auto_run_info.setWordWrap(True)
        auto_run_info.setIndent(20)  # Indent the info text

        general_layout.addWidget(self.auto_run_checkbox)
        general_layout.addWidget(auto_run_info)

        general_groupbox.setLayout(general_layout)
        main_layout.addWidget(general_groupbox)

        # Deletion Settings Group
        deletion_groupbox = QGroupBox("Deletion Settings")
        deletion_layout = QVBoxLayout()
        deletion_layout.setSpacing(10)
        deletion_layout.setContentsMargins(10, 10, 10, 10)

        # Delete after conversion
        self.delete_after_checkbox = QCheckBox("Delete files after conversion")
        self.delete_after_checkbox.setChecked(self.current_settings.get('delete_after_conversion', False))
        self.delete_after_checkbox.stateChanged.connect(self.toggle_retention)

        delete_info = QLabel("Delete original files after successful conversion.")
        delete_info.setWordWrap(True)
        delete_info.setIndent(20)  # Indent the info text

        deletion_layout.addWidget(self.delete_after_checkbox)
        deletion_layout.addWidget(delete_info)

        # Retention time
        retention_form_layout = QFormLayout()
        self.retention_label = QLabel("Retention time (days):")
        self.retention_input = QLineEdit(str(self.current_settings.get('retention_time', 0)))
        self.retention_label.setEnabled(self.delete_after_checkbox.isChecked())
        self.retention_input.setEnabled(self.delete_after_checkbox.isChecked())
        self.retention_input.textChanged.connect(self.retention_time_changed)
        self.retention_input.setMaximumWidth(100)

        retention_form_layout.addRow(self.retention_label, self.retention_input)

        retention_info = QLabel("Time in days to retain original files before deletion (0-30).")
        retention_info.setWordWrap(True)
        retention_info.setIndent(20)

        deletion_layout.addLayout(retention_form_layout)
        deletion_layout.addWidget(retention_info)

        # Use Backup Folder
        self.use_backup_checkbox = QCheckBox("Use Backup Folder")
        self.use_backup_checkbox.setChecked(self.current_settings.get('use_backup', False))
        self.use_backup_checkbox.setEnabled(not (self.delete_after_checkbox.isChecked() and int(self.retention_input.text()) == 0))
        self.use_backup_checkbox.stateChanged.connect(self.toggle_backup)

        backup_info = QLabel("Move original files to a backup folder after conversion.")
        backup_info.setWordWrap(True)
        backup_info.setIndent(20)

        deletion_layout.addWidget(self.use_backup_checkbox)
        deletion_layout.addWidget(backup_info)

        deletion_groupbox.setLayout(deletion_layout)
        main_layout.addWidget(deletion_groupbox)

        # Conversion Settings Group
        conversion_groupbox = QGroupBox("Conversion Settings")
        conversion_layout = QVBoxLayout()
        conversion_layout.setSpacing(10)
        conversion_layout.setContentsMargins(10, 10, 10, 10)

        # Output Format
        output_form_layout = QFormLayout()
        output_format_label = QLabel("Output Format:")
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(['mp4', 'mov', 'avi', 'mkv', 'flv', 'webm', 'mpeg', 'mpg', '3gp', 'ogg', 'wmv', 'm4v'])
        self.output_format_combo.setCurrentText(self.current_settings.get('output_format', 'mp4'))
        self.output_format_combo.currentTextChanged.connect(self.update_codecs)
        self.output_format_combo.setMaximumWidth(150)

        output_form_layout.addRow(output_format_label, self.output_format_combo)

        output_format_info = QLabel("Select the output format for the converted files.")
        output_format_info.setWordWrap(True)
        output_format_info.setIndent(20)

        conversion_layout.addLayout(output_form_layout)
        conversion_layout.addWidget(output_format_info)

        # Video Codec
        video_codec_form_layout = QFormLayout()
        video_codec_label = QLabel("Video Codec:")
        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(['libx264', 'mpeg4', 'libvpx', 'hevc', 'flv', 'mpeg2video', 'h263', 'theora', 'wmv2'])
        self.video_codec_combo.setCurrentText(self.current_settings.get('video_codec', 'libx264'))
        self.video_codec_combo.setMaximumWidth(150)

        video_codec_form_layout.addRow(video_codec_label, self.video_codec_combo)

        video_codec_info = QLabel("Select the video codec for conversion.")
        video_codec_info.setWordWrap(True)
        video_codec_info.setIndent(20)

        conversion_layout.addLayout(video_codec_form_layout)
        conversion_layout.addWidget(video_codec_info)

        # Audio Codec
        audio_codec_form_layout = QFormLayout()
        audio_codec_label = QLabel("Audio Codec:")
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(['aac', 'mp3', 'ac3', 'opus', 'vorbis', 'mp2', 'amr_nb', 'wmav2'])
        self.audio_codec_combo.setCurrentText(self.current_settings.get('audio_codec', 'aac'))
        self.audio_codec_combo.setMaximumWidth(150)

        audio_codec_form_layout.addRow(audio_codec_label, self.audio_codec_combo)

        audio_codec_info = QLabel("Select the audio codec for conversion.")
        audio_codec_info.setWordWrap(True)
        audio_codec_info.setIndent(20)

        conversion_layout.addLayout(audio_codec_form_layout)
        conversion_layout.addWidget(audio_codec_info)

        conversion_groupbox.setLayout(conversion_layout)
        main_layout.addWidget(conversion_groupbox)

        # Add a stretch to prevent group boxes from stretching vertically
        main_layout.addStretch()  # This line ensures group boxes don't expand unnecessarily

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.default_button = QPushButton("Default")
        self.default_button.clicked.connect(self.set_defaults)
        button_layout.addWidget(self.default_button)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def toggle_retention(self, state):
        enabled = state == Qt.Checked
        self.retention_label.setEnabled(enabled)
        self.retention_input.setEnabled(enabled)
        self.retention_time_changed(self.retention_input.text())

    def retention_time_changed(self, text):
        retention_time = int(text) if text.isdigit() else 0
        if self.delete_after_checkbox.isChecked():
            if retention_time == 0:
                # Immediate deletion, disable Use Backup Folder
                self.use_backup_checkbox.setEnabled(False)
                self.use_backup_checkbox.setChecked(False)
                self.backup_usage_changed.emit(False)
            else:
                # Retention time > 0, enable Use Backup Folder
                self.use_backup_checkbox.setEnabled(True)
        else:
            # Delete after conversion is not checked, enable Use Backup Folder
            self.use_backup_checkbox.setEnabled(True)

    def toggle_backup(self, state):
        enabled = state == Qt.Checked
        self.backup_usage_changed.emit(enabled)

    def update_codecs(self, format_selected):
        codec_map = {
            'mp4': {'video': 'libx264', 'audio': 'aac'},
            'mov': {'video': 'libx264', 'audio': 'aac'},
            'avi': {'video': 'mpeg4', 'audio': 'mp3'},
            'mkv': {'video': 'libx264', 'audio': 'aac'},
            'flv': {'video': 'flv', 'audio': 'mp3'},
            'webm': {'video': 'libvpx', 'audio': 'vorbis'},
            'mpeg': {'video': 'mpeg2video', 'audio': 'mp2'},
            'mpg': {'video': 'mpeg2video', 'audio': 'mp2'},
            '3gp': {'video': 'h263', 'audio': 'amr_nb'},
            'ogg': {'video': 'theora', 'audio': 'vorbis'},
            'wmv': {'video': 'wmv2', 'audio': 'wmav2'},
            'm4v': {'video': 'libx264', 'audio': 'aac'},
        }
        codecs = codec_map.get(format_selected, {'video': 'libx264', 'audio': 'aac'})
        self.video_codec_combo.setCurrentText(codecs['video'])
        self.audio_codec_combo.setCurrentText(codecs['audio'])

    def set_defaults(self):
        self.auto_run_checkbox.setChecked(False)
        self.delete_after_checkbox.setChecked(False)
        self.use_backup_checkbox.setChecked(False)
        self.retention_input.setText('0')
        self.output_format_combo.setCurrentText('mp4')
        self.video_codec_combo.setCurrentText('libx264')
        self.audio_codec_combo.setCurrentText('aac')
        self.toggle_retention(False)
        self.backup_usage_changed.emit(False)

    def save_settings(self):
        # Validate retention time
        retention_time = self.retention_input.text()
        if self.delete_after_checkbox.isChecked():
            if not retention_time.isdigit() or not (0 <= int(retention_time) <= 30):
                QMessageBox.critical(self, "Invalid Input", "Retention time must be an integer between 0 and 30.")
                return

        settings = {
            'auto_run': self.auto_run_checkbox.isChecked(),
            'delete_after_conversion': self.delete_after_checkbox.isChecked(),
            'retention_time': int(retention_time) if retention_time.isdigit() else 0,
            'use_backup': self.use_backup_checkbox.isChecked(),
            'output_format': self.output_format_combo.currentText(),
            'video_codec': self.video_codec_combo.currentText(),
            'audio_codec': self.audio_codec_combo.currentText()
        }
        self.settings_saved.emit(settings)
        self.accept()

# -------------------- Confirmation Dialog -------------------- #

class ConfirmationDialog(QDialog):
    def __init__(self, action, icon_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QIcon())
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove question mark
        self.init_ui(action)

    def init_ui(self, action):
        layout = QVBoxLayout()

        text_label = QLabel(f"Are you sure you want to {action} the application?")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignCenter)

        button_box = QHBoxLayout()
        yes_button = QPushButton("Yes")
        no_button = QPushButton("No")
        yes_button.clicked.connect(self.accept)
        no_button.clicked.connect(self.reject)
        button_box.addWidget(yes_button)
        button_box.addWidget(no_button)
        button_box.setAlignment(Qt.AlignCenter)

        layout.addWidget(text_label)
        layout.addLayout(button_box)

        self.setLayout(layout)
        self.setFixedSize(250, 100)

# -------------------- Info Dialog -------------------- #

class InfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Video Converter")
        # Set minimum size for dynamic resizing
        self.setMinimumSize(400, 300)
        self.setWindowIcon(QIcon(resource_path('info_icon.ico')))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove question mark
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        info_text = QLabel()
        info_text.setText(
            "NVC 1.4 monitors a source folder for various video files (e.g., .mp4, .avi, .wmv) and converts them to the specified output format "
            "using FFMPEG. Converted files are saved in the destination folder, ensuring that "
            "no files are deleted from either location unless specified. After conversion, original files can be moved to a backup folder. "
            "The application continuously monitors the source folder for new files and converts them automatically when detected.\n\n"
            "How to use this application:\n"
            "1. Click 'Source Folder' to choose the folder with video files.\n"
            "2. Click 'Destination Folder' to choose where converted files will be saved.\n"
            "3. Click 'Backup Folder' to choose where original files will be moved after conversion.\n"
            "4. Press 'Start/Stop Conversion' to begin monitoring and converting files.\n\n"
            "This application uses FFMPEG for video conversion. You can download the"
            "build of FFMPEG from: https://www.gyan.dev/ffmpeg/builds/\n\n"
            "This application was written in Python. The source code "
            "can be found at: https://github.com/ipaulbot/Video-converter"
        )
        info_text.setWordWrap(True)
        info_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        info_text.setStyleSheet("background-color: transparent; padding: 10px;")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_text)
        layout.addWidget(scroll_area)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

# -------------------- Main Application Window -------------------- #

class VideoConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Converter")
        self.setFixedHeight(300)  # Reduced vertical size by approximately 60%
        self.setMinimumWidth(600)  # Minimum horizontal size
        self.setWindowIcon(QIcon(resource_path('icon.ico')))

        # Initialize attributes
        self.running = False
        self.locked = False
        self.thread = None
        self.stop_event = threading.Event()
        self.status_running = False
        self.settings_window = None  # Reference to the settings window

        # Initialize settings
        self.settings = load_settings()
        self.source_folder = self.settings.get('source_folder', '')
        self.destination_folder = self.settings.get('destination_folder', '')
        self.backup_folder = self.settings.get('backup_folder', '')
        self.auto_run = self.settings.get('auto_run', False)
        self.delete_after_conversion = self.settings.get('delete_after_conversion', False)
        self.retention_time = self.settings.get('retention_time', 0)
        self.use_backup = self.settings.get('use_backup', False)
        self.output_format = self.settings.get('output_format', 'mp4')
        self.video_codec = self.settings.get('video_codec', 'libx264')
        self.audio_codec = self.settings.get('audio_codec', 'aac')

        # Initialize logging state variables
        self.last_scan_message_logged = False
        self.last_no_files_message_logged = False

        # Initialize LogEmitter and connect to GUI
        self.log_emitter = LogEmitter()
        self.log_emitter.log_signal.connect(self.append_log)

        # Initialize active conversion counter
        self.active_conversion_count = 0

        # Setup UI and system tray icon
        self.init_ui()
        self.init_tray_icon()

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Start minimized to the system tray
        self.hide()

        # If auto_run is enabled, start the conversion process automatically
        if self.auto_run and self.source_folder and self.destination_folder:
            QTimer.singleShot(1000, self.start_conversion)  # Delay to allow GUI to initialize

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()

        # Left side UI for control buttons and logo
        left_layout = QVBoxLayout()

        # Buttons
        self.source_button = QPushButton("Source Folder")
        self.source_button.clicked.connect(self.select_source_folder)
        left_layout.addWidget(self.source_button)

        self.destination_button = QPushButton("Destination Folder")
        self.destination_button.clicked.connect(self.select_destination_folder)
        left_layout.addWidget(self.destination_button)

        self.backup_button = QPushButton("Backup Folder")
        self.backup_button.clicked.connect(self.select_backup_folder)
        self.backup_button.setEnabled(self.use_backup)  # Set initial state based on settings
        left_layout.addWidget(self.backup_button)

        # Logo
        logo_path = resource_path('logo.png')
        grayscale_logo_path = resource_path('grayscale_logo.png')  # Path to grayscale logo
        if os.path.exists(logo_path) and os.path.exists(grayscale_logo_path):
            try:
                logo_pixmap = QPixmap(logo_path)
                grayscale_logo_pixmap = QPixmap(grayscale_logo_path)

                # Resize while preserving aspect ratio and adding padding
                logo_pixmap = self.resize_image_preserve_aspect(logo_pixmap, (120, 120))
                grayscale_logo_pixmap = self.resize_image_preserve_aspect(grayscale_logo_pixmap, (120, 120))

                self.logo_label = QLabel()
                self.logo_label.setPixmap(grayscale_logo_pixmap)
                left_layout.addWidget(self.logo_label)
                self.logo_pixmap = logo_pixmap
                self.grayscale_logo_pixmap = grayscale_logo_pixmap
            except Exception as e:
                log_message(f"Error loading logos: {e}", self.log_emitter)
                self.logo_label = QLabel()
        else:
            log_message(f"Logo files not found at paths '{logo_path}' and/or '{grayscale_logo_path}'.", self.log_emitter)
            self.logo_label = QLabel()
        left_layout.addStretch()

        # Start/Stop Button
        self.start_button = QPushButton("Start Conversion")
        self.start_button.clicked.connect(self.toggle_process)
        left_layout.addWidget(self.start_button)

        main_layout.addLayout(left_layout)

        # Right side for status information
        right_layout = QVBoxLayout()

        # Console Output
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        right_layout.addWidget(self.console_output)

        # Status Indicator
        self.status_label = QLabel("Status: Idle     ")  # Added spaces to fix length
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # Align text to the right

        # Set a monospaced font for consistent spacing
        monospaced_font = QFont("Courier New")
        self.status_label.setFont(monospaced_font)

        # Set a fixed width to prevent resizing
        self.status_label.setMinimumWidth(200)  # Adjust as needed
        self.status_label.setMaximumWidth(200)

        # Create a horizontal layout to align the status_label to the right
        status_layout = QHBoxLayout()
        status_layout.addStretch()  # Pushes the status_label to the right
        status_layout.addWidget(self.status_label)
        right_layout.addLayout(status_layout)

        main_layout.addLayout(right_layout)

        central_widget.setLayout(main_layout)

        # Menu Bar
        self.menubar = self.menuBar()
        self.info_action = QAction("Info", self)
        self.info_action.triggered.connect(self.show_info)
        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.show_settings)
        self.lock_action = QAction("Lock", self)
        self.lock_action.triggered.connect(self.toggle_lock)

        self.menubar.addAction(self.info_action)
        self.menubar.addAction(self.settings_action)
        self.menubar.addAction(self.lock_action)

    def append_log(self, message):
        """
        Append log messages to the console output.
        """
        self.console_output.appendPlainText(message)

    def init_tray_icon(self):
        """
        Setup the system tray icon with menu options.
        """
        self.tray_icon = QSystemTrayIcon(self)
        tray_icon_path = resource_path('icon.ico')
        if os.path.exists(tray_icon_path):
            self.tray_icon.setIcon(QIcon(tray_icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            log_message(f"Tray icon not found at path '{tray_icon_path}'. Using default icon.", self.log_emitter)

        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def closeEvent(self, event):
        """
        Override the close event to minimize to tray instead of exiting.
        """
        event.ignore()
        self.hide()

    def select_source_folder(self):
        """
        Open a dialog to select the source folder.
        """
        if not self.locked:
            folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", self.source_folder or os.path.expanduser("~"))
            if folder:
                self.source_folder = folder
                self.settings['source_folder'] = self.source_folder
                save_settings(self.settings)
                log_message(f"Source folder updated: {self.source_folder}", self.log_emitter)

    def select_destination_folder(self):
        """
        Open a dialog to select the destination folder.
        """
        if not self.locked:
            folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.destination_folder or os.path.expanduser("~"))
            if folder:
                self.destination_folder = folder
                self.settings['destination_folder'] = self.destination_folder
                save_settings(self.settings)
                log_message(f"Destination folder updated: {self.destination_folder}", self.log_emitter)

    def select_backup_folder(self):
        """
        Open a dialog to select the backup folder.
        """
        if not self.locked:
            folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder", self.backup_folder or os.path.expanduser("~"))
            if folder:
                self.backup_folder = folder
                self.settings['backup_folder'] = self.backup_folder
                save_settings(self.settings)
                log_message(f"Backup folder updated: {self.backup_folder}", self.log_emitter)

    def toggle_process(self):
        """
        Toggle between starting and stopping the conversion process.
        """
        if self.running:
            self.stop_conversion()
        else:
            self.start_conversion()

    def start_conversion_indicator(self):
        """
        Increment the active conversion counter and update the logo.
        """
        self.active_conversion_count += 1
        self.update_logo()

    def end_conversion_indicator(self):
        """
        Decrement the active conversion counter and update the logo.
        """
        if self.active_conversion_count > 0:
            self.active_conversion_count -= 1
        self.update_logo()

    def update_logo(self):
        """
        Update the logo based on the active conversion state.
        """
        if self.running or self.active_conversion_count > 0:
            if hasattr(self, 'logo_pixmap'):
                self.logo_label.setPixmap(self.logo_pixmap)
        else:
            if hasattr(self, 'grayscale_logo_pixmap'):
                self.logo_label.setPixmap(self.grayscale_logo_pixmap)

    def start_conversion(self):
        """
        Start the video conversion process in a separate thread.
        """
        if not self.source_folder or not self.destination_folder or (self.use_backup and not self.backup_folder):
            log_message("Please select all required folders.", self.log_emitter)
            QMessageBox.critical(self, "Missing Folders", "Please select Source, Destination, and Backup folders (if enabled).")
            return
        self.running = True
        self.stop_event.clear()
        self.start_button.setText("Stop Conversion")
        self.update_logo()  # Update logo immediately
        log_message("Conversion started.", self.log_emitter)

        self.thread = threading.Thread(target=self.run_conversion)
        self.thread.daemon = True
        self.thread.start()

        # Update status label
        self.status_running = True
        self.update_status()

    def stop_conversion(self):
        """
        Stop the video conversion process.
        """
        self.running = False
        self.stop_event.set()
        self.start_button.setText("Start Conversion")
        log_message("Conversion stopped.", self.log_emitter)

        # Update status label
        self.status_running = False
        # Reset to "Status: Idle" with padding
        idle_text = "Status: Idle     "  # Pad with spaces to match length
        self.status_label.setText(idle_text)
        self.update_logo()  # Update logo immediately

    def run_conversion(self):
        """
        Continuously monitor the source folder and convert new videos.
        """
        try:
            while self.running and not self.stop_event.is_set():
                self.convert_videos()
                time.sleep(5)  # Interval between scans
        except Exception as e:
            log_message(f"Error during conversion: {e}", self.log_emitter)
        finally:
            self.stop_event.set()
            self.update_logo()  # Ensure logo is updated
            self.status_running = False
            # Reset to "Status: Idle" with padding
            idle_text = "Status: Idle     "  # Pad with spaces to match length
            self.status_label.setText(idle_text)

    def update_status(self):
        """
        Update the status label with a running indicator.
        Prevents text shifting by maintaining a fixed length for the message.
        """
        def update():
            base_text = "Status: Running"
            max_dots = 3  # Maximum number of dots
            while self.status_running:
                for i in range(max_dots + 1):
                    if not self.status_running:
                        break
                    dots = '.' * i
                    spaces = ' ' * (max_dots - i)
                    indicator = f"{base_text}{dots}{spaces}"
                    self.status_label.setText(indicator)
                    time.sleep(0.5)
            # After stopping, reset to "Status: Idle" with padding
            idle_text = "Status: Idle     "  # Pad with spaces to match length
            self.status_label.setText(idle_text)

        threading.Thread(target=update, daemon=True).start()

    def show_info(self):
        """
        Display the About/Info dialog.
        """
        dialog = InfoDialog(self)
        self.center_dialog(dialog)
        dialog.exec_()

    def show_settings(self):
        """
        Display the Settings dialog.
        """
        if self.locked:
            QMessageBox.warning(self, "Settings Locked", "Settings are locked and cannot be modified.")
            return
        if self.settings_window and self.settings_window.isVisible():
            self.settings_window.activateWindow()
            return
        self.settings_window = SettingsDialog(self.settings, self)
        self.center_dialog(self.settings_window)
        self.settings_window.settings_saved.connect(self.update_settings)
        self.settings_window.backup_usage_changed.connect(self.update_backup_button_state)  # Connect Signal
        self.settings_window.exec_()

    def update_settings(self, new_settings):
        """
        Update settings based on the settings dialog.
        """
        self.settings.update(new_settings)
        save_settings(self.settings)
        self.auto_run = self.settings.get('auto_run', False)
        self.delete_after_conversion = self.settings.get('delete_after_conversion', False)
        self.retention_time = self.settings.get('retention_time', 0)
        self.use_backup = self.settings.get('use_backup', False)
        self.output_format = self.settings.get('output_format', 'mp4')
        self.video_codec = self.settings.get('video_codec', 'libx264')
        self.audio_codec = self.settings.get('audio_codec', 'aac')
        log_message("Settings updated.", self.log_emitter)

        # Update the backup_button state based on 'use_backup'
        self.backup_button.setEnabled(self.use_backup)

    def toggle_lock(self):
        """
        Toggle the lock state of the application, disabling/enabling certain UI elements.
        """
        action = "lock" if not self.locked else "unlock"
        icon_file = 'lock.ico' if not self.locked else 'unlock.ico'  # Updated file names
        icon_path = resource_path(icon_file)

        if not os.path.exists(icon_path):
            log_message(f"Icon file not found at path '{icon_path}'. Using default icon.", self.log_emitter)
            icon_path = None

        dialog = ConfirmationDialog(action, icon_path, self)
        self.center_dialog(dialog)
        reply = dialog.exec_()

        if reply == QDialog.Accepted:
            self.locked = not self.locked
            # Update the menu action text
            self.lock_action.setText("Unlock" if self.locked else "Lock")

            # Disable or enable Settings menu item
            self.settings_action.setEnabled(not self.locked)

            # Disable or enable buttons
            state = False if self.locked else True
            self.source_button.setEnabled(state)
            self.destination_button.setEnabled(state)
            self.backup_button.setEnabled(state)
            # Start/Stop button remains active regardless of lock status
            log_message(f"Application {'locked' if self.locked else 'unlocked'}.", self.log_emitter)

    def update_backup_button_state(self, enabled):
        """
        Enable or disable the backup folder selection button based on the 'Use Backup Folder' checkbox.
        """
        if not self.locked:
            self.backup_button.setEnabled(enabled)
        if not enabled:
            self.backup_folder = ''  # Optionally, clear the backup folder path
            self.settings['backup_folder'] = self.backup_folder
            save_settings(self.settings)
            log_message("Backup folder usage disabled.", self.log_emitter)

    def center_dialog(self, dialog):
        """
        Center a dialog over the main application window.
        """
        qr = dialog.frameGeometry()
        cp = self.frameGeometry().center()
        qr.moveCenter(cp)
        dialog.move(qr.topLeft())

    def resize_image_preserve_aspect(self, pixmap, size):
        """
        Resize a QPixmap while preserving aspect ratio and adding padding if necessary.
        """
        try:
            scaled_pixmap = pixmap.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
            final_pixmap = QPixmap(size[0], size[1])
            final_pixmap.fill(Qt.transparent)
            painter = QPainter(final_pixmap)
            painter.drawPixmap(
                (size[0] - scaled_pixmap.width()) // 2,
                (size[1] - scaled_pixmap.height()) // 2,
                scaled_pixmap
            )
            painter.end()
            return final_pixmap
        except Exception as e:
            log_message(f"Error resizing image: {e}", self.log_emitter)
            return pixmap  # Return original if resizing fails

    def quit_application(self):
        """
        Quit the application gracefully.
        """
        self.running = False
        self.status_running = False
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=5)
        self.tray_icon.hide()
        QApplication.quit()

    # -------------------- Drag and Drop Events -------------------- #

    def dragEnterEvent(self, event):
        """
        Handle drag enter event for drag-and-drop.
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e0e0e0;")  # Change background to indicate drag-over
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """
        Handle drag leave event to reset the background.
        """
        self.setStyleSheet("")

    def dropEvent(self, event):
        """
        Handle drop event for drag-and-drop.
        """
        self.setStyleSheet("")  # Reset background
        urls = event.mimeData().urls()
        dropped_files = [url.toLocalFile() for url in urls]

        # Supported formats
        supported_formats = (
            '.mp4', '.avi', '.wmv', '.mkv', '.flv', '.webm', '.mov', '.mpeg',
            '.mpg', '.m4v', '.3gp', '.ts', '.vob', '.rm', '.rmvb', '.asf',
            '.m2ts', '.mts', '.ogv', '.divx', '.dv', '.f4v', '.mxf', '.nut',
            '.ogm', '.qt', '.tod', '.vro'
        )

        unsupported_files = []
        for file_path in dropped_files:
            if os.path.isfile(file_path) and file_path.lower().endswith(supported_formats):
                self.convert_dropped_file(file_path)
            else:
                unsupported_files.append(file_path)

        if unsupported_files:
            unsupported_list = "\n".join(unsupported_files)
            QMessageBox.warning(self, "Unsupported Files", f"The following files are not supported and were not converted:\n{unsupported_list}")
            log_message(f"Unsupported files dropped:\n{unsupported_list}", self.log_emitter)

    def convert_dropped_file(self, file_path):
        """
        Start conversion for a single dropped file in a separate thread.
        """
        conversion_thread = threading.Thread(target=self._convert_dropped_file_thread, args=(file_path,))
        conversion_thread.daemon = True
        conversion_thread.start()

    def _convert_dropped_file_thread(self, file_path):
        """
        Convert a single dropped file.
        """
        self.start_conversion_indicator()  # Indicate conversion start
        try:
            file_name = os.path.basename(file_path)
            output_file_path = os.path.join(
                self.destination_folder,
                os.path.splitext(file_name)[0] + f'.{self.output_format}'
            )

            # Check if output file already exists
            if os.path.exists(output_file_path):
                log_message(f"Output file already exists: {output_file_path}", self.log_emitter)
                return

            # Preprocess to remux and potentially fix corrupted files
            temp_fixed_file = os.path.join(self.destination_folder, 'fixed_' + file_name)
            preprocess_command = [resource_path('ffmpeg.exe'), '-i', file_path, '-c', 'copy', temp_fixed_file]

            # Setup startupinfo and creationflags to prevent console window and taskbar icon
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            else:
                startupinfo = None
                creationflags = 0

            try:
                log_message(f"Preprocessing: {file_name} to fix potential corruption", self.log_emitter)
                subprocess.run(
                    preprocess_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
            except subprocess.CalledProcessError as e:
                log_message(f"Error preprocessing {file_path}: {e.stderr}", self.log_emitter)
                return

            # Proceed with conversion using GPU if available
            command = self.build_ffmpeg_command(temp_fixed_file, output_file_path)

            try:
                log_message(f"Converting: {file_name}", self.log_emitter)
                if os.name == 'nt':
                    startupinfo_popen = subprocess.STARTUPINFO()
                    startupinfo_popen.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags_popen = subprocess.CREATE_NO_WINDOW
                else:
                    startupinfo_popen = None
                    creationflags_popen = 0

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    startupinfo=startupinfo_popen,
                    creationflags=creationflags_popen
                )
                for line in process.stdout:
                    log_message(line.strip(), self.log_emitter)

                process.wait()
                log_message(f"Successfully converted: {file_name}", self.log_emitter)

                # Move original to backup if needed
                if self.use_backup and self.backup_folder:
                    try:
                        backup_file_path = os.path.join(self.backup_folder, file_name)
                        os.rename(file_path, backup_file_path)
                        log_message(f"Moved {file_name} to backup folder.", self.log_emitter)
                    except OSError as e:
                        log_message(f"Error moving {file_name} to backup folder: {e}", self.log_emitter)

                # Delete original file after conversion if enabled
                if self.delete_after_conversion and not self.use_backup:
                    if self.retention_time > 0:
                        deletion_time = datetime.now() + timedelta(days=self.retention_time)
                        log_message(f"Scheduled deletion for {file_name} at {deletion_time.strftime('%Y-%m-%d %H:%M:%S')}", self.log_emitter)
                        threading.Timer(self.retention_time * 86400, self.delete_file, args=(file_path,)).start()
                    else:
                        self.delete_file(file_path)

            except FileNotFoundError:
                log_message("ffmpeg not found.", self.log_emitter)
            except subprocess.CalledProcessError as e:
                log_message(f"Error converting {file_path}: {e}", self.log_emitter)
            finally:
                # Remove the temporary remuxed file to save space
                if os.path.exists(temp_fixed_file):
                    os.remove(temp_fixed_file)
        finally:
            self.end_conversion_indicator()  # Indicate conversion end

    def update_logo(self):
        """
        Update the logo based on the active conversion state.
        """
        if self.running or self.active_conversion_count > 0:
            if hasattr(self, 'logo_pixmap'):
                self.logo_label.setPixmap(self.logo_pixmap)
        else:
            if hasattr(self, 'grayscale_logo_pixmap'):
                self.logo_label.setPixmap(self.grayscale_logo_pixmap)

    def convert_videos(self):
        """
        Convert new video files found in the source folder.
        """
        if not os.path.exists(self.source_folder) or not os.path.exists(self.destination_folder):
            log_message("Error: Source or destination folder does not exist.", self.log_emitter)
            return

        # Supported input formats
        supported_formats = (
            '.mp4', '.avi', '.wmv', '.mkv', '.flv', '.webm', '.mov', '.mpeg',
            '.mpg', '.m4v', '.3gp', '.ts', '.vob', '.rm', '.rmvb', '.asf',
            '.m2ts', '.mts', '.ogv', '.divx', '.dv', '.f4v', '.mxf', '.nut',
            '.ogm', '.qt', '.tod', '.vro'
        )
        new_files = [
            f for f in os.listdir(self.source_folder)
            if f.lower().endswith(supported_formats) and
            not os.path.exists(os.path.join(self.destination_folder, os.path.splitext(f)[0] + f'.{self.output_format}'))
        ]
        if not new_files:
            if not self.last_scan_message_logged:
                log_message("Scanning source folder...", self.log_emitter)
                self.last_scan_message_logged = True
            if not self.last_no_files_message_logged:
                log_message("No new files found.", self.log_emitter)
                self.last_no_files_message_logged = True
            return
        self.last_scan_message_logged = False
        self.last_no_files_message_logged = False

        # Setup startupinfo and creationflags to prevent console window and taskbar icon
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        else:
            startupinfo = None
            creationflags = 0

        for file_name in new_files:
            if self.stop_event.is_set():
                log_message("Conversion stopped before completing all files.", self.log_emitter)
                return

            source_file = os.path.join(self.source_folder, file_name)
            temp_fixed_file = os.path.join(self.destination_folder, 'fixed_' + file_name)

            # Preprocess to remux and potentially fix corrupted files
            preprocess_command = [resource_path('ffmpeg.exe'), '-i', source_file, '-c', 'copy', temp_fixed_file]
            try:
                log_message(f"Preprocessing: {file_name} to fix potential corruption", self.log_emitter)
                subprocess.run(
                    preprocess_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
            except subprocess.CalledProcessError as e:
                log_message(f"Error preprocessing {source_file}: {e.stderr}", self.log_emitter)
                continue

            # Proceed with conversion using GPU if available
            output_file_path = os.path.join(
                self.destination_folder,
                os.path.splitext(file_name)[0] + f'.{self.output_format}'
            )
            command = self.build_ffmpeg_command(temp_fixed_file, output_file_path)

            try:
                log_message(f"Converting: {file_name}", self.log_emitter)
                if os.name == 'nt':
                    startupinfo_popen = subprocess.STARTUPINFO()
                    startupinfo_popen.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags_popen = subprocess.CREATE_NO_WINDOW
                else:
                    startupinfo_popen = None
                    creationflags_popen = 0

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    startupinfo=startupinfo_popen,
                    creationflags=creationflags_popen
                )
                for line in process.stdout:
                    if self.stop_event.is_set():
                        process.kill()
                        log_message(f"Conversion of {file_name} stopped.", self.log_emitter)
                        return
                    log_message(line.strip(), self.log_emitter)

                process.wait()
                log_message(f"Successfully converted: {file_name}", self.log_emitter)

                # Move original to backup if needed
                if self.use_backup and self.backup_folder:
                    try:
                        backup_file_path = os.path.join(self.backup_folder, file_name)
                        os.rename(source_file, backup_file_path)
                        log_message(f"Moved {file_name} to backup folder.", self.log_emitter)
                    except OSError as e:
                        log_message(f"Error moving {file_name} to backup folder: {e}", self.log_emitter)

                # Delete original file after conversion if enabled
                if self.delete_after_conversion and not self.use_backup:
                    if self.retention_time > 0:
                        deletion_time = datetime.now() + timedelta(days=self.retention_time)
                        log_message(f"Scheduled deletion for {file_name} at {deletion_time.strftime('%Y-%m-%d %H:%M:%S')}", self.log_emitter)
                        threading.Timer(self.retention_time * 86400, self.delete_file, args=(source_file,)).start()
                    else:
                        self.delete_file(source_file)

            except FileNotFoundError:
                log_message("ffmpeg not found.", self.log_emitter)
            except subprocess.CalledProcessError as e:
                log_message(f"Error converting {source_file}: {e.stderr}", self.log_emitter)
            finally:
                # Remove the temporary remuxed file to save space
                if os.path.exists(temp_fixed_file):
                    os.remove(temp_fixed_file)

    def build_ffmpeg_command(self, input_file, output_file):
        """
        Build the appropriate FFMPEG command based on available GPU encoders.
        """
        gpu_encoder = self.get_gpu_encoder()
        if gpu_encoder:
            # Choose encoder based on the desired output format's codec
            codec_map = {
                'mp4': {'video': gpu_encoder.get('h264', 'libx264'), 'audio': 'aac'},
                'mov': {'video': gpu_encoder.get('h264', 'libx264'), 'audio': 'aac'},
                'avi': {'video': gpu_encoder.get('mpeg4', 'mpeg4'), 'audio': 'mp3'},
                'mkv': {'video': gpu_encoder.get('h264', 'libx264'), 'audio': 'aac'},
                'flv': {'video': gpu_encoder.get('flv', 'flv'), 'audio': 'mp3'},
                'webm': {'video': gpu_encoder.get('libvpx', 'libvpx'), 'audio': 'vorbis'},
                'mpeg': {'video': gpu_encoder.get('mpeg2video', 'mpeg2video'), 'audio': 'mp2'},
                'mpg': {'video': gpu_encoder.get('mpeg2video', 'mpeg2video'), 'audio': 'mp2'},
                '3gp': {'video': gpu_encoder.get('h263', 'h263'), 'audio': 'amr_nb'},
                'ogg': {'video': gpu_encoder.get('theora', 'theora'), 'audio': 'vorbis'},
                'wmv': {'video': gpu_encoder.get('wmv2', 'wmv2'), 'audio': 'wmav2'},
                'm4v': {'video': gpu_encoder.get('h264', 'libx264'), 'audio': 'aac'},
            }

            selected_codec = codec_map.get(self.output_format, {'video': 'libx264', 'audio': 'aac'})
            video_codec = selected_codec.get('video')
            audio_codec = selected_codec.get('audio')

            command = [
                resource_path('ffmpeg.exe'), '-y', '-i', input_file,
                '-vcodec', video_codec,
                '-acodec', audio_codec,
                output_file
            ]
            log_message(f"Using GPU encoder: {video_codec}", self.log_emitter)
        else:
            # Fallback to CPU-based encoding
            command = [
                resource_path('ffmpeg.exe'), '-y', '-i', input_file,
                '-vcodec', self.video_codec,
                '-acodec', self.audio_codec,
                output_file
            ]
            log_message("Using CPU encoder.", self.log_emitter)
        return command

    def get_gpu_encoder(self):
        """
        Detect available GPU encoders.
        """
        supported_encoders = get_supported_encoders()
        if 'nvidia' in supported_encoders:
            return supported_encoders['nvidia']
        elif 'intel' in supported_encoders:
            return supported_encoders['intel']
        elif 'amd' in supported_encoders:
            return supported_encoders['amd']
        else:
            return None

    def delete_file(self, file_path):
        """
        Delete a file from the filesystem.
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                log_message(f"Deleted original file: {file_path}", self.log_emitter)
        except Exception as e:
            log_message(f"Error deleting file {file_path}: {e}", self.log_emitter)

# -------------------- PyQt5 Application Execution -------------------- #

def main():
    app = QApplication(sys.argv)
    window = VideoConverterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
