import os
import shutil
import subprocess
import threading
import sys
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QTabWidget,
    QHBoxLayout, QVBoxLayout, QSystemTrayIcon, QStyle, QMenu,
    QPlainTextEdit, QMessageBox, QSpacerItem, QSizePolicy, QProgressBar,
    QAction, QToolBar, QToolButton, QFrame, QStackedWidget, QGridLayout,
    QApplication, QStackedLayout, QSlider, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QThreadPool, pyqtSignal, QSize, QEvent, QUrl, QProcess, QPoint, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QIcon, QFont, QTextCursor, QPainter, QColor, QImage, QWheelEvent, QPen, QBrush

# Use native Observer; fall back to PollingObserver if needed.
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from ui.inspection_widget import InspectionWidget
from ui.converted_files_widget import ConvertedFilesWidget
from ui.settings_dialog import SettingsDialog
from ui.dialogs import InfoDialog, ConfirmationDialog, EasterEggDialog
from utils.config import load_settings, save_settings
from utils.system_state import get_game_unlocked, set_game_unlocked
from utils.logger import logger
from utils.resources import resource_path
from utils.media_files import collect_supported_media_paths
from utils.subprocess_helpers import (
    FFMPEG_RENDER_TIMEOUT,
    FFPROBE_TIMEOUT,
    get_subprocess_startupinfo,
)
from conversion.worker import ConversionWorker, WorkerSignals
from conversion.ffmpeg_utils import is_within_allowed_time
from ui.log_bus import LogBus
from ui.lossless_editor_widget import LosslessEditorWidget
from ui.multi_source_recorder_widget import MultiSourceRecorderWidget
from ui.media_player_widget import MediaPlayerWidget
from conversion.recording_commands import recording_layout_preview_rects
from ui.pc_report_dialog import PCReportWidget
from utils.update_checker import UpdateChecker, UpdateWorker

SUPPORTED_FORMATS = (
    '.mp4', '.avi', '.wmv', '.mkv', '.flv', '.webm', '.mov', '.mpeg',
    '.mpg', '.m4v', '.3gp', '.ts', '.vob', '.rm', '.rmvb', '.asf',
    '.m2ts', '.mts', '.ogv', '.divx', '.dv', '.f4v'
)

from utils.version import APP_VERSION

class FolderWatchdogHandler(FileSystemEventHandler):
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        ext = os.path.splitext(file_path)[1].lower()
        if ext in SUPPORTED_FORMATS:
            self.app_window.file_detected.emit(file_path)

from utils.version import APP_VERSION

