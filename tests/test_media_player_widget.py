import os
import subprocess
import tempfile
import time
import unittest

from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import QApplication

from ui.media_player_widget import (
    MAX_PANELS,
    PANEL_COUNT_OPTIONS,
    MediaPlayerWidget,
    format_timecode,
    panel_seek_position_ms,
)
from utils.resources import resource_path


class MediaPlayerHelperTests(unittest.TestCase):
    def test_format_timecode_under_one_hour_is_minutes_seconds(self):
        self.assertEqual(format_timecode(0), "0:00")
        self.assertEqual(format_timecode(65_000), "1:05")
        self.assertEqual(format_timecode(599_000), "9:59")

    def test_format_timecode_over_one_hour_includes_hours(self):
        self.assertEqual(format_timecode(3_661_000), "1:01:01")

    def test_format_timecode_handles_bad_input(self):
        self.assertEqual(format_timecode(None), "0:00")
        self.assertEqual(format_timecode(-500), "0:00")

    def test_panel_seek_applies_offset(self):
        self.assertEqual(panel_seek_position_ms(5_000, 1_000, 60_000), 6_000)
        self.assertEqual(panel_seek_position_ms(5_000, -2_000, 60_000), 3_000)

    def test_panel_seek_clamps_to_zero_and_duration(self):
        self.assertEqual(panel_seek_position_ms(500, -2_000, 60_000), 0)
        self.assertEqual(panel_seek_position_ms(59_000, 5_000, 60_000), 60_000)

    def test_panel_seek_without_duration_does_not_clamp_high(self):
        self.assertEqual(panel_seek_position_ms(10_000, 0, 0), 10_000)


class MediaPlayerWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _widget(self, settings=None, saves=None):
        widget = MediaPlayerWidget(
            settings=settings if settings is not None else {},
            save_settings=(lambda: saves.append(1)) if saves is not None else None,
        )
        self.addCleanup(widget.shutdown)
        return widget

    # No tearDown: conftest's reap_hidden_top_level_widgets calls shutdown()
    # and destroys this test's windows. What used to be here paired
    # deleteLater() with processEvents(), which reads like a cleanup and
    # deletes nothing -- processEvents() explicitly excludes DeferredDelete --
    # so these widgets leaked for the whole session.

    def test_creates_four_panels_with_players_created_lazily(self):
        widget = MediaPlayerWidget()
        try:
            self.assertEqual(len(widget.panels), MAX_PANELS)
            # Players are created lazily on first load, so they start out unallocated.
            for panel in widget.panels:
                self.assertIsNone(panel.player)
                self.assertFalse(panel.has_media())
        finally:
            widget.shutdown()

    def test_default_shows_two_panels(self):
        widget = MediaPlayerWidget()
        try:
            self.assertEqual(widget.visible_panel_count(), 2)
        finally:
            widget.shutdown()

    def test_panel_count_selector_changes_visible_panels(self):
        widget = MediaPlayerWidget()
        try:
            widget.set_visible_panel_count(4)
            self.assertEqual(widget.visible_panel_count(), 4)
            widget.set_visible_panel_count(1)
            self.assertEqual(widget.visible_panel_count(), 1)
        finally:
            widget.shutdown()

    def test_play_button_toggles_label_without_media(self):
        widget = MediaPlayerWidget()
        try:
            # With no media loaded play_all is a no-op and the label stays "Play all".
            widget.toggle_play_all()
            self.assertEqual(widget.play_btn.text(), "Play all")
            self.assertFalse(widget._is_playing)
        finally:
            widget.shutdown()

    def test_each_panel_offset_defaults_to_zero(self):
        widget = MediaPlayerWidget()
        try:
            for panel in widget.panels:
                self.assertEqual(panel.offset_ms(), 0)
        finally:
            widget.shutdown()

    def test_volume_and_mute_reach_every_created_player(self):
        widget = self._widget()
        first = widget.panels[0]._ensure_player()
        second = widget.panels[1]._ensure_player()
        widget.set_volume(40)
        widget.set_muted(True)
        for player in (first, second):
            self.assertEqual(player.volume(), 40)
            self.assertTrue(player.isMuted())
        # A panel whose player is created later inherits the current audio state.
        third = widget.panels[2]._ensure_player()
        self.assertEqual(third.volume(), 40)
        self.assertTrue(third.isMuted())

    def test_volume_controls_persist_to_settings_group(self):
        saves = []
        settings = {}
        widget = self._widget(settings=settings, saves=saves)
        widget.volume_slider.setValue(55)
        widget.mute_btn.setChecked(True)
        widget.panels_combo.setCurrentIndex(0)  # 1 panel
        self.assertEqual(settings["media_player"]["volume"], 55)
        self.assertTrue(settings["media_player"]["muted"])
        self.assertEqual(settings["media_player"]["panel_count"], 1)
        self.assertGreaterEqual(len(saves), 3)

    def test_widget_restores_settings_group_on_creation(self):
        settings = {"media_player": {"volume": 20, "muted": True, "panel_count": 4, "last_folder": "C:\\Videos"}}
        saves = []
        widget = self._widget(settings=settings, saves=saves)
        self.assertEqual(widget.volume(), 20)
        self.assertTrue(widget.is_muted())
        self.assertEqual(widget.visible_panel_count(), 4)
        self.assertEqual(widget.last_folder(), "C:\\Videos")
        # Restoring saved values must not write the settings file back.
        self.assertEqual(saves, [])

    def test_adjust_volume_clamps_and_unmutes_on_increase(self):
        widget = self._widget()
        widget.set_volume(98)
        widget.adjust_volume(+5)
        self.assertEqual(widget.volume(), 100)
        widget.adjust_volume(-200)
        self.assertEqual(widget.volume(), 0)

    def _loaded_widget_with_fake_player(self, duration_ms=10_000, fps=25.0, nb_frames=250):
        """A widget whose first panel reports media without touching the Windows backend."""
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": True, "fps": fps, "nb_frames": nb_frames,
                                            "duration_ms": duration_ms, "container": "mp4",
                                            "vcodec": "h264", "acodec": "aac"}
        panel = widget.panels[0]

        class FakePlayer:
            def __init__(self):
                self._position = 0
                self.paused = False
                self.playing = False

            def duration(self):
                return duration_ms

            def position(self):
                return self._position

            def setPosition(self, value):
                self._position = int(value)

            def pause(self):
                self.paused = True

            def play(self):
                self.playing = True

            def stop(self):
                pass

            def setPlaybackRate(self, _rate):
                pass

            def setVolume(self, _v):
                pass

            def setMuted(self, _m):
                pass

        panel.player = FakePlayer()
        panel._media_path = "C:\\Videos\\clip.mp4"
        panel.set_probe_info(widget.probe_runner(panel._media_path))
        widget._on_any_duration_changed(duration_ms)
        return widget, panel

    def test_step_frames_pauses_and_moves_by_one_frame(self):
        widget, panel = self._loaded_widget_with_fake_player(fps=25.0)
        widget.seek_all(1_000)
        widget.step_frames(1)
        self.assertTrue(panel.player.paused)
        self.assertEqual(panel.player.position(), 1_040)
        widget.step_frames(-2)
        self.assertEqual(panel.player.position(), 960)

    def test_step_frames_clamps_to_timeline(self):
        widget, panel = self._loaded_widget_with_fake_player(duration_ms=100, fps=25.0)
        widget.seek_all(90)
        widget.step_frames(1)
        self.assertEqual(panel.player.position(), 100)
        widget.seek_all(10)
        widget.step_frames(-1)
        self.assertEqual(panel.player.position(), 0)

    def test_step_uses_default_fps_before_probe_arrives(self):
        widget, panel = self._loaded_widget_with_fake_player(fps=0.0, nb_frames=0)
        widget.seek_all(0)
        widget.step_frames(1)
        self.assertEqual(panel.player.position(), 40)
        self.assertNotIn("frame", widget.time_label.text())

    def test_readout_shows_millis_and_frame_numbers(self):
        widget, _panel = self._loaded_widget_with_fake_player(duration_ms=2_000, fps=25.0, nb_frames=50)
        widget.seek_all(1_000)
        self.assertEqual(widget.time_label.text(), "0:00:01.000 / 0:00:02.000 · frame 25 / 50")

    def test_load_media_probes_in_background_and_updates_panel(self):
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": True, "fps": 29.97, "nb_frames": 10, "duration_ms": 333,
                                            "container": "mov", "vcodec": "h264", "acodec": "aac"}
        panel = widget.panels[0]
        panel._ensure_player = lambda: panel.player or type("P", (), {
            "setMedia": lambda self, *_: None, "setVolume": lambda self, *_: None,
            "setMuted": lambda self, *_: None, "duration": lambda self: 0})()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertTrue(panel.load_media(path))
        deadline = time.monotonic() + 5
        while not panel.probe_info and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertAlmostEqual(panel.fps(), 29.97, places=2)
        self.assertEqual(panel.nb_frames(), 10)

    def test_shortcut_table_maps_keys_to_slots(self):
        widget = self._widget()
        calls = []
        widget.toggle_play_all = lambda: calls.append("play")
        widget.step_frames = lambda delta: calls.append(("step", delta))
        widget.seek_relative_ms = lambda delta: calls.append(("seek", delta))
        widget.adjust_volume = lambda delta: calls.append(("vol", delta))
        widget.toggle_mute = lambda: calls.append("mute")
        widget.toggle_fullscreen = lambda: calls.append("fs")
        widget.playlist_next = lambda: calls.append("next")
        widget.playlist_previous = lambda: calls.append("prev")
        widget._rebind_shortcuts()
        for key in ("Space", "Left", "Right", "Shift+Left", "Shift+Right", "Up", "Down", "M", "F", "N", "P"):
            widget.shortcuts[key].activated.emit()
        self.assertEqual(calls, ["play", ("step", -1), ("step", 1), ("seek", -5000), ("seek", 5000),
                                 ("vol", 5), ("vol", -5), "mute", "fs", "next", "prev"])
        self.assertEqual(widget.shortcuts["Space"].context(), Qt.WidgetWithChildrenShortcut)

    def test_fullscreen_reparents_stage_and_restores(self):
        widget = self._widget()
        widget.show()
        stage_parent = widget.stage.parentWidget()
        widget.toggle_fullscreen()
        self.assertTrue(widget.is_fullscreen())
        self.assertIs(widget.stage.parentWidget(), widget._fullscreen_host)
        self.assertIs(widget.transport_widget.parentWidget(), widget._fullscreen_host)
        widget.toggle_fullscreen()
        self.assertFalse(widget.is_fullscreen())
        self.assertIs(widget.stage.parentWidget(), stage_parent)
        self.assertIsNone(widget._fullscreen_host)
        self.assertTrue(widget.transport_widget.isVisibleTo(widget))

    def test_fullscreen_bar_hides_after_timeout_and_returns_on_mouse(self):
        widget = self._widget()
        widget.show()
        widget.enter_fullscreen()
        widget._bar_hide_timer.timeout.emit()
        self.assertFalse(widget.transport_widget.isVisibleTo(widget._fullscreen_host))
        widget._fullscreen_host.mouse_moved.emit()
        self.assertTrue(widget.transport_widget.isVisibleTo(widget._fullscreen_host))
        self.assertTrue(widget._bar_hide_timer.isActive())
        widget.exit_fullscreen()

    def test_double_clicking_a_panel_toggles_fullscreen(self):
        widget = self._widget()
        toggles = []
        widget.toggle_fullscreen = lambda: toggles.append(1)
        widget.panels[0].mouseDoubleClickEvent(QMouseEvent(
            QEvent.MouseButtonDblClick, QPointF(5, 5), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        self.assertEqual(toggles, [1])

    def test_clicking_a_panel_selects_it_and_shows_its_playlist(self):
        widget = self._widget()
        widget.panels[1].on_selected(widget.panels[1])
        self.assertIs(widget.selected_panel(), widget.panels[1])
        self.assertTrue(widget.panels[1].selected)
        self.assertFalse(widget.panels[0].selected)
        self.assertIs(widget.playlist_dock.model, widget.panels[1].playlist)

    def test_playlist_visible_by_default_only_for_one_panel(self):
        widget = self._widget()
        widget.show()
        self.assertFalse(widget.playlist_dock.isVisibleTo(widget))
        widget.panels_combo.setCurrentIndex(0)
        self.assertTrue(widget.playlist_dock.isVisibleTo(widget))
        widget.playlist_btn.setChecked(False)
        self.assertFalse(widget.playlist_dock.isVisibleTo(widget))

    def test_playlist_next_and_previous_load_into_selected_panel(self):
        widget = self._widget()
        panel = widget.panels[0]
        loaded = []
        panel.load_media = lambda path: loaded.append(path) or True
        panel.playlist.add(["a.mp4", "b.mp4", "c.mp4"])
        panel._media_path = "a.mp4"
        widget.playlist_next()
        panel._media_path = loaded[-1]
        widget.playlist_next()
        panel._media_path = loaded[-1]
        widget.playlist_next()
        widget.playlist_previous()
        self.assertEqual(loaded, ["b.mp4", "c.mp4", "a.mp4", "c.mp4"])

    def test_auto_advance_only_with_one_visible_panel(self):
        widget = self._widget()
        panel = widget.panels[0]
        loaded = []
        panel.load_media = lambda path: loaded.append(path) or True
        panel.playlist.add(["a.mp4", "b.mp4"])
        panel._media_path = "a.mp4"
        widget._is_playing = True
        widget.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(2))
        widget._on_media_status_changed(QMediaPlayer.EndOfMedia, panel)
        self.assertEqual(loaded, [])
        self.assertFalse(widget._is_playing)
        widget._is_playing = True
        widget.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(1))
        widget.play_all = lambda: loaded.append("play")
        widget._on_media_status_changed(QMediaPlayer.EndOfMedia, panel)
        self.assertEqual(loaded, ["b.mp4", "play"])

    def test_format_error_probes_and_shows_tile_message(self):
        widget = self._widget()
        widget.probe_runner = lambda path: {
            "ok": True,
            "fps": 25.0,
            "nb_frames": 0,
            "duration_ms": 0,
            "container": "matroska",
            "vcodec": "hevc",
            "acodec": "opus",
        }
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.mkv"
        widget._on_player_error(panel, QMediaPlayer.FormatError)
        deadline = time.monotonic() + 5
        while (
            not panel.overlay.isVisibleTo(panel)
            and time.monotonic() < deadline
        ):
            self.app.processEvents()
            time.sleep(0.01)
        self.assertEqual(
            panel.overlay.message_label.text(),
            "Windows cannot play hevc/opus in matroska.",
        )

    def test_failed_probe_still_offers_convert(self):
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": False}
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.bin"
        widget._on_probe_finished_for_error(0, {"ok": False})
        self.assertEqual(
            panel.overlay.message_label.text(),
            "Windows cannot play this file.",
        )
        self.assertTrue(panel.overlay.convert_btn.isEnabled())

    def test_convert_enqueues_one_job_with_fixed_preset_and_plays_result(self):
        settings = {
            "destination_folder": "C:\\Videos\\Out",
            "video_codec": "libx265",
            "use_gpu": True,
        }
        widget = self._widget(settings=settings)
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.mkv"
        jobs = []
        widget._start_conversion_worker = (
            lambda path, job_settings, signals: jobs.append(
                (path, job_settings, signals)
            )
        )
        widget.convert_and_play(panel)
        self.assertEqual(len(jobs), 1)
        path, job_settings, signals = jobs[0]
        self.assertEqual(path, "C:\\Videos\\clip.mkv")
        self.assertEqual(job_settings["video_codec"], "libx264")
        self.assertEqual(
            job_settings["destination_folder"], "C:\\Videos\\Out"
        )
        self.assertIn("-crf 20", job_settings["custom_console_command"])
        signals.progress_update.emit(path, 30)
        self.assertIn("30", panel.overlay.progress_label.text())
        loaded = []
        panel.load_media = lambda new_path: loaded.append(new_path) or True
        widget.play_all = lambda: loaded.append("play")
        signals.conversion_complete.emit(
            "clip.mkv",
            True,
            {"output_file": "C:\\Videos\\Out\\clip.mp4"},
        )
        self.assertEqual(loaded, ["C:\\Videos\\Out\\clip.mp4", "play"])
        self.assertFalse(panel.overlay.isVisibleTo(panel))

    def test_convert_failure_shows_error_in_tile(self):
        widget = self._widget()
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.mkv"
        widget._start_conversion_worker = lambda *args: None
        widget.convert_and_play(panel)
        widget._on_convert_finished(
            panel,
            "clip.mkv",
            False,
            {"source_file": "C:\\Videos\\clip.mkv"},
        )
        self.assertIn("failed", panel.overlay.progress_label.text().lower())
        self.assertTrue(panel.overlay.convert_btn.isEnabled())


class MediaPlayerRealFileSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.clip = ""
        ffmpeg = resource_path("ffmpeg.exe")
        if not os.path.exists(ffmpeg):
            return
        handle = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        handle.close()
        command = [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=160x120:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            handle.name,
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            cls.clip = handle.name
        else:
            os.remove(handle.name)

    @classmethod
    def tearDownClass(cls):
        if cls.clip and os.path.exists(cls.clip):
            os.remove(cls.clip)

    def test_load_reports_duration_and_one_frame_step_moves_one_frame(self):
        if not self.clip:
            self.skipTest("ffmpeg.exe not available to synthesise a clip")
        widget = MediaPlayerWidget(settings={})
        self.addCleanup(widget.shutdown)
        panel = widget.panels[0]
        self.assertTrue(panel.load_media(self.clip))
        deadline = time.monotonic() + 8
        while (
            panel.duration_ms() <= 0 or not panel.probe_info
        ) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        if panel.duration_ms() <= 0:
            self.skipTest(
                "QMediaPlayer backend reported no duration in the headless session"
            )
        self.assertGreater(panel.duration_ms(), 1_500)
        self.assertAlmostEqual(panel.fps(), 25.0, places=1)
        widget.seek_all(400)
        widget.step_frames(1)
        deadline = time.monotonic() + 3
        while (
            abs(panel.player.position() - 440) > 40
            and time.monotonic() < deadline
        ):
            self.app.processEvents()
            time.sleep(0.02)
        self.assertLessEqual(abs(panel.player.position() - 440), 40)


if __name__ == "__main__":
    unittest.main()
