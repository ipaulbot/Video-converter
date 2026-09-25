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


if __name__ == "__main__":
    unittest.main()
