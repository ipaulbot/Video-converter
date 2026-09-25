import glob
import os
import threading
import time
from datetime import datetime

from PyQt5.QtCore import QCoreApplication, QProcess, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
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
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
)
from conversion.recording_sources import (
    CAMERA_SOURCE_TYPES,
    apply_axis_rtsp_recording_options,
    axis_mjpeg_preview_url,
    build_rtsp_url,
    build_source_text,
    discover_directshow_audio_devices,
    discover_directshow_video_devices,
    parse_directshow_video_options,
    parse_rtsp_url_settings,
)
from ui import theme
from ui.glyph_icons import make_icon_button
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
        _tr("Sync offset for Combined grid: shift this source earlier (negative) or later "
        "(positive) to line it up with the others.")
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

    def set_options(self, options):
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItems(options)
        self.setCurrentText(current if current else (options[0] if options else ""))
        self.blockSignals(False)


VIDEO_DEVICE_PLACEHOLDERS = {
    "No source selected...",
    "RTSP/IP Camera",
    "Refresh USB devices...",
    "Select video device...",
}


class PreviewLabel(QLabel):
    # Subclass QLabel so the recorder can keep the PTZ overlay button centered every
    # time the preview tile is resized. The parent window reflows whenever the global
    # "Stop Recording" button is shown/hidden, and without this hook the overlay drifts
    # off-center (it was just .move()'d to absolute coordinates the last time the
    # source was updated).
    def __init__(self, recorder, row_index, parent=None):
        super().__init__(parent)
        self._recorder = recorder
        self._row_index = row_index

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
    def __init__(self, source_rows, output_controls=None, parent=None, button_style=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Video Settings"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.source_rows = source_rows
        self.output_controls = output_controls or {}
        self.dialog_rows = []
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
            if index == 0:
                row_enabled.setChecked(True)
                row_enabled.setEnabled(False)
                row_enabled.toggled.connect(lambda checked, box=row_enabled: box.setChecked(True) if not checked else None)
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
            if source_edit.text():
                row_device.setText(source_edit.text())
            else:
                row_device.setCurrentText("No source selected...")
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
            stored_audio = (
                parent._audio_device_value(audio_device_combo)
                if parent and audio_device_combo
                else "No Audio"
            )
            if parent and hasattr(parent, "populate_audio_device_combo"):
                parent.populate_audio_device_combo(row_audio_device, stored_audio)
            else:
                row_audio_device.addItem(_tr("No Audio"), "No Audio")
            row_offset = make_sync_offset_spinbox()
            if offset_spin is not None:
                row_offset.setValue(offset_spin.value())
            grid.addWidget(QLabel(str(index + 1)), index + 1, 0)
            grid.addWidget(row_enabled, index + 1, 1)
            grid.addWidget(row_label, index + 1, 2)
            grid.addWidget(row_device, index + 1, 3)
            camera_button = QToolButton()
            camera_button.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            camera_button.setIconSize(QSize(11, 11))
            camera_button.setToolTip(_tr("Camera %(number)s settings")
                                     % {"number": index + 1})
            camera_button.setFixedSize(16, 16)
            camera_button.setMaximumWidth(16)
            camera_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            camera_button.setProperty("skipGlobalStyle", True)
            camera_button.setStyleSheet(theme.qss("""
                QToolButton {
                    background: transparent;
                    border: none;
                    padding: 0px;
                    margin: 0px;
                    min-width: 16px;
                    max-width: 16px;
                }
                QToolButton:hover { background: $accent_tint; }
            """))
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
        grid.setColumnStretch(3, 1)
        grid.setColumnMinimumWidth(4, 16)
        grid.setColumnStretch(4, 0)
        layout.addLayout(grid)
        self.refresh_audio_devices_button = QPushButton(_tr("Refresh devices"))
        self.refresh_audio_devices_button.clicked.connect(self.refresh_audio_devices)
        layout.addWidget(self.refresh_audio_devices_button, 0, Qt.AlignRight)
        if parent and hasattr(parent, "audio_devices_discovered"):
            parent.audio_devices_discovered.connect(self.apply_discovered_audio_devices)

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
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("No source selected...", "none")
        combo.addItem("RTSP/IP Camera", "rtsp_ip")
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
        if device_type == "none" and device_text and device_text != "No source selected...":
            device_type = None
        if device_text in (getattr(self.parent(), "directshow_devices", None) or []):
            device_type = "directshow"
        if not device_type:
            device_type = row_type.currentData()
        return device_type

    def refresh_directshow_devices(self):
        parent = self.parent()
        if parent and hasattr(parent, "discover_directshow_devices"):
            self.directshow_devices = parent.discover_directshow_devices()
        for dialog_row in self.dialog_rows:
            self.populate_video_device_combo(dialog_row[3])

    def refresh_audio_devices(self):
        parent = self.parent()
        if parent and hasattr(parent, "start_audio_device_discovery"):
            parent.start_audio_device_discovery(force=True)

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

    def handle_video_device_choice(self, combo):
        if combo.currentData() == "refresh_directshow":
            self.refresh_directshow_devices()
            return
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
        for row_index, (source_row, dialog_row) in enumerate(
            zip(self.source_rows, self.dialog_rows, strict=False)
        ):
            enabled, label_edit, type_combo, source_edit = source_row[:4]
            audio_name_edit = source_row[4] if len(source_row) > 4 else None
            audio_device_combo = source_row[7] if len(source_row) > 7 else None
            frame_rate_combo = source_row[8] if len(source_row) > 8 else None
            resolution_combo = source_row[9] if len(source_row) > 9 else None
            offset_spin = source_row[10] if len(source_row) > 10 else None
            (row_enabled, row_label, row_type, row_device, row_frame_rate,
             row_resolution, row_audio_name, row_audio_device, row_offset) = dialog_row
            enabled.setChecked(True if row_index == 0 else row_enabled.isChecked())
            label_edit.setText(row_label.text())
            device_type = self.effective_video_device_type(row_type, row_device)
            type_index = type_combo.findData(device_type)
            if type_index >= 0:
                type_combo.setCurrentIndex(type_index)
            if row_device.currentText() in VIDEO_DEVICE_PLACEHOLDERS:
                source_edit.setText("")
            else:
                source_edit.setText(row_device.text())
            if source_edit.text().strip():
                enabled.setChecked(True)
            elif row_index != 0:
                enabled.setChecked(False)
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
        buttons.accepted.connect(dialog.accept)
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


class MultiSourceRecorderWidget(QWidget):
    # Emitted whenever the output mode or the set of enabled sources changes, so a host
    # (the main window) can refresh the layout schematic shown in its sidebar preview.
    layout_preview_changed = pyqtSignal()
    audio_devices_discovered = pyqtSignal(list)

    def __init__(self, parent=None, button_style=None, directshow_devices=None, auto_preview=True, load_saved_settings=False):
        super().__init__(parent)
        self._workflow_host = parent
        self.button_style = button_style
        self.directshow_devices = directshow_devices
        self.directshow_audio_devices = []
        self.audio_discovery_running = False
        self.audio_devices_discovered.connect(self._apply_audio_devices)
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
        self.start_audio_device_discovery()
        if load_saved_settings:
            self.load_current_recorder_settings()

    def _source_label(self, source_type_id):
        return {
            "rtsp_ip": "RTSP/IP",
            "directshow": "USB",
            "basler_genicam": "Basler",
            "stream_url": "Stream",
            "file": "File",
        }.get(source_type_id, source_type_id)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.status_label = QLabel(_tr("Not recording"))
        self.status_label.setStyleSheet(theme.qss("color: $grey_650;"))

        preview_grid = QGridLayout()
        preview_grid.setSpacing(3)
        self.preview_grid = preview_grid
        self.preview_boxes = []
        for index in range(4):
            preview = PreviewLabel(self, index)
            preview.setText(_tr("Video %(number)s\nNo signal")
                            % {"number": index + 1})
            preview.setAlignment(Qt.AlignCenter)
            preview.setMinimumHeight(74)
            preview.setMaximumHeight(98)
            preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            preview.setStyleSheet(theme.qss("""
                QLabel {
                    background: $grey_950;
                    color: $grey_100;
                    border: 1px solid $grey_260;
                    font-size: 9pt;
                }
            """))
            ptz_button = PTZOverlayButton(self, index, preview)
            ptz_button.move((preview.width() - ptz_button.width()) // 2, (preview.minimumHeight() - ptz_button.height()) // 2)
            preview_grid.addWidget(preview, index // 2, index % 2)
            self.preview_boxes.append(preview)
            self.ptz_overlay_buttons.append(ptz_button)
        layout.addLayout(preview_grid)

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
            if index == 0:
                enabled.setEnabled(False)
                enabled.toggled.connect(lambda checked, box=enabled: box.setChecked(True) if not checked else None)
            enabled.toggled.connect(lambda _checked: self.update_preview_panel_visibility())
            enabled.toggled.connect(lambda _checked: self.layout_preview_changed.emit())
            label = QLineEdit(f"Video {index + 1}")
            label.setMinimumWidth(60)
            label.setMaximumWidth(82)
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
            audio_name.setMaximumWidth(82)
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
        source_grid.setColumnStretch(3, 1)
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
        output_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        output_form = QFormLayout()
        output_form.setContentsMargins(6, 6, 6, 6)
        output_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        output_form.setFormAlignment(Qt.AlignTop)
        output_form.setVerticalSpacing(3)
        self.output_folder_edit = QLineEdit(os.path.join(os.path.expanduser("~"), "Videos"))
        self.output_folder_edit.setMinimumWidth(120)
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
        folder_line.addWidget(self.output_folder_edit, 1)
        folder_line.addWidget(self.open_output_folder_button, 0)
        self.base_name_edit = QLineEdit(_tr("Video"))
        self.base_name_edit.setMaximumWidth(140)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["copy", "h264"])
        self.codec_combo.setMaximumWidth(120)
        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItems([
            _tr("Separate videos"),
            _tr("Combined grid"),
        ])
        self.output_mode_combo.setMaximumWidth(140)
        self.output_mode_combo.currentTextChanged.connect(lambda _text: self.layout_preview_changed.emit())
        output_form.addRow("File location:", folder_line)
        output_form.addRow("File base name:", self.base_name_edit)
        output_form.addRow("Encoding:", self.codec_combo)
        output_form.addRow("Output mode:", self.output_mode_combo)
        self.duration_edit = QLineEdit("")
        self.duration_edit.setMaximumWidth(140)
        self.duration_edit.setPlaceholderText(_tr("blank = until stopped"))
        output_form.addRow("Timer:", self.duration_edit)
        self.copy_mode_note = QLabel(
            _tr(
                "USB cameras are always re-encoded to H.264; copy applies to RTSP and file sources."
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

    def _show_output_path_tail(self, _text=None):
        edit = self.output_folder_edit
        if not edit.hasFocus():
            edit.setCursorPosition(len(edit.text()))

    def groups_stacked(self):
        return isinstance(self.groups_layout, QVBoxLayout)

    def apply_layout_mode(self, metrics):
        """Stack recorder groups in compact mode and place them side by side in full mode."""
        for preview in self.preview_boxes:
            preview.setMaximumHeight(metrics.recorder_tile_max_h)
        old = self.groups_layout
        if old is not None:
            old.removeWidget(self.source_group)
            old.removeWidget(self.output_group)
            QWidget().setLayout(old)
        if metrics.recorder_stacked:
            new = QVBoxLayout(self.groups_host)
            new.addWidget(self.source_group)
            new.addWidget(self.output_group)
        else:
            new = QHBoxLayout(self.groups_host)
            new.setAlignment(Qt.AlignTop)
            new.addWidget(self.source_group, 2)
            new.addWidget(self.output_group, 1)
        new.setContentsMargins(0, 0, 0, 0)
        new.setSpacing(metrics.spacing * 2)
        self.groups_layout = new
        self.source_group.show()
        self.output_group.show()

    def update_copy_mode_note(self):
        usb_enabled = any(
            enabled.isChecked()
            and self._source_type_id(type_combo) == "directshow"
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
        if not button_style:
            return
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)
            if button.property("skipGlobalStyle"):
                continue
            button.setStyleSheet(button_style)

    def _source_type_id(self, combo):
        return combo.currentData() or "stream_url"

    def _source_type_for_text(self, combo, text):
        source_text = (text or "").strip().lower()
        if source_text.startswith("rtsp://"):
            return "rtsp_ip"
        if source_text.startswith(("http://", "https://")):
            return "stream_url"
        return self._source_type_id(combo)

    def update_source_placeholder(self, combo, edit, row_index=None, force_preview_restart=False):
        source_type = self._source_type_for_text(combo, edit.text())
        hints = {
            "rtsp_ip": "IP address, e.g. 192.168.0.10",
            "directshow": "Windows camera name, e.g. Logitech Camera",
            "basler_genicam": "Basler/pylon/GenICam source string",
            "stream_url": "rtsp://, http://, https://, or mjpeg URL",
            "file": "Local test file path",
        }
        edit.setPlaceholderText(hints.get(source_type, "FFmpeg source"))
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
        if row_index is not None and 0 <= row_index < len(self.preview_boxes):
            labels = {
                "rtsp_ip": "RTSP/IP",
                "directshow": "USB / DirectShow",
                "basler_genicam": "Basler / GenICam",
                "stream_url": "Stream URL",
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
            self.update_ptz_overlay_for_row(row_index)

    def populate_directshow_devices(self, source_edit):
        devices = self.discover_directshow_devices()
        if hasattr(source_edit, "set_options"):
            source_edit.set_options(devices)

    def discover_directshow_devices(self):
        if not self.directshow_devices:
            self.directshow_devices = discover_directshow_video_devices(resource_path("ffmpeg.exe"))
        return self.directshow_devices

    def start_audio_device_discovery(self, force=False):
        if self.audio_discovery_running:
            return
        if self.directshow_audio_devices and not force:
            self._apply_audio_devices(self.directshow_audio_devices)
            return
        self.audio_discovery_running = True

        def discover():
            devices = discover_directshow_audio_devices(resource_path("ffmpeg.exe"))
            self._deliver_audio_devices(devices)

        threading.Thread(target=discover, daemon=True).start()

    def _deliver_audio_devices(self, devices):
        try:
            self.audio_devices_discovered.emit(devices)
        except RuntimeError:
            logger.debug(
                "Recorder closed before audio device discovery completed",
                exc_info=True,
            )

    def _apply_audio_devices(self, devices):
        self.audio_discovery_running = False
        self.directshow_audio_devices = list(devices or [])
        for source_row in self.source_rows:
            combo = source_row[7]
            self.populate_audio_device_combo(combo, self._audio_device_value(combo))

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
        source_text = (source or "").strip().lower()
        return source_text.startswith(("rtsp://", "http://", "https://"))

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
                        pixmap.scaled(self.preview_boxes[row_index].size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
                cropped.scaled(self.preview_boxes[row_index].size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def _preview_finished(self, row_index, exit_code, process=None):
        if row_index < 0 or row_index >= len(self.preview_boxes):
            return
        if process is not None and self.preview_processes.get(row_index) is not process:
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
            self.preview_boxes[row_index].setText(
                _tr("Video %(number)s\nPreview interrupted\nReconnecting...")
                % {"number": row_index + 1})
            self._schedule_preview_retry(row_index, source_info)
        elif exit_code:
            self.preview_boxes[row_index].setText(
                _tr("Video %(number)s\nPreview unavailable\nCamera may be in use")
                % {"number": row_index + 1}
            )

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

    def stop_preview_processes(self):
        for row_index, process in list(self.preview_processes.items()):
            try:
                if process.state() != QProcess.NotRunning:
                    self.preview_stopping_rows.add(row_index)
                    if hasattr(process, "terminate"):
                        process.terminate()
                        finished = process.waitForFinished(1500) if hasattr(process, "waitForFinished") else True
                        if not finished and process.state() != QProcess.NotRunning:
                            process.kill()
                    else:
                        process.kill()
            except RuntimeError:
                continue
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
        legacy_output_mode = (settings or {}).get("output", {}).get("mode")
        normalized = normalize_recorder_settings(settings)
        output = normalized.get("output", {})
        if legacy_output_mode == "Picture-in-picture":
            self._append_log(
                _tr(
                    "[recorder] legacy Picture-in-picture mode mapped to Separate videos"
                )
            )
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
            try:
                if process.state() != QProcess.NotRunning:
                    self.preview_stopping_rows.add(row_index)
                    if hasattr(process, "terminate"):
                        process.terminate()
                    else:
                        process.kill()
            except RuntimeError:
                pass
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
        )

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
        if self.output_mode_combo.currentText() == "Combined grid" and len(selected) > 1:
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

    def _start_combined_grid_process(
        self,
        ffmpeg,
        selected,
        output_folder,
        timestamp,
        attempt=0,
        force_video_only=False,
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
        combined_sources = []
        combined_offsets = []
        for _row_index, _label, source, *option_items in selected:
            options = option_items[0] if option_items else {}
            combined_sources.append(apply_axis_rtsp_recording_options(
                source,
                frame_rate=(options or {}).get("frame_rate", ""),
                resolution=(options or {}).get("resolution", ""),
            ))
            combined_offsets.append((options or {}).get("offset", ""))
        command = build_combined_grid_record_command(
            ffmpeg,
            combined_sources,
            output_file,
            self.duration_edit.text().strip(),
            preview_pipe=self.auto_preview,
            offsets_per_source=combined_offsets,
            audio_device=audio_device,
            mute=not bool(audio_device),
            volume=audio_volume,
            quality=self.output_quality,
        )
        audio_fallback_command = None
        if audio_device:
            audio_fallback_command = build_combined_grid_record_command(
                ffmpeg,
                combined_sources,
                output_file,
                self.duration_edit.text().strip(),
                preview_pipe=self.auto_preview,
                offsets_per_source=combined_offsets,
                audio_device="",
                mute=True,
                volume="0",
                quality=self.output_quality,
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
            self._start_combined_grid_process(ffmpeg, selected, output_folder, timestamp, attempt=attempt)

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
        if not any(marker in error_text for marker in retry_markers):
            return False
        next_command = fallback_commands[0]
        remaining_commands = fallback_commands[1:]
        preview_pipe = getattr(process, "recording_preview_pipe", False)
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
