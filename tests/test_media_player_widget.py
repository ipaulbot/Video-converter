import os
import subprocess
import tempfile
import time
import unittest

from PyQt5.QtCore import QEvent, QMimeData, QObject, QPointF, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDropEvent, QMouseEvent
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import (
    QWIDGETSIZE_MAX,
    QApplication,
    QLabel,
    QSizePolicy,
    QSplitter,
    QToolButton,
)

from ui import theme
from ui.media_player_parts import PlaylistTable
from ui.media_player_widget import (
    MAX_PANELS,
    PANEL_COUNT_OPTIONS,
    MediaPlayerWidget,
    PlayerPanel,
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
            self.assertEqual(widget.play_btn.toolTip(), "Play all")
            self.assertFalse(widget._is_playing)
        finally:
            widget.shutdown()

    def test_transport_is_an_icon_toolbar(self):
        widget, _panel = self._loaded_widget_with_fake_player()
        for button, tip in (
            (widget.play_btn, "Play all"),
            (widget.stop_btn, "Stop all"),
            (widget.restart_btn, "Restart"),
            (widget.fullscreen_btn, "Fullscreen (F)"),
            (widget.playlist_btn, "Playlist"),
            (widget.mute_btn, "Mute (M)"),
        ):
            self.assertIsInstance(button, QToolButton, tip)
            self.assertFalse(button.icon().isNull(), tip)
            self.assertEqual(button.toolTip(), tip)
            self.assertEqual(button.text(), "", tip)
        widget.play_all()
        self.assertEqual(widget.play_btn.toolTip(), "Pause all")
        widget.stop_all()
        self.assertEqual(widget.play_btn.toolTip(), "Play all")
        widget.mute_btn.setChecked(True)
        self.assertEqual(widget.mute_btn.toolTip(), "Unmute (M)")

    def test_panel_actions_are_icon_buttons(self):
        widget = self._widget()
        panel = widget.panels[0]
        self.assertIsInstance(panel.load_btn, QToolButton)
        self.assertIsInstance(panel.clear_btn, QToolButton)
        self.assertEqual(panel.load_btn.toolTip(), "Load a file into this panel")

    def test_layout_mode_sets_panel_min_height(self):
        widget = self._widget()
        widget.apply_layout_mode(theme.FULL)
        self.assertEqual(
            widget.panels[0].video_container.minimumHeight(),
            theme.FULL.player_panel_min_h,
        )
        widget.apply_layout_mode(theme.COMPACT)
        self.assertEqual(
            widget.panels[0].video_container.minimumHeight(),
            theme.COMPACT.player_panel_min_h,
        )

    def test_each_panel_offset_defaults_to_zero(self):
        widget = MediaPlayerWidget()
        try:
            for panel in widget.panels:
                self.assertEqual(panel.offset_ms(), 0)
                self.assertFalse(hasattr(panel, "offset_spin"))   # lives in the playlist now
        finally:
            widget.shutdown()

    def test_panel_offset_comes_from_the_current_clips_playlist_row(self):
        widget = MediaPlayerWidget()
        try:
            panel = widget.panels[0]
            panel.player = _FakePlayer()
            panel._media_path = "C:\\Videos\\a.mp4"
            panel.playlist.add(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
            panel.playlist.set_offset("C:\\Videos\\a.mp4", 1.5)
            panel.playlist.set_offset("C:\\Videos\\b.mp4", -2.0)
            self.assertEqual(panel.offset_ms(), 1500)
            panel._media_path = "C:\\Videos\\b.mp4"
            self.assertEqual(panel.offset_ms(), -2000)
            panel._media_path = ""
            self.assertEqual(panel.offset_ms(), 0)
        finally:
            widget.shutdown()

    def test_editing_an_offset_in_the_playlist_reseats_the_paused_panel(self):
        widget = MediaPlayerWidget()
        try:
            panel = widget.panels[0]
            panel.player = _FakePlayer(duration=60000)
            panel._media_path = "C:\\Videos\\a.mp4"
            panel.playlist.add(["C:\\Videos\\a.mp4"])
            widget.select_panel(0)
            widget.playlist_dock.refresh()
            widget.position_slider.setRange(0, 60000)
            widget._set_slider_value(4000)
            panel.player.calls.clear()
            widget.playlist_dock.list.item(0, PlaylistTable.OFFSET).setData(Qt.UserRole, 1.5)
            self.assertEqual(panel.offset_ms(), 1500)
            self.assertIn("setPosition(5500)", panel.player.calls)
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

    def test_help_documents_every_shortcut(self):
        import sys
        from pathlib import Path

        source_dir = Path(__file__).resolve().parents[1] / "docs" / "help" / "source"
        if str(source_dir) not in sys.path:
            sys.path.insert(0, str(source_dir))
        import content_loader

        chapter = next(c for c in content_loader.load_manual("help", "en")
                       if c["id"] == "media-player")
        tables = [b for b in chapter["blocks"]
                  if b["type"] == "table" and b["headers"][0] == "Keys"]
        self.assertEqual(len(tables), 1, "media-player needs exactly one Keys/Action table")
        documented = "\n".join(cell for row in tables[0]["rows"] for cell in row)
        widget = self._widget()
        for key in widget.shortcuts:
            self.assertIn(key, documented, f"shortcut {key} is not in the manual")

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

    def test_video_surface_native_size_never_drives_the_layout(self):
        # QVideoWidget.sizeHint() is the clip's resolution; after a fullscreen
        # round trip the layout re-reads hints and a 1080p clip used to grow the
        # panel to 1000+ px, scrolling the whole tab.
        widget = self._widget()
        panel = widget.panels[0]
        video = panel._ensure_video_widget()
        self.assertEqual(video.sizePolicy().verticalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(video.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(panel.video_container.layout().sizeHint().height(), 0)

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

    # --- stage layout: playlist strip under the grid, Inspect on the right ----

    def test_stage_is_a_splitter_with_the_video_column_left_and_inspect_right(self):
        widget = self._widget()
        self.assertIsInstance(widget.stage, QSplitter)
        self.assertEqual(widget.stage.orientation(), Qt.Horizontal)
        self.assertIs(widget.stage.widget(0), widget.video_column)
        self.assertIs(widget.stage.widget(1), widget.inspect_dock)
        self.assertFalse(widget.stage.childrenCollapsible())
        # The dock scales with the window: a floor, no ceiling.
        self.assertGreaterEqual(widget.inspect_dock.minimumWidth(), 260)
        self.assertEqual(widget.inspect_dock.maximumWidth(), QWIDGETSIZE_MAX)
        # Playlist sits below the panel grid inside the video column.
        column = widget.video_column.layout()
        self.assertIs(column.itemAt(column.count() - 1).widget(), widget.playlist_dock)
        self.assertTrue(widget.playlist_dock.horizontal)

    def test_splitter_gives_the_video_roughly_three_quarters(self):
        widget = self._widget()
        widget.resize(1600, 900)
        widget.show()
        self.app.processEvents()
        widget.inspect_btn.setChecked(True)
        widget._apply_initial_splitter_sizes()
        video_w, dock_w = widget.stage.sizes()
        self.assertGreater(video_w, dock_w * 2)
        self.assertGreater(dock_w, 300)

    def test_inspect_is_open_by_default_and_the_playlist_is_not(self):
        widget = self._widget()
        widget.show()
        self.assertTrue(widget.inspect_btn.isChecked())
        self.assertTrue(widget.inspect_dock.isVisibleTo(widget))
        self.assertFalse(widget.playlist_btn.isChecked())
        self.assertFalse(widget.playlist_dock.isVisibleTo(widget))
        # Panel count no longer drives the playlist.
        widget.panels_combo.setCurrentIndex(0)
        self.assertFalse(widget.playlist_dock.isVisibleTo(widget))

    def test_inspect_and_playlist_toggle_independently(self):
        widget = self._widget()
        widget.show()
        widget.playlist_btn.setChecked(True)
        self.assertTrue(widget.playlist_dock.isVisibleTo(widget))
        self.assertTrue(widget.inspect_dock.isVisibleTo(widget))
        widget.inspect_btn.setChecked(False)
        self.assertFalse(widget.inspect_dock.isVisibleTo(widget))
        self.assertTrue(widget.playlist_dock.isVisibleTo(widget))

    def test_dock_visibility_persists_and_restores(self):
        saves = []
        settings = {}
        widget = self._widget(settings=settings, saves=saves)
        widget.inspect_btn.setChecked(False)
        widget.playlist_btn.setChecked(True)
        self.assertFalse(settings["media_player"]["inspect_visible"])
        self.assertTrue(settings["media_player"]["playlist_visible"])
        self.assertEqual(len(saves), 2)
        restored = self._widget(settings={"media_player": {"inspect_visible": False, "playlist_visible": True}})
        self.assertFalse(restored.inspect_btn.isChecked())
        self.assertTrue(restored.playlist_btn.isChecked())

    def test_fullscreen_hides_the_docks_and_restores_them(self):
        widget = self._widget()
        widget.show()
        widget.playlist_btn.setChecked(True)
        widget.enter_fullscreen()
        host = widget._fullscreen_host
        self.assertFalse(widget.inspect_dock.isVisibleTo(host))
        self.assertFalse(widget.playlist_dock.isVisibleTo(host))
        widget.exit_fullscreen()
        self.assertTrue(widget.inspect_dock.isVisibleTo(widget))
        self.assertTrue(widget.playlist_dock.isVisibleTo(widget))
        self.assertTrue(widget.inspect_btn.isChecked())
        self.assertTrue(widget.playlist_btn.isChecked())

    def test_selected_media_is_announced_for_the_sidebar_preview(self):
        widget = self._widget()
        seen = []
        widget.media_selected.connect(seen.append)
        widget.panels[1]._media_path = "C:/Videos/b.mp4"
        widget.select_panel(1)
        widget.panels[1]._media_path = ""
        widget._on_panel_media_changed(widget.panels[1])
        widget.panels[0]._media_path = "C:/Videos/a.mp4"
        widget._on_panel_media_changed(widget.panels[0])      # not selected: silent
        self.assertEqual(seen, ["C:/Videos/b.mp4", ""])

    # --- Inspect dock (absorbed the Video Inspection Tool tab) ---------------

    def test_opening_the_inspect_dock_inspects_the_selected_panels_file(self):
        widget = self._widget()
        widget.inspect_btn.setChecked(False)
        inspected = []
        widget.inspect_dock.inspect_path = lambda path: inspected.append(path)
        widget.panels[1]._media_path = "C:/Videos/b.mp4"
        widget.select_panel(1)
        self.assertEqual(inspected, [])            # dock closed: nothing runs
        widget.inspect_btn.setChecked(True)
        self.assertEqual(inspected, ["C:/Videos/b.mp4"])

    def test_highlighting_a_playlist_row_inspects_that_clip_without_loading_it(self):
        widget = self._widget()
        inspected = []
        widget.inspect_dock.inspect_path = lambda path: inspected.append(path)
        panel = widget.panels[0]
        panel.playlist.add(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
        widget.select_panel(0)
        widget.playlist_dock.refresh()
        inspected.clear()
        widget.playlist_dock.list.setCurrentRow(1)
        self.assertEqual(inspected, ["C:\\Videos\\b.mp4"])
        self.assertEqual(panel._media_path, "")               # highlighted, not loaded
        # With the dock closed, highlighting runs nothing.
        widget.inspect_btn.setChecked(False)
        inspected.clear()
        widget.playlist_dock.list.setCurrentRow(0)
        self.assertEqual(inspected, [])

    def test_clicking_the_video_surface_selects_that_panel(self):
        # The native QVideoWidget sits over the panel; a press on it must
        # still count as a click on the panel (and so refresh Inspect).
        widget = self._widget()
        panel = widget.panels[1]
        video = panel._ensure_video_widget()
        self.assertNotEqual(widget.selected_index, 1)
        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(5, 5), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(video, press)
        self.assertEqual(widget.selected_index, 1)

    def test_panel_column_shows_where_each_clip_is_on_screen_only_with_several_panels(self):
        widget = self._widget()
        widget.panels_combo.setCurrentIndex(widget.panels_combo.findData(1))
        panel = widget.panels[0]
        panel.playlist.add(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
        panel._media_path = "C:\\Videos\\a.mp4"
        widget.panels[1]._media_path = "C:\\Videos\\a.mp4"
        widget.select_panel(0)
        table = widget.playlist_dock.list
        self.assertTrue(table.isColumnHidden(PlaylistTable.PANEL))       # one panel: hidden
        widget.panels_combo.setCurrentIndex(widget.panels_combo.findData(2))
        self.assertFalse(table.isColumnHidden(PlaylistTable.PANEL))
        self.assertEqual(table.item(0, PlaylistTable.PANEL).text(), "1, 2")
        self.assertEqual(table.item(1, PlaylistTable.PANEL).text(), "")
        # A panel changing its clip updates the column even when it is not the selected one.
        widget.panels[1]._media_path = "C:\\Videos\\b.mp4"
        widget._on_panel_media_changed(widget.panels[1])
        self.assertEqual(table.item(0, PlaylistTable.PANEL).text(), "1")
        self.assertEqual(table.item(1, PlaylistTable.PANEL).text(), "2")

    def test_the_inspect_dock_has_no_title_row(self):
        # The panel caption already names the clip; the dock is just the data.
        widget = self._widget()
        self.assertFalse(hasattr(widget.inspect_dock, "title_label"))
        labels = widget.inspect_dock.findChildren(QLabel)
        self.assertFalse(any(label.text().startswith("Inspect") for label in labels))

    # --- loading feeds the playlist ---------------------------------------------

    def test_loading_a_clip_adds_it_to_that_panels_playlist_and_selects_it(self):
        widget = self._widget()
        widget.playlist_btn.setChecked(True)
        panel = widget.panels[0]
        with tempfile.TemporaryDirectory() as folder:
            clip = os.path.join(folder, "a.mp4")
            with open(clip, "wb") as handle:
                handle.write(b"x")
            panel.load_media(clip)
            self.assertEqual(panel.playlist.items, [clip])
            self.assertEqual(widget.playlist_dock.list.currentRow(), 0)
            # Loading it again does not duplicate the entry.
            panel.load_media(clip)
            self.assertEqual(panel.playlist.items, [clip])

    def test_loading_into_an_unselected_panel_fills_that_panels_list_only(self):
        widget = self._widget()
        with tempfile.TemporaryDirectory() as folder:
            clip = os.path.join(folder, "b.mp4")
            with open(clip, "wb") as handle:
                handle.write(b"x")
            widget.panels[1].load_media(clip)
            self.assertEqual(widget.panels[1].playlist.items, [clip])
            self.assertEqual(widget.panels[0].playlist.items, [])

    def test_loading_into_a_panel_selects_it_so_the_dock_and_inspect_follow(self):
        # 15:32 report: a drop on panel 2 showed nothing -- the dock and Inspect
        # follow the *selected* panel and the drop did not select it.
        widget = self._widget()
        widget.playlist_btn.setChecked(True)
        inspected = []
        widget.inspect_dock.inspect_path = lambda path: inspected.append(path)
        with tempfile.TemporaryDirectory() as folder:
            clip = os.path.join(folder, "b.mp4")
            with open(clip, "wb") as handle:
                handle.write(b"x")
            self.assertEqual(widget.selected_index, 0)
            widget.panels[1].load_media(clip)
            self.assertEqual(widget.selected_index, 1)
            self.assertEqual(widget.playlist_dock.model, widget.panels[1].playlist)
            self.assertEqual(widget.playlist_dock.list.count(), 1)
            self.assertEqual(widget.playlist_dock.list.currentRow(), 0)
            self.assertEqual(inspected[-1], clip)
            self.assertEqual(widget.playlist_dock.panel_title(), "Panel 2")

    def test_a_drop_on_a_panel_loads_and_selects_it(self):
        widget = self._widget()
        with tempfile.TemporaryDirectory() as folder:
            clip = os.path.join(folder, "c.mp4")
            with open(clip, "wb") as handle:
                handle.write(b"x")
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(clip)])
            drop = QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
            widget.panels[1].dropEvent(drop)
            self.assertEqual(os.path.normpath(widget.panels[1]._media_path), os.path.normpath(clip))
            self.assertEqual(widget.selected_index, 1)

    # --- transport bar order ------------------------------------------------------

    def test_view_and_playback_settings_sit_left_with_the_transport_buttons(self):
        widget = self._widget()
        row = widget.button_row
        widgets = [row.itemAt(i).widget() for i in range(row.count())]
        names = [w for w in widgets if w is not None]
        order = [
            widget.play_btn, widget.stop_btn, widget.restart_btn,
            widget.fullscreen_btn, widget.playlist_btn, widget.inspect_btn,
            widget.panels_combo, widget.speed_combo, widget.volume_slider, widget.mute_btn,
        ]
        positions = [names.index(w) for w in order]
        self.assertEqual(positions, sorted(positions))
        # The stretch is the last item: everything hugs the left edge.
        last = row.itemAt(row.count() - 1)
        self.assertIsNone(last.widget())
        self.assertIsNotNone(last.spacerItem())
        self.assertGreater(last.spacerItem().sizePolicy().horizontalPolicy() & QSizePolicy.ExpandFlag, 0)

    # --- compact window: long clip names must not widen the tab ---------------------

    def test_long_clip_names_do_not_widen_the_video_column(self):
        widget = self._widget()
        empty_min = widget.video_column.minimumSizeHint().width()
        for panel in widget.panels[:2]:
            panel.name_label.setText("Panel 1: " + "Video_Video_1_20260925_202215_" * 2 + ".mp4")
        self.assertLessEqual(widget.video_column.minimumSizeHint().width(), empty_min + 40)
        self.assertTrue(hasattr(widget.panels[0].name_label, "elided_text"))

    # --- the native surface hides with its panel (no stale content on re-show) ----

    def test_the_video_surface_hides_with_the_panel_and_returns_with_the_frame(self):
        widget = self._widget()
        widget.show()
        panel = widget.panels[0]
        player = _FakePlayer(position=4200)
        panel._adopt_player(player)
        video = panel._ensure_video_widget()
        self.app.processEvents()          # the layout shows a late child on a queued call
        panel._media_path = "C:/Videos/a.mp4"
        panel._primed_path = panel._media_path
        self.assertFalse(video.isHidden())
        widget.hide()
        self.assertTrue(video.isHidden())
        widget.show()
        # The nudge runs against the hidden surface; the dark tile paints meanwhile.
        self.assertTrue(panel._priming)
        self.assertTrue(video.isHidden())
        player.positionChanged.emit(4240)
        self.assertFalse(panel._priming)
        self.assertFalse(video.isHidden())

    def test_the_surface_returns_at_once_when_no_nudge_is_needed(self):
        widget = self._widget()
        widget.show()
        panel = widget.panels[0]
        player = _FakePlayer(position=10)
        panel._adopt_player(player)
        video = panel._ensure_video_widget()
        self.app.processEvents()
        panel._media_path = "C:/Videos/a.mp4"
        widget._is_playing = True                 # playing on: nothing to nudge
        widget.hide()
        self.assertTrue(video.isHidden())
        widget.show()
        self.assertFalse(video.isHidden())
        # Play pressed while a nudge is running also reveals it.
        widget._is_playing = False
        panel._primed_path = panel._media_path
        widget.hide()
        widget.show()
        self.assertTrue(video.isHidden())
        panel._cancel_prime()
        self.assertFalse(video.isHidden())

    def test_hiding_the_widget_does_not_pause_or_stop_playback(self):
        # Workflow rule 1: switching tabs never stops anything.
        widget = self._widget()
        widget.show()
        panel = widget.panels[0]
        player = _FakePlayer(position=10)
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        widget._is_playing = True
        widget.hide()
        widget.show()
        self.assertNotIn("pause", player.calls)
        self.assertNotIn("stop", player.calls)

    # --- coming back to the tab re-presents the frame -------------------------

    def test_showing_the_widget_again_nudges_paused_panels_back_to_their_frame(self):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer(position=4200)
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._primed_path = panel._media_path      # first frame already shown
        widget.hide()
        widget.show()
        self.assertEqual(player.calls, ["setMuted(True)", "play"])
        player.positionChanged.emit(4240)
        self.assertEqual(player.calls[2:], ["pause", "setPosition(4200)", "setMuted(False)"])

    def test_re_show_leaves_playing_and_empty_panels_alone(self):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer(position=10)
        panel._adopt_player(player)
        widget._is_playing = True
        panel._media_path = "C:/Videos/a.mp4"
        widget.hide()
        widget.show()
        widget._is_playing = False
        panel._media_path = ""
        widget.hide()
        widget.show()
        self.assertEqual(player.calls, [])

    def test_selecting_another_panel_re_inspects_while_the_dock_is_open(self):
        widget = self._widget()
        widget.inspect_btn.setChecked(False)
        inspected = []
        widget.inspect_dock.inspect_path = lambda path: inspected.append(path)
        widget.panels[0]._media_path = "C:/Videos/a.mp4"
        widget.panels[1]._media_path = "C:/Videos/b.mp4"
        widget.inspect_btn.setChecked(True)
        widget.select_panel(1)
        self.assertEqual(inspected, ["C:/Videos/a.mp4", "C:/Videos/b.mp4"])

    def test_loading_or_clearing_the_selected_panel_updates_the_dock(self):
        widget = self._widget()
        inspected = []
        widget.inspect_dock.inspect_path = lambda path: inspected.append(path)
        panel = widget.selected_panel()
        panel._media_path = "C:/Videos/a.mp4"
        widget._on_panel_media_changed(panel)
        panel._media_path = ""
        widget._on_panel_media_changed(panel)
        self.assertEqual(inspected, ["C:/Videos/a.mp4", ""])   # empty path = clear

    def test_media_change_on_an_unselected_panel_is_ignored(self):
        widget = self._widget()
        inspected = []
        widget.inspect_dock.inspect_path = lambda path: inspected.append(path)
        widget.panels[2]._media_path = "C:/Videos/c.mp4"
        widget._on_panel_media_changed(widget.panels[2])
        self.assertEqual(inspected, [])

    # --- first frame on load ---------------------------------------------------

    def test_load_primes_the_first_frame_then_pauses_at_zero(self):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer()
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._on_status_for_prime(QMediaPlayer.LoadedMedia)
        self.assertEqual(player.calls, ["setMuted(True)", "play"])
        player.positionChanged.emit(40)
        self.assertEqual(player.calls[2:], ["pause", "setPosition(0)", "setMuted(False)"])
        self.assertFalse(panel._priming)
        # Only once per load.
        panel._on_status_for_prime(QMediaPlayer.LoadedMedia)
        self.assertEqual(len(player.calls), 5)

    def test_prime_falls_back_to_a_timer_when_no_position_arrives(self):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer()
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._on_status_for_prime(QMediaPlayer.BufferedMedia)
        self.assertTrue(panel._prime_timer.isActive())
        panel._prime_timer.timeout.emit()
        self.assertEqual(player.calls[-3:], ["pause", "setPosition(0)", "setMuted(False)"])

    def test_no_prime_while_the_host_is_playing_or_the_panel_is_empty(self):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer()
        panel._adopt_player(player)
        widget._is_playing = True
        panel._media_path = "C:/Videos/a.mp4"
        panel._on_status_for_prime(QMediaPlayer.LoadedMedia)
        widget._is_playing = False
        panel._media_path = ""
        panel._on_status_for_prime(QMediaPlayer.LoadedMedia)
        self.assertEqual(player.calls, [])

    def test_a_position_emitted_from_inside_play_does_not_finish_the_prime(self):
        # Media Foundation emits positionChanged() synchronously from play();
        # pausing in that stack loses the pause and the clip runs on.
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer(position=800)
        original_play = player.play

        def play_emitting_position():
            original_play()
            player.positionChanged.emit(800)

        player.play = play_emitting_position
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._primed_path = panel._media_path
        self.assertTrue(panel.represent_frame())
        self.assertTrue(panel._priming)
        self.assertEqual(player.calls, ["setMuted(True)", "play"])
        # Still at the target: no frame has been drawn yet either.
        player.positionChanged.emit(800)
        self.assertTrue(panel._priming)
        player.positionChanged.emit(840)
        self.assertFalse(panel._priming)
        self.assertEqual(player.calls[2:], ["pause", "setPosition(800)", "setMuted(False)"])

    # --- paused-seek watchdog -------------------------------------------------

    def _paused_panel(self, position=0):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePausedPlayer(position=position)
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._primed_path = panel._media_path
        return widget, panel, player

    def test_a_paused_seek_is_watched_and_left_alone_when_it_holds(self):
        widget, panel, player = self._paused_panel()
        widget._is_playing = False
        widget.seek_all(800)
        self.assertEqual(player.calls, ["setPosition(800)"])
        self.assertTrue(panel._settle_timer.isActive())
        player._position = 800
        for _ in range(PlayerPanel.SETTLE_TICKS):
            panel._on_settle_tick()
        self.assertFalse(panel._settle_timer.isActive())
        self.assertEqual(player.calls, ["setPosition(800)"])

    def test_a_paused_seek_that_runs_away_is_pinned_back_with_a_play_pause_round_trip(self):
        # Media Foundation may keep decoding at full rate while state() says Paused.
        widget, panel, player = self._paused_panel()
        widget._is_playing = False
        panel.seek_paused(800)
        player._position = 800
        panel._on_settle_tick()
        player._position = 1010                      # +210 ms in one 100 ms tick
        panel._on_settle_tick()
        self.assertTrue(panel._priming)
        self.assertEqual(panel._prime_target_ms, 800)
        self.assertEqual(player.calls[-2:], ["setMuted(True)", "play"])
        player.positionChanged.emit(1060)
        self.assertEqual(player.calls[-3:], ["pause", "setPosition(800)", "setMuted(False)"])
        self.assertTrue(panel._settle_timer.isActive())   # and watched again

    def test_the_watchdog_gives_up_after_a_few_retries(self):
        widget, panel, player = self._paused_panel()
        widget._is_playing = False
        panel.seek_paused(800)
        for _ in range(PlayerPanel.SETTLE_MAX_RETRIES + 2):
            player._position = 800
            panel._on_settle_tick()
            player._position = 1100
            panel._on_settle_tick()
            if panel._priming:
                player.positionChanged.emit(1150)
        self.assertEqual(player.calls.count("play"), PlayerPanel.SETTLE_MAX_RETRIES)

    def test_play_stops_the_watchdog_so_playback_is_never_pinned(self):
        widget, panel, player = self._paused_panel()
        widget._is_playing = False
        panel.seek_paused(800)
        widget.play_all()
        self.assertFalse(panel._settle_timer.isActive())
        widget._is_playing = True
        widget.seek_all(1200)
        self.assertFalse(panel._settle_timer.isActive())   # playing seeks are not watched

    def test_prime_restores_the_users_mute_choice(self):
        widget = self._widget()
        widget.mute_btn.setChecked(True)
        panel = widget.panels[0]
        player = _FakePlayer(muted=True)
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._on_status_for_prime(QMediaPlayer.LoadedMedia)
        player.positionChanged.emit(1)
        self.assertEqual(player.calls[-1], "setMuted(True)")

    def test_loading_shows_a_caption_until_the_first_frame(self):
        widget = self._widget()
        panel = widget.panels[0]
        player = _FakePlayer()
        panel._adopt_player(player)
        panel._media_path = "C:/Videos/a.mp4"
        panel._begin_prime()
        self.assertIn("Loading", panel.placeholder.text())
        self.assertFalse(panel.placeholder.isHidden())
        panel._finish_prime()
        self.assertTrue(panel.placeholder.isHidden())


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


class _FakePlayer(QObject):
    """Just enough QMediaPlayer for the first-frame prime."""

    positionChanged = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(int)

    def __init__(self, muted=False, position=0, duration=0):
        super().__init__()
        self.calls = []
        self._muted = muted
        self._position = position
        self._duration = duration

    # shutdown() calls these on every created player.
    def stop(self):
        self.calls.append("stop")

    def setMedia(self, _content):
        pass

    def setVideoOutput(self, _output):
        pass

    def setVolume(self, _volume):
        pass

    def setPlaybackRate(self, _rate):
        pass

    def isMuted(self):
        return self._muted

    def setMuted(self, muted):
        self._muted = bool(muted)
        self.calls.append(f"setMuted({bool(muted)})")

    def play(self):
        self.calls.append("play")

    def pause(self):
        self.calls.append("pause")

    def setPosition(self, position):
        self.calls.append(f"setPosition({int(position)})")

    def state(self):
        return QMediaPlayer.StoppedState

    def position(self):
        return self._position

    def duration(self):
        return self._duration


class _FakePausedPlayer(_FakePlayer):
    """A loaded player that reports Paused whatever it is really doing."""

    def state(self):
        return QMediaPlayer.PausedState


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
        if not (cls.clip and os.path.exists(cls.clip)):
            return
        # WMF lets go of the file only once the players are really deleted.
        deadline = time.monotonic() + 3
        while True:
            cls.app.sendPostedEvents(None, QEvent.DeferredDelete)
            cls.app.processEvents()
            try:
                os.remove(cls.clip)
                return
            except PermissionError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)

    def _shown_widget(self):
        """A widget that was really shown (WMF builds a presenter); deleted at the end."""
        widget = MediaPlayerWidget(settings={})
        widget.move(-7000, -7000)   # shown for real, but never on the desktop

        def dispose():
            try:
                widget.shutdown()
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass

        self.addCleanup(dispose)
        return widget

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

    def test_loading_a_real_clip_ends_paused_at_the_start_with_audio_restored(self):
        # The first-frame prime against the real backend: play, one tick, pause at 0.
        if not self.clip:
            self.skipTest("ffmpeg.exe not available to synthesise a clip")
        widget = self._shown_widget()
        panel = widget.panels[0]
        self.assertTrue(panel.load_media(self.clip))
        deadline = time.monotonic() + 8
        while (
            panel.duration_ms() <= 0 or panel._primed_path != self.clip or panel._priming
        ) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        if panel.duration_ms() <= 0:
            self.skipTest("QMediaPlayer backend reported no duration in the headless session")
        self.assertEqual(panel._primed_path, self.clip)
        self.assertFalse(panel._priming)
        self.assertEqual(panel.player.state(), QMediaPlayer.PausedState)
        self.assertLessEqual(panel.player.position(), 200)
        self.assertFalse(panel.player.isMuted())
        self.assertTrue(panel.placeholder.isHidden())
        # A later seek while paused must not re-prime (no jump back to 0).
        widget.seek_all(800)
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.02)
        self.assertGreater(panel.player.position(), 500)
        # Leaving the tab and coming back nudges the frame back at the same
        # spot: still paused, still near 800, still audible.
        widget.hide()
        self.app.processEvents()
        widget.show()
        deadline = time.monotonic() + 4
        started = False
        while time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
            started = started or panel._priming
            if started and not panel._priming:
                break
        self.assertTrue(started, "re-show did not nudge the paused panel")
        self.assertFalse(panel._priming)
        self.assertEqual(panel.player.state(), QMediaPlayer.PausedState)
        # The closing setPosition() is asynchronous in Media Foundation; give
        # it a moment to land before reading the position back.
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and abs(panel.player.position() - 800) > 250:
            self.app.processEvents()
            time.sleep(0.02)
        self.assertLessEqual(abs(panel.player.position() - 800), 250)
        self.assertFalse(panel.player.isMuted())


if __name__ == "__main__":
    unittest.main()
