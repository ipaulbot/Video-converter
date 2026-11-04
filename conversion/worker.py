import os
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from conversion.ffmpeg_utils import build_ffmpeg_command, build_gif_commands, preprocess_file
from utils.file_naming import get_unique_path
from utils.logger import logger
from utils.resources import resource_path
from utils.retention import add_pending_deletion

# Hides console windows on Windows.
from utils.subprocess_helpers import FFPROBE_TIMEOUT, get_subprocess_startupinfo


class WorkerSignals(QObject):
    log = pyqtSignal(str)
    conversion_complete = pyqtSignal(str, bool, dict)
    progress_update = pyqtSignal(str, int)  # file_path, percent

class ConversionWorker(QRunnable):
    def __init__(self, file_path, settings, signals):
        super().__init__()
        self.file_path = file_path
        self.settings = settings
        self.signals = signals
        self._cancel_requested = False
        self._process = None

    def cancel(self):
        """Cooperative cancel: request termination of the underlying ffmpeg process.
        Safe to call from UI thread. The worker thread handles teardown and final signals.
        """
        self._cancel_requested = True
        proc = getattr(self, '_process', None)
        if proc and proc.poll() is None:
            try:
                self.signals.log.emit("[cancel] Terminating FFmpeg…")
                proc.terminate()
            except Exception:
                logger.debug("ConversionWorker.cancel: suppressed error", exc_info=True)

    @pyqtSlot()
    def run(self):
        try:
            if not self.is_file_valid():
                logger.info(f"File {self.file_path} is invalid. Attempting to fix.")
                self.signals.log.emit(f"File {self.file_path} is corrupted or invalid.")
                if not preprocess_file(self.file_path):
                    self.signals.log.emit(f"Failed to fix file {self.file_path}. Skipping conversion.")
                    self.signals.conversion_complete.emit(os.path.basename(self.file_path), False, {"source_file": self.file_path})
                    return

            output_file = self.get_output_file_path()
            # GIF optimized two-pass handling
            if self.settings.get('output_format', 'mp4').lower() == 'gif':
                success = self.perform_gif_conversion(self.file_path, output_file)
            else:
                success = self.perform_conversion(self.file_path, output_file)
            deletion_info = {}
            if success:
                deletion_info['output_file'] = output_file
                deletion_info['source_file'] = self.file_path
                if self.settings.get('use_backup', False):
                    if not self.move_to_backup(self.file_path):
                        self.signals.log.emit(f"Failed to move {self.file_path} to backup.")
                elif self.settings.get('delete_after_conversion', False):
                    retention_days = int(self.settings.get('retention_time', 0))
                    if retention_days > 0:
                        deletion_time = datetime.now() + timedelta(days=retention_days)
                        # Persist pending deletions for robustness across restarts
                        try:
                            add_pending_deletion(self.file_path, deletion_time.timestamp())
                        except Exception:
                            logger.debug("ConversionWorker.run: suppressed error", exc_info=True)
                        # Also schedule a best-effort timer for this session.
                        # It MUST be a daemon: retention runs up to 30 days, and
                        # a non-daemon Timer blocks interpreter exit for its whole
                        # delay, so closing NVC would hang. Nothing is lost --
                        # add_pending_deletion above persists the deletion, and
                        # main.py processes overdue ones at startup.
                        timer = threading.Timer(retention_days * 86400,
                                                self.delete_file, args=[self.file_path])
                        timer.daemon = True
                        timer.start()
                        deletion_info['scheduled_deletion'] = deletion_time.strftime('%Y-%m-%d %H:%M:%S')
                        self.signals.log.emit(f"Scheduled deletion of {self.file_path} at {deletion_info['scheduled_deletion']}.")
                    else:
                        self.delete_file(self.file_path)
                if self._cancel_requested:
                    self.signals.conversion_complete.emit(os.path.basename(self.file_path), False, {"status":"canceled", "source_file": self.file_path})
                else:
                    self.signals.conversion_complete.emit(os.path.basename(self.file_path), True, deletion_info)
            else:
                if self._cancel_requested:
                    self.signals.conversion_complete.emit(os.path.basename(self.file_path), False, {"status":"canceled", "source_file": self.file_path})
                else:
                    self.signals.conversion_complete.emit(os.path.basename(self.file_path), False, {"source_file": self.file_path})
        except Exception as e:
            logger.error(f"Error during conversion of {self.file_path}: {e}")
            self.signals.conversion_complete.emit(os.path.basename(self.file_path), False, {"source_file": self.file_path})

    def is_file_valid(self):
        ffprobe_path = resource_path('ffprobe.exe')
        if not os.path.exists(ffprobe_path):
            self.signals.log.emit("ffprobe.exe not found.")
            return False
        command = [ffprobe_path, '-v', 'error', '-show_format', '-show_streams', self.file_path]
        try:
            startupinfo, creationflags = get_subprocess_startupinfo()
            subprocess.run(command, capture_output=True, text=True, check=True,
                           timeout=FFPROBE_TIMEOUT,
                           startupinfo=startupinfo, creationflags=creationflags)
            return True
        except subprocess.CalledProcessError:
            return False
        except subprocess.TimeoutExpired:
            logger.error("ffprobe timed out validating %s; treating as invalid.", self.file_path)
            return False

    def get_output_file_path(self):
        filename = os.path.basename(self.file_path)
        name, _ = os.path.splitext(filename)
        output_format = self.settings.get('output_format', 'mp4')
        output_filename = f"{name}.{output_format}"
        destination_folder = os.path.abspath(self.settings.get('destination_folder', ''))
        return get_unique_path(os.path.join(destination_folder, output_filename))

    def perform_conversion(self, input_file, output_file):
        ffmpeg_path = resource_path('ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            self.signals.log.emit("ffmpeg.exe not found.")
            return False
        command = build_ffmpeg_command(self.settings, input_file, output_file)
        total_duration = self.get_duration(input_file)
        if self._run_conversion_command(command, input_file, output_file, total_duration):
            return True
        if self._cancel_requested or not self.settings.get('use_gpu', False):
            return False
        cpu_settings = dict(self.settings)
        cpu_settings['use_gpu'] = False
        fallback_command = build_ffmpeg_command(cpu_settings, input_file, output_file)
        if fallback_command == command:
            return False
        try:
            if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
                os.remove(output_file)
        except OSError:
            pass
        self.signals.log.emit("[gpu] Hardware encoder failed; retrying with CPU encoder…")
        return self._run_conversion_command(fallback_command, input_file, output_file, total_duration)

    def _run_conversion_command(self, command, input_file, output_file, total_duration):
        startupinfo, creationflags = get_subprocess_startupinfo()
        try:
            with subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags
            ) as process:
                self._process = process
                percent = 0
                for line in process.stdout:
                    if self._cancel_requested:
                        try:
                            process.terminate()
                        except Exception:
                            logger.debug("ConversionWorker.perform_conversion: suppressed error", exc_info=True)
                        # Give it up to ~3s to die, else kill
                        for _ in range(30):
                            if process.poll() is not None:
                                break
                            # lightweight sleep without blocking UI thread
                            import time
                            time.sleep(0.1)
                        if process.poll() is None:
                            try:
                                process.kill()
                            except Exception:
                                logger.debug("ConversionWorker.perform_conversion: suppressed error", exc_info=True)
                        # Drain any remaining output quickly
                        try:
                            for _ in range(50):
                                if not process.stdout:
                                    break
                                chunk = process.stdout.readline()
                                if not chunk:
                                    break
                        except Exception:
                            logger.debug("ConversionWorker.perform_conversion: suppressed error", exc_info=True)
                        return False
                    line_str = line.rstrip('\n')
                    self.signals.log.emit(line_str)
                    if 'time=' in line_str and total_duration > 0:
                        # Parse time= value
                        match = re.search(r'time=([\d:.]+)', line_str)
                        if match:
                            time_str = match.group(1)
                            percent = int(self.time_to_seconds(time_str) / total_duration * 100)
                            if percent > 100:
                                percent = 100
                            self.signals.progress_update.emit(input_file, percent)
                # Wait non-blocking inside worker thread
                rc = process.wait()
                self._process = None
                return rc == 0 and not self._cancel_requested and self._output_file_ready(output_file)
        except Exception as e:
            self.signals.log.emit(f"Error during conversion: {e}")
            return False

    def perform_gif_conversion(self, input_file, output_file):
        """Run palette-optimized GIF encode (two-pass) or quick mode if configured."""
        ffmpeg_path = resource_path('ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            self.signals.log.emit("ffmpeg.exe not found.")
            return False
        # Temp palette path in destination folder
        temp_dir = os.path.dirname(output_file) or os.path.dirname(self.file_path)
        os.makedirs(temp_dir, exist_ok=True)
        palette_handle = tempfile.NamedTemporaryFile(prefix="nvc_palette_", suffix=".png", dir=temp_dir, delete=False)
        temp_palette = palette_handle.name
        palette_handle.close()
        try:
            os.remove(temp_palette)
        except OSError:
            pass
        palette_cmd, encode_cmd = build_gif_commands(self.settings, input_file, output_file, temp_palette)
        startupinfo, creationflags = get_subprocess_startupinfo()
        try:
            if palette_cmd is not None:
                # Pass 1: palette
                self.signals.log.emit("[gif] Generating palette…")
                p1 = subprocess.Popen(
                    palette_cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
                self._process = p1
                for _line in p1.stdout:
                    if self._cancel_requested:
                        try:
                            p1.terminate()
                        except Exception:
                            logger.debug("ConversionWorker.perform_gif_conversion: suppressed error", exc_info=True)
                        break
                rc1 = p1.wait()
                self._process = None
                if self._cancel_requested:
                    return False
                if rc1 != 0:
                    self.signals.log.emit("[gif] Palette generation failed.")
                    return False

            # Pass 2 or quick single pass
            self.signals.log.emit("[gif] Encoding GIF…")
            p2 = subprocess.Popen(
                encode_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            self._process = p2
            for line in p2.stdout:
                if self._cancel_requested:
                    try:
                        p2.terminate()
                    except Exception:
                        logger.debug("ConversionWorker.perform_gif_conversion: suppressed error", exc_info=True)
                    break
                self.signals.log.emit(line.rstrip('\n'))
            rc2 = p2.wait()
            self._process = None
            return (rc2 == 0) and not self._cancel_requested and self._output_file_ready(output_file)
        finally:
            # Cleanup palette
            try:
                if os.path.exists(temp_palette):
                    os.remove(temp_palette)
            except Exception:
                logger.debug("ConversionWorker.perform_gif_conversion: suppressed error", exc_info=True)

    def _output_file_ready(self, output_file):
        try:
            return os.path.exists(output_file) and os.path.getsize(output_file) > 0
        except OSError:
            return False

    def get_duration(self, file_path):
        ffprobe_path = resource_path('ffprobe.exe')
        if not os.path.exists(ffprobe_path):
            return 0
        command = [ffprobe_path, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        try:
            startupinfo, creationflags = get_subprocess_startupinfo()
            result = subprocess.run(command, capture_output=True, text=True, check=True,
                                   timeout=FFPROBE_TIMEOUT,
                                   startupinfo=startupinfo, creationflags=creationflags)
            return float(result.stdout.strip())
        except Exception:
            return 0

    def time_to_seconds(self, time_str):
        """Parse an ffmpeg progress timestamp: HH:MM:SS.xx, MM:SS.xx or SS.xx.

        Returns 0 for anything else. The bare-seconds branch is guarded on
        exactly one part: it used to be the `else`, so a four-part string
        returned its first component as a whole number of seconds, which would
        make the progress bar jump rather than fail.
        """
        parts = str(time_str).split(':')
        try:
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            if len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            if len(parts) == 1:
                return float(parts[0])
            return 0
        except (TypeError, ValueError):
            return 0

    def move_to_backup(self, file_path):
        backup_folder = os.path.abspath(self.settings.get('backup_folder', ''))
        try:
            if not os.path.exists(backup_folder):
                os.makedirs(backup_folder, exist_ok=True)
            shutil.move(file_path, backup_folder)
            self.signals.log.emit(f"Moved {file_path} to backup folder.")
            return True
        except Exception as e:
            self.signals.log.emit(f"Failed to move {file_path} to backup: {e}")
            return False

    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            self.signals.log.emit(f"Deleted {file_path}.")
        except Exception as e:
            self.signals.log.emit(f"Failed to delete {file_path}: {e}")
