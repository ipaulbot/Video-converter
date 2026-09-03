import os
import json
import subprocess

from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QTabWidget, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from utils.resources import resource_path
from ui import theme
from utils.logger import logger
from utils.subprocess_helpers import (
    FFMPEG_RENDER_TIMEOUT,
    FFPROBE_TIMEOUT,
    get_subprocess_startupinfo,
)

class InspectionWorker(QThread):
    finished = pyqtSignal(str, str, str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        ffprobe_path = resource_path('ffprobe.exe')
        command = [ffprobe_path, '-v', 'error', '-show_format', '-show_streams', '-print_format', 'json', self.file_path]
        keyframe_command = [
            ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'packet=pts_time,flags',
            '-of', 'csv=print_section=0',
            '-read_intervals', '%+30',
            self.file_path,
        ]
        startupinfo, creationflags = get_subprocess_startupinfo()
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    timeout=FFPROBE_TIMEOUT,
                                    startupinfo=startupinfo, creationflags=creationflags, check=True)
            try:
                gop_result = subprocess.run(keyframe_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                            timeout=FFMPEG_RENDER_TIMEOUT,
                                            startupinfo=startupinfo, creationflags=creationflags)
                keyframe_csv = gop_result.stdout or ''
            except Exception:
                keyframe_csv = ''
            self.finished.emit(result.stdout or '', keyframe_csv, '')
        except subprocess.CalledProcessError as e:
            self.finished.emit('', '', f"Error inspecting file:\n{e.stderr}")
        except Exception as e:
            self.finished.emit('', '', f"Error inspecting file:\n{e}")

class InspectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()

        # Summary tab with drag and drop area
        self.summary_tab = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_tab)
        # No margins - they are set at the tab level
        self.summary_layout.setContentsMargins(0, 0, 0, 0)

        # Create drag and drop area for summary
        self.summary_drag_drop = QWidget()
        self.summary_drag_drop.setStyleSheet(theme.drop_zone_style())
        self.summary_drag_drop.setMinimumHeight(120)
        self.summary_drag_drop.setAcceptDrops(True)

        summary_drag_layout = QVBoxLayout(self.summary_drag_drop)
        summary_drag_layout.setAlignment(Qt.AlignCenter)

        # Drag and drop text
        self.summary_drag_text = QLabel("Drag and drop media files here to see summary")
        self.summary_drag_text.setAlignment(Qt.AlignCenter)
        self.summary_drag_text.setObjectName("dragDropLabel")
        self.summary_drag_text.setStyleSheet(theme.drop_zone_label_style("dragDropLabel"))
        self.summary_drag_text.setWordWrap(True)

        summary_drag_layout.addWidget(self.summary_drag_text)

        # Create summary text widget and add it to the drag drop area
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.hide()  # Initially hidden
        self.summary_text.setFrameStyle(0)  # Remove frame completely
        self.summary_text.setStyleSheet("""
            QPlainTextEdit {
                background: transparent;
                border: none;
                outline: none;
                margin: 0px;
                padding: 0px;
            }
            QPlainTextEdit QScrollBar {
                background: transparent;
                border: none;
            }
            QPlainTextEdit QScrollBar::handle {
                background: transparent;
                border: none;
            }
            QPlainTextEdit QScrollBar::add-line,
            QPlainTextEdit QScrollBar::sub-line {
                background: transparent;
                border: none;
            }
        """)
        summary_drag_layout.addWidget(self.summary_text)

        # Connect drag and drop events
        self.summary_drag_drop.dragEnterEvent = self.summary_drag_enter
        self.summary_drag_drop.dragLeaveEvent = self.summary_drag_leave
        self.summary_drag_drop.dropEvent = self.summary_drop

        self.summary_layout.addWidget(self.summary_drag_drop)
        self.summary_tab.setLayout(self.summary_layout)

        # JSON tab with drag and drop area
        self.json_tab = QWidget()
        self.json_layout = QVBoxLayout(self.json_tab)
        # No margins - they are set at the tab level
        self.json_layout.setContentsMargins(0, 0, 0, 0)

        # Create drag and drop area for JSON
        self.json_drag_drop = QWidget()
        self.json_drag_drop.setStyleSheet(theme.drop_zone_style())
        self.json_drag_drop.setMinimumHeight(120)
        self.json_drag_drop.setAcceptDrops(True)

        json_drag_layout = QVBoxLayout(self.json_drag_drop)
        json_drag_layout.setAlignment(Qt.AlignCenter)

        # Drag and drop text
        self.json_drag_text = QLabel("Drag and drop media files here for detailed JSON")
        self.json_drag_text.setAlignment(Qt.AlignCenter)
        self.json_drag_text.setObjectName("dragDropLabelJSON")
        self.json_drag_text.setStyleSheet(theme.drop_zone_label_style("dragDropLabelJSON"))
        self.json_drag_text.setWordWrap(True)

        json_drag_layout.addWidget(self.json_drag_text)

        # Create info display widget and add it to the drag drop area
        self.info_display = QPlainTextEdit()
        self.info_display.setReadOnly(True)
        self.info_display.setToolTip("Raw JSON data from ffprobe.")
        self.info_display.hide()  # Initially hidden
        self.info_display.setFrameStyle(0)  # Remove frame completely
        self.info_display.setStyleSheet("""
            QPlainTextEdit {
                background: transparent;
                border: none;
                outline: none;
                margin: 0px;
                padding: 0px;
            }
            QPlainTextEdit QScrollBar {
                background: transparent;
                border: none;
                width: 0px;
            }
            QPlainTextEdit QScrollBar::handle {
                background: transparent;
                border: none;
            }
            QPlainTextEdit QScrollBar::add-line,
            QPlainTextEdit QScrollBar::sub-line {
                background: transparent;
                border: none;
                height: 0px;
            }
            QPlainTextEdit QScrollBar::up-arrow,
            QPlainTextEdit QScrollBar::down-arrow {
                background: transparent;
                border: none;
                height: 0px;
            }
        """)
        json_drag_layout.addWidget(self.info_display)

        # Connect drag and drop events
        self.json_drag_drop.dragEnterEvent = self.json_drag_enter
        self.json_drag_drop.dragLeaveEvent = self.json_drag_leave
        self.json_drag_drop.dropEvent = self.json_drop

        self.json_layout.addWidget(self.json_drag_drop)
        self.json_tab.setLayout(self.json_layout)

        self.tabs.addTab(self.summary_tab, "Summary")
        self.tabs.addTab(self.json_tab, "Detailed JSON")
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def summary_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.summary_drag_drop.setStyleSheet(theme.drop_zone_active_style())
            # Keep instruction consistent
            self.summary_drag_text.setText("Drag and drop media files here to see summary")
        else:
            event.ignore()

    def summary_drag_leave(self, event):
        self.summary_drag_drop.setStyleSheet(theme.drop_zone_style())
        self.summary_drag_text.setText("Drag and drop media files here to see summary")

    def summary_drop(self, event):
        self.summary_drag_drop.setStyleSheet(theme.drop_zone_style())
        self.summary_drag_text.setText("Drag and drop media files here to see summary")

        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            # Populate both summary and detailed JSON in one drop
            self.inspect_file(file_path)

    def json_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.json_drag_drop.setStyleSheet(theme.drop_zone_active_style())
            self.json_drag_text.setText("Drag and drop media files here for detailed JSON")
        else:
            event.ignore()

    def json_drag_leave(self, event):
        self.json_drag_drop.setStyleSheet(theme.drop_zone_style())
        self.json_drag_text.setText("Drag and drop media files here for detailed JSON")

    def json_drop(self, event):
        self.json_drag_drop.setStyleSheet(theme.drop_zone_style())
        self.json_drag_text.setText("Drag and drop media files here for detailed JSON")

        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            # Populate both summary and detailed JSON in one drop
            self.inspect_file(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.inspect_file(file_path)

    def inspect_file_summary(self, file_path):
        """Inspect file and show summary, keeping drag drop overlay visible."""
        # Hide the instruction text but keep the overlay visible
        self.summary_drag_text.hide()
        self.summary_text.show()
        self.summary_text.clear()
        self._notify_main_preview(file_path)

        if not os.path.isfile(file_path):
            self.summary_text.setPlainText("File not found.")
            return

        ffprobe_path = resource_path('ffprobe.exe')
        if not os.path.exists(ffprobe_path):
            self.summary_text.setPlainText("ffprobe.exe not found.")
            return

        command = [ffprobe_path, '-v', 'error', '-show_format', '-show_streams', '-print_format', 'json', file_path]

        # Additional command for keyframe interval using select filter (read 1000 frames max to estimate)
        # We can estimate GOP size by finding distance between I-frames.
        # This is a bit slow for large files, so we might want to run it in a thread or limit it.
        # For now, let's just get the first few GOPs.
        keyframe_command = [
            ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'packet=pts_time,flags',
            '-of', 'csv=print_section=0',
            '-read_intervals', '%+30', # Read first 30 seconds
            file_path
        ]

        startupinfo, creationflags = get_subprocess_startupinfo()
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      timeout=FFPROBE_TIMEOUT,
                                      startupinfo=startupinfo, creationflags=creationflags, check=True)
            data = json.loads(result.stdout)

            # Get keyframe info (best effort)
            try:
                gop_result = subprocess.run(keyframe_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                          timeout=FFMPEG_RENDER_TIMEOUT,
                                          startupinfo=startupinfo, creationflags=creationflags)
                keyframe_info = self.analyze_keyframes(gop_result.stdout)
            except Exception:
                keyframe_info = "Keyframe info: N/A (Error analyzing)"

            summary = self.generate_summary(data)
            if keyframe_info:
                summary += f"\n{keyframe_info}"

            self.summary_text.setPlainText(summary)
        except subprocess.TimeoutExpired:
            self.summary_text.setPlainText(
                f"Timed out reading this file after {FFPROBE_TIMEOUT} seconds.\n"
                "The file may be on a slow or disconnected drive.")
        except subprocess.CalledProcessError as e:
            err_msg = f"Error inspecting file:\n{e.stderr}"
            self.summary_text.setPlainText(err_msg)

    def analyze_keyframes(self, csv_data):
        """Analyze ffprobe packet data to find I-frame intervals."""
        if not csv_data:
            return ""

        last_pts = None
        intervals = []

        # Parse CSV: pts_time,flags (e.g. 0.000000,K_)
        # We look for 'K' (Keyframe)
        for line in csv_data.splitlines():
            parts = line.strip().split(',')
            if len(parts) >= 2:
                pts = float(parts[0]) if parts[0].strip() else 0
                flags = parts[1]
                if 'K' in flags:
                    if last_pts is not None:
                        intervals.append(pts - last_pts)
                    last_pts = pts

        if not intervals:
            return "Keyframe Interval: Unable to determine (No keyframes found in first 30s)"

        avg_interval = sum(intervals) / len(intervals)
        min_int = min(intervals)
        max_int = max(intervals)

        return (f"\n--- Keyframe Analysis (First 30s) ---\n"
                f"Average Interval: {avg_interval:.2f}s\n"
                f"Min Interval: {min_int:.2f}s\n"
                f"Max Interval: {max_int:.2f}s\n"
                f"Total Keyframes found: {len(intervals) + 1}")


    def inspect_file_json(self, file_path):
        """Inspect file and show JSON, keeping drag drop overlay visible."""
        # Hide the instruction text but keep the overlay visible
        self.json_drag_text.hide()
        self.info_display.show()
        self.info_display.clear()
        self._notify_main_preview(file_path)

        if not os.path.isfile(file_path):
            self.info_display.setPlainText("File not found.")
            return

        ffprobe_path = resource_path('ffprobe.exe')
        if not os.path.exists(ffprobe_path):
            self.info_display.setPlainText("ffprobe.exe not found.")
            return

        command = [ffprobe_path, '-v', 'error', '-show_format', '-show_streams', '-print_format', 'json', file_path]
        startupinfo, creationflags = get_subprocess_startupinfo()
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      timeout=FFPROBE_TIMEOUT,
                                      startupinfo=startupinfo, creationflags=creationflags, check=True)
            raw_json = result.stdout
            self.info_display.setPlainText(raw_json)
        except subprocess.TimeoutExpired:
            self.info_display.setPlainText(
                f"Timed out reading this file after {FFPROBE_TIMEOUT} seconds.\n"
                "The file may be on a slow or disconnected drive.")
        except subprocess.CalledProcessError as e:
            err_msg = f"Error inspecting file:\n{e.stderr}"
            self.info_display.setPlainText(err_msg)

    def inspect_file(self, file_path):
        """Inspect a file in the background and populate both tabs."""
        self.summary_drag_text.hide()
        self.json_drag_text.hide()
        self.summary_text.show()
        self.info_display.show()
        self.summary_text.setPlainText("Inspecting file...")
        self.info_display.setPlainText("Inspecting file...")
        self._notify_main_preview(file_path)

        if not os.path.isfile(file_path):
            self.summary_text.setPlainText("File not found.")
            self.info_display.setPlainText("File not found.")
            return

        ffprobe_path = resource_path('ffprobe.exe')
        if not os.path.exists(ffprobe_path):
            self.summary_text.setPlainText("ffprobe.exe not found.")
            self.info_display.setPlainText("ffprobe.exe not found.")
            return

        if hasattr(self, '_inspection_worker') and self._inspection_worker and self._inspection_worker.isRunning():
            self._inspection_worker.requestInterruption()
            self._inspection_worker.wait(250)
        self._inspection_worker = InspectionWorker(file_path, self)
        self._inspection_worker.finished.connect(self._inspection_finished)
        self._inspection_worker.start()

    def _inspection_finished(self, raw_json, keyframe_csv, error):
        if error:
            self.summary_text.setPlainText(error)
            self.info_display.setPlainText(error)
            return
        try:
            data = json.loads(raw_json)
            summary = self.generate_summary(data)
            keyframe_info = self.analyze_keyframes(keyframe_csv)
            if keyframe_info:
                summary += f"\n{keyframe_info}"
            self.summary_text.setPlainText(summary)
            self.info_display.setPlainText(raw_json)
        except Exception as e:
            self.summary_text.setPlainText(f"Error parsing ffprobe output:\n{e}")
            self.info_display.setPlainText(raw_json or "")

    def _notify_main_preview(self, file_path):
        """Tell parent (main window) to update the sidebar preview, if available."""
        try:
            widget = self
            while widget is not None:
                if hasattr(widget, 'preview_file') and callable(widget.preview_file):
                    widget.preview_file(file_path)
                    return
                widget = widget.parent()
        except Exception:
            logger.debug("InspectionWidget._notify_main_preview: suppressed error", exc_info=True)

    def generate_summary(self, data):
        format_info = data.get("format", {})
        streams = data.get("streams", [])

        filename = format_info.get("filename", "Unknown")
        duration = self.format_duration(format_info.get("duration", "0"))
        size_bytes = int(format_info.get("size", 0))
        size_mb = size_bytes / (1024 * 1024)
        container = format_info.get("format_long_name", "Unknown Format")
        overall_bitrate = self.format_bitrate(format_info.get("bit_rate", "0"))
        stream_count = format_info.get("nb_streams", 0)

        summary_lines = [
            f"File: {filename}",
            f"Container: {container}",
            f"Duration: {duration}",
            f"Size: {size_mb:.2f} MB",
            f"Bitrate: {overall_bitrate}",
            f"Number of Streams: {stream_count}",
            ""
        ]

        video_count = 0
        audio_count = 0
        subtitle_count = 0

        for s in streams:
            codec_type = s.get("codec_type", "unknown")
            if codec_type == "video":
                video_count += 1
                summary_lines.append("=== Video Stream ===")
                codec = s.get("codec_name", "Unknown")
                w = s.get("width", "unknown")
                h = s.get("height", "unknown")
                avg_fr = self.format_framerate(s.get("avg_frame_rate", "0/0"))
                vid_duration = self.calculate_stream_duration(s)
                r_fr = self.format_framerate(s.get("r_frame_rate", "0/0"))
                summary_lines.extend([
                    f"Codec: {codec}",
                    f"Resolution: {w}x{h}",
                    f"Avg Frame Rate: {avg_fr}",
                    f"Raw Frame Rate: {r_fr}",
                    f"Video Duration: {vid_duration}",
                    ""
                ])
            elif codec_type == "audio":
                audio_count += 1
                summary_lines.append("=== Audio Stream ===")
                codec = s.get("codec_name", "Unknown")
                channels = s.get("channels", 0)
                layout = s.get("channel_layout", "Unknown")
                sr = s.get("sample_rate", "Unknown")
                aud_duration = self.calculate_stream_duration(s)
                abr = self.format_bitrate(s.get("bit_rate", "0"))
                summary_lines.extend([
                    f"Codec: {codec}",
                    f"Channels: {channels} ({layout})",
                    f"Sample Rate: {sr} Hz",
                    f"Audio Bitrate: {abr}",
                    f"Audio Duration: {aud_duration}",
                    ""
                ])
            elif codec_type == "subtitle":
                subtitle_count += 1
                summary_lines.append("=== Subtitle Stream ===")
                codec = s.get("codec_name", "Unknown")
                st_duration = self.calculate_stream_duration(s)
                summary_lines.extend([
                    f"Codec: {codec}",
                    f"Subtitle Duration: {st_duration}",
                    ""
                ])

        if video_count == 0 and audio_count == 0 and subtitle_count == 0:
            summary_lines.append("No recognized streams found.")

        return "\n".join(summary_lines)

    def format_duration(self, duration_str):
        try:
            duration = float(duration_str)
            hours = int(duration // 3600)
            mins = int((duration % 3600) // 60)
            secs = int(duration % 60)
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        except (TypeError, ValueError):
            return "Unknown"

    def format_bitrate(self, bitrate_str):
        try:
            br = int(bitrate_str)
            kbps = br / 1000.0
            return f"{kbps:.1f} kbps"
        except (TypeError, ValueError):
            return "Unknown"

    def format_framerate(self, fr_str):
        if fr_str in ("0/0", "0"):
            return "Unknown"
        try:
            num, den = fr_str.split('/')
            fr = float(num) / float(den)
            return f"{fr:.2f} fps"
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            return "Unknown"

    def calculate_stream_duration(self, stream):
        dur = stream.get("duration", None)
        if dur is None:
            duration_ts = stream.get("duration_ts", None)
            time_base = stream.get("time_base", "1/1")
            if duration_ts is not None:
                try:
                    num, den = time_base.split('/')
                    dur = float(duration_ts) * (float(num)/float(den))
                except (AttributeError, TypeError, ValueError, ZeroDivisionError):
                    dur = None
        if dur is None:
            return "Unknown"
        return self.format_duration(str(dur))
