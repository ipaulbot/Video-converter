"""Tests for ui/preview_controller.py.

The preview had no tests before it was extracted, which is most of why it was
worth extracting: its logic was only reachable by building the whole main
window. These exercise it against a minimal host instead.

Nothing here starts ffmpeg. The pipeline is driven by feeding bytes and
signals directly, so the tests stay fast and do not depend on a media file.
"""
import unittest

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QWidget

from ui import theme
from ui.preview_controller import PreviewController

app = QApplication.instance() or QApplication([])


class _Host(QWidget):
    """The narrow contract PreviewController needs from its host.

    Deliberately tiny: if this ever has to grow, the controller has started
    reaching back into the main window again.
    """

    def __init__(self, locked=False, active=False):
        super().__init__()
        self.locked = locked
        self._active = active

    def is_active_workflow_visual_state(self):
        return self._active

    def _sync_theme_skin(self):
        return theme.theme_manager.set_state(locked=self.locked, active=self._active)


class PreviewControllerTests(unittest.TestCase):
    def setUp(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)
        self.host = _Host()
        self.pc = PreviewController(self.host)

    def tearDown(self):
        self.pc.shutdown()
        self.host.deleteLater()
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    # -- construction ---------------------------------------------------
    def test_builds_its_own_widgets(self):
        for name in ("preview_container", "preview_label", "preview_scrubber",
                     "play_pause_btn", "overlay_container"):
            self.assertIsNotNone(getattr(self.pc, name), name)

    def test_box_has_the_fixed_16_by_9_size_the_pipeline_depends_on(self):
        # The ffmpeg pipe is split into frames by byte count, so the frame size
        # must be known and constant. A resizable box would corrupt the stream.
        self.assertEqual(self.pc.preview_container.width(), 180)
        self.assertEqual(self.pc.preview_container.height(), 101)
        self.assertEqual(self.pc._preview_frame_size, 180 * 101 * 3)

    # isVisible() is False for any child of a window that was never shown, so
    # these assert the explicit show/hide state, which is what the code sets.
    def test_starts_idle_with_controls_hidden(self):
        self.assertEqual(self.pc.preview_source_path, "")
        self.assertFalse(self.pc.preview_playing)
        self.assertTrue(self.pc.play_pause_btn.isHidden())
        self.assertTrue(self.pc.preview_scrubber.isHidden())

    def test_placeholder_text_is_shown_initially(self):
        self.assertEqual(self.pc.preview_label.text(), "No Preview")

    # -- theming --------------------------------------------------------
    def test_widgets_take_their_colours_from_the_theme(self):
        accent = theme.skin().accent
        self.assertIn(accent, self.pc.preview_container.styleSheet())
        self.assertIn(accent, self.pc.play_pause_btn.styleSheet())

    def test_placeholder_colour_follows_the_hosts_state(self):
        for locked, active, expected in (
            (False, False, theme.IDLE),
            (False, True, theme.ACTIVE),
            (True, False, theme.LOCKED),
        ):
            self.host.locked = locked
            self.host._active = active
            self.pc._set_preview_placeholder("No Preview")
            self.assertIn(expected.accent, self.pc.preview_label.styleSheet(),
                          f"locked={locked} active={active}")

    # -- playback state -------------------------------------------------
    def test_toggle_is_a_noop_without_a_source(self):
        self.pc.toggle_preview_playback()
        self.assertFalse(self.pc.preview_playing)

    def test_toggle_is_a_noop_when_the_source_no_longer_exists(self):
        # A file can be deleted or moved between selection and playback.
        self.pc.preview_source_path = "Z:/gone/missing.mp4"
        self.pc.toggle_preview_playback()
        self.assertFalse(self.pc.preview_playing)

    def test_clear_resets_every_piece_of_state(self):
        self.pc.preview_source_path = "C:/x.mp4"
        self.pc.preview_playing = True
        self.pc.preview_seek_seconds = 12.5
        self.pc.preview_frame_index = 150
        self.pc.preview_duration_sec = 60.0

        self.pc._clear_preview_display()

        self.assertEqual(self.pc.preview_source_path, "")
        self.assertFalse(self.pc.preview_playing)
        self.assertEqual(self.pc.preview_seek_seconds, 0.0)
        self.assertEqual(self.pc.preview_frame_index, 0)
        self.assertEqual(self.pc.preview_duration_sec, 0.0)
        self.assertTrue(self.pc.play_pause_btn.isHidden())
        self.assertEqual(self.pc.preview_label.text(), "No Preview")

    def test_stopping_the_process_clears_the_frame_buffer(self):
        # A stale partial frame would desynchronise the next stream.
        self.pc._preview_buf = bytearray(b"\x01\x02\x03")
        self.pc._stop_preview_process()
        self.assertEqual(len(self.pc._preview_buf), 0)

    # -- the byte pipeline ----------------------------------------------
    def test_partial_frame_is_buffered_not_rendered(self):
        self.pc.preview_source_path = "C:/x.mp4"
        before = self.pc.preview_frame_index
        self.pc._preview_buf = bytearray(b"\x00" * (self.pc._preview_frame_size - 1))
        # One byte short: nothing should be assembled yet.
        self.assertEqual(self.pc.preview_frame_index, before)

    def test_probe_duration_returns_zero_for_a_missing_file(self):
        self.assertEqual(self.pc._probe_duration_seconds("Z:/gone/missing.mp4"), 0.0)

    def test_probe_duration_never_raises_on_nonsense(self):
        for value in ("", None, 12345):
            self.assertEqual(self.pc._probe_duration_seconds(value), 0.0)

    # -- paths that shell out -------------------------------------------
    # These were the two the extraction broke: FFMPEG_RENDER_TIMEOUT and
    # QImage were used here but not imported, so both raised NameError.
    # Ruff caught it; nothing in the suite reached them. Now something does.
    def test_thumbnail_generation_handles_a_missing_file(self):
        self.pc._generate_and_show_thumbnail("Z:/gone/missing.mp4")
        self.assertEqual(self.pc.preview_label.text(), "No Preview")

    def test_thumbnail_generation_handles_an_empty_path(self):
        self.pc._generate_and_show_thumbnail("")
        self.assertEqual(self.pc.preview_label.text(), "No Preview")

    def test_render_frame_at_handles_a_missing_file(self):
        # Must not raise: it runs from the scrub handler, on the UI thread.
        self.pc._render_frame_at("Z:/gone/missing.mp4", 1.0)

    def test_on_preview_bytes_assembles_a_full_frame(self):
        """Feed exactly one frame's worth of bytes and expect a pixmap.

        Exercises the QImage construction that was silently unimported.
        """
        self.pc.preview_source_path = "C:/x.mp4"
        self.pc.preview_label.setPixmap(__import__("PyQt5.QtGui", fromlist=["QPixmap"]).QPixmap())
        self.pc._preview_buf = bytearray(b"@" * self.pc._preview_frame_size)
        self.pc._assemble_frames()
        pixmap = self.pc.preview_label.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(len(self.pc._preview_buf), 0)

    def test_on_preview_bytes_leaves_a_partial_frame_buffered(self):
        self.pc.preview_source_path = "C:/x.mp4"
        partial = self.pc._preview_frame_size - 10
        self.pc._preview_buf = bytearray(b"@" * partial)
        self.pc._assemble_frames()
        self.assertEqual(len(self.pc._preview_buf), partial)

    # -- star field -----------------------------------------------------
    def test_star_field_starts_and_stops(self):
        self.pc._start_star_field("teal")
        self.assertEqual(len(self.pc.stars), 30)
        self.assertTrue(self.pc.star_field_timer.isActive())
        self.pc._stop_star_field()
        self.assertEqual(self.pc.stars, [])

    def test_star_field_accepts_the_legacy_theme_names(self):
        for name, expected in (("gray", theme.LOCKED),
                               ("teal", theme.IDLE),
                               ("green", theme.ACTIVE)):
            self.pc._start_star_field(name)
            self.assertEqual(self.pc.star_color.name().lower(),
                             expected.accent.lower(), name)
            self.pc._stop_star_field()

    def test_star_field_without_a_name_follows_the_hosts_state(self):
        self.host.locked = True
        self.pc._start_star_field()
        self.assertEqual(self.pc.star_color.name().lower(),
                         theme.LOCKED.accent.lower())
        self.pc._stop_star_field()

    def test_stopping_a_star_field_that_never_started_is_safe(self):
        self.pc._stop_star_field()
        self.pc._stop_star_field()

    def test_star_field_hides_the_playback_controls(self):
        # The star field is an idle animation; playback chrome over it is wrong.
        self.pc.play_pause_btn.show()
        self.pc.preview_scrubber.show()
        self.pc._start_star_field("teal")
        self.assertTrue(self.pc.play_pause_btn.isHidden())
        self.assertTrue(self.pc.preview_scrubber.isHidden())

    # -- hover behaviour ------------------------------------------------
    def test_hover_shows_the_play_button_only_when_media_is_loaded(self):
        enter = QEvent(QEvent.Enter)
        self.pc.eventFilter(self.pc.preview_container, enter)
        self.assertTrue(self.pc.play_pause_btn.isHidden())

        self.pc.preview_source_path = "C:/x.mp4"
        self.pc.eventFilter(self.pc.preview_container, enter)
        self.assertFalse(self.pc.play_pause_btn.isHidden())

    def test_hover_shows_the_scrubber_only_when_the_duration_is_known(self):
        enter = QEvent(QEvent.Enter)
        self.pc.preview_source_path = "C:/x.mp4"

        self.pc.preview_duration_sec = 0.0
        self.pc.eventFilter(self.pc.preview_container, enter)
        self.assertTrue(self.pc.preview_scrubber.isHidden())

        self.pc.preview_duration_sec = 30.0
        self.pc.eventFilter(self.pc.preview_container, enter)
        self.assertFalse(self.pc.preview_scrubber.isHidden())

    def test_leaving_hides_the_controls(self):
        self.pc.preview_source_path = "C:/x.mp4"
        self.pc.preview_duration_sec = 30.0
        self.pc.eventFilter(self.pc.preview_container, QEvent(QEvent.Enter))
        self.pc.eventFilter(self.pc.preview_container, QEvent(QEvent.Leave))
        self.assertTrue(self.pc.play_pause_btn.isHidden())
        self.assertTrue(self.pc.preview_scrubber.isHidden())

    def test_unrelated_widgets_are_ignored_by_the_filter(self):
        other = QWidget()
        self.assertFalse(
            self.pc.eventFilter(other, QEvent(QEvent.Enter)))
        other.deleteLater()

    # -- scrubbing ------------------------------------------------------
    def test_scrub_press_and_release_toggle_the_user_flag(self):
        # While the user drags, the UI tick must not fight them for the value.
        self.pc.preview_source_path = "C:/x.mp4"
        self.pc._on_preview_scrub_start()
        self.assertTrue(self.pc._preview_user_scrubbing)
        self.pc._on_preview_scrub_end()
        self.assertFalse(self.pc._preview_user_scrubbing)

    def test_scrubbing_with_no_media_is_ignored(self):
        self.pc.preview_source_path = ""
        self.pc._on_preview_scrub_start()
        self.assertFalse(self.pc._preview_user_scrubbing)

    def test_ui_tick_does_nothing_while_the_user_is_scrubbing(self):
        self.pc.preview_source_path = "C:/x.mp4"
        self.pc.preview_duration_sec = 60.0
        self.pc.preview_scrubber.setValue(500)
        self.pc._preview_user_scrubbing = True
        self.pc._tick_preview_ui()
        self.assertEqual(self.pc.preview_scrubber.value(), 500)

    def test_ui_tick_does_nothing_without_a_source(self):
        self.pc.preview_scrubber.setValue(250)
        self.pc._tick_preview_ui()
        self.assertEqual(self.pc.preview_scrubber.value(), 250)

    # -- lifecycle ------------------------------------------------------
    def test_shutdown_stops_the_ui_timer(self):
        self.assertTrue(self.pc.preview_ui_timer.isActive())
        self.pc.shutdown()
        self.assertFalse(self.pc.preview_ui_timer.isActive())

    def test_shutdown_is_idempotent(self):
        self.pc.shutdown()
        self.pc.shutdown()


