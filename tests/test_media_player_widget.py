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


if __name__ == "__main__":
    unittest.main()
