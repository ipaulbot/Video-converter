import os
import shutil
import subprocess
import threading
import sys
from datetime import datetime

from PyQt5.QtWidgets import (
    QActionGroup,
    QMainWindow, QWidget, QLabel, QPushButton, QTabWidget,
    QHBoxLayout, QVBoxLayout, QSystemTrayIcon, QStyle, QMenu,
    QPlainTextEdit, QMessageBox, QSpacerItem, QSizePolicy, QProgressBar,
    QAction, QToolBar, QToolButton, QFrame, QStackedWidget, QGridLayout,
    QApplication, QStackedLayout, QSlider, QScrollArea, QSplitter, QFileDialog
)
from PyQt5.QtCore import (QCoreApplication, Qt, QTimer, QThreadPool, pyqtSignal,
                          QSize, QEvent, QUrl, QProcess, QPoint,
                          QPropertyAnimation, QEasingCurve)
from PyQt5.QtGui import (QPixmap, QIcon, QFont, QTextCursor, QPainter, QColor, QImage, QWheelEvent, QPen, QBrush,
                         QDesktopServices)

# Use native Observer; fall back to PollingObserver if needed.
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from ui.converted_files_widget import ConvertedFilesWidget
from ui.settings_dialog import SettingsDialog
from ui.dialogs import InfoDialog, ConfirmationDialog, EasterEggDialog
from utils.config import load_settings, normalize_tool_tab_order, save_settings
from utils.system_state import get_game_unlocked, set_game_unlocked
from utils.logger import logger
from utils.resources import resource_path
from utils.media_files import collect_supported_media_paths
from utils.paths import log_dir
from ui import theme
from conversion.queue_state import Admission, ConversionQueueState
from utils.subprocess_helpers import (
    FFMPEG_RENDER_TIMEOUT,
    FFPROBE_TIMEOUT,
    get_subprocess_startupinfo,
)
from conversion.worker import ConversionWorker, WorkerSignals
from conversion.ffmpeg_utils import is_within_allowed_time
from ui.log_bus import LogBus
from ui.leaf_frame import LeafFrame
from ui.lossless_editor_widget import LosslessEditorWidget
from ui.multi_source_recorder_widget import MultiSourceRecorderWidget
from ui.media_player_widget import MediaPlayerWidget
from conversion.recording_commands import recording_layout_preview_rects
from conversion.recorder_settings import load_recorder_settings
from ui.pc_report_dialog import PCReportWidget
from ui.tab_header import TabHeader
from ui.workflow_rules import Activity, blocked_reason, status_markup
from utils.update_checker import UpdateChecker, UpdateWorker



