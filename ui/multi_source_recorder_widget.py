import glob
import os
import re
import threading
import time
from datetime import datetime

from PyQt5 import sip
from PyQt5.QtCore import QCoreApplication, QProcess, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from conversion.hardware_encoders import looks_like_encoder_failure, probe_hardware_h264_encoder
from conversion.ptz_controls import (
    axis_vapix_continuous_url,
    axis_vapix_ptz_url,
    parse_axis_ptz_presets,
    send_axis_vapix_request,
)
from conversion.recorder_settings import (
    list_recorder_presets,
    load_recorder_settings,
    normalize_recorder_settings,
    preset_file_path,
    safe_preset_name,
    save_recorder_settings,
)
from conversion.recording_commands import (
    build_combined_grid_record_command,
    build_directshow_camera_settings_command,
    build_directshow_list_options_command,
    build_directshow_preview_stream_command,
    build_directshow_record_with_preview_command,
    build_preview_stream_command,
    build_record_command,
    recording_layout_preview_rects,
    screen_gdi_fallback_source,
)
from conversion.recording_sources import (
    CAMERA_SOURCE_TYPES,
    SCREEN_DEFAULT_TARGET,
    SCREEN_MONITOR_PREFIX,
    DeviceScan,
    apply_axis_rtsp_recording_options,
    axis_mjpeg_preview_url,
    build_region_source_value,
    build_rtsp_url,
    build_source_text,
    discover_directshow_devices,
    discover_directshow_video_devices,
    is_hidden_directshow_video_device,
    list_capture_windows,
    parse_directshow_video_options,
    parse_rtsp_url_settings,
    screen_monitor_index,
    screen_region,
    stream_host_problem,
    terminate_device_probes,
)
from ui import theme
from ui.glyph_icons import make_icon_button, reskin_icon_buttons, set_link_glyph
from ui.screen_region_picker import pick_screen_region_value
from utils.file_naming import get_unique_path
from utils.logger import logger
from utils.resources import resource_path


def _tr(source: str) -> str:
    """Translate this module's strings under the stable "Recorder" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("Recorder", source)

def make_sync_offset_spinbox():
    # Compact per-source timeline nudge used to line cameras up in Combined grid.
    # Positive delays the source, negative pulls it earlier; this compensates for a
    # constant capture-latency difference (e.g. a GigE camera buffering behind a
    # USB webcam) that timestamp handling alone cannot remove.
    spin = QDoubleSpinBox()
    spin.setRange(-10.0, 10.0)
    spin.setSingleStep(0.05)
    spin.setDecimals(2)
    spin.setValue(0.0)
    spin.setSuffix(_tr(" s"))
    spin.setMaximumWidth(74)
    spin.setToolTip(
        _tr("Sync offset for Combined grid and Picture-in-picture: shift this source earlier "
        "(negative) or later (positive) to line it up with the others.")
    )
    return spin


class SourceComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.setEditable(True)

    def text(self):
        return self.currentText()

    def setText(self, text):
        if self.findText(text) < 0 and text:
            self.addItem(text)
        self.setCurrentText(text)

    def setPlaceholderText(self, text):
        if self.lineEdit():
            self.lineEdit().setPlaceholderText(text)

    def placeholderText(self):
        return self.lineEdit().placeholderText() if self.lineEdit() else ""

    def set_options(self, options, auto_select=True):
        """Replace the drop-down entries, keeping the typed text.

        `auto_select=False` leaves an empty field empty: a scan landing seconds
        after the user picked "USB camera" must not quietly fill in a camera.
        """
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItems(options)
        fallback = options[0] if (options and auto_select) else ""
        self.setCurrentText(current if current else fallback)
        self.blockSignals(False)

    def options(self):
        return [self.itemText(i) for i in range(self.count())]


VIDEO_DEVICE_PLACEHOLDERS = {
    "No source selected...",
    "RTSP/IP Camera",
    "Refresh USB devices...",
    "Select video device...",
}
# The Video Settings device list offers one "Screen capture" entry next to the
# cameras; what it captures is chosen in its settings (the gear), the way an RTSP
# camera's address is. The configured capture then shows as one of these labels.
SCREEN_CAPTURE_DEVICE_LABEL = "Screen capture"
SCREEN_DESKTOP_DEVICE_LABEL = "Screen capture (desktop)"
SCREEN_MONITOR_DEVICE_LABEL = "Screen capture (monitor %(number)d, GPU)"
_SCREEN_MONITOR_LABEL_PATTERN = re.compile(r"^Screen capture \(monitor (\d+), GPU\)$")
SCREEN_REGION_DEVICE_LABEL = "Screen capture (region %(x)d,%(y)d %(width)dx%(height)d)"
_SCREEN_REGION_LABEL_PATTERN = re.compile(r"^Screen capture \(region (-?\d+),(-?\d+) (\d+)x(\d+)\)$")
SCREEN_WINDOW_DEVICE_LABEL = "Screen capture (window: %(title)s)"
_SCREEN_WINDOW_LABEL_PATTERN = re.compile(r"^Screen capture \(window: (.+)\)$")


def screen_region_device_label(region):
    x, y, width, height = region
    return SCREEN_REGION_DEVICE_LABEL % {"x": x, "y": y, "width": width, "height": height}


def screen_region_from_label(label):
    match = _SCREEN_REGION_LABEL_PATTERN.match((label or "").strip())
    return tuple(int(match.group(i)) for i in range(1, 5)) if match else None


def screen_window_device_label(title):
    return SCREEN_WINDOW_DEVICE_LABEL % {"title": title}


def screen_window_title_from_label(label):
    match = _SCREEN_WINDOW_LABEL_PATTERN.match((label or "").strip())
    return match.group(1) if match else None


def screen_window_title(source_value):
    """The window title of a `title=…` / `screen=title=…` value, else None."""
    source_text = build_source_text("screen", source_value or "")
    if source_text.lower().startswith("screen=title="):
        title = source_text[len("screen=title="):]
        return title or None
    return None


def screen_device_label_for_source(source_type, source_value):
    """The Video Settings device entry that stands for this row's screen source, or None."""
    if source_type != "screen":
        return None
    source_text = build_source_text("screen", source_value)
    if source_value.strip().lower() in ("", SCREEN_DEFAULT_TARGET):
        return SCREEN_DESKTOP_DEVICE_LABEL
    monitor = screen_monitor_index(source_text)
    if monitor is not None:
        return screen_monitor_device_label(monitor)
    region = screen_region(source_text)
    if region is not None:
        return screen_region_device_label(region)
    title = screen_window_title(source_value)
    return screen_window_device_label(title) if title else None