class HostContractTests(unittest.TestCase):
    """The main window must keep providing what the controller relies on."""

    def test_main_window_exposes_the_delegating_accessors(self):
        from ui.main_window import VideoConverterApp
        for name in ("preview_container", "preview_label", "preview_scrubber",
                     "play_pause_btn", "overlay_container", "preview_source_path",
                     "preview_playing", "preview_seek_seconds",
                     "preview_frame_index", "preview_duration_sec"):
            self.assertIsInstance(getattr(VideoConverterApp, name, None), property,
                                  f"{name} should delegate to the controller")

    def test_main_window_still_offers_the_old_method_names(self):
        from ui.main_window import VideoConverterApp
        for name in ("toggle_preview_playback", "update_preview_controls_style",
                     "_set_preview_placeholder", "_clear_preview_display",
                     "_stop_preview_process", "_start_preview_process",
                     "_probe_duration_seconds", "_generate_and_show_thumbnail",
                     "_render_frame_at", "_start_star_field", "_stop_star_field"):
            self.assertTrue(callable(getattr(VideoConverterApp, name, None)), name)

    def test_the_host_contract_stays_narrow(self):
        """PreviewController should need almost nothing from its host.

        _Host above implements the whole contract in three members. If this
        test starts failing, check whether the controller has begun reaching
        back into the main window rather than just widening the stub.
        """
        import inspect

        import ui.preview_controller as mod
        source = inspect.getsource(mod)
        used = set()
        for line in source.splitlines():
            if "self._host." in line:
                for piece in line.split("self._host.")[1:]:
                    name = ""
                    for ch in piece:
                        if ch.isalnum() or ch == "_":
                            name += ch
                        else:
                            break
                    if name:
                        used.add(name)
        self.assertTrue(used <= {"style", "_sync_theme_skin"},
                        f"controller reaches into the host for: {sorted(used)}")


