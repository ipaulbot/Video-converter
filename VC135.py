import os
import subprocess
import threading
import json
import sys
import time
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QAction,
    QDialog, QCheckBox, QLineEdit, QComboBox, QSystemTrayIcon, QStyle, QMenu,
    QPlainTextEdit, QSizePolicy, QGroupBox, QFormLayout, QScrollArea,
    QTabWidget, QTimeEdit
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QPainter, QPen, QPainterPath, QFont,
    QTextCursor, QDesktopServices, QBrush, QColor
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QObject, QTimer, QUrl, QRectF, QPointF, QTime, QLocale
)
from PyQt5.QtNetwork import QLocalServer
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from jsonschema import validate, ValidationError
import math

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

def backup_settings():
    """
    Save a backup of the settings file.
    """
    if os.path.exists(settings_path):
        backup_path = settings_path + '.bak'
        shutil.copy2(settings_path, backup_path)
        logger.info(f"Settings backup created at {backup_path}")

def validate_settings(settings):
    """
    Validate settings against a predefined schema.
    """
    schema = {
        "type": "object",
        "properties": {
            "source_folder": {"type": "string"},
            "destination_folder": {"type": "string"},
            "backup_folder": {"type": "string"},
            "auto_run": {"type": "boolean"},
            "delete_after_conversion": {"type": "boolean"},
            "retention_time": {"type": "integer", "minimum": 0},
            "use_backup": {"type": "boolean"},
            "output_format": {"type": "string"},
            "video_codec": {"type": ["string", "null"]},
            "audio_codec": {"type": "string"},
            "copy_only": {"type": "boolean"},
            "locked": {"type": "boolean"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"},
            "no_time_restrictions": {"type": "boolean"}
        },
        "required": ["auto_run", "delete_after_conversion", "retention_time",
                     "use_backup", "output_format", "copy_only", "locked",
                     "start_time", "end_time", "no_time_restrictions"]
    }
    validate(instance=settings, schema=schema)

def save_settings(settings):
    """
    Save settings to a JSON file.
    """
    try:
        validate_settings(settings)
        backup_settings()
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info("Settings saved successfully.")
    except ValidationError as e:
        logger.error(f"Settings validation error: {e.message}")
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

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
        'audio_codec': 'aac',
        'copy_only': False,
        'locked': False,
        'start_time': '00:00',
        'end_time': '23:59',
        'no_time_restrictions': True
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            validate_settings(settings)
            return settings
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Settings file is corrupted or invalid: {e}. Loading default settings.")
            return default_settings
        except Exception as e:
            logger.error(f"Error loading settings: {e}. Loading default settings.")
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

def get_subprocess_startupinfo():
    """
    Helper function to set startupinfo and creationflags for subprocesses to prevent console windows.
    """
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    else:
        startupinfo = None
        creationflags = 0
    return startupinfo, creationflags

def get_supported_encoders():
    """
    Detect supported GPU encoders available in the current FFMPEG build.
    Returns a dictionary with encoder information.
    """
    try:
        # Retrieve the list of supported encoders
        startupinfo, creationflags = get_subprocess_startupinfo()
        result = subprocess.run(
            [resource_path('ffmpeg.exe'), '-encoders'],
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

# Cache the supported encoders to avoid redundant calls
GPU_ENCODERS = get_supported_encoders()

# -------------------- Easter Egg Dialog -------------------- #
class EasterEggDialog(QDialog):
    def __init__(self):
        super().__init__(None)  # Set parent to None to make it top-level
        self.setWindowTitle("")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.DISPLAY_DURATION = 120000  # Duration in milliseconds (120 seconds)
        self.init_ui()
        self.start_timer()
        self.play_audio()

    def init_ui(self):
        # Load team.png
        team_image_path = resource_path('team.png')  # Ensure the filename matches
        if os.path.exists(team_image_path):
            team_pixmap = QPixmap(team_image_path)
        else:
            team_pixmap = QPixmap()
            log_message(f"Team image not found at path '{team_image_path}'.", None)

        # Create label to display the image
        self.team_label = QLabel()
        self.team_label.setPixmap(team_pixmap)
        self.team_label.setAlignment(Qt.AlignCenter)
        self.team_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.team_label.setScaledContents(True)  # Ensure the image scales with the label

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.team_label)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)  # Remove any spacing
        self.setLayout(main_layout)

        # Resize the dialog to the size of the image with additional padding if necessary
        self.resize(team_pixmap.size())

    def start_timer(self):
        # Close the dialog after DISPLAY_DURATION milliseconds
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(self.DISPLAY_DURATION)

    def play_audio(self):
        # Initialize QMediaPlayer
        self.media_player = QMediaPlayer(self)
        audio_file_path = resource_path('paradise.mp3')  # Ensure the filename matches
        if os.path.exists(audio_file_path):
            url = QUrl.fromLocalFile(audio_file_path)
            media_content = QMediaContent(url)
            self.media_player.setMedia(media_content)
            self.media_player.play()
        else:
            log_message(f"Audio file not found at path '{audio_file_path}'.", None)

    def closeEvent(self, event):
        # Stop the audio when the dialog is closed
        if hasattr(self, 'media_player'):
            self.media_player.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

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
        self.setMinimumSize(400, 260)
        self.setWindowIcon(QIcon(resource_path('info_icon.ico')))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove question mark
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        info_text = QLabel()
        info_text.setText(
            "NVC 1.4.35 monitors a source folder for video files and converts them to the specified output format "
            "using FFMPEG. Converted files are saved in the destination folder, ensuring that "
            "no files are deleted from either location unless specified. After conversion, original files can be moved to a backup folder. "
            "The application continuously monitors the source folder for new files and converts them automatically when detected.\n\n"


            "This application uses FFMPEG for video conversion. You can download the "
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

# -------------------- Settings Dialog -------------------- #

class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)
    backup_usage_changed = pyqtSignal(bool)  # Signal to inform main window of backup usage change

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 300)  # Adjusted size to accommodate the new tab
        self.setWindowIcon(QIcon(resource_path('settings_logo.ico')))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove question mark
        self.current_settings = current_settings
        self.easter_egg_dialog = None  # Keep a reference to the Easter egg dialog
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create the QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        # Create tabs
        self.create_general_tab()
        self.create_folders_tab()
        self.create_deletion_tab()
        self.create_conversion_tab()
        self.create_time_tab()

        # Add the tabs to the tab widget
        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.folders_tab, "Folders")
        self.tabs.addTab(self.deletion_tab, "Deletion")
        self.tabs.addTab(self.conversion_tab, "Conversion")
        self.tabs.addTab(self.time_tab, "Time Restriction")

        # Add the tabs to the main layout
        main_layout.addWidget(self.tabs)

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

    def create_general_tab(self):
        self.general_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Auto Run on Startup
        self.auto_run_checkbox = QCheckBox("Auto Run on Startup")
        self.auto_run_checkbox.setChecked(self.current_settings.get('auto_run', False))

        auto_run_info = QLabel("Automatically start the application with previous settings.")
        auto_run_info.setWordWrap(True)
        auto_run_info.setIndent(20)  # Indent the info text

        # Copy Only Option
        self.copy_only_checkbox = QCheckBox("Copy only")
        self.copy_only_checkbox.setChecked(self.current_settings.get('copy_only', False))
        self.copy_only_checkbox.stateChanged.connect(self.toggle_copy_only)

        copy_only_info = QLabel("Copy files without converting them.")
        copy_only_info.setWordWrap(True)
        copy_only_info.setIndent(20)

        layout.addWidget(self.auto_run_checkbox)
        layout.addWidget(auto_run_info)
        layout.addWidget(self.copy_only_checkbox)
        layout.addWidget(copy_only_info)

        layout.addStretch()
        self.general_tab.setLayout(layout)

    def create_folders_tab(self):
        self.folders_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Source Folder
        source_form_layout = QFormLayout()
        source_label = QLabel("      Source Folder:")
        self.source_display = QLineEdit(self.current_settings.get('source_folder', ''))
        self.source_display.setReadOnly(True)
        source_button = QPushButton("Change")
        source_button.clicked.connect(self.change_source_folder)
        source_button.setMaximumWidth(75)
        source_form_layout.addRow(source_label, self.source_display)
        source_form_layout.addWidget(source_button)

        # Destination Folder
        destination_form_layout = QFormLayout()
        destination_label = QLabel("Destination Folder:")
        self.destination_display = QLineEdit(self.current_settings.get('destination_folder', ''))
        self.destination_display.setReadOnly(True)
        destination_button = QPushButton("Change")
        destination_button.clicked.connect(self.change_destination_folder)
        destination_button.setMaximumWidth(75)
        destination_form_layout.addRow(destination_label, self.destination_display)
        destination_form_layout.addWidget(destination_button)

        # Backup Folder
        backup_form_layout = QFormLayout()
        backup_label = QLabel("      Backup Folder:")
        self.backup_display = QLineEdit(self.current_settings.get('backup_folder', ''))
        self.backup_display.setReadOnly(True)
        backup_button = QPushButton("Change")
        backup_button.clicked.connect(self.change_backup_folder)
        backup_button.setMaximumWidth(75)
        backup_form_layout.addRow(backup_label, self.backup_display)
        backup_form_layout.addWidget(backup_button)

        layout.addLayout(source_form_layout)
        layout.addLayout(destination_form_layout)
        layout.addLayout(backup_form_layout)

        layout.addStretch()
        self.folders_tab.setLayout(layout)

    def change_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", self.current_settings.get('source_folder', '') or os.path.expanduser("~"))
        if folder:
            self.source_display.setText(folder)

    def change_destination_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.current_settings.get('destination_folder', '') or os.path.expanduser("~"))
        if folder:
            self.destination_display.setText(folder)

    def change_backup_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder", self.current_settings.get('backup_folder', '') or os.path.expanduser("~"))
        if folder:
            self.backup_display.setText(folder)

    def create_deletion_tab(self):
        self.deletion_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Delete after conversion
        self.delete_after_checkbox = QCheckBox("Delete files after conversion")
        self.delete_after_checkbox.setChecked(self.current_settings.get('delete_after_conversion', False))
        self.delete_after_checkbox.stateChanged.connect(self.toggle_retention)

        delete_info = QLabel("Delete original files after successful conversion.")
        delete_info.setWordWrap(True)
        delete_info.setIndent(20)  # Indent the info text

        layout.addWidget(self.delete_after_checkbox)
        layout.addWidget(delete_info)

        # Retention time
        retention_form_layout = QFormLayout()
        self.retention_label = QLabel("Retention time (days):")
        self.retention_input = QLineEdit(str(self.current_settings.get('retention_time', 0)))
        self.retention_label.setEnabled(self.delete_after_checkbox.isChecked())
        self.retention_input.setEnabled(self.delete_after_checkbox.isChecked())
        self.retention_input.textChanged.connect(self.retention_time_changed)
        self.retention_input.returnPressed.connect(self.retention_time_entered)  # Handle Enter key
        self.retention_input.setMaximumWidth(50)

        retention_form_layout.addRow(self.retention_label, self.retention_input)

        retention_info = QLabel("Time in days to retain original files before deletion (0-30).")
        retention_info.setWordWrap(True)
        retention_info.setIndent(20)

        layout.addLayout(retention_form_layout)
        layout.addWidget(retention_info)

        # Use Backup Folder
        self.use_backup_checkbox = QCheckBox("Use Backup Folder")
        self.use_backup_checkbox.setChecked(self.current_settings.get('use_backup', False))
        self.use_backup_checkbox.setEnabled(not (self.delete_after_checkbox.isChecked() and int(self.retention_input.text()) == 0))
        self.use_backup_checkbox.stateChanged.connect(self.toggle_backup)

        backup_info = QLabel("Move original files to a backup folder after conversion.")
        backup_info.setWordWrap(True)
        backup_info.setIndent(20)

        layout.addWidget(self.use_backup_checkbox)
        layout.addWidget(backup_info)

        layout.addStretch()
        self.deletion_tab.setLayout(layout)

    def create_conversion_tab(self):
        self.conversion_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Output Format
        output_form_layout = QFormLayout()
        output_format_label = QLabel("Output Format:")
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(['mp4', 'mov', 'avi', 'mkv', 'mp3'])
        self.output_format_combo.setCurrentText(self.current_settings.get('output_format', 'mp4'))
        self.output_format_combo.currentTextChanged.connect(self.update_codecs)
        self.output_format_combo.setMaximumWidth(75)

        output_form_layout.addRow(output_format_label, self.output_format_combo)

        output_format_info = QLabel("Select the output format for the converted files.")
        output_format_info.setWordWrap(True)
        output_format_info.setIndent(20)

        layout.addLayout(output_form_layout)
        layout.addWidget(output_format_info)

        # Video Codec
        video_codec_form_layout = QFormLayout()
        video_codec_label = QLabel("    Video Codec:")
        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(['libx264', 'mpeg4', 'libvpx', 'hevc', 'flv', 'mpeg2video', 'h263', 'theora', 'wmv2'])
        self.video_codec_combo.setCurrentText(self.current_settings.get('video_codec', 'libx264'))
        self.video_codec_combo.setMaximumWidth(75)

        video_codec_form_layout.addRow(video_codec_label, self.video_codec_combo)

        video_codec_info = QLabel("Select the video codec for conversion.")
        video_codec_info.setWordWrap(True)
        video_codec_info.setIndent(20)

        layout.addLayout(video_codec_form_layout)
        layout.addWidget(video_codec_info)

        # Audio Codec
        audio_codec_form_layout = QFormLayout()
        audio_codec_label = QLabel("   Audio Codec:")
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(['aac', 'mp3', 'ac3', 'opus', 'vorbis', 'mp2', 'amr_nb', 'wmav2', 'libmp3lame'])
        self.audio_codec_combo.setCurrentText(self.current_settings.get('audio_codec', 'aac'))
        self.audio_codec_combo.setMaximumWidth(75)

        audio_codec_form_layout.addRow(audio_codec_label, self.audio_codec_combo)

        audio_codec_info = QLabel("Select the audio codec for conversion.")
        audio_codec_info.setWordWrap(True)
        audio_codec_info.setIndent(20)

        layout.addLayout(audio_codec_form_layout)
        layout.addWidget(audio_codec_info)

        # Disable codecs if "Copy only" is selected
        self.toggle_copy_only(self.copy_only_checkbox.isChecked())

        layout.addStretch()
        self.conversion_tab.setLayout(layout)

    def create_time_tab(self):
        self.time_tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        time_info = QLabel("Restrict conversion to specific times of the day.")
        time_info.setWordWrap(True)
        time_info.setIndent(20)

        # Get system time format
        locale = QLocale()
        system_time_format = locale.timeFormat(QLocale.ShortFormat)
        # Determine if the system uses 12-hour or 24-hour format
        if 'AP' in system_time_format or 'ap' in system_time_format:
            # 12-hour format
            time_display_format = 'hh:mm AP'
        else:
            # 24-hour format
            time_display_format = 'HH:mm'

        # No Time Restrictions Checkbox
        self.no_time_restrictions_checkbox = QCheckBox("No Time Restrictions")
        self.no_time_restrictions_checkbox.setChecked(self.current_settings.get('no_time_restrictions', True))
        self.no_time_restrictions_checkbox.toggled.connect(self.toggle_time_restrictions)

        # Start and End Time on the same line
        time_selection_layout = QHBoxLayout()
        start_time_label = QLabel("Start Time:")
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat(time_display_format)
        self.start_time_edit.setTime(QTime.fromString(self.current_settings.get('start_time', '00:00'), "HH:mm"))
        self.start_time_edit.timeChanged.connect(self.validate_time_range)

        end_time_label = QLabel("End Time:")
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat(time_display_format)
        self.end_time_edit.setTime(QTime.fromString(self.current_settings.get('end_time', '23:59'), "HH:mm"))
        self.end_time_edit.timeChanged.connect(self.validate_time_range)

        time_selection_layout.addWidget(start_time_label)
        time_selection_layout.addWidget(self.start_time_edit)
        time_selection_layout.addSpacing(20)
        time_selection_layout.addWidget(end_time_label)
        time_selection_layout.addWidget(self.end_time_edit)
        time_selection_layout.addStretch()

        layout.addWidget(time_info)
        layout.addWidget(self.no_time_restrictions_checkbox)
        layout.addLayout(time_selection_layout)

        # Initially disable time edits if no time restrictions is checked
        self.toggle_time_restrictions(self.no_time_restrictions_checkbox.isChecked())

        layout.addStretch()
        self.time_tab.setLayout(layout)

    def validate_time_range(self):
        """
        Ensure that the start time is not after the end time.
        """
        start_time = self.start_time_edit.time()
        end_time = self.end_time_edit.time()
        # No action needed if times are valid; handle any validation logic if required

    def toggle_time_restrictions(self, checked):
        """
        Enable or disable the time edits based on the checkbox state.
        """
        enabled = not checked
        self.start_time_edit.setEnabled(enabled)
        self.end_time_edit.setEnabled(enabled)

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
                if self.use_backup_checkbox.isEnabled():
                    self.use_backup_checkbox.setEnabled(False)
                    self.use_backup_checkbox.setChecked(False)
                    self.backup_usage_changed.emit(False)
            else:
                # Retention time > 0, enable Use Backup Folder
                if not self.use_backup_checkbox.isEnabled():
                    self.use_backup_checkbox.setEnabled(True)
        else:
            # Delete after conversion is not checked, enable Use Backup Folder
            if not self.use_backup_checkbox.isEnabled():
                self.use_backup_checkbox.setEnabled(True)

    def retention_time_entered(self):
        text = self.retention_input.text()
        if text == "Noldus123":
            self.trigger_easter_egg()
            self.retention_input.clear()
        else:
            # Optionally validate the retention time
            pass

    def trigger_easter_egg(self):
        """
        Display the Easter egg when the secret code is entered.
        """
        self.easter_egg_dialog = EasterEggDialog()
        self.easter_egg_dialog.show()
        self.easter_egg_dialog.activateWindow()
        self.easter_egg_dialog.setFocus()

    def toggle_backup(self, state):
        enabled = state == Qt.Checked
        self.backup_usage_changed.emit(enabled)
        # Keep the backup folder path intact

    def update_codecs(self, format_selected):
        codec_map = {
            'mp4': {'video': 'libx264', 'audio': 'aac'},
            'mov': {'video': 'libx264', 'audio': 'aac'},
            'avi': {'video': 'mpeg4', 'audio': 'mp3'},
            'mkv': {'video': 'libx264', 'audio': 'aac'},
            'mp3': {'video': None, 'audio': 'libmp3lame'}  # No video codec for mp3
        }
        codecs = codec_map.get(format_selected, {'video': 'libx264', 'audio': 'aac'})
        self.video_codec_combo.setEnabled(codecs['video'] is not None)
        if codecs['video']:
            self.video_codec_combo.setCurrentText(codecs['video'])
        self.audio_codec_combo.setCurrentText(codecs['audio'])

    def toggle_copy_only(self, state):
        enabled = state != Qt.Checked
        self.output_format_combo.setEnabled(enabled)
        self.video_codec_combo.setEnabled(enabled and self.output_format_combo.currentText() != 'mp3')  # Disable video codec if mp3
        self.audio_codec_combo.setEnabled(enabled)
        # Additionally, update conversion tab UI if necessary

    def set_defaults(self):
        self.auto_run_checkbox.setChecked(False)
        self.delete_after_checkbox.setChecked(True)
        self.use_backup_checkbox.setChecked(False)
        self.retention_input.setText('0')
        self.output_format_combo.setCurrentText('mov')
        self.video_codec_combo.setCurrentText('libx264')
        self.audio_codec_combo.setCurrentText('aac')
        self.copy_only_checkbox.setChecked(False)  # Reset copy_only to default
        self.start_time_edit.setTime(QTime.fromString('00:00', 'HH:mm'))
        self.end_time_edit.setTime(QTime.fromString('23:59', 'HH:mm'))
        self.no_time_restrictions_checkbox.setChecked(True)
        # Do not reset the folder paths
        self.toggle_retention(True)
        self.backup_usage_changed.emit(self.use_backup_checkbox.isChecked())

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
            'video_codec': self.video_codec_combo.currentText() if self.video_codec_combo.isEnabled() else None,
            'audio_codec': self.audio_codec_combo.currentText(),
            'copy_only': self.copy_only_checkbox.isChecked(),
            'start_time': self.start_time_edit.time().toString("HH:mm"),
            'end_time': self.end_time_edit.time().toString("HH:mm"),
            'no_time_restrictions': self.no_time_restrictions_checkbox.isChecked(),
            'source_folder': self.source_display.text(),
            'destination_folder': self.destination_display.text(),
            'backup_folder': self.backup_display.text(),
            'locked': self.current_settings.get('locked', False)  # Preserve lock state
        }
        self.settings_saved.emit(settings)
        self.accept()

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
        self.copy_only = self.settings.get('copy_only', False)  # Load copy_only setting
        self.locked = self.settings.get('locked', False)  # Load the lock state
        self.start_time = self.settings.get('start_time', '00:00')
        self.end_time = self.settings.get('end_time', '23:59')
        self.no_time_restrictions = self.settings.get('no_time_restrictions', True)

        # Initialize logging state variables
        self.last_scan_message_logged = False
        self.last_no_files_message_logged = False
        self.logged_outside_time_message = False  # For logging outside time only once

        # Initialize LogEmitter and connect to GUI
        self.log_emitter = LogEmitter()
        self.log_emitter.log_signal.connect(self.append_log)

        # Initialize active conversion counter
        self.active_conversion_count = 0

        # Initialize backup usage state
        self.backup_usage_enabled = self.use_backup

        # Initialize thread pool executor
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Setup UI and system tray icon
        self.init_ui()
        self.init_tray_icon()

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Update UI elements based on lock state
        self.update_lock_state_ui()

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
                self.logo_label.setAlignment(Qt.AlignCenter)
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
        self.lock_action = QAction("Unlock" if self.locked else "Lock", self)
        self.lock_action.triggered.connect(self.toggle_lock)
        self.help_action = QAction("Help", self)
        self.help_action.triggered.connect(self.open_help_document)

        self.menubar.addAction(self.info_action)
        self.menubar.addAction(self.settings_action)
        self.menubar.addAction(self.help_action)
        self.menubar.addAction(self.lock_action)

    def open_help_document(self):
        """
        Open the help document (PDF) using the default application.
        """
        help_pdf_path = resource_path('help_document.pdf')  # Replace with the actual filename
        if os.path.exists(help_pdf_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(help_pdf_path))
        else:
            log_message(f"Help document not found at path '{help_pdf_path}'.", self.log_emitter)
            QMessageBox.warning(self, "Help Document Not Found", "The help document could not be found.")

    def update_lock_state_ui(self):
        """
        Update UI elements based on the lock state.
        """
        # Update the menu action text
        self.lock_action.setText("Unlock" if self.locked else "Lock")
        # Disable or enable Settings menu item
        self.settings_action.setEnabled(not self.locked)
        # Disable or enable buttons
        state = not self.locked
        self.source_button.setEnabled(state)
        self.destination_button.setEnabled(state)
        self.backup_button.setEnabled(state and self.use_backup)  # Ensure backup is enabled based on use_backup
        # Start/Stop button remains active regardless of lock status

    def append_log(self, message):
        """
        Append log messages to the console output.
        """
        self.console_output.appendPlainText(message)

        # Limit the log window to 1000 lines
        MAX_LOG_LINES = 1000
        if self.console_output.blockCount() > MAX_LOG_LINES:
            # Remove the oldest lines
            cursor = self.console_output.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # Remove the newline character

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

        # Set tooltip
        self.tray_icon.setToolTip("Video Converter Application")

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
        Start the video conversion process using ThreadPoolExecutor.
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
        self.copy_only = self.settings.get('copy_only', False)  # Update copy_only setting
        self.start_time = self.settings.get('start_time', '00:00')
        self.end_time = self.settings.get('end_time', '23:59')
        self.no_time_restrictions = self.settings.get('no_time_restrictions', True)
        self.source_folder = self.settings.get('source_folder', '')
        self.destination_folder = self.settings.get('destination_folder', '')
        self.backup_folder = self.settings.get('backup_folder', '')
        log_message("Settings updated.", self.log_emitter)

        # Update the backup_button state based on 'use_backup'
        self.backup_button.setEnabled(self.use_backup and not self.locked)
        self.backup_usage_enabled = self.use_backup

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
            # Save the lock state to settings
            self.settings['locked'] = self.locked
            save_settings(self.settings)
            self.update_lock_state_ui()
            log_message(f"Application {'locked' if self.locked else 'unlocked'}.", self.log_emitter)

    def update_backup_button_state(self, enabled):
        """
        Enable or disable the backup folder selection button based on the 'Use Backup Folder' checkbox.
        """
        if not self.locked:
            self.backup_button.setEnabled(enabled)
        self.backup_usage_enabled = enabled

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

        # Clean up the local server
        if hasattr(self, 'local_server'):
            self.local_server.close()
            self.local_server.removeServer("VideoConverterAppInstance")

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
                self.executor.submit(self.convert_file, file_path)
            else:
                unsupported_files.append(file_path)

        if unsupported_files:
            unsupported_list = "\n".join(unsupported_files)
            QMessageBox.warning(self, "Unsupported Files", f"The following files are not supported and were not converted:\n{unsupported_list}")
            log_message(f"Unsupported files dropped:\n{unsupported_list}", self.log_emitter)

    def is_within_allowed_hours(self):
        """
        Check if the current time is within the allowed conversion times.
        """
        if self.no_time_restrictions:
            return True

        current_time = datetime.now().time()
        # Parse start_time and end_time from settings
        start_time_str = self.start_time
        end_time_str = self.end_time
        # Adjust time format based on system settings
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.strptime(end_time_str, "%H:%M").time()

        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # Time range crosses midnight
            return current_time >= start_time or current_time <= end_time

    def has_audio_stream(self, file_path):
        """
        Check if the file has an audio stream.
        """
        command = [resource_path('ffprobe.exe'), '-v', 'error', '-select_streams', 'a', '-show_entries',
                   'stream=codec_type', '-of', 'default=nw=1', file_path]
        startupinfo, creationflags = get_subprocess_startupinfo()
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                startupinfo=startupinfo, creationflags=creationflags)
        return 'codec_type=audio' in result.stdout

    def convert_file(self, file_path):
        """
        Convert a single file.
        """
        if not self.is_within_allowed_hours():
            if not self.logged_outside_time_message:
                log_message(f"Current time is outside the allowed conversion times ({self.start_time} to {self.end_time}).", self.log_emitter)
                self.logged_outside_time_message = True
            return

        self.logged_outside_time_message = False  # Reset the flag
        self.start_conversion_indicator()  # Indicate conversion start
        try:
            file_name = os.path.basename(file_path)
            destination_file = os.path.join(
                self.destination_folder,
                file_name if self.copy_only else os.path.splitext(file_name)[0] + f'.{self.output_format}'
            )

            # Check if output file already exists
            if os.path.exists(destination_file):
                log_message(f"Output file already exists: {destination_file}", self.log_emitter)
                return

            if self.copy_only:
                # Copy the file directly
                try:
                    log_message(f"Copying: {file_name}", self.log_emitter)
                    shutil.copy2(file_path, destination_file)
                    log_message(f"Successfully copied: {file_name}", self.log_emitter)

                    # Move original to backup if needed
                    if self.use_backup and self.backup_folder:
                        try:
                            backup_file_path = os.path.join(self.backup_folder, file_name)
                            os.rename(file_path, backup_file_path)
                            log_message(f"Moved {file_name} to backup folder.", self.log_emitter)
                        except OSError as e:
                            log_message(f"Error moving {file_name} to backup folder: {e}", self.log_emitter)

                    # Delete original file after copying if enabled
                    if self.delete_after_conversion and not self.use_backup:
                        if self.retention_time > 0:
                            deletion_time = datetime.now() + timedelta(days=self.retention_time)
                            log_message(f"Scheduled deletion for {file_name} at {deletion_time.strftime('%Y-%m-%d %H:%M:%S')}", self.log_emitter)
                            threading.Timer(self.retention_time * 86400, self.delete_file, args=(file_path,)).start()
                        else:
                            self.delete_file(file_path)
                except Exception as e:
                    log_message(f"Error copying {file_path}: {e}", self.log_emitter)
                return  # Skip conversion

            # Proceed with conversion
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_fixed_file = os.path.join(temp_dir, 'fixed_' + file_name)
                preprocess_needed = True  # Assume preprocessing is needed

                # Introduce an option to skip preprocessing unless corruption is detected
                try:
                    # Check if file is corrupted using ffprobe
                    probe_command = [resource_path('ffprobe.exe'), '-v', 'error', '-i', file_path]
                    startupinfo, creationflags = get_subprocess_startupinfo()
                    subprocess.run(
                        probe_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags
                    )
                    preprocess_needed = False
                    log_message(f"No corruption detected in {file_name}. Skipping preprocessing.", self.log_emitter)
                except subprocess.CalledProcessError:
                    log_message(f"Corruption detected in {file_name}. Preprocessing required.", self.log_emitter)

                if preprocess_needed:
                    preprocess_command = [resource_path('ffmpeg.exe'), '-i', file_path, '-c', 'copy', temp_fixed_file]
                    try:
                        log_message(f"Preprocessing: {file_name} to fix potential corruption", self.log_emitter)
                        startupinfo, creationflags = get_subprocess_startupinfo()
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
                    input_file = temp_fixed_file
                else:
                    input_file = file_path

                # Check for audio stream if converting to mp3
                if self.output_format == 'mp3':
                    if not self.has_audio_stream(input_file):
                        log_message(f"No audio stream found in {file_name}. Cannot convert to mp3.", self.log_emitter)
                        return

                # Build FFMPEG command
                output_file_path = destination_file
                command = self.build_ffmpeg_command(input_file, output_file_path)
                startupinfo, creationflags = get_subprocess_startupinfo()

                try:
                    log_message(f"Converting: {file_name}", self.log_emitter)
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags
                    )
                    for line in process.stdout:
                        if self.stop_event.is_set():
                            process.kill()
                            log_message(f"Conversion of {file_name} stopped.", self.log_emitter)
                            return
                        log_message(line.strip(), self.log_emitter)

                    return_code = process.wait()
                    if return_code == 0:
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
                    else:
                        log_message(f"Error converting {file_name}: ffmpeg exited with code {return_code}", self.log_emitter)
                        return

                except FileNotFoundError:
                    log_message("ffmpeg not found.", self.log_emitter)
                except Exception as e:
                    log_message(f"Error converting {file_name}: {e}", self.log_emitter)
        finally:
            self.end_conversion_indicator()  # Indicate conversion end

    def convert_videos(self):
        """
        Convert new video files found in the source folder.
        """
        if not os.path.exists(self.source_folder) or not os.path.exists(self.destination_folder):
            log_message("Error: Source or destination folder does not exist.", self.log_emitter)
            return

        if not self.is_within_allowed_hours():
            if not self.logged_outside_time_message:
                log_message(f"Current time is outside the allowed conversion times ({self.start_time} to {self.end_time}).", self.log_emitter)
                self.logged_outside_time_message = True
            return
        else:
            self.logged_outside_time_message = False  # Reset the flag

        # Supported input formats
        supported_formats = (
            '.mp4', '.avi', '.wmv', '.mkv', '.flv', '.webm', '.mov', '.mpeg',
            '.mpg', '.m4v', '.3gp', '.ts', '.vob', '.rm', '.rmvb', '.asf',
            '.m2ts', '.mts', '.ogv', '.divx', '.dv', '.f4v', '.mxf', '.nut',
            '.ogm', '.qt', '.tod', '.vro'
        )
        new_files = [
            os.path.join(self.source_folder, f) for f in os.listdir(self.source_folder)
            if f.lower().endswith(supported_formats) and
            not os.path.exists(os.path.join(self.destination_folder, f if self.copy_only else os.path.splitext(f)[0] + f'.{self.output_format}'))
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

        for file_path in new_files:
            if self.stop_event.is_set():
                log_message("Process stopped before completing all files.", self.log_emitter)
                return
            self.executor.submit(self.convert_file, file_path)

    def build_ffmpeg_command(self, input_file, output_file):
        """
        Build the appropriate FFMPEG command based on available GPU encoders.
        """
        gpu_encoder = self.get_gpu_encoder()
        if self.output_format == 'mp3':
            command = [
                resource_path('ffmpeg.exe'), '-y', '-i', input_file,
                '-vn',  # Skip video stream
                '-acodec', self.audio_codec or 'libmp3lame',  # Audio codec for mp3
                output_file
            ]
            log_message("Building command for audio-only conversion to mp3.", self.log_emitter)
        elif gpu_encoder:
            # Choose encoder based on the desired output format's codec
            video_codec = gpu_encoder.get('h264', self.video_codec)
            command = [
                resource_path('ffmpeg.exe'), '-y', '-i', input_file,
                '-vcodec', video_codec,
                '-acodec', self.audio_codec,
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
        if 'nvidia' in GPU_ENCODERS:
            return GPU_ENCODERS['nvidia']
        elif 'intel' in GPU_ENCODERS:
            return GPU_ENCODERS['intel']
        elif 'amd' in GPU_ENCODERS:
            return GPU_ENCODERS['amd']
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

    # Unique name for your application
    app_name = "VideoConverterAppInstance"

    # Remove existing server if needed (handles crashes)
    existing_server = QLocalServer()
    existing_server.removeServer(app_name)

    # Create a local server
    local_server = QLocalServer()
    if not local_server.listen(app_name):
        log_message("Another instance is already running.", None)
        QMessageBox.warning(None, "Application Already Running", "Another instance of the application is already running.")
        sys.exit()
    else:
        window = VideoConverterApp()
        window.show()
        window.local_server = local_server
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
