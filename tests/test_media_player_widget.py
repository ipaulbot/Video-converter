import os
import tempfile
import time
import unittest

from PyQt5.QtWidgets import QApplication

from ui.media_player_widget import (
    MAX_PANELS,
    MediaPlayerWidget,
    format_timecode,
    panel_seek_position_ms,
)


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


if __name__ == "__main__":
    unittest.main()
