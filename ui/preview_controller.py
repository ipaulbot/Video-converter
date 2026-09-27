
"""The sidebar video preview: an ffmpeg-decoded player in a 180x101 box.

Extracted from ui/main_window.py, where these 18 methods and ~150 lines of
widget construction sat among the watchdog, the tray icon, the conversion
queue and two easter eggs.

QMediaPlayer/QVideoWidget are deliberately not used: on Windows they depend on
installed DirectShow codecs and frequently render black. Frames are decoded by
piping `ffmpeg -f rawvideo -pix_fmt rgb24` into a QProcess and assembling
QImages from the byte stream, which is why the box has a fixed size -- the
frame size has to be known to split the pipe into frames.

The controller owns its widgets; the host adds `controller.preview_container`
to its own layout and calls `shutdown()` before closing.
"""
from __future__ import annotations

import os
import subprocess

from PyQt5.QtCore import QCoreApplication, QEvent, QObject, QProcess, QSize, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QPushButton,
    QSlider,
    QStackedLayout,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui import theme
from ui.leaf_frame import LeafPixmapLabel
from utils.logger import logger
from utils.resources import resource_path
from utils.subprocess_helpers import (
    FFMPEG_RENDER_TIMEOUT,
    FFPROBE_TIMEOUT,
    get_subprocess_startupinfo,
)