if __name__ == "__main__":
    unittest.main()


class GlobalStyleWalkerTests(unittest.TestCase):
    """The overlay button must survive the main window's style sweep.

    VideoConverterApp.apply_button_style_to_all_widgets walks the widget tree
    and stamps the main gradient onto every QPushButton. The preview's play
    button is a 22px translucent circle over a video thumbnail, so it opts
    out via the `skipGlobalStyle` property the walker checks. Without that it
    was silently given the main gradient moments after being styled -- which
    is what it looked like for as long as both pieces of code existed.
    """

    def test_the_play_button_opts_out_of_the_global_button_style(self):
        host = _Host()
        pc = PreviewController(host)
        try:
            self.assertTrue(pc.play_pause_btn.property("skipGlobalStyle"))
        finally:
            pc.shutdown()
            host.deleteLater()

    def test_it_keeps_its_own_style_in_a_real_window(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.main_window import VideoConverterApp

        window = VideoConverterApp()
        try:
            for _ in range(15):
                app.processEvents()
            sheet = window.play_pause_btn.styleSheet()
            self.assertIn("border-radius: 11px", sheet,
                          "the overlay button lost its circular shape")
            self.assertNotIn("qlineargradient", sheet,
                             "the main gradient overwrote the overlay style")
        finally:
            window.close()
            window.deleteLater()
            app.processEvents()