class VideoConverterApp(QMainWindow):
    file_detected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Video Converter v{APP_VERSION}")
        self.setMinimumHeight(520)  # Keep the designed baseline while allowing the window to resize.
        self.setMinimumWidth(900)  # Increased minimum width for more space

        # Load settings and normalize folder paths.
        self.settings = load_settings()
        self.source_folder = os.path.abspath(self.settings.get('source_folder', ''))
        self.destination_folder = os.path.abspath(self.settings.get('destination_folder', ''))
        self.backup_folder = os.path.abspath(self.settings.get('backup_folder', ''))
        self.locked = self.settings.get('locked', False)
        # Apply window button configuration based on settings (minimize when close-on-X enabled)
        self.apply_window_flags_based_on_settings()
        # Ensure state flags defined before any dependent calls
        self.running = False
        self.status_running = False
        self.active_conversion_count = 0
        self.in_flight_conversions = set()
        self.file_detected.connect(self.convert_file)

        # Use modern clean stylesheet
        modern_stylesheet = """
            QWidget {
                background: #F5F5F5;
                color: #333333;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
            }
            QMainWindow, QDialog {
                background: #F5F5F5;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #43a296, stop:1 #3a9284);
                border: 1px solid #2d7d6f;
                border-radius: 6px;
                padding: 8px 16px;
                min-width: 100px;
                min-height: 32px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4bb3a7, stop:1 #43a296);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a9284, stop:1 #2d7d6f);
            }
            QTabWidget::pane {
                border: 1px solid #E0E0E0;
                background: white;
                border-radius: 8px;
                margin-top: 4px;
            }
            QTabBar::tab {
                background: #F0F0F0;
                border: 1px solid #E0E0E0;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: normal;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #43a296;
            }
            QPlainTextEdit {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QMenuBar, QMenu {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #43a296;
                color: white;
            }
            QProgressBar {
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                border-radius: 4px;
                text-align: center;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
                font-weight: normal;
                color: #333333;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #43a296;
                border-radius: 3px;
                margin: 1px;
            }
        """
        self.setStyleSheet(modern_stylesheet)

        # Set new logo as window icon
        self.icon_color = resource_path('graphics/TEALNVCLOGO.ico')
        self.icon_gray = resource_path('graphics/GRAYSCALENVCLOGO.ico')
        if os.path.exists(self.icon_color):
            self.setWindowIcon(QIcon(self.icon_color))

        # Sidebar sizing constants
        # Sidebar logo size (used everywhere, including update_icons()).
        # Scaled up to 175% of original 88px size (154px) for better visibility.
        self.logo_size = 154

        # Logo in sidebar
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(self.logo_size, self.logo_size)  # Fix container size to prevent shifting
        self.logo_label.setAlignment(Qt.AlignCenter)
        # Ensure padding is 0 to save space
        self.logo_label.setContentsMargins(0,0,0,0)
        self.logo_label.setStyleSheet("""
            QLabel { 
                background: transparent; 
                border: none; 
                padding: 0px;
            }
            QLabel:hover { 
                background: #e9ecef;
                border-radius: 25px;
            }
        """)
        self.logo_label.setCursor(Qt.PointingHandCursor)
        self.logo_label.setToolTip("Click to open settings")
        self.logo_label.mousePressEvent = self.logo_clicked
        self.logo_pixmap = None
        self.grayscale_logo_pixmap = None

        # --- Video Preview Panel (below logo) ---
        # NOTE: We intentionally avoid QMediaPlayer/QVideoWidget here because on Windows it depends on
        # installed DirectShow codecs and often renders black. We decode frames with ffmpeg instead.
        self.preview_container = QFrame()
        self.preview_container.setStyleSheet("""
            QFrame {
                background: white; 
                border: 2px dashed #dee2e6; 
                border-radius: 8px;
            }
            QFrame:hover {
                border: 2px dashed #43a296;
                background: rgba(67, 162, 150, 0.05);
            }
        """)
        # Keep aspect ratio 16:9 and match sidebar content width for clean alignment
        # (settings_display is fixedWidth(180) below)
        self.preview_container.setFixedSize(180, 101)
        self.preview_container.setMouseTracking(True)  # Enable mouse tracking for hover events
        self.preview_container.setAttribute(Qt.WA_Hover, True)  # Enable hover events
        self.preview_w = self.preview_container.width()
        self.preview_h = self.preview_container.height()

        self.preview_layout = QStackedLayout(self.preview_container)
        self.preview_layout.setStackingMode(QStackedLayout.StackAll)
        self.preview_layout.setContentsMargins(0,0,0,0)

        # 1. Preview Label (thumbnail + decoded frames)
        self.preview_label = QLabel("No Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                color: #43a296;
                font-size: 14px;
                font-weight: normal;
                background-color: transparent;
                border: none;
            }
        """)
        self.preview_label.setMouseTracking(True)  # Enable mouse tracking
        self.preview_label.setAttribute(Qt.WA_Hover, True)  # Enable hover events
        self.preview_layout.addWidget(self.preview_label)

        # 3. Play/Pause Overlay (Top layer)
        self.overlay_container = QWidget()
        self.overlay_container.setStyleSheet("background: transparent;")
        self.overlay_container.setMouseTracking(True)  # Enable mouse tracking
        self.overlay_container.setAttribute(Qt.WA_Hover, True)  # Enable hover events
        overlay_layout = QVBoxLayout(self.overlay_container)
        overlay_layout.setContentsMargins(6, 6, 6, 6)
        overlay_layout.setSpacing(6)

        self.play_pause_btn = QPushButton()
        # Smaller overlay button so it doesn't dominate the thumbnail
        self.play_pause_btn.setFixedSize(22, 22)
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setMouseTracking(True)
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.setIconSize(QSize(12, 12))
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.6);
                border-radius: 11px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                padding: 0px;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover {
                background-color: rgba(67, 162, 150, 0.8);
                border: 1px solid #43a296;
                border-radius: 11px;
            }
        """)
        self.play_pause_btn.hide()
        self.play_pause_btn.clicked.connect(self.toggle_preview_playback)

        # Progress scrubber (thin slider)
        self.preview_scrubber = QSlider(Qt.Horizontal)
        self.preview_scrubber.setRange(0, 1000)
        self.preview_scrubber.setValue(0)
        self.preview_scrubber.setFixedHeight(10)
        self.preview_scrubber.setMouseTracking(True)
        self.preview_scrubber.setCursor(Qt.PointingHandCursor)
        self.preview_scrubber.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.35);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                height: 4px;
                background: rgba(67, 162, 150, 0.9);
                border-radius: 2px;
            }
            QSlider::add-page:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.25);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 8px;
                margin: -3px 0;
                border-radius: 4px;
                background: rgba(255, 255, 255, 0.75);
                border: 1px solid rgba(0,0,0,0.2);
            }
        """)
        self.preview_scrubber.hide()
        self._preview_user_scrubbing = False
        self.preview_duration_sec = 0.0
        self.preview_scrubber.sliderPressed.connect(self._on_preview_scrub_start)
        self.preview_scrubber.sliderReleased.connect(self._on_preview_scrub_end)
        self.preview_scrubber.valueChanged.connect(self._on_preview_scrub_value_changed)

        # Layout: center play button, bottom scrubber
        overlay_layout.addStretch(1)
        overlay_layout.addWidget(self.play_pause_btn, alignment=Qt.AlignCenter)
        overlay_layout.addStretch(1)
        overlay_layout.addWidget(self.preview_scrubber, alignment=Qt.AlignBottom)
        self.preview_layout.addWidget(self.overlay_container)

        # Install event filter on all preview-related widgets to catch hover properly
        self.preview_label.installEventFilter(self)
        self.overlay_container.installEventFilter(self)

        # Preview playback state (ffmpeg -> rawvideo -> QImage)
        self.preview_source_path = ""
        self.preview_playing = False
        self.preview_fps = 12
        self.preview_seek_seconds = 0.0
        self.preview_frame_index = 0
        self._preview_buf = bytearray()
        self._preview_frame_size = int(self.preview_w * self.preview_h * 3)  # rgb24

        # Star field animation state
        self.stars = []
        self.star_color = None
        self.star_bg_color = None

        self.preview_process = QProcess(self)
        self.preview_process.setProcessChannelMode(QProcess.MergedChannels)
        self.preview_process.readyReadStandardOutput.connect(self._on_preview_bytes)
        self.preview_process.finished.connect(self._on_preview_finished)

        # Handle hover events for overlay
        self.preview_container.installEventFilter(self)

        # Timer to update scrubber based on current preview time
        self.preview_ui_timer = QTimer(self)
        self.preview_ui_timer.setInterval(100)
        self.preview_ui_timer.timeout.connect(self._tick_preview_ui)
        self.preview_ui_timer.start()
        self.update_preview_controls_style()

        # Update Checker Label (hidden by default, shown if update available)
        self.update_label = QLabel("Update Available!")
        self.update_label.setAlignment(Qt.AlignCenter)
        self.update_label.setStyleSheet("background: #ffcc00; color: #333; padding: 4px; border-radius: 4px; font-weight: bold;")
        self.update_label.setCursor(Qt.PointingHandCursor)
        self.update_label.hide()
        self.update_label.mousePressEvent = self.open_update_url
        self.update_url = ""

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(4)

        # Check for updates
        self.check_updates()

        self.folder_observer = None
        self.watchdog_handler = None

        self.per_file_logs = {}  # file_path -> list of log lines
        self.manual_queue = []   # files dropped into Converted tab while idle
        self.conversion_workers = {}
        # Central log bus for conversion output with batched delivery
        self.log_bus = LogBus(maxlen=5000)
        def _deliver(lines):
            try:
                # Preserve user scroll position; only auto-scroll when already at bottom
                sb = self.console_output.verticalScrollBar()
                at_bottom = sb.value() == sb.maximum()
                for ln in lines:
                    self.console_output.appendPlainText(ln)
                if at_bottom:
                    cursor = self.console_output.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.console_output.setTextCursor(cursor)
                    self.console_output.ensureCursorVisible()
            except Exception:
                logger.debug("VideoConverterApp._deliver: suppressed error", exc_info=True)
        self.log_bus.start_delivery(_deliver, interval_ms=75)

        # Store the full tab stylesheet as a template
        self.tab_stylesheet_template = (
            "QTabBar {{ color: #333; }} "
            "QTabBar::tab {{ min-width: 140px; padding: 10px 16px; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 9pt; border-top-left-radius: 6px; border-top-right-radius: 6px; background: #F0F0F0; border: 1px solid #E0E0E0; border-bottom: none; margin-right: 2px; font-weight: normal; color: #333; }} "
            "QTabBar::tab:selected {{ background: white; border-bottom: 2px solid {highlight}; color: #333; }} "
            "QTabBar::tab:selected:focus {{ color: #333; }} "
            "QTabBar::tab:selected:!focus {{ color: #333; }} "
            "QTabBar::tab:selected:active {{ color: #333; }} "
            "QTabBar::tab:!selected {{ background: #F0F0F0; border: 1px solid #E0E0E0; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; color: #333; }} "
            "QTabBar::tab:!selected:focus {{ color: #333; }} "
            "QTabBar::tab:!selected:active {{ color: #333; }} "
            "QTabWidget::pane {{ margin: 4px; border-radius: 8px; }}"
        )
        # Set initial tab stylesheet with teal underline
        self.tabs = QTabWidget()
        self.tabs.setCursor(Qt.PointingHandCursor)
        self.tabs.setStyleSheet(self.tab_stylesheet_template.format(highlight="#43a296"))
        # Conversion Log Tab
        self.log_tab = QWidget()
        log_tab_layout = QVBoxLayout(self.log_tab)
        # Set margins to match video inspection tool
        log_tab_layout.setContentsMargins(11, 11, 11, 11)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setContextMenuPolicy(Qt.CustomContextMenu)
        self.console_output.customContextMenuRequested.connect(
            lambda pos: self.show_log_context_menu_global(self.console_output.mapToGlobal(pos))
        )
        # Clean modern styling for log output (scrollable, scrollbar hidden)
        self.console_output.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                background: white;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
            QPlainTextEdit QScrollBar {
                background: transparent;
                border: none;
                width: 0px; /* hide scrollbar track */
            }
            QPlainTextEdit QScrollBar::handle {
                background: transparent;
                border: none;
            }
            QPlainTextEdit QScrollBar::add-line,
            QPlainTextEdit QScrollBar::sub-line,
            QPlainTextEdit QScrollBar::up-arrow,
            QPlainTextEdit QScrollBar::down-arrow {
                background: transparent;
                border: none;
                height: 0px;
            }
            """)

        # Create a container widget for the log area with overlay
        self.log_container = QFrame()
        self.log_container.setFrameStyle(QFrame.Box)
        self.log_container.setStyleSheet("QFrame { border: 1px solid #E0E0E0; border-radius: 6px; background: white; }")
        self.log_container.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_container.customContextMenuRequested.connect(
            lambda pos: self.show_log_context_menu_global(self.log_container.mapToGlobal(pos))
        )

        # Create a layout for the container
        log_container_layout = QVBoxLayout(self.log_container)
        log_container_layout.setContentsMargins(0, 0, 0, 0)
        log_container_layout.setSpacing(0)

        # Add the console output to the container
        log_container_layout.addWidget(self.console_output)
        # Forward wheel events from container to console_output
        self.log_container.wheelEvent = lambda e: self._forward_log_wheel(e)
        self.log_container.installEventFilter(self)

        # Create drag and drop overlay widget with absolute positioning
        self.drag_drop_overlay = QWidget(self.log_container)
        self.drag_drop_overlay.setStyleSheet("""
            QWidget { 
                background: white; 
                border: 2px dashed #dee2e6; 
                border-radius: 8px; 
                margin: 10px;
            }
            QWidget:hover {
                border-color: #43a296;
                background: rgba(67, 162, 150, 0.1);
            }
        """)
        # Allow context menu on overlay to fall back to log actions
        self.drag_drop_overlay.setContextMenuPolicy(Qt.CustomContextMenu)
        self.drag_drop_overlay.customContextMenuRequested.connect(
            lambda pos: self.show_log_context_menu_global(self.drag_drop_overlay.mapToGlobal(pos))
        )
        self.drag_drop_overlay.setAcceptDrops(True)
        # Forward wheel events to console_output for consistent scrolling
        self.drag_drop_overlay.wheelEvent = lambda e: self._forward_log_wheel(e)
        self.drag_drop_overlay.installEventFilter(self)

        # Install event filter to handle mouse events selectively
        self.drag_drop_overlay.installEventFilter(self)

        # Create a layout for the overlay
        overlay_layout = QVBoxLayout(self.drag_drop_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        # Drag and drop text
        self.drag_drop_text = QLabel("Drag and drop media files here\nor select source folder to start monitoring and converting")
        self.drag_drop_text.setAlignment(Qt.AlignCenter)
        self.drag_drop_text.setStyleSheet("""
            QLabel { 
                color: #6c757d; 
                font-size: 12px; 
                background: rgba(255,255,255,0.85); 
                border-radius: 8px;
                border: none;
                padding: 12px;
            }
        """)
        self.drag_drop_text.setWordWrap(True)

        overlay_layout.addWidget(self.drag_drop_text)

        # Connect drag and drop events to the container instead
        self.log_container.dragEnterEvent = self.drag_drop_widget_drag_enter
        self.log_container.dragLeaveEvent = self.drag_drop_widget_drag_leave
        self.log_container.dropEvent = self.drag_drop_widget_drop
        self.log_container.setAcceptDrops(True)

        # Initialize conversion state tracking
        self.is_converting = False
        self.conversion_count = 0

        # Initially show the overlay
        self.drag_drop_overlay.show()

        # Connect resize event to reposition overlay
        self.log_container.resizeEvent = self.log_container_resize_event

        # Position overlay initially
        self.log_container_resize_event(None)

        log_tab_layout.addWidget(self.log_container)
        # Initialize footer widgets before make_footer
        self.lock_icon_label_log_tab = QLabel()
        self.status_label_log_tab = QLabel()
        monospaced_font = QFont("Courier New")
        self.status_label_log_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_log_tab.setFont(monospaced_font)
        self.footer_lock_labels = []
        self.footer_file_labels = []
        self.footer_broom_labels = []
        self.footer_layouts = []
        def make_footer(lock_label, status_label, clear_callback):
            layout = QHBoxLayout()
            lock_label.setPixmap(self.get_lock_icon_pixmap())
            lock_label.setFixedSize(36, 36)
            lock_label.setAlignment(Qt.AlignCenter)
            lock_label.setProperty("wiggleTarget", True)
            lock_label.setCursor(Qt.PointingHandCursor)
            lock_label.setToolTip("Lock/Unlock settings")
            lock_label.mousePressEvent = self.lock_icon_clicked
            lock_label.setStyleSheet("""
                QLabel { 
                    background: transparent; 
                    border: none; 
                    padding: 4px;
                }
                QLabel:hover {
                    background: #e9ecef;
                    border-radius: 18px;
                }
            """)
            # File icon button (dynamic)
            file_icon_path = self.get_icon_path('FILE')
            file_label = QLabel()
            if os.path.exists(file_icon_path):
                file_pixmap = QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                file_label.setPixmap(file_pixmap)
            file_label.setFixedSize(36, 36)
            file_label.setAlignment(Qt.AlignCenter)
            file_label.setCursor(Qt.PointingHandCursor)
            file_label.setToolTip("Select media files to convert")
            file_label.mousePressEvent = lambda event: self.open_file_dialog()
            file_label.setStyleSheet("""
                QLabel { 
                    background: transparent; 
                    border: none; 
                    padding: 4px;
                }
                QLabel:hover {
                    background: #e9ecef;
                    border-radius: 18px;
                }
            """)
            # Broom icon
            if self.locked:
                broom_icon_path = resource_path('graphics/GRAYSCALEBROOM.ico')
            else:
                broom_icon_path = resource_path('graphics/BROOM.ico')
            broom_label = QLabel()
            if os.path.exists(broom_icon_path):
                broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                broom_label.setPixmap(broom_pixmap)
            broom_label.setFixedSize(36, 36)
            broom_label.setAlignment(Qt.AlignCenter)
            broom_label.setCursor(Qt.PointingHandCursor)
            broom_label.setToolTip("Clear log")
            broom_label.mousePressEvent = clear_callback
            broom_label.setStyleSheet("""
                QLabel { 
                    background: transparent; 
                    border: none; 
                    padding: 4px;
                }
                QLabel:hover {
                    background: #e9ecef;
                    border-radius: 18px;
                }
            """)
            # Save references for update_lock_state_ui if needed
            if status_label is self.status_label_log_tab:
                self.file_label_log_tab = file_label
                self.broom_label_log_tab = broom_label
            elif status_label is self.status_label_converted_tab:
                self.file_label_converted_tab = file_label
                self.broom_label_converted_tab = broom_label
            elif status_label is self.status_label_inspection_tab:
                self.file_label_inspection_tab = file_label
                self.broom_label_inspection_tab = broom_label
            self.footer_lock_labels.append(lock_label)
            self.footer_file_labels.append(file_label)
            self.footer_broom_labels.append(broom_label)
            self.footer_layouts.append(layout)
            layout.addWidget(lock_label)
            layout.addWidget(file_label)
            layout.addWidget(broom_label)
            layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
            layout.addWidget(status_label)
            return layout
        # Wrap footer in a widget with explicit zero margins for show/hide control
        self.log_tab_footer_widget = QWidget()
        self.log_tab_footer = make_footer(self.lock_icon_label_log_tab, self.status_label_log_tab, self.clear_log_tab)
        # Explicitly set zero margins on both the widget and layout to match direct addLayout behavior
        self.log_tab_footer_widget.setContentsMargins(0, 0, 0, 0)
        self.log_tab_footer.setContentsMargins(0, 0, 0, 0)
        self.log_tab_footer_widget.setLayout(self.log_tab_footer)
        log_tab_layout.addWidget(self.log_tab_footer_widget)
        # Scroll wrapper for log tab (scrolling enabled, scrollbar hidden)
        self.log_tab_scroll = QScrollArea()
        self.log_tab_scroll.setWidgetResizable(True)
        self.log_tab_scroll.setFrameShape(QFrame.NoFrame)
        self.log_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_tab_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar { width: 0px; height: 0px; }
        """)
        self.log_tab_scroll.setWidget(self.log_tab)
        # Forward wheel events from the scroll area to the log text for smooth scrolling
        self.log_tab_scroll.wheelEvent = lambda e: self._forward_log_wheel(e)
        self.log_tab_scroll.installEventFilter(self)
        self.tabs.addTab(self.log_tab_scroll, "Conversion Log")

        # Converted Files Tab
        self.converted_files_tab = QWidget()
        converted_layout = QVBoxLayout(self.converted_files_tab)
        # Set margins to match conversion log baseline
        converted_layout.setContentsMargins(11, 11, 11, 11)
        self.converted_files_widget = ConvertedFilesWidget(button_style=getattr(self, 'current_button_style', None))
        # Forward drag/drop from the converted list to the main window handler
        self.converted_files_widget.drop_files_signal.connect(self._handle_converted_tab_drop)
        # Ensure per-file logs go to unified logs directory
        try:
            from utils.paths import get_data_dir
            self.converted_files_widget.set_log_folder(get_data_dir("logs"))
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)
        # Preview on selection in converted list
        try:
            self.converted_files_widget.preview_requested.connect(
                lambda path: self.preview_file(path) if path else self._clear_preview_display()
            )
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)
        # Clean modern styling for converted files widget
        self.converted_files_widget.setStyleSheet("QTableWidget { border: 1px solid #E0E0E0; border-radius: 6px; background: white; }")
        converted_layout.addWidget(self.converted_files_widget)
        # Initialize footer widgets before make_footer
        self.lock_icon_label_converted_tab = QLabel()
        self.status_label_converted_tab = QLabel()
        self.status_label_converted_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_converted_tab.setFont(monospaced_font)
        self.converted_footer = make_footer(self.lock_icon_label_converted_tab, self.status_label_converted_tab, self.clear_converted_tab)
        converted_layout.addLayout(self.converted_footer)
        # Scroll wrapper for converted files tab
        self.converted_tab_scroll = QScrollArea()
        self.converted_tab_scroll.setWidgetResizable(True)
        self.converted_tab_scroll.setFrameShape(QFrame.NoFrame)
        self.converted_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.converted_tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.converted_tab_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar { width: 0px; height: 0px; }
        """)
        self.converted_tab_scroll.setWidget(self.converted_files_tab)
        # Accept drops anywhere in the Converted tab container and forward them to the table
        self.converted_tab_scroll.setAcceptDrops(True)
        self.converted_tab_scroll.dragEnterEvent = lambda e: self.converted_files_widget.dragEnterEvent(e)
        self.converted_tab_scroll.dropEvent = lambda e: self.converted_files_widget.dropEvent(e)
        self.tabs.addTab(self.converted_tab_scroll, "Converted Files")

        # Inspection Tab
        self.inspection_tab = QWidget()
        inspection_layout = QVBoxLayout(self.inspection_tab)
        # Set margins to match conversion log baseline
        inspection_layout.setContentsMargins(11, 11, 11, 11)
        self.inspection_widget = InspectionWidget()
        # Clean modern styling for inspection widget
        self.inspection_widget.setStyleSheet("QWidget { border: 1px solid #E0E0E0; border-radius: 6px; background: white; }")
        # Context menu for inspection texts/areas
        try:
            self.inspection_widget.summary_text.setContextMenuPolicy(Qt.CustomContextMenu)
            self.inspection_widget.summary_text.customContextMenuRequested.connect(
                lambda pos: self.show_inspection_context_menu_global(
                    self.inspection_widget.summary_text.mapToGlobal(pos),
                    self.inspection_widget.summary_text
                )
            )
            self.inspection_widget.info_display.setContextMenuPolicy(Qt.CustomContextMenu)
            self.inspection_widget.info_display.customContextMenuRequested.connect(
                lambda pos: self.show_inspection_context_menu_global(
                    self.inspection_widget.info_display.mapToGlobal(pos),
                    self.inspection_widget.info_display
                )
            )
            # Drag/drop areas share the same menu, targeting their respective text widgets
            self.inspection_widget.summary_drag_drop.setContextMenuPolicy(Qt.CustomContextMenu)
            self.inspection_widget.summary_drag_drop.customContextMenuRequested.connect(
                lambda pos: self.show_inspection_context_menu_global(
                    self.inspection_widget.summary_drag_drop.mapToGlobal(pos),
                    self.inspection_widget.summary_text
                )
            )
            self.inspection_widget.json_drag_drop.setContextMenuPolicy(Qt.CustomContextMenu)
            self.inspection_widget.json_drag_drop.customContextMenuRequested.connect(
                lambda pos: self.show_inspection_context_menu_global(
                    self.inspection_widget.json_drag_drop.mapToGlobal(pos),
                    self.inspection_widget.info_display
                )
            )
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)
        inspection_layout.addWidget(self.inspection_widget)
        # Initialize footer widgets before make_footer
        self.lock_icon_label_inspection_tab = QLabel()
        self.status_label_inspection_tab = QLabel()
        self.status_label_inspection_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_inspection_tab.setFont(monospaced_font)
        self.inspection_footer = make_footer(self.lock_icon_label_inspection_tab, self.status_label_inspection_tab, self.clear_inspection_tab)
        inspection_layout.addLayout(self.inspection_footer)
        # If game already unlocked (system-wide), add controller icons now
        if get_game_unlocked():
            self.add_game_icons()
        # Scroll wrapper for inspection tab
        self.inspection_tab_scroll = QScrollArea()
        self.inspection_tab_scroll.setWidgetResizable(True)
        self.inspection_tab_scroll.setFrameShape(QFrame.NoFrame)
        self.inspection_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.inspection_tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.inspection_tab_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar { width: 0px; height: 0px; }
        """)
        self.inspection_tab_scroll.setWidget(self.inspection_tab)
        self.tabs.addTab(self.inspection_tab_scroll, "Video Inspection Tool")

        # PC Report Tab
        converting_or_monitoring = bool(self.running or getattr(self, 'is_converting', False))
        self.pc_report_widget = PCReportWidget(
            self,
            button_style=getattr(self, 'current_button_style', None),
            converting=converting_or_monitoring,
            locked=bool(getattr(self, 'locked', False))
        )
        self.pc_report_tab = QWidget()
        pc_report_layout = QVBoxLayout(self.pc_report_tab)
        pc_report_layout.setContentsMargins(11, 11, 11, 11)
        pc_report_layout.addWidget(self.pc_report_widget)
        self.lock_icon_label_pc_report_tab = QLabel()
        self.status_label_pc_report_tab = QLabel()
        self.status_label_pc_report_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_pc_report_tab.setFont(monospaced_font)
        pc_report_layout.addLayout(make_footer(self.lock_icon_label_pc_report_tab, self.status_label_pc_report_tab, self.clear_pc_report_tab))

        self.pc_report_tab_scroll = QScrollArea()
        self.pc_report_tab_scroll.setWidgetResizable(True)
        self.pc_report_tab_scroll.setFrameStyle(0)
        self.pc_report_tab_scroll.setWidget(self.pc_report_tab)
        self.tabs.addTab(self.pc_report_tab_scroll, "PC Report")

        # Lossless Editor Tab
        self.lossless_editor_widget = LosslessEditorWidget(
            SUPPORTED_FORMATS,
            self,
            button_style=getattr(self, 'current_button_style', None)
        )
        self.lossless_editor_tab = QWidget()
        lossless_editor_layout = QVBoxLayout(self.lossless_editor_tab)
        lossless_editor_layout.setContentsMargins(11, 11, 11, 11)
        lossless_editor_layout.addWidget(self.lossless_editor_widget)
        self.lock_icon_label_lossless_editor_tab = QLabel()
        self.status_label_lossless_editor_tab = QLabel()
        self.status_label_lossless_editor_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_lossless_editor_tab.setFont(monospaced_font)
        lossless_editor_layout.addLayout(make_footer(self.lock_icon_label_lossless_editor_tab, self.status_label_lossless_editor_tab, self.clear_lossless_editor_tab))
        self.lossless_editor_tab_scroll = QScrollArea()
        self.lossless_editor_tab_scroll.setWidgetResizable(True)
        self.lossless_editor_tab_scroll.setFrameStyle(0)
        self.lossless_editor_tab_scroll.setWidget(self.lossless_editor_tab)
        self.tabs.addTab(self.lossless_editor_tab_scroll, "Lossless Editor")

        # Multi-Source Recorder Tab
        self.multi_source_recorder_widget = MultiSourceRecorderWidget(
            self,
            button_style=getattr(self, 'current_button_style', None),
            load_saved_settings=True
        )
        self.multi_source_recorder_widget.start_btn.clicked.disconnect()
        self.multi_source_recorder_widget.start_btn.clicked.connect(self.toggle_process)
        self.multi_source_recorder_widget.stop_btn.clicked.disconnect()
        self.multi_source_recorder_widget.stop_btn.clicked.connect(self.toggle_process)
        self.multi_source_recorder_tab = QWidget()
        multi_source_recorder_layout = QVBoxLayout(self.multi_source_recorder_tab)
        multi_source_recorder_layout.setContentsMargins(11, 11, 11, 11)
        multi_source_recorder_layout.addWidget(self.multi_source_recorder_widget)
        self.lock_icon_label_multi_source_recorder_tab = QLabel()
        self.status_label_multi_source_recorder_tab = QLabel()
        self.status_label_multi_source_recorder_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_multi_source_recorder_tab.setFont(monospaced_font)
        multi_source_recorder_layout.addLayout(make_footer(self.lock_icon_label_multi_source_recorder_tab, self.status_label_multi_source_recorder_tab, self.clear_multi_source_recorder_tab))
        self.multi_source_recorder_tab_scroll = QScrollArea()
        self.multi_source_recorder_tab_scroll.setWidgetResizable(True)
        self.multi_source_recorder_tab_scroll.setFrameStyle(0)
        self.multi_source_recorder_tab_scroll.setWidget(self.multi_source_recorder_tab)
        self.tabs.addTab(self.multi_source_recorder_tab_scroll, "Multi-Source Recorder")

        # Media Player Tab. The player tree (4 video panels) is heavy and the tab is
        # hidden by default, so it is built lazily the first time the tab is shown via
        # _ensure_media_player_widget(). This keeps startup cheap and avoids building the
        # widget in the many headless tests that never open it.
        self.media_player_widget = None
        self.media_player_tab = QWidget()
        media_player_layout = QVBoxLayout(self.media_player_tab)
        media_player_layout.setContentsMargins(11, 11, 11, 11)
        self.media_player_layout = media_player_layout
        self.media_player_placeholder = QLabel("Loading media player…")
        self.media_player_placeholder.setAlignment(Qt.AlignCenter)
        media_player_layout.addWidget(self.media_player_placeholder)
        self.lock_icon_label_media_player_tab = QLabel()
        self.status_label_media_player_tab = QLabel()
        self.status_label_media_player_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_media_player_tab.setFont(monospaced_font)
        media_player_layout.addLayout(make_footer(self.lock_icon_label_media_player_tab, self.status_label_media_player_tab, self.clear_media_player_tab))
        self.media_player_tab_scroll = QScrollArea()
        self.media_player_tab_scroll.setWidgetResizable(True)
        self.media_player_tab_scroll.setFrameStyle(0)
        self.media_player_tab_scroll.setWidget(self.media_player_tab)
        self.tabs.addTab(self.media_player_tab_scroll, "Media Player")

        self.tool_tab_widgets = {
            "conversion_log": self.log_tab_scroll,
            "converted_files": self.converted_tab_scroll,
            "video_inspection": self.inspection_tab_scroll,
            "pc_report": self.pc_report_tab_scroll,
            "lossless_editor": self.lossless_editor_tab_scroll,
            "multi_source_recorder": self.multi_source_recorder_tab_scroll,
            "media_player": self.media_player_tab_scroll,
        }
        self.apply_tool_tab_visibility()
        if get_game_unlocked():
            self.add_game_icons()

        # Sidebar preview mirrors the recorder's expected output layout while the
        # Multi-Source Recorder tab is active, refreshing when its mode/sources change.
        self._showing_recorder_layout_preview = False
        self.tabs.currentChanged.connect(self._on_tab_changed_for_layout_preview)
        try:
            self.multi_source_recorder_widget.layout_preview_changed.connect(
                self._refresh_recorder_layout_preview_if_active
            )
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)

        central_widget = QWidget()
        central_widget.setMouseTracking(True)  # Enable mouse tracking for hover events
        self.setCentralWidget(central_widget)
        self.central_widget = central_widget  # Save reference for drag events
        main_layout = QHBoxLayout(central_widget)

        # Left side: logo + settings + preview + start/stop button
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.logo_label, alignment=Qt.AlignHCenter)
        left_layout.addWidget(self.update_label, alignment=Qt.AlignHCenter)  # under logo

        # Current settings display in sidebar
        self.settings_display = QLabel()
        self.settings_display.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.settings_display.setStyleSheet("""
            QLabel { 
                color: #495057; 
                font-size: 9pt; 
                background: transparent; 
                border: none;
                margin: 0px;
                padding: 0px;
                text-align: justify;
            }
        """)
        self.settings_display.setWordWrap(True)
        self.settings_display.setFixedWidth(180)
        # Make it clickable with hover effects
        self.settings_display.mousePressEvent = self.settings_display_clicked
        self.settings_display.enterEvent = self.settings_display_enter
        self.settings_display.leaveEvent = self.settings_display_leave
        self.settings_display.setCursor(Qt.PointingHandCursor)  # Show hand cursor on hover
        self.settings_display.setToolTip("Open Settings")  # Add tooltip
        left_layout.addWidget(self.settings_display)

        # Preview goes below settings text (no special centering; align with other sidebar items)
        left_layout.addWidget(self.preview_container)

        left_layout.addStretch()

        # Start/Stop Button
        self.start_button = QPushButton("Start")
        # Match settings + preview width for perfect edge alignment
        self.start_button.setFixedWidth(180)
        self.start_button.setToolTip("Start or stop the automatic conversion process.")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self.toggle_process)
        left_layout.addWidget(self.start_button)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.tabs)

        # Add compact mode toggle and burger menu to the top right
        from PyQt5.QtWidgets import QToolButton, QMenu
        self.burger_button = QToolButton()
        self.burger_button.setIconSize(QSize(43, 43))
        self.burger_button.setFixedSize(43, 43)
        self.burger_button.setPopupMode(QToolButton.InstantPopup)
        self.burger_button.setCursor(Qt.PointingHandCursor)
        # Create the dropdown menu
        burger_menu = QMenu()
        # Add actions without icons initially - they will be set by update_icons()
        burger_menu.addAction("Info", self.show_info)
        burger_menu.addAction("Help", self.open_help_document)
        burger_menu.addSeparator()
        burger_menu.addSeparator()
        burger_menu.addAction("Open Source Folder", self.open_source_folder_in_explorer)
        burger_menu.addAction("Open Destination Folder", self.open_destination_folder_in_explorer)
        burger_menu.addAction("Open Backup Folder", self.open_backup_folder_in_explorer)
        burger_menu.addSeparator()
        burger_menu.addAction("Settings", self.show_settings)
        burger_menu.addAction("Check for Updates", self.check_for_updates)
        burger_menu.addSeparator()
        burger_menu.addAction("Quit", self.quit_application)
        self.burger_button.setMenu(burger_menu)
        # Set the burger icon for the initial state
        burger_icon_path = self.get_icon_path('BURGER')
        if os.path.exists(burger_icon_path):
            self.burger_button.setIcon(QIcon(QPixmap(burger_icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        top_right_widget = QWidget()
        top_right_layout = QHBoxLayout(top_right_widget)
        top_right_layout.setContentsMargins(0, 0, 0, 0)
        top_right_layout.setSpacing(4)
        top_right_layout.addWidget(self.burger_button)
        self.tabs.setCornerWidget(top_right_widget, Qt.TopRightCorner)
        self.burger_button.setStyleSheet("""
            QToolButton { 
                background: transparent; 
                border: none; 
                padding: 4px;
                margin: 0px;
                spacing: 0px;
            }
            QToolButton:hover {
                background: #e9ecef;
                border-radius: 18px;
            }
            QToolButton::menu-indicator { 
                image: none; 
            }
        """)
        # React to tab changes (e.g., restore log view, keep UI in sync)
        try:
            self.tabs.currentChanged.connect(self.on_tab_changed)
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)
        # Add Compact Mode toggle to burger menu
        # self.compact_mode_action = burger_menu.addAction("Compact Mode")
        # self.compact_mode_action.setCheckable(True)
        # self.compact_mode_action.toggled.connect(self.toggle_compact_mode)
        # Remove old File menu

        # --- Compact mode widgets ---
        # self.compact_widget = QWidget()
        # compact_layout = QVBoxLayout(self.compact_widget)
        # compact_layout.setContentsMargins(10, 10, 10, 10)
        # compact_layout.setSpacing(8)
        # # Logo
        # self.compact_logo = QLabel()
        # self.compact_logo.setPixmap(self.logo_label.pixmap())
        # self.compact_logo.setAlignment(Qt.AlignCenter)
        # compact_layout.addWidget(self.compact_logo)
        # # Row: burger, lock, broom
        # row = QHBoxLayout()
        # row.setSpacing(12)
        # row.setContentsMargins(0, 0, 0, 0)
        # row.setAlignment(Qt.AlignHCenter)
        # # Helper for framed icon
        # def make_framed_icon(widget, icon_widget, size=40):
        #     frame = QWidget()
        #     frame_layout = QHBoxLayout(frame)
        #     frame_layout.setContentsMargins(0, 0, 0, 0)
        #     frame_layout.setSpacing(0)
        #     icon_widget.setParent(frame)
        #     icon_widget.setFixedSize(size, size)
        #     # Only set alignment if QLabel
        #     from PyQt5.QtWidgets import QLabel
        #     if isinstance(icon_widget, QLabel):
        #         icon_widget.setAlignment(Qt.AlignCenter)
        #     frame.setFixedSize(size + 8, size + 8)
        #     # Use thin black border to match normal mode
        #     frame.setStyleSheet("QWidget { border: 1px solid #000; background: #E0E0E0; border-radius: 4px; }")
        #     frame_layout.addStretch()
        #     frame_layout.addWidget(icon_widget, alignment=Qt.AlignCenter)
        #     frame_layout.addStretch()
        #     return frame
        # # Burger
        # self.compact_burger = QToolButton()
        # self.compact_burger.setIcon(self.burger_button.icon())
        # self.compact_burger.setIconSize(QSize(36, 36))
        # self.compact_burger.setMenu(self.burger_button.menu())
        # self.compact_burger.setPopupMode(QToolButton.InstantPopup)
        # self.compact_burger.setCursor(Qt.PointingHandCursor)
        # self.compact_burger.setStyleSheet("""
        #     QToolButton {
        #         border: none;
        #         background: transparent;
        #         padding: 4px;
        #     }
        #     QToolButton:hover {
        #         background: #e9ecef;
        #         border-radius: 18px;
        #     }
        #     QToolButton::menu-indicator {
        #         image: none;
        #     }
        # """)
        # self.compact_burger.setFixedSize(36, 36)
        # burger_frame = make_framed_icon(self, self.compact_burger)
        # row.addWidget(burger_frame)
        # # Lock
        # self.compact_lock = QLabel()
        # self.compact_lock.setPixmap(self.get_lock_icon_pixmap())
        # self.compact_lock.setFixedSize(36, 36)
        # self.compact_lock.setAlignment(Qt.AlignCenter)
        # self.compact_lock.setCursor(Qt.PointingHandCursor)
        # self.compact_lock.setToolTip("Lock/Unlock settings")
        # self.compact_lock.mousePressEvent = self.lock_icon_clicked
        # self.compact_lock.setStyleSheet("background: transparent; border: none;")
        # lock_frame = make_framed_icon(self, self.compact_lock)
        # row.addWidget(lock_frame)
        # # File (new, dynamic)
        # self.compact_file = QLabel()
        # file_icon_path = self.get_icon_path('FILE')
        # if os.path.exists(file_icon_path):
        #     file_pixmap = QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        #     self.compact_file.setPixmap(file_pixmap)
        # self.compact_file.setFixedSize(36, 36)
        # self.compact_file.setAlignment(Qt.AlignCenter)
        # self.compact_file.setCursor(Qt.PointingHandCursor)
        # self.compact_file.setToolTip("Select media files to convert")
        # self.compact_file.mousePressEvent = lambda event: self.open_file_dialog()
        # self.compact_file.setStyleSheet("background: transparent; border: none;")
        # file_frame = make_framed_icon(self, self.compact_file)
        # row.addWidget(file_frame)
        # # Broom
        # self.compact_broom = QLabel()
        # broom_icon_path = resource_path('graphics/GRAYSCALEBROOM.ico') if self.locked else resource_path('graphics/BROOM.ico')
        # if os.path.exists(broom_icon_path):
        #     broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        #     self.compact_broom.setPixmap(broom_pixmap)
        # self.compact_broom.setFixedSize(36, 36)
        # self.compact_broom.setAlignment(Qt.AlignCenter)
        # self.compact_broom.setCursor(Qt.PointingHandCursor)
        # self.compact_broom.setToolTip("Clear log")
        # self.compact_broom.mousePressEvent = self.clear_log_tab
        # self.compact_broom.setStyleSheet("background: transparent; border: none;")
        # broom_frame = make_framed_icon(self, self.compact_broom)
        # row.addWidget(broom_frame)
        # row.addStretch()
        # compact_layout.addLayout(row)
        # # Start/Stop button
        # self.compact_start_button = QPushButton()
        # self.compact_start_button.setText(self.start_button.text())
        # self.compact_start_button.setStyleSheet(self.start_button.styleSheet())
        # # Sync enabled/disabled state
        # self.compact_start_button.setEnabled(self.start_button.isEnabled())
        # # Add status to compact mode
        # self.compact_status_label = QLabel("Status: Not monitoring")
        # self.compact_status_label.setAlignment(Qt.AlignCenter)
        # self.compact_status_label.setStyleSheet("QLabel { color: #6c757d; font-size: 10px; background: transparent; border: none; }")
        # compact_layout.addWidget(self.compact_status_label)

        # compact_layout.addWidget(self.compact_start_button)
        # self.compact_widget.hide()
        # main_layout.addWidget(self.compact_widget)
        # --- End compact mode widgets ---
        self.setStyleSheet(self.styleSheet() + '\nQMainWindow { border-radius: 8px; background: #F5F5F5; }')
        self.is_compact = False
        # At the very end of init_ui, call update_icons to ensure all icons are set for the initial state
        self.update_icons()

        # Initialize button styles and tab highlighting for the initial state
        self.update_all_button_styles()
        self.update_highlight_colors()

        # Initialize status labels for the initial state
        self.update_status_labels()

        # Initialize settings display for the initial state
        self.update_settings_display()

        # Center the main window on screen on first show
        self.center_on_screen()

        # Enable mouse tracking on the main window for proper hover detection
        self.setMouseTracking(True)

        # Set the initial start button state after all widgets are created
        self.set_start_button_state(is_running=self.running)

        # Initialize system tray icon and ensure app keeps running when window is closed
        self.init_tray_icon()
        QApplication.setQuitOnLastWindowClosed(False)

        self.log_tab_layout = log_tab_layout
        self.log_container_index = self.log_tab_layout.indexOf(self.log_container)

    def open_pc_report_dialog(self):
        try:
            index = self.tabs.indexOf(self.pc_report_tab_scroll)
            if index >= 0:
                self.tabs.setCurrentIndex(index)
            if hasattr(self, 'pc_report_widget'):
                self.pc_report_widget.on_run()
        except Exception as e:
            logger.error(f"Failed to start embedded PC Report: {e}")

    def apply_tool_tab_visibility(self):
        visible_tabs = self.settings.get('visible_tool_tabs', {})
        for key, widget in getattr(self, 'tool_tab_widgets', {}).items():
            index = self.tabs.indexOf(widget)
            if index < 0:
                continue
            try:
                self.tabs.setTabVisible(index, bool(visible_tabs.get(key, False)))
            except AttributeError:
                widget.setVisible(bool(visible_tabs.get(key, False)))

    def lock_icon_clicked(self, event):
        self.toggle_lock()

    def get_lock_icon_pixmap(self):
        if self.locked:
            icon_path = resource_path('graphics/GRAYSCALELOCK.ico')
        elif self.is_active_workflow_visual_state():
            # Monitoring state: use green lock/unlock
            if hasattr(self, 'locked') and self.locked:
                icon_path = resource_path('graphics/GREENLOCK.ico')
            else:
                icon_path = resource_path('graphics/GREENUNLOCK.ico')
        else:
            # Default state: use teal lock/unlock
            if hasattr(self, 'locked') and self.locked:
                icon_path = resource_path('graphics/LOCK.ico')
            else:
                icon_path = resource_path('graphics/UNLOCK.ico')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            return pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap(36, 36)

    def log_container_resize_event(self, event):
        """Handle resize events to reposition the overlay."""
        if hasattr(self, 'drag_drop_overlay'):
            # Position overlay to cover the entire container
            self.drag_drop_overlay.setGeometry(0, 0, self.log_container.width(), self.log_container.height())
        if event is not None:
            event.accept()



    def update_log_display(self):
        """Update the log display based on monitoring and conversion state."""
        if hasattr(self, 'drag_drop_overlay'):
            # Check if there's log content to determine transparency
            has_log_content = len(self.console_output.toPlainText().strip()) > 0
            # Only show the overlay if not hidden by a drop event
            if not self.drag_drop_overlay.isHidden():
                if self.running or self.is_converting or has_log_content:
                    # Semi-transparent overlay when monitoring, converting, or has log content
                    self.drag_drop_overlay.setStyleSheet("""
                        QWidget { 
                            background: rgba(255, 255, 255, 0.5); 
                            border: 2px dashed #dee2e6; 
                            border-radius: 8px; 
                            margin: 10px;
                        }
                        QWidget:hover {
                            border-color: #43a296;
                            background: rgba(67, 162, 150, 0.1);
                        }
                    """)
                else:
                    # Fully opaque overlay when idle and no log content
                    self.drag_drop_overlay.setStyleSheet("""
                        QWidget { 
                            background: white; 
                            border: 2px dashed #dee2e6; 
                            border-radius: 8px; 
                            margin: 10px;
                        }
                        QWidget:hover {
                            border-color: #43a296;
                            background: rgba(67, 162, 150, 0.1);
                        }
                    """)
                # Hide the overlay text ONLY if conversion is running or after a drop
                if self.is_converting:
                    self.drag_drop_text.hide()
                # Always show the overlay (unless hidden by drop)
                self.drag_drop_overlay.show()

    def set_start_button_state(self, is_running):
        if self.locked:
            self.start_button.setEnabled(False)
            self.start_button.setText("Locked")
            # Modern grayscale style for locked state
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: #F0F0F0;
                    color: #999;
                    border: 1px solid #E0E0E0;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """)
            self.start_button.setToolTip("Application is locked.")
            return
        recorder_mode = self.is_recorder_tab_active() and not is_running and not getattr(self, 'is_converting', False)
        recorder_recording = recorder_mode and self.is_recorder_recording()
        if self.is_recorder_tab_active() and getattr(self, 'is_converting', False) and not is_running and not recorder_recording:
            self.start_button.setEnabled(False)
            self.start_button.setText("Converting...")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: #F0F0F0;
                    color: #999;
                    border: 1px solid #E0E0E0;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """)
            self.start_button.setToolTip("Recording is unavailable while conversion is running.")
            return
        self.start_button.setEnabled(True)
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        recorder_status = (
            recorder.status_label.text()
            if recorder and hasattr(recorder, 'status_label')
            else ""
        )
        recorder_starting = bool(recorder_mode and recorder_status == "Starting recording...")
        recorder_stopping = bool(
            recorder_mode
            and recorder_status == "Stopping..."
        )
        if recorder_starting:
            self.start_button.setEnabled(False)
            self.start_button.setText("Starting...")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: #F0F0F0;
                    color: #999;
                    border: 1px solid #E0E0E0;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """)
            self.start_button.setToolTip("Releasing the camera preview before recording starts.")
            return
        if recorder_stopping:
            self.start_button.setEnabled(False)
            self.start_button.setText("Stopping...")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: #F0F0F0;
                    color: #999;
                    border: 1px solid #E0E0E0;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """)
            self.start_button.setToolTip("Finishing and saving the active recording.")
            return
        if is_running or recorder_recording:
            self.start_button.setText("Stop Recording" if recorder_mode else "Stop")
            # Update log display based on monitoring state
            self.update_log_display()
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #92cb4f, stop:1 #33a16d);
                    border: 1px solid #2d7d6f;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    color: white;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9dd55a, stop:1 #92cb4f);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33a16d, stop:1 #2d7d6f);
                }
            """)
            if recorder_mode:
                self.start_button.setToolTip("Stop the active multi-source recording.")
            else:
                self.start_button.setToolTip("Stop monitoring the source folder for files to convert.")
        else:
            self.start_button.setText("Start Recording" if recorder_mode else "Start")
            # Update log display based on monitoring state
            self.update_log_display()
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #43a296, stop:1 #3a9284);
                    border: 1px solid #2d7d6f;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    color: white;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4bb3a7, stop:1 #43a296);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a9284, stop:1 #2d7d6f);
                }
            """)
            if recorder_mode:
                self.start_button.setToolTip("Start recording from the enabled recorder sources.")
            else:
                self.start_button.setToolTip("Start monitoring the source folder for files to convert.")
        self.update_icons()
        # After updating main start_button, also update compact
        if hasattr(self, 'compact_start_button'):
            self.update_compact_start_button()
        # Also update compact logo
        if hasattr(self, 'compact_logo'):
            self.update_compact_logo()
        # Update all button styles based on monitoring state
        self.update_all_button_styles()
        # Update converted files widget button style
        if hasattr(self, 'converted_files_widget'):
            self.converted_files_widget.update_button_style(self.current_button_style)

    def toggle_lock(self):
        self.locked = not self.locked
        self.settings['locked'] = self.locked
        save_settings(self.settings)
        logger.info(f"Toggle lock: self.locked is now {self.locked}")
        self.update_lock_state_ui()
        self.update_icons()  # Ensure icons (including burger) update on lock/unlock
        self.update_all_button_styles()  # Update button styles for lock state
        self.update_highlight_colors()  # Update tab highlighting for lock state
        logger.info(f"Application {'locked' if self.locked else 'unlocked'}.")
        self.append_log(f"Application {'locked' if self.locked else 'unlocked'}.")

    def update_lock_state_ui(self):
        # Remove settings_action, info_action, help_action enable/disable since they are now in the burger menu
        # Optionally, disable the burger button if locked, or leave as is
        # self.burger_button.setEnabled(not self.locked)  # Uncomment if you want to disable the menu when locked
        self.set_menu_icons()
        # Update lock and broom icons in all footers
        self.lock_icon_label_log_tab.setPixmap(self.get_lock_icon_pixmap())
        self.lock_icon_label_converted_tab.setPixmap(self.get_lock_icon_pixmap())
        self.lock_icon_label_inspection_tab.setPixmap(self.get_lock_icon_pixmap())
        for lock_label in getattr(self, 'footer_lock_labels', []):
            lock_label.setPixmap(self.get_lock_icon_pixmap())
        # Update broom icons
        broom_icon_path = resource_path('graphics/GRAYSCALEBROOM.ico') if self.locked else resource_path('graphics/BROOM.ico')
        if os.path.exists(broom_icon_path):
            broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            for broom_label in getattr(self, 'footer_broom_labels', []):
                broom_label.setPixmap(broom_pixmap)
        if hasattr(self, 'broom_label_log_tab'):
            if os.path.exists(broom_icon_path):
                broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                self.broom_label_log_tab.setPixmap(broom_pixmap)
        if hasattr(self, 'broom_label_converted_tab'):
            if os.path.exists(broom_icon_path):
                broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                self.broom_label_converted_tab.setPixmap(broom_pixmap)
        if hasattr(self, 'broom_label_inspection_tab'):
            if os.path.exists(broom_icon_path):
                broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                self.broom_label_inspection_tab.setPixmap(broom_pixmap)
        self.set_start_button_state(is_running=self.running)
        self.update_status_labels()

    def set_status_label(self, label, is_running):
        label.setTextFormat(Qt.RichText)
        if self.locked:
            label.setText("Status: Locked <font color='#888888'>●</font>")  # Gray
        elif self.active_conversion_count > 0:
            label.setText("Status: Converting <font color='#00cc00'>●</font>")  # Green
        elif self.running:
            label.setText("Status: Monitoring <font color='#FFD700'>●</font>")  # Yellow
        else:
            label.setText("Status: Not monitoring <font color='#43a296'>●</font>")  # Teal

    def is_recorder_tab_active(self):
        return (
            hasattr(self, 'multi_source_recorder_tab_scroll')
            and self.tabs.currentWidget() is self.multi_source_recorder_tab_scroll
        )

    def is_recorder_recording(self):
        widget = getattr(self, 'multi_source_recorder_widget', None)
        if not widget:
            return False
        for process in getattr(widget, 'processes', []):
            try:
                if process.state() != QProcess.NotRunning:
                    return True
            except RuntimeError:
                continue
        status_label = getattr(widget, 'status_label', None)
        return bool(status_label and status_label.text() in ("Recording", "Stopping..."))

    def is_active_workflow_visual_state(self):
        return bool(
            getattr(self, 'running', False)
            or getattr(self, 'active_conversion_count', 0) > 0
            or self.is_recorder_recording()
        )

    def update_single_workflow_availability(self):
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        if recorder:
            conversion_busy = bool(getattr(self, 'running', False) or getattr(self, 'is_converting', False))
            recording = self.is_recorder_recording()
            recorder.setEnabled(not conversion_busy or recording)
            if conversion_busy and not recording and hasattr(recorder, 'status_label'):
                recorder.status_label.setText("Unavailable while conversion is running")
            elif not recording and hasattr(recorder, 'status_label') and "Unavailable" in recorder.status_label.text():
                recorder.status_label.setText("Not recording")
            self.update_recorder_footer_status()
        self._apply_recording_tab_lock()
        if hasattr(self, 'start_button'):
            self.set_start_button_state(is_running=getattr(self, 'running', False))

    def _recorder_tab_is_active(self):
        recorder_scroll = getattr(self, 'multi_source_recorder_tab_scroll', None)
        tabs = getattr(self, 'tabs', None)
        if recorder_scroll is None or tabs is None:
            return False
        return tabs.currentWidget() is recorder_scroll

    def _ensure_media_player_widget(self):
        if self.media_player_widget is not None:
            return self.media_player_widget
        widget = MediaPlayerWidget(
            self,
            button_style=getattr(self, 'current_button_style', None)
        )
        self.media_player_widget = widget
        placeholder = getattr(self, 'media_player_placeholder', None)
        if placeholder is not None:
            self.media_player_layout.removeWidget(placeholder)
            placeholder.deleteLater()
            self.media_player_placeholder = None
        self.media_player_layout.insertWidget(0, widget)
        return widget

    def _on_tab_changed_for_layout_preview(self, _index=None):
        media_scroll = getattr(self, 'media_player_tab_scroll', None)
        if media_scroll is not None and self.tabs.currentWidget() is media_scroll:
            self._ensure_media_player_widget()
        if self._recorder_tab_is_active():
            self._show_recorder_layout_preview()
        elif self._showing_recorder_layout_preview:
            # Leaving the recorder tab: drop the schematic so a later file preview is clean.
            self._showing_recorder_layout_preview = False
            self._set_preview_placeholder("No Preview")

    def _refresh_recorder_layout_preview_if_active(self):
        if self._recorder_tab_is_active():
            self._show_recorder_layout_preview()

    def _show_recorder_layout_preview(self):
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        container = getattr(self, 'preview_container', None)
        label = getattr(self, 'preview_label', None)
        if recorder is None or container is None or label is None:
            return
        mode = recorder.output_mode_combo.currentText()
        rects = recorder.current_layout_preview_rects()
        pixmap = self._build_layout_preview_pixmap(
            mode, rects, max(2, container.width()), max(2, container.height())
        )
        label.setText("")
        label.setPixmap(pixmap)
        self._showing_recorder_layout_preview = True

    def _build_layout_preview_pixmap(self, mode, rects, width, height):
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#1b2227"))
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            # "Separate videos" are distinct files, so draw each tile inset with a gap;
            # "Combined grid" is one frame, so tiles sit flush. PiP draws insets on top.
            mode_text = (mode or "").strip().lower()
            gap = 4 if mode_text.startswith("separate") else 1
            accent = QColor("#43a296")
            font = QFont()
            font.setPixelSize(max(9, height // 7))
            font.setBold(True)
            painter.setFont(font)
            for order, (nx, ny, nw, nh) in enumerate(rects):
                x = int(round(nx * width)) + gap
                y = int(round(ny * height)) + gap
                w = max(1, int(round(nw * width)) - 2 * gap)
                h = max(1, int(round(nh * height)) - 2 * gap)
                is_pip_inset = mode_text.startswith("picture") and order > 0
                painter.setPen(QPen(accent, 2))
                painter.setBrush(QBrush(QColor("#2c353b") if is_pip_inset else QColor("#222b30")))
                painter.drawRoundedRect(x, y, w, h, 4, 4)
                painter.setPen(QPen(QColor("#cfd6da")))
                painter.drawText(x, y, w, h, Qt.AlignCenter, str(order + 1))
        finally:
            painter.end()
        return pixmap

    def _apply_recording_tab_lock(self):
        # While a recording is active (or starting), gray out every other tab so the user
        # cannot switch away and accidentally start a conversion/inspection that competes
        # with the live capture. The Multi-Source Recorder tab stays enabled so recording
        # can still be stopped.
        tabs = getattr(self, 'tabs', None)
        recorder_scroll = getattr(self, 'multi_source_recorder_tab_scroll', None)
        if tabs is None or recorder_scroll is None:
            return
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        status_text = recorder.status_label.text() if recorder and hasattr(recorder, 'status_label') else ""
        locked = self.is_recorder_recording() or status_text == "Starting recording..."
        recorder_index = tabs.indexOf(recorder_scroll)
        for index in range(tabs.count()):
            if index == recorder_index:
                tabs.setTabEnabled(index, True)
            else:
                tabs.setTabEnabled(index, not locked)

    def update_recorder_footer_status(self):
        label = getattr(self, 'status_label_multi_source_recorder_tab', None)
        if not label:
            return
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        status_text = recorder.status_label.text() if recorder and hasattr(recorder, 'status_label') else ""
        if "failed" in status_text.lower():
            label.setText("Status: Recording failed <font color='#dc3545'>●</font>")
        elif status_text == "Starting recording...":
            label.setText("Status: Starting <font color='#ffc107'>●</font>")
        elif self.is_recorder_recording():
            label.setText("Status: Recording <font color='#00cc00'>●</font>")
        else:
            label.setText("Status: Not recording <font color='#43a296'>●</font>")

    def update_status_labels(self):
        self.set_status_label(self.status_label_log_tab, self.status_running)
        self.set_status_label(self.status_label_converted_tab, self.status_running)
        self.set_status_label(self.status_label_inspection_tab, self.status_running)
        # Update compact mode status
        if hasattr(self, 'compact_status_label'):
            if self.locked:
                self.compact_status_label.setText("Status: Locked")
                self.compact_status_label.setStyleSheet("QLabel { color: #6c757d; font-size: 10px; background: transparent; border: none; }")
            elif self.active_conversion_count > 0:
                self.compact_status_label.setText("Status: Converting")
                self.compact_status_label.setStyleSheet("QLabel { color: #28a745; font-size: 10px; background: transparent; border: none; }")
            elif self.running:
                self.compact_status_label.setText("Status: Monitoring")
                self.compact_status_label.setStyleSheet("QLabel { color: #ffc107; font-size: 10px; background: transparent; border: none; }")
            else:
                self.compact_status_label.setText("Status: Not monitoring")
                self.compact_status_label.setStyleSheet("QLabel { color: #dc3545; font-size: 10px; background: transparent; border: none; }")

        # When setting the lock icon label, always set fixed size and alignment
        self.lock_icon_label_log_tab.setPixmap(self.get_lock_icon_pixmap())
        self.lock_icon_label_log_tab.setFixedSize(36, 36)
        self.lock_icon_label_log_tab.setAlignment(Qt.AlignCenter)
        self.lock_icon_label_converted_tab.setPixmap(self.get_lock_icon_pixmap())
        self.lock_icon_label_converted_tab.setFixedSize(36, 36)
        self.lock_icon_label_converted_tab.setAlignment(Qt.AlignCenter)
        self.lock_icon_label_inspection_tab.setPixmap(self.get_lock_icon_pixmap())
        self.lock_icon_label_inspection_tab.setFixedSize(36, 36)
        self.lock_icon_label_inspection_tab.setAlignment(Qt.AlignCenter)
        for lock_label in getattr(self, 'footer_lock_labels', []):
            lock_label.setPixmap(self.get_lock_icon_pixmap())
            lock_label.setFixedSize(36, 36)
            lock_label.setAlignment(Qt.AlignCenter)

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Always use teal logo for tray icon
        tray_icon_path = self.icon_color if os.path.exists(self.icon_color) else self.icon_gray
        self.tray_icon.setIcon(QIcon(tray_icon_path))
        self.tray_icon.setToolTip("Video Converter Application")
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show_window)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_application)
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
        """Handle window close button.

        - If user enabled `close_on_x`, fully exit the application.
        - Otherwise, ignore and hide to system tray.
        """
        try:
            should_close = bool(self.settings.get('close_on_x', False))
        except Exception:
            should_close = False
        if should_close:
            event.accept()
            self.quit_application()
        else:
            event.ignore()
            self.hide()

    def shutdown(self):
        self.running = False
        self.status_running = False
        try:
            self._stop_preview_process()
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        try:
            recorder = getattr(self, 'multi_source_recorder_widget', None)
            if recorder and hasattr(recorder, 'shutdown'):
                recorder.shutdown()
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        try:
            player = getattr(self, 'media_player_widget', None)
            if player and hasattr(player, 'shutdown'):
                player.shutdown()
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        # Wait for the update-check QThread to finish. If the window (and thus the QThread
        # wrapper) is destroyed while the thread is still running, Qt aborts the process
        # ("QThread: Destroyed while thread is still running") - a non-deterministic crash
        # that shows up when many windows are created and torn down in one process.
        try:
            update_thread = getattr(self, 'update_thread', None)
            if update_thread is not None:
                update_thread.quit()
                update_thread.wait(3000)
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        # Hide the system tray icon so it unregisters from the Windows shell. It is parented
        # to the window, so Qt frees it with the window; we must NOT deleteLater() it here or
        # the later deferred-delete would fire on an already-freed child.
        try:
            tray = getattr(self, 'tray_icon', None)
            if tray is not None:
                tray.hide()
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        try:
            if self.folder_observer:
                self.folder_observer.stop()
                self.folder_observer.join(timeout=3)
                self.folder_observer = None
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        for timer_name in ('preview_ui_timer', 'star_field_timer', 'game_progress_timer'):
            timer = getattr(self, timer_name, None)
            try:
                if timer:
                    timer.stop()
            except Exception:
                logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        for worker in list(getattr(self, 'conversion_workers', {}).values()):
            try:
                worker.cancel()
            except Exception:
                logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        try:
            self.threadpool.waitForDone(3000)
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)

    def check_updates(self):
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_thread = UpdateWorker(self.update_checker)
        self.update_thread.start()

    def on_update_available(self, version, url):
        self.update_url = url
        self.update_label.setText(f"Update v{version} Available!")
        self.update_label.setToolTip(f"Click to download update")
        self.update_label.show()

    def open_update_url(self, event):
        import webbrowser
        if self.update_url:
            webbrowser.open(self.update_url)

    def handle_media_error(self):
        """
        Backwards-compatible hook: we no longer use QMediaPlayer (DirectShow),
        but keep this method so older call sites won't crash.
        """
        try:
            self.append_log("Preview Error: Playback failed. Falling back to thumbnail.", is_error=True)
        except Exception:
            logger.debug("VideoConverterApp.handle_media_error: suppressed error", exc_info=True)
        try:
            if getattr(self, 'preview_source_path', ''):
                self._generate_and_show_thumbnail(self.preview_source_path)
        except Exception:
            logger.debug("VideoConverterApp.handle_media_error: suppressed error", exc_info=True)

    def show_thumbnail_fallback(self):
        """Backward compatible wrapper for older callers."""
        try:
            if getattr(self, 'preview_source_path', ''):
                self._generate_and_show_thumbnail(self.preview_source_path)
        except Exception as e:
            logger.error(f"Thumbnail fallback failed: {e}")

    def logo_clicked(self, event):
        if self.locked:
            logger.info("Application is locked.")
            self._show_locked_dialog()
            return
        self.show_settings()

    def append_log(self, message, is_error=False):
        if is_error:
            self.console_output.appendHtml(f'<span style="color:#a94442;font-weight:bold;">{message}</span>')
        else:
            self.console_output.appendPlainText(message)
        # Always auto-scroll to the latest line and ensure visibility
        try:
            cursor = self.console_output.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.console_output.setTextCursor(cursor)
            self.console_output.ensureCursorVisible()
        except Exception:
            logger.debug("VideoConverterApp.append_log: suppressed error", exc_info=True)
        # Keep overlay styling/state in sync as logs arrive
        try:
            self.update_log_display()
        except Exception:
            logger.debug("VideoConverterApp.append_log: suppressed error", exc_info=True)

    def _wiggle_lock_icon(self):
        """Animate visible lock icons to indicate locked state when actions are blocked."""
        try:
            targets = list(getattr(self, 'footer_lock_labels', [])) or [
                getattr(self, 'lock_icon_label_log_tab', None),
                getattr(self, 'lock_icon_label_converted_tab', None),
                getattr(self, 'lock_icon_label_inspection_tab', None),
            ]
            for target in targets:
                if target is None or not target.isVisible():
                    continue
                start_pos = target.pos()
                anim = QPropertyAnimation(target, b"pos", self)
                anim.setDuration(350)
                anim.setEasingCurve(QEasingCurve.InOutQuad)
                anim.setKeyValueAt(0.0, start_pos)
                anim.setKeyValueAt(0.25, start_pos + QPoint(-4, 0))
                anim.setKeyValueAt(0.5, start_pos + QPoint(4, 0))
                anim.setKeyValueAt(0.75, start_pos + QPoint(-4, 0))
                anim.setKeyValueAt(1.0, start_pos)
                anim.start(QPropertyAnimation.DeleteWhenStopped)
        except Exception:
            logger.debug("VideoConverterApp._wiggle_lock_icon: suppressed error", exc_info=True)

    def _wiggle_converted_tab(self):
        """Animate the 'Converted Files' tab text to indicate a file has been converted."""
        try:
            # Find the index of the Converted Files tab
            converted_tab_index = -1
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Converted Files":
                    converted_tab_index = i
                    break

            if converted_tab_index == -1:
                return

            # Get the tab bar and tab button
            tab_bar = self.tabs.tabBar()
            if tab_bar is None:
                return

            # Use a custom property animation on tab bar's style
            # Since we can't directly animate tab text, we'll use a timer-based approach
            original_text = "Converted Files"
            wiggle_chars = ["C", "o", "n", "v", "e", "r", "t", "e", "d", " ", "F", "i", "l", "e", "s"]
            wiggle_count = [0]  # Use list to allow modification in nested function

            def do_wiggle():
                if wiggle_count[0] >= 6:  # 3 full cycles (left-right-left-right-left-right)
                    self.tabs.setTabText(converted_tab_index, original_text)
                    return

                # Alternate between adding spaces at beginning and end for wiggle effect
                if wiggle_count[0] % 2 == 0:
                    self.tabs.setTabText(converted_tab_index, " " + original_text)
                else:
                    self.tabs.setTabText(converted_tab_index, original_text + " ")

                wiggle_count[0] += 1
                QTimer.singleShot(80, do_wiggle)  # Fast wiggle every 80ms

            do_wiggle()
        except Exception:
            logger.debug("VideoConverterApp._wiggle_converted_tab: suppressed error", exc_info=True)

    def _show_locked_dialog(self):
        """Consistent locked dialog with grayscale styling and wiggle before/after."""
        try:
            self._wiggle_lock_icon()
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Information)
            dlg.setWindowTitle("Locked")
            dlg.setText("The application is locked. Unlock to change settings.")
            info_icon_path = resource_path('graphics/GRAYSCALEINFO.ico')
            if os.path.exists(info_icon_path):
                dlg.setWindowIcon(QIcon(info_icon_path))
                dlg.setIconPixmap(QPixmap(info_icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            elif os.path.exists(getattr(self, 'icon_gray', '')):
                dlg.setWindowIcon(QIcon(self.icon_gray))
            dlg.setStyleSheet("""
                QMessageBox { background: #f2f2f2; }
                QLabel { color: #666; }
                QPushButton {
                    background: #e0e0e0;
                    border: 1px solid #c0c0c0;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: #555;
                }
                QPushButton:hover { background: #d5d5d5; }
            """)
            dlg.exec_()
            self._wiggle_lock_icon()
        except Exception:
            logger.debug("VideoConverterApp._show_locked_dialog: suppressed error", exc_info=True)

    # Remove update_conversion_status and update_percentage methods

    def toggle_process(self):
        logger.info(
            "toggle_process entered locked=%s recorder_tab=%s running=%s is_converting=%s recorder_recording=%s",
            self.locked,
            self.is_recorder_tab_active(),
            self.running,
            getattr(self, 'is_converting', False),
            self.is_recorder_recording(),
        )
        if self.locked:
            logger.info("Conversion is locked. Cannot start/stop.")
            self._show_locked_dialog()
            return
        if self.is_recorder_tab_active() and not self.running and not getattr(self, 'is_converting', False):
            logger.info("toggle_process branch=recorder")
            recorder = self.multi_source_recorder_widget
            if self.is_recorder_recording():
                logger.info("toggle_process recorder action=stop")
                recorder.stop_recording()
            else:
                logger.info("toggle_process recorder action=start")
                recorder.start_recording()
            self.update_single_workflow_availability()
            return
        if self.running:
            logger.info("toggle_process branch=stop_conversion")
            self.stop_conversion()
            self.set_start_button_state(is_running=False)
        else:
            logger.info("toggle_process branch=start_conversion")
            self.start_conversion()
            self.set_start_button_state(is_running=True)
        # Sync compact start button after toggling
        if hasattr(self, 'compact_start_button'):
            self.update_compact_start_button()

    def start_conversion(self):
        if self.is_recorder_recording():
            self.append_log("Cannot start conversion while recording is active.", is_error=True)
            return
        if not (os.path.exists(self.source_folder) and os.path.exists(self.destination_folder)):
            logger.info("Source or Destination folder is missing.")
            self.append_log("Source or Destination folder is missing.", is_error=True)
            QMessageBox.critical(self, "Missing Folders", "Please select valid Source and Destination folders.")
            return
        self.running = True
        self.status_running = True
        self.update_single_workflow_availability()
        self.update_status_labels()
        logger.info("Conversion started.")
        self.append_log("Conversion started.")
        self.append_log(f"Monitoring folder: {self.source_folder}")
        self.watchdog_handler = FolderWatchdogHandler(self)
        try:
            self.folder_observer = Observer()
            self.folder_observer.schedule(self.watchdog_handler, self.source_folder, recursive=False)
            self.folder_observer.start()
        except Exception as e:
            logger.error(f"Native Observer failed: {e}. Falling back to PollingObserver.")
            self.append_log(f"Native Observer failed: {e}. Falling back to PollingObserver.", is_error=True)
            from watchdog.observers.polling import PollingObserver
            self.folder_observer = PollingObserver()
            self.folder_observer.schedule(self.watchdog_handler, self.source_folder, recursive=False)
            self.folder_observer.start()
        self.scan_existing_files()
        self._process_manual_queue()
        self.update_icons()  # Ensure logo switches to color
        self.update_highlight_colors()
        # Also update compact logo
        if hasattr(self, 'compact_logo'):
            self.update_compact_logo()

    def stop_conversion(self):
        self.running = False
        if self.folder_observer:
            self.folder_observer.stop()
            self.folder_observer.join()
            self.folder_observer = None
        self.status_running = False
        self.update_single_workflow_availability()
        self.update_status_labels()
        logger.info("Conversion stopped.")
        self.append_log("Conversion stopped.")
        self.update_icons()  # Ensure logo switches to greyscale
        self.update_highlight_colors()
        # Also update compact logo
        if hasattr(self, 'compact_logo'):
            self.update_compact_logo()

    def scan_existing_files(self):
        for filename in os.listdir(self.source_folder):
            file_path = os.path.join(self.source_folder, filename)
            ext = os.path.splitext(file_path)[1].lower()
            if os.path.isfile(file_path) and ext in SUPPORTED_FORMATS:
                # Add to queue as 'queued' before starting conversion
                self.converted_files_widget.add_queued_file(os.path.basename(file_path), self.destination_folder)
                self.convert_file(file_path)

    def get_icon_path(self, icon_name):
        if self.locked:
            # When locked, always use grayscale version
            path = resource_path(f'graphics/GRAYSCALE{icon_name}.ico')
            logger.info(f"Locked state - {icon_name} icon path: {path}")
            return path
        elif self.is_active_workflow_visual_state():
            # When monitoring/converting, use green version
            path = resource_path(f'graphics/GREEN{icon_name}.ico')
            logger.info(f"Monitoring state - {icon_name} icon path: {path}")
            return path
        else:
            # Default state - try teal version first
            teal_path = resource_path(f'graphics/{icon_name}.ico')
            if os.path.exists(teal_path):
                logger.info(f"Default state - {icon_name} icon path: {teal_path}")
                return teal_path
            # Special handling for BURGER icon in default state
            if icon_name == 'BURGER':
                # Since there's no teal BURGER.ico, use INFO.ico as fallback (teal color)
                path = resource_path('graphics/INFO.ico')
                logger.info(f"Default state - BURGER fallback icon path: {path}")
                return path
            logger.info(f"Default state - {icon_name} icon path: {teal_path}")
            return teal_path

    # ────────────────────────────────────────────────────────────────
    # BallBuster XT helper (intro + delayed launch)
    # ────────────────────────────────────────────────────────────────
    def _play_ballbuster_intro(self):
        """Display ASCII art title and launch the game after 3-second pause."""
        # Ensure log tab is visible so user can read the banner
        try:
            if hasattr(self, 'tabs'):
                self.tabs.setCurrentIndex(0)  # Conversion Log tab
                # Mimic drag-drop behaviour: hide instruction text
                if hasattr(self, 'drag_drop_text'):
                    self.drag_drop_text.hide()
                if hasattr(self, 'drag_drop_overlay'):
                    # Light translucent background
                    self.drag_drop_overlay.setStyleSheet("""
                        QWidget {
                            background: rgba(255, 255, 255, 0.5);
                            border: 2px dashed #dee2e6;
                            border-radius: 8px;
                            margin: 10px;
                        }
                    """)
                    self.drag_drop_overlay.show()
        except Exception:
            logger.debug("VideoConverterApp._play_ballbuster_intro: suppressed error", exc_info=True)
        from utils.resources import resource_path
        binary_path = resource_path('graphics/balls/BallbusterXT.txt')
        try:
            import time
            from PyQt5.QtCore import QCoreApplication, QTimer
            from PyQt5.QtGui import QFont
            with open(binary_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.rstrip('\n') for idx, line in enumerate(f) if idx < 1000]
            # Temporarily switch console font to small monospace for ASCII art
            prev_font = self.console_output.font()
            self.console_output.setFont(QFont('Courier New', 7))
            try:
                for _ in range(3):
                    for idx, line in enumerate(lines):
                        self.console_output.appendHtml(f"<pre style='margin:0;font-family:\"Courier New\";font-size:7pt'>>{line}</pre>")
                        if idx % 20 == 0:
                            QCoreApplication.processEvents()
                        time.sleep(0.01)
            finally:
                self.console_output.setFont(prev_font)
        except FileNotFoundError:
            self.append_log(f"[INFO] Binary file {binary_path} not found. Proceeding anyway.")
        # Read high score and best level from system state
        try:
            from utils.system_state import get_high_scores, get_best_level
            hs = get_high_scores()
            high = max([s for (_, s, __) in hs]) if hs else 0
            best_level = get_best_level()
        except Exception:
            high = 0
            best_level = 0
        self.append_log('Starting BallBuster XT!')
        self.append_log(f'HIGH SCORE: {high}')
        # Append rank welcome line in the conversion log
        try:
            if best_level <= 2:
                rank = 'Trainee'
            elif best_level <= 4:
                rank = 'Trainer'
            elif best_level <= 6:
                rank = 'Administrator'
            elif best_level <= 9:
                rank = 'Ballbuster'
            else:
                rank = 'Master Ballbuster'
            self.append_log(f'Welcome back {rank}')
        except Exception:
            logger.debug("VideoConverterApp._play_ballbuster_intro: suppressed error", exc_info=True)
        from PyQt5.QtCore import QTimer, QCoreApplication
        QCoreApplication.processEvents()
        QTimer.singleShot(3000, self.launch_ballbuster_game)

    def get_game_icon_path(self):
        """Return the appropriate controller-circle icon based on current app state."""
        from utils.resources import resource_path
        if self.locked:
            return resource_path('graphics/grayscalegame.ico')
        elif self.is_active_workflow_visual_state():
            return resource_path('graphics/greengame.ico')
        else:
            return resource_path('graphics/game.ico')

    def add_game_icons(self):
        """Insert the BallBuster XT launcher icon into each footer to the left of the status label."""
        footer_layouts = [footer for footer in getattr(self, 'footer_layouts', []) if footer is not None]
        if getattr(self, '_game_icons_added', False) and len(getattr(self, 'game_icon_labels', [])) >= len(footer_layouts):
            return  # Already added
        if not hasattr(self, 'game_icon_labels'):
            self.game_icon_labels = []
        if not hasattr(self, 'game_icon_footer_ids'):
            self.game_icon_footer_ids = set()
        icon_path = self.get_game_icon_path()
        from PyQt5.QtWidgets import QLabel
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        for footer in footer_layouts:
            footer_id = id(footer)
            if footer_id in self.game_icon_footer_ids:
                continue
            label = QLabel()
            if os.path.exists(icon_path):
                label.setPixmap(QPixmap(icon_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            label.setFixedSize(36, 36)
            label.setAlignment(Qt.AlignCenter)
            label.setCursor(Qt.PointingHandCursor)
            label.setToolTip('Play BallBuster XT')
            # Match visual style of other circular footer icons
            label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    border: none;
                    padding: 4px;
                }
                QLabel:hover {
                    background: #e9ecef;
                    border-radius: 18px;
                }
            """)
            label.mousePressEvent = lambda event, self=self: self._play_ballbuster_intro()
            # Insert right before the status label (last widget in footer)
            footer.insertWidget(footer.count() - 1, label)
            self.game_icon_labels.append(label)
            self.game_icon_footer_ids.add(footer_id)
        self._game_icons_added = len(self.game_icon_footer_ids) >= len(footer_layouts)

    def update_game_icons(self):
        """Refresh icon pixmaps when state changes (locked/running)."""
        if not getattr(self, 'game_icon_labels', None):
            return
        icon_path = self.get_game_icon_path()
        if not os.path.exists(icon_path):
            return
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        for label in self.game_icon_labels:
            label.setPixmap(QPixmap(icon_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def get_logo_path(self):
        # During BallBuster game, swap to BallBuster logos
        in_game = hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None
        if in_game:
            if self.locked:
                return resource_path('graphics/GRAYSCALEBALLBUSTER.png')
            elif self.is_active_workflow_visual_state():
                return resource_path('graphics/BALLBUSTER.png')
            else:
                return resource_path('graphics/TEALBALLBUSTER.png')
        # Normal NVC logos
        if self.locked:
            return resource_path('graphics/GRAYSCALENVCLOGO.ico')
        elif self.is_active_workflow_visual_state():
            return resource_path('graphics/NVCLOGO.ico')
        else:
            return resource_path('graphics/TEALNVCLOGO.ico')

    def update_icons(self):
        # Logo - scale consistently to logo_size to handle varying asset dimensions
        logo_path = self.get_logo_path()
        if hasattr(self, 'logo_label') and os.path.exists(logo_path):
            size = getattr(self, 'logo_size', 154)
            self.logo_label.setPixmap(QPixmap(logo_path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # Burger
        burger_icon_path = self.get_icon_path('BURGER')
        if hasattr(self, 'burger_button') and os.path.exists(burger_icon_path):
            burger_icon = QIcon(QPixmap(burger_icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.burger_button.setIcon(burger_icon)
            # Also update compact burger icon
            if hasattr(self, 'compact_burger'):
                self.compact_burger.setIcon(burger_icon)
        elif hasattr(self, 'burger_button'):
            # Debug: log when burger icon path doesn't exist
            logger.info(f"Burger icon path not found: {burger_icon_path}")
            # Fallback to grayscale burger if path doesn't exist
            fallback_path = resource_path('graphics/GRAYSCALEBURGER.ico')
            if os.path.exists(fallback_path):
                fallback_icon = QIcon(QPixmap(fallback_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.burger_button.setIcon(fallback_icon)
                # Also update compact burger icon
                if hasattr(self, 'compact_burger'):
                    self.compact_burger.setIcon(fallback_icon)
        # Broom (log tab)
        broom_icon_path = self.get_icon_path('BROOM')
        if os.path.exists(broom_icon_path):
            broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            for broom_label in getattr(self, 'footer_broom_labels', []):
                broom_label.setPixmap(broom_pixmap)
        if hasattr(self, 'broom_label_log_tab') and os.path.exists(broom_icon_path):
            self.broom_label_log_tab.setPixmap(QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        # Broom (converted tab)
        if hasattr(self, 'broom_label_converted_tab') and os.path.exists(broom_icon_path):
            self.broom_label_converted_tab.setPixmap(QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        # Broom (inspection tab)
        if hasattr(self, 'broom_label_inspection_tab') and os.path.exists(broom_icon_path):
            self.broom_label_inspection_tab.setPixmap(QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        # Lock/Unlock (log tab)
        for lock_label in getattr(self, 'footer_lock_labels', []):
            lock_label.setPixmap(self.get_lock_icon_pixmap())
        if hasattr(self, 'lock_icon_label_log_tab'):
            self.lock_icon_label_log_tab.setPixmap(self.get_lock_icon_pixmap())
        # Lock/Unlock (converted tab)
        if hasattr(self, 'lock_icon_label_converted_tab'):
            self.lock_icon_label_converted_tab.setPixmap(self.get_lock_icon_pixmap())
        # Lock/Unlock (inspection tab)
        if hasattr(self, 'lock_icon_label_inspection_tab'):
            self.lock_icon_label_inspection_tab.setPixmap(self.get_lock_icon_pixmap())
        # Update game controller icons
        self.update_game_icons()
        # Compact mode icons
        if hasattr(self, 'compact_broom') and os.path.exists(broom_icon_path):
            self.compact_broom.setPixmap(QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, 'compact_lock'):
            self.compact_lock.setPixmap(self.get_lock_icon_pixmap())
        if hasattr(self, 'compact_file'):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                self.compact_file.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        # File icon (normal mode footers)
        for file_label in getattr(self, 'footer_file_labels', []):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                file_label.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, 'file_label_log_tab'):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                self.file_label_log_tab.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, 'file_label_converted_tab'):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                self.file_label_converted_tab.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, 'file_label_inspection_tab'):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                self.file_label_inspection_tab.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        # Menu actions (Info, Help, Settings, etc.) - all follow the same color scheme
        if hasattr(self, 'burger_button') and self.burger_button.menu():
            menu = self.burger_button.menu()
            for action in menu.actions():
                if action.text() == "Info":
                    icon_path = self.get_icon_path('INFO')
                    logger.info(f"Setting Info icon to: {icon_path}")
                    if os.path.exists(icon_path):
                        action.setIcon(QIcon(QPixmap(icon_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                        logger.info(f"Info icon set successfully")
                    else:
                        logger.warning(f"Info icon path does not exist: {icon_path}")
                elif action.text() == "Help":
                    icon_path = self.get_icon_path('HELP')
                    logger.info(f"Setting Help icon to: {icon_path}")
                    if os.path.exists(icon_path):
                        action.setIcon(QIcon(QPixmap(icon_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                        logger.info(f"Help icon set successfully")
                    else:
                        logger.warning(f"Help icon path does not exist: {icon_path}")
                elif action.text() == "Settings":
                    icon_path = self.get_icon_path('GEAR')
                    logger.info(f"Setting Settings icon to: {icon_path}")
                    if os.path.exists(icon_path):
                        action.setIcon(QIcon(QPixmap(icon_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                        logger.info(f"Settings icon set successfully")
                    else:
                        logger.warning(f"Settings icon path does not exist: {icon_path}")
                elif action.text() in ["Open Source Folder", "Open Destination Folder", "Open Backup Folder"]:
                    # Don't assign any icon to folder open actions
                    action.setIcon(QIcon())

            # Force menu to refresh
            menu.update()
            # Force burger button to refresh
            self.burger_button.update()

        # Update preview placeholder text color if no video is loaded
        if hasattr(self, 'preview_source_path') and hasattr(self, 'preview_label'):
            if not self.preview_source_path:
                current_text = self.preview_label.text()
                if current_text:  # Only update if there's text (not an image)
                    self._set_preview_placeholder(current_text)

    def preview_file(self, file_path):
        """Show video preview in the sidebar."""
        if not os.path.exists(file_path):
            return

        self.preview_source_path = os.path.abspath(file_path)
        self.preview_seek_seconds = 0.0
        self.preview_frame_index = 0
        self.preview_playing = False
        self.preview_duration_sec = self._probe_duration_seconds(self.preview_source_path)
        self.preview_scrubber.setValue(0)
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._stop_preview_process()
        # Stop star field if it's running
        try:
            self._stop_star_field()
        except Exception:
            logger.debug("VideoConverterApp.preview_file: suppressed error", exc_info=True)
        self._set_preview_placeholder(text="Loading preview…")
        self._generate_and_show_thumbnail(self.preview_source_path)
        # Ensure overlay is on top and can receive hover events
        self.overlay_container.raise_()
        # Hide play button and scrubber initially - they'll show on hover
        self.play_pause_btn.hide()
        self.preview_scrubber.hide()
        logger.info(f"Preview loaded for {file_path}")

    def _handle_converted_tab_drop(self, file_paths):
        """Handle files dropped onto the Converted Files tab."""
        if not file_paths:
            return
        valid_paths = collect_supported_media_paths(file_paths, SUPPORTED_FORMATS)
        if not valid_paths:
            return
        for path in valid_paths:
            # Always show in the queue
            self.converted_files_widget.add_queued_file(os.path.basename(path), self.destination_folder)
            if self.running and not self.locked:
                # Monitoring mode (unlocked): convert immediately
                self.convert_file(path)
            else:
                # Idle or locked: queue for later when Start is pressed (after unlock)
                if path not in self.manual_queue:
                    self.manual_queue.append(path)
        # Gentle reminder only when not auto-converting
        if not self.running or self.locked:
            try:
                self.append_log("Files queued. Start conversion after unlocking/starting.")
            except Exception:
                logger.debug("VideoConverterApp._handle_converted_tab_drop: suppressed error", exc_info=True)

    def _confirm_dropped_conversion(self, count, show_dialog):
        if not show_dialog:
            return True
        label = "media file" if count == 1 else f"{count} media files"
        reply = QMessageBox.question(
            self,
            "Convert Media Files",
            f"Do you wish to convert {label} according to settings?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            return False
        if not self.settings.get('dont_show_drop_dialog', False):
            dont_show_reply = QMessageBox.question(
                self,
                "Don't Show Again",
                "Don't show me this dialog again?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if dont_show_reply == QMessageBox.Yes:
                self.settings['show_drop_confirmation'] = False
                save_settings(self.settings)
        return True

    def _convert_dropped_paths(self, dropped_paths, show_dialog):
        valid_paths = collect_supported_media_paths(dropped_paths, SUPPORTED_FORMATS)
        if not valid_paths:
            unsupported_list = "\n".join(dropped_paths)
            QMessageBox.warning(self, "Unsupported Files", f"No supported video files found in:\n{unsupported_list}")
            logger.info(f"No supported files found in dropped paths:\n{unsupported_list}")
            return

        if not self._confirm_dropped_conversion(len(valid_paths), show_dialog):
            return

        self.preview_file(valid_paths[0])
        for file_path in valid_paths:
            self.converted_files_widget.add_queued_file(os.path.basename(file_path), self.destination_folder)
            if self.locked:
                if file_path not in self.manual_queue:
                    self.manual_queue.append(file_path)
            else:
                self.convert_file(file_path, force=True)
        if self.locked:
            self.append_log("Files queued while locked. Unlock and start conversion to process them.")

    def convert_file(self, file_path, force=False):
        """Start the conversion process for a single file."""
        file_path = os.path.abspath(file_path)
        if self.locked and not force:
            self._wiggle_lock_icon()
            logger.info("Conversion attempt blocked while locked.")
            return
        if file_path in self.in_flight_conversions:
            logger.info(f"Skipping duplicate conversion request for {file_path}.")
            self.append_log(f"Skipping duplicate conversion request for {file_path}.")
            return
        # Load Preview (Always, for better UX) - thumbnail first, optional play on click
        try:
            self.preview_file(file_path)
        except Exception as e:
            logger.error(f"Preview error: {e}")

        # Easter egg: Launch BallBuster game when special filename detected
        if 'noldus123' in os.path.basename(file_path).lower():
            # Mark Easter egg as unlocked via system state
            if not get_game_unlocked():
                set_game_unlocked(True)
                self.add_game_icons()  # Insert game icons immediately
            self._play_ballbuster_intro()
            return
        if not self.running and not force:
            logger.info(f"Received file {file_path} but conversion is not running. Ignoring.")
            self.append_log(f"Received file {file_path} but conversion is not running. Ignoring.")
            return
        if not is_within_allowed_time(self.settings):
            logger.info(f"Current time outside allowed range. Skipping {file_path}.")
            self.append_log(f"Current time outside allowed range. Skipping {file_path}.")
            return
        self.in_flight_conversions.add(file_path)
        # Update status to 'processing' in the queue
        self.converted_files_widget.update_file_status(os.path.basename(file_path), 'processing')
        self.active_conversion_count += 1  # Track active conversions
        self.is_converting = self.active_conversion_count > 0
        self.update_single_workflow_availability()
        # Ensure start/stop button switches to green while conversion is active
        self.set_start_button_state(is_running=True)
        self.update_icons()
        self.update_status_labels()  # Update status when conversion starts
        self.update_log_display()  # Update log display to show console during conversion
        worker_signals = WorkerSignals()
        # Buffer for per-file log
        self.per_file_logs[file_path] = []
        def per_file_log_handler(msg):
            # Route through LogBus to keep UI responsive and resilient across tab switches
            try:
                self.log_bus.append(msg)
            except Exception:
                self.append_log(msg)
            self.per_file_logs[file_path].append(msg)
        worker_signals.log.connect(per_file_log_handler)
        worker_signals.conversion_complete.connect(self.handle_conversion_complete)
        from conversion.worker import ConversionWorker
        worker = ConversionWorker(file_path, self.settings, worker_signals)
        self.conversion_workers[file_path] = worker
        self.threadpool.start(worker)

    def _process_manual_queue(self):
        """Convert any files queued while idle once monitoring starts."""
        if not getattr(self, 'manual_queue', None):
            return
        pending = list(dict.fromkeys(self.manual_queue))  # dedupe, preserve order
        self.manual_queue.clear()
        for path in pending:
            try:
                ext = os.path.splitext(path)[1].lower()
                if not (os.path.isfile(path) and ext in SUPPORTED_FORMATS):
                    continue
                # Ensure they are visible in the queue, then convert now that we're running
                self.converted_files_widget.add_queued_file(os.path.basename(path), self.destination_folder)
                self.convert_file(path)
            except Exception:
                continue

    def handle_conversion_complete(self, file_name, success, deletion_info):
        # Keep preview visible after conversion; don't auto-stop it.
        # If preview is playing, leave it playing; otherwise keep thumbnail.
        # (Play button will show on hover)

        output_format = self.settings.get('output_format', 'mp4')
        name, _ = os.path.splitext(file_name)
        output_file = (deletion_info or {}).get('output_file', '')
        output_file_name = os.path.basename(output_file) if output_file else f"{name}.{output_format}"
        source_file = os.path.abspath((deletion_info or {}).get('source_file', '')) if deletion_info else ''
        if source_file:
            self.in_flight_conversions.discard(source_file)
            self.conversion_workers.pop(source_file, None)
        # Update status to 'success' or 'failure' in the queue
        self.converted_files_widget.update_file_status(output_file_name, 'success' if success else 'failure')
        self.converted_files_widget.file_converted_signal.emit(output_file_name, deletion_info, self.destination_folder, success)
        # Write per-file log if available
        for src_path in list(self.per_file_logs.keys()):
            if os.path.basename(src_path) == file_name:
                try:
                    from utils.paths import get_data_dir
                    default_logs = get_data_dir("logs")
                except Exception:
                    default_logs = os.path.expanduser("~")
                log_folder = getattr(self.converted_files_widget, 'log_folder', default_logs)
                if not os.path.exists(log_folder):
                    os.makedirs(log_folder, exist_ok=True)
                log_path = os.path.join(log_folder, output_file_name + '.txt')
                with open(log_path, 'w', encoding='utf-8') as f:
                    for line in self.per_file_logs[src_path]:
                        f.write(line + '\n')
                del self.per_file_logs[src_path]
        if success:
            self.append_log("Conversion complete!", is_error=False)
            # Wiggle the Converted Files tab to draw attention
            self._wiggle_converted_tab()
        else:
            self.append_log("Conversion failed!", is_error=True)
        self.active_conversion_count = max(0, self.active_conversion_count - 1)  # Decrement, never below 0
        self.is_converting = self.active_conversion_count > 0
        self.update_single_workflow_availability()
        # If monitoring is not running and all conversions have finished, restore button style
        if not self.running and not self.is_converting:
            self.set_start_button_state(is_running=False)
        self.update_icons()  # Update logo after conversion
        self.update_status_labels()  # Update status when conversion finishes
        self.update_log_display()  # Update log display after conversion completes

    def show_info(self):
        dialog = InfoDialog(self, is_converting=self.running, button_style=getattr(self, 'current_button_style', None))
        self.center_dialog(dialog)
        dialog.exec_()

    def open_help_document(self):
        # Prefers the generated manual from docs/help (see
        # utils/help_resolution.py) and falls back to the legacy hand-written
        # help_document.pdf/.html when no generated one has been shipped.
        from utils.help_resolution import resolve_help_document
        help_path = resolve_help_document()
        if help_path is not None:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            logger.info(f"Opening help document {help_path.name}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(help_path)))
        else:
            logger.warning("No help document found in docs/help or alongside the app.")
            QMessageBox.warning(
                self, "Help Document Not Found",
                "The help document could not be found.\n\n"
                "Build it with:\n"
                "  python docs/help/source/build_help_docs.py")

    def open_source_folder_in_explorer(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        if not self.source_folder or not os.path.exists(self.source_folder):
            QMessageBox.warning(self, "Folder Not Found", "Source folder path does not exist.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.source_folder))

    def open_destination_folder_in_explorer(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        if not self.destination_folder or not os.path.exists(self.destination_folder):
            QMessageBox.warning(self, "Folder Not Found", "Destination folder path does not exist.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.destination_folder))

    def open_backup_folder_in_explorer(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        if not self.backup_folder or not os.path.exists(self.backup_folder):
            QMessageBox.warning(self, "Folder Not Found", "Backup folder path does not exist.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.backup_folder))

    def show_settings(self, tab_index=None):
        if self.locked:
            logger.info("Settings are locked.")
            self._show_locked_dialog()
            return
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.settings, self, button_style=getattr(self, 'current_button_style', None))
        self.center_dialog(dialog)
        dialog.settings_saved.connect(self.update_settings)
        dialog.backup_usage_changed.connect(self.update_backup_button_state)
        # Set the tab if specified
        if tab_index is not None:
            dialog.tabs.setCurrentIndex(tab_index)
        dialog.exec_()

    def settings_display_clicked(self, event):
        """Handle click on the settings display label to open Format tab."""
        # Only open settings if not in game mode
        if not (hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None):
            self.show_settings(tab_index=3)  # 3 is the Format tab index

    def settings_display_enter(self, event):
        """Add underline to header text on hover."""
        if not (hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None):
            # Add underline to "Current Video Settings:"
            current_text = self.settings_display.text()
            underlined_text = current_text.replace(
                '<b>Current Video Settings:</b>',
                '<b><u>Current Video Settings:</u></b>'
            )
            self.settings_display.setText(underlined_text)

    def settings_display_leave(self, event):
        """Remove underline from header text when not hovering."""
        if not (hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None):
            # Remove underline from "Current Video Settings:"
            current_text = self.settings_display.text()
            ununderlined_text = current_text.replace(
                '<b><u>Current Video Settings:</u></b>',
                '<b>Current Video Settings:</b>'
            )
            self.settings_display.setText(ununderlined_text)

    def update_settings(self, new_settings):
        self.settings.update(new_settings)
        save_settings(self.settings)
        self.source_folder = os.path.abspath(self.settings.get('source_folder', ''))
        self.destination_folder = os.path.abspath(self.settings.get('destination_folder', ''))
        self.backup_folder = os.path.abspath(self.settings.get('backup_folder', ''))
        self.locked = self.settings.get('locked', False)
        # Re-apply window flags if "close_on_x" changed
        self.apply_window_flags_based_on_settings()
        logger.info("Settings updated.")
        self.apply_tool_tab_visibility()
        self.update_lock_state_ui()
        self.update_settings_display()

    def apply_window_flags_based_on_settings(self):
        """Show minimize button next to X when close-on-X is enabled; otherwise keep current behavior."""
        try:
            close_on_x_enabled = bool(self.settings.get('close_on_x', False))
        except Exception:
            close_on_x_enabled = False

        # Preserve current window state and geometry to avoid unintended minimize/hide
        prev_state = self.windowState()
        prev_geom = self.geometry()
        was_visible = self.isVisible()

        base_flags = Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint
        if close_on_x_enabled:
            base_flags |= Qt.WindowMinimizeButtonHint

        self.setWindowFlags(base_flags)

        # Restore geometry and state without forcing a minimize
        try:
            self.setGeometry(prev_geom)
        except Exception:
            logger.debug("VideoConverterApp.apply_window_flags_based_on_settings: suppressed error", exc_info=True)

        # If it was visible before, keep it visible. Restore to Normal unless it was minimized/maximized.
        if was_visible:
            if prev_state & Qt.WindowMinimized:
                # Keep minimized if it already was minimized; this will still show on taskbar
                self.setWindowState(Qt.WindowMinimized)
            elif prev_state & Qt.WindowMaximized:
                self.setWindowState(Qt.WindowMaximized)
                self.show()  # Ensure visibility
            else:
                self.setWindowState(Qt.WindowNoState)
                self.showNormal()
            self.activateWindow()

    def update_backup_button_state(self, enabled):
        # Implement additional UI updates if needed.
        pass

    def center_dialog(self, dialog):
        qr = dialog.frameGeometry()
        cp = self.frameGeometry().center()
        qr.moveCenter(cp)
        dialog.move(qr.topLeft())

    def center_on_screen(self):
        """Center the main window on the active screen without changing its size."""
        try:
            screen = None
            try:
                screen = self.screen()
            except Exception:
                screen = None
            if screen is not None:
                center_point = screen.availableGeometry().center()
            else:
                from PyQt5.QtWidgets import QApplication
                center_point = QApplication.desktop().availableGeometry(self).center()
            frame_geo = self.frameGeometry()
            frame_geo.moveCenter(center_point)
            self.move(frame_geo.topLeft())
        except Exception:
            logger.debug("VideoConverterApp.center_on_screen: suppressed error", exc_info=True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.central_widget.setStyleSheet("background-color: #e0e0e0;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.central_widget.setStyleSheet("")

    def drag_drop_widget_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # Show overlay with drop styling
            self.drag_drop_overlay.setStyleSheet("""
                QWidget { 
                    background: rgba(67, 162, 150, 0.1); 
                    border: 2px solid #43a296; 
                    border-radius: 8px; 
                    margin: 10px;
                }
            """)
            self.drag_drop_overlay.show()
            # Keep instruction consistent while hovering
            self.drag_drop_text.setText("Drag and drop media files here\nor select source folder to start monitoring and converting")
        else:
            event.ignore()

    def drag_drop_widget_drag_leave(self, event):
        # Restore appropriate styling based on current state
        has_log_content = len(self.console_output.toPlainText().strip()) > 0
        if self.running or self.is_converting or has_log_content:
            self.drag_drop_overlay.setStyleSheet("""
                QWidget { 
                    background: rgba(255, 255, 255, 0.5); 
                    border: 2px dashed #dee2e6; 
                    border-radius: 8px; 
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: #43a296;
                    background: rgba(67, 162, 150, 0.1);
                }
            """)
        else:
            self.drag_drop_overlay.setStyleSheet("""
                QWidget { 
                    background: white; 
                    border: 2px dashed #dee2e6; 
                    border-radius: 8px; 
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: #43a296;
                    background: rgba(67, 162, 150, 0.1);
                }
            """)
        # Always reset to default instruction after drag leave
        self.drag_drop_text.setText("Drag and drop media files here\nor select source folder to start monitoring and converting")
        # Always show the overlay
        self.drag_drop_overlay.show()

    def drag_drop_widget_drop(self, event):
        # Restore appropriate styling based on current state
        has_log_content = len(self.console_output.toPlainText().strip()) > 0
        if self.running or self.is_converting or has_log_content:
            self.drag_drop_overlay.setStyleSheet("""
                QWidget { 
                    background: rgba(255, 255, 255, 0.5); 
                    border: 2px dashed #dee2e6; 
                    border-radius: 8px; 
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: #43a296;
                    background: rgba(67, 162, 150, 0.1);
                }
            """)
        else:
            self.drag_drop_overlay.setStyleSheet("""
                QWidget { 
                    background: white; 
                    border: 2px dashed #dee2e6; 
                    border-radius: 8px; 
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: #43a296;
                    background: rgba(67, 162, 150, 0.1);
                }
            """)
        # After drop, hide only the text, keep the overlay visible
        self.drag_drop_text.hide()
        self.drag_drop_overlay.show()
        urls = event.mimeData().urls()
        dropped_files = [url.toLocalFile() for url in urls]
        self._convert_dropped_paths(dropped_files, self.settings.get('show_drop_confirmation', False))

    def dropEvent(self, event):
        self.central_widget.setStyleSheet("")
        urls = event.mimeData().urls()
        dropped_files = [url.toLocalFile() for url in urls]
        self._convert_dropped_paths(dropped_files, self.settings.get('show_drop_confirmation', True))

    def quit_application(self):
        self.shutdown()
        self.tray_icon.hide()
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()

    def resize_image_preserve_aspect(self, pixmap, size):
        try:
            scaled_pixmap = pixmap.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
            final_pixmap = QPixmap(size[0], size[1])
            final_pixmap.fill(Qt.transparent)
            painter = QPainter(final_pixmap)
            painter.drawPixmap((size[0] - scaled_pixmap.width()) // 2,
                               (size[1] - scaled_pixmap.height()) // 2,
                               scaled_pixmap)
            painter.end()
            return final_pixmap
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return pixmap

    # Add clear log methods
    def clear_log_tab(self, event=None):
        self.console_output.clear()
        # Show the instruction text again when log is cleared
        if hasattr(self, 'drag_drop_text'):
            self.drag_drop_text.show()

        # Also clear the video preview (reset to placeholder)
        self._stop_preview_process()
        self.preview_source_path = ""
        self.preview_seek_seconds = 0.0
        self.preview_frame_index = 0
        self.preview_playing = False
        self.play_pause_btn.hide()
        self._set_preview_placeholder(text="No Preview")
    def clear_converted_tab(self, event=None):
        if hasattr(self.converted_files_widget, 'table_widget'):
            self.converted_files_widget.table_widget.setRowCount(0)
    def clear_inspection_tab(self, event=None):
        if hasattr(self.inspection_widget, 'summary_text'):
            self.inspection_widget.summary_text.clear()
            self.inspection_widget.summary_text.hide()
            self.inspection_widget.summary_drag_text.show()
        if hasattr(self.inspection_widget, 'info_display'):
            self.inspection_widget.info_display.clear()
            self.inspection_widget.info_display.hide()
            self.inspection_widget.json_drag_text.show()
        # Also clear the sidebar preview so it doesn't persist
        self._clear_preview_display()

    def clear_pc_report_tab(self, event=None):
        widget = getattr(self, 'pc_report_widget', None)
        if widget and hasattr(widget, 'output'):
            widget.output.clear()
            if hasattr(widget, 'status_label'):
                widget.status_label.setText("Ready. Reports are saved to your Desktop by default.")

    def clear_lossless_editor_tab(self, event=None):
        widget = getattr(self, 'lossless_editor_widget', None)
        if widget and hasattr(widget, 'log_output'):
            widget.log_output.clear()

    def clear_multi_source_recorder_tab(self, event=None):
        widget = getattr(self, 'multi_source_recorder_widget', None)
        if widget:
            widget.log_lines = []
            if hasattr(widget, 'status_label'):
                widget.status_label.setText("Not recording")

    def clear_media_player_tab(self, event=None):
        widget = getattr(self, 'media_player_widget', None)
        if widget:
            widget.stop_all()
            for panel in getattr(widget, 'panels', []):
                panel.clear_media()

    def show_log_context_menu_global(self, global_pos):
        """Context menu on conversion log to quick-access lock/upload/clear/copy/select-all."""
        menu = QMenu(self)
        lock_text = "Unlock" if getattr(self, 'locked', False) else "Lock"
        lock_action = menu.addAction(lock_text)
        upload_action = menu.addAction("Upload")
        clear_action = menu.addAction("Clear Log")
        menu.addSeparator()
        settings_action = menu.addAction("Settings")
        menu.addSeparator()
        copy_action = menu.addAction("Copy")
        select_all_action = menu.addAction("Select All")
        chosen = menu.exec_(global_pos)
        if chosen == lock_action:
            self.toggle_lock()
        elif chosen == upload_action:
            self.open_file_dialog()
        elif chosen == clear_action:
            self.clear_log_tab()
        elif chosen == settings_action:
            self.show_settings()
        elif chosen == copy_action:
            try:
                self.console_output.copy()
            except Exception:
                logger.debug("VideoConverterApp.show_log_context_menu_global: suppressed error", exc_info=True)
        elif chosen == select_all_action:
            try:
                self.console_output.selectAll()
            except Exception:
                logger.debug("VideoConverterApp.show_log_context_menu_global: suppressed error", exc_info=True)

    def show_inspection_context_menu_global(self, global_pos, text_widget=None):
        """Context menu on inspection tab to mirror conversion log options."""
        menu = QMenu(self)
        lock_text = "Unlock" if getattr(self, 'locked', False) else "Lock"
        lock_action = menu.addAction(lock_text)
        upload_action = menu.addAction("Upload")
        clear_action = menu.addAction("Clear Inspection")
        menu.addSeparator()
        settings_action = menu.addAction("Settings")
        menu.addSeparator()
        copy_action = menu.addAction("Copy")
        select_all_action = menu.addAction("Select All")
        chosen = menu.exec_(global_pos)
        if chosen == lock_action:
            self.toggle_lock()
        elif chosen == upload_action:
            self.open_inspection_file_dialog()
        elif chosen == clear_action:
            self.clear_inspection_tab()
        elif chosen == settings_action:
            self.show_settings()
        elif chosen == copy_action and text_widget:
            try:
                text_widget.copy()
            except Exception:
                logger.debug("VideoConverterApp.show_inspection_context_menu_global: suppressed error", exc_info=True)
        elif chosen == select_all_action and text_widget:
            try:
                text_widget.selectAll()
            except Exception:
                logger.debug("VideoConverterApp.show_inspection_context_menu_global: suppressed error", exc_info=True)

    def set_menu_icons(self):
        # Update burger icon for locked/unlocked state if desired (optional)
        pass

    def check_for_updates(self):
        """Mock update checker - in a real app this would query a server."""
        try:
            # Simulate a check
            # For demo purposes, let's say 2.3.0 is available if we are on 2.2.0
            # Ideally perform a GET request to a version.txt URL

            # import requests
            # resp = requests.get("https://example.com/nvc/version.txt", timeout=3)
            # latest_version = resp.text.strip()

            # Mock result
            latest_version = "2.3.0"
            current = APP_VERSION

            if latest_version > current:
                reply = QMessageBox.question(
                    self,
                    "Update Available",
                    f"A new version ({latest_version}) is available.\n\nDo you want to visit the download page?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    from PyQt5.QtGui import QDesktopServices
                    from PyQt5.QtCore import QUrl
                    QDesktopServices.openUrl(QUrl("https://example.com/nvc/downloads")) # Replace with actual URL
            else:
                QMessageBox.information(self, "No Updates", "You are running the latest version.")

        except Exception as e:
            logger.error(f"Update check failed: {e}")
            QMessageBox.warning(self, "Update Check Failed", "Could not check for updates.")

    def update_all_button_styles(self):
        """Update all button styles based on monitoring state and lock state"""
        if self.locked:
            # Grayscale gradient for locked mode
            self.current_button_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8a8a8a, stop:1 #7f7f7f);
                    color: #ffffff;
                    border: 1px solid #6a6a6a;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9a9a9a, stop:1 #8a8a8a);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7f7f7f, stop:1 #6a6a6a);
                }
            """
        elif self.is_active_workflow_visual_state():
            # Green gradient for monitoring mode
            self.current_button_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #92cb4f, stop:1 #33a16d);
                    border: 1px solid #2d7d6f;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    color: white;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9dd55a, stop:1 #92cb4f);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33a16d, stop:1 #2d7d6f);
                }
            """
        else:
            # Teal gradient for non-monitoring mode
            self.current_button_style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #43a296, stop:1 #3a9284);
                    border: 1px solid #2d7d6f;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    color: white;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4bb3a7, stop:1 #43a296);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a9284, stop:1 #2d7d6f);
                }
            """

        # Apply the style to all QPushButton widgets in the application
        self.apply_button_style_to_all_widgets(self)
        if hasattr(self, 'pc_report_widget'):
            self.pc_report_widget.update_button_style(
                self.current_button_style,
                converting=bool(self.running or getattr(self, 'is_converting', False)),
                locked=bool(getattr(self, 'locked', False))
            )

    def apply_button_style_to_all_widgets(self, widget):
        """Recursively apply button style to all QPushButton widgets"""
        if hasattr(widget, 'children'):
            for child in widget.children():
                if isinstance(child, QPushButton):
                    # Don't override the start button's specific styling and also skip buttons marked to skip global style
                    if child != self.start_button and child != getattr(self, 'compact_start_button', None) and not child.property('skipGlobalStyle'):
                        child.setStyleSheet(self.current_button_style)
                # Recursively apply to child widgets
                self.apply_button_style_to_all_widgets(child)

    def eventFilter(self, obj, event):
        """Event filter to handle mouse events on the drag drop overlay and video preview."""
        overlay = getattr(self, 'drag_drop_overlay', None)
        if overlay is not None and obj == overlay:
            if event.type() == QEvent.Enter:
                # Mouse entered the overlay - show hover effect (keep dashed border)
                self.drag_drop_overlay.setStyleSheet("""
                    QWidget { 
                        background: rgba(67, 162, 150, 0.1); 
                        border: 2px dashed #43a296; 
                        border-radius: 8px; 
                        margin: 10px;
                    }
                """)
                return False  # Let the event continue
            elif event.type() == QEvent.Leave:
                # Mouse left the overlay - restore normal styling
                self.update_log_display()  # This will restore appropriate styling
                return False  # Let the event continue
            elif event.type() == QEvent.Wheel:
                # Forward wheel events to console_output so scrolling works when overlay is on top
                from PyQt5.QtWidgets import QApplication
                QApplication.sendEvent(self.console_output, event)
                return True  # Event handled after forwarding
            elif event.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseMove]:
                return False
        elif obj in tuple(x for x in (getattr(self, 'log_tab_scroll', None), getattr(self, 'log_container', None)) if x):
            if event.type() == QEvent.Wheel:
                from PyQt5.QtWidgets import QApplication
                QApplication.sendEvent(self.console_output, event)
                return True

        elif obj in (self.preview_container, getattr(self, 'preview_label', None), getattr(self, 'overlay_container', None)):
            if event.type() in (QEvent.Enter, QEvent.HoverEnter):
                # Show play/pause button if we have media
                if bool(getattr(self, 'preview_source_path', "")):
                    self.play_pause_btn.show()
                    self.overlay_container.raise_()  # Ensure overlay is on top
                    # Show scrubber only if duration is known
                    if getattr(self, 'preview_duration_sec', 0.0) > 0:
                        self.preview_scrubber.show()
            elif event.type() in (QEvent.Leave, QEvent.HoverLeave):
                self.play_pause_btn.hide()
                if hasattr(self, 'preview_scrubber'):
                    self.preview_scrubber.hide()
            elif event.type() == QEvent.MouseButtonPress:
                 if bool(getattr(self, 'preview_source_path', "")):
                     self.toggle_preview_playback()
                 return True

        return super().eventFilter(obj, event)

    def toggle_preview_playback(self):
        """Toggle play/pause state of the preview player (ffmpeg-decoded frames)."""
        if not self.preview_source_path or not os.path.exists(self.preview_source_path):
            return

        # Toggle
        if self.preview_playing:
            # Pause: stop ffmpeg but keep last frame, store timestamp via frame index
            self.preview_playing = False
            self._stop_preview_process()
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.play_pause_btn.show()
            return

        # Play: start (or resume from approximate timestamp)
        self.preview_playing = True
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.play_pause_btn.show()
        self.overlay_container.raise_()
        if getattr(self, 'preview_duration_sec', 0.0) > 0:
            self.preview_scrubber.show()
        self._start_preview_process(self.preview_source_path, seek_seconds=self.preview_seek_seconds)

    def _set_preview_placeholder(self, text="No Preview"):
        try:
            # Determine theme color
            if hasattr(self, 'locked') and self.locked:
                theme_color = '#888888'  # Gray
            elif hasattr(self, 'running') and hasattr(self, 'active_conversion_count') and (self.running or self.active_conversion_count > 0):
                theme_color = '#3CA37B'  # Green
            else:
                theme_color = '#43a296'  # Teal

            # Clear any pixmap, then set text and style
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(text)
            self.preview_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme_color};
                    font-size: 14px;
                    font-weight: normal;
                    background-color: transparent;
                    border: none;
                }}
            """)
        except Exception as e:
            logger.error(f"Error setting preview placeholder: {e}")

    def _forward_log_wheel(self, event):
        """Send wheel events to the console_output so scrolling always works."""
        try:
            # Re-target the wheel event to the text viewport so Qt can scroll it
            viewport = self.console_output.viewport()
            if viewport is None:
                return
            mapped_pos = viewport.mapFromGlobal(event.globalPos())
            new_event = QWheelEvent(
                mapped_pos,
                event.globalPos(),
                event.pixelDelta(),
                event.angleDelta(),
                event.buttons(),
                event.modifiers(),
                event.phase(),
                event.inverted()
            )
            QApplication.sendEvent(viewport, new_event)
            event.accept()
        except Exception:
            logger.debug("VideoConverterApp._forward_log_wheel: suppressed error", exc_info=True)

    def _clear_preview_display(self):
        """Fully reset sidebar preview (thumbnail/timeline/buttons/state)."""
        try:
            self._stop_preview_process()
        except Exception:
            logger.debug("VideoConverterApp._clear_preview_display: suppressed error", exc_info=True)
        try:
            self._stop_star_field()
        except Exception:
            logger.debug("VideoConverterApp._clear_preview_display: suppressed error", exc_info=True)
        self.preview_source_path = ""
        self.preview_playing = False
        self.preview_seek_seconds = 0.0
        self.preview_frame_index = 0
        self.preview_duration_sec = 0.0
        try:
            self.preview_scrubber.hide()
            self.preview_scrubber.setValue(0)
        except Exception:
            logger.debug("VideoConverterApp._clear_preview_display: suppressed error", exc_info=True)
        try:
            self.play_pause_btn.hide()
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        except Exception:
            logger.debug("VideoConverterApp._clear_preview_display: suppressed error", exc_info=True)
        self._set_preview_placeholder("No Preview")

    def _start_star_field(self, theme='teal'):
        """Start animated star field in preview box."""
        # Stop any existing star field or preview
        self._stop_preview_process()
        try:
            self._stop_star_field()
        except Exception:
            logger.debug("VideoConverterApp._start_star_field: suppressed error", exc_info=True)

        # Hide play button and scrubber
        self.play_pause_btn.hide()
        self.preview_scrubber.hide()

        # Determine star and background colors based on theme
        from PyQt5.QtGui import QColor
        if theme == 'gray':
            self.star_color = QColor('#888888')  # Gray stars on white
            self.star_bg_color = QColor('#FFFFFF')
        elif theme == 'teal':
            self.star_color = QColor('#43a296')  # Teal stars on white
            self.star_bg_color = QColor('#FFFFFF')
        else:  # green
            self.star_color = QColor('#3CA37B')  # Green stars on white
            self.star_bg_color = QColor('#FFFFFF')

        # Initialize stars
        import random
        self.stars = []
        for _ in range(30):  # 30 stars
            self.stars.append({
                'x': random.randint(0, self.preview_w),
                'y': random.randint(0, self.preview_h),
                'speed': random.uniform(1.0, 3.0),
                'size': random.randint(1, 3)
            })

        # Start animation timer
        self.star_field_timer = QTimer(self)
        self.star_field_timer.timeout.connect(self._update_star_field)
        self.star_field_timer.start(50)  # Update every 50ms

    def _stop_star_field(self):
        """Stop star field animation."""
        if hasattr(self, 'star_field_timer'):
            try:
                self.star_field_timer.stop()
                self.star_field_timer.deleteLater()
            except Exception:
                logger.debug("VideoConverterApp._stop_star_field: suppressed error", exc_info=True)
        if hasattr(self, 'stars'):
            self.stars = []

    def _update_star_field(self):
        """Update star positions and redraw."""
        import random
        from PyQt5.QtGui import QPixmap, QPainter

        # Create a canvas with theme background color
        pixmap = QPixmap(self.preview_w, self.preview_h)
        pixmap.fill(self.star_bg_color)

        # Draw stars
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.star_color)

        for star in self.stars:
            # Draw star
            painter.drawEllipse(int(star['x']), int(star['y']), star['size'], star['size'])

            # Move star down (cascading effect)
            star['y'] += star['speed']

            # Reset star to top when it goes off screen
            if star['y'] > self.preview_h:
                star['y'] = -star['size']
                star['x'] = random.randint(0, self.preview_w)

        painter.end()

        # Update preview label
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")

    def _probe_duration_seconds(self, file_path):
        """Return duration in seconds using ffprobe; 0 if unknown."""
        try:
            ffprobe_path = resource_path('ffprobe.exe')
            if not os.path.exists(ffprobe_path):
                return 0.0
            cmd = [
                ffprobe_path,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            startupinfo, creationflags = get_subprocess_startupinfo()
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 timeout=FFPROBE_TIMEOUT,
                                 startupinfo=startupinfo, creationflags=creationflags, check=False)
            s = (res.stdout or "").strip()
            if not s:
                return 0.0
            return max(0.0, float(s))
        except Exception:
            return 0.0

    def _generate_and_show_thumbnail(self, file_path):
        """Generate and show a thumbnail for the given file."""
        try:
            if not file_path or not os.path.exists(file_path):
                self._set_preview_placeholder("No Preview")
                return

            import tempfile
            # Clean up previous thumbnail if present
            try:
                old = getattr(self, '_preview_thumb_path', '')
                if old and os.path.exists(old):
                    os.remove(old)
            except Exception:
                logger.debug("VideoConverterApp._generate_and_show_thumbnail: suppressed error", exc_info=True)

            thumb_path = os.path.join(tempfile.gettempdir(), "nvc_preview.jpg")
            self._preview_thumb_path = thumb_path
            ffmpeg_path = resource_path('ffmpeg.exe')
            if not os.path.exists(ffmpeg_path):
                self._set_preview_placeholder("ffmpeg missing")
                return

            # Fill the whole preview box (cover) by scaling up and cropping (no black bars)
            vf = f"scale={self.preview_w}:{self.preview_h}:force_original_aspect_ratio=increase,crop={self.preview_w}:{self.preview_h}"

            cmd = [
                ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', '00:00:01', '-i', file_path,
                '-vframes', '1',
                '-vf', vf,
                thumb_path
            ]

            startupinfo, creationflags = get_subprocess_startupinfo()
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=FFMPEG_RENDER_TIMEOUT,
                           startupinfo=startupinfo, creationflags=creationflags, check=False)

            if os.path.exists(thumb_path):
                pix = QPixmap(thumb_path)
                self.preview_label.setText("")
                self.preview_label.setPixmap(pix)
            else:
                self._set_preview_placeholder("No Preview")
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            self._set_preview_placeholder("No Preview")

    def _stop_preview_process(self):
        try:
            if hasattr(self, 'preview_process') and self.preview_process.state() != QProcess.NotRunning:
                self.preview_process.kill()
                self.preview_process.waitForFinished(500)
        except Exception:
            logger.debug("VideoConverterApp._stop_preview_process: suppressed error", exc_info=True)
        try:
            self._preview_buf = bytearray()
        except Exception:
            logger.debug("VideoConverterApp._stop_preview_process: suppressed error", exc_info=True)

    def _start_preview_process(self, file_path, seek_seconds=0.0):
        """Start ffmpeg rawvideo decode for in-panel playback."""
        self._stop_preview_process()
        self._preview_buf = bytearray()
        self.preview_frame_index = max(0, int(seek_seconds * self.preview_fps))
        self.preview_seek_seconds = float(seek_seconds)

        ffmpeg_path = resource_path('ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            self._set_preview_placeholder("ffmpeg missing")
            self.preview_playing = False
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            return

        # Build filter: fill the whole preview box (cover) and keep frame size constant
        vf = f"scale={self.preview_w}:{self.preview_h}:force_original_aspect_ratio=increase,crop={self.preview_w}:{self.preview_h}"

        args = [
            '-hide_banner', '-loglevel', 'error',
            '-re',
        ]
        if seek_seconds and seek_seconds > 0:
            args += ['-ss', f"{seek_seconds:.3f}"]
        args += [
            '-i', file_path,
            '-an',
            '-vf', vf,
            '-r', str(self.preview_fps),
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            'pipe:1'
        ]

        self.preview_process.start(ffmpeg_path, args)
        if not self.preview_process.waitForStarted(1500):
            self._set_preview_placeholder("Preview failed")
            self.preview_playing = False
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def _tick_preview_ui(self):
        """Keep timeline scrubber in sync with preview playback."""
        try:
            if self._preview_user_scrubbing:
                return
            if not getattr(self, 'preview_source_path', ''):
                return
            if not getattr(self, 'preview_duration_sec', 0.0):
                # Unknown duration: keep scrubber hidden
                return
            frac = min(1.0, max(0.0, self.preview_seek_seconds / float(self.preview_duration_sec)))
            self.preview_scrubber.setValue(int(frac * 1000))
        except Exception:
            logger.debug("VideoConverterApp._tick_preview_ui: suppressed error", exc_info=True)

    def _on_preview_scrub_start(self):
        if not self.preview_source_path:
            return
        self._preview_user_scrubbing = True

    def _on_preview_scrub_value_changed(self, val):
        # While dragging, optionally update preview frame (cheap-ish), but avoid spamming.
        # We'll update on release for responsiveness.
        pass

    def _on_preview_scrub_end(self):
        if not self.preview_source_path:
            self._preview_user_scrubbing = False
            return
        self._preview_user_scrubbing = False
        if not self.preview_duration_sec:
            return
        frac = self.preview_scrubber.value() / 1000.0
        target = max(0.0, min(float(self.preview_duration_sec), frac * float(self.preview_duration_sec)))
        self.preview_seek_seconds = target
        self.preview_frame_index = int(self.preview_seek_seconds * self.preview_fps)

        if self.preview_playing:
            # Restart playback from new timestamp
            self._start_preview_process(self.preview_source_path, seek_seconds=self.preview_seek_seconds)
        else:
            # Paused: show a single frame at target
            self._render_frame_at(self.preview_source_path, self.preview_seek_seconds)

    def _render_frame_at(self, file_path, seconds):
        """Render a single frame at the given timestamp into the preview label."""
        try:
            import tempfile
            img_path = os.path.join(tempfile.gettempdir(), "nvc_preview_seek.jpg")
            ffmpeg_path = resource_path('ffmpeg.exe')
            if not os.path.exists(ffmpeg_path):
                return
            # Fill the whole preview box (cover)
            vf = f"scale={self.preview_w}:{self.preview_h}:force_original_aspect_ratio=increase,crop={self.preview_w}:{self.preview_h}"
            cmd = [
                ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', f"{seconds:.3f}",
                '-i', file_path,
                '-vframes', '1',
                '-vf', vf,
                img_path
            ]
            startupinfo, creationflags = get_subprocess_startupinfo()
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=FFMPEG_RENDER_TIMEOUT,
                           startupinfo=startupinfo, creationflags=creationflags, check=False)
            if os.path.exists(img_path):
                pix = QPixmap(img_path)
                self.preview_label.setText("")
                self.preview_label.setPixmap(pix)
        except Exception:
            logger.debug("VideoConverterApp._render_frame_at: suppressed error", exc_info=True)

    def _on_preview_bytes(self):
        """Consume rawvideo frames from ffmpeg."""
        try:
            data = bytes(self.preview_process.readAllStandardOutput())
            if not data:
                return
            self._preview_buf += data

            while len(self._preview_buf) >= self._preview_frame_size:
                frame = self._preview_buf[:self._preview_frame_size]
                del self._preview_buf[:self._preview_frame_size]

                img = QImage(frame, self.preview_w, self.preview_h, QImage.Format_RGB888).copy()
                self.preview_label.setText("")
                self.preview_label.setPixmap(QPixmap.fromImage(img))
                self.preview_frame_index += 1
                self.preview_seek_seconds = self.preview_frame_index / float(self.preview_fps)
        except Exception as e:
            logger.error(f"Preview decode error: {e}")
            self.preview_playing = False
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self._stop_preview_process()

    def _on_preview_finished(self, *args):
        # Playback ended or process stopped; keep last frame displayed
        self.preview_playing = False
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))


    def update_highlight_colors(self):
        """
        Update the tab underline color based on monitoring state and lock state.
        """
        if self.locked:
            # Grayscale for locked mode
            highlight = '#8a8a8a'
        elif self.is_active_workflow_visual_state():
            # Green for monitoring/converting
            highlight = '#92cb4f'
        else:
            # Teal for idle mode
            highlight = '#43a296'

        if hasattr(self, 'tabs'):
            tab_style = self.tab_stylesheet_template.format(highlight=highlight)
            self.tabs.setStyleSheet(tab_style)
        self.update_preview_controls_style()

    def update_preview_controls_style(self):
        if self.locked:
            highlight = '#8a8a8a'
        elif self.is_active_workflow_visual_state():
            highlight = '#92cb4f'
        else:
            highlight = '#43a296'

        if hasattr(self, 'play_pause_btn'):
            self.play_pause_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(0, 0, 0, 0.6);
                    border-radius: 11px;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    padding: 0px;
                    min-width: 22px;
                    max-width: 22px;
                    min-height: 22px;
                    max-height: 22px;
                }}
                QPushButton:hover {{
                    background-color: {highlight};
                    border: 1px solid {highlight};
                    border-radius: 11px;
                }}
            """)
        if hasattr(self, 'preview_scrubber'):
            self.preview_scrubber.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    height: 4px;
                    background: rgba(255, 255, 255, 0.35);
                    border-radius: 2px;
                }}
                QSlider::sub-page:horizontal {{
                    height: 4px;
                    background: {highlight};
                    border-radius: 2px;
                }}
                QSlider::add-page:horizontal {{
                    height: 4px;
                    background: rgba(255, 255, 255, 0.25);
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    width: 8px;
                    margin: -3px 0;
                    border-radius: 4px;
                    background: rgba(255, 255, 255, 0.75);
                    border: 1px solid rgba(0,0,0,0.2);
                }}
            """)

    def update_settings_display(self):
        """Update the current video settings display in the main area."""
        if hasattr(self, 'settings_display'):
            # Check if game is active
            if hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None:
                # Show game progress
                try:
                    score = getattr(self.ballbuster_widget, 'score', 0)
                    level = getattr(self.ballbuster_widget, 'level_index', 0) + 1  # Display as 1-indexed
                    high_scores = getattr(self.ballbuster_widget, 'high_scores', [])
                    # Get the highest score and level from high_scores list
                    # high_scores format: [(name, score, level), ...]
                    high_score = high_scores[0][1] if high_scores else 0
                    highest_level = high_scores[0][2] if high_scores else 0

                    settings_text = f"""