def _tr(source: str) -> str:
    """Translate this module's strings under the stable "Preview" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("Preview", source)



class PreviewController(QObject):
    """Owns the sidebar preview box and its ffmpeg decode pipeline."""

    def __init__(self, host, parent=None):
        super().__init__(parent or host)
        # The host is used for style() (Qt standard icons) and for the theme
        # state sync, which depends on the app's lock/activity flags.
        self._host = host
        self._build()

    def _build(self):
        # --- Video Preview Panel (below logo) ---
        # NOTE: We intentionally avoid QMediaPlayer/QVideoWidget here because on Windows it depends on
        # installed DirectShow codecs and often renders black. We decode frames with ffmpeg instead.
        self.preview_container = QFrame()
        self.preview_container.setStyleSheet(theme.preview_box_style())
        # Keep aspect ratio 16:9 and match sidebar content width for clean alignment
        # (the context header and Start button are fixedWidth(180) too)
        self.preview_container.setFixedSize(180, 101)
        self.preview_container.setMouseTracking(True)  # Enable mouse tracking for hover events
        self.preview_container.setAttribute(Qt.WA_Hover, True)  # Enable hover events
        self.preview_w = self.preview_container.width()
        self.preview_h = self.preview_container.height()

        self.preview_layout = QStackedLayout(self.preview_container)
        self.preview_layout.setStackingMode(QStackedLayout.StackAll)
        self.preview_layout.setContentsMargins(0,0,0,0)

        # 1. Preview Label (thumbnail + decoded frames), painted inside the leaf
        # outline so a frame never squares off the container's rounded corners.
        # Idle is a blank leaf: a caption would read as an error on tabs that
        # simply have nothing to preview.
        self.preview_label = LeafPixmapLabel("", radius=18)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(theme.preview_placeholder_style())
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
        self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.setIconSize(QSize(12, 12))
        # VideoConverterApp.apply_button_style_to_all_widgets walks the whole
        # widget tree and stamps the main gradient onto every QPushButton it
        # finds. This one is a 22px translucent circle floating over a video
        # thumbnail, so it has to opt out of that, using the property the
        # walker already checks -- otherwise its own style is overwritten
        # moments after being set.
        self.play_pause_btn.setProperty('skipGlobalStyle', True)
        # Styled by update_preview_controls_style() at the end of _build.
        self.play_pause_btn.hide()
        self.play_pause_btn.clicked.connect(self.toggle_preview_playback)

        # Progress scrubber (thin slider)
        self.preview_scrubber = QSlider(Qt.Horizontal)
        self.preview_scrubber.setRange(0, 1000)
        self.preview_scrubber.setValue(0)
        self.preview_scrubber.setFixedHeight(10)
        self.preview_scrubber.setMouseTracking(True)
        self.preview_scrubber.setCursor(Qt.PointingHandCursor)
        # Styled by update_preview_controls_style() at the end of _build.
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

        # PC Report heartbeat: a red heart pulsing in the otherwise blank leaf
        # while a report runs. Painted here, not in the PC Report tab, so the
        # sidebar shows the work of the tool that owns it.
        self.heartbeat_active = False
        self._heartbeat_scale = 1.0
        self._heartbeat_tick = 0
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(self.HEARTBEAT_TICK_MS)
        self._heartbeat_timer.timeout.connect(self._tick_heartbeat)
        self.update_preview_controls_style()

    # -- heartbeat ------------------------------------------------------
    HEARTBEAT_PERIOD_MS = 900
    HEARTBEAT_TICK_MS = 50
    HEARTBEAT_COLOR = "#f75f5f"

    def show_heartbeat(self, active):
        """Pulse a red heart in the leaf (True) or return to the idle state (False)."""
        active = bool(active)
        if active == self.heartbeat_active:
            return
        self.heartbeat_active = active
        if active:
            self.play_pause_btn.hide()
            self.preview_scrubber.hide()
            self._heartbeat_tick = 0
            self._paint_heartbeat()
            self._heartbeat_timer.start()
            return
        self._heartbeat_timer.stop()
        self._heartbeat_scale = 1.0
        if self.preview_source_path and not self.preview_playing:
            # Hand the leaf back to the file that was being previewed.
            self._generate_and_show_thumbnail(self.preview_source_path)
        elif not self.preview_source_path:
            self._set_preview_placeholder()

    def _tick_heartbeat(self):
        self._heartbeat_tick += 1
        self._paint_heartbeat()

    def _paint_heartbeat(self):
        import math

        from PyQt5.QtGui import QColor, QPainter, QPainterPath

        phase = (self._heartbeat_tick * self.HEARTBEAT_TICK_MS % self.HEARTBEAT_PERIOD_MS) / self.HEARTBEAT_PERIOD_MS
        self._heartbeat_scale = 1.0 + 0.1 * math.sin(2 * math.pi * phase)
        w, h = self.preview_w, self.preview_h
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.HEARTBEAT_COLOR))
        size = h * 0.55 * self._heartbeat_scale
        painter.translate(w / 2, h / 2 + size * 0.05)
        painter.scale(size / 100.0, size / 100.0)
        # A heart on a 100-unit canvas centred on the origin.
        heart = QPainterPath()
        heart.moveTo(0, 45)
        heart.cubicTo(-70, 0, -40, -55, 0, -25)
        heart.cubicTo(40, -55, 70, 0, 0, 45)
        heart.closeSubpath()
        painter.drawPath(heart)
        painter.end()
        self.preview_label.setText("")
        self.preview_label.setPixmap(pixmap)

    def eventFilter(self, obj, event):
        """Show the play button and scrubber while the pointer is over the box.

        Lifted out of VideoConverterApp.eventFilter, which was handling three
        unrelated widgets' hover behaviour in one method.
        """
        if obj in (self.preview_container, self.preview_label, self.overlay_container):
            if event.type() in (QEvent.Enter, QEvent.HoverEnter):
                if bool(self.preview_source_path):
                    self.play_pause_btn.show()
                    self.overlay_container.raise_()
                    if self.preview_duration_sec > 0:
                        self.preview_scrubber.show()
            elif event.type() in (QEvent.Leave, QEvent.HoverLeave):
                self.play_pause_btn.hide()
                self.preview_scrubber.hide()
            elif event.type() == QEvent.MouseButtonPress:
                if bool(self.preview_source_path):
                    self.toggle_preview_playback()
                return True
        return super().eventFilter(obj, event)

    # -- lifecycle ------------------------------------------------------
    def shutdown(self):
        """Stop the ffmpeg process and every timer. Call before teardown."""
        self._stop_preview_process()
        self._stop_star_field()
        try:
            self.preview_ui_timer.stop()
            self._heartbeat_timer.stop()
        except RuntimeError:
            logger.debug("PreviewController.shutdown: timer already gone", exc_info=True)

    def toggle_preview_playback(self):
        """Toggle play/pause state of the preview player (ffmpeg-decoded frames)."""
        if not self.preview_source_path or not os.path.exists(self.preview_source_path):
            return

        # Toggle
        if self.preview_playing:
            # Pause: stop ffmpeg but keep last frame, store timestamp via frame index
            self.preview_playing = False
            self._stop_preview_process()
            self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))
            self.play_pause_btn.show()
            return

        # Play: start (or resume from approximate timestamp)
        self.preview_playing = True
        self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPause))
        self.play_pause_btn.show()
        self.overlay_container.raise_()
        if getattr(self, 'preview_duration_sec', 0.0) > 0:
            self.preview_scrubber.show()
        self._start_preview_process(self.preview_source_path, seek_seconds=self.preview_seek_seconds)

    def _set_preview_placeholder(self, text=None):
        """Show `text` in the empty leaf; None (the idle state) shows nothing."""
        if text is None:
            text = ""
        try:
            # Was a fourth copy of the locked/active/idle colour chain.
            self._host._sync_theme_skin()
            theme_color = theme.skin().accent

            # Clear any pixmap, then set text and style
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(text)
            self.preview_label.setStyleSheet(
                theme.preview_placeholder_style(theme_color))
        except Exception as e:
            logger.error(f"Error setting preview placeholder: {e}")

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
            self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))
        except Exception:
            logger.debug("VideoConverterApp._clear_preview_display: suppressed error", exc_info=True)
        self._set_preview_placeholder()

    def _start_star_field(self, theme_name=None):
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
        # The three legacy names map onto the three skins. Callers may still
        # pass 'gray'/'teal'/'green'; None follows the app's current state.
        skin_for_name = {
            'gray': theme.LOCKED,
            'teal': theme.IDLE,
            'green': theme.ACTIVE,
        }
        chosen = skin_for_name.get(theme_name) if theme_name else None
        if chosen is None:
            self._host._sync_theme_skin()
            chosen = theme.skin()
        self.star_color = QColor(chosen.accent)
        self.star_bg_color = QColor(chosen.panel_bg)

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

        from PyQt5.QtGui import QPainter, QPixmap

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
                self._set_preview_placeholder()
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
                self._set_preview_placeholder(_tr("ffmpeg missing"))
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
                self._set_preview_placeholder()
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            self._set_preview_placeholder()

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
            self._set_preview_placeholder(_tr("ffmpeg missing"))
            self.preview_playing = False
            self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))
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
            self._set_preview_placeholder(_tr("Preview failed"))
            self.preview_playing = False
            self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))

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
        """Read whatever ffmpeg has produced and render any complete frames."""
        try:
            data = bytes(self.preview_process.readAllStandardOutput())
            if not data:
                return
            self._preview_buf += data
            self._assemble_frames()
        except Exception as e:
            logger.error(f"Preview decode error: {e}")
            self.preview_playing = False
            self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))
            self._stop_preview_process()

    def _assemble_frames(self):
        """Turn buffered bytes into frames, leaving any partial tail buffered.

        Split out from _on_preview_bytes so it can be driven from a byte
        buffer in a test without starting ffmpeg. The stream carries no frame
        delimiters -- frames are a fixed rgb24 byte count -- which is why the
        preview box has a fixed size and why a stale buffer must be cleared
        whenever the process stops.
        """
        while len(self._preview_buf) >= self._preview_frame_size:
            frame = self._preview_buf[:self._preview_frame_size]
            del self._preview_buf[:self._preview_frame_size]

            img = QImage(bytes(frame), self.preview_w, self.preview_h,
                         QImage.Format_RGB888).copy()
            self.preview_label.setText("")
            self.preview_label.setPixmap(QPixmap.fromImage(img))
            self.preview_frame_index += 1
            self.preview_seek_seconds = self.preview_frame_index / float(self.preview_fps)

    def _on_preview_finished(self, *args):
        # Playback ended or process stopped; keep last frame displayed
        self.preview_playing = False
        self.play_pause_btn.setIcon(self._host.style().standardIcon(QStyle.SP_MediaPlay))


    def update_preview_controls_style(self):
        self._host._sync_theme_skin()
        highlight = theme.highlight_color()

        if hasattr(self, 'play_pause_btn'):
            self.play_pause_btn.setStyleSheet(
                theme.preview_overlay_button_style(highlight))
        if hasattr(self, 'preview_scrubber'):
            self.preview_scrubber.setStyleSheet(
                theme.preview_scrubber_style(highlight))