def _tr(source: str) -> str:
    """Translate this module's strings under the stable "MainWindow" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("MainWindow", source)

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
        self.setWindowTitle(_tr("Video Converter v%(version)s")
                            % {"version": APP_VERSION})
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
        # Queue bookkeeping lives in ConversionQueueState (Qt-free and tested).
        self.queue = ConversionQueueState()
        self.file_detected.connect(self.convert_file)

        # Use modern clean stylesheet
        modern_stylesheet = theme.qss("""
            QWidget {
                color: $text_body;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
            }
            /* Only the window surfaces are grey. Children paint nothing of
               their own, so labels and group boxes sitting on a white leaf
               card stay white instead of showing grey blocks. */
            QMainWindow, QDialog {
                background: $window_bg;
            }
            QScrollArea, QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent, stop:1 $accent_pressed);
                border: 1px solid $accent_dark;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_hover, stop:1 $accent);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_pressed, stop:1 $accent_dark);
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
                margin-top: 4px;
            }
            QTabBar::tab {
                background: $panel_alt_bg;
                border: 1px solid $separator;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: normal;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid $accent;
            }
            QPlainTextEdit {
                background: white;
                border: 1px solid $separator;
                border-radius: 4px;
            }
            QSplitter::handle {
                background: transparent;
            }
            QMenuBar, QMenu {
                background: white;
                border: 1px solid $separator;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: $accent;
                color: white;
            }
            QProgressBar {
                border: 1px solid $separator;
                background: $window_bg;
                border-radius: 4px;
                text-align: center;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
                font-weight: normal;
                color: $text_body;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: $accent;
                border-radius: 3px;
                margin: 1px;
            }
        """)
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
        self.logo_label.setStyleSheet(theme.qss("""
            QLabel { 
                background: transparent; 
                border: none; 
                padding: 0px;
            }
            QLabel:hover { 
                background: $inner_border;
                border-radius: 25px;
            }
        """))
        self.logo_label.setCursor(Qt.PointingHandCursor)
        self.logo_label.setToolTip(_tr("Click to open settings"))
        self.logo_label.mousePressEvent = self.logo_clicked
        self.logo_pixmap = None
        self.grayscale_logo_pixmap = None

        # --- Video Preview Panel (below logo) ---
        # Owned by PreviewController (ui/preview_controller.py), which builds
        # the box and runs the ffmpeg decode pipeline. Its widgets are exposed
        # as properties below so existing call sites keep working.
        from ui.preview_controller import PreviewController
        self.preview = PreviewController(self)

        # Update Checker Label (hidden by default, shown if update available)
        self.update_label = QLabel(_tr("Update Available!"))
        self.update_label.setAlignment(Qt.AlignCenter)
        self.update_label.setStyleSheet(theme.qss("background: $warning_bright; color: $text_body; padding: 4px; border-radius: 4px; font-weight: bold;"))
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
            theme.qss("QTabBar {{ color: $text_body; }} QTabBar::tab {{ min-width: {tab_min}px; padding: {tab_pad}; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: {tab_font}pt; border-top-left-radius: 6px; border-top-right-radius: 6px; background: $panel_alt_bg; border: 1px solid $separator; border-bottom: none; margin-right: 2px; font-weight: normal; color: $text_body; }} QTabBar::tab:selected {{ background: white; border-bottom: 2px solid {highlight}; color: $text_body; }} QTabBar::tab:selected:focus {{ color: $text_body; }} QTabBar::tab:selected:!focus {{ color: $text_body; }} QTabBar::tab:selected:active {{ color: $text_body; }} QTabBar::tab:!selected {{ background: $panel_alt_bg; border: 1px solid $separator; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; color: $text_body; }} QTabBar::tab:!selected:focus {{ color: $text_body; }} QTabBar::tab:!selected:active {{ color: $text_body; }} QTabWidget::pane {{ margin: 4px; border: none; background: transparent; }}")
        )
        # Set initial tab stylesheet with teal underline
        self.tabs = QTabWidget()
        self.tool_tab_cards = {}
        self.tabs.setCursor(Qt.PointingHandCursor)
        # Shrink and elide tabs rather than growing scroll arrows when the
        # bar is too narrow for every enabled tool tab.
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setElideMode(Qt.ElideRight)
        # Drag a tab to reorder; the order is saved once the tool tabs exist
        # (see apply_tool_tab_order / _on_tab_moved).
        self.tabs.setMovable(True)
        self.apply_tab_style("#43a296")
        # Conversion Log Tab
        self.log_tab = QWidget()
        log_tab_layout = QVBoxLayout(self.log_tab)
        # Set margins to match video inspection tool
        log_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setContextMenuPolicy(Qt.CustomContextMenu)
        self.console_output.customContextMenuRequested.connect(
            lambda pos: self.show_log_context_menu_global(self.console_output.mapToGlobal(pos))
        )
        # Clean modern styling for log output (scrollable, scrollbar hidden)
        self.console_output.setStyleSheet(theme.qss("""
            QPlainTextEdit {
                border: 1px solid $separator;
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
            """))

        # Create a container widget for the log area with overlay
        self.log_container = QFrame()
        self.log_container.setFrameStyle(QFrame.Box)
        self.log_container.setStyleSheet(theme.qss("QFrame { border: 1px solid $separator; border-radius: 6px; background: white; }"))
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
        self.drag_drop_overlay.setStyleSheet(theme.qss("""
            QWidget { 
                background: white; 
                border: 2px dashed $panel_border; 
                $leaf
                margin: 10px;
            }
            QWidget:hover {
                border-color: $accent;
                background: rgba(67, 162, 150, 0.1);
            }
        """, leaf=theme.leaf_radii(18)))
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
        self.drag_drop_text = QLabel(_tr("Drag and drop media files here\nor select source folder to start monitoring and converting"))
        self.drag_drop_text.setAlignment(Qt.AlignCenter)
        self.drag_drop_text.setStyleSheet(theme.qss("""
            QLabel { 
                color: $text_muted; 
                font-size: 12px; 
                background: rgba(255,255,255,0.85); 
                border-radius: 8px;
                border: none;
                padding: 12px;
            }
        """))
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
            lock_label.setToolTip(_tr("Lock/Unlock settings"))
            lock_label.mousePressEvent = self.lock_icon_clicked
            lock_label.setStyleSheet(theme.qss("""
                QLabel { 
                    background: transparent; 
                    border: none; 
                    padding: 4px;
                }
                QLabel:hover {
                    background: $inner_border;
                    border-radius: 18px;
                }
            """))
            # File icon button (dynamic)
            file_icon_path = self.get_icon_path('FILE')
            file_label = QLabel()
            if os.path.exists(file_icon_path):
                file_pixmap = QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                file_label.setPixmap(file_pixmap)
            file_label.setFixedSize(36, 36)
            file_label.setAlignment(Qt.AlignCenter)
            file_label.setCursor(Qt.PointingHandCursor)
            file_label.setToolTip(_tr("Select media files to convert"))
            file_label.mousePressEvent = lambda event: self.open_file_dialog()
            file_label.setStyleSheet(theme.qss("""
                QLabel { 
                    background: transparent; 
                    border: none; 
                    padding: 4px;
                }
                QLabel:hover {
                    background: $inner_border;
                    border-radius: 18px;
                }
            """))
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
            broom_label.setToolTip(_tr("Clear log"))
            broom_label.mousePressEvent = clear_callback
            broom_label.setStyleSheet(theme.qss("""
                QLabel { 
                    background: transparent; 
                    border: none; 
                    padding: 4px;
                }
                QLabel:hover {
                    background: $inner_border;
                    border-radius: 18px;
                }
            """))
            # Save references for update_lock_state_ui if needed
            if status_label is self.status_label_log_tab:
                self.file_label_log_tab = file_label
                self.broom_label_log_tab = broom_label
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
        self.broom_label_log_tab.setToolTip(_tr("Clear the file list and the log"))
        # Explicitly set zero margins on both the widget and layout to match direct addLayout behavior
        self.log_tab_footer_widget.setContentsMargins(0, 0, 0, 0)
        self.log_tab_footer.setContentsMargins(0, 0, 0, 0)
        self.log_tab_footer_widget.setLayout(self.log_tab_footer)
        # Video Converter tab: the Converted Files table above the conversion log,
        # in one card with one footer. Replaced the separate Conversion Log and
        # Converted Files tabs on 2026-09-26.
        self.converted_files_widget = ConvertedFilesWidget(button_style=getattr(self, 'current_button_style', None))
        # Forward drag/drop from the converted list to the main window handler
        self.converted_files_widget.drop_files_signal.connect(self._handle_converted_tab_drop)
        self.converted_files_widget.set_log_folder(log_dir(self.settings))
        # Preview on selection in converted list
        try:
            self.converted_files_widget.preview_requested.connect(
                lambda path: self.preview_file(path) if path else self._clear_preview_display()
            )
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)
        self.converted_files_widget.play_requested.connect(self.play_in_media_player)
        self.converted_files_widget.inspect_requested.connect(self.inspect_in_media_player)
        self.converted_files_widget.add_files_requested.connect(lambda: self.open_file_dialog())
        self.converted_files_widget.monitor_folder_requested.connect(self.monitor_folder_from_menu)
        self.converted_files_widget.open_in_requested.connect(self.open_file_in)
        # Clean modern styling for converted files widget
        self.converted_files_widget.setStyleSheet(theme.qss("QTableWidget { border: 1px solid $separator; border-radius: 6px; background: white; }"))

        self.converter_tab = QWidget()
        converter_layout = QVBoxLayout(self.converter_tab)
        converter_layout.setContentsMargins(0, 0, 0, 0)
        self.converter_header = TabHeader(
            "convert",
            _tr("Video Converter"),
            _tr("Drop files or monitor a folder; converted files are listed above the log."),
        )
        converter_layout.addWidget(self.converter_header)
        self.converter_splitter = QSplitter(Qt.Vertical)
        self.converter_splitter.setChildrenCollapsible(False)
        self.converter_splitter.setHandleWidth(8)
        self.converter_splitter.addWidget(self.converted_files_widget)
        self.converter_splitter.addWidget(self.log_tab)
        self.converter_splitter.setStretchFactor(0, 2)
        self.converter_splitter.setStretchFactor(1, 3)
        converter_layout.addWidget(self.converter_splitter, 1)
        converter_layout.addWidget(self.log_tab_footer_widget)
        # Scroll wrapper (scrolling enabled, scrollbar hidden)
        self.converter_tab_scroll = QScrollArea()
        self.converter_tab_scroll.setWidgetResizable(True)
        self.converter_tab_scroll.setFrameShape(QFrame.NoFrame)
        self.converter_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.converter_tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.converter_tab_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar { width: 0px; height: 0px; }
        """)
        card = LeafFrame(radius=28)
        card.body.addWidget(self.converter_tab)
        self.tool_tab_cards["video_converter"] = card
        self.converter_tab_scroll.setWidget(card)
        # Forward wheel events from the scroll area to the log text for smooth scrolling
        self.converter_tab_scroll.wheelEvent = lambda e: self._forward_log_wheel(e)
        self.converter_tab_scroll.installEventFilter(self)
        self.tabs.addTab(self.converter_tab_scroll, _tr("Video Converter"))

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
        pc_report_layout.setContentsMargins(0, 0, 0, 0)
        pc_report_layout.addWidget(self.pc_report_widget)
        self.lock_icon_label_pc_report_tab = QLabel()
        self.status_label_pc_report_tab = QLabel()
        self.status_label_pc_report_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_pc_report_tab.setFont(monospaced_font)
        pc_report_layout.addLayout(make_footer(self.lock_icon_label_pc_report_tab, self.status_label_pc_report_tab, self.clear_pc_report_tab))

        self.pc_report_tab_scroll = QScrollArea()
        self.pc_report_tab_scroll.setWidgetResizable(True)
        self.pc_report_tab_scroll.setFrameStyle(0)
        card = LeafFrame(radius=28)
        card.body.addWidget(self.pc_report_tab)
        self.tool_tab_cards["pc_report"] = card
        self.pc_report_tab_scroll.setWidget(card)
        self.tabs.addTab(self.pc_report_tab_scroll, _tr("PC Report"))

        # Lossless Editor Tab
        self.lossless_editor_widget = LosslessEditorWidget(
            SUPPORTED_FORMATS,
            self,
            button_style=getattr(self, 'current_button_style', None)
        )
        self.lossless_editor_tab = QWidget()
        lossless_editor_layout = QVBoxLayout(self.lossless_editor_tab)
        lossless_editor_layout.setContentsMargins(0, 0, 0, 0)
        lossless_editor_layout.addWidget(self.lossless_editor_widget)
        self.lock_icon_label_lossless_editor_tab = QLabel()
        self.status_label_lossless_editor_tab = QLabel()
        self.status_label_lossless_editor_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_lossless_editor_tab.setFont(monospaced_font)
        lossless_editor_layout.addLayout(make_footer(self.lock_icon_label_lossless_editor_tab, self.status_label_lossless_editor_tab, self.clear_lossless_editor_tab))
        self.lossless_editor_tab_scroll = QScrollArea()
        self.lossless_editor_tab_scroll.setWidgetResizable(True)
        self.lossless_editor_tab_scroll.setFrameStyle(0)
        card = LeafFrame(radius=28)
        card.body.addWidget(self.lossless_editor_tab)
        self.tool_tab_cards["lossless_editor"] = card
        self.lossless_editor_tab_scroll.setWidget(card)
        self.tabs.addTab(self.lossless_editor_tab_scroll, _tr("Lossless Editor"))

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
        multi_source_recorder_layout.setContentsMargins(0, 0, 0, 0)
        multi_source_recorder_layout.addWidget(self.multi_source_recorder_widget)
        self.lock_icon_label_multi_source_recorder_tab = QLabel()
        self.status_label_multi_source_recorder_tab = QLabel()
        self.status_label_multi_source_recorder_tab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label_multi_source_recorder_tab.setFont(monospaced_font)
        multi_source_recorder_layout.addLayout(make_footer(self.lock_icon_label_multi_source_recorder_tab, self.status_label_multi_source_recorder_tab, self.clear_multi_source_recorder_tab))
        self.multi_source_recorder_tab_scroll = QScrollArea()
        self.multi_source_recorder_tab_scroll.setWidgetResizable(True)
        self.multi_source_recorder_tab_scroll.setFrameStyle(0)
        card = LeafFrame(radius=28)
        card.body.addWidget(self.multi_source_recorder_tab)
        self.tool_tab_cards["multi_source_recorder"] = card
        self.multi_source_recorder_tab_scroll.setWidget(card)
        self.tabs.addTab(self.multi_source_recorder_tab_scroll, _tr("Multi-Source Recorder"))

        # Media Player Tab. The player tree (4 video panels) is heavy and the tab is
        # hidden by default, so it is built lazily the first time the tab is shown via
        # _ensure_media_player_widget(). This keeps startup cheap and avoids building the
        # widget in the many headless tests that never open it.
        self.media_player_widget = None
        self.media_player_tab = QWidget()
        media_player_layout = QVBoxLayout(self.media_player_tab)
        media_player_layout.setContentsMargins(0, 0, 0, 0)
        self.media_player_layout = media_player_layout
        self.media_player_placeholder = QLabel(_tr("Loading media player…"))
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
        card = LeafFrame(radius=28)
        card.body.addWidget(self.media_player_tab)
        self.tool_tab_cards["media_player"] = card
        self.media_player_tab_scroll.setWidget(card)
        self.tabs.addTab(self.media_player_tab_scroll, _tr("Media Player"))

        self.tool_tab_widgets = {
            "video_converter": self.converter_tab_scroll,
            "pc_report": self.pc_report_tab_scroll,
            "lossless_editor": self.lossless_editor_tab_scroll,
            "multi_source_recorder": self.multi_source_recorder_tab_scroll,
            "media_player": self.media_player_tab_scroll,
        }
        self.apply_tool_tab_order()
        self.tabs.tabBar().tabMoved.connect(self._on_tab_moved)
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
        self.settings_display.setStyleSheet(theme.qss("""
            QLabel { 
                color: $ink_slate; 
                font-size: 9pt; 
                background: transparent; 
                border: none;
                margin: 0px;
                padding: 0px;
                text-align: justify;
            }
        """))
        self.settings_display.setWordWrap(True)
        self.settings_display.setFixedWidth(180)
        # Make it clickable with hover effects
        self.settings_display.mousePressEvent = self.settings_display_clicked
        self.settings_display.enterEvent = self.settings_display_enter
        self.settings_display.leaveEvent = self.settings_display_leave
        self.settings_display.setCursor(Qt.PointingHandCursor)  # Show hand cursor on hover
        self.settings_display.setToolTip(_tr("Open Settings"))  # Add tooltip
        left_layout.addWidget(self.settings_display)

        # Preview goes below settings text (no special centering; align with other sidebar items)
        left_layout.addWidget(self.preview_container)

        left_layout.addStretch()

        # Start/Stop Button
        self.start_button = QPushButton(_tr("Start"))
        # Its look is driven by set_start_button_state, so the global
        # button sweep must not overwrite it.
        theme.opt_out_of_button_style(self.start_button)
        # Match settings + preview width for perfect edge alignment
        self.start_button.setFixedWidth(180)
        self.start_button.setToolTip(_tr("Start or stop the automatic conversion process."))
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self.toggle_process)
        left_layout.addWidget(self.start_button)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.tabs)

        # Add compact mode toggle and burger menu to the top right
        from PyQt5.QtWidgets import QToolButton, QMenu
        self.burger_button = QToolButton()
        self.burger_button.setPopupMode(QToolButton.InstantPopup)
        self.burger_button.setCursor(Qt.PointingHandCursor)
        # Create the dropdown menu
        burger_menu = QMenu()
        # Add actions without icons initially - they will be set by update_icons()
        burger_menu.addAction(_tr("Info"), self.show_info)
        burger_menu.addAction(_tr("Help"), self.open_help_document)
        burger_menu.addSeparator()
        burger_menu.addSeparator()
        burger_menu.addAction(_tr("Open Source Folder"), self.open_source_folder_in_explorer)
        burger_menu.addAction(_tr("Open Destination Folder"), self.open_destination_folder_in_explorer)
        burger_menu.addAction(_tr("Open Backup Folder"), self.open_backup_folder_in_explorer)
        burger_menu.addSeparator()
        burger_menu.addAction(_tr("Settings"), self.show_settings)
        window_menu = burger_menu.addMenu(_tr("Window"))
        from PyQt5.QtWidgets import QActionGroup
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        self.window_mode_actions = {}
        for mode, label in (("compact", _tr("Compact mode")), ("full", _tr("Full window mode"))):
            action = window_menu.addAction(label)
            action.setCheckable(True)
            action.setData(mode)
            mode_group.addAction(action)
            action.triggered.connect(lambda _checked, m=mode: self.set_window_mode(m))
            self.window_mode_actions[mode] = action
        self._add_language_menu(burger_menu)
        burger_menu.addAction(_tr("Check for Updates"), self.check_for_updates)
        burger_menu.addSeparator()
        burger_menu.addAction(_tr("Quit"), self.quit_application)
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
        self._fit_burger_button()
        # React to tab changes (e.g., restore log view, keep UI in sync)
        try:
            self.tabs.currentChanged.connect(self.on_tab_changed)
        except Exception:
            logger.debug("VideoConverterApp.__init__: suppressed error", exc_info=True)
        self.setStyleSheet(self.styleSheet() + '\nQMainWindow { border-radius: 8px; background: #F5F5F5; }')
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
        self.set_window_mode(self.settings.get("window_mode", "compact"), persist=False)

        # Enable mouse tracking on the main window for proper hover detection
        self.setMouseTracking(True)

        # Set the initial start button state after all widgets are created
        self.set_start_button_state(is_running=self.running)

        # Initialize system tray icon and ensure app keeps running when window is closed
        self.init_tray_icon()
        QApplication.setQuitOnLastWindowClosed(False)

        self.log_tab_layout = log_tab_layout
        self.log_container_index = self.log_tab_layout.indexOf(self.log_container)

    def hide_files_table_for_game(self):
        """The easter-egg game replaces the log pane; give it the whole card."""
        self.converted_files_widget.hide()

    def restore_files_table_after_game(self):
        self.converted_files_widget.show()

    def layout_mode_widgets(self):
        """Tool widgets that adapt to the window mode."""
        candidates = (
            getattr(self, "multi_source_recorder_widget", None),
            getattr(self, "media_player_widget", None),
            getattr(self, "pc_report_widget", None),
            getattr(self, "lossless_editor_widget", None),
        )
        return [w for w in candidates if w is not None and hasattr(w, "apply_layout_mode")]

    def _fit_burger_button(self):
        """Size the burger to the corner slot QTabWidget actually gives it.

        The corner widget is laid out at the tab bar's height and clipped to
        it. The button used to be a fixed 43 px with a 43 px icon and 4 px of
        padding, so in a 31 px slot the round icon lost its bottom edge. The
        tab bar's height depends on the layout mode (tab font / padding), so
        set_window_mode calls this again after restyling the tabs.
        """
        button = getattr(self, "burger_button", None)
        if button is None or not hasattr(self, "tabs"):
            return
        padding = 2
        size = max(20, self.tabs.tabBar().sizeHint().height())
        button.setFixedSize(size, size)
        button.setIconSize(QSize(size - 2 * padding, size - 2 * padding))
        button.setProperty("glyph_padding", padding)
        button.setStyleSheet(theme.qss("""
            QToolButton {
                background: transparent;
                border: none;
                padding: ${padding}px;
                margin: 0px;
                spacing: 0px;
            }
            QToolButton:hover {
                background: $inner_border;
                border-radius: ${radius}px;
            }
            QToolButton::menu-indicator {
                image: none;
            }
        """, padding=padding, radius=size // 2))

    def set_window_mode(self, name, persist=True, resize=True):
        """Switch between Compact (theme.COMPACT.window_size, normal) and Full window (maximised).

        `resize=False` re-flows the tabs for the mode but leaves the window
        geometry alone; changeEvent uses it when the title-bar maximize /
        restore button already changed the window state.

        Raises ValueError for unknown names so a typo in settings cannot leave
        the window half-applied.
        """
        metrics = theme.set_layout_mode(name)
        self.settings["window_mode"] = metrics.name
        for mode, action in getattr(self, "window_mode_actions", {}).items():
            action.setChecked(mode == metrics.name)
        # One frame, not five: the re-flow (margins, every tab's layout mode,
        # tab restyle) and the geometry change (restore, resize, centre) each
        # used to paint on their own, so full -> compact flickered through
        # half-laid-out panels for about half a second. Hold repaints until
        # everything is in place, then let a single paint show the result.
        self.setUpdatesEnabled(False)
        try:
            central = self.centralWidget()
            if central is not None and central.layout() is not None:
                m = metrics.margin
                central.layout().setContentsMargins(m, m, m, m)
            for widget in self.layout_mode_widgets():
                widget.apply_layout_mode(metrics)
            if hasattr(self, "tabs"):
                self.apply_tab_style(theme.highlight_color())
                self._fit_burger_button()
            # Before the first show() (i.e. from __init__) only record the window
            # state; main.py's show() honours it. Showing here would pop the window
            # up mid-construction, and in every test that builds the main window.
            if resize and metrics.name == "full":
                if self.isVisible():
                    self.showMaximized()
                else:
                    self.setWindowState(self.windowState() | Qt.WindowMaximized)
            elif resize:
                if self.isVisible():
                    self.showNormal()
                else:
                    self.setWindowState(self.windowState() & ~Qt.WindowMaximized)
                self.resize(*metrics.window_size)
                self.center_on_screen()
        finally:
            self.setUpdatesEnabled(True)
        if persist:
            save_settings(self.settings)

    def changeEvent(self, event):
        """Keep the window mode in step with the title-bar maximize / restore button."""
        super().changeEvent(event)
        if event.type() != QEvent.WindowStateChange or not self.isVisible():
            return
        if self.windowState() & Qt.WindowMinimized:
            return
        wanted = "full" if self.isMaximized() else "compact"
        if wanted != theme.metrics().name:
            self.set_window_mode(wanted, persist=True, resize=False)

    def open_pc_report_dialog(self):
        try:
            index = self.tabs.indexOf(self.pc_report_tab_scroll)
            if index >= 0:
                self.tabs.setCurrentIndex(index)
            if hasattr(self, 'pc_report_widget'):
                self.pc_report_widget.on_run()
        except Exception as e:
            logger.error(f"Failed to start embedded PC Report: {e}")

    # -- command-line control (NVC.exe /E /R /S /X /C= /B=) -------------------

    def run_command_request(self, request):
        """Apply MRCmd-style switches to this running NVC.

        Returns (ok, message) for the caller's console and exit code. Steps run
        in the order preset, base name, record, stop, close; the first failure
        stops the run so `/C=Wrong /R` does not record with the old preset.
        """
        done = []
        for action, value in request.steps():
            ok, note = self._run_command_step(action, value)
            self.append_log(f"[command] /{action} {value or ''}: {note}".rstrip(), is_error=not ok)
            done.append(note)
            if not ok:
                return False, "; ".join(done)
        if request.launch:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            done.append("NVC brought to the front")
        return True, "; ".join(done) or "nothing to do"

    def _run_command_step(self, action, value):
        recorder = getattr(self, "multi_source_recorder_widget", None)
        if recorder is None:
            return False, "the recorder is not available"
        if action == "preset":
            return self._command_load_preset(recorder, value)
        if action == "base_name":
            recorder.base_name_edit.setText(value)
            return True, f"base name set to {value}"
        if action == "record":
            return self._command_start_recording(recorder)
        if action == "stop":
            if not self.is_recorder_recording():
                return True, "not recording; nothing to stop"
            recorder.stop_recording()
            return True, "recording stopped"
        if action == "close":
            if self.is_recorder_recording():
                recorder.stop_recording()
            # Deferred so the reply reaches the command-line process before the
            # event loop goes away.
            self._schedule(500, self.quit_application)
            return True, "NVC is closing"
        return False, f"unknown command {action}"

    def _command_load_preset(self, recorder, value):
        looks_like_path = value.lower().endswith(".json") or os.sep in value or "/" in value
        if looks_like_path:
            if not os.path.isfile(value):
                return False, f"preset file not found: {value}"
            recorder.apply_recorder_settings(load_recorder_settings(value))
            recorder.refresh_previews_from_sources()
            recorder.save_current_recorder_settings()
            return True, f"preset loaded from {value}"
        if not os.path.isfile(recorder.recorder_preset_path(value)):
            return False, f"preset not found: {value}"
        recorder.load_named_recorder_preset(value)
        return True, f"preset {value} loaded"

    def _command_start_recording(self, recorder):
        if self.locked:
            return False, "NVC is locked; unlock it before recording"
        if self.running or getattr(self, "is_converting", False):
            return False, "a conversion is running; recording cannot start"
        if self.is_recorder_recording() or recorder.status_label.text() == "Starting recording...":
            return True, "already recording"
        self.show_recorder_tab()
        recorder.start_recording()
        started = self.is_recorder_recording() or recorder.status_label.text() == "Starting recording..."
        if not started:
            return False, "recording did not start (check that a source is enabled)"
        self.update_single_workflow_availability()
        return True, "recording started"

    def show_recorder_tab(self):
        """Make the (optional) recorder tab visible and current."""
        scroll = getattr(self, "multi_source_recorder_tab_scroll", None)
        if scroll is None:
            return
        visible_tabs = self.settings.setdefault("visible_tool_tabs", {})
        if not visible_tabs.get("multi_source_recorder"):
            visible_tabs["multi_source_recorder"] = True
            self.apply_tool_tab_visibility()
        index = self.tabs.indexOf(scroll)
        if index >= 0:
            self.tabs.setCurrentIndex(index)
            self.on_tab_changed(index)

    def current_tool_tab_order(self):
        """Tool tab keys left to right as the bar shows them now."""
        widgets = getattr(self, 'tool_tab_widgets', {})
        by_widget = {widget: key for key, widget in widgets.items()}
        order = []
        for index in range(self.tabs.count()):
            key = by_widget.get(self.tabs.widget(index))
            if key is not None:
                order.append(key)
        return order

    def apply_tool_tab_order(self):
        """Arrange the tool tabs as saved in settings["tool_tab_order"]."""
        order = normalize_tool_tab_order(self.settings.get('tool_tab_order'))
        widgets = getattr(self, 'tool_tab_widgets', {})
        bar = self.tabs.tabBar()
        # QTabWidget follows the bar's tabMoved signal to move the page, so the
        # signal must stay live; a flag keeps _on_tab_moved from re-saving.
        self._applying_tab_order = True
        try:
            for target, key in enumerate(order):
                widget = widgets.get(key)
                current = self.tabs.indexOf(widget) if widget is not None else -1
                if current >= 0 and current != target:
                    bar.moveTab(current, target)
        finally:
            self._applying_tab_order = False

    def _on_tab_moved(self, _from_index, _to_index):
        if getattr(self, '_applying_tab_order', False):
            return
        order = self.current_tool_tab_order()
        if order and order != self.settings.get('tool_tab_order'):
            self.settings['tool_tab_order'] = order
            save_settings(self.settings)

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
                    self.drag_drop_overlay.setStyleSheet(theme.qss("""
                        QWidget { 
                            background: rgba(255, 255, 255, 0.5); 
                            border: 2px dashed $panel_border; 
                            $leaf
                            margin: 10px;
                        }
                        QWidget:hover {
                            border-color: $accent;
                            background: rgba(67, 162, 150, 0.1);
                        }
                    """, leaf=theme.leaf_radii(18)))
                else:
                    # Fully opaque overlay when idle and no log content
                    self.drag_drop_overlay.setStyleSheet(theme.qss("""
                        QWidget { 
                            background: white; 
                            border: 2px dashed $panel_border; 
                            $leaf
                            margin: 10px;
                        }
                        QWidget:hover {
                            border-color: $accent;
                            background: rgba(67, 162, 150, 0.1);
                        }
                    """, leaf=theme.leaf_radii(18)))
                # Hide the overlay text ONLY if conversion is running or after a drop
                if self.is_converting:
                    self.drag_drop_text.hide()
                # Always show the overlay (unless hidden by drop)
                self.drag_drop_overlay.show()

    def set_start_button_state(self, is_running):
        # Every stylesheet below is rendered from theme.skin(), so the skin has
        # to match the state we are about to draw *before* the first qss()
        # call. It used to be synced only afterwards (through update_icons in
        # the idle branch), which painted the button one state late: stopping
        # a recording left "Start Recording" in the active green.
        self._sync_theme_skin()
        if self.locked:
            self.start_button.setEnabled(False)
            self.start_button.setText(_tr("Locked"))
            # Modern grayscale style for locked state
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: $panel_alt_bg;
                    color: $grey_500;
                    border: 1px solid $separator;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """))
            self.start_button.setToolTip(_tr("Application is locked."))
            return
        recorder_mode = self.is_recorder_tab_active() and not is_running and not getattr(self, 'is_converting', False)
        recorder_recording = recorder_mode and self.is_recorder_recording()
        convert_block = (
            "" if self.is_recorder_tab_active()
            else blocked_reason(self.current_activity(), "convert")
        )
        if convert_block and not is_running:
            # Rule 2: a recording is active, so conversion may not start here.
            self.start_button.setEnabled(False)
            self.start_button.setText(_tr("Recording..."))
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: $panel_alt_bg;
                    color: $grey_500;
                    border: 1px solid $separator;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """))
            self.start_button.setToolTip(convert_block)
            return
        if self.is_recorder_tab_active() and getattr(self, 'is_converting', False) and not is_running and not recorder_recording:
            self.start_button.setEnabled(False)
            self.start_button.setText(_tr("Converting..."))
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: $panel_alt_bg;
                    color: $grey_500;
                    border: 1px solid $separator;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """))
            self.start_button.setToolTip(_tr("Recording is unavailable while conversion is running."))
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
            self.start_button.setText(_tr("Starting..."))
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: $panel_alt_bg;
                    color: $grey_500;
                    border: 1px solid $separator;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """))
            self.start_button.setToolTip(_tr("Releasing the camera preview before recording starts."))
            return
        if recorder_stopping:
            self.start_button.setEnabled(False)
            self.start_button.setText(_tr("Stopping..."))
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: $panel_alt_bg;
                    color: $grey_500;
                    border: 1px solid $separator;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    font-size: 10pt;
                }
            """))
            self.start_button.setToolTip(_tr("Finishing and saving the active recording."))
            return
        if is_running or recorder_recording:
            self.start_button.setText(
                _tr("Stop Recording") if recorder_mode else _tr("Stop"))
            # Update log display based on monitoring state
            self.update_log_display()
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $active_accent, stop:1 $active_accent_dark);
                    border: 1px solid $accent_dark;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    color: white;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $active_accent_bright, stop:1 $active_accent);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $active_accent_dark, stop:1 $accent_dark);
                }
            """))
            if recorder_mode:
                self.start_button.setToolTip(_tr("Stop the active multi-source recording."))
            else:
                self.start_button.setToolTip(_tr("Stop monitoring the source folder for files to convert."))
        else:
            self.start_button.setText(
                _tr("Start Recording") if recorder_mode else _tr("Start"))
            # Update log display based on monitoring state
            self.update_log_display()
            self.start_button.setStyleSheet(theme.qss("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent, stop:1 $accent_pressed);
                    border: 1px solid $accent_dark;
                    border-radius: 6px;
                    padding: 10px 20px;
                    min-width: 120px;
                    min-height: 36px;
                    font-weight: bold;
                    color: white;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_hover, stop:1 $accent);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_pressed, stop:1 $accent_dark);
                }
            """))
            if recorder_mode:
                self.start_button.setToolTip(_tr("Start recording from the enabled recorder sources."))
            else:
                self.start_button.setToolTip(_tr("Start monitoring the source folder for files to convert."))
        self.update_icons()
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
        self.set_start_button_state(is_running=self.running)
        self.update_status_labels()

    def recording_phase(self):
        """"", "starting", "recording", "stopping" or "failed" -- from the recorder."""
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        status_text = (
            recorder.status_label.text()
            if recorder is not None and hasattr(recorder, 'status_label')
            else ""
        )
        if status_text == "Starting recording...":
            return "starting"
        if status_text == "Stopping...":
            return "stopping"
        if self.is_recorder_recording():
            return "recording"
        if "failed" in status_text.lower():
            return "failed"
        return ""

    def current_activity(self):
        """What NVC is doing right now, for the workflow rules and the status line."""
        converting = int(self.queue.active_count)
        if not converting and getattr(self, 'is_converting', False):
            converting = 1
        return Activity(
            locked=bool(self.locked),
            recording_phase=self.recording_phase(),
            converting=converting,
            monitoring=bool(getattr(self, 'running', False)),
        )

    def footer_status_labels(self):
        names = (
            'status_label_log_tab',
            'status_label_pc_report_tab',
            'status_label_lossless_editor_tab',
            'status_label_multi_source_recorder_tab',
            'status_label_media_player_tab',
        )
        return [getattr(self, name) for name in names if getattr(self, name, None) is not None]

    def set_status_label(self, label, is_running=None):
        """Every footer shows the same line; `is_running` is kept for old callers."""
        label.setTextFormat(Qt.RichText)
        label.setText(status_markup(self.current_activity()))

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
            or self.queue.active_count > 0
            or self.is_recorder_recording()
        )

    def update_single_workflow_availability(self):
        """Apply the workflow rules (ui/workflow_rules.py) to every start control.

        Tabs are never disabled and nothing is stopped: a job that may not
        start now is greyed out with the reason as tooltip, that is all.
        """
        activity = self.current_activity()
        recorder = getattr(self, 'multi_source_recorder_widget', None)
        if recorder:
            # The recorder stays usable (previews, settings, devices) while a
            # conversion runs; only Start Recording is unavailable.
            recorder.setEnabled(True)
            record_block = blocked_reason(activity, "record")
            if hasattr(recorder, 'status_label') and not activity.recording:
                if record_block and not activity.locked:
                    recorder.status_label.setText(_tr("Unavailable while conversion is running"))
                elif "Unavailable" in recorder.status_label.text():
                    recorder.status_label.setText(_tr("Not recording"))
        editor = getattr(self, 'lossless_editor_widget', None)
        if editor is not None and hasattr(editor, 'set_blocked'):
            editor.set_blocked(blocked_reason(activity, "lossless_edit"))
        self.update_status_labels()
        if hasattr(self, 'start_button'):
            self.set_start_button_state(is_running=getattr(self, 'running', False))
        # The tab underline follows the conversion workflow (start/stop_conversion
        # call this); the recording workflow reaches the window only through here.
        if hasattr(self, 'tabs'):
            self.update_highlight_colors()

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
            button_style=getattr(self, 'current_button_style', None),
            settings=self.settings,
            save_settings=lambda: save_settings(self.settings),
            threadpool=self.threadpool,
        )
        if hasattr(widget, "apply_layout_mode"):
            widget.apply_layout_mode(theme.metrics())
        # The sidebar preview follows the player's selected clip, as it used to
        # follow the inspection tab. (Whether the sidebar preview stays at all is
        # an open backlog question.)
        widget.media_selected.connect(self._preview_player_selection)
        self.media_player_widget = widget
        placeholder = getattr(self, 'media_player_placeholder', None)
        if placeholder is not None:
            self.media_player_layout.removeWidget(placeholder)
            placeholder.deleteLater()
            self.media_player_placeholder = None
        self.tool_tab_cards["media_player"].body.insertWidget(0, widget)
        return widget

    def _preview_player_selection(self, path):
        if path and os.path.exists(path):
            self.preview_file(path)

    def play_in_media_player(self, path):
        """Converted Files -> Media Player: show the tab for this session and play `path`."""
        if not path or not os.path.exists(path):
            return
        widget = self._ensure_media_player_widget()
        self.show_media_player_tab()
        panel = widget.selected_panel()
        if panel.load_media(path):
            widget.play_all()

    def _on_tab_changed_for_layout_preview(self, _index=None):
        media_scroll = getattr(self, 'media_player_tab_scroll', None)
        if media_scroll is not None and self.tabs.currentWidget() is media_scroll:
            self._ensure_media_player_widget()
        if self._recorder_tab_is_active():
            self._show_recorder_layout_preview()
        elif self._showing_recorder_layout_preview:
            # Leaving the recorder tab: drop the schematic so a later file preview is clean.
            self._showing_recorder_layout_preview = False
            self._set_preview_placeholder()

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
        # Transparent canvas: the dashed leaf frame of the sidebar preview box
        # stays visible around the schematic, matching the other tabs' white look.
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            s = theme.skin()
            # Keep clear of the frame's 2 px dashed border.
            inset = 6
            area_w = max(1, width - 2 * inset)
            area_h = max(1, height - 2 * inset)
            # "Separate videos" are distinct files, so draw each tile inset with a gap;
            # "Combined grid" is one frame, so tiles sit flush. PiP draws insets on top.
            mode_text = (mode or "").strip().lower()
            gap = 4 if mode_text.startswith("separate") else 1
            accent = QColor(s.accent)
            font = QFont()
            font.setPixelSize(max(9, height // 7))
            font.setBold(True)
            painter.setFont(font)
            for order, (nx, ny, nw, nh) in enumerate(rects):
                x = inset + int(round(nx * area_w)) + gap
                y = inset + int(round(ny * area_h)) + gap
                w = max(1, int(round(nw * area_w)) - 2 * gap)
                h = max(1, int(round(nh * area_h)) - 2 * gap)
                is_pip_inset = mode_text.startswith("picture") and order > 0
                painter.setPen(QPen(accent, 2))
                painter.setBrush(QBrush(QColor(s.panel_alt_bg) if is_pip_inset else QColor(s.panel_bg)))
                painter.drawRoundedRect(x, y, w, h, 4, 4)
                painter.setPen(QPen(accent))
                painter.drawText(x, y, w, h, Qt.AlignCenter, str(order + 1))
        finally:
            painter.end()
        return pixmap

    def update_recorder_footer_status(self):
        """Kept for old callers: the recorder footer shows the shared status line."""
        self.update_status_labels()

    def update_status_labels(self):
        # One status line, the same on every tab (spec §7).
        for label in self.footer_status_labels():
            self.set_status_label(label)

        # When setting the lock icon label, always set fixed size and alignment
        self.lock_icon_label_log_tab.setPixmap(self.get_lock_icon_pixmap())
        self.lock_icon_label_log_tab.setFixedSize(36, 36)
        self.lock_icon_label_log_tab.setAlignment(Qt.AlignCenter)
        for lock_label in getattr(self, 'footer_lock_labels', []):
            lock_label.setPixmap(self.get_lock_icon_pixmap())
            lock_label.setFixedSize(36, 36)
            lock_label.setAlignment(Qt.AlignCenter)

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Always use teal logo for tray icon
        tray_icon_path = self.icon_color if os.path.exists(self.icon_color) else self.icon_gray
        self.tray_icon.setIcon(QIcon(tray_icon_path))
        self.tray_icon.setToolTip(_tr("Video Converter Application"))
        tray_menu = QMenu()
        show_action = tray_menu.addAction(_tr("Show"))
        show_action.triggered.connect(self.show_window)
        quit_action = tray_menu.addAction(_tr("Quit"))
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

    def _schedule(self, msec, callback):
        """Run `callback` after `msec`, but only while this widget lives.

        `QTimer.singleShot` is a static method, so the timer it creates belongs
        to nobody and still fires after this widget has been destroyed. The
        callback then touches a deleted C++ object and raises -- and an
        exception escaping a Qt slot makes PyQt call qFatal(), which aborts the
        process with no traceback. A QTimer parented to `self` is destroyed
        with `self`, so the callback is cancelled instead.
        """
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(msec)
        return timer

    def shutdown(self):
        self.running = False
        self.status_running = False
        self.hide()
        try:
            # Stops the ffmpeg process, the UI tick timer and the star field.
            self.preview.shutdown()
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
        try:
            pc_report = getattr(self, 'pc_report_widget', None)
            if pc_report and hasattr(pc_report, 'shutdown'):
                pc_report.shutdown()
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
        for worker in self.queue.workers():
            try:
                worker.cancel()
            except Exception:
                logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)
        try:
            self.threadpool.waitForDone(3000)
        except Exception:
            logger.debug("VideoConverterApp.shutdown: suppressed error", exc_info=True)

    def check_updates(self):
        """Check for an update in the background, if a source is configured.

        Skipped entirely when it is not, rather than starting a thread to
        reach a placeholder URL.
        """
        from utils import update_checker

        if not update_checker.is_configured():
            logger.info("Update checking is not configured; not starting the "
                        "background check.")
            return
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_thread = UpdateWorker(self.update_checker)
        self.update_thread.start()

    def on_update_available(self, version, url):
        self.update_url = url
        self.update_label.setText(_tr("Update v%(version)s Available!")
                                  % {"version": version})
        self.update_label.setToolTip(_tr("Click to download update"))
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
                self._schedule(80, do_wiggle)  # Fast wiggle every 80ms

            do_wiggle()
        except Exception:
            logger.debug("VideoConverterApp._wiggle_converted_tab: suppressed error", exc_info=True)

    def _show_locked_dialog(self):
        """Consistent locked dialog with grayscale styling and wiggle before/after."""
        try:
            self._wiggle_lock_icon()
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Information)
            dlg.setWindowTitle(_tr("Locked"))
            dlg.setText(_tr("The application is locked. Unlock to change settings."))
            info_icon_path = resource_path('graphics/GRAYSCALEINFO.ico')
            if os.path.exists(info_icon_path):
                dlg.setWindowIcon(QIcon(info_icon_path))
                dlg.setIconPixmap(QPixmap(info_icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            elif os.path.exists(getattr(self, 'icon_gray', '')):
                dlg.setWindowIcon(QIcon(self.icon_gray))
            dlg.setStyleSheet(theme.qss("""
                QMessageBox { background: $grey_100; }
                QLabel { color: $grey_650; }
                QPushButton {
                    background: $separator;
                    border: 1px solid $grey_300;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: $grey_700;
                }
                QPushButton:hover { background: $grey_240; }
            """))
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
            reason = blocked_reason(self.current_activity(), "convert")
            if reason:
                logger.info("toggle_process branch=blocked reason=%s", reason)
                self.append_log(reason, is_error=True)
                self.set_start_button_state(is_running=False)
                return
            logger.info("toggle_process branch=start_conversion")
            self.start_conversion()
            self.set_start_button_state(is_running=True)

    def start_conversion(self):
        if self.is_recorder_recording():
            self.append_log("Cannot start conversion while recording is active.", is_error=True)
            return
        if not (os.path.exists(self.source_folder) and os.path.exists(self.destination_folder)):
            logger.info("Source or Destination folder is missing.")
            self.append_log("Source or Destination folder is missing.", is_error=True)
            QMessageBox.critical(self, _tr("Missing Folders"), _tr("Please select valid Source and Destination folders."))
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

    def scan_existing_files(self):
        for filename in os.listdir(self.source_folder):
            file_path = os.path.join(self.source_folder, filename)
            ext = os.path.splitext(file_path)[1].lower()
            if os.path.isfile(file_path) and ext in SUPPORTED_FORMATS:
                # Add to queue as 'queued' before starting conversion
                self.converted_files_widget.add_queued_file(os.path.basename(file_path), self.destination_folder)
                self.convert_file(file_path)

    def get_icon_path(self, icon_name):
        """Resolve an icon for the current lock/activity state.

        The GRAYSCALE / GREEN / unprefixed naming in graphics/ is the theme's
        icon_prefix, so this just syncs the skin and asks theme.menu_icon.
        (It used to log at INFO on every lookup, which update_icons calls in a
        loop -- that is now debug.)
        """
        self._sync_theme_skin()
        path = theme.menu_icon(icon_name)
        logger.debug("Icon %s in %s skin: %s", icon_name, theme.skin().name, path)
        return path

    def _sync_theme_skin(self):
        """Point the theme at the skin matching the app's current state."""
        return theme.theme_manager.set_state(
            locked=bool(getattr(self, 'locked', False)),
            active=bool(self.is_active_workflow_visual_state()),
        )

    # ────────────────────────────────────────────────────────────────
    # BallBuster XT helper (intro + delayed launch)
    # ────────────────────────────────────────────────────────────────
    def _play_ballbuster_intro(self):
        """Display ASCII art title and launch the game after 3-second pause."""
        # Ensure log tab is visible so user can read the banner
        try:
            if hasattr(self, 'tabs'):
                self.tabs.setCurrentWidget(self.converter_tab_scroll)  # the log lives on the Video Converter tab
                # Mimic drag-drop behaviour: hide instruction text
                if hasattr(self, 'drag_drop_text'):
                    self.drag_drop_text.hide()
                if hasattr(self, 'drag_drop_overlay'):
                    # Light translucent background
                    self.drag_drop_overlay.setStyleSheet(theme.qss("""
                        QWidget {
                            background: rgba(255, 255, 255, 0.5);
                            border: 2px dashed $panel_border;
                            $leaf
                            margin: 10px;
                        }
                    """, leaf=theme.leaf_radii(18)))
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
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        self._schedule(3000, self.launch_ballbuster_game)

    def get_game_icon_path(self):
        """The controller-circle icon for the current lock/activity state."""
        self._sync_theme_skin()
        return theme.menu_icon('GAME')

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
            label.setToolTip(_tr('Play BallBuster XT'))
            # Match visual style of other circular footer icons
            label.setStyleSheet(theme.qss("""
                QLabel {
                    background: transparent;
                    border: none;
                    padding: 4px;
                }
                QLabel:hover {
                    background: $inner_border;
                    border-radius: 18px;
                }
            """))
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
        elif hasattr(self, 'burger_button'):
            # Debug: log when burger icon path doesn't exist
            logger.info(f"Burger icon path not found: {burger_icon_path}")
            # Fallback to grayscale burger if path doesn't exist
            fallback_path = resource_path('graphics/GRAYSCALEBURGER.ico')
            if os.path.exists(fallback_path):
                fallback_icon = QIcon(QPixmap(fallback_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.burger_button.setIcon(fallback_icon)
        # Broom (log tab)
        broom_icon_path = self.get_icon_path('BROOM')
        if os.path.exists(broom_icon_path):
            broom_pixmap = QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            for broom_label in getattr(self, 'footer_broom_labels', []):
                broom_label.setPixmap(broom_pixmap)
        if hasattr(self, 'broom_label_log_tab') and os.path.exists(broom_icon_path):
            self.broom_label_log_tab.setPixmap(QPixmap(broom_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        # Lock/Unlock (log tab)
        for lock_label in getattr(self, 'footer_lock_labels', []):
            lock_label.setPixmap(self.get_lock_icon_pixmap())
        if hasattr(self, 'lock_icon_label_log_tab'):
            self.lock_icon_label_log_tab.setPixmap(self.get_lock_icon_pixmap())
        # Update game controller icons
        self.update_game_icons()
        # File icon (normal mode footers)
        for file_label in getattr(self, 'footer_file_labels', []):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                file_label.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, 'file_label_log_tab'):
            file_icon_path = self.get_icon_path('FILE')
            if os.path.exists(file_icon_path):
                self.file_label_log_tab.setPixmap(QPixmap(file_icon_path).scaled(36, 36, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
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
                self.queue.queue_manual(path)
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
            _tr("Convert Media Files"),
            _tr("Do you wish to convert %(what)s according to settings?")
            % {"what": label},
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            return False
        if not self.settings.get('dont_show_drop_dialog', False):
            dont_show_reply = QMessageBox.question(
                self,
                _tr("Don't Show Again"),
                _tr("Don't show me this dialog again?"),
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
            QMessageBox.warning(
                self, _tr("Unsupported Files"),
                _tr("No supported video files found in:\n%(paths)s")
                % {"paths": unsupported_list})
            logger.info(f"No supported files found in dropped paths:\n{unsupported_list}")
            return

        if not self._confirm_dropped_conversion(len(valid_paths), show_dialog):
            return

        self.preview_file(valid_paths[0])
        for file_path in valid_paths:
            self.converted_files_widget.add_queued_file(os.path.basename(file_path), self.destination_folder)
            if self.locked:
                self.queue.queue_manual(file_path)
            else:
                self.convert_file(file_path, force=True)
        if self.locked:
            self.append_log("Files queued while locked. Unlock and start conversion to process them.")

    def convert_file(self, file_path, force=False):
        """Start the conversion process for a single file."""
        file_path = self.queue.normalize(file_path)

        # The four admission rules now live in ConversionQueueState.admit,
        # which is unit-tested; this method keeps only the UI response to each.
        verdict = self.queue.admit(
            file_path,
            locked=bool(self.locked),
            running=bool(self.running),
            force=force,
            within_allowed_time=is_within_allowed_time(self.settings),
        )
        if verdict is Admission.LOCKED:
            self._wiggle_lock_icon()
            logger.info("Conversion attempt blocked while locked.")
            return
        if verdict is Admission.DUPLICATE:
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
        if verdict is Admission.NOT_RUNNING:
            logger.info(f"Received file {file_path} but conversion is not running. Ignoring.")
            self.append_log(f"Received file {file_path} but conversion is not running. Ignoring.")
            return
        if verdict is Admission.OUTSIDE_TIME:
            logger.info(f"Current time outside allowed range. Skipping {file_path}.")
            self.append_log(f"Current time outside allowed range. Skipping {file_path}.")
            return
        # Update status to 'processing' in the queue
        self.converted_files_widget.update_file_status(os.path.basename(file_path), 'processing')
        self.queue.start(file_path)
        self.is_converting = self.queue.is_converting
        self.update_single_workflow_availability()
        # Ensure start/stop button switches to green while conversion is active
        self.set_start_button_state(is_running=True)
        self.update_icons()
        self.update_status_labels()  # Update status when conversion starts
        self.update_log_display()  # Update log display to show console during conversion
        worker_signals = WorkerSignals()

        def per_file_log_handler(msg):
            # Route through LogBus to keep UI responsive and resilient across tab switches
            try:
                self.log_bus.append(msg)
            except Exception:
                self.append_log(msg)
            self.queue.log_line(file_path, msg)

        worker_signals.log.connect(per_file_log_handler)
        worker_signals.conversion_complete.connect(self.handle_conversion_complete)
        from conversion.worker import ConversionWorker
        worker = ConversionWorker(file_path, self.settings, worker_signals)
        self.queue.start(file_path, worker)
        self.threadpool.start(worker)

    def _process_manual_queue(self):
        """Convert any files queued while idle once monitoring starts."""
        pending = self.queue.take_manual()
        if not pending:
            return
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
        # Buffered log lines come back with the conversion, keyed on the
        # source path. This used to be matched by basename below, so two
        # files called clip.mov in different folders wrote each other's log.
        log_lines = self.queue.finish(source_file) if source_file else []
        # Update status to 'success' or 'failure' in the queue
        self.converted_files_widget.update_file_status(output_file_name, 'success' if success else 'failure')
        self.converted_files_widget.file_converted_signal.emit(output_file_name, deletion_info, self.destination_folder, success)
        # Write the per-file log, if this conversion produced any lines.
        if log_lines:
            log_folder = log_dir(self.settings)
            try:
                os.makedirs(log_folder, exist_ok=True)
                log_path = os.path.join(log_folder, output_file_name + '.txt')
                with open(log_path, 'w', encoding='utf-8') as f:
                    for line in log_lines:
                        f.write(line + chr(10))
            except OSError:
                logger.exception("Could not write the per-file log for %s.",
                                 output_file_name)
        if success:
            self.append_log("Conversion complete!", is_error=False)
            # Wiggle the Converted Files tab to draw attention
            self._wiggle_converted_tab()
        else:
            self.append_log("Conversion failed!", is_error=True)
        # queue.finish() above already removed it, and the count derives
        # from the in-flight set, so it cannot drift or go negative.
        self.is_converting = self.queue.is_converting
        self.update_single_workflow_availability()
        # If monitoring is not running and all conversions have finished, restore button style
        if not self.running and not self.is_converting:
            self.set_start_button_state(is_running=False)
        self.update_icons()  # Update logo after conversion
        self.update_status_labels()  # Update status when conversion finishes
        self.update_log_display()  # Update log display after conversion completes

    def _add_language_menu(self, parent_menu):
        """Add a Language submenu, unless only one language is available.

        Draft translations are hidden unless NVC_I18N_PREVIEW=1, so unreviewed
        strings do not reach a user who did not ask to see them.
        """
        from utils import localization

        codes = localization.selectable_locales()
        if len(codes) < 2:
            return

        current = localization.saved_locale()
        submenu = parent_menu.addMenu(_tr("Language"))
        group = QActionGroup(submenu)
        group.setExclusive(True)
        for code in codes:
            spec = localization.locale_spec(code)
            label = spec.native_name
            if spec.review_status != "production":
                label = _tr("%(language)s (draft)") % {"language": spec.native_name}
            action = submenu.addAction(label)
            action.setCheckable(True)
            action.setChecked(code == current)
            group.addAction(action)
            action.triggered.connect(
                lambda _checked, c=code: self._choose_language(c))

    def _choose_language(self, code):
        """Save the chosen language and say when it will take effect."""
        from utils import localization

        if code == localization.saved_locale():
            return
        localization.save_locale(code)
        spec = localization.locale_spec(code)
        logger.info("Language set to %s; takes effect on next start.", code)
        QMessageBox.information(
            self, _tr("Language"),
            localization.language_restart_message(spec.native_name))

    def show_info(self):
        dialog = InfoDialog(self, is_converting=self.running, button_style=getattr(self, 'current_button_style', None))
        self.center_dialog(dialog)
        dialog.exec_()

    def open_help_document(self):
        # Prefers the generated manual from docs/help (see
        # utils/help_resolution.py) and falls back to the legacy hand-written
        # help_document.pdf/.html when no generated one has been shipped.
        from utils.help_resolution import resolve_help_document
        from utils.localization import saved_locale
        help_path = resolve_help_document(saved_locale())
        if help_path is not None:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            logger.info(f"Opening help document {help_path.name}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(help_path)))
        else:
            logger.warning("No help document found in docs/help or alongside the app.")
            QMessageBox.warning(
                self, _tr("Help Document Not Found"),
                _tr("The help document could not be found.\n\n"
                "Build it with:\n"
                "  python docs/help/source/build_help_docs.py"))

    def open_source_folder_in_explorer(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        if not self.source_folder or not os.path.exists(self.source_folder):
            QMessageBox.warning(self, _tr("Folder Not Found"), _tr("Source folder path does not exist."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.source_folder))

    def open_destination_folder_in_explorer(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        if not self.destination_folder or not os.path.exists(self.destination_folder):
            QMessageBox.warning(self, _tr("Folder Not Found"), _tr("Destination folder path does not exist."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.destination_folder))

    def open_backup_folder_in_explorer(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        if not self.backup_folder or not os.path.exists(self.backup_folder):
            QMessageBox.warning(self, _tr("Folder Not Found"), _tr("Backup folder path does not exist."))
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
        self.converted_files_widget.set_log_folder(log_dir(self.settings))
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

        # Maximize/restore is always offered: it is how Full window mode is
        # brought back to a manageable size (changeEvent keeps the mode in sync).
        base_flags = (Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint
                      | Qt.WindowMaximizeButtonHint)
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
            self.central_widget.setStyleSheet(theme.qss("background-color: $separator;"))
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.central_widget.setStyleSheet("")

    def drag_drop_widget_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # Show overlay with drop styling
            self.drag_drop_overlay.setStyleSheet(theme.qss("""
                QWidget { 
                    background: rgba(67, 162, 150, 0.1); 
                    border: 2px solid $accent; 
                    $leaf
                    margin: 10px;
                }
            """, leaf=theme.leaf_radii(18)))
            self.drag_drop_overlay.show()
            # Keep instruction consistent while hovering
            self.drag_drop_text.setText(_tr("Drag and drop media files here\nor select source folder to start monitoring and converting"))
        else:
            event.ignore()

    def drag_drop_widget_drag_leave(self, event):
        # Restore appropriate styling based on current state
        has_log_content = len(self.console_output.toPlainText().strip()) > 0
        if self.running or self.is_converting or has_log_content:
            self.drag_drop_overlay.setStyleSheet(theme.qss("""
                QWidget { 
                    background: rgba(255, 255, 255, 0.5); 
                    border: 2px dashed $panel_border; 
                    $leaf
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: $accent;
                    background: rgba(67, 162, 150, 0.1);
                }
            """, leaf=theme.leaf_radii(18)))
        else:
            self.drag_drop_overlay.setStyleSheet(theme.qss("""
                QWidget { 
                    background: white; 
                    border: 2px dashed $panel_border; 
                    $leaf
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: $accent;
                    background: rgba(67, 162, 150, 0.1);
                }
            """, leaf=theme.leaf_radii(18)))
        # Always reset to default instruction after drag leave
        self.drag_drop_text.setText(_tr("Drag and drop media files here\nor select source folder to start monitoring and converting"))
        # Always show the overlay
        self.drag_drop_overlay.show()

    def drag_drop_widget_drop(self, event):
        # Restore appropriate styling based on current state
        has_log_content = len(self.console_output.toPlainText().strip()) > 0
        if self.running or self.is_converting or has_log_content:
            self.drag_drop_overlay.setStyleSheet(theme.qss("""
                QWidget { 
                    background: rgba(255, 255, 255, 0.5); 
                    border: 2px dashed $panel_border; 
                    $leaf
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: $accent;
                    background: rgba(67, 162, 150, 0.1);
                }
            """, leaf=theme.leaf_radii(18)))
        else:
            self.drag_drop_overlay.setStyleSheet(theme.qss("""
                QWidget { 
                    background: white; 
                    border: 2px dashed $panel_border; 
                    $leaf
                    margin: 10px;
                }
                QWidget:hover {
                    border-color: $accent;
                    background: rgba(67, 162, 150, 0.1);
                }
            """, leaf=theme.leaf_radii(18)))
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
        """The converter footer's broom: empty the file list and the log together."""
        table = getattr(self, "converted_files_widget", None)
        if table is not None:
            table.clear_table()
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
        self._set_preview_placeholder()
    def clear_pc_report_tab(self, event=None):
        widget = getattr(self, 'pc_report_widget', None)
        if widget and hasattr(widget, 'output'):
            widget.output.clear()
            if hasattr(widget, 'status_label'):
                widget.status_label.setText(_tr("Ready. Reports are saved to your Desktop by default."))

    def clear_lossless_editor_tab(self, event=None):
        widget = getattr(self, 'lossless_editor_widget', None)
        if widget and hasattr(widget, 'log_output'):
            widget.log_output.clear()

    def clear_multi_source_recorder_tab(self, event=None):
        widget = getattr(self, 'multi_source_recorder_widget', None)
        if widget:
            widget.log_lines = []
            if hasattr(widget, 'status_label'):
                widget.status_label.setText(_tr("Not recording"))

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
        upload_action = menu.addAction(_tr("Upload"))
        clear_action = menu.addAction(_tr("Clear Log"))
        menu.addSeparator()
        settings_action = menu.addAction(_tr("Settings"))
        menu.addSeparator()
        copy_action = menu.addAction(_tr("Copy"))
        select_all_action = menu.addAction(_tr("Select All"))
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

    def set_menu_icons(self):
        # Update burger icon for locked/unlocked state if desired (optional)
        pass

    def check_for_updates(self):
        """Report the update state honestly, including "not configured".

        This used to hardcode `latest_version = "2.3.0"` and compare it with a
        string comparison, so it always announced a fake update and offered to
        open https://example.com/nvc/downloads. See utils/update_checker.py for
        how to enable real checking.
        """
        from utils import update_checker

        if not update_checker.is_configured():
            QMessageBox.information(
                self, _tr("Updates Not Configured"),
                _tr("This build cannot check for updates: no update source has "
                    "been set.\n\nYou are running version %(version)s.")
                % {"version": APP_VERSION})
            return

        checker = update_checker.UpdateChecker()
        checker.update_available.connect(self._prompt_for_update)
        checker.no_update.connect(
            lambda: QMessageBox.information(
                self, _tr("No Updates"),
                _tr("You are running the latest version.")))
        checker.error_occurred.connect(
            lambda message: QMessageBox.warning(
                self, _tr("Update Check Failed"),
                _tr("Could not check for updates:\n%(error)s")
                % {"error": message}))
        checker.check_for_updates()

    def _prompt_for_update(self, version, url):
        reply = QMessageBox.question(
            self,
            _tr("Update Available"),
            _tr("A new version (%(version)s) is available.\n\n"
                "Do you want to visit the download page?")
            % {"version": version},
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(url))

    def update_all_button_styles(self):
        """Restyle the primary buttons for the current lock/activity state.

        Was three near-identical hardcoded gradient stylesheets chosen by an
        if/elif; the skin now carries the colours. See ui/theme.py.
        """
        self._sync_theme_skin()
        self.current_button_style = theme.gradient_button_style()

        # Apply the style to all QPushButton widgets in the application
        self.apply_button_style_to_all_widgets(self)
        if hasattr(self, 'pc_report_widget'):
            self.pc_report_widget.update_button_style(
                self.current_button_style,
                converting=bool(self.running or getattr(self, 'is_converting', False)),
                locked=bool(getattr(self, 'locked', False))
            )
        # Compact / link / icon tiers opt out of the gradient traversal above,
        # so they re-derive their own colours from the skin here.
        for widget in self.reskin_widgets():
            widget.reskin()

    def reskin_widgets(self):
        """Tool widgets and tab cards that carry skin-derived styles of their own."""
        candidates = [
            getattr(self, "lossless_editor_widget", None),
            getattr(self, "media_player_widget", None),
            getattr(self, "multi_source_recorder_widget", None),
            getattr(self, "converted_files_widget", None),
            getattr(self, "converter_header", None),
        ] + list(getattr(self, "tool_tab_cards", {}).values())
        return [w for w in candidates if w is not None and hasattr(w, "reskin")]

    def tab_headers(self):
        """The shared TabHeader at the top of each tool tab, keyed like tool_tab_widgets."""
        headers = {}
        for key, widget in getattr(self, "tool_tab_widgets", {}).items():
            if key == "video_converter":
                headers[key] = self.converter_header
                continue
            header = widget.findChild(TabHeader)
            if header is not None:
                headers[key] = header
        return headers

    def apply_button_style_to_all_widgets(self, widget):
        """Apply the current button style beneath `widget`.

        The traversal lives in theme.apply_to_buttons now, shared with
        SettingsDialog. Buttons keep their own look by setting the
        skipGlobalStyle property rather than by this method knowing their
        names.
        """
        return theme.apply_to_buttons(widget, self.current_button_style)

    def eventFilter(self, obj, event):
        """Event filter to handle mouse events on the drag drop overlay and video preview."""
        overlay = getattr(self, 'drag_drop_overlay', None)
        if overlay is not None and obj == overlay:
            if event.type() == QEvent.Enter:
                # Mouse entered the overlay - show hover effect (keep dashed border)
                self.drag_drop_overlay.setStyleSheet(theme.qss("""
                    QWidget { 
                        background: rgba(67, 162, 150, 0.1); 
                        border: 2px dashed $accent; 
                        $leaf
                        margin: 10px;
                    }
                """, leaf=theme.leaf_radii(18)))
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
        elif obj in tuple(x for x in (getattr(self, 'converter_tab_scroll', None), getattr(self, 'log_container', None)) if x):
            if event.type() == QEvent.Wheel:
                from PyQt5.QtWidgets import QApplication
                QApplication.sendEvent(self.console_output, event)
                return True

        # Preview hover is handled by PreviewController's own event filter.
        return super().eventFilter(obj, event)

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

    # ------------------------------------------------------------------
    # Sidebar preview. The implementation lives in PreviewController; these
    # keep the previous attribute and method names working, so call sites and
    # tests did not have to change with the extraction.
    # ------------------------------------------------------------------
    @property
    def preview_container(self):
        return self.preview.preview_container

    @property
    def preview_label(self):
        return self.preview.preview_label

    @property
    def preview_scrubber(self):
        return self.preview.preview_scrubber

    @property
    def play_pause_btn(self):
        return self.preview.play_pause_btn

    @property
    def overlay_container(self):
        return self.preview.overlay_container

    @property
    def preview_source_path(self):
        return self.preview.preview_source_path

    @preview_source_path.setter
    def preview_source_path(self, value):
        self.preview.preview_source_path = value

    @property
    def preview_playing(self):
        return self.preview.preview_playing

    @preview_playing.setter
    def preview_playing(self, value):
        self.preview.preview_playing = value

    @property
    def preview_seek_seconds(self):
        return self.preview.preview_seek_seconds

    @preview_seek_seconds.setter
    def preview_seek_seconds(self, value):
        self.preview.preview_seek_seconds = value

    @property
    def preview_frame_index(self):
        return self.preview.preview_frame_index

    @preview_frame_index.setter
    def preview_frame_index(self, value):
        self.preview.preview_frame_index = value

    @property
    def preview_duration_sec(self):
        return self.preview.preview_duration_sec

    @preview_duration_sec.setter
    def preview_duration_sec(self, value):
        self.preview.preview_duration_sec = value

    def toggle_preview_playback(self):
        return self.preview.toggle_preview_playback()

    def update_preview_controls_style(self):
        return self.preview.update_preview_controls_style()

    def _set_preview_placeholder(self, text=None):
        return self.preview._set_preview_placeholder(text)

    def _clear_preview_display(self):
        return self.preview._clear_preview_display()

    def _stop_preview_process(self):
        return self.preview._stop_preview_process()

    def _start_preview_process(self, file_path, seek_seconds=0.0):
        return self.preview._start_preview_process(file_path, seek_seconds)

    def _probe_duration_seconds(self, file_path):
        return self.preview._probe_duration_seconds(file_path)

    def _generate_and_show_thumbnail(self, file_path):
        return self.preview._generate_and_show_thumbnail(file_path)

    def _render_frame_at(self, file_path, seconds):
        return self.preview._render_frame_at(file_path, seconds)

    def _start_star_field(self, theme_name=None):
        return self.preview._start_star_field(theme_name)

    def _stop_star_field(self):
        return self.preview._stop_star_field()

    def update_highlight_colors(self):
        """
        Update the tab underline color based on monitoring state and lock state.
        """
        self._sync_theme_skin()
        highlight = theme.highlight_color()

        if hasattr(self, 'tabs'):
            self.apply_tab_style(highlight)
        self.update_preview_controls_style()

    def apply_tab_style(self, highlight):
        """Tab bar QSS for the current window mode with the given underline colour."""
        m = theme.metrics()
        self.tabs.setStyleSheet(self.tab_stylesheet_template.format(
            highlight=highlight, tab_min=m.tab_min_w, tab_pad=m.tab_padding,
            tab_font=m.tab_font_pt))

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
                self.queue.queue_manual(path)
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
                        _tr("Convert Media File"),
                        _tr("Do you wish to convert media file according to settings?"),
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.No:
                        continue
                    if not self.settings.get('dont_show_drop_dialog', False):
                        dont_show_reply = QMessageBox.question(
                            self,
                            _tr("Don't Show Again"),
                            _tr("Don't show me this dialog again?"),
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
            QMessageBox.warning(
                self, _tr("Unsupported Files"),
                _tr("The following files are not supported:\n%(paths)s")
                % {"paths": unsupported_list})
            logger.info(f"Unsupported files selected:\n{unsupported_list}")

    def inspect_in_media_player(self, path):
        """Converted Files -> Media Player: load `path` into the selected panel with the Inspect dock open."""
        if not path or not os.path.exists(path):
            return
        widget = self._ensure_media_player_widget()
        self.show_media_player_tab()
        widget.selected_panel().load_media(path)
        widget.inspect_btn.setChecked(True)

    def show_media_player_tab(self):
        self._show_tool_tab_for_session(self.media_player_tab_scroll)

    def _show_tool_tab_for_session(self, tab_widget):
        """Reveal and raise a tool tab without changing the saved visibility setting."""
        index = self.tabs.indexOf(tab_widget)
        if index < 0:
            return
        try:
            self.tabs.setTabVisible(index, True)
        except AttributeError:
            tab_widget.setVisible(True)
        self.tabs.setCurrentIndex(index)

    # --- Video Converter list: right-click feeds ------------------------------
    def monitor_folder_from_menu(self, folder):
        """Right-click "Monitor ..." on the file list; "" means ask which folder."""
        if not folder:
            folder = QFileDialog.getExistingDirectory(
                self, _tr("Choose the folder to monitor"), self.source_folder or ""
            )
            if not folder:
                return
        self.set_monitored_folder(folder)

    def set_monitored_folder(self, folder):
        """Save `folder` as the source folder; a running watch moves over to it."""
        self.update_settings({"source_folder": folder})
        self.append_log(f"Monitoring folder set to: {folder}")
        if self.running:
            self.stop_conversion()
            self.start_conversion()

    def open_file_in(self, target, path):
        """Right-click "Open in" on the file list."""
        if not path or not os.path.exists(path):
            return
        if target == "media_player":
            self.play_in_media_player(path)
        elif target == "lossless_editor":
            self.lossless_editor_widget.input_edit.setText(path)
            self._show_tool_tab_for_session(self.lossless_editor_tab_scroll)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def launch_ballbuster_game(self):
        if hasattr(self, 'ballbuster_widget') and self.ballbuster_widget is not None:
            return # Game already running

        from ui.extras import BallBusterWidget

        # The game names its palettes 'teal' / 'green' / 'gray'; the theme
        # translates. This was a seventh copy of the locked/active/idle chain,
        # in a local called `theme` that shadowed the theme module itself.
        self._sync_theme_skin()
        skin_name = theme.legacy_skin_name()

        # The star field follows the current skin on its own now.
        self._start_star_field()

        self.log_container.hide()
        self.hide_files_table_for_game()

        self.ballbuster_widget = BallBusterWidget(theme=skin_name)
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
        # The tab header belongs to the game while it runs.
        self.converter_header.set_heading(
            "balls",
            _tr("BallBuster XT"),
            _tr("Fling balls at other balls until the balls are gone. Video conversion "
                "has been temporarily postponed in the name of science."),
        )
        # Update status label to Gaming
        self.status_label_log_tab.setText(_tr("Status: Gaming <font color='#43a296'>●</font>"))

        # Transform Start button into Exit Game
        try:
            self.start_button.clicked.disconnect()
        except Exception:
            logger.debug("launch_ballbuster_game: suppressed error", exc_info=True)
        # Ensure the button is clickable even in locked (gray) mode
        self.start_button.setEnabled(True)
        self.start_button.setText(_tr("Exit Game"))
        self.start_button.setToolTip(_tr("Click to exit the Easter Egg and return to the log view."))
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
        self.restore_files_table_after_game()
        self.log_tab_footer_widget.show()
        self.converter_header.set_heading(
            "convert",
            _tr("Video Converter"),
            _tr("Drop files or monitor a folder; converted files are listed above the log."),
        )
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