<div style="line-height: 1.2;">
<b>Current Game Progress:</b><br>
• Current Score: {score}<br>
• High Score: {high_score}<br>
• Level: {level}<br>
• Highest Level: {highest_level}<br>
<span style="color: transparent;">• Placeholder</span><br>
<span style="color: transparent;">• Placeholder</span>
</div>
"""
                    self.settings_display.setText(settings_text)
                    return
                except Exception:
                    pass  # Fall through to show video settings if game data unavailable

            # Format settings similar to EthoVision dialog
            settings_text = f"""
<div style="line-height: 1.2;">
<b>Current Video Settings:</b><br>
• Format: {self.settings.get('output_format', 'MP4').upper()}<br>
• Video Codec: {self.settings.get('video_codec', 'H.264')}<br>
• Audio Codec: {self.settings.get('audio_codec', 'AAC')}<br>
• Resolution: {self.settings.get('video_size', '1920x1080')}<br>
• Bitrate: {self.settings.get('video_bitrate', '2000k')}<br>
• Frame Rate: {self.settings.get('framerate', '25')} fps
</div>
"""

            # Add time restrictions if enabled
            if not self.settings.get('no_time_restrictions', True):
                start_time = self.settings.get('start_time', '00:00')
                end_time = self.settings.get('end_time', '23:59')
                settings_text += f"• Time Window: {start_time} - {end_time}<br>"

            # Add copy-only mode if enabled
            if self.settings.get('copy_only', False):
                settings_text += "• Mode: Copy Only (No Conversion)<br>"

            self.settings_display.setText(settings_text)

    def open_file_dialog(self):
        from PyQt5.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(self, "Select Media Files", "", "Media Files (*.mp4 *.avi *.wmv *.mkv *.flv *.webm *.mov *.mpeg *.mpg *.m4v *.3gp *.ts *.vob *.rm *.rmvb *.asf *.m2ts *.mts *.ogv *.divx *.dv *.f4v)")
        if not files:
            return
        if self.locked:
            for path in collect_supported_media_paths(files, SUPPORTED_FORMATS):
                self.converted_files_widget.add_queued_file(os.path.basename(path), self.destination_folder)
                if path not in self.manual_queue:
                    self.manual_queue.append(path)
            self._wiggle_lock_icon()
            self.append_log("Files queued while locked. Unlock and start conversion to process them.")
            return
        unsupported_files = []
        show_dialog = self.settings.get('show_drop_confirmation', True)
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            if os.path.isfile(file_path) and ext in SUPPORTED_FORMATS:
                # Add to queue as 'queued'
                self.converted_files_widget.add_queued_file(os.path.basename(file_path), self.destination_folder)
                if show_dialog:
                    reply = QMessageBox.question(
                        self,
                        "Convert Media File",
                        "Do you wish to convert media file according to settings?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.No:
                        continue
                    if not self.settings.get('dont_show_drop_dialog', False):
                        dont_show_reply = QMessageBox.question(
                            self,
                            "Don't Show Again",
                            "Don't show me this dialog again?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if dont_show_reply == QMessageBox.Yes:
                            self.settings['show_drop_confirmation'] = False
                            save_settings(self.settings)
                self.convert_file(file_path, force=True)
            else:
                unsupported_files.append(file_path)
        if unsupported_files:
            unsupported_list = "\n".join(unsupported_files)
            QMessageBox.warning(self, "Unsupported Files", f"The following files are not supported:\n{unsupported_list}")
            logger.info(f"Unsupported files selected:\n{unsupported_list}")

    def open_inspection_file_dialog(self):
        """Open file dialog specifically for the Video Inspection Tool."""
        from PyQt5.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(self, "Select Media Files to Inspect", "", "Media Files (*.mp4 *.avi *.wmv *.mkv *.flv *.webm *.mov *.mpeg *.mpg *.m4v *.3gp *.ts *.vob *.rm *.rmvb *.asf *.m2ts *.mts *.ogv *.divx *.dv *.f4v)")
        if not files:
            return
        # Inspect the first selected file
        file_path = files[0]
        if os.path.isfile(file_path):
            self.inspection_widget.inspect_file(file_path)
            # Switch to inspection tab if not already there
            inspection_tab_index = self.tabs.indexOf(self.inspection_tab_scroll)
            if inspection_tab_index >= 0:
                self.tabs.setCurrentIndex(inspection_tab_index)

    def launch_ballbuster_game(self):
        if hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None:
            return # Game already running

        from ui.ballbuster_widget import BallBusterWidget

        # Determine color theme based on app state
        if self.running or self.active_conversion_count > 0:
            theme = 'green'
        elif self.locked:
            theme = 'gray'
        else:
            theme = 'teal'

        # Start star field animation in preview when entering game mode
        self._start_star_field(theme)

        self.log_container.hide()

        self.ballbuster_widget = BallBusterWidget(theme=theme)
        self.ballbuster_widget.setAttribute(Qt.WA_DeleteOnClose)
        self.log_tab_layout.insertWidget(self.log_container_index, self.ballbuster_widget, 1) # stretch=1
        self.ballbuster_widget.setFocus()

        # Update settings display to show game progress
        self.update_settings_display()

        # Start a timer to update game progress in real-time
        self.game_progress_timer = QTimer(self)
        self.game_progress_timer.timeout.connect(self.update_settings_display)
        self.game_progress_timer.start(100)  # Update every 100ms for smooth score updates

        # Disable mouse interaction for all other widgets (so they keep visual style)
        self.mouse_blocked_widgets = []
        protected = (self.ballbuster_widget, self.start_button)
        for w in self.findChildren(QWidget):
            if w in protected or any(p.isAncestorOf(w) or w.isAncestorOf(p) for p in protected):
                continue
            if not w.testAttribute(Qt.WA_TransparentForMouseEvents):
                w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.mouse_blocked_widgets.append(w)

        # Hide drag-drop overlay if present
        if hasattr(self, 'drag_drop_overlay'):
            self.drag_drop_overlay.hide()

        self.ballbuster_widget.destroyed.connect(self.restore_log_view)
        # Update status label to Gaming
        self.status_label_log_tab.setText("Status: Gaming <font color='#43a296'>●</font>")

        # Transform Start button into Exit Game
        try:
            self.start_button.clicked.disconnect()
        except Exception:
            logger.debug("launch_ballbuster_game: suppressed error", exc_info=True)
        # Ensure the button is clickable even in locked (gray) mode
        self.start_button.setEnabled(True)
        self.start_button.setText("Exit Game")
        self.start_button.setToolTip("Click to exit the Easter Egg and return to the log view.")
        self.start_button.clicked.connect(self.exit_game)
        # Refresh sidebar logo to BallBuster version
        self.update_icons()
        return

        # Restore start button behaviour
        try:
            self.start_button.clicked.disconnect(self.exit_game)
        except Exception:
            logger.debug("launch_ballbuster_game: suppressed error", exc_info=True)
        if self.start_button.receivers(self.start_button.clicked) == 0:
            self.start_button.clicked.connect(self.toggle_process)
        self.set_start_button_state(is_running=self.running)

        # Restore status labels
        self.update_status_labels()

        # Restore settings display to show video settings
        self.update_settings_display()

        # Re-enable previously disabled widgets
        if hasattr(self, 'disabled_for_game'):
            for w in self.disabled_for_game:
                try:
                    w.setEnabled(True)
                except RuntimeError:
                    pass
            self.disabled_for_game = []

    def restore_log_view(self):
        # Stop the game progress timer if it exists
        if hasattr(self, 'game_progress_timer') and self.game_progress_timer:
            self.game_progress_timer.stop()
            self.game_progress_timer = None

        # Stop star field animation and clear preview
        try:
            self._stop_star_field()
        except Exception:
            logger.debug("restore_log_view: suppressed error", exc_info=True)
        try:
            self._clear_preview_display()
        except Exception:
            logger.debug("restore_log_view: suppressed error", exc_info=True)

        if hasattr(self, 'ballbuster_widget') and self.ballbuster_widget:
            try:
                self.log_tab_layout.removeWidget(self.ballbuster_widget)
            except RuntimeError:
                # Widget might have been deleted already
                pass
            self.ballbuster_widget = None

        self.log_container.show()
        self.log_tab_footer_widget.show()
        # Restore NVC logo and tray icon
        self.update_icons()

        if hasattr(self, 'drag_drop_overlay'):
            self.drag_drop_overlay.show()
            # Bring overlay to front again but let wheel events through
            self.drag_drop_overlay.raise_()
            self.log_container.setAcceptDrops(True)

        # Restore start button behaviour
        try:
            self.start_button.clicked.disconnect(self.exit_game)
        except Exception:
            logger.debug("restore_log_view: suppressed error", exc_info=True)
        if self.start_button.receivers(self.start_button.clicked) == 0:
            self.start_button.clicked.connect(self.toggle_process)
        self.set_start_button_state(is_running=self.running)

        # Restore status labels
        self.update_status_labels()

        # Restore settings display to show video settings
        self.update_settings_display()

        # Re-enable mouse interaction
        if hasattr(self, 'mouse_blocked_widgets'):
            for w in self.mouse_blocked_widgets:
                try:
                    w.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                except RuntimeError:
                    pass
            self.mouse_blocked_widgets = []

    def on_tab_changed(self, index):
        # If game is running and we move away from log tab (index 0), close it.
        if hasattr(self, 'ballbuster_widget') and self.ballbuster_widget and index != 0:
            self.ballbuster_widget.close()
        self.update_single_workflow_availability()

    def exit_game(self):
        if hasattr(self, 'ballbuster_widget') and self.ballbuster_widget:
            self.ballbuster_widget.close()
