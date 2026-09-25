import os
import threading

from PyQt5.QtCore import (
    QCoreApplication,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QShortcut,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from conversion.worker import ConversionWorker, WorkerSignals
from ui import theme
from ui.glyph_icons import (
    glyph_icon,
    make_icon_button,
    reskin_icon_buttons,
    set_button_glyph,
)
from ui.media_player_parts import FullscreenHost, PlaylistDock, UnsupportedOverlay
from ui.media_player_support import (
    MEDIA_PLAYER_DEFAULTS,
    PlaylistModel,
    collect_video_files,
    format_readout,
    frame_step_ms,
    player_convert_settings,
    prefer_windows_media_foundation,
    probe_media_info,
)
from utils.config import normalize_media_player_settings
from utils.logger import logger

# main.py does this before QApplication; repeating it here covers tests and scripts that
# build the widget directly. It is a no-op once the variable is set.
prefer_windows_media_foundation()


def _tr(source: str) -> str:
    """Translate this module's strings under the stable "MediaPlayer" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("MediaPlayer", source)

VIDEO_NAME_FILTER = (
    "Video files (*.mp4 *.mov *.mkv *.avi *.wmv *.webm *.m4v *.mpg *.mpeg *.flv);;All files (*)"
)

# Available playback speeds shared by every panel so the tiles stay locked together.
PLAYBACK_SPEEDS = [0.25, 0.5, 1.0, 1.5, 2.0]

# Panel count presets the user can switch between. Observer-style review usually wants
# 2 clips side by side, but up to 4 can be compared in a 2x2 grid.
PANEL_COUNT_OPTIONS = [1, 2, 4]

MAX_PANELS = 4

# If a panel drifts further than this from where the shared timeline says it should be,
# it gets nudged back into place on the next tick so the tiles do not slowly separate.
DRIFT_CORRECTION_MS = 250


def format_timecode(milliseconds):
    """Format a millisecond position as H:MM:SS (or M:SS under an hour)."""
    try:
        total_seconds = int(max(0, milliseconds) // 1000)
    except (TypeError, ValueError):
        total_seconds = 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def panel_seek_position_ms(master_ms, offset_ms, duration_ms):
    """Map a shared-timeline position to a single panel's position.

    Each panel can carry a per-source offset (in ms) so clips that started at slightly
    different real-world times can be aligned. The result is clamped to the panel's own
    media duration so a seek never runs past the end of a shorter clip.
    """
    try:
        target = int(master_ms) + int(offset_ms)
    except (TypeError, ValueError):
        return 0
    if target < 0:
        target = 0
    if duration_ms and duration_ms > 0 and target > duration_ms:
        target = int(duration_ms)
    return target


class PlayerPanel(QWidget):
    """A single video tile: a video surface plus its own player and sync offset."""

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.host = parent
        self.setAcceptDrops(True)
        self._media_path = ""
        self.player = None
        self.probe_info = {}
        self.playlist = PlaylistModel()
        self.selected = False
        # The host wires these so the player can drive the shared timeline once created.
        self.on_duration_changed = None
        self.on_media_status_changed = None
        self.on_player_created = None
        self.on_probe_finished = None
        self.on_selected = None
        self.on_player_error = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # The actual QVideoWidget (a native video surface) is created lazily on first
        # load. Spawning one per panel up front allocates Windows video-surface resources
        # that accumulate across many widgets and can crash the backend on teardown.
        self.video_container = QFrame(self)
        self.video_container.setStyleSheet(theme.video_surface_style())
        self.video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_container.setMinimumHeight(120)
        self._video_layout = QVBoxLayout(self.video_container)
        self._video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = None

        self.placeholder = QLabel(_tr("Drop a video here\nor click Load"), self.video_container)
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(
            theme.video_label_style(size=11, muted=True) + " background:transparent;")
        self.overlay = UnsupportedOverlay(self.video_container)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        self.name_label = QLabel(f"Panel {self.index + 1}: empty")
        self.name_label.setStyleSheet(theme.video_label_style())
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-600.0, 600.0)
        self.offset_spin.setSingleStep(0.1)
        self.offset_spin.setDecimals(1)
        self.offset_spin.setValue(0.0)
        self.offset_spin.setSuffix(_tr(" s"))
        self.offset_spin.setMaximumWidth(78)
        self.offset_spin.setToolTip(
            _tr("Sync offset for this panel. Shift this clip earlier (negative) or later "
            "(positive) so its action lines up with the other panels.")
        )

        accent = theme.skin().accent
        self.load_btn = make_icon_button(
            "folder_open",
            _tr("Load a file into this panel"),
            accent,
            size=24,
        )
        self.load_btn.clicked.connect(self.browse_for_media)

        self.clear_btn = make_icon_button(
            "clear",
            _tr("Clear this panel"),
            accent,
            size=24,
        )
        self.clear_btn.clicked.connect(self.clear_media)

        controls.addWidget(self.name_label)
        controls.addWidget(QLabel(_tr("offset")))
        controls.addWidget(self.offset_spin)
        controls.addWidget(self.load_btn)
        controls.addWidget(self.clear_btn)

        layout.addWidget(self.video_container, 1)
        layout.addLayout(controls)

        frame_style = (
            "PlayerPanel { " + theme.video_panel_style() + " }"
        )
        self.setStyleSheet(frame_style)
        self.setObjectName("PlayerPanel")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.placeholder.setGeometry(self.video_container.rect())
        self.overlay.setGeometry(self.video_container.rect())

    def _ensure_video_widget(self):
        if self.video_widget is None:
            self.video_widget = QVideoWidget(self.video_container)
            self.video_widget.setStyleSheet(theme.video_surface_style())
            # QVideoWidget.sizeHint() is the clip's native size (1920x1080 for HD).
            # With any policy but Ignored that hint reaches the tab's scroll area
            # the next time the layout is invalidated (e.g. after a fullscreen
            # round trip) and the panel balloons to full video height.
            self.video_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            self._video_layout.addWidget(self.video_widget)
            self.placeholder.raise_()
        return self.video_widget

    def _ensure_player(self):
        # Create the QMediaPlayer lazily on first load. Creating it up front for every
        # panel spawns Windows media-backend objects that are expensive and can crash on
        # mass teardown; deferring until a clip is actually loaded avoids that entirely.
        if self.player is not None:
            return self.player
        # No QMediaPlayer.VideoSurface flag: with the Media Foundation backend that flag
        # makes every MP4 load end in InvalidMedia; the plain player renders to the
        # QVideoWidget correctly (verified on Windows 10 with H.264/AAC MP4).
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self._ensure_video_widget())
        self.player.setNotifyInterval(50)
        if callable(self.on_player_created):
            self.on_player_created(self)
        if callable(self.on_duration_changed):
            self.player.durationChanged.connect(self.on_duration_changed)
        if callable(self.on_media_status_changed):
            self.player.mediaStatusChanged.connect(
                lambda status, panel=self: self.on_media_status_changed(status, panel)
            )
        error_signal = self.player.error
        try:
            error_signal[QMediaPlayer.Error].connect(self._on_player_error_code)
        except (TypeError, KeyError):
            error_signal.connect(self._on_player_error_code)
        self.player.mediaStatusChanged.connect(self._on_status_for_errors)
        return self.player

    def _on_player_error_code(self, code):
        if callable(self.on_player_error):
            self.on_player_error(self, code)

    def _on_status_for_errors(self, status):
        if (
            status == QMediaPlayer.InvalidMedia
            and callable(self.on_player_error)
        ):
            self.on_player_error(self, QMediaPlayer.FormatError)

    def set_selected(self, selected):
        self.selected = bool(selected)
        border = (
            theme.qss("2px solid $accent")
            if self.selected
            else "1px solid transparent"
        )
        self.setStyleSheet(
            "PlayerPanel { "
            + theme.video_panel_style()
            + f" border: {border}; "
            + " }"
        )

    def mousePressEvent(self, event):
        if callable(self.on_selected):
            self.on_selected(self)
        super().mousePressEvent(event)

    def apply_audio(self, volume, muted):
        if self.player is not None:
            self.player.setVolume(int(volume))
            self.player.setMuted(bool(muted))

    def fps(self):
        return float(self.probe_info.get("fps") or 0.0)

    def nb_frames(self):
        return int(self.probe_info.get("nb_frames") or 0)

    def set_probe_info(self, info):
        self.probe_info = dict(info or {})
        if callable(self.on_probe_finished):
            self.on_probe_finished(self, self.probe_info)

    def has_media(self):
        return bool(self._media_path)

    def offset_ms(self):
        return int(round(self.offset_spin.value() * 1000))

    def duration_ms(self):
        return self.player.duration() if self.player is not None else 0

    def browse_for_media(self):
        start_dir = self.host.last_folder() if self.host is not None and hasattr(self.host, "last_folder") else ""
        path, _ = QFileDialog.getOpenFileName(self, _tr("Open video"), start_dir, VIDEO_NAME_FILTER)
        if path:
            if self.host is not None and hasattr(self.host, "set_last_folder"):
                self.host.set_last_folder(path)
            self.load_media(path)

    def load_media(self, path):
        if not path or not os.path.exists(path):
            return False
        self.hide_unsupported()
        self._ensure_player().setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self._media_path = path
        self.name_label.setText(
            _tr("Panel %(number)s: %(name)s")
            % {"number": self.index + 1, "name": os.path.basename(path)})
        self.name_label.setToolTip(path)
        self.placeholder.hide()
        self.probe_info = {}
        if self.host is not None and hasattr(self.host, "start_probe"):
            self.host.start_probe(self)
        return True

    def clear_media(self):
        self.hide_unsupported()
        if self.player is not None:
            self.player.stop()
            self.player.setMedia(QMediaContent())
        self._media_path = ""
        self.probe_info = {}
        self.name_label.setText(_tr("Panel %(number)s: empty")
                                % {"number": self.index + 1})
        self.name_label.setToolTip("")
        self.placeholder.show()

    def show_unsupported(self, text):
        self.overlay.show_message(text)
        self.overlay.setGeometry(self.video_container.rect())

    def hide_unsupported(self):
        self.overlay.reset()
        self.overlay.hide()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local:
                self.load_media(local)
                break
        event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        if self.host is not None and hasattr(self.host, "toggle_fullscreen"):
            self.host.toggle_fullscreen()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MediaPlayerWidget(QWidget):
    """Observer-style synchronized multi-panel player (up to four clips at once)."""

    probe_finished = pyqtSignal(int, dict)
    probe_finished_for_error = pyqtSignal(int, dict)
    UNSUPPORTED_ERRORS = (
        QMediaPlayer.FormatError,
        QMediaPlayer.ResourceError,
        QMediaPlayer.AccessDeniedError,
    )

    def __init__(self, parent=None, button_style=None, settings=None, save_settings=None, threadpool=None):
        super().__init__(parent)
        self.button_style = button_style
        self.settings = settings if settings is not None else {}
        self._save_settings = save_settings if callable(save_settings) else (lambda: None)
        self.threadpool = threadpool
        self.settings["media_player"] = normalize_media_player_settings(self.settings.get("media_player"))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.panels = []
        self._is_playing = False
        self._suppress_seek = False
        self._timers = []
        self._restoring = False
        self.probe_runner = probe_media_info
        self.probe_finished.connect(self._on_probe_finished)
        self.probe_finished_for_error.connect(
            self._on_probe_finished_for_error
        )
        self._build_ui()

        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(60)
        self.sync_timer.timeout.connect(self._on_tick)
        self.sync_timer.start()

        # Restoring saved values fires the same change slots as user input; do not
        # write the settings file back while doing so.
        self._restoring = True
        try:
            group = self.settings_group
            self.volume_slider.setValue(group["volume"])
            self.mute_btn.setChecked(group["muted"])
            self.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(group["panel_count"]))
            self.set_visible_panel_count(group["panel_count"])
            self.playlist_btn.setChecked(group["panel_count"] == 1)
            self._apply_audio_to_panels()
        finally:
            self._restoring = False

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(_tr("Media Player"))
        title.setStyleSheet(theme.tab_title_style())
        layout.addWidget(title)

        description = QLabel(
            _tr("Load up to four clips and review them side by side. Play, pause and seek "
            "control every panel together; use each panel's offset to line up clips that "
            "started at slightly different times.")
        )
        description.setWordWrap(True)
        description.setStyleSheet(theme.tab_description_style())
        layout.addWidget(description)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        for index in range(MAX_PANELS):
            panel = PlayerPanel(index, self)
            panel.on_duration_changed = self._on_any_duration_changed
            panel.on_media_status_changed = self._on_media_status_changed
            panel.on_player_created = self._on_player_created
            panel.on_selected = self._on_panel_selected
            panel.on_player_error = self._on_player_error
            panel.overlay.convert_requested.connect(
                lambda checked=False, p=panel: self.convert_and_play(p)
            )
            panel.overlay.dismissed.connect(panel.hide_unsupported)
            self.panels.append(panel)
        # 2x2 grid layout positions.
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for panel, (row, col) in zip(self.panels, positions, strict=True):
            self.grid.addWidget(panel, row, col)

        self.stage = QWidget(self)
        stage_layout = QHBoxLayout(self.stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(8)
        stage_layout.addLayout(self.grid, 1)
        self.playlist_dock = PlaylistDock(self.stage)
        self.playlist_dock.activate_requested.connect(self._play_from_playlist)
        self.playlist_dock.files_requested.connect(self.add_playlist_files)
        self.playlist_dock.folder_requested.connect(self.add_playlist_folder)
        stage_layout.addWidget(self.playlist_dock)
        self.playlist_dock.hide()
        self.selected_index = 0
        self.select_panel(0)
        self._stage_layout = stage_layout
        layout.addWidget(self.stage, 1)

        self.transport_widget = QWidget(self)
        self.transport_widget.setLayout(self._build_transport_bar())
        layout.addWidget(self.transport_widget)
        self._main_layout = layout
        self._fullscreen_host = None
        self._bar_hide_timer = QTimer(self)
        self._bar_hide_timer.setSingleShot(True)
        self._bar_hide_timer.setInterval(3000)
        self._bar_hide_timer.timeout.connect(self._hide_transport_bar)
        self.shortcuts = {}
        self._rebind_shortcuts()
        self.apply_layout_mode(theme.metrics())

    def _build_transport_bar(self):
        bar = QVBoxLayout()
        bar.setSpacing(6)

        seek_row = QHBoxLayout()
        seek_row.setSpacing(8)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.seek_all)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.time_label = QLabel(_tr("0:00:00.000 / 0:00:00.000"))
        self.time_label.setStyleSheet(theme.video_label_style())
        self.time_label.setMinimumWidth(260)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        seek_row.addWidget(self.position_slider, 1)
        seek_row.addWidget(self.time_label)
        bar.addLayout(seek_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(4)

        accent = theme.skin().accent
        self._icon_color = accent
        self.play_btn = make_icon_button("play", _tr("Play all"), accent)
        self.play_btn.clicked.connect(self.toggle_play_all)

        self.stop_btn = make_icon_button("stop", _tr("Stop all"), accent)
        self.stop_btn.clicked.connect(self.stop_all)

        self.restart_btn = make_icon_button("restart", _tr("Restart"), accent)
        self.restart_btn.clicked.connect(self.restart_all)

        self.fullscreen_btn = make_icon_button(
            "fullscreen",
            _tr("Fullscreen (F)"),
            accent,
        )
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.playlist_btn = make_icon_button("playlist", _tr("Playlist"), accent)
        self.playlist_btn.setCheckable(True)
        self.playlist_btn.toggled.connect(self._on_playlist_toggled)

        speed_label = QLabel(_tr("Speed"))
        speed_label.setStyleSheet(theme.video_label_style())
        self.speed_combo = QComboBox()
        for speed in PLAYBACK_SPEEDS:
            self.speed_combo.addItem(f"{speed:g}x", speed)
        self.speed_combo.setCurrentIndex(PLAYBACK_SPEEDS.index(1.0))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        volume_label = QLabel(_tr("Volume"))
        volume_label.setStyleSheet(theme.video_label_style())
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(MEDIA_PLAYER_DEFAULTS["volume"])
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.setToolTip(_tr("Volume for every panel"))
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self.mute_btn = make_icon_button("volume", _tr("Mute (M)"), accent)
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._on_mute_toggled)

        panels_label = QLabel(_tr("Panels"))
        panels_label.setStyleSheet(theme.video_label_style())
        self.panels_combo = QComboBox()
        for count in PANEL_COUNT_OPTIONS:
            self.panels_combo.addItem(str(count), count)
        self.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(2))
        self.panels_combo.currentIndexChanged.connect(self._on_panel_count_changed)

        button_row.addWidget(self.play_btn)
        button_row.addWidget(self.stop_btn)
        button_row.addWidget(self.restart_btn)
        button_row.addSpacing(12)
        button_row.addWidget(self.fullscreen_btn)
        button_row.addWidget(self.playlist_btn)
        button_row.addStretch(1)
        button_row.addWidget(panels_label)
        button_row.addWidget(self.panels_combo)
        button_row.addWidget(speed_label)
        button_row.addWidget(self.speed_combo)
        button_row.addWidget(volume_label)
        button_row.addWidget(self.volume_slider)
        button_row.addWidget(self.mute_btn)
        bar.addLayout(button_row)
        return bar

    def apply_layout_mode(self, metrics):
        for panel in self.panels:
            panel.video_container.setMinimumHeight(metrics.player_panel_min_h)

    def reskin(self):
        """Repaint every glyph (transport, panels, playlist dock) in the current skin."""
        self._icon_color = theme.skin().accent
        reskin_icon_buttons(self, self._icon_color)
        self._set_play_glyph(self._is_playing)
        set_button_glyph(
            self.mute_btn, "muted" if self.mute_btn.isChecked() else "volume", self._icon_color
        )

    # --- shortcuts -------------------------------------------------------
    def _shortcut_table(self):
        return {
            "Space": self.toggle_play_all,
            "Home": self.restart_all,
            "Left": lambda: self.step_frames(-1),
            "Right": lambda: self.step_frames(1),
            "Shift+Left": lambda: self.seek_relative_ms(-5000),
            "Shift+Right": lambda: self.seek_relative_ms(5000),
            "Up": lambda: self.adjust_volume(5),
            "Down": lambda: self.adjust_volume(-5),
            "M": self.toggle_mute,
            "F": self.toggle_fullscreen,
            "Escape": self.exit_fullscreen,
            "N": self.playlist_next,
            "P": self.playlist_previous,
        }

    def _rebind_shortcuts(self):
        for shortcut in self.shortcuts.values():
            shortcut.setParent(None)
            shortcut.deleteLater()
        self.shortcuts = {}
        for key, slot in self._shortcut_table().items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)
            self.shortcuts[key] = shortcut

    def toggle_mute(self):
        self.set_muted(not self.is_muted())

    def playlist_next(self):
        was_playing = self._is_playing
        if self._advance_playlist(1) and was_playing:
            self.play_all()

    def playlist_previous(self):
        was_playing = self._is_playing
        if self._advance_playlist(-1) and was_playing:
            self.play_all()

    # --- fullscreen ------------------------------------------------------
    def is_fullscreen(self):
        return self._fullscreen_host is not None

    def toggle_fullscreen(self):
        if self.is_fullscreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.is_fullscreen():
            return
        host = FullscreenHost()
        host.exit_requested.connect(self.exit_fullscreen)
        host.mouse_moved.connect(self._show_transport_bar)
        self._stage_index = self._main_layout.indexOf(self.stage)
        self._main_layout.removeWidget(self.stage)
        self._main_layout.removeWidget(self.transport_widget)
        host.take(self.stage)
        host.take(self.transport_widget)
        self._fullscreen_host = host
        host.showFullScreen()
        host.setFocus()
        self._show_transport_bar()

    def exit_fullscreen(self):
        host = self._fullscreen_host
        if host is None:
            return
        self._bar_hide_timer.stop()
        host.release()
        self._fullscreen_host = None
        self._main_layout.insertWidget(self._stage_index, self.stage, 1)
        self._main_layout.insertWidget(self._stage_index + 1, self.transport_widget)
        self.stage.show()
        self.transport_widget.show()
        host.close()
        host.deleteLater()
        self._rebind_shortcuts()

    def _show_transport_bar(self):
        self.transport_widget.show()
        if self.is_fullscreen():
            self._bar_hide_timer.start()

    def _hide_transport_bar(self):
        if self.is_fullscreen():
            self.transport_widget.hide()

    # --- audio & persistence ---------------------------------------------
    @property
    def settings_group(self):
        return self.settings["media_player"]

    def _persist(self, **changes):
        self.settings_group.update(changes)
        if not self._restoring:
            self._save_settings()

    def last_folder(self):
        return self.settings_group.get("last_folder", "")

    def set_last_folder(self, path):
        folder = path if os.path.isdir(path or "") else os.path.dirname(path or "")
        if folder and folder != self.last_folder():
            self._persist(last_folder=folder)

    def _schedule(self, msec, callback):
        """Run `callback` after `msec` while this widget lives (no QTimer.singleShot)."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        self._timers.append(timer)

        def fire():
            if timer in self._timers:
                self._timers.remove(timer)
            callback()

        timer.timeout.connect(fire)
        timer.start(max(0, int(msec)))
        return timer

    def volume(self):
        return self.volume_slider.value()

    def is_muted(self):
        return self.mute_btn.isChecked()

    def set_volume(self, value):
        self.volume_slider.setValue(max(0, min(100, int(value))))

    def set_muted(self, muted):
        self.mute_btn.setChecked(bool(muted))

    def adjust_volume(self, delta):
        self.set_volume(self.volume() + int(delta))

    def _apply_audio_to_panels(self):
        for panel in self.panels:
            panel.apply_audio(self.volume(), self.is_muted())

    def _on_volume_slider_changed(self, value):
        self._apply_audio_to_panels()
        self._persist(volume=int(value))

    def _on_mute_toggled(self, checked):
        self.mute_btn.setIcon(
            glyph_icon("muted" if checked else "volume", self._icon_color, 20)
        )
        self.mute_btn.setToolTip(
            _tr("Unmute (M)") if checked else _tr("Mute (M)")
        )
        self._apply_audio_to_panels()
        self._persist(muted=bool(checked))

    def _on_player_created(self, panel):
        panel.apply_audio(self.volume(), self.is_muted())

    # --- selection & playlist --------------------------------------------
    def select_panel(self, index):
        if not (0 <= index < len(self.panels)):
            return
        self.selected_index = index
        for panel in self.panels:
            panel.set_selected(panel.index == index)
        panel = self.panels[index]
        self.playlist_dock.set_model(
            panel.playlist,
            _tr("Panel %(number)s") % {"number": index + 1},
        )
        self.playlist_dock.select_path(panel._media_path)

    def selected_panel(self):
        panel = self.panels[self.selected_index]
        if panel.isHidden():
            return self.panels[0]
        return panel

    def _on_panel_selected(self, panel):
        self.select_panel(panel.index)

    def toggle_playlist(self):
        self.playlist_btn.setChecked(not self.playlist_btn.isChecked())

    def _on_playlist_toggled(self, checked):
        self.playlist_dock.setVisible(bool(checked))

    def add_playlist_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            _tr("Add videos to playlist"),
            self.last_folder(),
            VIDEO_NAME_FILTER,
        )
        if paths:
            self.set_last_folder(paths[0])
            self.playlist_dock.add_paths(paths)

    def add_playlist_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            _tr("Add a folder of videos"),
            self.last_folder(),
        )
        if folder:
            self.set_last_folder(folder)
            self.playlist_dock.add_paths(collect_video_files(folder))

    def _play_from_playlist(self, path):
        panel = self.selected_panel()
        if panel.load_media(path):
            self.playlist_dock.select_path(path)
            self.play_all()

    def _advance_playlist(self, step):
        panel = self.selected_panel()
        model = panel.playlist
        current = model.index_of(panel._media_path)
        target = (
            model.next_index(current)
            if step > 0
            else model.previous_index(current)
        )
        if target is None:
            return False
        path = model.items[target]
        if not panel.load_media(path):
            return False
        panel._media_path = path
        self.playlist_dock.select_path(path)
        return True

    # --- panel visibility -------------------------------------------------
    def set_visible_panel_count(self, count):
        for index, panel in enumerate(self.panels):
            panel.setVisible(index < count)

    def visible_panel_count(self):
        return sum(1 for panel in self.panels if not panel.isHidden())

    def _on_panel_count_changed(self, _index):
        count = self.panels_combo.currentData()
        self.set_visible_panel_count(count)
        self.playlist_btn.setChecked(int(count) == 1)
        self._persist(panel_count=int(count))

    # --- active players ---------------------------------------------------
    def active_panels(self):
        return [panel for panel in self.panels if not panel.isHidden() and panel.has_media()]

    def _reference_panel(self):
        # The longest loaded clip drives the shared timeline so the slider can reach the
        # end of every panel.
        candidates = self.active_panels()
        if not candidates:
            return None
        return max(candidates, key=lambda panel: panel.duration_ms())

    def timeline_duration_ms(self):
        panels = self.active_panels()
        if not panels:
            return 0
        return max(panel.duration_ms() for panel in panels)

    # --- probing -----------------------------------------------------------
    def start_probe(self, panel, for_error=False):
        path = panel._media_path
        index = panel.index

        def run():
            info = self.probe_runner(path)
            try:
                signal = (
                    self.probe_finished_for_error
                    if for_error
                    else self.probe_finished
                )
                signal.emit(index, info)
            except RuntimeError:
                logger.debug("Media player closed before probe finished", exc_info=True)

        threading.Thread(target=run, daemon=True).start()

    def _on_probe_finished(self, index, info):
        if not (0 <= index < len(self.panels)):
            return
        panel = self.panels[index]
        if not panel.has_media():
            return
        panel.set_probe_info(info)
        self._update_time_label(self.position_slider.value())

    def _on_player_error(self, panel, code):
        if code not in self.UNSUPPORTED_ERRORS or not panel.has_media():
            return
        if self._is_playing:
            self.pause_all()
        self.start_probe(panel, for_error=True)

    def _unsupported_text(self, info):
        if not info or not info.get("ok"):
            return _tr("Windows cannot play this file.")
        vcodec = info.get("vcodec") or _tr("unknown")
        container = info.get("container") or _tr("unknown")
        acodec = info.get("acodec") or ""
        codecs = f"{vcodec}/{acodec}" if acodec else vcodec
        return _tr(
            "Windows cannot play %(codecs)s in %(container)s."
        ) % {"codecs": codecs, "container": container}

    def _on_probe_finished_for_error(self, index, info):
        if not (0 <= index < len(self.panels)):
            return
        panel = self.panels[index]
        if not panel.has_media():
            return
        panel.set_probe_info(info)
        panel.show_unsupported(self._unsupported_text(info))

    def convert_and_play(self, panel):
        path = panel._media_path
        if not path:
            return
        settings = player_convert_settings(self.settings)
        signals = WorkerSignals()
        signals.progress_update.connect(
            lambda _path, percent, p=panel: p.overlay.show_progress(percent)
        )
        signals.conversion_complete.connect(
            lambda name, success, info, p=panel: self._on_convert_finished(
                p, name, success, info
            )
        )
        panel.overlay.show_progress(0)
        panel._conversion_signals = signals
        self._start_conversion_worker(path, settings, signals)

    def _start_conversion_worker(self, path, settings, signals):
        worker = ConversionWorker(path, settings, signals)
        pool = self.threadpool or QThreadPool.globalInstance()
        pool.start(worker)

    def _on_convert_finished(
        self,
        panel,
        _file_name,
        success,
        deletion_info,
    ):
        output = (deletion_info or {}).get("output_file", "")
        if success and output:
            panel.hide_unsupported()
            if panel.load_media(output):
                self.play_all()
            return
        panel.overlay.show_error(
            _tr(
                "the converter could not produce an MP4; "
                "see the Conversion Log"
            )
        )

    # --- transport --------------------------------------------------------
    def toggle_play_all(self):
        if self._is_playing:
            self.pause_all()
        else:
            self.play_all()

    def _set_play_glyph(self, playing):
        self.play_btn.setIcon(
            glyph_icon("pause" if playing else "play", self._icon_color, 20)
        )
        self.play_btn.setToolTip(
            _tr("Pause all") if playing else _tr("Play all")
        )

    def play_all(self):
        panels = self.active_panels()
        if not panels:
            return
        rate = self.speed_combo.currentData() or 1.0
        master = self.position_slider.value()
        for panel in panels:
            panel.player.setPlaybackRate(rate)
            panel.player.setPosition(
                panel_seek_position_ms(master, panel.offset_ms(), panel.duration_ms())
            )
            panel.player.play()
        self._is_playing = True
        self._set_play_glyph(playing=True)

    def pause_all(self):
        for panel in self.panels:
            if panel.player is not None:
                panel.player.pause()
        self._is_playing = False
        self._set_play_glyph(playing=False)

    def stop_all(self):
        for panel in self.panels:
            if panel.player is not None:
                panel.player.stop()
        self._is_playing = False
        self._set_play_glyph(playing=False)
        self._set_slider_value(0)
        self._update_time_label(0)

    def restart_all(self):
        self.seek_all(0)
        self.play_all()

    def seek_all(self, master_ms):
        self._set_slider_value(master_ms)
        for panel in self.active_panels():
            panel.player.setPosition(
                panel_seek_position_ms(master_ms, panel.offset_ms(), panel.duration_ms())
            )
        self._update_time_label(master_ms)

    def _clamp_master(self, master_ms):
        return max(0, min(int(master_ms), self.timeline_duration_ms() or int(master_ms)))

    def seek_relative_ms(self, delta_ms):
        target = self._clamp_master(self.position_slider.value() + int(delta_ms))
        self._set_slider_value(target)
        self.seek_all(target)

    def step_frames(self, delta):
        reference = self._reference_panel()
        if reference is None:
            return
        # Stepping always pauses (spec §2): a paused, frame-exact position is the point.
        self.pause_all()
        self.seek_relative_ms(int(delta) * frame_step_ms(reference.fps()))

    def _on_slider_pressed(self):
        self._suppress_seek = True

    def _on_slider_released(self):
        self._suppress_seek = False
        self.seek_all(self.position_slider.value())

    def _on_speed_changed(self, _index):
        rate = self.speed_combo.currentData() or 1.0
        for panel in self.panels:
            if panel.player is not None:
                panel.player.setPlaybackRate(rate)

    # --- player signals ---------------------------------------------------
    def _on_any_duration_changed(self, _duration):
        self.position_slider.setRange(0, self.timeline_duration_ms())
        self._update_time_label(self.position_slider.value())

    def _on_media_status_changed(self, status, panel=None):
        if status != QMediaPlayer.EndOfMedia or not self._is_playing:
            return
        selected = self.selected_panel()
        if (
            self.visible_panel_count() == 1
            and panel is selected
            and len(selected.playlist.items) > 1
            and self._advance_playlist(1)
        ):
            self.play_all()
            return
        self.pause_all()

    def _on_tick(self):
        if not self._is_playing or self._suppress_seek:
            return
        reference = self._reference_panel()
        if reference is None:
            return
        # Advance the slider from the reference panel, compensating for its own offset so
        # the slider reflects the shared timeline rather than that panel's local position.
        master = max(0, reference.player.position() - reference.offset_ms())
        self._set_slider_value(master)
        self._update_time_label(master)
        self._correct_drift(master)

    def _correct_drift(self, master_ms):
        for panel in self.active_panels():
            expected = panel_seek_position_ms(master_ms, panel.offset_ms(), panel.duration_ms())
            if abs(panel.player.position() - expected) > DRIFT_CORRECTION_MS:
                panel.player.setPosition(expected)

    def _set_slider_value(self, value):
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(int(value))
        self.position_slider.blockSignals(False)

    def _update_time_label(self, master_ms):
        reference = self._reference_panel()
        fps = reference.fps() if reference is not None else 0.0
        nb_frames = reference.nb_frames() if reference is not None else 0
        self.time_label.setText(format_readout(master_ms, self.timeline_duration_ms(), fps, nb_frames))

    def shutdown(self):
        self.exit_fullscreen()
        self._bar_hide_timer.stop()
        for timer in self._timers:
            timer.stop()
        try:
            self.sync_timer.stop()
        except Exception:
            logger.debug("MediaPlayerWidget.shutdown: suppressed error", exc_info=True)
        for panel in self.panels:
            if panel.player is None:
                continue
            try:
                panel.player.stop()
                # Detach the media and video surface before teardown. Leaving a live
                # QMediaPlayer bound to a QVideoWidget can crash the Windows media backend
                # when many players are destroyed at interpreter/app shutdown.
                panel.player.setMedia(QMediaContent())
                panel.player.setVideoOutput(None)
            except Exception:
                logger.debug("MediaPlayerWidget.shutdown: suppressed error", exc_info=True)
