import os
import subprocess
import tempfile

from PyQt5.QtCore import QCoreApplication, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from conversion.lossless_commands import (
    build_concat_command,
    build_extract_audio_command,
    build_remove_audio_command,
    build_remux_command,
    build_trim_command,
    format_concat_file_line,
)
from ui import theme
from ui.glyph_icons import make_icon_button, reskin_icon_buttons
from ui.tab_header import TabHeader
from utils.file_naming import get_unique_path
from utils.resources import resource_path
from utils.subprocess_helpers import get_subprocess_startupinfo


def _tr(source: str) -> str:
    """Translate this module's strings under the stable "LosslessEditor" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("LosslessEditor", source)

class LosslessWorker(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command

    def run(self):
        try:
            startupinfo, creationflags = get_subprocess_startupinfo()
            with subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
            ) as process:
                for line in process.stdout:
                    self.log.emit(line.rstrip())
                rc = process.wait()
            self.finished.emit(rc == 0, self.command[-1])
        except Exception as exc:
            self.log.emit(f"Error: {exc}")
            self.finished.emit(False, "")


class LosslessEditorWidget(QWidget):
    def __init__(self, supported_formats, parent=None, button_style=None):
        super().__init__(parent)
        self.supported_formats = supported_formats
        self.button_style = button_style
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.header = TabHeader(
            "scissors",
            _tr("Lossless Editor"),
            _tr("Trim, remux, extract or remove audio, and merge clips without re-encoding."),
        )
        layout.addWidget(self.header)

        file_row = QHBoxLayout()
        file_row.setSpacing(6)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(_tr("Select a source media file"))
        self.browse_btn = make_icon_button(
            "folder_open", _tr("Choose a source media file"), theme.skin().accent
        )
        self.browse_btn.clicked.connect(self.browse_input)
        file_row.addWidget(QLabel(_tr("Input:")))
        file_row.addWidget(self.input_edit, 1)
        file_row.addWidget(self.browse_btn)
        layout.addLayout(file_row)

        time_row = QHBoxLayout()
        time_row.setSpacing(6)
        self.start_edit = QLineEdit(_tr("00:00:00"))
        self.start_edit.setMaximumWidth(110)
        self.end_edit = QLineEdit("")
        self.end_edit.setMaximumWidth(110)
        self.end_edit.setPlaceholderText(_tr("end of file"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "mov", "avi", "m4a"])
        time_row.addWidget(QLabel(_tr("Start:")))
        time_row.addWidget(self.start_edit)
        time_row.addWidget(QLabel(_tr("End:")))
        time_row.addWidget(self.end_edit)
        time_row.addStretch(1)
        time_row.addWidget(QLabel(_tr("Output:")))
        time_row.addWidget(self.format_combo)
        layout.addLayout(time_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.trim_btn = QPushButton(_tr("Trim"))
        self.trim_btn.setToolTip(_tr("Cut Start to End without re-encoding"))
        self.remux_btn = QPushButton(_tr("Remux"))
        self.remux_btn.setToolTip(_tr("Copy every stream into the chosen container"))
        self.extract_audio_btn = QPushButton(_tr("Extract audio"))
        self.remove_audio_btn = QPushButton(_tr("Remove audio"))
        for button, handler in (
            (self.trim_btn, self.trim_losslessly),
            (self.remux_btn, self.remux),
            (self.extract_audio_btn, self.extract_audio),
            (self.remove_audio_btn, self.remove_audio),
        ):
            button.clicked.connect(handler)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            action_row.addWidget(button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.merge_list = QListWidget()
        self.merge_list.setAcceptDrops(False)
        self.merge_list.setMaximumHeight(120)
        self.merge_list.setStyleSheet(theme.list_box_style())   # grey box, not Qt's black frame

        merge_header = QHBoxLayout()
        merge_header.setSpacing(4)
        merge_label = QLabel(_tr("Merge list"))
        merge_label.setStyleSheet(theme.group_title_style())
        merge_header.addWidget(merge_label)
        merge_header.addStretch(1)
        accent = theme.skin().accent
        self.add_merge_btn = make_icon_button(
            "add_file", _tr("Add files to the merge list"), accent, size=24
        )
        self.clear_merge_btn = make_icon_button(
            "clear", _tr("Clear the merge list"), accent, size=24
        )
        self.merge_btn = QPushButton(_tr("Merge"))
        self.merge_btn.setToolTip(_tr("Concatenate the listed clips losslessly"))
        self.add_merge_btn.clicked.connect(self.add_merge_files)
        self.clear_merge_btn.clicked.connect(self.merge_list.clear)
        self.merge_btn.clicked.connect(self.merge_losslessly)
        merge_header.addWidget(self.add_merge_btn)
        merge_header.addWidget(self.clear_merge_btn)
        merge_header.addWidget(self.merge_btn)
        layout.addLayout(merge_header)
        layout.addWidget(self.merge_list)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText(_tr("FFmpeg output appears here."))
        layout.addWidget(self.log_output, 1)

        self._apply_tier_styles()

    def _apply_tier_styles(self):
        compact = theme.compact_button_style()
        accent = theme.skin().accent
        for button in (
            self.trim_btn,
            self.remux_btn,
            self.extract_audio_btn,
            self.remove_audio_btn,
            self.merge_btn,
        ):
            theme.opt_out_of_button_style(button)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(compact)
        reskin_icon_buttons(self, accent)

    def reskin(self):
        """Called by the main window on skin change; re-derive tiers from the skin."""
        self.header.reskin()
        self._apply_tier_styles()

    def update_button_style(self, button_style):
        self.button_style = button_style
        self.reskin()

    def browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Media File", "", "Media Files (*.*)")
        if path:
            self.input_edit.setText(path)

    def add_merge_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Merge", "", "Media Files (*.*)")
        for path in paths:
            self.merge_list.addItem(path)

    def _ffmpeg_path(self):
        path = resource_path("ffmpeg.exe")
        if not os.path.exists(path):
            QMessageBox.warning(self, _tr("Missing FFmpeg"), _tr("ffmpeg.exe could not be found."))
            return ""
        return path

    def _input_path(self):
        path = self.input_edit.text().strip()
        if not os.path.isfile(path):
            QMessageBox.warning(self, _tr("Missing Input"), _tr("Select a valid input media file first."))
            return ""
        return path

    def _output_path(self, suffix, extension=None):
        input_path = self._input_path()
        if not input_path:
            return ""
        directory = os.path.dirname(input_path)
        stem = os.path.splitext(os.path.basename(input_path))[0]
        ext = extension or self.format_combo.currentText()
        return get_unique_path(os.path.join(directory, f"{stem}_{suffix}.{ext}"))

    def _run_command(self, command):
        self.log_output.clear()
        self.log_output.appendPlainText(" ".join(f'"{part}"' if " " in part else part for part in command))
        self.worker = LosslessWorker(command, self)
        self.worker.log.connect(self.log_output.appendPlainText)
        self.worker.finished.connect(self._command_finished)
        self.worker.start()

    def _command_finished(self, success, output_file):
        if success:
            self.log_output.appendPlainText(f"Complete: {output_file}")
        else:
            self.log_output.appendPlainText("Operation failed.")

    def trim_losslessly(self):
        ffmpeg = self._ffmpeg_path()
        input_path = self._input_path()
        output_path = self._output_path("trim")
        if ffmpeg and input_path and output_path:
            self._run_command(build_trim_command(ffmpeg, input_path, output_path, self.start_edit.text().strip(), self.end_edit.text().strip()))

    def remux(self):
        ffmpeg = self._ffmpeg_path()
        input_path = self._input_path()
        output_path = self._output_path("remux")
        if ffmpeg and input_path and output_path:
            self._run_command(build_remux_command(ffmpeg, input_path, output_path))

    def extract_audio(self):
        ffmpeg = self._ffmpeg_path()
        input_path = self._input_path()
        output_path = self._output_path("audio", "m4a")
        if ffmpeg and input_path and output_path:
            self._run_command(build_extract_audio_command(ffmpeg, input_path, output_path))

    def remove_audio(self):
        ffmpeg = self._ffmpeg_path()
        input_path = self._input_path()
        output_path = self._output_path("silent")
        if ffmpeg and input_path and output_path:
            self._run_command(build_remove_audio_command(ffmpeg, input_path, output_path))

    def merge_losslessly(self):
        ffmpeg = self._ffmpeg_path()
        files = [self.merge_list.item(i).text() for i in range(self.merge_list.count())]
        files = [path for path in files if os.path.isfile(path)]
        if not ffmpeg or len(files) < 2:
            QMessageBox.warning(self, _tr("Merge Files"), _tr("Add at least two valid files to merge."))
            return
        first = files[0]
        ext = self.format_combo.currentText()
        output_path = get_unique_path(os.path.join(os.path.dirname(first), f"merged_lossless.{ext}"))
        list_file = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        try:
            with list_file:
                for path in files:
                    list_file.write(format_concat_file_line(path) + "\n")
            self._run_command(build_concat_command(ffmpeg, list_file.name, output_path))
        except Exception as exc:
            QMessageBox.warning(self, _tr("Merge Error"), str(exc))