class ScreenCaptureSettingsDialog(QDialog):
    """What a "Screen capture" row records: the desktop, one display, a window or a region."""

    def __init__(self, current_value="", parent=None, window_titles=None, monitor_count=None, pick_region=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Screen Capture Settings"))
        self._pick_region = pick_region or self._pick_region_on_screen
        if monitor_count is None:
            monitor_count = len(screen_monitor_device_labels())
        if window_titles is None:
            window_titles = list_capture_windows()

        layout = QVBoxLayout(self)
        intro = QLabel(_tr("Choose what this source records. The desktop and window modes use GDI; "
                           "a single display is captured through the GPU."))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.desktop_radio = QRadioButton(_tr("Whole desktop (every monitor)"))
        layout.addWidget(self.desktop_radio)

        self.monitor_radio = QRadioButton(_tr("One display (GPU)"))
        self.monitor_combo = QComboBox()
        for number in range(1, max(1, monitor_count) + 1):
            self.monitor_combo.addItem(_tr("Monitor %(number)d") % {"number": number}, number)
        layout.addLayout(self._option_row(self.monitor_radio, self.monitor_combo))

        self.window_radio = QRadioButton(_tr("One window"))
        self.window_combo = QComboBox()
        self.window_combo.setEditable(True)
        self.window_combo.addItems(list(window_titles))
        self.window_combo.setMinimumWidth(260)
        self.refresh_windows_button = QPushButton(_tr("Refresh"))
        self.refresh_windows_button.clicked.connect(self.refresh_windows)
        layout.addLayout(self._option_row(self.window_radio, self.window_combo, self.refresh_windows_button))

        self.region_radio = QRadioButton(_tr("Part of the desktop"))
        self.region_x = self._coordinate_spinbox(-32768, 32767)
        self.region_y = self._coordinate_spinbox(-32768, 32767)
        self.region_width = self._coordinate_spinbox(2, 32766, 640)
        self.region_height = self._coordinate_spinbox(2, 32766, 480)
        self.pick_region_button = QPushButton(_tr("Select on screen..."))
        self.pick_region_button.clicked.connect(self.pick_region)
        region_row = QHBoxLayout()
        region_row.addWidget(self.region_radio)
        for label_text, spin in (
            (_tr("X"), self.region_x), (_tr("Y"), self.region_y),
            (_tr("Width"), self.region_width), (_tr("Height"), self.region_height),
        ):
            region_row.addWidget(QLabel(label_text))
            region_row.addWidget(spin)
        region_row.addWidget(self.pick_region_button)
        region_row.addStretch(1)
        layout.addLayout(region_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._select_from_value(current_value)

    @staticmethod
    def _option_row(radio, *widgets):
        row = QHBoxLayout()
        row.addWidget(radio)
        for widget in widgets:
            row.addWidget(widget)
        row.addStretch(1)
        return row

    @staticmethod
    def _coordinate_spinbox(minimum, maximum, value=0):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setMaximumWidth(80)
        return spin

    def _select_from_value(self, value):
        value = (value or "").strip()
        source_text = build_source_text("screen", value)
        monitor = screen_monitor_index(source_text)
        region = screen_region(source_text)
        title = screen_window_title(value)
        if monitor is not None:
            self.monitor_radio.setChecked(True)
            index = self.monitor_combo.findData(monitor)
            if index < 0:
                self.monitor_combo.addItem(_tr("Monitor %(number)d") % {"number": monitor}, monitor)
                index = self.monitor_combo.count() - 1
            self.monitor_combo.setCurrentIndex(index)
        elif region is not None:
            self.region_radio.setChecked(True)
            x, y, width, height = region
            self.region_x.setValue(x)
            self.region_y.setValue(y)
            self.region_width.setValue(width)
            self.region_height.setValue(height)
        elif title:
            self.window_radio.setChecked(True)
            if self.window_combo.findText(title) < 0:
                self.window_combo.addItem(title)        # a window that is not open right now
            self.window_combo.setCurrentText(title)
        else:
            self.desktop_radio.setChecked(True)

    def refresh_windows(self):
        current = self.window_combo.currentText()
        self.window_combo.clear()
        self.window_combo.addItems(list_capture_windows())
        if current:
            self.window_combo.setCurrentText(current)

    def _windows_to_fade(self):
        """This dialog and the Video Settings dialog it was opened from."""
        windows = [self]
        parent = self.parentWidget()
        if parent is not None:
            windows.append(parent.window())
        return tuple(windows)

    def _pick_region_on_screen(self):
        return pick_screen_region_value(fade_windows=self._windows_to_fade())

    def pick_region(self):
        value = self._pick_region()
        region = screen_region(build_source_text("screen", value)) if value else None
        if region is None:
            return
        x, y, width, height = region
        self.region_x.setValue(x)
        self.region_y.setValue(y)
        self.region_width.setValue(width)
        self.region_height.setValue(height)
        self.region_radio.setChecked(True)

    def source_value(self):
        """The row's screen address: "desktop", "monitor=N", "title=…" or "region=X,Y,WxH"."""
        if self.monitor_radio.isChecked():
            return f"{SCREEN_MONITOR_PREFIX}{self.monitor_combo.currentData()}"
        if self.window_radio.isChecked():
            title = self.window_combo.currentText().strip()
            return f"title={title}" if title else SCREEN_DEFAULT_TARGET
        if self.region_radio.isChecked():
            width = max(2, self.region_width.value() // 2 * 2)
            height = max(2, self.region_height.value() // 2 * 2)
            return build_region_source_value(self.region_x.value(), self.region_y.value(), width, height)
        return SCREEN_DEFAULT_TARGET


def screen_monitor_device_label(number):
    return SCREEN_MONITOR_DEVICE_LABEL % {"number": number}


def screen_monitor_device_labels():
    """One "Screen capture (monitor N, GPU)" entry per display attached right now."""
    app = QApplication.instance()
    screens = app.screens() if app is not None else []
    return [screen_monitor_device_label(number) for number in range(1, len(screens) + 1)]


def screen_monitor_number_from_label(label):
    match = _SCREEN_MONITOR_LABEL_PATTERN.match((label or "").strip())
    return int(match.group(1)) if match else None


class PreviewLabel(QLabel):
    # Subclass QLabel so the recorder can keep the PTZ overlay button centered every
    # time the preview tile is resized. The parent window reflows whenever the global
    # "Stop Recording" button is shown/hidden, and without this hook the overlay drifts
    # off-center (it was just .move()'d to absolute coordinates the last time the
    # source was updated).
    # The tile's size comes from the layout, never from the picture on it. A
    # QLabel's size hints follow its pixmap, and each preview frame is scaled
    # to the tile's *current* size -- so with the default hints every frame
    # asked for pixmap height + 2 px of frame, the layout obliged, the next
    # frame was scaled 2 px taller, and a single-source tab crept downwards a
    # frame at a time until the groups below needed scrolling.
    HINT = QSize(160, 90)

    def __init__(self, recorder, row_index, parent=None):
        super().__init__(parent)
        self._recorder = recorder
        self._row_index = row_index

    def sizeHint(self):
        return QSize(self.HINT)

    def minimumSizeHint(self):
        return QSize(0, self.minimumHeight())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        recorder = self._recorder
        if recorder is None:
            return
        try:
            recorder.update_ptz_overlay_for_row(self._row_index)
        except RuntimeError:
            return


class PTZOverlayButton(QPushButton):
    def __init__(self, recorder, row_index, parent=None):
        super().__init__("PTZ", parent)
        self.recorder = recorder
        self.row_index = row_index
        self.drag_start = None
        self.last_direction = ""
        self.setFixedSize(30, 24)
        self.setToolTip(_tr("Drag to pan/tilt this camera"))
        self.setProperty("skipGlobalStyle", True)
        self.setStyleSheet(theme.qss("""
            QPushButton {
                background: rgba(255, 255, 255, 180);
                color: $grey_900;
                border: 1px solid $grey_600;
                border-radius: 3px;
                padding: 1px;
                font-size: 7pt;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 220); }
        """))
        self.hide()

    def mousePressEvent(self, event):
        self.drag_start = event.pos()
        self.last_direction = ""
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_start is None:
            return
        delta = event.pos() - self.drag_start
        if abs(delta.x()) < 4 and abs(delta.y()) < 4:
            return
        if abs(delta.x()) >= abs(delta.y()):
            direction = "right" if delta.x() > 0 else "left"
        else:
            direction = "down" if delta.y() > 0 else "up"
        if direction != self.last_direction:
            self.send_direction(direction)
            self.last_direction = direction
        event.accept()

    def mouseReleaseEvent(self, event):
        self.send_stop()
        self.drag_start = None
        self.last_direction = ""
        event.accept()

    def send_direction(self, direction):
        self.recorder.send_ptz_for_row(self.row_index, direction)

    def send_stop(self):
        self.recorder.send_ptz_for_row(self.row_index, "stop")


class VideoSettingsDialog(QDialog):
    # The audio device column was the widest thing in the dialog (long
    # microphone names); it is capped and the names elide instead.
    AUDIO_DEVICE_MAX_W = 180

    def __init__(self, source_rows, output_controls=None, parent=None, button_style=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Video Settings"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.source_rows = source_rows
        self.output_controls = output_controls or {}
        self.dialog_rows = []
        # Last real device text per row combo, so "Refresh USB devices..." can
        # be undone after it has triggered a scan.
        self._last_device_choice = {}
        self.camera_settings_buttons = []
        self.mode_status_labels = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(4)
        self.video_settings_headers = [
            "Nr", "Use", "Video name", "Video device", "",
            "Frame rate", "Resolution", "Audio name", "Audio device", "Sync offset"
        ]
        headers = self.video_settings_headers
        for col, text in enumerate(headers):
            header = QLabel(text)
            header.setStyleSheet("font-weight: bold;")
            grid.addWidget(header, 0, col)

        self.directshow_devices = getattr(parent, "directshow_devices", None) or []
        for index, source_row in enumerate(source_rows):
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            audio_name_edit = source_row[4] if len(source_row) > 4 else None
            audio_device_combo = source_row[7] if len(source_row) > 7 else None
            frame_rate_combo = source_row[8] if len(source_row) > 8 else None
            resolution_combo = source_row[9] if len(source_row) > 9 else None
            offset_spin = source_row[10] if len(source_row) > 10 else None
            row_enabled = QCheckBox()
            row_enabled.setChecked(enabled.isChecked())
            row_label = QLineEdit(label_edit.text())
            row_label.setMinimumWidth(58)
            row_label.setMaximumWidth(82)
            row_type = QComboBox()
            for item in CAMERA_SOURCE_TYPES:
                row_type.addItem(item["label"], item["id"])
            current_index = row_type.findData(type_combo.currentData())
            if current_index >= 0:
                row_type.setCurrentIndex(current_index)
            row_device = SourceComboBox()
            row_device.setMinimumWidth(190)
            self.populate_video_device_combo(row_device)
            screen_label = screen_device_label_for_source(type_combo.currentData(), source_edit.text())
            if screen_label:
                if row_device.findText(screen_label) < 0:
                    # A display or window that is not there right now still shows as itself.
                    row_device.addItem(screen_label, "screen")
                row_device.setCurrentText(screen_label)
            elif source_edit.text():
                row_device.setText(source_edit.text())
            else:
                row_device.setCurrentText("No source selected...")
            if row_device.currentText().strip():
                self._last_device_choice[row_device] = row_device.currentText()
            row_device.activated.connect(
                lambda _index, combo=row_device: self.handle_video_device_choice(combo)
            )
            row_device.currentTextChanged.connect(
                lambda _text, combo=row_device: self.handle_video_device_choice(combo)
            )
            row_frame_rate = QComboBox()
            row_frame_rate.addItems(["30.00", "25.00", "15.00"])
            if frame_rate_combo:
                row_frame_rate.setCurrentText(frame_rate_combo.currentText())
            row_resolution = QComboBox()
            row_resolution.addItems(["1920 x 1080", "1280 x 720", "640 x 480", "Auto"])
            if resolution_combo:
                row_resolution.setCurrentText(resolution_combo.currentText())
            row_audio_name = QLineEdit(audio_name_edit.text() if audio_name_edit else f"Audio {index + 1}")
            row_audio_name.setMinimumWidth(58)
            row_audio_name.setMaximumWidth(82)
            row_audio_device = QComboBox()
            # Microphone names run long ("... (USB Audio Device, ...)"); elide
            # them in the field rather than let the column set the dialog width.
            # The full name is the tooltip and shows in the drop-down.
            row_audio_device.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            row_audio_device.setMinimumContentsLength(12)
            row_audio_device.setMaximumWidth(self.AUDIO_DEVICE_MAX_W)
            row_audio_device.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row_audio_device.currentTextChanged.connect(
                lambda text, combo=row_audio_device: combo.setToolTip(text)
            )
            stored_audio = (
                parent._audio_device_value(audio_device_combo)
                if parent and audio_device_combo
                else "No Audio"
            )
            if parent and hasattr(parent, "populate_audio_device_combo"):
                parent.populate_audio_device_combo(row_audio_device, stored_audio)
            else:
                row_audio_device.addItem(_tr("No Audio"), "No Audio")
            row_audio_device.setToolTip(row_audio_device.currentText())
            row_offset = make_sync_offset_spinbox()
            if offset_spin is not None:
                row_offset.setValue(offset_spin.value())
            grid.addWidget(QLabel(str(index + 1)), index + 1, 0)
            grid.addWidget(row_enabled, index + 1, 1)
            grid.addWidget(row_label, index + 1, 2)
            grid.addWidget(row_device, index + 1, 3)
            camera_button = make_icon_button(
                "camera",
                _tr("Camera %(number)s settings") % {"number": index + 1},
                theme.skin().accent,
                size=20,
            )
            camera_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            camera_button.clicked.connect(
                lambda _checked=False, row=index: self.open_camera_settings(row)
            )
            grid.addWidget(camera_button, index + 1, 4, Qt.AlignCenter)
            grid.addWidget(row_frame_rate, index + 1, 5)
            grid.addWidget(row_resolution, index + 1, 6)
            grid.addWidget(row_audio_name, index + 1, 7)
            grid.addWidget(row_audio_device, index + 1, 8)
            grid.addWidget(row_offset, index + 1, 9)
            mode_status = QLabel("")
            mode_status.setStyleSheet(theme.qss("color: $grey_600; font-size: 8pt;"))
            mode_status.hide()
            self.camera_settings_buttons.append(camera_button)
            self.mode_status_labels.append(mode_status)
            self.dialog_rows.append((
                row_enabled, row_label, row_type, row_device, row_frame_rate,
                row_resolution, row_audio_name, row_audio_device, row_offset
            ))
        # Spare width goes to the video device column first, then the audio
        # device column (capped); nothing else stretches.
        grid.setColumnStretch(3, 3)
        grid.setColumnMinimumWidth(4, 20)
        grid.setColumnStretch(4, 0)
        grid.setColumnStretch(8, 2)
        layout.addLayout(grid)
        scan_row = QHBoxLayout()
        scan_row.setContentsMargins(0, 0, 0, 0)
        scan_row.setSpacing(6)
        self.device_scan_status = QLabel("")
        self.device_scan_status.setStyleSheet(theme.muted_label_style())
        self.refresh_devices_button = make_icon_button(
            "refresh",
            _tr("Scan again for cameras and microphones"),
            theme.skin().accent,
            size=24,
        )
        self.refresh_devices_button.clicked.connect(self.refresh_devices)
        # Older name, kept for callers that only knew about the audio side.
        self.refresh_audio_devices_button = self.refresh_devices_button
        scan_row.addStretch(1)
        scan_row.addWidget(self.device_scan_status, 0, Qt.AlignVCenter)
        scan_row.addWidget(self.refresh_devices_button, 0, Qt.AlignVCenter)
        layout.addLayout(scan_row)
        if parent and hasattr(parent, "audio_devices_discovered"):
            parent.audio_devices_discovered.connect(self.apply_discovered_audio_devices)
        if parent and hasattr(parent, "video_devices_discovered"):
            parent.video_devices_discovered.connect(self.apply_discovered_video_devices)
        if parent and hasattr(parent, "device_scan_started"):
            parent.device_scan_started.connect(self._on_device_scan_started)
            parent.device_scan_finished.connect(self._on_device_scan_finished)
        if parent and hasattr(parent, "start_device_discovery"):
            # Opening the dialog is the moment the lists matter; a listing that
            # is still fresh is reused, otherwise one starts in the background.
            if parent.start_device_discovery() or getattr(parent, "device_discovery_running", False):
                self._on_device_scan_started()
            else:
                self._show_device_counts()

        preset_group = QGroupBox(_tr("Video Preset"))
        preset_layout = QHBoxLayout()
        self.preset_layout = preset_layout
        preset_layout.setContentsMargins(6, 6, 6, 6)
        preset_layout.setAlignment(Qt.AlignLeft)
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(False)
        self.preset_combo.setMaximumWidth(120)
        self.preset_path_edit = QLineEdit()
        self.preset_path_edit.setReadOnly(True)
        self.preset_path_edit.setMinimumWidth(120)
        self.preset_load_button = QPushButton(_tr("Load"))
        self.preset_set_button = QPushButton(_tr("Set"))
        self.preset_save_as_button = QPushButton(_tr("Save as..."))
        self.preset_delete_button = QPushButton(_tr("Delete"))
        self.preset_open_bracket = QLabel(_tr("["))
        self.preset_separator = QLabel(_tr("/"))
        self.preset_close_bracket = QLabel(_tr("]"))
        link_style = theme.qss("""
            QPushButton {
                background: transparent;
                color: $accent_dark;
                border: none;
                text-decoration: underline;
                padding: 0px;
                text-align: left;
            }
            QPushButton:hover { color: $accent_deep; }
        """)
        self.preset_load_button.setMaximumWidth(48)
        self.preset_set_button.setMaximumWidth(38)
        for button in (self.preset_load_button, self.preset_set_button):
            button.setProperty("skipGlobalStyle", True)
            button.setStyleSheet(link_style)
        # Save as / Delete are rarer than Load / Set: quiet text links in the
        # muted colour, so the eye is not pulled to two filled buttons.
        quiet_link_style = theme.qss("""
            QPushButton {
                background: transparent;
                color: $grey_650;
                border: none;
                text-decoration: underline;
                padding: 0px 4px;
                text-align: left;
            }
            QPushButton:hover { color: $accent_deep; }
        """)
        for button in (self.preset_save_as_button, self.preset_delete_button):
            button.setProperty("skipGlobalStyle", True)
            button.setStyleSheet(quiet_link_style)
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.preset_save_as_button.setMaximumWidth(64)
        self.preset_delete_button.setMaximumWidth(48)
        self.preset_combo.currentTextChanged.connect(lambda _text: self.update_selected_preset_path())
        self.preset_load_button.clicked.connect(self.load_selected_preset)
        self.preset_set_button.clicked.connect(self.set_selected_preset)
        self.preset_save_as_button.clicked.connect(self.save_preset_as)
        self.preset_delete_button.clicked.connect(self.delete_selected_preset)
        preset_layout.addWidget(QLabel(_tr("Video Preset:")))
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addWidget(self.preset_path_edit)
        preset_action_layout = QHBoxLayout()
        self.preset_action_layout = preset_action_layout
        preset_action_layout.setContentsMargins(0, 0, 0, 0)
        preset_action_layout.setSpacing(2)
        preset_action_layout.addWidget(self.preset_open_bracket)
        preset_action_layout.addWidget(self.preset_load_button)
        preset_action_layout.addWidget(self.preset_separator)
        preset_action_layout.addWidget(self.preset_set_button)
        preset_action_layout.addWidget(self.preset_close_bracket)
        preset_action_widget = QWidget()
        self.preset_action_widget = preset_action_widget
        preset_action_widget.setLayout(preset_action_layout)
        preset_action_widget.setMaximumWidth(90)
        preset_action_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        preset_layout.addWidget(preset_action_widget)
        preset_layout.addWidget(self.preset_save_as_button)
        preset_layout.addWidget(self.preset_delete_button)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        lower_row = QHBoxLayout()
        output_group = QGroupBox(_tr("Output settings"))
        output_form = QFormLayout()
        self.output_quality_combo = QComboBox()
        self.output_quality_combo.addItems(["Default", "High", "Balanced", "Compact"])
        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItems([
            _tr("Separate videos"),
            _tr("Combined grid"),
            _tr("Picture-in-picture"),
        ])
        quality_control = self.output_controls.get("quality")
        if quality_control:
            self.output_quality_combo.setCurrentText(quality_control)
        output_mode_control = self.output_controls.get("output_mode")
        if output_mode_control:
            self.output_mode_combo.setCurrentText(output_mode_control.currentText())
        output_form.addRow("Output quality:", self.output_quality_combo)
        output_form.addRow("Output mode:", self.output_mode_combo)
        output_group.setLayout(output_form)
        lower_row.addWidget(output_group, 1)

        timer_group = QGroupBox(_tr("Timer settings"))
        timer_form = QFormLayout()
        self.maximum_time_check = QCheckBox(_tr("Use maximum recording time"))
        self.maximum_time_edit = QLineEdit()
        self.maximum_time_edit.setPlaceholderText(_tr("01:00:00"))
        current_timer = self.output_controls.get("duration")
        current_text = current_timer.text().strip() if current_timer is not None else ""
        self.maximum_time_check.setChecked(bool(current_text))
        self.maximum_time_edit.setText(current_text)
        self.maximum_time_edit.setEnabled(bool(current_text))
        self.maximum_time_check.toggled.connect(self.maximum_time_edit.setEnabled)
        timer_form.addRow(self.maximum_time_check, self.maximum_time_edit)
        timer_group.setLayout(timer_form)
        lower_row.addWidget(timer_group, 1)
        layout.addLayout(lower_row)

        help_text = QLabel(
            _tr("USB / DirectShow expects the Windows camera name. RTSP/IP can use an IP address or full rtsp:// URL. "
            "Basler / GenICam expects the source string from pylon or device setup.")
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet(theme.qss("color: $grey_700;"))
        layout.addWidget(help_text)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.buttons = buttons
        if button_style:
            for button in buttons.buttons():
                button.setStyleSheet(button_style)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply_changes)
        buttons.accepted.connect(self.accept_with_changes)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.loaded_preset_name = ""
        self.loaded_preset_settings = None
        self.refresh_preset_list()

    def apply_changes(self):
        self.apply_to_sources()
        self.update_preset_dirty_marker()
        parent = self.parent()
        if parent and hasattr(parent, "refresh_previews_from_sources"):
            parent.refresh_previews_from_sources()
        if parent and hasattr(parent, "save_current_recorder_settings"):
            parent.save_current_recorder_settings()

    def accept_with_changes(self):
        self.apply_changes()
        self.accept()

    def selected_preset_name(self):
        return self.preset_combo.currentText().removesuffix(" *").strip()

    def update_selected_preset_path(self):
        parent = self.parent()
        name = self.selected_preset_name()
        if parent and hasattr(parent, "recorder_preset_path"):
            self.preset_path_edit.setText(parent.recorder_preset_path(name))
        else:
            self.preset_path_edit.setText(name)

    def load_selected_preset(self):
        name = self.selected_preset_name()
        parent = self.parent()
        if not name or not parent:
            return
        self.loaded_preset_settings = parent.load_named_recorder_preset(name)
        self.loaded_preset_name = name
        self.apply_parent_state_to_dialog()
        self.refresh_preset_list(name)

    def save_selected_preset(self):
        self.set_selected_preset()

    def set_selected_preset(self):
        name = self.selected_preset_name()
        parent = self.parent()
        if not name or not parent:
            return
        self.apply_changes()
        self.loaded_preset_settings = parent.save_named_recorder_preset(name)
        self.loaded_preset_name = name
        self.refresh_preset_list(name)

    def save_preset_as(self):
        name, accepted = QInputDialog.getText(
            self,
            _tr("Save Video Preset"),
            _tr("Preset name:"),
            text=self.selected_preset_name(),
        )
        if not accepted or not name.strip():
            return
        safe_name = safe_preset_name(name)
        self.apply_changes()
        self.loaded_preset_settings = self.parent().save_named_recorder_preset(safe_name)
        self.loaded_preset_name = safe_name
        self.refresh_preset_list(safe_name)

    def delete_selected_preset(self):
        name = self.selected_preset_name()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            _tr("Delete Video Preset"),
            _tr("Delete preset '%(name)s'?") % {"name": name},
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.parent().delete_named_recorder_preset(name)
        self.loaded_preset_name = ""
        self.loaded_preset_settings = None
        self.refresh_preset_list()

    def refresh_preset_list(self, selected_name=""):
        parent = self.parent()
        names = (
            parent.list_recorder_presets()
            if parent and hasattr(parent, "list_recorder_presets")
            else []
        )
        current = selected_name or self.selected_preset_name().removesuffix(" *")
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(names)
        if current in names:
            self.preset_combo.setCurrentText(current)
        self.preset_combo.blockSignals(False)
        self.update_selected_preset_path()

    def _comparable_settings(self, settings):
        value = normalize_recorder_settings(settings)
        value.pop("version", None)
        return value

    def update_preset_dirty_marker(self):
        if not self.loaded_preset_name or self.loaded_preset_settings is None:
            return
        current = self.parent().capture_recorder_settings()
        dirty = self._comparable_settings(current) != self._comparable_settings(
            self.loaded_preset_settings
        )
        text = (
            _tr("%(name)s *") % {"name": self.loaded_preset_name}
            if dirty
            else self.loaded_preset_name
        )
        index = self.preset_combo.currentIndex()
        if index < 0:
            return
        self.preset_combo.blockSignals(True)
        self.preset_combo.setItemText(index, text)
        self.preset_combo.blockSignals(False)
        self.update_selected_preset_path()

    def populate_ptz_sources(self):
        self.ptz_source_combo.clear()
        for index, source_row in enumerate(self.source_rows):
            _enabled, label_edit, type_combo, source_edit = source_row[:4]
            source_type = type_combo.currentData()
            source_text = build_source_text(source_type, source_edit.text().strip())
            if source_text.lower().startswith("rtsp://"):
                self.ptz_source_combo.addItem(f"{label_edit.text() or f'Video {index + 1}'} - Axis PTZ", source_text)

    def selected_ptz_source(self):
        return self.ptz_source_combo.currentData() or ""

    def send_ptz_move(self, move):
        parent = self.parent()
        if parent and hasattr(parent, "axis_ptz_move"):
            parent.axis_ptz_move(self.selected_ptz_source(), move)

    def refresh_ptz_presets(self):
        parent = self.parent()
        if not parent or not hasattr(parent, "axis_ptz_presets"):
            return
        presets = parent.axis_ptz_presets(self.selected_ptz_source())
        self.ptz_preset_combo.clear()
        self.ptz_preset_combo.addItems(presets)

    def selected_ptz_preset(self):
        return self.ptz_preset_combo.currentText().strip()

    def goto_ptz_preset(self):
        parent = self.parent()
        if parent and hasattr(parent, "axis_ptz_goto_preset"):
            parent.axis_ptz_goto_preset(self.selected_ptz_source(), self.selected_ptz_preset())

    def save_ptz_preset(self):
        parent = self.parent()
        if parent and hasattr(parent, "axis_ptz_set_preset"):
            parent.axis_ptz_set_preset(self.selected_ptz_source(), self.selected_ptz_preset())

    def apply_parent_state_to_dialog(self):
        # Rebuild the dialog field values from the parent widget after loading a preset.
        for source_row, dialog_row in zip(
            self.source_rows,
            self.dialog_rows,
            strict=False,
        ):
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            audio_name_edit = source_row[4] if len(source_row) > 4 else None
            audio_device_combo = source_row[7] if len(source_row) > 7 else None
            frame_rate_combo = source_row[8] if len(source_row) > 8 else None
            resolution_combo = source_row[9] if len(source_row) > 9 else None
            offset_spin = source_row[10] if len(source_row) > 10 else None
            (row_enabled, row_label, row_type, row_device, row_frame_rate,
             row_resolution, row_audio_name, row_audio_device, row_offset) = dialog_row
            row_enabled.setChecked(enabled.isChecked())
            row_label.setText(label_edit.text())
            type_index = row_type.findData(type_combo.currentData())
            if type_index >= 0:
                row_type.setCurrentIndex(type_index)
            row_device.setText(source_edit.text())
            if audio_name_edit:
                row_audio_name.setText(audio_name_edit.text())
            if audio_device_combo:
                parent = self.parent()
                selected_audio = (
                    parent._audio_device_value(audio_device_combo)
                    if parent and hasattr(parent, "_audio_device_value")
                    else audio_device_combo.currentText()
                )
                if parent and hasattr(parent, "populate_audio_device_combo"):
                    parent.populate_audio_device_combo(row_audio_device, selected_audio)
                else:
                    row_audio_device.setCurrentText(selected_audio)
            if frame_rate_combo:
                row_frame_rate.setCurrentText(frame_rate_combo.currentText())
            if resolution_combo:
                row_resolution.setCurrentText(resolution_combo.currentText())
            if offset_spin is not None:
                row_offset.setValue(offset_spin.value())

    def populate_video_device_combo(self, combo):
        current = combo.currentText()
        if current == "Refresh USB devices...":
            current = self._last_device_choice.get(combo, "No source selected...")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("No source selected...", "none")
        combo.addItem("RTSP/IP Camera", "rtsp_ip")
        combo.addItem(SCREEN_CAPTURE_DEVICE_LABEL, "screen")
        for device in self.directshow_devices:
            combo.addItem(device, "directshow")
        combo.addItem("Refresh USB devices...", "refresh_directshow")
        combo.addItem("Select video device...", "")
        if current:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    def effective_video_device_type(self, row_type, row_device):
        device_type = row_device.currentData()
        device_text = row_device.currentText().strip()
        if device_text.lower().startswith("rtsp://"):
            return "rtsp_ip"
        if device_text.lower().startswith(("http://", "https://")):
            return "stream_url"
        if self._screen_source_value_for_label(device_text) is not None or device_text.lower().startswith("screen="):
            return "screen"
        if device_type == "none" and device_text and device_text != "No source selected...":
            device_type = None
        if device_text in (getattr(self.parent(), "directshow_devices", None) or []):
            device_type = "directshow"
        if not device_type:
            device_type = row_type.currentData()
        return device_type

    def refresh_devices(self):
        """Rescan cameras and microphones in the background (one ffmpeg run)."""
        parent = self.parent()
        if parent and hasattr(parent, "start_device_discovery"):
            if parent.start_device_discovery(force=True):
                self._on_device_scan_started()

    # Both older entry points now mean the same thing: one scan lists both.
    refresh_directshow_devices = refresh_devices
    refresh_audio_devices = refresh_devices

    def apply_discovered_video_devices(self, devices):
        self.directshow_devices = list(devices or [])
        for dialog_row in self.dialog_rows:
            self.populate_video_device_combo(dialog_row[3])

    def apply_discovered_audio_devices(self, _devices):
        parent = self.parent()
        if not parent:
            return
        for dialog_row in self.dialog_rows:
            combo = dialog_row[7]
            parent.populate_audio_device_combo(
                combo,
                parent._audio_device_value(combo),
            )

    def _on_device_scan_started(self):
        self.refresh_devices_button.setEnabled(False)
        self.device_scan_status.setText(_tr("Scanning for cameras and microphones..."))

    def _on_device_scan_finished(self, scan):
        self.refresh_devices_button.setEnabled(True)
        if not getattr(scan, "ok", False):
            self.device_scan_status.setText(
                _tr("Device scan failed. Check that ffmpeg.exe is present and try again.")
            )
            return
        self._show_device_counts()

    def _show_device_counts(self):
        parent = self.parent()
        cameras = len(getattr(parent, "directshow_devices", None) or self.directshow_devices or [])
        microphones = len(getattr(parent, "directshow_audio_devices", None) or [])
        camera_text = _tr("%(n)d camera") % {"n": cameras} if cameras == 1 else _tr("%(n)d cameras") % {"n": cameras}
        microphone_text = (
            _tr("%(n)d microphone") % {"n": microphones}
            if microphones == 1
            else _tr("%(n)d microphones") % {"n": microphones}
        )
        self.device_scan_status.setText(
            _tr("%(cameras)s, %(microphones)s found")
            % {"cameras": camera_text, "microphones": microphone_text}
        )

    @staticmethod
    def _screen_source_value_for_label(label):
        """The row's screen address ("desktop", "monitor=2", "region=…", "title=…") for a device entry."""
        text = (label or "").strip()
        if text in (SCREEN_CAPTURE_DEVICE_LABEL, SCREEN_DESKTOP_DEVICE_LABEL):
            return SCREEN_DEFAULT_TARGET
        monitor = screen_monitor_number_from_label(text)
        if monitor is not None:
            return f"{SCREEN_MONITOR_PREFIX}{monitor}"
        region = screen_region_from_label(text)
        if region is not None:
            return build_region_source_value(*region)
        title = screen_window_title_from_label(text)
        if title is not None:
            return f"title={title}"
        return None

    def _restore_previous_device_choice(self, combo):
        previous = self._last_device_choice.get(combo, "No source selected...")
        combo.blockSignals(True)
        combo.setCurrentText(previous)
        combo.blockSignals(False)

    def _show_screen_capture_label(self, combo, label):
        """Show the configured capture in the device box (added as an entry when new)."""
        combo.blockSignals(True)
        if combo.findText(label) < 0:
            combo.insertItem(combo.findText(SCREEN_CAPTURE_DEVICE_LABEL) + 1, label, "screen")
        combo.setCurrentIndex(combo.findText(label))     # the index, so currentData() follows
        combo.blockSignals(False)
        self._last_device_choice[combo] = label

    def open_screen_capture_settings(self, row_index):
        _enabled, _label, _type, row_device, *_rest = self.dialog_rows[row_index]
        current_value = self._screen_source_value_for_label(row_device.currentText())
        if current_value is None:
            current_value = row_device.currentText()
        dialog = ScreenCaptureSettingsDialog(current_value, parent=self)
        try:
            if dialog.exec_() != QDialog.Accepted:
                return
            value = dialog.source_value()
        finally:
            dialog.setParent(None)
            dialog.deleteLater()
        label = screen_device_label_for_source("screen", value) or SCREEN_DESKTOP_DEVICE_LABEL
        self._show_screen_capture_label(row_device, label)

    def handle_video_device_choice(self, combo):
        if combo.currentData() == "refresh_directshow":
            # Put the previous choice back so the entry can be picked again
            # and the row never records "Refresh USB devices..." as a camera.
            self._restore_previous_device_choice(combo)
            self.refresh_devices()
            return
        if combo.currentText().strip():
            self._last_device_choice[combo] = combo.currentText()
        self.detect_modes_for_combo(combo)

    def detect_modes_for_combo(self, combo):
        row_index = next((index for index, row in enumerate(self.dialog_rows) if row[3] is combo), -1)
        if row_index < 0:
            return
        device_name = combo.currentText().strip()
        if not device_name or device_name in VIDEO_DEVICE_PLACEHOLDERS:
            return
        parent = self.parent()
        device_type = combo.currentData()
        if device_type == "none":
            device_type = None
        if device_name in (getattr(parent, "directshow_devices", None) or []):
            device_type = "directshow"
        if device_type != "directshow":
            return
        cache_key = f"directshow:{device_name}"
        cached = getattr(parent, "camera_mode_cache", {}).get(cache_key) if parent else None
        if cached:
            self.apply_detected_modes(row_index, cached)
            return
        if row_index < len(self.mode_status_labels):
            self.mode_status_labels[row_index].setText("")
            self.mode_status_labels[row_index].hide()
        if row_index < len(self.dialog_rows):
            self.dialog_rows[row_index][4].setToolTip(_tr("Detecting supported camera modes..."))
            self.dialog_rows[row_index][5].setToolTip(_tr("Detecting supported camera modes..."))
        if parent and hasattr(parent, "start_directshow_mode_detection"):
            parent.start_directshow_mode_detection(
                device_name,
                lambda modes, row=row_index: self.apply_detected_modes(row, modes),
            )

    def apply_detected_modes(self, row_index, modes):
        if row_index < 0 or row_index >= len(self.dialog_rows):
            return
        if not modes:
            if row_index < len(self.mode_status_labels):
                self.mode_status_labels[row_index].setText("")
                self.mode_status_labels[row_index].hide()
            self.dialog_rows[row_index][4].setToolTip(_tr("Could not detect supported modes; Auto is recommended."))
            self.dialog_rows[row_index][5].setToolTip(_tr("Could not detect supported modes; Auto is recommended."))
            return
        row_frame_rate = self.dialog_rows[row_index][4]
        row_resolution = self.dialog_rows[row_index][5]
        current_fps = row_frame_rate.currentText()
        current_resolution = row_resolution.currentText()
        frame_rates = []
        resolutions = []
        for mode in modes:
            fps = mode.get("frame_rate", "")
            resolution = mode.get("resolution", "")
            if fps and fps not in frame_rates:
                frame_rates.append(fps)
            if resolution and resolution not in resolutions:
                resolutions.append(resolution)
        row_frame_rate.blockSignals(True)
        row_resolution.blockSignals(True)
        row_frame_rate.clear()
        row_resolution.clear()
        row_frame_rate.addItems(frame_rates or ["30.00", "25.00", "15.00"])
        row_frame_rate.addItem("Auto")
        row_resolution.addItems(resolutions + ["Auto"])
        row_frame_rate.setCurrentText(current_fps if current_fps in frame_rates else "Auto")
        row_resolution.setCurrentText(current_resolution if current_resolution in resolutions else (resolutions[0] if resolutions else "Auto"))
        row_frame_rate.blockSignals(False)
        row_resolution.blockSignals(False)
        if row_index < len(self.mode_status_labels):
            self.mode_status_labels[row_index].setText("")
            self.mode_status_labels[row_index].hide()
        row_frame_rate.setToolTip(_tr("Supported frame rates detected from the camera driver."))
        row_resolution.setToolTip(_tr("Supported resolutions detected from the camera driver."))

    def apply_to_sources(self):
        for source_row, dialog_row in zip(self.source_rows, self.dialog_rows, strict=False):
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            audio_name_edit = source_row[4] if len(source_row) > 4 else None
            audio_device_combo = source_row[7] if len(source_row) > 7 else None
            frame_rate_combo = source_row[8] if len(source_row) > 8 else None
            resolution_combo = source_row[9] if len(source_row) > 9 else None
            offset_spin = source_row[10] if len(source_row) > 10 else None
            (row_enabled, row_label, row_type, row_device, row_frame_rate,
             row_resolution, row_audio_name, row_audio_device, row_offset) = dialog_row
            enabled.setChecked(row_enabled.isChecked())
            label_edit.setText(row_label.text())
            device_type = self.effective_video_device_type(row_type, row_device)
            type_index = type_combo.findData(device_type)
            if type_index >= 0:
                type_combo.setCurrentIndex(type_index)
            if row_device.currentText() in VIDEO_DEVICE_PLACEHOLDERS:
                source_edit.setText("")
            elif device_type == "screen" and self._screen_source_value_for_label(row_device.currentText()) is not None:
                source_edit.setText(self._screen_source_value_for_label(row_device.currentText()))
            else:
                source_edit.setText(row_device.text())
            # A row with a source is worth recording; a row without one is not,
            # row 1 included -- it has no special claim to the first tile.
            enabled.setChecked(bool(source_edit.text().strip()))
            if audio_name_edit:
                audio_name_edit.setText(row_audio_name.text())
            if audio_device_combo:
                selected_audio = row_audio_device.currentData() or row_audio_device.currentText()
                parent = self.parent()
                if parent and hasattr(parent, "populate_audio_device_combo"):
                    parent.populate_audio_device_combo(audio_device_combo, selected_audio)
                else:
                    audio_device_combo.setCurrentText(selected_audio)
            if frame_rate_combo:
                frame_rate_combo.setCurrentText(row_frame_rate.currentText())
            if resolution_combo:
                resolution_combo.setCurrentText(row_resolution.currentText())
            if offset_spin is not None:
                offset_spin.setValue(row_offset.value())
        output_mode_control = self.output_controls.get("output_mode")
        if output_mode_control:
            output_mode_control.setCurrentText(self.output_mode_combo.currentText())
        parent = self.parent()
        if parent is not None:
            if hasattr(parent, "output_quality"):
                parent.output_quality = self.output_quality_combo.currentText()
            if hasattr(parent, "duration_edit"):
                parent.duration_edit.setText(
                    self.maximum_time_edit.text().strip()
                    if self.maximum_time_check.isChecked()
                    else ""
                )
        if parent and hasattr(parent, "update_preview_panel_visibility"):
            parent.update_preview_panel_visibility()

    def open_camera_settings(self, row_index):
        if row_index < 0 or row_index >= len(self.dialog_rows):
            return
        row_enabled, row_label, row_type, row_device, *_rest = self.dialog_rows[row_index]
        source_type = self.effective_video_device_type(row_type, row_device)
        if source_type == "basler_genicam" or "basler genicam source" in row_device.currentText().lower():
            parent = self.parent()
            if parent and hasattr(parent, "open_basler_camera_settings"):
                parent.open_basler_camera_settings(row_device.text())
            else:
                QMessageBox.information(
                    self,
                    _tr("Basler Camera Settings"),
                    _tr("Basler / GenICam settings are managed in Basler pylon Viewer."),
                )
            return
        if source_type == "directshow":
            parent = self.parent()
            if parent and hasattr(parent, "open_directshow_camera_settings"):
                parent.open_directshow_camera_settings(row_device.text())
            else:
                QMessageBox.information(
                    self,
                    _tr("USB Camera Settings"),
                    _tr("Camera settings for %(device)s will use the camera "
                        "driver's native controls when available.")
                    % {"device": row_device.text() or row_label.text()},
                )
            return
        if source_type == "rtsp_ip":
            self.open_rtsp_camera_settings(row_index)
            return
        if source_type == "screen":
            self.open_screen_capture_settings(row_index)
            return
        QMessageBox.information(self, _tr("Camera Settings"), _tr("No camera-specific settings are available for this source type yet."))

    def apply_rtsp_settings_to_row(self, row_index, host, username="", password="", port="", path="stream"):
        if row_index < 0 or row_index >= len(self.dialog_rows):
            return
        row_enabled, row_label, row_type, row_device, *_rest = self.dialog_rows[row_index]
        row_device.setText(build_rtsp_url(host, port=port, username=username, password=password, path=path))
        row_enabled.setChecked(True)

    def rtsp_settings_from_current_text(self, text):
        return parse_rtsp_url_settings(text)

    def open_rtsp_camera_settings(self, row_index):
        if row_index < 0 or row_index >= len(self.dialog_rows):
            return
        _enabled, _label, _type, row_device, *_rest = self.dialog_rows[row_index]
        dialog = QDialog(self)
        dialog.setWindowTitle(_tr("RTSP/IP Camera Settings"))
        form = QFormLayout(dialog)
        host_edit = QLineEdit()
        current = row_device.currentText()
        current_settings = self.rtsp_settings_from_current_text(current if current != "RTSP/IP Camera" else "")
        host_edit.setText(current_settings["host"])
        host_edit.setPlaceholderText(_tr("192.168.1.50 or rtsp://camera/stream"))
        user_edit = QLineEdit()
        user_edit.setText(current_settings["username"])
        password_edit = QLineEdit()
        password_edit.setText(current_settings["password"])
        password_edit.setEchoMode(QLineEdit.Password)
        port_edit = QLineEdit(current_settings["port"])
        path_edit = QLineEdit(current_settings["path"])
        form.addRow("Address / URL:", host_edit)
        form.addRow("Username:", user_edit)
        form.addRow("Password:", password_edit)
        form.addRow("Port:", port_edit)
        form.addRow("Stream path:", path_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        def accept_if_reachable():
            # A mistyped IP is the one mistake ffmpeg cannot report usefully.
            if self._accept_rtsp_host(host_edit.text(), parent=dialog):
                dialog.accept()

        buttons.accepted.connect(accept_if_reachable)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec_() == QDialog.Accepted:
            self.apply_rtsp_settings_to_row(
                row_index,
                host=host_edit.text(),
                username=user_edit.text(),
                password=password_edit.text(),
                port=port_edit.text(),
                path=path_edit.text(),
            )

    def _accept_rtsp_host(self, host_text, parent=None):
        """True when `host_text` can be used; otherwise warn and keep the dialog open."""
        problem = stream_host_problem(host_text)
        if not problem:
            return True
        QMessageBox.warning(
            parent or self,
            _tr("RTSP/IP Camera Settings"),
            _tr("Check the camera address.\n\n%(problem)s") % {"problem": problem},
        )
        return False


class MultiSourceRecorderWidget(QWidget):
    # Emitted whenever the output mode or the set of enabled sources changes, so a host
    # (the main window) can refresh the layout schematic shown in its sidebar preview.
    layout_preview_changed = pyqtSignal()
    # One ffmpeg listing yields both lists; the Video Settings dialog listens
    # to all three (the split ones for its combos, the summary for its status).
    device_scan_finished = pyqtSignal(object)
    audio_devices_discovered = pyqtSignal(list)
    video_devices_discovered = pyqtSignal(list)
    device_scan_started = pyqtSignal()
    hardware_encoder_detected = pyqtSignal(str)

    # Output settings group width cap; its fields all stretch to this so they
    # share one width (the folder row is edit + open-folder button).
    OUTPUT_GROUP_MAX_W = 380

    # How long a listing stays "fresh": opening Video Settings within this
    # window reuses it instead of spinning ffmpeg up again.
    DEVICE_SCAN_TTL_S = 45.0

    def __init__(self, parent=None, button_style=None, directshow_devices=None, auto_preview=True, load_saved_settings=False):
        super().__init__(parent)
        self._workflow_host = parent
        self.button_style = button_style
        self.directshow_devices = directshow_devices
        self.directshow_audio_devices = []
        # Hardware H.264 encoder that initialises on this machine ("" = libx264).
        # Found by the device scan; used for screen captures, whose frames are large.
        self.hardware_h264_encoder = ""
        self.hardware_encoder_detected.connect(self._apply_hardware_encoder)
        self.device_discovery_running = False
        self.last_device_scan_ok = None
        self.last_device_scan_at = None
        self.device_scan_finished.connect(self._apply_device_scan)
        self.auto_preview = auto_preview
        self.preview_processes = {}
        self.preview_files = {}
        self.preview_buffers = {}
        self.preview_pending_frames = {}
        self.preview_sources = {}
        self.ptz_overlay_buttons = []
        self.preview_source_profile = "low-latency-v1"
        self.preview_retry_attempts = {}
        self.preview_auto_mode_rows = set()
        self.preview_stopping_rows = set()
        self.preview_paused_rows = set()
        self.preview_frame_logged_rows = set()
        self.preview_render_logged_rows = set()
        self.combined_preview_rows = []
        self.combined_preview_pending_frame = None
        self.processes = []
        self.pending_recording_start = None
        self.record_start_delay_ms = 700
        self.basler_record_start_delay_ms = 2200
        self.record_start_watchdog_delay_ms = 2500
        self.log_lines = []
        self.camera_mode_cache = {}
        self.camera_mode_processes = []
        self.source_rows = []
        self.source_config_buttons = []
        self.video_name_edits = []
        self.source_type_map = {item["id"]: item for item in CAMERA_SOURCE_TYPES}
        self.output_quality = "Default"
        self._init_ui()
        # Take all spare height in the tab card; otherwise the tab's footer row
        # shares the surplus and its icons float mid-page in Full window mode.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_render_timer = QTimer(self)
        self.preview_render_timer.setInterval(100)
        self.preview_render_timer.timeout.connect(self._render_pending_preview_frames)
        self.preview_render_timer.start()
        self.record_start_timer = QTimer(self)
        self.record_start_timer.setSingleShot(True)
        self.record_start_timer.timeout.connect(self._begin_pending_recording)
        self.record_start_watchdog_timer = QTimer(self)
        self.record_start_watchdog_timer.setSingleShot(True)
        self.record_start_watchdog_timer.timeout.connect(self._begin_pending_recording)
        self.start_device_discovery()
        if load_saved_settings:
            self.load_current_recorder_settings()

    def _source_label(self, source_type_id):
        return {
            "rtsp_ip": "RTSP/IP",
            "directshow": "USB",
            "basler_genicam": "Basler",
            "stream_url": "Stream",
            "screen": "Screen",
            "file": "File",
        }.get(source_type_id, source_type_id)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        # No outer margins: the tab container already pads every tool tab the
        # same way, and a margin here put this header 6 px below the others'.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # No header of its own: the sidebar context header names the current tab.

        self.status_label = QLabel(_tr("Not recording"))
        self.status_label.setStyleSheet(theme.qss("color: $grey_650;"))

        preview_grid = QGridLayout()
        preview_grid.setSpacing(3)
        self.preview_grid = preview_grid
        self.preview_boxes = []
        tile_style = theme.qss("""
            QLabel {
                background: $grey_950;
                color: $grey_100;
                border: 1px solid $grey_260;
                font-size: 9pt;
            }
        """)
        for index in range(4):
            preview = PreviewLabel(self, index)
            preview.setText(_tr("Video %(number)s\nNo signal")
                            % {"number": index + 1})
            preview.setAlignment(Qt.AlignCenter)
            # Tiles take whatever height the tab has left once the two groups
            # (Fixed) have theirs; Ignored horizontally so a big pixmap never
            # widens the window.
            preview.setMinimumHeight(74)
            preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
            preview.setStyleSheet(tile_style)
            ptz_button = PTZOverlayButton(self, index, preview)
            ptz_button.move((preview.width() - ptz_button.width()) // 2, (preview.minimumHeight() - ptz_button.height()) // 2)
            preview_grid.addWidget(preview, index // 2, index % 2)
            self.preview_boxes.append(preview)
            self.ptz_overlay_buttons.append(ptz_button)
        # With every row unticked the live tiles all hide; this blank tile
        # takes the whole grid so the video area keeps its height and the
        # groups below do not jump up. Same look as an idle tile.
        self.no_source_tile = QLabel(_tr("No source enabled\nTick Use on a source to preview it"))
        self.no_source_tile.setAlignment(Qt.AlignCenter)
        self.no_source_tile.setMinimumHeight(74)
        self.no_source_tile.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.no_source_tile.setStyleSheet(tile_style)
        self.no_source_tile.hide()
        layout.addLayout(preview_grid, 1)

        self.groups_host = QWidget()
        self.groups_layout = None
        source_group = QGroupBox(_tr("Recording properties"))
        source_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        source_grid = QGridLayout()
        source_grid.setContentsMargins(6, 6, 6, 6)
        source_grid.setHorizontalSpacing(4)
        source_grid.setVerticalSpacing(2)
        self.recording_property_headers = ["Nr", "Use", "Video name", "Audio name", "Mute", "Volume"]
        headers = self.recording_property_headers
        for col, text in enumerate(headers):
            label = QLabel(text)
            label.setStyleSheet(theme.qss("font-weight: bold; color: $grey_800;"))
            source_grid.addWidget(label, 0, col)

        for index in range(4):
            number = QLabel(str(index + 1))
            enabled = QCheckBox()
            enabled.setChecked(index == 0)
            enabled.toggled.connect(lambda _checked: self.update_preview_panel_visibility())
            enabled.toggled.connect(lambda _checked: self.update_start_availability())
            enabled.toggled.connect(lambda _checked: self.layout_preview_changed.emit())
            label = QLineEdit(f"Video {index + 1}")
            label.setMinimumWidth(60)
            label.setMaximumWidth(220)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            label.setToolTip(_tr("Double-click to open video settings"))
            label.mouseDoubleClickEvent = lambda event, row=index: self.open_video_settings(row)
            source_type = QComboBox()
            for item in CAMERA_SOURCE_TYPES:
                source_type.addItem(self._source_label(item["id"]), item["id"])
            source_type.setMinimumWidth(64)
            source_type.setMaximumWidth(78)
            source = SourceComboBox()
            source.setMinimumWidth(90)
            source.setMaximumWidth(160)
            source.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            source.setPlaceholderText(_tr("address, device, or URL"))
            source_type.currentIndexChanged.connect(
                lambda _idx, row=index, combo=source_type, edit=source: self.update_source_placeholder(combo, edit, row)
            )
            audio_name = QLineEdit(f"Audio {index + 1}")
            audio_name.setMinimumWidth(60)
            audio_name.setMaximumWidth(220)
            audio_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            mute = QCheckBox()
            volume = QComboBox()
            volume.addItems(["100", "75", "50", "25", "0"])
            volume.setMaximumWidth(62)
            audio_device = QComboBox()
            audio_device.addItems(["No Audio"])
            frame_rate = QComboBox()
            frame_rate.addItems(["30.00", "25.00", "15.00"])
            resolution = QComboBox()
            resolution.addItems(["1920 x 1080", "1280 x 720", "640 x 480", "Auto"])
            sync_offset = make_sync_offset_spinbox()
            source_grid.addWidget(number, index + 1, 0)
            source_grid.addWidget(enabled, index + 1, 1)
            source_grid.addWidget(label, index + 1, 2)
            source_grid.addWidget(audio_name, index + 1, 3)
            source_grid.addWidget(mute, index + 1, 4)
            source_grid.addWidget(volume, index + 1, 5)
            self.source_rows.append((
                enabled, label, source_type, source, audio_name, mute, volume,
                audio_device, frame_rate, resolution, sync_offset
            ))
            self.video_name_edits.append(label)
        self.update_preview_panel_visibility()
        # Spare width goes to the name columns first (up to their caps) and
        # then to an empty trailing column, so Qt never pads Nr/Use/Mute.
        source_grid.setColumnStretch(2, 3)
        source_grid.setColumnStretch(3, 3)
        source_grid.setColumnStretch(6, 1)
        source_group_layout = QVBoxLayout()
        source_group_layout.setContentsMargins(6, 6, 6, 6)
        source_group_layout.setSpacing(2)
        source_grid.setContentsMargins(0, 0, 0, 0)
        source_group_layout.addLayout(source_grid)
        self.video_settings_link = QPushButton(_tr("Video Settings"))
        self.video_settings_link.setMaximumWidth(110)
        self.video_settings_link.setProperty("skipGlobalStyle", True)
        self.video_settings_link.setStyleSheet(theme.link_button_style())
        self.video_settings_link.clicked.connect(lambda: self.open_video_settings())
        self.recording_log_link = QPushButton(_tr("Show recording log"))
        self.recording_log_link.setMaximumWidth(130)
        self.recording_log_link.setProperty("skipGlobalStyle", True)
        self.recording_log_link.setStyleSheet(theme.link_button_style())
        self.recording_log_link.clicked.connect(self.show_recording_log)
        link_row = QHBoxLayout()
        link_row.setContentsMargins(0, 0, 0, 0)
        link_row.setSpacing(10)
        link_row.addWidget(self.video_settings_link, 0, Qt.AlignLeft)
        link_row.addWidget(self.recording_log_link, 0, Qt.AlignLeft)
        link_row.addStretch()
        source_group_layout.addLayout(link_row)
        source_group.setLayout(source_group_layout)
        self.source_group = source_group
        self.source_grid = source_grid

        output_group = QGroupBox(_tr("Output settings"))
        output_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        # The *group* is capped, not the fields: every field expands to the
        # same width inside it, so the boxes line up instead of each having
        # its own maximum.
        output_group.setMaximumWidth(self.OUTPUT_GROUP_MAX_W)
        output_form = QFormLayout()
        output_form.setContentsMargins(6, 6, 6, 6)
        output_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        output_form.setFormAlignment(Qt.AlignTop)
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        output_form.setVerticalSpacing(3)
        self.output_folder_edit = QLineEdit(os.path.join(os.path.expanduser("~"), "Videos"))
        # Wide enough to read a path tail, never spanning the whole window.
        self.output_folder_edit.setMinimumWidth(200)
        self.output_folder_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Keep the folder *name* (the tail) visible when the path is set
        # programmatically; leave the caret alone while the user is typing.
        self.output_folder_edit.textChanged.connect(self._show_output_path_tail)
        self._show_output_path_tail()
        self.output_folder_edit.setToolTip(_tr("Double-click to choose the recording folder"))
        self.output_folder_edit.mouseDoubleClickEvent = lambda event: self.browse_output_folder()
        browse_btn = QPushButton(_tr("..."))
        browse_btn.setToolTip(_tr("Choose recording folder"))
        browse_btn.setFixedSize(30, 24)
        browse_btn.setMaximumWidth(30)
        browse_btn.setProperty("skipGlobalStyle", True)
        browse_btn.setStyleSheet(theme.qss("""
            QPushButton {
                background: $accent;
                color: white;
                border: 1px solid $accent_dark;
                border-radius: 4px;
                padding: 0px;
                font-weight: bold;
            }
            QPushButton:hover { background: $accent_pressed; }
        """))
        browse_btn.clicked.connect(self.browse_output_folder)
        browse_btn.hide()
        self.browse_output_button = browse_btn
        self.open_output_folder_button = make_icon_button(
            "folder_open",
            _tr("Open the recording folder in your file browser"),
            theme.skin().accent,
            size=24,
        )
        self.open_output_folder_button.clicked.connect(self.open_output_folder)
        self.open_output_folder_link = self.open_output_folder_button
        folder_line = QHBoxLayout()
        folder_line.setContentsMargins(0, 0, 0, 0)
        folder_line.addWidget(self.output_folder_edit, 1)
        folder_line.addWidget(self.open_output_folder_button, 0)
        self.base_name_edit = QLineEdit(_tr("Video"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["copy", "h264"])
        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItems([
            _tr("Separate videos"),
            _tr("Combined grid"),
            _tr("Picture-in-picture"),
        ])
        self.output_mode_combo.setToolTip(_tr(
            "Separate videos: one file per source. Combined grid: one file with the sources "
            "side by side. Picture-in-picture: one file with source 1 full frame and the "
            "others as insets."
        ))
        self.output_mode_combo.currentTextChanged.connect(lambda _text: self.layout_preview_changed.emit())
        output_form.addRow("File location:", folder_line)
        output_form.addRow("File base name:", self.base_name_edit)
        output_form.addRow("Encoding:", self.codec_combo)
        output_form.addRow("Output mode:", self.output_mode_combo)
        self.duration_edit = QLineEdit("")
        self.duration_edit.setPlaceholderText(_tr("blank = until stopped"))
        output_form.addRow("Timer:", self.duration_edit)
        for field in (self.base_name_edit, self.codec_combo, self.output_mode_combo, self.duration_edit):
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.copy_mode_note = QLabel(
            _tr(
                "USB cameras and screen capture are always re-encoded to H.264; copy applies to RTSP and file sources."
            )
        )
        self.copy_mode_note.setWordWrap(True)
        self.copy_mode_note.setStyleSheet(
            theme.qss("color: $grey_650; font-size: 9pt;")
        )
        self.copy_mode_note.hide()
        output_form.addRow(self.copy_mode_note)
        self.codec_combo.currentTextChanged.connect(
            lambda _text: self.update_copy_mode_note()
        )
        for enabled, _label, type_combo, *_rest in self.source_rows:
            enabled.toggled.connect(lambda _checked: self.update_copy_mode_note())
            type_combo.currentIndexChanged.connect(
                lambda _index: self.update_copy_mode_note()
            )
        output_group.setLayout(output_form)
        self.output_group = output_group
        self.output_form = output_form
        layout.addWidget(self.groups_host)

        self.start_btn = QPushButton("")
        self.start_btn.setToolTip(_tr("Start recording"))
        self.start_btn.setFixedSize(44, 44)
        self.start_btn.setMaximumWidth(44)
        self.start_btn.setProperty("skipGlobalStyle", True)
        self.start_btn.setStyleSheet(theme.qss("""
            QPushButton {
                border-radius: 22px;
                background: $danger_deep;
                border: 3px solid $grey_280;
            }
            QPushButton:hover { background: $danger_mid; }
            QPushButton:disabled { background: $grey_500; }
        """))
        self.stop_btn = QPushButton(_tr("Stop Recording"))
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_recording)
        self.stop_btn.clicked.connect(self.stop_recording)
        self.status_label.hide()
        self.start_btn.hide()
        self.stop_btn.hide()

        self.update_button_style(self.button_style)
        self.apply_layout_mode(theme.metrics())
        self.update_copy_mode_note()
        self.update_start_availability()

    def any_row_enabled(self):
        return any(row[0].isChecked() for row in self.source_rows)

    def update_start_availability(self):
        """Start needs at least one enabled row; say so instead of failing later.

        Only touches the idle state: while recording (or stopping) the buttons
        and status line belong to the recording state machine.
        """
        if not hasattr(self, "start_btn") or self.processes or self.stop_btn.isEnabled():
            return
        if self.any_row_enabled():
            self.start_btn.setEnabled(True)
            if self.status_label.text() == _tr("Enable at least one source"):
                self.status_label.setText(_tr("Not recording"))
        else:
            self.start_btn.setEnabled(False)
            self.status_label.setText(_tr("Enable at least one source"))

    def _show_output_path_tail(self, _text=None):
        edit = self.output_folder_edit
        if not edit.hasFocus():
            edit.setCursorPosition(len(edit.text()))

    def groups_stacked(self):
        return isinstance(self.groups_layout, QVBoxLayout)

    def apply_layout_mode(self, metrics):
        """Stack recorder groups in compact mode and place them side by side in full mode."""
        # Tiles are uncapped in both modes (they fill what the groups leave);
        # `metrics.recorder_tile_max_h` is no longer applied.
        old = self.groups_layout
        if old is not None:
            old.removeWidget(self.source_group)
            old.removeWidget(self.output_group)
            QWidget().setLayout(old)
        # Output settings first (left / top); the properties table takes
        # whatever width is left so the output form keeps its natural size.
        # Both hang from the top: a box layout centres items of unequal
        # height, which is what left the properties table sitting lower.
        if metrics.recorder_stacked:
            new = QVBoxLayout(self.groups_host)
            new.addWidget(self.output_group, 0, Qt.AlignTop)
            new.addWidget(self.source_group, 0, Qt.AlignTop)
        else:
            new = QHBoxLayout(self.groups_host)
            new.setAlignment(Qt.AlignTop)
            new.addWidget(self.output_group, 0, Qt.AlignTop)
            new.addWidget(self.source_group, 1, Qt.AlignTop)
        new.setContentsMargins(0, 0, 0, 0)
        new.setSpacing(metrics.spacing * 2)
        self.groups_layout = new
        self.source_group.show()
        self.output_group.show()

    def update_copy_mode_note(self):
        usb_enabled = any(
            enabled.isChecked()
            and self._source_type_id(type_combo) in ("directshow", "screen")
            for enabled, _label, type_combo, *_rest in self.source_rows
        )
        self.copy_mode_note.setVisible(
            self.codec_combo.currentText() == "copy" and usb_enabled
        )

    def sizeHint(self):
        return QSize(640, 440)

    def minimumSizeHint(self):
        return QSize(520, 360)

    def active_preview_rows(self):
        return [index for index, source_row in enumerate(self.source_rows) if source_row[0].isChecked()]

    def current_layout_preview_rects(self):
        # Normalized tile rectangles for the current output mode + enabled source count,
        # used by the host to draw the output-layout schematic in the sidebar preview.
        return recording_layout_preview_rects(
            self.output_mode_combo.currentText(),
            len(self.active_preview_rows()),
        )

    def update_preview_panel_visibility(self):
        active_rows = self.active_preview_rows()
        for row_index, preview in enumerate(self.preview_boxes):
            self.preview_grid.removeWidget(preview)
            preview.setVisible(row_index in active_rows)
            if row_index < len(self.ptz_overlay_buttons):
                self.ptz_overlay_buttons[row_index].setVisible(
                    row_index in active_rows and self.ptz_overlay_buttons[row_index].isVisible()
                )
        total = len(active_rows)
        self.preview_grid.removeWidget(self.no_source_tile)
        self.no_source_tile.setVisible(total == 0)
        if total == 0:
            self.preview_grid.addWidget(self.no_source_tile, 0, 0, 1, 2)
        for display_index, row_index in enumerate(active_rows):
            preview = self.preview_boxes[row_index]
            if total == 1:
                position = (0, 0, 1, 2)
            elif total == 2:
                position = (0, display_index, 1, 1)
            elif total == 3 and display_index == 2:
                position = (1, 0, 1, 2)
            else:
                position = (display_index // 2, display_index % 2, 1, 1)
            self.preview_grid.addWidget(preview, *position)
            self.update_ptz_overlay_for_row(row_index)

    def update_button_style(self, button_style):
        self.button_style = button_style
        if button_style:
            for button in self.findChildren(QPushButton):
                button.setCursor(Qt.PointingHandCursor)
                if button.property("skipGlobalStyle"):
                    continue
                button.setStyleSheet(button_style)
        self.reskin()

    def reskin(self):
        """Links and glyph buttons follow the lock / converting skin like the bubbles do."""
        link = theme.link_button_style()
        accent = theme.skin().accent
        for widget, glyph in (
            (self.video_settings_link, "settings"),
            (self.recording_log_link, "log"),
        ):
            widget.setStyleSheet(link)
            set_link_glyph(widget, glyph, accent)
        reskin_icon_buttons(self, accent)

    def _source_type_id(self, combo):
        return combo.currentData() or "stream_url"

    def _source_type_for_text(self, combo, text):
        source_text = (text or "").strip().lower()
        if source_text.startswith("rtsp://"):
            return "rtsp_ip"
        if source_text.startswith(("http://", "https://")):
            return "stream_url"
        return self._source_type_id(combo)

    @staticmethod
    def _row_wants_preview(source_type, source_text):
        """True when a row of this type/text would start a live preview tile."""
        text = (source_text or "").strip()
        if source_type == "screen":
            return True  # empty text means the whole desktop
        if source_type in ("directshow", "rtsp_ip"):
            return bool(text)
        return False

    def update_source_placeholder(self, combo, edit, row_index=None, force_preview_restart=False):
        source_type = self._source_type_for_text(combo, edit.text())
        hints = {
            "rtsp_ip": "IP address, e.g. 192.168.0.10",
            "directshow": "Windows camera name, e.g. Logitech Camera",
            "basler_genicam": "Basler/pylon/GenICam source string",
            "stream_url": "rtsp://, http://, https://, or mjpeg URL",
            "screen": "desktop, monitor=1 (GPU), region=X,Y,WxH, or a window title",
            "file": "Local test file path",
        }
        edit.setPlaceholderText(hints.get(source_type, "FFmpeg source"))
        if row_index is not None and not self._row_wants_preview(source_type, edit.text()):
            # The row no longer describes anything previewable ("No source
            # selected...", a file, a plain stream URL). Whatever it was
            # previewing before -- a camera, the desktop -- must stop now, or
            # the old ffmpeg keeps the camera open (light on) and the tile
            # keeps showing the old picture.
            self.stop_preview_for_row(row_index)
        if source_type == "directshow":
            self.populate_directshow_devices(edit)
            if row_index is not None:
                self.start_directshow_preview(row_index, edit.text(), force_preview_restart)
        elif source_type == "rtsp_ip" and row_index is not None and edit.text():
            self.start_stream_preview(
                row_index,
                build_source_text(source_type, edit.text()),
                force_preview_restart,
            )
        elif source_type == "screen" and row_index is not None:
            # No address needed: an empty field means the whole desktop.
            self.start_stream_preview(
                row_index,
                build_source_text(source_type, edit.text()),
                force_preview_restart,
            )
        if row_index is not None and 0 <= row_index < len(self.preview_boxes):
            labels = {
                "rtsp_ip": "RTSP/IP",
                "directshow": "USB / DirectShow",
                "basler_genicam": "Basler / GenICam",
                "stream_url": "Stream URL",
                "screen": "Screen capture",
                "file": "File / Test",
            }
            self.preview_boxes[row_index].setText(
                _tr("Video %(number)s\n%(kind)s\nConfigure the source")
                % {"number": row_index + 1,
                   "kind": labels.get(source_type, _tr("Source"))})
            if source_type == "directshow" and edit.text():
                self.preview_boxes[row_index].setText(
                    _tr("Video %(number)s\n%(source)s\nOpening preview...")
                    % {"number": row_index + 1, "source": edit.text()})
            elif source_type == "rtsp_ip" and edit.text():
                self.preview_boxes[row_index].setText(
                    _tr("Video %(number)s\nRTSP/IP\nOpening preview...")
                    % {"number": row_index + 1})
            elif source_type == "screen":
                self.preview_boxes[row_index].setText(
                    _tr("Video %(number)s\nScreen capture\nOpening preview...")
                    % {"number": row_index + 1})
            self.update_ptz_overlay_for_row(row_index)

    def populate_directshow_devices(self, source_edit):
        """Offer the cameras we know about now and refresh them in the background.

        Never scans inline: a listing takes several seconds on a machine with
        a few virtual cameras, and this runs while the user is picking a
        source type or while saved settings load at startup.

        Never fills an empty field either. "No source selected..." in Video
        Settings arrives here as "", and auto-picking the first known camera
        would switch that camera straight back on.
        """
        if hasattr(source_edit, "set_options"):
            source_edit.set_options(list(self.directshow_devices or []), auto_select=False)
        self.start_device_discovery()

    def discover_directshow_devices(self):
        """Blocking listing, kept for callers that explicitly want to wait."""
        if not self.directshow_devices:
            self.directshow_devices = discover_directshow_video_devices(resource_path("ffmpeg.exe"))
        return self.directshow_devices

    def device_scan_is_fresh(self):
        if self.last_device_scan_ok is not True or self.last_device_scan_at is None:
            return False
        return (time.monotonic() - self.last_device_scan_at) < self.DEVICE_SCAN_TTL_S

    def start_device_discovery(self, force=False):
        """List cameras and microphones off the GUI thread.

        Returns True when a scan was started. A fresh result is reused unless
        `force`; a scan already in flight is never doubled up.
        """
        if self.device_discovery_running:
            return False
        if not force and self.device_scan_is_fresh():
            return False
        self.device_discovery_running = True
        self.device_scan_started.emit()

        def discover():
            ffmpeg = resource_path("ffmpeg.exe")
            try:
                scan = discover_directshow_devices(ffmpeg)
            except Exception:
                logger.warning("Device listing failed", exc_info=True)
                scan = DeviceScan([], [], False)
            if sip.isdeleted(self):
                return          # the recorder was closed while the listing ran
            self._deliver_device_scan(scan)
            # Same background pass: which hardware H.264 encoder starts here
            # (cached, so only the first scan pays the ~1 s).
            try:
                encoder = probe_hardware_h264_encoder(ffmpeg)
            except Exception:
                logger.warning("Hardware encoder probe failed", exc_info=True)
                encoder = ""
            if sip.isdeleted(self):
                return
            try:
                self.hardware_encoder_detected.emit(encoder)
            except RuntimeError:
                pass

        self._run_in_background(discover)
        return True

    def _apply_hardware_encoder(self, encoder):
        if not encoder:
            # The probe is cached per ffmpeg path, so an empty result arriving
            # after a positive one is a stale scan, not a change of hardware.
            return
        if encoder != self.hardware_h264_encoder:
            self._append_log(f"[encoder] screen captures will use {encoder}; cameras keep their current encoding")
        self.hardware_h264_encoder = encoder

    # Alias kept for the Video Settings dialog and older call sites.
    def start_audio_device_discovery(self, force=False):
        return self.start_device_discovery(force=force)

    @staticmethod
    def _run_in_background(fn):
        threading.Thread(target=fn, daemon=True).start()

    def _deliver_device_scan(self, scan):
        try:
            self.device_scan_finished.emit(scan)
        except RuntimeError:
            logger.debug(
                "Recorder closed before device discovery completed",
                exc_info=True,
            )

    def _apply_device_scan(self, scan):
        self.device_discovery_running = False
        self.last_device_scan_ok = bool(scan.ok)
        self.last_device_scan_at = time.monotonic()
        if not scan.ok:
            # ffmpeg missing, crashed or timed out: the machine has not lost
            # its cameras, we just could not ask. Keep what we had.
            return
        self.directshow_devices = list(scan.video)
        self.directshow_audio_devices = list(scan.audio)
        for source_row in self.source_rows:
            type_combo, source_edit, audio_combo = source_row[2], source_row[3], source_row[7]
            self.populate_audio_device_combo(audio_combo, self._audio_device_value(audio_combo))
            if self._source_type_id(type_combo) == "directshow" and hasattr(source_edit, "set_options"):
                source_edit.set_options(self.directshow_devices, auto_select=False)
        self.video_devices_discovered.emit(list(self.directshow_devices))
        self.audio_devices_discovered.emit(list(self.directshow_audio_devices))

    @staticmethod
    def _audio_device_value(combo):
        return (
            str(combo.currentData() or combo.currentText())
            .removesuffix(" (not found)")
            .strip()
        )

    def populate_audio_device_combo(self, combo, stored_device=""):
        selected = (
            str(stored_device or "")
            .removesuffix(" (not found)")
            .strip()
        )
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_tr("No Audio"), "No Audio")
        for device in self.directshow_audio_devices:
            combo.addItem(device, device)
        if (
            selected
            and selected != "No Audio"
            and selected not in self.directshow_audio_devices
        ):
            combo.addItem(
                _tr("%(device)s (not found)") % {"device": selected},
                selected,
            )
        target = combo.findData(selected or "No Audio")
        combo.setCurrentIndex(max(0, target))
        combo.blockSignals(False)

    @staticmethod
    def _deliver_modes(callback, modes):
        """Hand detected camera modes back to whoever asked for them.

        The requester is the Video Settings dialog, which the user may have
        closed in the meantime -- on the cached path while a signal is still
        being delivered, or seconds later when the ffmpeg probe finishes.
        Writing into its deleted widgets raises RuntimeError, and an exception
        escaping a Qt slot makes PyQt call qFatal() and abort the process. The
        modes are cached either way, so the next open picks them up.
        """
        try:
            callback(modes)
        except RuntimeError:
            logger.debug("Video Settings dialog closed before modes arrived",
                         exc_info=True)

    def start_directshow_mode_detection(self, device_name, callback):
        cache_key = f"directshow:{device_name}"
        if cache_key in self.camera_mode_cache:
            self._deliver_modes(callback, self.camera_mode_cache[cache_key])
            return
        command = build_directshow_list_options_command(resource_path("ffmpeg.exe"), device_name)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        self.camera_mode_processes.append(process)

        def finish_detection(_exit_code=0, _status=None, p=process, key=cache_key):
            try:
                output = bytes(p.readAllStandardOutput()).decode(errors="replace")
            except RuntimeError:
                output = ""
            modes = parse_directshow_video_options(output)
            self.camera_mode_cache[key] = modes
            self.camera_mode_processes = [item for item in self.camera_mode_processes if item is not p]
            self._deliver_modes(callback, modes)

        process.finished.connect(finish_detection)
        process.start(command[0], command[1:])

    def start_directshow_preview(self, row_index, device_name, force_restart=False):
        if not self.auto_preview or row_index < 0 or row_index >= len(self.preview_boxes):
            return
        device = (device_name or "").strip()
        if not device:
            return
        existing = self.preview_processes.get(row_index)
        if (
            existing
            and existing.state() != QProcess.NotRunning
            and self.preview_sources.get(row_index) == ("directshow", device, self.preview_source_profile)
            and not force_restart
        ):
            return
        if existing and existing.state() != QProcess.NotRunning:
            existing.kill()
        self.clear_preview_backlog([row_index])
        use_selected_options = row_index not in self.preview_auto_mode_rows and not self._is_basler_genicam_source(device)
        options = self.recording_options_for_row(row_index) if use_selected_options else {}
        command = build_directshow_preview_stream_command(
            resource_path("ffmpeg.exe"),
            device,
            frame_rate=options.get("frame_rate", ""),
            resolution=options.get("resolution", ""),
        )
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(lambda p=process, row=row_index: self._read_preview_frames(p, row))
        process.readyReadStandardError.connect(lambda p=process, row=row_index: self._read_preview_output(p, row))
        process.finished.connect(lambda exit_code, _status, row=row_index, p=process: self._preview_finished(row, exit_code, p))
        process.preview_requested_options = use_selected_options
        process.preview_error_text = ""
        self.preview_processes[row_index] = process
        self.preview_sources[row_index] = ("directshow", device, self.preview_source_profile)
        self.preview_buffers[row_index] = bytearray()
        self.preview_frame_logged_rows.discard(row_index)
        self.preview_render_logged_rows.discard(row_index)
        process.start(command[0], command[1:])

    def start_stream_preview(self, row_index, source, force_restart=False):
        if not self.auto_preview or row_index < 0 or row_index >= len(self.preview_boxes):
            return
        source_text = (source or "").strip()
        if not source_text:
            return
        existing = self.preview_processes.get(row_index)
        if (
            existing
            and existing.state() != QProcess.NotRunning
            and self.preview_sources.get(row_index) == ("stream", source_text, self.preview_source_profile)
            and not force_restart
        ):
            return
        if existing and existing.state() != QProcess.NotRunning:
            existing.kill()
        self.clear_preview_backlog([row_index])
        preview_source_text = axis_mjpeg_preview_url(source_text) or source_text
        command = build_preview_stream_command(resource_path("ffmpeg.exe"), preview_source_text)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(lambda p=process, row=row_index: self._read_preview_frames(p, row))
        process.readyReadStandardError.connect(lambda p=process, row=row_index: self._read_preview_output(p, row))
        process.finished.connect(lambda exit_code, _status, row=row_index, p=process: self._preview_finished(row, exit_code, p))
        self.preview_processes[row_index] = process
        self.preview_sources[row_index] = ("stream", source_text, self.preview_source_profile)
        self.preview_buffers[row_index] = bytearray()
        self.preview_frame_logged_rows.discard(row_index)
        self.preview_render_logged_rows.discard(row_index)
        process.start(command[0], command[1:])

    def is_directshow_source(self, source):
        return (source or "").strip().lower().startswith(("video=", "audio="))

    def can_preview_separately_while_recording(self, source):
        # Network streams and the desktop have no exclusive-device lock, so the idle
        # preview process can keep running next to the recording process.
        source_text = (source or "").strip().lower()
        return source_text.startswith(("rtsp://", "http://", "https://", "screen="))

    def source_for_row(self, row_index):
        if row_index < 0 or row_index >= len(self.source_rows):
            return ""
        _enabled, _label, type_combo, source_edit = self.source_rows[row_index][:4]
        return build_source_text(self._source_type_for_text(type_combo, source_edit.text()), source_edit.text().strip())

    def update_ptz_overlay_for_row(self, row_index):
        if row_index < 0 or row_index >= len(self.ptz_overlay_buttons):
            return
        button = self.ptz_overlay_buttons[row_index]
        source = self.source_for_row(row_index)
        if source.lower().startswith("rtsp://"):
            preview = self.preview_boxes[row_index]
            button.move((preview.width() - button.width()) // 2, max(4, (preview.height() - button.height()) // 2))
            button.show()
            button.raise_()
        else:
            button.hide()

    def send_ptz_for_row(self, row_index, move):
        source = self.source_for_row(row_index)
        if source.lower().startswith("rtsp://"):
            self.axis_ptz_move(source, move)

    def _read_preview_output(self, process, row_index):
        try:
            data = bytes(process.readAllStandardError()).decode(errors="replace")
        except RuntimeError:
            return
        if data:
            for line in data.splitlines():
                process.preview_error_text = (getattr(process, "preview_error_text", "") + "\n" + line)[-4000:]
                self._append_log(f"[preview {row_index + 1}] {line}")

    def clear_preview_backlog(self, rows=None):
        if rows is None:
            self.preview_buffers = {}
            self.preview_pending_frames = {}
            self.combined_preview_pending_frame = None
            return
        for row_index in rows:
            self.preview_buffers[row_index] = bytearray()
            self.preview_pending_frames.pop(row_index, None)
        if "combined" in rows:
            self.combined_preview_pending_frame = None

    def _read_preview_frames(self, process, row_index):
        buffer = self.preview_buffers.setdefault(row_index, bytearray())
        try:
            buffer.extend(bytes(process.readAllStandardOutput()))
        except RuntimeError:
            return
        while True:
            start = buffer.find(b"\xff\xd8")
            end = buffer.find(b"\xff\xd9", start + 2)
            if start < 0 or end < 0:
                if len(buffer) > 2_000_000:
                    del buffer[:-2]
                return
            frame = bytes(buffer[start:end + 2])
            del buffer[:end + 2]
            self.preview_pending_frames[row_index] = frame
            if row_index not in self.preview_frame_logged_rows:
                self.preview_frame_logged_rows.add(row_index)
                self._append_log(f"[preview {row_index + 1}] received first MJPEG frame ({len(frame)} bytes)")
            self.preview_retry_attempts.pop(row_index, None)

    def _read_combined_preview_frames(self, process):
        buffer = self.preview_buffers.setdefault("combined", bytearray())
        try:
            buffer.extend(bytes(process.readAllStandardOutput()))
        except RuntimeError:
            return
        while True:
            start = buffer.find(b"\xff\xd8")
            end = buffer.find(b"\xff\xd9", start + 2)
            if start < 0 or end < 0:
                if len(buffer) > 2_000_000:
                    del buffer[:-2]
                return
            frame = bytes(buffer[start:end + 2])
            del buffer[:end + 2]
            self.combined_preview_pending_frame = frame

    def _render_pending_preview_frames(self):
        # Wrap the whole render pass in a RuntimeError guard so we degrade gracefully if the
        # underlying QWidget/QLabel children have already been destroyed by Qt (this can
        # happen during test teardown where many widgets accumulate and timers may fire
        # after the C++ side has been torn down).
        try:
            combined_frame = self.combined_preview_pending_frame
            self.combined_preview_pending_frame = None
            if combined_frame:
                pixmap = QPixmap()
                if pixmap.loadFromData(combined_frame, "JPG"):
                    self._render_combined_preview_pixmap(pixmap)
            pending = self.preview_pending_frames
            self.preview_pending_frames = {}
            for row_index, frame in pending.items():
                pixmap = QPixmap()
                if pixmap.loadFromData(frame, "JPG") and row_index < len(self.preview_boxes):
                    if row_index not in self.preview_render_logged_rows:
                        self.preview_render_logged_rows.add(row_index)
                        average_luma = self._preview_frame_average_luma(pixmap)
                        self._append_log(
                            f"[preview {row_index + 1}] rendered first frame "
                            f"{pixmap.width()}x{pixmap.height()} avg_luma={average_luma:.1f}"
                        )
                    self.preview_boxes[row_index].setPixmap(
                        pixmap.scaled(self.preview_boxes[row_index].contentsRect().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
        except RuntimeError:
            return

    def _preview_frame_average_luma(self, pixmap):
        image = pixmap.toImage()
        if image.isNull():
            return 0.0
        sample = image.scaled(32, 32, Qt.KeepAspectRatio, Qt.FastTransformation)
        total = 0
        count = 0
        for y in range(sample.height()):
            for x in range(sample.width()):
                color = sample.pixelColor(x, y)
                total += (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
                count += 1
        return total / count if count else 0.0

    def _combined_preview_crop_rect(self, index, total, width, height):
        if total <= 1:
            return (0, 0, width, height)
        if total == 2:
            crop_width = width // 2
            return (index * crop_width, 0, crop_width, height)
        crop_width = width // 2
        crop_height = height // 2
        return ((index % 2) * crop_width, (index // 2) * crop_height, crop_width, crop_height)

    def _render_combined_preview_pixmap(self, pixmap):
        rows = [row for row in self.combined_preview_rows if row < len(self.preview_boxes)]
        total = len(rows)
        if not rows:
            return
        for index, row_index in enumerate(rows):
            x, y, width, height = self._combined_preview_crop_rect(index, total, pixmap.width(), pixmap.height())
            cropped = pixmap.copy(x, y, width, height)
            self.preview_boxes[row_index].setPixmap(
                cropped.scaled(self.preview_boxes[row_index].contentsRect().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def _preview_finished(self, row_index, exit_code, process=None):
        if row_index < 0 or row_index >= len(self.preview_boxes):
            return
        if process is not None and self.preview_processes.get(row_index) is not process:
            # A preview we already dropped (stop_preview_for_row pops it before
            # killing) has now actually exited: that consumes its "stopping"
            # mark, otherwise the row's next preview would skip one retry.
            self.preview_stopping_rows.discard(row_index)
            return
        self.clear_preview_backlog([row_index])
        if row_index in self.preview_stopping_rows:
            self.preview_stopping_rows.discard(row_index)
            return
        source_info = self.preview_sources.get(row_index)
        if source_info:
            self.preview_processes.pop(row_index, None)
            if (
                source_info[0] == "directshow"
                and getattr(process, "preview_requested_options", False)
                and "could not set video options" in getattr(process, "preview_error_text", "").lower()
            ):
                self.preview_auto_mode_rows.add(row_index)
            if (
                source_info[0] == "directshow"
                and self._directshow_device_unavailable_error(getattr(process, "preview_error_text", ""))
                and not self._is_basler_genicam_source(source_info[1] if len(source_info) > 1 else "")
            ):
                self.preview_boxes[row_index].setText(
                    _tr("Video %(number)s\n"
                        "Camera is not available as a DirectShow video device\n"
                        "Refresh devices or check pylon/GenICam setup")
                    % {"number": row_index + 1}
                )
                return
            if (
                source_info[0] == "stream"
                and self._unresolvable_host_error(getattr(process, "preview_error_text", ""))
            ):
                # DNS failed for the address itself (typically a mistyped IP).
                # Reconnecting cannot help; editing the source restarts the preview.
                self.preview_boxes[row_index].setText(
                    _tr("Video %(number)s\n"
                        "Cannot resolve the camera address\n"
                        "Check the IP in Video Settings")
                    % {"number": row_index + 1}
                )
                return
            self.preview_boxes[row_index].setText(
                _tr("Video %(number)s\nPreview interrupted\nReconnecting...")
                % {"number": row_index + 1})
            self._schedule_preview_retry(row_index, source_info)
        elif exit_code:
            self.preview_boxes[row_index].setText(
                _tr("Video %(number)s\nPreview unavailable\nCamera may be in use")
                % {"number": row_index + 1}
            )

    @staticmethod
    def _unresolvable_host_error(text):
        return "failed to resolve hostname" in (text or "").lower()

    def _directshow_device_unavailable_error(self, text):
        error_text = (text or "").lower()
        return (
            "unable to bindtoobject" in error_text
            or "could not find video device" in error_text
            or "among source devices of type video" in error_text
        )

    def _is_basler_genicam_source(self, source):
        return "basler genicam source" in (source or "").lower()

    def _schedule_preview_retry(self, row_index, source_info):
        attempts = self.preview_retry_attempts.get(row_index, 0)
        self.preview_retry_attempts[row_index] = attempts + 1
        delay_ms = min(1000 * (2 ** attempts), 10000)
        self._schedule(delay_ms, lambda row=row_index, info=source_info: self._retry_preview(row, info))

    def _retry_preview(self, row_index, source_info):
        if self.preview_sources.get(row_index) != source_info:
            return
        current = self.preview_processes.get(row_index)
        try:
            if current and current.state() != QProcess.NotRunning:
                return
        except RuntimeError:
            pass
        source_kind = source_info[0] if len(source_info) > 0 else ""
        source_value = source_info[1] if len(source_info) > 1 else ""
        if source_kind == "directshow":
            self.start_directshow_preview(row_index, source_value, force_restart=True)
        elif source_kind == "stream":
            self.start_stream_preview(row_index, source_value, force_restart=True)

    def _kill_preview_process(self, row_index, process):
        """End a preview ffmpeg for good.

        QProcess.terminate() posts WM_CLOSE to the process's windows on
        Windows; ffmpeg.exe has none, so a terminated preview simply keeps
        running -- camera light on, tile still updating -- while we have
        already forgotten about it. A preview writes JPEGs to a pipe and has
        nothing to flush, so kill() is the right call, not an escalation.
        """
        try:
            if process.state() != QProcess.NotRunning:
                self.preview_stopping_rows.add(row_index)
                process.kill()
        except RuntimeError:
            pass

    def stop_preview_processes(self):
        for row_index, process in list(self.preview_processes.items()):
            self._kill_preview_process(row_index, process)
        self.preview_processes = {}
        self.preview_buffers = {}
        self.preview_pending_frames = {}
        self.preview_sources = {}
        self.preview_retry_attempts = {}
        self.preview_auto_mode_rows = set()

    def _schedule(self, msec, callback):
        """Run `callback` after `msec`, but only while this widget lives.

        `QTimer.singleShot` is a static method: the timer it creates belongs to
        nobody, so it still fires after this widget has been destroyed. The
        callback then touches a deleted C++ object and raises -- and an
        exception that escapes a Qt slot makes PyQt call qFatal(), which aborts
        the process outright (STATUS_STACK_BUFFER_OVERRUN, 0xC0000409) with no
        traceback on stderr. Closing NVC within a few seconds of pressing Stop
        was enough to hit it, because stop_recording schedules terminate and
        kill escalations 1.5s and 3s out.

        A QTimer parented to `self` is destroyed with `self`, so the callback
        is simply cancelled instead.
        """
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(msec)
        return timer

    def shutdown(self):
        self.pending_recording_start = None
        terminate_device_probes()
        self.record_start_timer.stop()
        self.record_start_watchdog_timer.stop()
        self.preview_render_timer.stop()
        # camera_mode_processes belongs here too: picking a camera in Video
        # Settings starts an ffmpeg probe whose finished handler writes back
        # into the dialog. Left running, it fires after the dialog and this
        # widget are gone, which aborts the process (0xC0000409) rather than
        # raising anything catchable.
        for process in (list(self.preview_processes.values())
                        + list(self.processes)
                        + list(self.camera_mode_processes)):
            try:
                if process.state() != QProcess.NotRunning:
                    process.kill()
            except RuntimeError:
                continue
        self.camera_mode_processes = []
        self.preview_processes = {}
        self.preview_buffers = {}
        self.preview_pending_frames = {}
        self.preview_sources = {}
        self.preview_retry_attempts = {}
        self.preview_auto_mode_rows = set()
        self.processes = []
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(_tr("Not recording"))

    def release_preview_processes_for_recording(self, selected=None):
        # If no selection is provided, fall back to releasing every running preview. This
        # legacy path keeps internal callers that just want to free all cameras working.
        # When ``selected`` is supplied, only previews whose source cannot be shared
        # with the recording process (DirectShow devices) are released. RTSP/HTTP
        # previews stay alive because the recording process for those sources is a
        # plain stream copy and does not pipe its own preview frames - killing the
        # preview here would leave the tile frozen for the whole recording.
        if selected is None:
            drop_rows = set(self.preview_processes.keys())
        else:
            drop_rows = {
                row_index
                for row_index, _label, source, *_options in selected
                if not self.can_preview_separately_while_recording(source)
            }
        released_any_preview = False
        for row_index, process in list(self.preview_processes.items()):
            if row_index not in drop_rows:
                continue
            try:
                if process.state() != QProcess.NotRunning:
                    released_any_preview = True
                    self.preview_stopping_rows.add(row_index)
                    if hasattr(process, "terminate"):
                        process.terminate()
                        finished = process.waitForFinished(750) if hasattr(process, "waitForFinished") else True
                        if not finished and process.state() != QProcess.NotRunning:
                            process.kill()
                    else:
                        process.kill()
            except RuntimeError:
                continue
            self.preview_paused_rows.add(row_index)
            if row_index < len(self.preview_boxes):
                self.preview_boxes[row_index].clear()
                if any(
                    selected_row == row_index and self._is_basler_genicam_source(source)
                    for selected_row, _label, source, *_options in (selected or [])
                ):
                    self.preview_boxes[row_index].setText(
                        _tr("Video %(number)s\nRecording\nStarting live preview...")
                        % {"number": row_index + 1}
                    )
            self._append_log(f"[preview {row_index + 1}] paused for recording")
        self.preview_processes = {
            row_index: process
            for row_index, process in self.preview_processes.items()
            if row_index not in drop_rows
        }
        self.preview_buffers = {
            row_index: buffer
            for row_index, buffer in self.preview_buffers.items()
            if row_index not in drop_rows
        }
        self.preview_pending_frames = {
            row_index: frame
            for row_index, frame in self.preview_pending_frames.items()
            if row_index not in drop_rows
        }
        self.preview_sources = {
            row_index: source
            for row_index, source in self.preview_sources.items()
            if row_index not in drop_rows
        }
        self.preview_retry_attempts = {
            row_index: attempts
            for row_index, attempts in self.preview_retry_attempts.items()
            if row_index not in drop_rows
        }
        self.preview_auto_mode_rows = {
            row_index for row_index in self.preview_auto_mode_rows if row_index not in drop_rows
        }
        return released_any_preview

    def open_directshow_camera_settings(self, device_name):
        device = (device_name or "").strip()
        if not device:
            QMessageBox.information(self, _tr("Camera Settings"), _tr("Select a USB / DirectShow camera first."))
            return
        command = build_directshow_camera_settings_command(resource_path("ffmpeg.exe"), device)
        QProcess.startDetached(command[0], command[1:])

    def find_pylon_viewer(self):
        roots = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        patterns = []
        for root in [path for path in roots if path]:
            patterns.extend([
                os.path.join(root, "Basler", "pylon*", "Applications", "*", "PylonViewerApp.exe"),
                os.path.join(root, "Basler", "pylon*", "Applications", "PylonViewerApp.exe"),
                os.path.join(root, "Basler", "pylon*", "Runtime", "*", "PylonViewerApp.exe"),
                os.path.join(root, "Basler", "*", "PylonViewerApp.exe"),
            ])
        for pattern in patterns:
            matches = sorted(glob.glob(pattern), reverse=True)
            if matches:
                return matches[0]
        return ""

    def open_basler_camera_settings(self, device_name):
        viewer = self.find_pylon_viewer()
        if viewer:
            QProcess.startDetached(viewer, [])
            self._append_log(f"[Basler] opened pylon Viewer for {device_name or 'camera settings'}")
            return
        QMessageBox.information(
            self,
            _tr("Basler Camera Settings"),
            _tr("Basler / GenICam settings are managed in Basler pylon Viewer.\n\n"
            "The FFmpeg DirectShow property dialog does not reliably open Basler camera controls and can "
            "produce BindToObject errors while NVC is previewing the camera.\n\n"
            "Open pylon Viewer to adjust exposure, gain, trigger mode, pixel format, and camera defaults."),
        )

    def output_controls(self):
        return {
            "output_folder": self.output_folder_edit,
            "base_name": self.base_name_edit,
            "codec": self.codec_combo,
            "output_mode": self.output_mode_combo,
            "duration": self.duration_edit,
            "quality": self.output_quality,
        }

    def capture_recorder_settings(self):
        channels = []
        for source_row in self.source_rows:
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            audio_name_edit, mute_check, volume_combo = source_row[4:7]
            audio_device_combo, frame_rate_combo, resolution_combo = source_row[7:10]
            offset_spin = source_row[10] if len(source_row) > 10 else None
            channels.append({
                "enabled": enabled.isChecked(),
                "video_name": label_edit.text(),
                "source_type": self._source_type_id(type_combo),
                "source": source_edit.text(),
                "audio_name": audio_name_edit.text(),
                "audio_device": self._audio_device_value(audio_device_combo),
                "mute": mute_check.isChecked(),
                "volume": volume_combo.currentText(),
                "frame_rate": frame_rate_combo.currentText(),
                "resolution": resolution_combo.currentText(),
                "sync_offset": f"{offset_spin.value():.2f}" if offset_spin is not None else "0.00",
            })
        return normalize_recorder_settings({
            "output": {
                "folder": self.output_folder_edit.text(),
                "base_name": self.base_name_edit.text(),
                "encoding": self.codec_combo.currentText(),
                "mode": self.output_mode_combo.currentText(),
                "quality": self.output_quality,
            },
            "timer": {
                "duration": self.duration_edit.text(),
            },
            "channels": channels,
        })

    def apply_recorder_settings(self, settings, refresh_previews=True):
        normalized = normalize_recorder_settings(settings)
        output = normalized.get("output", {})
        timer = normalized.get("timer", {})
        self.output_folder_edit.setText(output.get("folder", self.output_folder_edit.text()))
        self.base_name_edit.setText(output.get("base_name", self.base_name_edit.text()))
        self.codec_combo.setCurrentText(output.get("encoding", self.codec_combo.currentText()))
        self.output_mode_combo.setCurrentText(output.get("mode", self.output_mode_combo.currentText()))
        self.output_quality = output.get("quality", self.output_quality)
        self.duration_edit.setText(timer.get("duration", self.duration_edit.text()))
        for index, channel in enumerate(normalized.get("channels", [])):
            if index >= len(self.source_rows):
                break
            source_row = self.source_rows[index]
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            audio_name_edit, mute_check, volume_combo = source_row[4:7]
            audio_device_combo, frame_rate_combo, resolution_combo = source_row[7:10]
            offset_spin = source_row[10] if len(source_row) > 10 else None
            enabled.setChecked(bool(channel.get("enabled", enabled.isChecked())))
            label_edit.setText(channel.get("video_name", label_edit.text()))
            channel = self._redirect_hidden_capture_filter(channel, index)
            type_index = type_combo.findData(channel.get("source_type"))
            if type_index >= 0:
                type_combo.blockSignals(True)
                type_combo.setCurrentIndex(type_index)
                type_combo.blockSignals(False)
            source_edit.setText(channel.get("source", source_edit.text()))
            audio_name_edit.setText(channel.get("audio_name", audio_name_edit.text()))
            self.populate_audio_device_combo(
                audio_device_combo,
                channel.get(
                    "audio_device",
                    self._audio_device_value(audio_device_combo),
                ),
            )
            mute_check.setChecked(bool(channel.get("mute", mute_check.isChecked())))
            volume_combo.setCurrentText(channel.get("volume", volume_combo.currentText()))
            frame_rate_combo.setCurrentText(channel.get("frame_rate", frame_rate_combo.currentText()))
            resolution_combo.setCurrentText(channel.get("resolution", resolution_combo.currentText()))
            if offset_spin is not None and "sync_offset" in channel:
                try:
                    offset_spin.setValue(float(channel.get("sync_offset") or 0.0))
                except (TypeError, ValueError):
                    offset_spin.setValue(0.0)
            if refresh_previews:
                self.update_source_placeholder(type_combo, source_edit, index)

    def _redirect_hidden_capture_filter(self, channel, index):
        """Presets that name a licensed DirectShow capture filter use the built-in screen source.

        The filter is no longer listed (it pops a licence dialog inside ffmpeg and
        blocks the recording), and a preset written by MediaRecorder or an older
        NVC may still refer to it.
        """
        source = str(channel.get("source", "") or "")
        if not is_hidden_directshow_video_device(source):
            return channel
        self._append_log(
            f"[Video_{index + 1}] \"{source}\" is a licensed capture filter and is not offered; "
            "using the built-in screen capture instead"
        )
        redirected = dict(channel)
        redirected["source_type"] = "screen"
        redirected["source"] = SCREEN_DEFAULT_TARGET
        return redirected

    def recorder_settings_path(self):
        if os.name == "nt":
            public_root = os.environ.get("PUBLIC", r"C:\Users\Public")
            return os.path.join(public_root, "Documents", "Noldus", "NVC", "MediaRecorder", "Current Settings.json")
        return os.path.join(os.path.expanduser("~"), ".nvc", "MediaRecorder", "Current Settings.json")

    def recorder_presets_dir(self):
        return os.path.join(os.path.dirname(self.recorder_settings_path()), "Presets")

    def recorder_preset_path(self, name):
        return preset_file_path(self.recorder_presets_dir(), name)

    def list_recorder_presets(self):
        return list_recorder_presets(self.recorder_presets_dir())

    def save_named_recorder_preset(self, name):
        settings = self.capture_recorder_settings()
        save_recorder_settings(self.recorder_preset_path(name), settings)
        return settings

    def load_named_recorder_preset(self, name):
        settings = load_recorder_settings(self.recorder_preset_path(name))
        self.apply_recorder_settings(settings)
        self.refresh_previews_from_sources()
        self.save_current_recorder_settings()
        return settings

    def delete_named_recorder_preset(self, name):
        path = self.recorder_preset_path(name)
        if os.path.exists(path):
            os.remove(path)

    def _send_axis_ptz_url(self, url):
        if not url:
            return
        threading.Thread(
            target=self._dispatch_axis_ptz_request,
            args=(url,),
            daemon=True,
        ).start()

    def _dispatch_axis_ptz_request(self, url):
        try:
            send_axis_vapix_request(url)
        except Exception as exc:
            self._append_log(f"[ptz] request failed: {exc} url={url}")

    def axis_ptz_move(self, source, move):
        if move in ("stop", "home"):
            action = move
        elif move in ("zoom_in", "zoom_out"):
            action = move
        else:
            action = "move"
        url = axis_vapix_ptz_url(source, action, move=move)
        self._append_log(f"[ptz] move={move} url={url}")
        self._send_axis_ptz_url(url)

    def axis_ptz_continuous(self, source, pan=None, tilt=None, zoom=None):
        url = axis_vapix_continuous_url(source, pan=pan, tilt=tilt, zoom=zoom)
        if not url:
            return
        self._append_log(
            f"[ptz] continuous pan={pan} tilt={tilt} zoom={zoom} url={url}"
        )
        self._send_axis_ptz_url(url)

    def axis_ptz_goto_preset(self, source, preset_name):
        if preset_name:
            url = axis_vapix_ptz_url(source, "goto_preset", preset_name=preset_name)
            self._append_log(f"[ptz] goto_preset={preset_name} url={url}")
            self._send_axis_ptz_url(url)

    def axis_ptz_set_preset(self, source, preset_name):
        if preset_name:
            url = axis_vapix_ptz_url(source, "set_preset", preset_name=preset_name)
            self._append_log(f"[ptz] set_preset={preset_name} url={url}")
            self._send_axis_ptz_url(url)

    def axis_ptz_presets(self, source):
        url = axis_vapix_ptz_url(source, "list_presets")
        try:
            response = send_axis_vapix_request(url)
        except Exception as exc:
            self._append_log(f"[ptz] preset refresh failed: {exc} url={url}")
            return []
        return parse_axis_ptz_presets(response)

    def save_current_recorder_settings(self):
        save_recorder_settings(self.recorder_settings_path(), self.capture_recorder_settings())

    def load_current_recorder_settings(self):
        try:
            refresh_previews = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
            self.apply_recorder_settings(
                load_recorder_settings(self.recorder_settings_path()),
                refresh_previews=refresh_previews,
            )
        except Exception as exc:
            self._append_log(f"[recorder] could not load settings: {exc}")

    def open_video_settings(self, row_index=None):
        dialog = VideoSettingsDialog(self.source_rows, self.output_controls(), self, self.button_style)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh_previews_from_sources()

    def build_recording_log_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_tr("Recording Log"))
        layout = QVBoxLayout(dialog)
        log_edit = QPlainTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setPlainText("\n".join(self.log_lines))
        layout.addWidget(log_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        return dialog

    def show_recording_log(self):
        self.build_recording_log_dialog().exec_()

    def refresh_previews_from_sources(self, force_restart=True):
        self.update_preview_panel_visibility()
        for index, source_row in enumerate(self.source_rows):
            enabled, _label, type_combo, source_edit = source_row[:4]
            if not enabled.isChecked():
                self.stop_preview_for_row(index)
                continue
            self.update_source_placeholder(
                type_combo,
                source_edit,
                index,
                force_preview_restart=force_restart,
            )

    def stop_preview_for_row(self, row_index):
        process = self.preview_processes.pop(row_index, None)
        if process is not None:
            self._kill_preview_process(row_index, process)
        self.preview_buffers.pop(row_index, None)
        self.preview_pending_frames.pop(row_index, None)
        self.preview_sources.pop(row_index, None)
        self.preview_retry_attempts.pop(row_index, None)
        self.preview_frame_logged_rows.discard(row_index)
        self.preview_render_logged_rows.discard(row_index)
        self.preview_auto_mode_rows.discard(row_index)

    def show_source_help(self, combo, edit):
        source_type = self._source_type_id(combo)
        item = self.source_type_map.get(source_type, {})
        QMessageBox.information(
            self,
            item.get("label", "Camera Source"),
            item.get("hint", "Enter a source that FFmpeg can read.") + "\n\n"
            "Examples:\n"
            "- RTSP/IP: 192.168.0.10 or rtsp://camera/stream\n"
            "- USB/DirectShow: Logitech Camera\n"
            "- Basler/GenICam: pylon/GenICam source string from device setup\n"
            "- Stream URL: http://camera/live.mjpg"
        )

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Recording Folder", self.output_folder_edit.text())
        if folder:
            self.output_folder_edit.setText(folder)

    def open_output_folder(self):
        folder = self.output_folder_edit.text().strip()
        if not folder:
            return
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, _tr("Folder unavailable"),
                _tr("Could not open the recording folder:\n%(error)s")
                % {"error": exc})
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(folder)):
            QMessageBox.warning(
                self, _tr("Folder unavailable"),
                _tr("Could not open the recording folder:\n%(path)s")
                % {"path": folder})

    def _ffmpeg_path(self):
        path = resource_path("ffmpeg.exe")
        if not os.path.exists(path):
            QMessageBox.warning(self, _tr("Missing FFmpeg"), _tr("ffmpeg.exe could not be found."))
            return ""
        return path

    def build_recording_command(
        self,
        ffmpeg,
        source,
        output_file,
        preview_pipe=False,
        frame_rate="",
        resolution="",
        audio_device="",
        mute=False,
        volume="100",
        software_encoder=False,
    ):
        if self.is_directshow_source(source):
            return build_directshow_record_with_preview_command(
                ffmpeg,
                source,
                output_file,
                self.duration_edit.text().strip(),
                preview_pipe=preview_pipe,
                frame_rate=frame_rate,
                resolution=resolution,
                audio_device=audio_device,
                mute=mute,
                volume=volume,
                quality=self.output_quality,
            )
        source = apply_axis_rtsp_recording_options(source, frame_rate=frame_rate, resolution=resolution)
        return build_record_command(
            ffmpeg,
            source,
            output_file,
            self.codec_combo.currentText(),
            self.duration_edit.text().strip(),
            preview_pipe=preview_pipe,
            frame_rate=frame_rate,
            resolution=resolution,
            audio_device=audio_device,
            mute=mute,
            volume=volume,
            quality=self.output_quality,
            video_encoder=self._video_encoder_for(source, software_encoder),
        )

    def _video_encoder_for(self, source, software_encoder=False):
        """The hardware encoder for a screen capture, "" (libx264) otherwise."""
        if software_encoder or not source.lower().startswith("screen="):
            return ""
        return self.hardware_h264_encoder or ""

    def recording_fallback_commands(
        self,
        ffmpeg,
        source,
        output_file,
        preview_pipe=False,
        frame_rate="",
        resolution="",
        audio_device="",
        mute=False,
        volume="100",
    ):
        commands = []
        if source.lower().startswith("screen="):
            common = {
                "preview_pipe": preview_pipe, "frame_rate": frame_rate, "resolution": "",
                "audio_device": audio_device, "mute": mute, "volume": volume,
            }
            if self._video_encoder_for(source):
                # The hardware encoder passed its probe but refused this stream
                # (driver update, GPU busy, unsupported size): same capture, libx264.
                commands.append(self.build_recording_command(ffmpeg, source, output_file, software_encoder=True, **common))
            gdi_source = screen_gdi_fallback_source(source)
            if gdi_source:
                # Desktop Duplication could not start (no D3D11 device, remote
                # session, display index gone). Dropping the frame rate would not
                # help; grab the whole desktop through GDI at the same rate, with
                # the software encoder so one rung cannot fail for two reasons.
                commands.append(self.build_recording_command(ffmpeg, gdi_source, output_file, software_encoder=True, **common))
            return commands
        if source.lower().startswith("rtsp://") and frame_rate and resolution:
            commands.append(self.build_recording_command(
                ffmpeg,
                source,
                output_file,
                preview_pipe=preview_pipe,
                frame_rate="",
                resolution=resolution,
                audio_device=audio_device,
                mute=mute,
                volume=volume,
            ))
        commands.append(self.build_recording_command(
            ffmpeg,
            source,
            output_file,
            preview_pipe=preview_pipe,
            frame_rate="",
            resolution="",
            audio_device=audio_device,
            mute=mute,
            volume=volume,
        ))
        unique = []
        for command in commands:
            if command not in unique:
                unique.append(command)
        return unique

    def _row_sync_offset(self, source_row):
        offset_spin = source_row[10] if len(source_row) > 10 else None
        if offset_spin is None:
            return ""
        value = offset_spin.value()
        # Treat a near-zero nudge as "no offset" so the command builder leaves the
        # input untouched instead of adding a redundant -itsoffset 0.
        return f"{value:.2f}" if abs(value) >= 1e-6 else ""

    def recording_options_for_row(self, row_index):
        if row_index < 0 or row_index >= len(self.source_rows):
            return {"frame_rate": "", "resolution": "", "offset": ""}
        source_row = self.source_rows[row_index]
        source_edit = source_row[3] if len(source_row) > 3 else None
        # The sync offset is needed even for Basler/GenICam (it is usually the camera
        # that lags), so it is returned regardless of the auto-mode frame rate/resolution.
        offset = self._row_sync_offset(source_row)
        if source_edit and self._is_basler_genicam_source(source_edit.text()):
            return {"frame_rate": "", "resolution": "", "offset": offset}
        frame_rate_combo = source_row[8] if len(source_row) > 8 else None
        resolution_combo = source_row[9] if len(source_row) > 9 else None
        return {
            "frame_rate": frame_rate_combo.currentText() if frame_rate_combo else "",
            "resolution": resolution_combo.currentText() if resolution_combo else "",
            "offset": offset,
        }

    def _source_identity(self, source):
        return (source or "").strip().lower()

    def _deduplicate_selected_sources(self, selected):
        unique = []
        seen = set()
        for row_index, label, source, options in selected:
            identity = self._source_identity(source)
            if identity in seen:
                self._append_log(
                    f"[recorder] skipped Video {row_index + 1} ({label}): duplicate source already selected"
                )
                continue
            seen.add(identity)
            unique.append((row_index, label, source, options))
        return unique

    def start_recording(self):
        if self.status_label.text() in ("Recording", "Stopping...", "Starting recording...") or self.processes:
            return
        ffmpeg = self._ffmpeg_path()
        if not ffmpeg:
            return
        output_folder = self.output_folder_edit.text().strip()
        os.makedirs(output_folder, exist_ok=True)
        self.log_lines = []
        selected = []
        for row_index, source_row in enumerate(self.source_rows):
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            source = build_source_text(self._source_type_for_text(type_combo, source_edit.text()), source_edit.text().strip())
            if enabled.isChecked() and source:
                selected.append((row_index, label_edit.text().strip() or "source", source, self.recording_options_for_row(row_index)))
            elif source:
                self._append_log(
                    f"[recorder] skipped Video {row_index + 1} ({label_edit.text().strip() or 'source'}): Use is unchecked"
                )
        if not selected:
            QMessageBox.warning(self, _tr("No Sources"), _tr("Enable at least one source and enter its source string."))
            return
        selected = self._deduplicate_selected_sources(selected)
        if not selected:
            QMessageBox.warning(self, _tr("No Sources"), _tr("Enable at least one unique source."))
            return

        self.clear_preview_backlog()
        released_directshow_preview = self.release_preview_processes_for_recording(selected)
        self.save_current_recorder_settings()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.pending_recording_start = (ffmpeg, selected, output_folder, timestamp)
        if released_directshow_preview:
            delay_ms = self._recording_start_delay_for_selection(selected)
            self.status_label.setText(_tr("Starting recording..."))
            self._append_log("[recorder] waiting for USB camera preview to release before recording")
            self._notify_workflow_availability_change()
            self.record_start_timer.start(delay_ms)
            self.record_start_watchdog_timer.start(max(self.record_start_watchdog_delay_ms, delay_ms + 1800))
            return
        self._begin_pending_recording()

    def _recording_start_delay_for_selection(self, selected):
        if any(self._is_basler_genicam_source(source) for _row_index, _label, source, *_options in selected):
            return self.basler_record_start_delay_ms
        return self.record_start_delay_ms

    def _begin_pending_recording(self):
        if not self.pending_recording_start:
            return
        ffmpeg, selected, output_folder, timestamp = self.pending_recording_start
        self.pending_recording_start = None
        self.record_start_timer.stop()
        self.record_start_watchdog_timer.stop()
        try:
            self._start_recording_processes(ffmpeg, selected, output_folder, timestamp)
        except Exception as exc:
            self._append_log(f"[recorder] failed to start: {exc}")
            self.status_label.setText(_tr("Recording failed - check camera availability"))
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self._notify_workflow_availability_change()

    def _start_recording_processes(self, ffmpeg, selected, output_folder, timestamp):
        self.processes = []
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(_tr("Recording"))
        self._notify_workflow_availability_change()
        if self.composite_layout() and len(selected) > 1:
            self._start_combined_grid_process(ffmpeg, selected, output_folder, timestamp)
            return
        for row_index, label, source, *option_items in selected:
            options = option_items[0] if option_items else {}
            mute = self.source_rows[row_index][5].isChecked()
            volume = self.source_rows[row_index][6].currentText()
            audio_device = self._audio_device_value(self.source_rows[row_index][7])
            safe_label = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in label)
            output_file = get_unique_path(os.path.join(output_folder, f"{self.base_name_edit.text().strip()}_{safe_label}_{timestamp}.mp4"))
            # For DirectShow, the recording process MUST also pipe the preview because the
            # device can only be opened by one consumer at a time. This now includes
            # Basler / GenICam: opening the device once and teeing the file + preview from
            # that single capture keeps the live preview running during recording and
            # avoids the BindToObject contention that a separate preview process used to
            # trigger. The pre-recording release + settle window
            # (basler_record_start_delay_ms) is what lets the recording graph re-open the
            # device cleanly. For RTSP/HTTP we still record via a plain stream copy and
            # leave the separate preview process alive, because those network sources have
            # no exclusive-device lock and stream copy is the most reliable file output.
            preview_pipe = self.auto_preview and self.is_directshow_source(source)
            command = self.build_recording_command(
                ffmpeg,
                source,
                output_file,
                preview_pipe=preview_pipe,
                frame_rate=options.get("frame_rate", ""),
                resolution=options.get("resolution", ""),
                audio_device=audio_device,
                mute=mute,
                volume=volume,
            )
            audio_fallback_command = None
            if (
                audio_device
                and audio_device != "No Audio"
                and not mute
                and volume != "0"
            ):
                audio_fallback_command = self.build_recording_command(
                    ffmpeg,
                    source,
                    output_file,
                    preview_pipe=preview_pipe,
                    frame_rate=options.get("frame_rate", ""),
                    resolution=options.get("resolution", ""),
                    audio_device="",
                    mute=True,
                    volume="0",
                )
            fallback_commands = [
                fallback
                for fallback in self.recording_fallback_commands(
                    ffmpeg,
                    source,
                    output_file,
                    preview_pipe=preview_pipe,
                    frame_rate=options.get("frame_rate", ""),
                    resolution=options.get("resolution", ""),
                    audio_device=audio_device,
                    mute=mute,
                    volume=volume,
                )
                if fallback != command
            ]
            retry_delay_ms = 1500 if preview_pipe else 0
            if self._is_basler_genicam_source(source):
                # Basler's DirectShow graph can report I/O errors briefly after the
                # preview process releases it. Retry the exact same tee recording command
                # once after a longer pylon unwind window so the re-open succeeds.
                fallback_commands = [command]
                retry_delay_ms = self.basler_record_start_delay_ms
            process = self.create_recording_process()
            self._start_configured_recording_process(
                process,
                command,
                safe_label,
                row_index,
                preview_pipe,
                fallback_command=(fallback_commands[0] if fallback_commands else None),
                fallback_commands=fallback_commands,
                retry_delay_ms=retry_delay_ms,
                audio_device=audio_device,
                audio_fallback_command=audio_fallback_command,
            )
            if not preview_pipe and self.auto_preview and self.can_preview_separately_while_recording(source):
                # Ensure the standalone preview process for this RTSP/HTTP row is running.
                # If release_preview_processes_for_recording left it alive, this is a
                # no-op; otherwise it (re)starts it so the user keeps seeing frames.
                self.start_stream_preview(row_index, source, force_restart=False)

    def _start_configured_recording_process(
        self,
        process,
        command,
        safe_label,
        row_index=None,
        preview_pipe=False,
        fallback_command=None,
        fallback_commands=None,
        retry_delay_ms=0,
        audio_device="",
        audio_fallback_command=None,
        audio_retry_attempted=False,
    ):
        process.recording_fallback_commands = list(fallback_commands or ([fallback_command] if fallback_command else []))
        process.recording_fallback_command = process.recording_fallback_commands[0] if process.recording_fallback_commands else None
        process.recording_preview_pipe = preview_pipe
        process.recording_retry_delay_ms = retry_delay_ms
        process.recording_row_index = row_index
        process.recording_safe_label = safe_label
        process.recording_error_text = ""
        process.recording_started_at = time.monotonic()
        process.recording_audio_device = audio_device
        process.recording_audio_fallback_command = audio_fallback_command
        process.recording_audio_retry_attempted = audio_retry_attempted
        if preview_pipe:
            process.setProcessChannelMode(QProcess.SeparateChannels)
            self.preview_buffers[row_index] = bytearray()
            process.readyReadStandardOutput.connect(lambda p=process, row=row_index: self._read_preview_frames(p, row))
            process.readyReadStandardError.connect(lambda p=process, name=safe_label: self._read_process_error(p, name))
        else:
            process.setProcessChannelMode(QProcess.MergedChannels)
            process.readyReadStandardOutput.connect(lambda p=process, name=safe_label: self._read_process_output(p, name))
        process.errorOccurred.connect(lambda _error, p=process, name=safe_label: self._process_start_error(p, name))
        process.finished.connect(lambda exit_code, _status, p=process, name=safe_label: self._process_finished(p, name, exit_code))
        self._append_log(f"[{safe_label}] {' '.join(command)}")
        process.start(command[0], command[1:])
        self.processes.append(process)

    def _prepare_combined_preview_placeholders(self, selected):
        if not self.auto_preview:
            return
        visible_rows = [row_index for row_index, _label, _source, *_options in selected if row_index < len(self.preview_boxes)]
        if not visible_rows:
            return
        self.combined_preview_rows = visible_rows
        for row_index in visible_rows:
            self.preview_boxes[row_index].clear()
            self.preview_boxes[row_index].setText(
                _tr("Video %(number)s\nOpening combined preview...")
                % {"number": row_index + 1})

    COMPOSITE_LAYOUTS = {"Combined grid": "grid", "Picture-in-picture": "pip"}
    # Requested-option ladder for the single composite process, mirroring
    # recording_fallback_commands for separate files: full options, then without
    # the frame rate, then without any requested option at all.
    COMBINED_OPTION_TIERS = 3

    def composite_layout(self):
        """'grid' / 'pip' when the output mode records one composite file, else None."""
        return self.COMPOSITE_LAYOUTS.get(self.output_mode_combo.currentText())

    @staticmethod
    def _degrade_requested_options(options, tier):
        options = dict(options or {})
        if tier >= 1:
            options["frame_rate"] = ""
        if tier >= 2:
            options["resolution"] = ""
        return options

    def _start_combined_grid_process(
        self,
        ffmpeg,
        selected,
        output_folder,
        timestamp,
        attempt=0,
        force_video_only=False,
        option_tier=0,
    ):
        self._prepare_combined_preview_placeholders(selected)
        output_file = get_unique_path(os.path.join(output_folder, f"{self.base_name_edit.text().strip()}_Combined_{timestamp}.mp4"))
        audio_device = ""
        audio_row_label = ""
        audio_volume = "100"
        if not force_video_only:
            for row_index, label, _source, *_options in selected:
                source_row = self.source_rows[row_index]
                candidate = self._audio_device_value(source_row[7])
                if (
                    candidate != "No Audio"
                    and not source_row[5].isChecked()
                    and source_row[6].currentText() != "0"
                ):
                    audio_device = candidate
                    audio_row_label = label
                    audio_volume = source_row[6].currentText()
                    break
        if audio_device:
            self._append_log(
                _tr("[Combined] using audio from %(row)s")
                % {"row": audio_row_label}
            )
        layout = self.composite_layout() or "grid"
        combined_sources = []
        combined_offsets = []
        combined_options = []
        for _row_index, _label, source, *option_items in selected:
            options = self._degrade_requested_options(option_items[0] if option_items else {}, option_tier)
            if option_tier >= self.COMBINED_OPTION_TIERS - 1:
                # Last rung: a GPU monitor capture that would not start becomes a
                # GDI grab of the whole desktop, as in Separate videos.
                source = screen_gdi_fallback_source(source) or source
            combined_sources.append(apply_axis_rtsp_recording_options(
                source,
                frame_rate=options.get("frame_rate", ""),
                resolution=options.get("resolution", ""),
            ))
            combined_offsets.append(options.get("offset", ""))
            combined_options.append({
                "frame_rate": options.get("frame_rate", ""),
                "resolution": options.get("resolution", ""),
            })
        command_kwargs = {
            "preview_pipe": self.auto_preview,
            "offsets_per_source": combined_offsets,
            "options_per_source": combined_options,
            "layout": layout,
            "quality": self.output_quality,
        }
        command = build_combined_grid_record_command(
            ffmpeg,
            combined_sources,
            output_file,
            self.duration_edit.text().strip(),
            audio_device=audio_device,
            mute=not bool(audio_device),
            volume=audio_volume,
            **command_kwargs,
        )
        audio_fallback_command = None
        if audio_device:
            audio_fallback_command = build_combined_grid_record_command(
                ffmpeg,
                combined_sources,
                output_file,
                self.duration_edit.text().strip(),
                audio_device="",
                mute=True,
                volume="0",
                **command_kwargs,
            )
        process = self.create_recording_process()
        # A Basler/GenICam device can briefly report "Unable to BindToObject" / I/O error
        # if its idle preview graph has not finished releasing the device when the combined
        # recording opens it. The single combined process has no other input to fall back
        # on, so allow one retry of the same command after a longer pylon unwind window.
        process.recording_safe_label = "Combined"
        process.recording_error_text = ""
        process.recording_started_at = time.monotonic()
        process.recording_audio_device = audio_device
        process.recording_audio_fallback_command = audio_fallback_command
        process.recording_audio_retry_attempted = force_video_only
        process.recording_preview_pipe = self.auto_preview
        has_genicam_source = any(
            self._is_basler_genicam_source(source) for _row, _label, source, *_options in selected
        )
        process.combined_recording_context = (ffmpeg, selected, output_folder, timestamp)
        process.combined_recording_attempt = attempt
        process.combined_option_tier = option_tier
        process.combined_can_retry = has_genicam_source and attempt < 2
        process.combined_retry_delay_ms = self.basler_record_start_delay_ms
        if self.auto_preview:
            process.setProcessChannelMode(QProcess.SeparateChannels)
            self.preview_buffers["combined"] = bytearray()
            process.readyReadStandardOutput.connect(lambda p=process: self._read_combined_preview_frames(p))
            process.readyReadStandardError.connect(lambda p=process: self._read_process_error(p, "Combined"))
        else:
            process.setProcessChannelMode(QProcess.MergedChannels)
            process.readyReadStandardOutput.connect(lambda p=process: self._read_process_output(p, "Combined"))
        process.errorOccurred.connect(lambda _error, p=process: self._process_start_error(p, "Combined"))
        process.finished.connect(lambda exit_code, _status, p=process: self._process_finished(p, "Combined", exit_code))
        self._append_log(f"[Combined] {' '.join(command)}")
        process.start(command[0], command[1:])
        self.processes.append(process)

    def create_recording_process(self):
        return QProcess(self)

    def _read_process_output(self, process, name):
        data = bytes(process.readAllStandardOutput()).decode(errors="replace")
        if data:
            for line in data.splitlines():
                process.recording_error_text = (getattr(process, "recording_error_text", "") + "\n" + line)[-4000:]
                self._append_log(f"[{name}] {line}")

    def _read_process_error(self, process, name):
        data = bytes(process.readAllStandardError()).decode(errors="replace")
        if data:
            for line in data.splitlines():
                process.recording_error_text = (getattr(process, "recording_error_text", "") + "\n" + line)[-4000:]
                self._append_log(f"[{name}] {line}")

    def _process_start_error(self, process, name):
        self._append_log(f"[{name}] failed to start")
        self.processes = [p for p in self.processes if p is not process and p.state() != QProcess.NotRunning]
        has_retry = bool(
            getattr(process, "recording_fallback_commands", None)
            or getattr(process, "recording_fallback_command", None)
            or getattr(process, "recording_audio_fallback_command", None)
        )
        if self.processes or has_retry:
            self.status_label.setText(_tr("Recording"))
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self._notify_workflow_availability_change()
            return
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pending_recording_start = None
        self.status_label.setText(_tr("Recording failed - check camera availability"))
        self._notify_workflow_availability_change()

    def _process_finished(self, process, name, exit_code=0):
        self._append_log(f"[{name}] recording stopped exit_code={exit_code}")
        self.processes = [p for p in self.processes if p is not process and p.state() != QProcess.NotRunning]
        if exit_code and self._retry_recording_without_audio(process, name):
            return
        if exit_code and self._retry_combined_without_requested_options(process, name):
            return
        if exit_code and self._retry_combined_recording(process, name):
            return
        if exit_code and self._retry_recording_without_requested_options(process, name):
            return
        # Surface per-source failures so the user can tell which camera dropped without a
        # log box. Only do this while we are still in the "Recording" phase: during
        # Stopping... we let the stop-flow decide the final status, and after the last
        # process exits the aggregate branch below paints the final state.
        if exit_code and self.processes and self.status_label.text() == "Recording":
            self.status_label.setText(
                _tr("Recording: %(name)s failed - check camera availability")
                % {"name": name})
        if not self.processes:
            was_stopping = self.status_label.text() == "Stopping..."
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            if exit_code and not was_stopping:
                self.status_label.setText(_tr("Recording failed - check camera availability"))
            else:
                self.status_label.setText(_tr("Not recording"))
                self.resume_previews_after_recording_stop()
            self._notify_workflow_availability_change()

    def resume_previews_after_recording_stop(self):
        # DirectShow/Basler devices often need a short release window after FFmpeg closes
        # the recording graph. Restarting the preview immediately can leave the tile stuck
        # on "Opening preview..." while the driver is still unwinding.
        if self.auto_preview and self.preview_paused_rows:
            self._schedule(self.record_start_delay_ms, self._resume_paused_previews)
            return
        self._resume_paused_previews()

    def _resume_paused_previews(self):
        self.refresh_previews_from_sources(force_restart=False)
        self.preview_paused_rows = set()

    def _retry_combined_without_requested_options(self, process, name):
        """Step the composite process down the requested-option ladder.

        Separate videos has always retried an Axis camera without ``?fps``, then
        without ``?resolution``, and a USB camera without ``-framerate`` /
        ``-video_size``; the single combined process had no such ladder, so a
        camera that rejected the requested settings ("Server returned 400 Bad
        Request") failed the whole recording.
        """
        context = getattr(process, "combined_recording_context", None)
        if not context:
            return False
        tier = getattr(process, "combined_option_tier", 0)
        if tier >= self.COMBINED_OPTION_TIERS - 1:
            return False
        error_text = getattr(process, "recording_error_text", "").lower()
        if "bindtoobject" in error_text:
            return False          # a busy GenICam device: _retry_combined_recording's job
        retry_markers = (
            "bad request",
            "could not set video options",
            "error opening input",
            "i/o error",
        )
        if not any(marker in error_text for marker in retry_markers):
            return False
        ffmpeg, selected, output_folder, timestamp = context
        attempt = getattr(process, "combined_recording_attempt", 0)
        self._append_log(
            f"[{name}] retrying with safer input format after camera rejected requested settings"
        )
        self.status_label.setText(_tr("Recording"))
        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)

        def start_retry():
            if self.status_label.text() not in ("Recording", "Starting recording..."):
                return
            self._start_combined_grid_process(
                ffmpeg, selected, output_folder, timestamp,
                attempt=attempt,
                force_video_only=getattr(process, "recording_audio_retry_attempted", False),
                option_tier=tier + 1,
            )

        # A USB camera needs a moment to release before it can be reopened.
        self._schedule(self.record_start_delay_ms if self.auto_preview else 0, start_retry)
        self._notify_workflow_availability_change()
        return True

    def _retry_combined_recording(self, process, name):
        # Retry the whole combined command once if the only failure was a GenICam/Basler
        # device that had not finished releasing from its idle preview when we opened it.
        if not getattr(process, "combined_can_retry", False):
            return False
        context = getattr(process, "combined_recording_context", None)
        if not context:
            return False
        error_text = getattr(process, "recording_error_text", "").lower()
        retry_markers = (
            "bindtoobject",
            "could not find video device",
            "error opening input",
            "i/o error",
        )
        if not any(marker in error_text for marker in retry_markers):
            return False
        attempt = getattr(process, "combined_recording_attempt", 0) + 1
        delay_ms = getattr(process, "combined_retry_delay_ms", self.basler_record_start_delay_ms)
        ffmpeg, selected, output_folder, timestamp = context
        self._append_log(
            f"[{name}] camera busy on first open; retrying combined recording after device settle window"
        )
        self.status_label.setText(_tr("Recording"))
        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)

        def start_retry():
            if self.status_label.text() not in ("Recording", "Starting recording..."):
                return
            self._start_combined_grid_process(
                ffmpeg, selected, output_folder, timestamp, attempt=attempt,
                option_tier=getattr(process, "combined_option_tier", 0),
            )

        self._schedule(delay_ms, start_retry)
        self._notify_workflow_availability_change()
        return True

    @staticmethod
    def _is_audio_start_failure(error_text, audio_device):
        text = str(error_text or "").lower()
        device = str(audio_device or "").lower()
        return (
            "could not find audio device" in text
            or (
                "i/o error" in text
                and ("audio=" in text or (device and device in text))
            )
        )

    def _retry_recording_without_audio(self, process, name):
        command = getattr(process, "recording_audio_fallback_command", None)
        audio_device = getattr(process, "recording_audio_device", "")
        if (
            not command
            or getattr(process, "recording_audio_retry_attempted", False)
        ):
            return False
        started_at = getattr(process, "recording_started_at", 0.0)
        early_window = self.record_start_watchdog_delay_ms / 1000
        if not started_at or time.monotonic() - started_at > early_window:
            return False
        if not self._is_audio_start_failure(
            getattr(process, "recording_error_text", ""),
            audio_device,
        ):
            return False
        message = _tr(
            "%(row)s: audio device '%(device)s' unavailable, recording video only"
        ) % {
            "row": name,
            "device": audio_device,
        }
        self._append_log(message)
        self.status_label.setText(message)

        def start_retry():
            if "recording video only" not in self.status_label.text().lower():
                return
            combined_context = getattr(
                process,
                "combined_recording_context",
                None,
            )
            if combined_context:
                self._start_combined_grid_process(
                    *combined_context,
                    attempt=getattr(
                        process,
                        "combined_recording_attempt",
                        0,
                    ),
                    force_video_only=True,
                    option_tier=getattr(process, "combined_option_tier", 0),
                )
                return
            replacement = self.create_recording_process()
            self._start_configured_recording_process(
                replacement,
                command,
                getattr(process, "recording_safe_label", name),
                getattr(process, "recording_row_index", None),
                getattr(process, "recording_preview_pipe", False),
                fallback_commands=[],
                retry_delay_ms=0,
                audio_device="",
                audio_fallback_command=None,
                audio_retry_attempted=True,
            )

        self._schedule(0, start_retry)
        self._notify_workflow_availability_change()
        return True

    def _retry_recording_without_requested_options(self, process, name):
        fallback_commands = list(getattr(process, "recording_fallback_commands", None) or [])
        if not fallback_commands:
            fallback_command = getattr(process, "recording_fallback_command", None)
            fallback_commands = [fallback_command] if fallback_command else []
        if not fallback_commands:
            return False
        error_text = getattr(process, "recording_error_text", "").lower()
        retry_markers = (
            "bad request",
            "could not set video options",
            "error opening input",
            "i/o error",
        )
        encoder_failed = looks_like_encoder_failure(error_text)
        if not encoder_failed and not any(marker in error_text for marker in retry_markers):
            return False
        next_command = fallback_commands[0]
        remaining_commands = fallback_commands[1:]
        preview_pipe = getattr(process, "recording_preview_pipe", False)
        if encoder_failed:
            self._append_log(f"[{name}] retrying with the software encoder after the hardware encoder failed to start")
        else:
            self._append_log(f"[{name}] retrying with safer input format after camera rejected requested settings")
        self.status_label.setText(_tr("Recording"))
        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        def start_retry():
            if self.status_label.text() not in ("Recording", "Starting recording..."):
                return
            replacement = self.create_recording_process()
            self._start_configured_recording_process(
                replacement,
                next_command,
                getattr(process, "recording_safe_label", name),
                getattr(process, "recording_row_index", None),
                preview_pipe,
                fallback_command=(remaining_commands[0] if remaining_commands else None),
                fallback_commands=remaining_commands,
                retry_delay_ms=getattr(process, "recording_retry_delay_ms", 1500 if preview_pipe else 0),
                audio_device=getattr(process, "recording_audio_device", ""),
                audio_fallback_command=getattr(
                    process,
                    "recording_audio_fallback_command",
                    None,
                ),
                audio_retry_attempted=getattr(
                    process,
                    "recording_audio_retry_attempted",
                    False,
                ),
            )
        retry_delay_ms = getattr(process, "recording_retry_delay_ms", 1500 if preview_pipe else 0)
        if retry_delay_ms:
            self._schedule(retry_delay_ms, start_retry)
        else:
            start_retry()
        self._notify_workflow_availability_change()
        return True

    def stop_recording(self):
        logger.info("Recorder stop_recording entered with status=%s processes=%s", self.status_label.text(), len(self.processes))
        self.pending_recording_start = None
        self.record_start_timer.stop()
        self.record_start_watchdog_timer.stop()
        self.clear_preview_backlog()
        self.stop_btn.setEnabled(False)
        self.status_label.setText(_tr("Stopping..."))
        running_processes = []
        for process in list(self.processes):
            try:
                running = process.state() != QProcess.NotRunning
            except RuntimeError:
                running = False
            if running:
                running_processes.append(process)
        self.processes = running_processes
        for process in list(self.processes):
            self._write_recording_quit(process)
        for process in list(self.processes):
            self._finish_recording_quit(process)
        # Final safety net: even if every per-process timer fails to clear self.processes
        # (FFmpeg ignored q AND terminate AND kill, or Qt skipped a callback) this
        # watchdog forcibly returns the UI from "Stopping..." so the user is never
        # stuck waiting indefinitely.
        self._schedule(4000, self._stop_recording_watchdog)
        if not self.processes and self.status_label.text() == "Stopping...":
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText(_tr("Not recording"))
            self.resume_previews_after_recording_stop()
        self._notify_workflow_availability_change()

    def _stop_recording_watchdog(self):
        logger.info("Recorder stop watchdog fired with status=%s processes=%s", self.status_label.text(), len(self.processes))
        # If a regular finished/forced-finish path already moved past "Stopping..." we
        # have nothing to do; never second-guess a clean shutdown.
        if self.status_label.text() != "Stopping...":
            return
        for process in list(self.processes):
            try:
                if process.state() != QProcess.NotRunning:
                    process.kill()
            except RuntimeError:
                pass
        self.processes = []
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(_tr("Recording stopped (forced)"))
        self.resume_previews_after_recording_stop()
        self._notify_workflow_availability_change()

    def _request_recording_process_stop(self, process):
        self._write_recording_quit(process)
        self._finish_recording_quit(process)

    def _write_recording_quit(self, process):
        try:
            process.write(b"q\n")
        except Exception:
            logger.debug("MultiSourceRecorderWidget._write_recording_quit: suppressed error", exc_info=True)

    def _finish_recording_quit(self, process):
        try:
            if hasattr(process, "waitForBytesWritten"):
                # Keep this short so the UI thread is never visibly blocked even when
                # there are several recording processes. 100ms is enough for the bytes
                # to land in FFmpeg's stdin pipe; the rest of the shutdown happens via
                # the terminate/kill timers we schedule below.
                process.waitForBytesWritten(100)
            if hasattr(process, "closeWriteChannel"):
                process.closeWriteChannel()
        except Exception:
            logger.debug("MultiSourceRecorderWidget._finish_recording_quit: suppressed error", exc_info=True)
        # Keep stop snappy: on Windows QProcess.terminate() behaves like TerminateProcess,
        # so we follow the graceful q with a short window for FFmpeg to finalize the
        # MP4 moov atom, then escalate.
        self._schedule(1500, lambda p=process: self._terminate_recording_process_if_running(p))
        self._schedule(3000, lambda p=process: self._force_finish_if_running(p))

    def _terminate_recording_process_if_running(self, process):
        if process not in self.processes:
            return
        self._terminate_if_running(process)

    def _terminate_if_running(self, process):
        try:
            if process.state() != QProcess.NotRunning:
                process.terminate()
        except RuntimeError:
            pass

    def _kill_if_running(self, process):
        try:
            if process.state() != QProcess.NotRunning:
                process.kill()
        except RuntimeError:
            pass

    def _force_finish_if_running(self, process):
        try:
            if process.state() != QProcess.NotRunning:
                process.kill()
        except RuntimeError:
            pass
        self.processes = [p for p in self.processes if p is not process]
        if not self.processes and self.status_label.text() == "Stopping...":
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText(_tr("Recording failed - FFmpeg did not stop cleanly"))
            # Bring back any previews that were paused for recording even though the
            # finished signal never fired — otherwise the user is stuck staring at
            # frozen tiles after a forced kill.
            self.resume_previews_after_recording_stop()
            self._notify_workflow_availability_change()

    def _notify_workflow_availability_change(self):
        host = getattr(self, "_workflow_host", None)
        if host is not None and hasattr(host, "update_single_workflow_availability"):
            try:
                host.update_single_workflow_availability()
            except Exception:
                logger.debug("MultiSourceRecorderWidget._notify_workflow_availability_change: suppressed error", exc_info=True)
            return

        # Fallback for tests/legacy construction paths where no explicit host was
        # supplied. The widget may have been reparented by Qt layouts, so walk upward.
        seen = set()
        ancestor = None
        try:
            ancestor = self.parent()
        except RuntimeError:
            ancestor = None
        while ancestor is not None and id(ancestor) not in seen:
            seen.add(id(ancestor))
            if hasattr(ancestor, "update_single_workflow_availability"):
                try:
                    ancestor.update_single_workflow_availability()
                except Exception:
                    logger.debug("MultiSourceRecorderWidget._notify_workflow_availability_change: suppressed error", exc_info=True)
                return
            parent_attr = getattr(ancestor, "parent", None)
            if not callable(parent_attr):
                return
            try:
                ancestor = parent_attr()
            except (RuntimeError, TypeError):
                return

    def _append_log(self, line):
        self.log_lines.append(line)
        logger.info(line)
