import os
import subprocess
import tempfile

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFileDialog, QPlainTextEdit, QComboBox, QListWidget, QMessageBox
)

from conversion.lossless_commands import (
    build_concat_command,
    build_extract_audio_command,
    build_remove_audio_command,
    build_remux_command,
    build_trim_command,
    format_concat_file_line,
)
from utils.file_naming import get_unique_path
from utils.resources import resource_path
from utils.subprocess_helpers import get_subprocess_startupinfo
from ui import theme


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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Lossless FFmpeg Editor")
        title.setStyleSheet(theme.tab_title_style())
        layout.addWidget(title)

        description = QLabel(
            "Fast stream-copy tools for trimming, remuxing, extracting audio, removing audio, and merging clips without re-encoding."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        file_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select a source media file")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_input)
        file_row.addWidget(QLabel("Input:"))
        file_row.addWidget(self.input_edit)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        time_row = QHBoxLayout()
        self.start_edit = QLineEdit("00:00:00")
        self.end_edit = QLineEdit("")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "mov", "avi", "m4a"])
        time_row.addWidget(QLabel("Start:"))
        time_row.addWidget(self.start_edit)
        time_row.addWidget(QLabel("End:"))
        time_row.addWidget(self.end_edit)
        time_row.addWidget(QLabel("Output:"))
        time_row.addWidget(self.format_combo)
        layout.addLayout(time_row)

        action_row = QHBoxLayout()
        self.trim_btn = QPushButton("Trim Losslessly")
        self.remux_btn = QPushButton("Remux")
        self.extract_audio_btn = QPushButton("Extract Audio")
        self.remove_audio_btn = QPushButton("Remove Audio")
        for button, handler in (
            (self.trim_btn, self.trim_losslessly),
            (self.remux_btn, self.remux),
            (self.extract_audio_btn, self.extract_audio),
            (self.remove_audio_btn, self.remove_audio),
        ):
            button.clicked.connect(handler)
            action_row.addWidget(button)
        layout.addLayout(action_row)

        merge_label = QLabel("Merge list:")
        layout.addWidget(merge_label)
        self.merge_list = QListWidget()
        self.merge_list.setAcceptDrops(False)
        layout.addWidget(self.merge_list)

        merge_row = QHBoxLayout()
        add_merge_btn = QPushButton("Add Files")
        clear_merge_btn = QPushButton("Clear")
        merge_btn = QPushButton("Merge Losslessly")
        add_merge_btn.clicked.connect(self.add_merge_files)
        clear_merge_btn.clicked.connect(self.merge_list.clear)
        merge_btn.clicked.connect(self.merge_losslessly)
        merge_row.addWidget(add_merge_btn)
        merge_row.addWidget(clear_merge_btn)
        merge_row.addWidget(merge_btn)
        layout.addLayout(merge_row)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("FFmpeg output appears here.")
        layout.addWidget(self.log_output)

        self.update_button_style(self.button_style)

    def update_button_style(self, button_style):
        self.button_style = button_style
        if not button_style:
            return
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(button_style)

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
            QMessageBox.warning(self, "Missing FFmpeg", "ffmpeg.exe could not be found.")
            return ""
        return path

    def _input_path(self):
        path = self.input_edit.text().strip()
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Missing Input", "Select a valid input media file first.")
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
            QMessageBox.warning(self, "Merge Files", "Add at least two valid files to merge.")
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
            QMessageBox.warning(self, "Merge Error", str(exc))
