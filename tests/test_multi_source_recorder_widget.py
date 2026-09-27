import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from PyQt5.QtCore import QEvent, QProcess, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWIDGETSIZE_MAX,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from conversion.recording_sources import DeviceScan
from ui import theme
from ui.multi_source_recorder_widget import MultiSourceRecorderWidget, ScreenCaptureSettingsDialog, VideoSettingsDialog


class MultiSourceRecorderWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Anything top-level that exists now belongs to an earlier module and
        # is not this test's to destroy.
        self._pre_existing = list(self.app.topLevelWidgets())

    def _widget(self):
        return MultiSourceRecorderWidget(
            directshow_devices=["Camera A"],
            auto_preview=False,
            load_saved_settings=False,
        )

    def tearDown(self):
        """Destroy the windows this test created, for real.

        Every MultiSourceRecorderWidget arms a 100ms preview render timer in
        its constructor, and most tests here never call shutdown(). Left
        alone, 152 tests pile up ~3,900 hidden top-level widgets and ~19,000
        widgets in total under the session-long QApplication -- at which point
        constructing a full VideoConverterApp in a *later* module aborts the
        interpreter with STATUS_STACK_BUFFER_OVERRUN (0xC0000409), blaming a
        test that did nothing wrong.

        This used to call deleteLater() followed by processEvents(), which
        looks right and deletes nothing: processEvents() explicitly excludes
        DeferredDelete events. sendPostedEvents(None, DeferredDelete) is what
        actually runs them -- and, unlike processEvents(), it does not fire the
        preview timers of widgets still alive from another test.

        Each widget's own shutdown() runs first, so its timers are stopped and
        any preview ffmpeg is killed rather than being destroyed underneath a
        running QProcess. Only top-levels with no parent *widget* are touched:
        `topLevelWidgets()` also lists child windows (a QComboBox popup, a
        QMenu) that are destroyed with their owner anyway. `parentWidget()`
        rather than `parent()`, because a widget parented to one of this
        file's fake QObject containers is still a top-level window.
        """
        stale = [w for w in self.app.topLevelWidgets()
                 if w not in self._pre_existing and w.parentWidget() is None]
        for widget in stale:
            try:
                if hasattr(widget, "shutdown"):
                    # Stops the three timers and kills any preview ffmpeg.
                    # Non-blocking, unlike VideoConverterApp.shutdown().
                    widget.shutdown()
                widget.deleteLater()
            except RuntimeError:  # the wrapped C++ object is already gone
                pass
            except Exception:
                # A test may have patched a collaborator out from under
                # shutdown(); the widget still has to be destroyed.
                try:
                    widget.deleteLater()
                except RuntimeError:
                    pass
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_uses_single_video_settings_button_instead_of_per_row_configure_buttons(self):
        widget = MultiSourceRecorderWidget()

        button_texts = [button.text() for button in widget.findChildren(QPushButton)]

        self.assertNotIn("Configure", button_texts)
        self.assertNotIn("Video Settings...", button_texts)
        self.assertEqual(widget.source_config_buttons, [])

    def test_double_clicking_video_name_opens_video_settings(self):
        widget = MultiSourceRecorderWidget()

        self.assertTrue(callable(widget.video_name_edits[0].mouseDoubleClickEvent))

    def test_audio_discovery_populates_all_row_combos(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        widget._apply_device_scan(DeviceScan([], ["Microphone A", "Microphone B"], True))

        for row in widget.source_rows:
            self.assertEqual(
                [row[7].itemText(index) for index in range(row[7].count())],
                ["No Audio", "Microphone A", "Microphone B"],
            )

    def test_stored_missing_audio_device_is_displayed_and_preserved(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        settings = widget.capture_recorder_settings()
        settings["channels"][0]["audio_device"] = "Lab Microphone"

        widget.apply_recorder_settings(settings, refresh_previews=False)
        widget._apply_device_scan(DeviceScan([], ["Microphone A"], True))

        combo = widget.source_rows[0][7]
        self.assertEqual(combo.currentText(), "Lab Microphone (not found)")
        self.assertEqual(combo.currentData(), "Lab Microphone")
        self.assertEqual(
            widget.capture_recorder_settings()["channels"][0]["audio_device"],
            "Lab Microphone",
        )

    def test_widget_starts_device_discovery_on_creation(self):
        started = []
        with patch.object(
            MultiSourceRecorderWidget,
            "start_device_discovery",
            lambda self, force=False: started.append(force),
        ):
            MultiSourceRecorderWidget(auto_preview=False)

        self.assertEqual(started, [False])

    def test_discovery_result_is_ignored_after_widget_is_destroyed(self):
        with patch.object(
            MultiSourceRecorderWidget,
            "start_device_discovery",
            lambda self, force=False: None,
        ):
            widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

        widget._deliver_device_scan(DeviceScan(["Camera A"], ["Microphone A"], True))

    def _widget_with_scan(self, scans):
        """A widget whose ffmpeg listing is replaced by `scans` (popped per call), run inline."""
        calls = []

        def fake_scan(_ffmpeg):
            calls.append(_ffmpeg)
            return scans.pop(0)

        widget = self._inline_widget()
        patcher = patch("ui.multi_source_recorder_widget.discover_directshow_devices", fake_scan)
        patcher.start()
        self.addCleanup(patcher.stop)
        return widget, calls

    def _inline_widget(self):
        """A widget whose background scans run inline (the construction scan included)."""
        with patch.object(MultiSourceRecorderWidget, "_run_in_background", staticmethod(lambda fn: fn())):
            widget = MultiSourceRecorderWidget(
                directshow_devices=[], auto_preview=False, load_saved_settings=False
            )
        widget._run_in_background = lambda fn: fn()
        widget.last_device_scan_at = None  # forget the construction scan
        return widget

    def test_device_discovery_runs_once_off_thread_and_fills_both_lists(self):
        widget, calls = self._widget_with_scan(
            [DeviceScan(["Camera A", "Camera B"], ["Microphone A"], True)]
        )

        self.assertTrue(widget.start_device_discovery(force=True))
        self.app.processEvents()

        self.assertEqual(len(calls), 1)
        self.assertEqual(widget.directshow_devices, ["Camera A", "Camera B"])
        self.assertEqual(widget.directshow_audio_devices, ["Microphone A"])
        self.assertFalse(widget.device_discovery_running)
        combo = widget.source_rows[0][7]
        self.assertEqual(
            [combo.itemText(i) for i in range(combo.count())],
            ["No Audio", "Microphone A"],
        )

    def test_failed_scan_keeps_the_lists_we_already_had(self):
        widget, _calls = self._widget_with_scan([DeviceScan([], [], False)])
        widget.directshow_devices = ["Camera A"]
        widget.directshow_audio_devices = ["Microphone A"]

        widget.start_device_discovery(force=True)
        self.app.processEvents()

        self.assertEqual(widget.directshow_devices, ["Camera A"])
        self.assertEqual(widget.directshow_audio_devices, ["Microphone A"])
        self.assertFalse(widget.last_device_scan_ok)
        self.assertFalse(widget.device_discovery_running)

    def test_fresh_results_are_reused_and_force_rescans(self):
        widget, calls = self._widget_with_scan(
            [DeviceScan(["Camera A"], [], True), DeviceScan(["Camera B"], [], True)]
        )
        widget.start_device_discovery(force=True)
        self.app.processEvents()
        self.assertFalse(widget.start_device_discovery())  # fresh: no second scan
        self.assertEqual(len(calls), 1)

        self.assertTrue(widget.start_device_discovery(force=True))
        self.app.processEvents()
        self.assertEqual(len(calls), 2)
        self.assertEqual(widget.directshow_devices, ["Camera B"])

    def test_a_scan_that_raises_still_clears_the_running_flag(self):
        widget = self._inline_widget()

        def boom(_ffmpeg):
            raise RuntimeError("ffmpeg exploded")

        with patch("ui.multi_source_recorder_widget.discover_directshow_devices", boom):
            widget.start_device_discovery(force=True)
            self.app.processEvents()

        self.assertFalse(widget.device_discovery_running)
        self.assertFalse(widget.last_device_scan_ok)

    def test_populating_a_source_row_never_blocks_on_a_scan(self):
        widget, calls = self._widget_with_scan([DeviceScan(["Camera A"], [], True)])
        pending = []
        widget._run_in_background = pending.append  # hold the scan, like a slow ffmpeg
        type_combo, source_edit = widget.source_rows[0][2], widget.source_rows[0][3]
        with patch.object(widget, "discover_directshow_devices", side_effect=AssertionError("blocking scan")):
            type_combo.setCurrentIndex(type_combo.findData("directshow"))
            widget.populate_directshow_devices(source_edit)
        # Nothing to offer yet, one scan queued, and the UI never waited for it.
        self.assertEqual(source_edit.options(), [])
        self.assertEqual(len(pending), 1)
        pending[0]()
        self.app.processEvents()
        # The scan landed: the row offers the camera without filling it in
        # behind the user's back.
        self.assertEqual(len(calls), 1)
        self.assertEqual(source_edit.options(), ["Camera A"])
        self.assertEqual(source_edit.text(), "")

    def test_shutdown_terminates_device_probes(self):
        widget = self._widget()
        with patch("ui.multi_source_recorder_widget.terminate_device_probes") as terminate:
            widget.shutdown()
        terminate.assert_called_once()

    def test_selecting_usb_directshow_updates_preview_guidance(self):
        # Picking the type offers the known cameras but does not switch one on;
        # "Opening preview" only appears once the user picks a camera name.
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False)
        row = widget.source_rows[0]
        source_type = row[2]
        source = row[3]
        index = source_type.findData("directshow")

        source_type.setCurrentIndex(index)

        self.assertIn("Configure the source", widget.preview_boxes[0].text())
        self.assertIn("Windows camera name", source.placeholderText())

        source.setCurrentText("Camera A")
        widget.refresh_previews_from_sources()  # what Video Settings > OK does

        self.assertIn("Opening preview", widget.preview_boxes[0].text())

    def test_selecting_usb_directshow_populates_detected_camera_names(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        source_type = row[2]
        source = row[3]

        source_type.setCurrentIndex(source_type.findData("directshow"))

        # Offered in the drop-down, never filled in on the user's behalf: a
        # camera the user did not choose must not come on.
        self.assertEqual(source.text(), "")
        self.assertIn("HD Pro Webcam C920", [source.itemText(i) for i in range(source.count())])

    def test_selecting_usb_directshow_marks_preview_as_opening(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        source_type = widget.source_rows[0][2]
        source = widget.source_rows[0][3]

        source_type.setCurrentIndex(source_type.findData("directshow"))
        source.setCurrentText("HD Pro Webcam C920")
        widget.refresh_previews_from_sources()

        self.assertIn("HD Pro Webcam C920", widget.preview_boxes[0].text())

    def test_widget_size_hint_stays_compact_for_original_window(self):
        widget = MultiSourceRecorderWidget()

        self.assertLessEqual(widget.sizeHint().width(), 700)
        self.assertLessEqual(widget.sizeHint().height(), 460)

    def test_internal_record_controls_are_hidden_for_global_start_button(self):
        widget = MultiSourceRecorderWidget()

        self.assertTrue(widget.start_btn.isHidden())
        self.assertTrue(widget.stop_btn.isHidden())
        self.assertTrue(widget.status_label.isHidden())

    def test_output_folder_browse_is_compact_and_double_clickable(self):
        widget = MultiSourceRecorderWidget()

        self.assertTrue(widget.browse_output_button.isHidden())
        self.assertTrue(callable(widget.output_folder_edit.mouseDoubleClickEvent))

    def test_recording_forms_stay_top_aligned_and_compact(self):
        widget = MultiSourceRecorderWidget()

        self.assertEqual(widget.source_group.sizePolicy().verticalPolicy(), QSizePolicy.Fixed)
        self.assertEqual(widget.output_group.sizePolicy().verticalPolicy(), QSizePolicy.Fixed)
        self.assertTrue(widget.output_form.labelAlignment() & Qt.AlignRight)

    def test_main_recording_properties_headers_match_media_recorder_layout(self):
        widget = MultiSourceRecorderWidget()

        self.assertEqual(
            widget.recording_property_headers,
            ["Nr", "Use", "Video name", "Audio name", "Mute", "Volume"],
        )

    def test_video_settings_link_opens_video_settings(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        calls = []
        widget.open_video_settings = lambda: calls.append("opened")

        widget.video_settings_link.click()

        self.assertEqual(calls, ["opened"])
        self.assertEqual(widget.video_settings_link.text(), "Video Settings")

    def test_main_recorder_supports_four_preview_panes(self):
        widget = MultiSourceRecorderWidget()

        self.assertEqual(len(widget.preview_boxes), 4)
        self.assertEqual(len(widget.ptz_overlay_buttons), 4)

    def test_first_recording_row_can_be_unchecked_like_the_others(self):
        # "Unassign" and "uncheck" both have to mean nothing shows -- a saved
        # screen-capture source on row 1 must not be pinned on for ever.
        widget = MultiSourceRecorderWidget()
        first_enabled = widget.source_rows[0][0]
        self.assertTrue(first_enabled.isEnabled())

        first_enabled.setChecked(False)

        self.assertFalse(first_enabled.isChecked())
        self.assertTrue(widget.preview_boxes[0].isHidden())

    def test_video_settings_can_disable_the_first_row(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        first_enabled = dialog.dialog_rows[0][0]
        self.assertTrue(first_enabled.isEnabled())

        dialog.dialog_rows[0][3].setCurrentText("No source selected...")
        first_enabled.setChecked(False)
        dialog.apply_to_sources()

        self.assertFalse(first_enabled.isChecked())
        self.assertFalse(widget.source_rows[0][0].isChecked())

    def test_start_is_disabled_with_a_hint_when_no_row_is_enabled(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        for row in widget.source_rows:
            row[0].setChecked(False)

        self.assertFalse(widget.start_btn.isEnabled())
        self.assertEqual(widget.status_label.text(), "Enable at least one source")

        widget.source_rows[1][0].setChecked(True)

        self.assertTrue(widget.start_btn.isEnabled())
        self.assertEqual(widget.status_label.text(), "Not recording")

    def test_empty_source_list_keeps_a_black_placeholder_tile_in_the_grid(self):
        # Unticking every row must not collapse the video area and shove the
        # groups below it upwards -- one blank tile stays put with a hint.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.resize(900, 600)
        widget.show()
        QApplication.processEvents()
        groups_y_before = widget.groups_host.y()

        for row in widget.source_rows:
            row[0].setChecked(False)
        QApplication.processEvents()

        self.assertTrue(all(tile.isHidden() for tile in widget.preview_boxes))
        self.assertFalse(widget.no_source_tile.isHidden())
        self.assertEqual(widget.no_source_tile.text(), "No source enabled\nTick Use on a source to preview it")
        self.assertEqual(widget.preview_grid.getItemPosition(0), (0, 0, 1, 2))
        self.assertEqual(widget.preview_grid.count(), 1)
        self.assertEqual(widget.groups_host.y(), groups_y_before)

        widget.source_rows[1][0].setChecked(True)
        QApplication.processEvents()

        self.assertTrue(widget.no_source_tile.isHidden())
        self.assertFalse(widget.preview_boxes[1].isHidden())
        self.assertEqual(widget.preview_grid.count(), 1)
        widget.close()

    def test_preview_grid_uses_two_by_two_layout_for_four_sources(self):
        widget = MultiSourceRecorderWidget()
        for row in widget.source_rows:
            row[0].setChecked(True)
        widget.update_preview_panel_visibility()

        positions = [widget.preview_grid.getItemPosition(index)[:2] for index in range(4)]

        self.assertEqual(positions, [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_preview_panels_follow_checked_recording_rows(self):
        widget = MultiSourceRecorderWidget()
        for row in widget.source_rows:
            row[0].setChecked(False)
        widget.source_rows[0][0].setChecked(True)
        widget.source_rows[2][0].setChecked(True)

        widget.update_preview_panel_visibility()

        self.assertFalse(widget.preview_boxes[0].isHidden())
        self.assertTrue(widget.preview_boxes[1].isHidden())
        self.assertFalse(widget.preview_boxes[2].isHidden())
        self.assertTrue(widget.preview_boxes[3].isHidden())
        self.assertEqual(widget.preview_grid.getItemPosition(0)[:2], (0, 0))
        self.assertEqual(widget.preview_grid.getItemPosition(1)[:2], (0, 1))

    def test_three_checked_preview_panels_put_third_panel_on_second_row(self):
        widget = MultiSourceRecorderWidget()
        for row in widget.source_rows:
            row[0].setChecked(False)
        for index in (0, 1, 2):
            widget.source_rows[index][0].setChecked(True)

        widget.update_preview_panel_visibility()

        self.assertEqual(widget.preview_grid.getItemPosition(0), (0, 0, 1, 1))
        self.assertEqual(widget.preview_grid.getItemPosition(1), (0, 1, 1, 1))
        self.assertEqual(widget.preview_grid.getItemPosition(2), (1, 0, 1, 2))

    def test_preview_panes_ignore_pixmap_size_hints_to_prevent_layout_growth(self):
        widget = MultiSourceRecorderWidget()

        self.assertEqual(widget.preview_boxes[0].sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
        self.assertEqual(widget.preview_boxes[1].sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)

    def test_main_recorder_exposes_recording_log_without_always_showing_log_box(self):
        widget = MultiSourceRecorderWidget()

        self.assertEqual(widget.findChildren(QPlainTextEdit), [])
        self.assertTrue(hasattr(widget, "recording_log_link"))
        self.assertEqual(widget.recording_log_link.text(), "Show recording log")

    def test_show_recording_log_dialog_contains_ffmpeg_output(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.log_lines = ["[Video_1] ffmpeg command", "[Video_1] muxer error"]

        dialog = widget.build_recording_log_dialog()
        log_edit = dialog.findChild(QPlainTextEdit)

        self.assertIsNotNone(log_edit)
        self.assertIn("muxer error", log_edit.toPlainText())

    def test_video_settings_dialog_contains_output_and_timer_controls(self):
        widget = MultiSourceRecorderWidget()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertTrue(hasattr(dialog, "output_quality_combo"))
        self.assertTrue(hasattr(dialog, "output_mode_combo"))
        self.assertFalse(hasattr(dialog, "time_format_combo"))
        self.assertFalse(hasattr(dialog, "decimals_combo"))
        self.assertTrue(hasattr(dialog, "preset_combo"))
        self.assertEqual(len(dialog.dialog_rows), len(widget.source_rows))

    def test_video_settings_binds_maximum_time_to_timer(self):
        widget = self._widget()
        widget.duration_edit.setText("00:10:00")
        dialog = VideoSettingsDialog(
            widget.source_rows,
            widget.output_controls(),
            widget,
            widget.button_style,
        )

        self.assertTrue(dialog.maximum_time_check.isChecked())
        self.assertEqual(dialog.maximum_time_edit.text(), "00:10:00")
        dialog.maximum_time_edit.setText("00:05:00")
        dialog.apply_to_sources()
        self.assertEqual(widget.duration_edit.text(), "00:05:00")

        dialog.maximum_time_check.setChecked(False)
        dialog.apply_to_sources()
        self.assertEqual(widget.duration_edit.text(), "")

    def test_output_quality_round_trips_through_settings_and_commands(self):
        widget = self._widget()
        dialog = VideoSettingsDialog(
            widget.source_rows,
            widget.output_controls(),
            widget,
            widget.button_style,
        )

        dialog.output_quality_combo.setCurrentText("High")
        dialog.apply_to_sources()

        self.assertEqual(widget.output_quality, "High")
        self.assertEqual(widget.capture_recorder_settings()["output"]["quality"], "High")
        widget.codec_combo.setCurrentText("h264")
        command = widget.build_recording_command(
            "ffmpeg.exe",
            "rtsp://camera/stream",
            "out.mp4",
        )
        self.assertEqual(command[command.index("-crf") + 1], "16")

        widget.apply_recorder_settings(
            {"output": {"quality": "Compact"}},
            refresh_previews=False,
        )
        self.assertEqual(widget.output_quality, "Compact")

    def test_video_settings_dialog_uses_compact_columns_and_preset_buttons(self):
        widget = MultiSourceRecorderWidget()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        (_row_enabled, row_label, _row_type, _row_device, _row_frame_rate,
         _row_resolution, row_audio_name, _row_audio_device, _row_offset) = dialog.dialog_rows[0]

        self.assertLessEqual(row_label.maximumWidth(), 82)
        self.assertLessEqual(row_audio_name.maximumWidth(), 82)
        self.assertIsInstance(dialog.camera_settings_buttons[0], QToolButton)
        self.assertLessEqual(dialog.camera_settings_buttons[0].maximumWidth(), 20)
        self.assertLessEqual(dialog.camera_settings_buttons[0].sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)
        self.assertLessEqual(dialog.preset_load_button.maximumWidth(), 48)
        self.assertLessEqual(dialog.preset_set_button.maximumWidth(), 38)
        self.assertIn("text-decoration: underline", dialog.preset_load_button.styleSheet())
        self.assertIn("background: transparent", dialog.preset_set_button.styleSheet())
        self.assertFalse(hasattr(dialog, "preset_save_button"))
        self.assertTrue(hasattr(dialog, "preset_save_as_button"))
        self.assertTrue(hasattr(dialog, "preset_delete_button"))

    def _shown_video_settings_dialog(self, audio_devices):
        widget = MultiSourceRecorderWidget(
            directshow_devices=["Camera A"], auto_preview=False, load_saved_settings=False,
        )
        widget.directshow_audio_devices = list(audio_devices)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        dialog.owner = widget          # the parent must outlive this helper's frame
        # No close() cleanup: conftest reaps the hidden parent (and with it the
        # dialog) before unittest cleanups run, so close() would hit a dead object.
        dialog.move(-7000, -7000)
        dialog.show()
        for _ in range(5):
            self.app.processEvents()
        return dialog

    def test_video_settings_dialog_stays_narrow_with_long_device_names(self):
        short = self._shown_video_settings_dialog(["Microphone A"])
        long = self._shown_video_settings_dialog(
            ["Microphone A (USB Audio Device, Realtek High Definition Audio Endpoint)", "Microphone B"]
        )
        # Long device names elide inside the combo instead of stretching the window.
        self.assertEqual(long.width(), short.width())
        audio_device = long.dialog_rows[0][7]
        self.assertLessEqual(audio_device.width(), VideoSettingsDialog.AUDIO_DEVICE_MAX_W)
        self.assertLessEqual(audio_device.width(), long.dialog_rows[0][3].width())   # video device is the wide one
        dialog = long
        self.assertEqual(audio_device.sizeAdjustPolicy(), QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.assertEqual(audio_device.toolTip(), audio_device.currentText())
        # Save as / Delete are quiet text links, not filled buttons.
        for button in (dialog.preset_save_as_button, dialog.preset_delete_button):
            self.assertTrue(button.property("skipGlobalStyle"))
            self.assertIn("background: transparent", button.styleSheet())
            self.assertLessEqual(button.width(), 70)
        self.assertIn("text-decoration: underline", dialog.preset_save_as_button.styleSheet())

    def test_video_settings_preset_actions_are_left_aligned_bracketed_links(self):
        widget = MultiSourceRecorderWidget()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertTrue(dialog.preset_layout.alignment() & Qt.AlignLeft)
        self.assertEqual(dialog.preset_open_bracket.text(), "[")
        self.assertEqual(dialog.preset_separator.text(), "/")
        self.assertEqual(dialog.preset_close_bracket.text(), "]")
        self.assertLessEqual(dialog.preset_action_layout.spacing(), 2)
        self.assertLessEqual(dialog.preset_action_widget.maximumWidth(), 90)
        self.assertEqual(dialog.preset_action_widget.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)
        self.assertEqual(dialog.preset_action_layout.indexOf(dialog.preset_open_bracket), 0)
        self.assertEqual(dialog.preset_action_layout.indexOf(dialog.preset_load_button), 1)
        self.assertEqual(dialog.preset_action_layout.indexOf(dialog.preset_separator), 2)
        self.assertEqual(dialog.preset_action_layout.indexOf(dialog.preset_set_button), 3)
        self.assertEqual(dialog.preset_action_layout.indexOf(dialog.preset_close_bracket), 4)
        self.assertLessEqual(dialog.preset_combo.maximumWidth(), 120)

    def test_video_settings_dialog_uses_disk_preset_actions(self):
        widget = MultiSourceRecorderWidget()
        widget.list_recorder_presets = lambda: ["Alpha", "Beta"]
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(
            [dialog.preset_combo.itemText(index) for index in range(dialog.preset_combo.count())],
            ["Alpha", "Beta"],
        )
        self.assertTrue(hasattr(dialog, "preset_save_as_button"))
        self.assertTrue(hasattr(dialog, "preset_delete_button"))
        self.assertFalse(dialog.preset_path_edit.isHidden())

    def test_video_settings_dialog_defaults_empty_rows_to_no_source_selected(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(dialog.dialog_rows[1][3].currentText(), "No source selected...")
        dialog.dialog_rows[1][3].setCurrentText("No source selected...")
        dialog.dialog_rows[1][0].setChecked(True)
        dialog.apply_to_sources()

        self.assertEqual(widget.source_rows[1][3].text(), "")
        self.assertFalse(widget.source_rows[1][0].isChecked())

    def test_video_settings_dialog_does_not_apply_refresh_placeholder_as_source(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        row = dialog.dialog_rows[1]
        row[3].setCurrentText("Refresh USB devices...")
        row[0].setChecked(True)

        dialog.apply_to_sources()

        self.assertEqual(widget.source_rows[1][3].text(), "")
        self.assertFalse(widget.source_rows[1][0].isChecked())

    def test_video_settings_dialog_hides_successful_mode_detection_status_text(self):
        widget = MultiSourceRecorderWidget()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.apply_detected_modes(0, [{"resolution": "1280 x 1024", "frame_rate": "30.00"}])

        self.assertTrue(dialog.mode_status_labels[0].isHidden())
        self.assertNotEqual(dialog.mode_status_labels[0].text(), "Modes detected")

    def test_video_settings_dialog_shows_selected_preset_path(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.list_recorder_presets = lambda: ["Custom 3"]
        widget.recorder_preset_path = lambda name: f"C:\\Presets\\{name}.json"

        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        dialog.preset_combo.setCurrentText("Custom 3")
        dialog.update_selected_preset_path()

        self.assertEqual(dialog.preset_path_edit.text(), "C:\\Presets\\Custom 3.json")

    def test_video_settings_dialog_loads_and_saves_selected_preset(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        calls = []
        widget.list_recorder_presets = lambda: ["Default"]
        widget.recorder_preset_path = lambda name: f"C:\\Presets\\{name}.json"
        widget.load_named_recorder_preset = lambda name: (
            calls.append(("load", name)) or widget.capture_recorder_settings()
        )
        widget.save_named_recorder_preset = lambda name: (
            calls.append(("save", name)) or widget.capture_recorder_settings()
        )
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.load_selected_preset()
        dialog.set_selected_preset()

        self.assertEqual(calls, [("load", "Default"), ("save", "Default")])

    def test_video_settings_lists_disk_presets_and_refreshes_on_open(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.list_recorder_presets = lambda: ["Alpha", "Beta"]

        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(
            [dialog.preset_combo.itemText(index) for index in range(dialog.preset_combo.count())],
            ["Alpha", "Beta"],
        )

    def test_video_settings_dirty_marker_ignores_version(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.list_recorder_presets = lambda: ["Alpha"]
        widget.load_named_recorder_preset = lambda name: widget.capture_recorder_settings()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        dialog.loaded_preset_name = "Alpha"
        dialog.loaded_preset_settings = widget.capture_recorder_settings()
        dialog.loaded_preset_settings["version"] = 999

        dialog.update_preset_dirty_marker()
        self.assertEqual(dialog.preset_combo.currentText(), "Alpha")

        widget.source_rows[0][2].setCurrentIndex(1)
        dialog.update_preset_dirty_marker()
        self.assertEqual(dialog.preset_combo.currentText(), "Alpha *")

    def test_delete_selected_preset_confirms_and_refreshes(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.list_recorder_presets = lambda: ["Alpha"]
        deleted = []
        widget.delete_named_recorder_preset = lambda name: deleted.append(name)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        with patch(
            "ui.multi_source_recorder_widget.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ):
            dialog.delete_selected_preset()

        self.assertEqual(deleted, ["Alpha"])

    def test_video_settings_basler_camera_settings_use_pylon_dialog(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        opened_basler = []
        opened_directshow = []
        widget.open_basler_camera_settings = lambda device: opened_basler.append(device)
        widget.open_directshow_camera_settings = lambda device: opened_directshow.append(device)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        row = dialog.dialog_rows[1]
        row[2].setCurrentIndex(row[2].findData("basler_genicam"))
        row[3].setText("Basler GenICam Source")

        with patch("ui.multi_source_recorder_widget.QMessageBox.information") as information:
            dialog.open_camera_settings(1)

        self.assertEqual(opened_basler, ["Basler GenICam Source"])
        self.assertEqual(opened_directshow, [])
        information.assert_not_called()

    def test_open_basler_camera_settings_launches_pylon_viewer_when_available(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.find_pylon_viewer = lambda: r"C:\Program Files\Basler\pylon Viewer\PylonViewerApp.exe"
        started = []

        with patch("ui.multi_source_recorder_widget.QProcess.startDetached", lambda program, args=None: started.append((program, args or [])) or True):
            widget.open_basler_camera_settings("Basler GenICam Source")

        self.assertEqual(started, [(r"C:\Program Files\Basler\pylon Viewer\PylonViewerApp.exe", [])])

    def test_open_basler_camera_settings_explains_when_pylon_viewer_is_missing(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.find_pylon_viewer = lambda: ""

        with patch("ui.multi_source_recorder_widget.QMessageBox.information") as information:
            widget.open_basler_camera_settings("Basler GenICam Source")

        self.assertIn("pylon Viewer", information.call_args.args[2])

    def test_video_settings_dialog_omits_bulky_ptz_controls(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("rtsp_ip"))
        row[3].setText("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")

        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertFalse(hasattr(dialog, "ptz_source_combo"))
        self.assertFalse(hasattr(dialog, "ptz_left_button"))

    def test_preview_resize_recenters_ptz_overlay_button(self):
        # Reproduces the user-reported bug where the PTZ overlay drifted right while
        # the parent window reflowed during recording (the parent "Stop Recording"
        # button became visible) and snapped back when the layout reset. The overlay
        # must follow the preview tile's size changes so it stays roughly centered.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("rtsp_ip"))
        row[3].setText("rtsp://camera/stream")
        # Qt only delivers resizeEvent for widgets that have been realized; show the
        # widget so the resize hook fires the same way it does in the running app.
        widget.show()
        self.app.processEvents()
        widget.update_ptz_overlay_for_row(0)

        preview = widget.preview_boxes[0]
        button = widget.ptz_overlay_buttons[0]

        # Force the preview tile to a new width and let Qt deliver the resize event.
        preview.setFixedWidth(400)
        self.app.processEvents()

        expected_x = (preview.width() - button.width()) // 2
        self.assertLessEqual(abs(button.x() - expected_x), 2)

        # Resetting the width should also recenter the overlay.
        preview.setFixedWidth(200)
        self.app.processEvents()
        expected_x_after = (preview.width() - button.width()) // 2
        self.assertLessEqual(abs(button.x() - expected_x_after), 2)

    def test_preview_ptz_overlay_routes_actions_to_parent(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("rtsp_ip"))
        row[3].setText("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")
        calls = []
        widget.axis_ptz_move = lambda source, move: calls.append((source, move))

        widget.update_ptz_overlay_for_row(0)
        widget.ptz_overlay_buttons[0].send_direction("left")
        widget.ptz_overlay_buttons[0].send_stop()

        self.assertEqual(calls, [
            ("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp", "left"),
            ("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp", "stop"),
        ])

    def test_video_settings_dialog_persists_output_mode(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.output_mode_combo.setCurrentText("Combined grid")
        dialog.apply_to_sources()

        self.assertEqual(widget.output_mode_combo.currentText(), "Combined grid")

    def test_output_mode_combos_offer_only_implemented_modes(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        expected = ["Separate videos", "Combined grid", "Picture-in-picture"]
        self.assertEqual(
            [
                widget.output_mode_combo.itemText(index)
                for index in range(widget.output_mode_combo.count())
            ],
            expected,
        )
        self.assertEqual(
            [
                dialog.output_mode_combo.itemText(index)
                for index in range(dialog.output_mode_combo.count())
            ],
            expected,
        )

    def test_video_settings_apply_refreshes_main_preview_without_closing(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        calls = {"refresh": 0, "save": 0}
        widget.refresh_previews_from_sources = lambda: calls.__setitem__("refresh", calls["refresh"] + 1)
        widget.save_current_recorder_settings = lambda: calls.__setitem__("save", calls["save"] + 1)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.dialog_rows[0][3].setCurrentText("HD Pro Webcam C920")
        dialog.apply_changes()

        self.assertEqual(widget.source_rows[0][3].text(), "HD Pro Webcam C920")
        self.assertEqual(calls, {"refresh": 1, "save": 1})
        self.assertTrue(dialog.isVisible() or dialog.result() == 0)

    def test_video_settings_dialog_has_apply_button(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertIsNotNone(dialog.buttons.button(QDialogButtonBox.Apply))

    def test_capture_recorder_settings_includes_output_and_channels(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        widget.output_folder_edit.setText("C:\\Videos")
        widget.base_name_edit.setText("Task")
        widget.codec_combo.setCurrentText("h264")
        widget.output_mode_combo.setCurrentText("Combined grid")
        widget.duration_edit.setText("00:10:00")
        row = widget.source_rows[0]
        row[0].setChecked(True)
        row[1].setText("Face")
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")
        row[4].setText("Mic")
        row[5].setChecked(True)
        row[6].setCurrentText("75")
        row[8].setCurrentText("25.00")
        row[9].setCurrentText("1280 x 720")

        settings = widget.capture_recorder_settings()

        self.assertEqual(settings["output"]["folder"], "C:\\Videos")
        self.assertEqual(settings["output"]["base_name"], "Task")
        self.assertEqual(settings["output"]["encoding"], "h264")
        self.assertEqual(settings["output"]["mode"], "Combined grid")
        self.assertEqual(settings["timer"]["duration"], "00:10:00")
        self.assertEqual(settings["channels"][0]["video_name"], "Face")
        self.assertEqual(settings["channels"][0]["source_type"], "directshow")
        self.assertEqual(settings["channels"][0]["source"], "HD Pro Webcam C920")
        self.assertTrue(settings["channels"][0]["mute"])

    def test_apply_recorder_settings_restores_output_and_channels(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        calls = []
        widget.update_source_placeholder = lambda combo, edit, index: calls.append((index, combo.currentData(), edit.text()))
        settings = {
            "output": {
                "folder": "C:\\Videos",
                "base_name": "Task",
                "encoding": "h264",
                "mode": "Combined grid",
            },
            "timer": {"duration": "00:10:00"},
            "channels": [{
                "enabled": True,
                "video_name": "Face",
                "source_type": "directshow",
                "source": "HD Pro Webcam C920",
                "audio_name": "Mic",
                "audio_device": "No Audio",
                "mute": True,
                "volume": "75",
                "frame_rate": "25.00",
                "resolution": "1280 x 720",
            }],
        }

        widget.apply_recorder_settings(settings)

        row = widget.source_rows[0]
        self.assertEqual(widget.output_folder_edit.text(), "C:\\Videos")
        self.assertEqual(widget.base_name_edit.text(), "Task")
        self.assertEqual(widget.codec_combo.currentText(), "h264")
        self.assertEqual(widget.output_mode_combo.currentText(), "Combined grid")
        self.assertEqual(widget.duration_edit.text(), "00:10:00")
        self.assertTrue(row[0].isChecked())
        self.assertEqual(row[1].text(), "Face")
        self.assertEqual(row[2].currentData(), "directshow")
        self.assertEqual(row[3].text(), "HD Pro Webcam C920")
        self.assertEqual(row[4].text(), "Mic")
        self.assertTrue(row[5].isChecked())
        self.assertEqual(row[6].currentText(), "75")
        self.assertEqual(calls[0], (0, "directshow", "HD Pro Webcam C920"))

    def test_current_recorder_settings_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "Current Settings.json")
            widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False, load_saved_settings=False)
            widget.recorder_settings_path = lambda: path
            widget.base_name_edit.setText("Task")
            widget.output_mode_combo.setCurrentText("Combined grid")
            row = widget.source_rows[0]
            row[2].setCurrentIndex(row[2].findData("directshow"))
            row[3].setText("HD Pro Webcam C920")

            widget.save_current_recorder_settings()

            restored = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False, load_saved_settings=False)
            restored.recorder_settings_path = lambda: path
            restored.load_current_recorder_settings()

        self.assertEqual(restored.base_name_edit.text(), "Task")
        self.assertEqual(restored.output_mode_combo.currentText(), "Combined grid")
        self.assertEqual(restored.source_rows[0][2].currentData(), "directshow")
        self.assertEqual(restored.source_rows[0][3].text(), "HD Pro Webcam C920")

    def test_combined_output_mode_starts_one_process_for_all_enabled_sources(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        widget.output_mode_combo.setCurrentText("Combined grid")
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("rtsp_ip"))
        row_one[3].setText("rtsp://camera/stream")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("HD Pro Webcam C920")

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            errorOccurred = Signal()
            finished = Signal()
            readyReadStandardOutput = Signal()

            def __init__(self):
                self.started = None

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, arguments):
                self.started = (program, arguments)

        process = FakeProcess()
        widget.create_recording_process = lambda: process

        widget.start_recording()

        self.assertEqual(len(widget.processes), 1)
        self.assertIn("Combined", process.started[1][-1])

    def _two_source_widget(self, mode="Combined grid", auto_preview=False):
        """Row 1: Axis RTSP camera, row 2: USB camera, both 30 fps 1080p."""
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera B"], auto_preview=auto_preview)
        widget.output_mode_combo.setCurrentText(mode)
        row_one, row_two = widget.source_rows[0], widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("rtsp_ip"))
        row_one[3].setText("rtsp://camera/axis-media/media.amp")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("Camera B")
        for row in (row_one, row_two):
            row[8].setCurrentText("30.00")
            row[9].setCurrentText("1920 x 1080")
        return widget

    @staticmethod
    def _capturing_process_factory():
        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.command = None

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, arguments):
                self.command = [program] + list(arguments)

            def state(self):
                return QProcess.Running

        started = []

        def factory():
            process = FakeProcess()
            started.append(process)
            return process

        return factory, started

    def test_combined_grid_opens_usb_sources_with_their_configured_mode(self):
        widget = self._two_source_widget()
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory

        widget.start_recording()

        command = started[0].command
        usb = command.index("video=Camera B")
        self.assertEqual(command[usb - 7:usb], ["-framerate", "30", "-video_size", "1920x1080", "-f", "dshow", "-i"])
        rtsp = [arg for arg in command if arg.startswith("rtsp://")][0]
        self.assertIn("resolution=1920x1080", rtsp)
        self.assertIn("fps=30", rtsp)

    def test_combined_grid_backs_off_requested_options_when_a_camera_rejects_them(self):
        # Separate mode has always retried an Axis camera without ?fps, then without
        # ?resolution; the single combined process had no such ladder and simply
        # failed with "Server returned 400 Bad Request".
        widget = self._two_source_widget()
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory
        scheduled = []
        widget.start_recording()
        self.assertEqual(len(started), 1)

        def fail(process):
            process.recording_error_text = "Error opening input: Server returned 400 Bad Request"
            with patch.object(widget, "_schedule", lambda delay, cb: scheduled.append(cb)):
                widget._process_finished(process, "Combined", 1)
            while scheduled:
                scheduled.pop(0)()

        fail(started[0])
        self.assertEqual(len(started), 2)
        self.assertEqual(widget.status_label.text(), "Recording")
        second = [arg for arg in started[1].command if arg.startswith("rtsp://")][0]
        self.assertIn("resolution=1920x1080", second)
        self.assertNotIn("fps=", second)
        self.assertIn("-video_size", started[1].command)
        self.assertNotIn("-framerate", started[1].command)

        fail(started[1])
        self.assertEqual(len(started), 3)
        third = [arg for arg in started[2].command if arg.startswith("rtsp://")][0]
        self.assertEqual(third, "rtsp://camera/axis-media/media.amp")
        self.assertNotIn("-video_size", started[2].command)

        fail(started[2])
        self.assertEqual(len(started), 3)                 # ladder exhausted
        self.assertIn("failed", widget.status_label.text().lower())
        self.assertIn("safer input format", "\n".join(widget.log_lines))

    def test_combined_grid_does_not_back_off_for_an_unrelated_failure(self):
        widget = self._two_source_widget()
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory
        widget.start_recording()

        started[0].recording_error_text = "Conversion failed!"
        widget._process_finished(started[0], "Combined", 1)

        self.assertEqual(len(started), 1)
        self.assertIn("failed", widget.status_label.text().lower())

    def test_picture_in_picture_is_an_output_mode_that_records_one_composite(self):
        widget = self._two_source_widget(mode="Picture-in-picture")
        self.assertEqual(widget.output_mode_combo.currentText(), "Picture-in-picture")
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory

        widget.start_recording()

        self.assertEqual(len(started), 1)
        command = started[0].command
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("overlay=", graph)
        self.assertNotIn("xstack", graph)
        self.assertIn("Combined", command[-1])

    def test_legacy_picture_in_picture_setting_is_kept(self):
        widget = MultiSourceRecorderWidget(auto_preview=False, load_saved_settings=False)
        widget.apply_recorder_settings({"output": {"mode": "Picture-in-picture"}})
        self.assertEqual(widget.output_mode_combo.currentText(), "Picture-in-picture")

    def test_screen_capture_is_a_source_type_that_records_the_desktop(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[0].setChecked(True)
        self.assertGreaterEqual(row[2].findData("screen"), 0)
        row[2].setCurrentIndex(row[2].findData("screen"))
        self.assertEqual(widget.source_for_row(0), "screen=desktop")
        self.assertIn("Screen", widget.preview_boxes[0].text())
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory

        widget.start_recording()

        command = started[0].command
        self.assertEqual(command[command.index("-f") + 1], "gdigrab")
        self.assertEqual(command[command.index("-i") + 1], "desktop")
        self.assertIn("libx264", command)

    def test_screen_capture_previews_like_a_stream_and_keeps_previewing_while_recording(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        starts = []
        widget.start_stream_preview = lambda row, source, force=False: starts.append((row, source))
        row = widget.source_rows[0]
        row[0].setChecked(True)
        row[2].setCurrentIndex(row[2].findData("screen"))
        widget.update_source_placeholder(row[2], row[3], 0)

        self.assertIn((0, "screen=desktop"), starts)
        self.assertTrue(widget.can_preview_separately_while_recording("screen=desktop"))

    def test_video_settings_dialog_offers_screen_capture_as_a_device(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        try:
            row_device = dialog.dialog_rows[0][3]
            self.assertGreaterEqual(row_device.findData("screen"), 0)
            row_device.setCurrentIndex(row_device.findData("screen"))
            dialog.accept_with_changes()
        finally:
            dialog.deleteLater()

        self.assertEqual(widget.source_rows[0][2].currentData(), "screen")
        self.assertEqual(widget.source_for_row(0), "screen=desktop")

    def test_video_settings_dialog_offers_a_single_screen_capture_entry(self):
        # Displays, windows and regions are chosen in the screen capture settings
        # (the gear), the same way an RTSP camera's address is -- not as a pile
        # of entries in the device list.
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False)
        with patch("ui.multi_source_recorder_widget.list_capture_windows", return_value=["Notepad"]):
            dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        try:
            row_device = dialog.dialog_rows[0][3]
            labels = [row_device.itemText(i) for i in range(row_device.count())]
            screen_labels = [label for label in labels if "creen" in label or label.startswith("Window")]
            self.assertEqual(screen_labels, ["Screen capture"])
            self.assertEqual(row_device.itemData(labels.index("Screen capture")), "screen")
        finally:
            dialog.deleteLater()

    def test_screen_capture_settings_dialog_preselects_and_builds_each_mode(self):
        titles = ["Notepad", "Spreadsheet - Budget"]
        dialog = ScreenCaptureSettingsDialog("", window_titles=titles, monitor_count=2)
        try:
            self.assertTrue(dialog.desktop_radio.isChecked())
            self.assertEqual(dialog.source_value(), "desktop")
            self.assertEqual(dialog.monitor_combo.count(), 2)
            self.assertEqual([dialog.window_combo.itemText(i) for i in range(dialog.window_combo.count())], titles)

            dialog.monitor_radio.setChecked(True)
            dialog.monitor_combo.setCurrentIndex(1)
            self.assertEqual(dialog.source_value(), "monitor=2")

            dialog.window_radio.setChecked(True)
            dialog.window_combo.setCurrentText("Spreadsheet - Budget")
            self.assertEqual(dialog.source_value(), "title=Spreadsheet - Budget")

            dialog.region_radio.setChecked(True)
            dialog.region_x.setValue(-100)
            dialog.region_y.setValue(200)
            dialog.region_width.setValue(801)
            dialog.region_height.setValue(600)
            self.assertEqual(dialog.source_value(), "region=-100,200,800x600")   # even sizes
        finally:
            dialog.deleteLater()

        for value, radio_name, check in (
            ("monitor=2", "monitor_radio", lambda d: d.monitor_combo.currentIndex() == 1),
            ("region=10,20,300x200", "region_radio", lambda d: (d.region_x.value(), d.region_width.value()) == (10, 300)),
            ("title=Notepad", "window_radio", lambda d: d.window_combo.currentText() == "Notepad"),
            ("title=Closed App", "window_radio", lambda d: d.window_combo.currentText() == "Closed App"),
            ("desktop", "desktop_radio", lambda d: True),
        ):
            dialog = ScreenCaptureSettingsDialog(value, window_titles=titles, monitor_count=2)
            try:
                self.assertTrue(getattr(dialog, radio_name).isChecked(), value)
                self.assertTrue(check(dialog), value)
                self.assertEqual(dialog.source_value(), value)
            finally:
                dialog.deleteLater()

    def test_screen_capture_settings_dialog_region_picker_fills_the_fields(self):
        dialog = ScreenCaptureSettingsDialog(
            "", window_titles=[], monitor_count=1, pick_region=lambda: "region=100,200,800x600",
        )
        try:
            dialog.pick_region_button.click()
            self.assertTrue(dialog.region_radio.isChecked())
            self.assertEqual(dialog.source_value(), "region=100,200,800x600")
        finally:
            dialog.deleteLater()

        dialog = ScreenCaptureSettingsDialog("region=1,2,30x40", window_titles=[], monitor_count=1, pick_region=lambda: "")
        try:
            dialog.pick_region_button.click()               # cancelled: fields untouched
            self.assertEqual(dialog.source_value(), "region=1,2,30x40")
        finally:
            dialog.deleteLater()

    def test_region_picker_fades_both_settings_dialogs_while_it_is_open(self):
        # Video Settings and Screen Capture Settings would otherwise sit on top of
        # the very area the user is trying to select.
        parent = QDialog()
        dialog = ScreenCaptureSettingsDialog("", parent=parent, window_titles=[], monitor_count=1)
        seen = {}

        def fake_pick(fade_windows=()):
            seen["windows"] = tuple(fade_windows)
            return "region=0,0,100x100"

        try:
            with patch("ui.multi_source_recorder_widget.pick_screen_region_value", fake_pick):
                dialog.pick_region_button.click()
            self.assertEqual(seen["windows"], (dialog, parent))
            self.assertEqual(dialog.source_value(), "region=0,0,100x100")
        finally:
            dialog.deleteLater()
            parent.deleteLater()

    def test_camera_settings_gear_configures_the_screen_capture_row(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        try:
            row_device = dialog.dialog_rows[0][3]
            row_device.setCurrentIndex(row_device.findText("Screen capture"))

            def choose_monitor(settings_dialog):
                settings_dialog.monitor_radio.setChecked(True)
                settings_dialog.monitor_combo.setCurrentIndex(0)
                return QDialog.Accepted

            with patch.object(ScreenCaptureSettingsDialog, "exec_", choose_monitor):
                dialog.open_camera_settings(0)
            self.assertEqual(row_device.currentText(), "Screen capture (monitor 1, GPU)")
            self.assertEqual(row_device.currentData(), "screen")
            dialog.accept_with_changes()
        finally:
            dialog.deleteLater()

        self.assertEqual(widget.source_rows[0][2].currentData(), "screen")
        self.assertEqual(widget.source_rows[0][3].text(), "monitor=1")
        self.assertEqual(widget.source_for_row(0), "screen=monitor=1")

        # Reopening shows the configured capture, and cancelling the gear keeps it.
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        try:
            row_device = dialog.dialog_rows[0][3]
            self.assertEqual(row_device.currentText(), "Screen capture (monitor 1, GPU)")
            with patch.object(ScreenCaptureSettingsDialog, "exec_", lambda _self: QDialog.Rejected):
                dialog.open_camera_settings(0)
            self.assertEqual(row_device.currentText(), "Screen capture (monitor 1, GPU)")
        finally:
            dialog.deleteLater()

    def test_camera_settings_gear_shows_windows_and_regions_as_screen_captures(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False)
        widget.source_rows[0][2].setCurrentIndex(widget.source_rows[0][2].findData("screen"))
        widget.source_rows[0][3].setText("title=Spreadsheet - Budget")
        widget.source_rows[1][2].setCurrentIndex(widget.source_rows[1][2].findData("screen"))
        widget.source_rows[1][3].setText("region=100,200,800x600")
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        try:
            self.assertEqual(dialog.dialog_rows[0][3].currentText(), "Screen capture (window: Spreadsheet - Budget)")
            self.assertEqual(dialog.dialog_rows[1][3].currentText(), "Screen capture (region 100,200 800x600)")
            dialog.accept_with_changes()
        finally:
            dialog.deleteLater()
        self.assertEqual(widget.source_for_row(0), "screen=title=Spreadsheet - Budget")
        self.assertEqual(widget.source_for_row(1), "screen=region=100,200,800x600")

    def test_screen_recordings_use_the_detected_hardware_encoder_and_cameras_do_not(self):
        widget = self._two_source_widget(mode="Separate videos")
        row_two = widget.source_rows[1]
        row_two[2].setCurrentIndex(row_two[2].findData("screen"))
        row_two[3].setText("desktop")
        widget.hardware_h264_encoder = "h264_nvenc"
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory

        widget.start_recording()

        self.assertEqual(len(started), 2)
        camera, screen = started
        self.assertIn("-i", camera.command)
        self.assertNotIn("h264_nvenc", camera.command)          # RTSP: stream copy / libx264 as before
        self.assertEqual(screen.command[screen.command.index("-c:v") + 1], "h264_nvenc")

    def test_hardware_encoder_failure_falls_back_to_libx264_for_the_same_capture(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[0].setChecked(True)
        row[2].setCurrentIndex(row[2].findData("screen"))
        row[3].setText("monitor=1")
        widget.hardware_h264_encoder = "h264_nvenc"
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory

        widget.start_recording()
        self.assertEqual(started[0].command[started[0].command.index("-c:v") + 1], "h264_nvenc")

        started[0].recording_error_text = "[h264_nvenc @ 0x1] Cannot load nvcuda.dll\nError while opening encoder for output stream #0:0"
        widget._process_finished(started[0], "Video_1", 1)

        self.assertEqual(len(started), 2)
        second = started[1].command
        self.assertEqual(second[second.index("-c:v") + 1], "libx264")
        self.assertIn("ddagrab=output_idx=0", second[second.index("-i") + 1])      # capture unchanged

        started[1].recording_error_text = "Error opening input: Failed to create D3D11 device"
        widget._process_finished(started[1], "Video_1", 1)
        third = started[2].command
        self.assertEqual(third[third.index("-f") + 1], "gdigrab")                      # then the GDI rung
        self.assertEqual(third[third.index("-c:v") + 1], "libx264")
        self.assertTrue(any("software encoder" in line for line in widget.log_lines))

    def test_hardware_encoder_is_probed_with_the_device_scan(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        self.assertEqual(widget.hardware_h264_encoder, "")
        with patch("ui.multi_source_recorder_widget.probe_hardware_h264_encoder", return_value="h264_qsv"):
            widget._run_in_background = lambda fn: fn()
            widget.device_discovery_running = False      # the constructor's scan thread may still be in flight
            self.assertTrue(widget.start_device_discovery(force=True))
            QApplication.processEvents()
        self.assertEqual(widget.hardware_h264_encoder, "h264_qsv")
        self.assertTrue(any("h264_qsv" in line for line in widget.log_lines))

    def test_monitor_capture_falls_back_to_gdi_when_desktop_duplication_fails(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[0].setChecked(True)
        row[2].setCurrentIndex(row[2].findData("screen"))
        row[3].setText("monitor=1")
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory

        widget.start_recording()
        self.assertEqual(len(started), 1)
        self.assertIn("ddagrab=output_idx=0", started[0].command[started[0].command.index("-i") + 1])

        started[0].recording_error_text = "Error opening input: Failed to create D3D11 device"
        widget._process_finished(started[0], "Video_1", 1)

        self.assertEqual(len(started), 2)
        second = started[1].command
        self.assertEqual(second[second.index("-f") + 1], "gdigrab")
        self.assertEqual(second[second.index("-i") + 1], "desktop")
        self.assertEqual(widget.status_label.text(), "Recording")

    def test_combined_monitor_capture_falls_back_to_gdi_at_the_end_of_the_ladder(self):
        widget = self._two_source_widget()
        row_two = widget.source_rows[1]
        row_two[2].setCurrentIndex(row_two[2].findData("screen"))
        row_two[3].setText("monitor=1")
        factory, started = self._capturing_process_factory()
        widget.create_recording_process = factory
        scheduled = []
        widget.start_recording()
        self.assertEqual(len(started), 1)
        self.assertTrue(any(arg.startswith("ddagrab=") for arg in started[0].command))

        def fail(process):
            process.recording_error_text = "Error opening input: Failed to create D3D11 device"
            with patch.object(widget, "_schedule", lambda delay, cb: scheduled.append(cb)):
                widget._process_finished(process, "Combined", 1)
            while scheduled:
                scheduled.pop(0)()

        fail(started[0])
        fail(started[1])
        self.assertEqual(len(started), 3)
        self.assertFalse(any(arg.startswith("ddagrab=") for arg in started[2].command))
        self.assertIn("desktop", started[2].command)
        self.assertIn("gdigrab", started[2].command)

    def test_presets_naming_a_licensed_capture_filter_use_the_built_in_screen_source(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False, load_saved_settings=False)
        widget.apply_recorder_settings({
            "channels": [
                {"enabled": True, "source_type": "directshow", "source": "Camera A"},
                {"enabled": False, "source_type": "directshow", "source": "Medialooks Screen Capture"},
            ],
        })

        self.assertEqual(widget.source_rows[0][2].currentData(), "directshow")
        self.assertEqual(widget.source_for_row(0), "video=Camera A")
        self.assertEqual(widget.source_rows[1][2].currentData(), "screen")
        self.assertEqual(widget.source_for_row(1), "screen=desktop")
        self.assertTrue(any("Medialooks Screen Capture" in line and "screen capture" in line.lower() for line in widget.log_lines))

    def test_screen_hint_mentions_the_monitor_option(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("screen"))
        self.assertIn("monitor=1", row[3].placeholderText())

    def test_combined_output_mode_streams_live_preview_from_recording_process(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920", "OBS Virtual Camera"], auto_preview=True)
        widget.start_stream_preview = lambda *_args: None
        widget.start_directshow_preview = lambda *_args: None
        widget.output_mode_combo.setCurrentText("Combined grid")
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("rtsp_ip"))
        row_one[3].setText("rtsp://camera/stream")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("OBS Virtual Camera")

        class Signal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.channel_mode = None
                self.started = None

            def setProcessChannelMode(self, mode):
                self.channel_mode = mode

            def start(self, program, arguments):
                self.started = (program, arguments)

        process = FakeProcess()
        widget.create_recording_process = lambda: process

        widget.start_recording()

        self.assertEqual(process.channel_mode, QProcess.SeparateChannels)
        self.assertTrue(process.readyReadStandardOutput.callbacks)
        self.assertTrue(process.readyReadStandardError.callbacks)
        self.assertIn("image2pipe", process.started[1])
        self.assertIn("combined", widget.preview_buffers)

    def test_directshow_separate_output_mode_streams_preview_from_each_recording_process(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920", "OBS Virtual Camera"], auto_preview=True)
        widget.start_stream_preview = lambda *_args: None
        widget.start_directshow_preview = lambda *_args: None
        widget.output_mode_combo.setCurrentText("Separate videos")
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("directshow"))
        row_one[3].setText("HD Pro Webcam C920")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("OBS Virtual Camera")

        class Signal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.channel_mode = None
                self.started = None

            def setProcessChannelMode(self, mode):
                self.channel_mode = mode

            def start(self, program, arguments):
                self.started = (program, arguments)

        processes = []
        widget.create_recording_process = lambda: processes.append(FakeProcess()) or processes[-1]

        widget.start_recording()

        self.assertEqual(len(processes), 2)
        for index, process in enumerate(processes):
            self.assertEqual(process.channel_mode, QProcess.SeparateChannels)
            self.assertTrue(process.readyReadStandardOutput.callbacks)
            self.assertTrue(process.readyReadStandardError.callbacks)
            self.assertIn("image2pipe", process.started[1])
            self.assertIn(index, widget.preview_buffers)

    def test_rtsp_recording_uses_stream_copy_single_process_and_separate_preview(self):
        # RTSP file recording must be the simplest, most reliable form possible: a
        # single FFmpeg process that stream-copies packets straight to the MP4 file.
        # The previous attempts at sharing the input with the preview pipeline (both
        # dual-output stream-copy + tap, and filter_complex split=2 + libx264) ended
        # up either freezing the preview or failing to produce an MP4 at all on some
        # cameras. The reliable fallback is to leave the existing separate preview
        # process alive instead, even though it costs a second client connection.
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=True)
        stream_preview_calls = []
        widget.start_stream_preview = lambda row, source, force_restart=False: stream_preview_calls.append((row, source, force_restart))
        widget.start_directshow_preview = lambda *_args: None
        widget.output_mode_combo.setCurrentText("Separate videos")
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("rtsp_ip"))
        row_one[3].setText("rtsp://camera/stream")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("HD Pro Webcam C920")

        class Signal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.channel_mode = None
                self.started = None

            def setProcessChannelMode(self, mode):
                self.channel_mode = mode

            def start(self, program, arguments):
                self.started = (program, arguments)

        processes = []
        widget.create_recording_process = lambda: processes.append(FakeProcess()) or processes[-1]

        widget.start_recording()

        self.assertEqual(len(processes), 2)
        # RTSP: stream copy, no preview pipe in the recording command.
        self.assertNotIn("image2pipe", processes[0].started[1])
        self.assertEqual(processes[0].channel_mode, QProcess.MergedChannels)
        # DirectShow: still uses the filter_complex split path with preview pipe.
        self.assertIn("image2pipe", processes[1].started[1])
        self.assertEqual(processes[1].channel_mode, QProcess.SeparateChannels)
        # A separate preview process is (re)started for the RTSP row so the user sees
        # frames during recording.
        self.assertEqual(stream_preview_calls, [(0, "rtsp://camera/stream", False)])

    def test_recording_applies_row_resolution_and_frame_rate_to_commands(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        widget.output_mode_combo.setCurrentText("Separate videos")
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("directshow"))
        row_one[3].setText("HD Pro Webcam C920")
        row_one[8].setCurrentText("30.00")
        row_one[9].setCurrentText("1920 x 1080")
        row_two[2].setCurrentIndex(row_two[2].findData("rtsp_ip"))
        row_two[3].setText("rtsp://root:pw@192.168.200.4:554/axis-media/media.amp")
        row_two[8].setCurrentText("30.00")
        row_two[9].setCurrentText("1920 x 1080")

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.started = None

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, arguments):
                self.started = [program] + list(arguments)

        processes = []
        widget.create_recording_process = lambda: processes.append(FakeProcess()) or processes[-1]

        widget.start_recording()

        directshow_command = processes[0].started
        rtsp_command = processes[1].started
        self.assertEqual(directshow_command[directshow_command.index("-framerate") + 1], "30")
        self.assertEqual(directshow_command[directshow_command.index("-video_size") + 1], "1920x1080")
        self.assertIn(
            "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp?resolution=1920x1080&fps=30",
            rtsp_command,
        )

    def test_start_recording_skips_duplicate_physical_sources(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        for index in (0, 2):
            row = widget.source_rows[index]
            row[0].setChecked(True)
            row[2].setCurrentIndex(row[2].findData("directshow"))
            row[3].setText("Basler GenICam Source")
        started = []
        widget._start_recording_processes = lambda ffmpeg, selected, output_folder, timestamp: started.append(selected)

        widget.start_recording()

        self.assertEqual(len(started[0]), 1)
        self.assertTrue(any("duplicate source" in line.lower() for line in widget.log_lines))

    def test_failed_recording_retries_without_requested_input_options_after_directshow_release_delay(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.started = None
                self.channel_mode = None

            def setProcessChannelMode(self, mode):
                self.channel_mode = mode

            def start(self, program, arguments):
                self.started = [program] + list(arguments)

            def state(self):
                return QProcess.Running

        replacements = []
        widget.create_recording_process = lambda: replacements.append(FakeProcess()) or replacements[-1]
        failed = FakeProcess()
        failed.recording_fallback_command = ["ffmpeg.exe", "-hide_banner", "-y", "-f", "dshow", "-i", "video=Basler GenICam Source", "out.mp4"]
        failed.recording_preview_pipe = True
        failed.recording_row_index = 0
        failed.recording_safe_label = "Video_1"
        failed.recording_error_text = "Could not set video options"
        widget.processes = [failed]
        widget.status_label.setText("Recording")
        scheduled = []

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._process_finished(failed, "Video_1", 1)

        self.assertEqual(replacements, [])
        self.assertEqual(len(scheduled), 1)
        self.assertGreaterEqual(scheduled[0][0], 1000)
        scheduled[0][1]()
        self.assertEqual(replacements[0].started, failed.recording_fallback_command)
        self.assertEqual(widget.processes, [replacements[0]])
        self.assertIn("retrying", "\n".join(widget.log_lines).lower())

    def test_axis_rejected_fps_retries_resolution_only_before_auto(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        commands = widget.recording_fallback_commands(
            "ffmpeg.exe",
            "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp",
            "out.mp4",
            preview_pipe=False,
            frame_rate="30.00",
            resolution="1920 x 1080",
        )

        self.assertIn(
            "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp?resolution=1920x1080",
            commands[0],
        )
        self.assertIn(
            "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp",
            commands[1],
        )

    def test_non_preview_fallback_starts_even_after_start_error_status(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.started = None

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, arguments):
                self.started = [program] + list(arguments)

            def state(self):
                return QProcess.Running

        replacements = []
        widget.create_recording_process = lambda: replacements.append(FakeProcess()) or replacements[-1]
        failed = FakeProcess()
        failed.recording_fallback_commands = [
            ["ffmpeg.exe", "-hide_banner", "-y", "-rtsp_transport", "tcp", "-timeout", "5000000", "-i", "rtsp://camera/axis-media/media.amp?resolution=1920x1080", "-c:v", "copy", "-an", "out.mp4"],
            ["ffmpeg.exe", "-hide_banner", "-y", "-rtsp_transport", "tcp", "-timeout", "5000000", "-i", "rtsp://camera/axis-media/media.amp", "-c:v", "copy", "-an", "out.mp4"],
        ]
        failed.recording_preview_pipe = False
        failed.recording_row_index = 0
        failed.recording_safe_label = "Video_1"
        failed.recording_error_text = "Server returned 400 Bad Request"
        widget.processes = [failed]
        widget.status_label.setText("Recording failed - check camera availability")

        widget._process_finished(failed, "Video_1", 1)

        self.assertEqual(replacements[0].started, failed.recording_fallback_commands[0])
        self.assertEqual(widget.status_label.text(), "Recording")

    def test_audio_start_failure_retries_once_without_audio(self):
        import time
        import types

        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Recording")
        replacement_commands = []
        scheduled = []

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, args):
                replacement_commands.append([program] + list(args))

        widget.create_recording_process = FakeProcess
        failed = types.SimpleNamespace(
            recording_error_text=(
                "Could not find audio device with name [Microphone A]"
            ),
            recording_audio_device="Microphone A",
            recording_audio_fallback_command=[
                "ffmpeg.exe",
                "-hide_banner",
                "-y",
                "-i",
                "sample.mp4",
                "-map",
                "0:v",
                "-an",
                "-c:v",
                "copy",
                "out.mp4",
            ],
            recording_audio_retry_attempted=False,
            recording_started_at=time.monotonic(),
            recording_preview_pipe=False,
            recording_row_index=0,
            recording_safe_label="Camera",
            recording_fallback_commands=[],
            recording_retry_delay_ms=0,
            state=lambda: QProcess.NotRunning,
        )
        widget.processes = [failed]

        with patch.object(
            widget,
            "_schedule",
            lambda delay, callback: scheduled.append((delay, callback)),
        ):
            widget._process_finished(failed, "Camera", 1)

        self.assertEqual(len(scheduled), 1)
        scheduled[0][1]()
        self.assertEqual(
            replacement_commands[0],
            failed.recording_audio_fallback_command,
        )
        self.assertIn(
            "audio device 'Microphone A' unavailable, recording video only",
            "\n".join(widget.log_lines),
        )
        self.assertIn("video only", widget.status_label.text().lower())

    def test_non_audio_io_error_does_not_use_audio_fallback(self):
        import time

        widget = MultiSourceRecorderWidget(auto_preview=False)
        process = type(
            "Failed",
            (),
            {
                "recording_audio_fallback_command": [
                    "ffmpeg.exe",
                    "video-only",
                ],
                "recording_audio_device": "Microphone A",
                "recording_audio_retry_attempted": False,
                "recording_started_at": time.monotonic(),
                "recording_error_text": (
                    "I/O error while opening video=Camera A"
                ),
            },
        )()

        self.assertFalse(
            widget._retry_recording_without_audio(process, "Camera")
        )

    def test_late_audio_failure_does_not_restart_recording(self):
        import time

        widget = MultiSourceRecorderWidget(auto_preview=False)
        process = type(
            "Failed",
            (),
            {
                "recording_audio_fallback_command": [
                    "ffmpeg.exe",
                    "video-only",
                ],
                "recording_audio_device": "Microphone A",
                "recording_audio_retry_attempted": False,
                "recording_started_at": time.monotonic() - 10,
                "recording_error_text": "Could not find audio device",
            },
        )()

        self.assertFalse(
            widget._retry_recording_without_audio(process, "Camera")
        )

    def test_start_recording_keeps_existing_rtsp_preview_alive(self):
        # The pre-existing idle preview for an RTSP row must keep running during
        # recording, because the recording process intentionally does not pipe its
        # own preview frames (that broke file recording on Axis cameras). DirectShow
        # rows still get paused because their device cannot be opened twice.
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=True)
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("rtsp_ip"))
        row_one[3].setText("rtsp://camera/stream")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("HD Pro Webcam C920")

        class PreviewProcess:
            def __init__(self):
                self.terminated = False

            def state(self):
                return QProcess.Running

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                return True

            def kill(self):
                pass

        rtsp_preview = PreviewProcess()
        directshow_preview = PreviewProcess()
        widget.preview_processes = {0: rtsp_preview, 1: directshow_preview}
        widget.preview_sources = {
            0: ("stream", "rtsp://camera/stream", widget.preview_source_profile),
            1: ("directshow", "HD Pro Webcam C920", widget.preview_source_profile),
        }
        widget._start_recording_processes = lambda *_args: None

        widget.start_recording()

        self.assertFalse(rtsp_preview.terminated)
        self.assertTrue(directshow_preview.terminated)
        self.assertIn(0, widget.preview_processes)
        self.assertNotIn(1, widget.preview_processes)
        self.assertNotIn(0, widget.preview_paused_rows)
        self.assertIn(1, widget.preview_paused_rows)

    def test_separate_recording_passes_row_audio_controls_to_builder(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        widget.populate_audio_device_combo(row[7], "Microphone A")
        row[6].setCurrentText("50")
        calls = []
        widget.build_recording_command = (
            lambda *args, **kwargs: calls.append(kwargs)
            or ["ffmpeg.exe", "out.mp4"]
        )
        widget.recording_fallback_commands = lambda *args, **kwargs: []

        class FakeProcess:
            def __getattr__(self, _name):
                return type(
                    "Signal",
                    (),
                    {"connect": lambda *_args: None},
                )()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, _program, _args):
                pass

        widget.create_recording_process = FakeProcess
        widget._start_recording_processes(
            "ffmpeg.exe",
            [(0, "Camera", "rtsp://camera/stream", {})],
            "C:\\Temp",
            "stamp",
        )

        self.assertEqual(calls[0]["audio_device"], "Microphone A")
        self.assertFalse(calls[0]["mute"])
        self.assertEqual(calls[0]["volume"], "50")

    def test_combined_grid_uses_first_selected_unmuted_audio_row(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.output_mode_combo.setCurrentText("Combined grid")
        widget.populate_audio_device_combo(
            widget.source_rows[0][7],
            "Muted Microphone",
        )
        widget.source_rows[0][5].setChecked(True)
        widget.populate_audio_device_combo(
            widget.source_rows[1][7],
            "Microphone B",
        )
        captured = []

        with patch(
            "ui.multi_source_recorder_widget.build_combined_grid_record_command",
            lambda *args, **kwargs: captured.append(kwargs)
            or ["ffmpeg.exe", "combined.mp4"],
        ):
            widget.create_recording_process = lambda: type(
                "FakeProcess",
                (),
                {
                    "errorOccurred": type(
                        "Signal",
                        (),
                        {"connect": lambda *_args: None},
                    )(),
                    "finished": type(
                        "Signal",
                        (),
                        {"connect": lambda *_args: None},
                    )(),
                    "readyReadStandardOutput": type(
                        "Signal",
                        (),
                        {"connect": lambda *_args: None},
                    )(),
                    "readyReadStandardError": type(
                        "Signal",
                        (),
                        {"connect": lambda *_args: None},
                    )(),
                    "setProcessChannelMode": lambda self, mode: None,
                    "start": lambda self, program, args: None,
                },
            )()
            selected = [
                (0, "One", "rtsp://camera/one", {}),
                (1, "Two", "rtsp://camera/two", {}),
            ]
            widget._start_recording_processes(
                "ffmpeg.exe",
                selected,
                "C:\\Temp",
                "stamp",
            )

        self.assertEqual(captured[0]["audio_device"], "Microphone B")
        self.assertFalse(captured[0]["mute"])
        self.assertEqual(captured[0]["volume"], "100")
        self.assertIn("Two", "\n".join(widget.log_lines))

    def test_stop_recording_refreshes_idle_previews_without_force_restarting_healthy_streams(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        refreshed = []
        widget.refresh_previews_from_sources = lambda force_restart=False: refreshed.append(force_restart)

        class FakeRecordProcess:
            def state(self):
                return QProcess.NotRunning

        widget.processes = [FakeRecordProcess()]
        widget.status_label.setText("Recording")

        widget.stop_recording()

        self.assertEqual(refreshed, [False])

    def test_stop_recording_does_not_block_waiting_for_ffmpeg_to_finish(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class SlowRecordProcess:
            def __init__(self):
                self.wrote_quit = False
                self.closed_input = False
                self.waited_for_finish = False

            def state(self):
                return QProcess.Running

            def write(self, data):
                self.wrote_quit = data == b"q\n"

            def waitForBytesWritten(self, _timeout):
                return True

            def closeWriteChannel(self):
                self.closed_input = True

            def waitForFinished(self, _timeout):
                self.waited_for_finish = True
                return False

            # stop_recording escalates to terminate() after 1.5s and kill()
            # after 3s. A fake without these looks harmless -- the test itself
            # passes -- but the escalation fires from a timer long after this
            # test has finished, and an AttributeError escaping a Qt slot makes
            # PyQt call qFatal(), aborting the whole run at whatever unrelated
            # test happened to be pumping the event loop.
            def terminate(self):
                self.terminated = True

            def kill(self):
                self.killed = True

        process = SlowRecordProcess()
        widget.processes = [process]

        widget.stop_recording()

        self.assertTrue(process.wrote_quit)
        self.assertTrue(process.closed_input)
        self.assertFalse(process.waited_for_finish)
        self.assertEqual(widget.status_label.text(), "Stopping...")

    def test_stop_recording_sends_quit_to_all_processes_before_waiting(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        events = []

        class RunningProcess:
            def __init__(self, name):
                self.name = name

            def state(self):
                return QProcess.Running

            def write(self, data):
                if data == b"q\n":
                    events.append(("write", self.name))

            def waitForBytesWritten(self, _timeout):
                events.append(("wait", self.name))
                return True

            def closeWriteChannel(self):
                events.append(("close", self.name))

        widget.processes = [RunningProcess("one"), RunningProcess("two"), RunningProcess("three")]

        widget.stop_recording()

        self.assertEqual(events[:3], [("write", "one"), ("write", "two"), ("write", "three")])

    def test_stop_recording_filters_dead_processes_before_requesting_stop(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class DeadProcess:
            def state(self):
                return QProcess.NotRunning

        class RunningProcess:
            def __init__(self):
                self.stop_requested = False

            def state(self):
                return QProcess.Running

            def write(self, data):
                self.stop_requested = data == b"q\n"

            def waitForBytesWritten(self, _timeout):
                return True

            def closeWriteChannel(self):
                pass

        running = RunningProcess()
        widget.processes = [DeadProcess(), running]

        with patch.object(widget, "_schedule", lambda *_args: None):
            widget.stop_recording()

        self.assertEqual(widget.processes, [running])
        self.assertTrue(running.stop_requested)

    def test_refresh_previews_restarts_existing_idle_stream_preview(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("rtsp_ip"))
        row[3].setText("rtsp://camera/stream")

        class Signal:
            def connect(self, _callback):
                pass

        class ExistingProcess:
            def __init__(self):
                self.killed = False

            def state(self):
                return 1

            def kill(self):
                self.killed = True

        starts = []

        class FakeProcess:
            NotRunning = 0
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self, _parent=None):
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()
                self.finished = Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, arguments):
                starts.append((program, arguments))

        existing = ExistingProcess()
        widget.preview_processes[0] = existing
        widget.preview_sources[0] = ("stream", "rtsp://camera/stream")

        with patch("ui.multi_source_recorder_widget.QProcess", FakeProcess):
            widget.refresh_previews_from_sources(force_restart=True)

        self.assertTrue(existing.killed)
        self.assertEqual(len(starts), 1)
        self.assertIn("-fflags", starts[0][1])

    def _stubborn_preview_process(self):
        # ffmpeg.exe has no window, so QProcess.terminate() (WM_CLOSE on
        # Windows) leaves it running with the camera open. Only kill() works.
        class StubbornProcess:
            def __init__(self):
                self.terminated = False
                self.killed = False

            def state(self):
                return QProcess.NotRunning if self.killed else QProcess.Running

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                return self.killed

            def kill(self):
                self.killed = True

        return StubbornProcess()

    def test_unchecking_a_row_kills_a_preview_that_ignores_terminate(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=True)
        row = widget.source_rows[1]  # row 1 can never be unchecked
        widget.start_directshow_preview = lambda *_args, **_kwargs: None  # no real ffmpeg while configuring
        row[0].setChecked(True)
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("Camera A")
        del widget.start_directshow_preview
        process = self._stubborn_preview_process()
        widget.preview_processes[1] = process
        widget.preview_sources[1] = ("directshow", "Camera A", widget.preview_source_profile)

        row[0].setChecked(False)
        widget.refresh_previews_from_sources()

        self.assertTrue(process.killed)
        self.assertNotIn(1, widget.preview_processes)
        self.assertNotIn(1, widget.preview_sources)

    def test_clearing_a_rows_device_stops_its_old_preview(self):
        # Row 1 was previewing the desktop; the user switches it to a camera type
        # with "No source selected..." -> nothing to preview, so the desktop
        # preview must not keep running underneath.
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=True)
        row = widget.source_rows[0]
        row[0].setChecked(True)
        process = self._stubborn_preview_process()
        widget.preview_processes[0] = process
        widget.preview_sources[0] = ("stream", "screen=desktop", widget.preview_source_profile)
        with patch("ui.multi_source_recorder_widget.QProcess.start", lambda *_args, **_kwargs: None):
            row[2].setCurrentIndex(row[2].findData("directshow"))
            row[3].setText("")
            widget.refresh_previews_from_sources()

        self.assertTrue(process.killed)
        self.assertNotIn(0, widget.preview_processes)

    def test_no_source_selected_is_not_replaced_by_the_first_known_camera(self):
        # Video Settings writes "" for "No source selected...". The row must stay
        # empty (and preview nothing) rather than quietly adopting the first
        # camera the last scan found -- that is how a deselected webcam came
        # back on with its light lit.
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=True)
        row = widget.source_rows[0]
        started = []
        widget.start_directshow_preview = lambda _row, device, *_args: started.append(device)

        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("")
        widget.refresh_previews_from_sources()

        self.assertEqual(row[3].text(), "")
        self.assertEqual(row[3].options(), ["Camera A"])
        self.assertEqual([device for device in started if device], [])
        self.assertNotIn(0, widget.preview_processes)

    def test_switching_a_row_to_a_type_without_preview_stops_its_old_preview(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        row = widget.source_rows[0]
        row[0].setChecked(True)
        process = self._stubborn_preview_process()
        widget.preview_processes[0] = process
        widget.preview_sources[0] = ("stream", "screen=desktop", widget.preview_source_profile)
        row[2].setCurrentIndex(row[2].findData("file"))
        row[3].setText(r"C:\Videos\clip.mp4")

        widget.refresh_previews_from_sources()

        self.assertTrue(process.killed)
        self.assertNotIn(0, widget.preview_processes)

    def test_killed_preview_exiting_clears_the_rows_stopping_mark(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        process = self._stubborn_preview_process()
        widget.preview_processes[0] = process
        widget.preview_sources[0] = ("stream", "screen=desktop", widget.preview_source_profile)

        widget.stop_preview_for_row(0)
        self.assertIn(0, widget.preview_stopping_rows)
        widget._preview_finished(0, 0, process)  # the kill lands a moment later

        self.assertNotIn(0, widget.preview_stopping_rows)

    def test_stop_preview_processes_does_not_block_on_terminate(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        process = self._stubborn_preview_process()
        widget.preview_processes[0] = process

        widget.stop_preview_processes()

        self.assertTrue(process.killed)
        self.assertEqual(widget.preview_processes, {})

    def test_combined_output_keeps_each_source_in_its_own_preview_box(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=True)
        widget.start_stream_preview = lambda *_args: None
        widget.start_directshow_preview = lambda *_args: None
        widget.output_mode_combo.setCurrentText("Combined grid")
        row_one = widget.source_rows[0]
        row_two = widget.source_rows[1]
        row_one[0].setChecked(True)
        row_two[0].setChecked(True)
        row_one[2].setCurrentIndex(row_one[2].findData("rtsp_ip"))
        row_one[3].setText("rtsp://camera/stream")
        row_two[2].setCurrentIndex(row_two[2].findData("directshow"))
        row_two[3].setText("HD Pro Webcam C920")
        widget.preview_boxes[1].setPixmap(QPixmap(20, 20))

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            errorOccurred = Signal()
            finished = Signal()
            readyReadStandardOutput = Signal()
            readyReadStandardError = Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, _program, _arguments):
                pass

        widget.create_recording_process = lambda: FakeProcess()

        widget.start_recording()

        self.assertEqual(widget.combined_preview_rows, [0, 1])
        self.assertIn("Opening combined preview", widget.preview_boxes[0].text())
        self.assertIn("Opening combined preview", widget.preview_boxes[1].text())

    def test_combined_preview_uses_side_by_side_crops_for_two_sources(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        first_crop = widget._combined_preview_crop_rect(0, 2, 200, 100)
        second_crop = widget._combined_preview_crop_rect(1, 2, 200, 100)

        self.assertEqual(first_crop, (0, 0, 100, 100))
        self.assertEqual(second_crop, (100, 0, 100, 100))

    def test_video_settings_dialog_headers_match_media_recorder_layout(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(
            dialog.video_settings_headers,
            ["Nr", "Use", "Video name", "Video device", "", "Frame rate", "Resolution", "Audio name", "Audio device", "Sync offset"],
        )
        self.assertIn("HD Pro Webcam C920", [dialog.dialog_rows[0][3].itemText(i) for i in range(dialog.dialog_rows[0][3].count())])

    def test_video_settings_dialog_camera_button_tooltip_names_camera_number(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(dialog.camera_settings_buttons[0].toolTip(), "Camera 1 settings")
        self.assertEqual(dialog.camera_settings_buttons[1].toolTip(), "Camera 2 settings")

    def test_opening_video_settings_from_row_keeps_generic_window_title(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        titles = []

        class FakeDialog:
            def __init__(self, *_args):
                pass

            def setWindowTitle(self, title):
                titles.append(title)

            def exec_(self):
                return 0

        with patch("ui.multi_source_recorder_widget.VideoSettingsDialog", FakeDialog):
            widget.open_video_settings(0)

        self.assertEqual(titles, [])

    def test_video_settings_dialog_does_not_discover_devices_while_opening(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        calls = {"discover": 0}
        widget.discover_directshow_devices = lambda: calls.__setitem__("discover", calls["discover"] + 1) or ["HD Pro Webcam C920", "OBS Virtual Camera"]

        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        options = [dialog.dialog_rows[0][3].itemText(i) for i in range(dialog.dialog_rows[0][3].count())]
        self.assertEqual(calls["discover"], 0)
        self.assertNotIn("HD Pro Webcam C920", options)
        self.assertIn("RTSP/IP Camera", options)

    def test_video_settings_apply_selected_directshow_device_to_source_row(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        dialog.dialog_rows[0][3].setCurrentText("HD Pro Webcam C920")

        dialog.apply_to_sources()

        self.assertEqual(widget.source_rows[0][2].currentData(), "directshow")
        self.assertEqual(widget.source_rows[0][3].text(), "HD Pro Webcam C920")

    def test_video_settings_infers_rtsp_url_when_combo_metadata_is_stale(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        row = dialog.dialog_rows[0]
        row[3].setCurrentText("HD Pro Webcam C920")
        row[3].setText("rtsp://root:root@192.168.200.4:554/axis-media/media.amp")

        dialog.apply_to_sources()

        self.assertEqual(widget.source_rows[0][2].currentData(), "rtsp_ip")
        self.assertEqual(widget.source_rows[0][3].text(), "rtsp://root:root@192.168.200.4:554/axis-media/media.amp")

    def test_video_settings_auto_detects_modes_after_directshow_selection(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        calls = []
        widget.start_directshow_mode_detection = lambda device, callback: calls.append((device, callback))
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.dialog_rows[0][3].setCurrentText("Basler GenICam Source")
        dialog.handle_video_device_choice(dialog.dialog_rows[0][3])

        self.assertEqual(calls[0][0], "Basler GenICam Source")
        calls[0][1]([
            {"resolution": "1280 x 1024", "frame_rate": "30.00"},
            {"resolution": "640 x 480", "frame_rate": "15.00"},
        ])

        resolutions = [dialog.dialog_rows[0][5].itemText(i) for i in range(dialog.dialog_rows[0][5].count())]
        frame_rates = [dialog.dialog_rows[0][4].itemText(i) for i in range(dialog.dialog_rows[0][4].count())]
        self.assertEqual(resolutions[:2], ["1280 x 1024", "640 x 480"])
        self.assertEqual(frame_rates[:2], ["30.00", "15.00"])

    def test_video_settings_defaults_to_auto_for_nonstandard_detected_basler_fps(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.apply_detected_modes(0, [{"resolution": "1280 x 1024", "frame_rate": "40.73"}])

        frame_rate_combo = dialog.dialog_rows[0][4]
        frame_rates = [frame_rate_combo.itemText(i) for i in range(frame_rate_combo.count())]
        self.assertIn("40.73", frame_rates)
        self.assertIn("Auto", frame_rates)
        self.assertEqual(frame_rate_combo.currentText(), "Auto")
        self.assertEqual(dialog.dialog_rows[0][5].currentText(), "1280 x 1024")

    def test_video_settings_mode_detection_uses_cached_modes(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        widget.camera_mode_cache["directshow:Basler GenICam Source"] = [
            {"resolution": "1280 x 1024", "frame_rate": "30.00"}
        ]
        calls = []
        widget.start_directshow_mode_detection = lambda device, callback: calls.append((device, callback))
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.dialog_rows[0][3].setCurrentText("Basler GenICam Source")
        dialog.handle_video_device_choice(dialog.dialog_rows[0][3])

        self.assertEqual(calls, [])
        self.assertEqual(dialog.dialog_rows[0][5].itemText(0), "1280 x 1024")

    def test_directshow_mode_detection_caches_parsed_ffmpeg_output(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        callbacks = []

        class Signal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

        class FakeProcess:
            MergedChannels = QProcess.MergedChannels

            def __init__(self, _parent=None):
                self.finished = Signal()
                self.started = None

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, arguments):
                self.started = [program] + list(arguments)

            def readAllStandardOutput(self):
                return b"[dshow] pixel_format=yuyv422 min s=1280x1024 fps=30 max s=1280x1024 fps=30"

        with patch("ui.multi_source_recorder_widget.QProcess", FakeProcess):
            widget.start_directshow_mode_detection("Basler GenICam Source", lambda modes: callbacks.append(modes))
            process = widget.camera_mode_processes[0]
            process.finished.callback(0, None)

        self.assertEqual(callbacks, [[{"resolution": "1280 x 1024", "frame_rate": "30.00"}]])
        self.assertEqual(widget.camera_mode_cache["directshow:Basler GenICam Source"], callbacks[0])

    def test_video_settings_selecting_camera_auto_enables_that_recording_row(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        widget.source_rows[1][0].setChecked(False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        dialog.dialog_rows[1][3].setCurrentText("HD Pro Webcam C920")

        dialog.apply_to_sources()

        self.assertTrue(widget.source_rows[1][0].isChecked())

    def test_rtsp_camera_settings_auto_enables_that_recording_row(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.source_rows[1][0].setChecked(False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.apply_rtsp_settings_to_row(1, host="192.168.200.4", username="root", password="root", port="554", path="axis-media/media.amp")

        self.assertTrue(dialog.dialog_rows[1][0].isChecked())

    def test_start_recording_logs_configured_rows_that_are_not_enabled(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget._ffmpeg_path = lambda: "ffmpeg.exe"
        widget.release_preview_processes_for_recording = lambda _selected: None
        widget.save_current_recorder_settings = lambda: None
        widget._start_recording_processes = lambda *_args: None
        row_one = widget.source_rows[0]
        row_one[2].setCurrentIndex(row_one[2].findData("directshow"))
        row_one[3].setText("HD Pro Webcam C920")
        row_two = widget.source_rows[1]
        row_two[0].setChecked(False)
        row_two[2].setCurrentIndex(row_two[2].findData("rtsp_ip"))
        row_two[3].setText("rtsp://camera/stream")

        widget.start_recording()

        self.assertTrue(any("Video 2" in line and "Use is unchecked" in line for line in widget.log_lines))

    def test_video_settings_dialog_has_camera_settings_buttons(self):
        widget = MultiSourceRecorderWidget()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(len(dialog.camera_settings_buttons), len(widget.source_rows))
        self.assertEqual(dialog.camera_settings_buttons[0].text(), "")
        self.assertLessEqual(dialog.camera_settings_buttons[0].maximumWidth(), 26)

    def test_single_source_recording_failure_surfaces_source_name_in_status(self):
        # When only one of several recordings fails (typical Axis-vs-webcam case),
        # the user has no log box to consult. The status_label must surface a hint
        # so the operator knows which camera dropped without having to wait for the
        # final aggregate status.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Recording")

        class FailedProcess:
            def state(self):
                return QProcess.NotRunning

        class HealthyProcess:
            def state(self):
                return QProcess.Running

        healthy = HealthyProcess()
        failed = FailedProcess()
        widget.processes = [failed, healthy]

        widget._process_finished(failed, "Axis", 1)

        self.assertIn("Axis", widget.status_label.text())

    def test_single_source_failure_does_not_overwrite_stopping_status(self):
        # During a graceful Stop, the user is already in control of the transition and
        # should keep seeing "Stopping..." until the watchdog or the last finished
        # signal moves them off it. Per-source failures during that window must not
        # flash a confusing error message.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Stopping...")

        class FailedProcess:
            def state(self):
                return QProcess.NotRunning

        class HealthyProcess:
            def state(self):
                return QProcess.Running

        healthy = HealthyProcess()
        failed = FailedProcess()
        widget.processes = [failed, healthy]

        widget._process_finished(failed, "Axis", 1)

        self.assertEqual(widget.status_label.text(), "Stopping...")

    def test_failed_recording_sets_visible_failure_status(self):
        widget = MultiSourceRecorderWidget()

        class FakeProcess:
            def state(self):
                return QProcess.NotRunning

        widget._append_log("[Video_1] Could not run graph")
        widget._process_finished(FakeProcess(), "Video_1", 1)

        self.assertIn("failed", widget.status_label.text().lower())

    def test_process_start_error_sets_visible_failure_status(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Starting recording...")

        class FakeProcess:
            def state(self):
                return QProcess.NotRunning

        widget.processes = [FakeProcess()]
        widget._process_start_error(FakeProcess(), "Video_1")

        self.assertIn("failed", widget.status_label.text().lower())

    def test_process_start_error_does_not_abort_session_when_other_sources_continue(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Recording")

        class FailedProcess:
            recording_fallback_commands = [["ffmpeg.exe", "-i", "fallback", "out.mp4"]]

            def state(self):
                return QProcess.NotRunning

        class RunningProcess:
            def state(self):
                return QProcess.Running

        running = RunningProcess()
        failed = FailedProcess()
        widget.processes = [failed, running]

        widget._process_start_error(failed, "Video_1")

        self.assertEqual(widget.status_label.text(), "Recording")
        self.assertTrue(widget.stop_btn.isEnabled())
        self.assertFalse(widget.start_btn.isEnabled())
        self.assertEqual(widget.processes, [running])

    def test_recording_stops_active_preview_processes_first(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class FakePreviewProcess:
            def __init__(self):
                self.killed = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

        preview = FakePreviewProcess()
        widget.preview_processes[0] = preview

        widget.stop_preview_processes()

        self.assertTrue(preview.killed)

    def test_stopping_previews_kills_instead_of_terminating(self):
        # terminate() is WM_CLOSE on Windows and ffmpeg.exe has no window: a
        # "terminated" preview kept running with the camera light on. Previews
        # write to a pipe and have nothing to flush, so kill() is used directly
        # and nothing blocks on waitForFinished().
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class FakePreviewProcess:
            def __init__(self):
                self.terminated = False
                self.waited = False
                self.killed = False

            def state(self):
                return QProcess.Running

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                self.waited = True
                return False

            def kill(self):
                self.killed = True

        preview = FakePreviewProcess()
        widget.preview_processes[0] = preview

        widget.stop_preview_processes()

        self.assertTrue(preview.killed)
        self.assertFalse(preview.terminated)
        self.assertFalse(preview.waited)

    def test_start_recording_waits_briefly_for_preview_camera_release(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class FakePreviewProcess:
            def __init__(self):
                self.terminated = False
                self.waited = False

            def state(self):
                return QProcess.Running

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                self.waited = True
                return True

            def kill(self):
                pass

        preview = FakePreviewProcess()
        widget.preview_processes[0] = preview

        widget.release_preview_processes_for_recording()

        self.assertTrue(preview.terminated)
        self.assertTrue(preview.waited)

    def test_start_recording_launches_processes_immediately_after_preview_release(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")
        widget.release_preview_processes_for_recording = lambda *_args: None
        started = []
        widget._start_recording_processes = lambda ffmpeg, selected, output_folder, timestamp: started.append(selected)

        widget.start_recording()

        self.assertTrue(started)
        self.assertIsNone(widget.pending_recording_start)

    def test_start_recording_delays_after_releasing_running_directshow_preview(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")
        widget.release_preview_processes_for_recording = lambda *_args: True
        started = []
        widget._start_recording_processes = lambda ffmpeg, selected, output_folder, timestamp: started.append(selected)

        widget.start_recording()

        self.assertEqual(started, [])
        self.assertIsNotNone(widget.pending_recording_start)
        self.assertTrue(widget.record_start_timer.isActive())
        self.assertTrue(widget.record_start_watchdog_timer.isActive())
        self.assertEqual(widget.status_label.text(), "Starting recording...")

    def test_start_recording_uses_longer_release_delay_for_basler_preview(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("Basler GenICam Source")
        widget.release_preview_processes_for_recording = lambda *_args: True
        delays = []
        original_start = widget.record_start_timer.start
        widget.record_start_timer.start = lambda delay: delays.append(delay) or original_start(delay)

        widget.start_recording()

        self.assertEqual(delays, [widget.basler_record_start_delay_ms])

    def test_start_recording_waits_when_selected_directshow_preview_process_was_running(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")

        class RunningPreviewProcess:
            def state(self):
                return QProcess.Running

            def terminate(self):
                pass

            def waitForFinished(self, _timeout):
                return True

            def kill(self):
                pass

        widget.preview_processes[0] = RunningPreviewProcess()
        started = []
        widget._start_recording_processes = lambda ffmpeg, selected, output_folder, timestamp: started.append(selected)

        widget.start_recording()

        self.assertEqual(started, [])
        self.assertTrue(widget.record_start_timer.isActive())

    def test_start_recording_does_not_leave_pending_timer_active(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")
        widget.release_preview_processes_for_recording = lambda *_args: None
        started = []
        widget._start_recording_processes = lambda ffmpeg, selected, output_folder, timestamp: started.append(selected)

        widget.start_recording()

        self.assertTrue(started)
        self.assertIsNone(widget.pending_recording_start)
        self.assertFalse(widget.record_start_timer.isActive())
        self.assertFalse(widget.record_start_watchdog_timer.isActive())

    def test_begin_pending_recording_still_supports_manual_recovery(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        started = []
        widget._start_recording_processes = lambda ffmpeg, selected, output_folder, timestamp: started.append(selected)
        widget.pending_recording_start = ("ffmpeg.exe", [(0, "Video 1", "video=HD Pro Webcam C920")], "C:\\Temp", "stamp")

        widget._begin_pending_recording()

        self.assertTrue(started)
        self.assertIsNone(widget.pending_recording_start)

    def test_pending_recording_start_failure_does_not_leave_starting_status(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.pending_recording_start = ("ffmpeg.exe", [(0, "Video 1", "video=HD Pro Webcam C920")], "C:\\Temp", "stamp")
        widget._start_recording_processes = lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))

        widget._begin_pending_recording()

        self.assertIn("failed", widget.status_label.text().lower())
        self.assertIsNone(widget.pending_recording_start)

    def test_recording_status_is_set_before_ffmpeg_start_returns(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        observed = {}

        class FakeProcess:
            errorOccurred = type("Signal", (), {"connect": lambda self, callback: None})()
            finished = type("Signal", (), {"connect": lambda self, callback: None})()
            readyReadStandardOutput = type("Signal", (), {"connect": lambda self, callback: None})()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, _program, _arguments):
                observed["status_at_start"] = widget.status_label.text()

        widget.create_recording_process = lambda: FakeProcess()

        widget._start_recording_processes("ffmpeg.exe", [(0, "Video 1", "rtsp://camera/stream")], "C:\\Temp", "stamp")

        self.assertEqual(observed["status_at_start"], "Recording")

    def test_stop_recording_clears_pending_start_timer(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.pending_recording_start = ("ffmpeg.exe", [], "C:\\Temp", "stamp")
        widget.record_start_timer.start(1000)
        widget.record_start_watchdog_timer.start(1000)

        widget.stop_recording()

        self.assertIsNone(widget.pending_recording_start)
        self.assertFalse(widget.record_start_timer.isActive())
        self.assertFalse(widget.record_start_watchdog_timer.isActive())

    def test_video_settings_dialog_does_not_block_on_usb_discovery_when_cache_empty(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        calls = {"discover": 0}
        widget.discover_directshow_devices = lambda: calls.__setitem__("discover", calls["discover"] + 1) or ["HD Pro Webcam C920"]

        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(calls["discover"], 0)
        options = [dialog.dialog_rows[0][3].itemText(i) for i in range(dialog.dialog_rows[0][3].count())]
        self.assertIn("Refresh USB devices...", options)

    def test_video_settings_dialog_can_refresh_usb_devices_on_demand(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        calls = {"discover": 0}
        widget.discover_directshow_devices = lambda: calls.__setitem__("discover", calls["discover"] + 1) or ["HD Pro Webcam C920"]
        started = []
        widget.start_device_discovery = lambda force=False: started.append(force) or True
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        dialog.refresh_directshow_devices()
        widget._apply_device_scan(DeviceScan(["HD Pro Webcam C920"], [], True))

        options = [dialog.dialog_rows[0][3].itemText(i) for i in range(dialog.dialog_rows[0][3].count())]
        self.assertEqual(calls["discover"], 0)          # never the blocking path
        self.assertEqual(started[-1], True)             # an explicit refresh always rescans
        self.assertIn("HD Pro Webcam C920", options)

    def test_video_settings_dialog_scans_in_the_background_when_it_opens(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        started = []
        widget.start_device_discovery = lambda force=False: started.append(force) or True

        VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        self.assertEqual(started, [False])  # reuse a fresh listing, scan otherwise

    def test_video_settings_dialog_shows_scan_progress_and_result(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        widget.start_device_discovery = lambda force=False: True
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        widget.device_scan_started.emit()
        self.assertIn("Scanning", dialog.device_scan_status.text())
        self.assertFalse(dialog.refresh_devices_button.isEnabled())

        widget._deliver_device_scan(DeviceScan(["Camera A", "Camera B"], ["Microphone A"], True))
        self.assertEqual(dialog.device_scan_status.text(), "2 cameras, 1 microphone found")
        self.assertTrue(dialog.refresh_devices_button.isEnabled())

        widget._deliver_device_scan(DeviceScan([], [], False))
        self.assertIn("failed", dialog.device_scan_status.text())
        self.assertTrue(dialog.refresh_devices_button.isEnabled())

    def test_refresh_button_is_a_glyph_button_that_rescans_everything(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        started = []
        widget.start_device_discovery = lambda force=False: started.append(force) or True
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        self.assertEqual(dialog.refresh_devices_button.property("glyph"), "refresh")
        self.assertIs(dialog.refresh_devices_button, dialog.refresh_audio_devices_button)
        # The opening scan is in flight: no doubling up until it lands.
        self.assertFalse(dialog.refresh_devices_button.isEnabled())
        widget._deliver_device_scan(DeviceScan([], [], True))
        self.assertTrue(dialog.refresh_devices_button.isEnabled())

        dialog.refresh_devices_button.click()

        self.assertEqual(started, [False, True])

    def test_recorder_links_and_camera_buttons_carry_glyphs_that_follow_the_skin(self):
        widget = self._widget()
        self.assertEqual(widget.video_settings_link.property("glyph"), "settings")
        self.assertEqual(widget.recording_log_link.property("glyph"), "log")
        self.assertFalse(widget.video_settings_link.icon().isNull())
        before = widget.video_settings_link.icon().pixmap(16).toImage()
        with patch.object(theme, "skin", return_value=theme.skin_for_state(locked=True)):
            widget.reskin()
        self.assertNotEqual(widget.video_settings_link.icon().pixmap(16).toImage(), before)

        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        for button in dialog.camera_settings_buttons:
            self.assertEqual(button.property("glyph"), "camera")
            self.assertFalse(button.icon().isNull())

    def test_picking_refresh_in_a_row_combo_rescans_and_keeps_the_previous_choice(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Camera A"], auto_preview=False)
        started = []
        widget.start_device_discovery = lambda force=False: started.append(force) or True
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        combo = dialog.dialog_rows[0][3]
        combo.setCurrentText("Camera A")
        started.clear()

        combo.setCurrentIndex(combo.findData("refresh_directshow"))

        self.assertEqual(started, [True])
        self.assertEqual(combo.currentText(), "Camera A")  # not left on "Refresh USB devices..."

    def test_rtsp_camera_settings_can_fill_axis_rtsp_url(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        row_device = dialog.dialog_rows[0][3]

        dialog.apply_rtsp_settings_to_row(0, host="192.168.1.50", username="root", password="pass", port="554", path="axis-media/media.amp")

        self.assertEqual(row_device.currentText(), "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")

    def test_rtsp_settings_reopen_parses_url_into_ip_field(self):
        widget = MultiSourceRecorderWidget(directshow_devices=[], auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

        fields = dialog.rtsp_settings_from_current_text("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")

        self.assertEqual(fields["host"], "192.168.1.50")
        self.assertEqual(fields["username"], "root")
        self.assertEqual(fields["password"], "pass")
        self.assertEqual(fields["port"], "554")
        self.assertEqual(fields["path"], "axis-media/media.amp")

    def test_rtsp_source_starts_preview_without_stopping_usb_preview(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        calls = []
        widget.start_stream_preview = lambda row, source, *_args: calls.append((row, source))
        widget.start_directshow_preview = lambda row, device, *_args: calls.append((row, device))
        rtsp_type, rtsp_source = widget.source_rows[1][2], widget.source_rows[1][3]
        rtsp_type.setCurrentIndex(rtsp_type.findData("rtsp_ip"))
        rtsp_source.setText("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")

        widget.update_source_placeholder(rtsp_type, rtsp_source, 1)

        self.assertEqual(calls, [(1, "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")])

    def test_rtsp_url_preview_uses_stream_path_even_when_type_metadata_is_stale(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=True)
        calls = []
        widget.start_stream_preview = lambda row, source, *_args: calls.append(("stream", row, source))
        widget.start_directshow_preview = lambda row, device, *_args: calls.append(("directshow", row, device))
        source_type, source_edit = widget.source_rows[0][2], widget.source_rows[0][3]
        source_type.setCurrentIndex(source_type.findData("directshow"))
        calls.clear()
        source_edit.setText("rtsp://root:root@192.168.200.4:554/axis-media/media.amp")

        widget.update_source_placeholder(source_type, source_edit, 0)

        self.assertEqual(calls, [("stream", 0, "rtsp://root:root@192.168.200.4:554/axis-media/media.amp")])

    def test_axis_rtsp_preview_uses_mjpeg_vapix_endpoint_for_lower_latency(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        commands = []

        class FakeProcess:
            NotRunning = QProcess.NotRunning
            Running = QProcess.Running
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self, _parent=None):
                pass

            def setProcessChannelMode(self, _mode):
                pass

            @property
            def readyReadStandardOutput(self):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            @property
            def readyReadStandardError(self):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            @property
            def finished(self):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            def start(self, program, args):
                commands.append([program] + list(args))

        with patch("ui.multi_source_recorder_widget.QProcess", FakeProcess):
            widget.start_stream_preview(1, "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")

        self.assertIn("http://root:pass@192.168.1.50/axis-cgi/mjpg/video.cgi?resolution=480x270&fps=15", commands[0])
        self.assertEqual(
            widget.preview_sources[1],
            ("stream", "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp", widget.preview_source_profile),
        )

    def test_directshow_preview_uses_selected_recording_mode_for_matching_aspect_ratio(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=True)
        row = widget.source_rows[0]
        row[8].setCurrentText("30.00")
        row[9].setCurrentText("1920 x 1080")
        commands = []

        class FakeProcess:
            NotRunning = QProcess.NotRunning
            Running = QProcess.Running
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self, _parent=None):
                pass

            def __getattr__(self, _name):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, args):
                commands.append([program] + list(args))

        with patch("ui.multi_source_recorder_widget.QProcess", FakeProcess):
            widget.start_directshow_preview(0, "HD Pro Webcam C920")

        self.assertEqual(commands[0][commands[0].index("-framerate") + 1], "30")
        self.assertEqual(commands[0][commands[0].index("-video_size") + 1], "1920x1080")

    def test_basler_preview_uses_auto_driver_mode_even_when_resolution_is_selected(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=True)
        row = widget.source_rows[0]
        row[8].setCurrentText("40.73")
        row[9].setCurrentText("1280 x 1024")
        commands = []

        class FakeProcess:
            NotRunning = QProcess.NotRunning
            Running = QProcess.Running
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self, _parent=None):
                pass

            def __getattr__(self, _name):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, args):
                commands.append([program] + list(args))

        with patch("ui.multi_source_recorder_widget.QProcess", FakeProcess):
            widget.start_directshow_preview(0, "Basler GenICam Source")

        self.assertNotIn("-framerate", commands[0])
        self.assertNotIn("-video_size", commands[0])

    def test_basler_recording_options_use_auto_driver_mode_even_when_resolution_is_selected(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        row = widget.source_rows[0]
        row[3].setText("Basler GenICam Source")
        row[8].setCurrentText("40.73")
        row[9].setCurrentText("1280 x 1024")

        self.assertEqual(widget.recording_options_for_row(0), {"frame_rate": "", "resolution": "", "offset": ""})

    def test_recording_options_include_sync_offset(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[3].setText("rtsp://camera/stream")
        row[10].setValue(0.75)

        self.assertEqual(widget.recording_options_for_row(0)["offset"], "0.75")

    def test_basler_sync_offset_is_returned_even_in_auto_mode(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        row = widget.source_rows[0]
        row[3].setText("Basler GenICam Source")
        row[10].setValue(-0.5)

        self.assertEqual(
            widget.recording_options_for_row(0),
            {"frame_rate": "", "resolution": "", "offset": "-0.50"},
        )

    def test_sync_offset_round_trips_through_recorder_settings(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.source_rows[0][10].setValue(1.25)

        settings = widget.capture_recorder_settings()
        self.assertEqual(settings["channels"][0]["sync_offset"], "1.25")

        widget.source_rows[0][10].setValue(0.0)
        widget.apply_recorder_settings(settings, refresh_previews=False)
        self.assertAlmostEqual(widget.source_rows[0][10].value(), 1.25)

    def test_combined_grid_recording_passes_sync_offset_to_command(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        widget.output_mode_combo.setCurrentText("Combined grid")
        started = []

        class Signal:
            def connect(self, *_args):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, args):
                started.append([program] + list(args))

        widget.create_recording_process = FakeProcess
        selected = [
            (0, "Cam1", "rtsp://camera/stream", {"frame_rate": "", "resolution": "", "offset": "0.75"}),
            (1, "Cam2", "video=Basler GenICam Source", {"frame_rate": "", "resolution": "", "offset": ""}),
        ]

        widget._start_recording_processes("ffmpeg.exe", selected, "C:\\Temp", "stamp")

        command = started[0]
        filter_complex = command[command.index("-filter_complex") + 1]
        # The +0.75s sync offset is folded into that tile's own setpts (a plain
        # -itsoffset would be cancelled by the per-input PTS-STARTPTS rebase).
        self.assertIn("setpts=PTS-STARTPTS+(0.75)/TB", filter_complex)

    def test_output_folder_has_icon_button_and_legacy_alias(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        self.assertIsInstance(widget.open_output_folder_button, QToolButton)
        self.assertEqual(widget.open_output_folder_button.property("glyph"), "folder_open")
        self.assertIs(
            widget.open_output_folder_link,
            widget.open_output_folder_button,
        )
        self.assertTrue(hasattr(widget, "open_output_folder"))

    def test_current_layout_preview_rects_follows_mode_and_enabled_sources(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.output_mode_combo.setCurrentText("Combined grid")
        # Enable two sources (row 0 is always enabled).
        widget.source_rows[1][0].setChecked(True)
        rects = widget.current_layout_preview_rects()
        self.assertEqual(rects, [(0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0)])

    def test_changing_output_mode_emits_layout_preview_changed(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        fired = []
        widget.layout_preview_changed.connect(lambda: fired.append(True))
        widget.output_mode_combo.setCurrentText("Combined grid")
        self.assertTrue(fired)

    def test_enabling_a_source_emits_layout_preview_changed(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        fired = []
        widget.layout_preview_changed.connect(lambda: fired.append(True))
        widget.source_rows[1][0].setChecked(True)
        self.assertTrue(fired)

    def test_combined_recording_marks_genicam_runs_as_retryable(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        widget.output_mode_combo.setCurrentText("Combined grid")
        captured = []

        class Signal:
            def connect(self, *_args):
                pass

        class FakeProcess:
            def __init__(self):
                self.errorOccurred = Signal()
                self.finished = Signal()
                self.readyReadStandardOutput = Signal()
                self.readyReadStandardError = Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, args):
                captured.append(self)

        widget.create_recording_process = FakeProcess
        selected = [
            (0, "Cam1", "rtsp://camera/stream", {"frame_rate": "", "resolution": "", "offset": ""}),
            (1, "Cam2", "video=Basler GenICam Source", {"frame_rate": "", "resolution": "", "offset": ""}),
        ]

        widget._start_recording_processes("ffmpeg.exe", selected, "C:\\Temp", "stamp")

        # A combined run that includes a Basler/GenICam source can retry once if the device
        # is still releasing from its idle preview when the recording opens it.
        self.assertTrue(captured[0].combined_can_retry)
        self.assertEqual(captured[0].combined_recording_attempt, 0)

    def test_combined_recording_retries_after_basler_bind_failure(self):
        import types

        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        retries = []
        widget._start_combined_grid_process = lambda *args, **kwargs: retries.append(kwargs.get("attempt"))
        widget.status_label.setText("Recording")

        process = types.SimpleNamespace(
            combined_can_retry=True,
            combined_recording_context=(
                "ffmpeg.exe",
                [(1, "Cam", "video=Basler GenICam Source", {})],
                "C:\\Temp",
                "stamp",
            ),
            combined_recording_attempt=0,
            combined_retry_delay_ms=0,
            recording_error_text="Unable to BindToObject for Basler GenICam Source\nI/O error",
        )

        handled = widget._retry_combined_recording(process, "Combined")
        self.assertTrue(handled)
        self.app.processEvents()
        self.assertEqual(retries, [1])

    def test_combined_recording_does_not_retry_on_clean_stop(self):
        import types

        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=False)
        process = types.SimpleNamespace(
            combined_can_retry=True,
            combined_recording_context=("ffmpeg.exe", [], "C:\\Temp", "stamp"),
            combined_recording_attempt=0,
            combined_retry_delay_ms=0,
            recording_error_text="",
        )

        self.assertFalse(widget._retry_combined_recording(process, "Combined"))

    def test_basler_recording_tees_file_and_live_preview_from_single_open(self):
        # Basler / GenICam can only be owned by one DirectShow graph at a time, so the
        # recording process opens the device once and tees the MP4 file plus a live
        # MJPEG preview from that single capture. This keeps the preview running during
        # recording instead of pausing it, and avoids the BindToObject contention a
        # separate preview process used to cause. Validated live: the Basler tee
        # produces a valid MP4 and a drained preview pipe when given the pre-recording
        # settle window.
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=True)
        started = []

        class FakeProcess:
            MergedChannels = QProcess.MergedChannels
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self):
                self.readyReadStandardOutput = type("Signal", (), {"connect": lambda *_args: None})()
                self.readyReadStandardError = type("Signal", (), {"connect": lambda *_args: None})()
                self.finished = type("Signal", (), {"connect": lambda *_args: None})()
                self.errorOccurred = type("Signal", (), {"connect": lambda *_args: None})()

            def setProcessChannelMode(self, mode):
                self.channel_mode = mode

            def start(self, program, args):
                started.append([program] + list(args))

        widget.create_recording_process = FakeProcess

        widget._start_recording_processes(
            "ffmpeg.exe",
            [(0, "Video 1", "video=Basler GenICam Source", {"frame_rate": "", "resolution": ""})],
            "C:\\Temp",
            "stamp",
        )

        self.assertIn("image2pipe", started[0])
        self.assertIn("C:\\Temp\\Video_Video_1_stamp.mp4", started[0])
        self.assertEqual(started[0][-1], "pipe:1")

    def test_basler_recording_gets_delayed_retry_when_first_open_fails(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=True)
        started = []

        class FakeProcess:
            MergedChannels = QProcess.MergedChannels
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self):
                self.readyReadStandardOutput = type("Signal", (), {"connect": lambda *_args: None})()
                self.readyReadStandardError = type("Signal", (), {"connect": lambda *_args: None})()
                self.finished = type("Signal", (), {"connect": lambda *_args: None})()
                self.errorOccurred = type("Signal", (), {"connect": lambda *_args: None})()

            def setProcessChannelMode(self, mode):
                self.channel_mode = mode

            def start(self, program, args):
                started.append([program] + list(args))

        widget.create_recording_process = FakeProcess

        widget._start_recording_processes(
            "ffmpeg.exe",
            [(0, "Video 1", "video=Basler GenICam Source", {"frame_rate": "", "resolution": ""})],
            "C:\\Temp",
            "stamp",
        )

        self.assertEqual(widget.processes[0].recording_fallback_commands, [started[0]])
        self.assertEqual(widget.processes[0].recording_retry_delay_ms, widget.basler_record_start_delay_ms)

    def test_directshow_preview_retries_without_requested_mode_when_driver_rejects_options(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=True)
        row = widget.source_rows[2]
        row[8].setCurrentText("30.00")
        row[9].setCurrentText("1920 x 1080")
        scheduled = []

        class FailedPreviewProcess:
            preview_requested_options = True
            preview_error_text = "Could not set video options"

            def state(self):
                return QProcess.NotRunning

        process = FailedPreviewProcess()
        widget.preview_processes[2] = process
        widget.preview_sources[2] = ("directshow", "Basler GenICam Source", widget.preview_source_profile)

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._preview_finished(2, 1, process)

        self.assertIn(2, widget.preview_auto_mode_rows)
        self.assertEqual(len(scheduled), 1)

        commands = []

        class FakeProcess:
            NotRunning = QProcess.NotRunning
            Running = QProcess.Running
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self, _parent=None):
                pass

            def __getattr__(self, _name):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, program, args):
                commands.append([program] + list(args))

        with patch("ui.multi_source_recorder_widget.QProcess", FakeProcess):
            scheduled[0][1]()

        self.assertNotIn("-video_size", commands[0])
        self.assertNotIn("-framerate", commands[0])

    def test_directshow_preview_stops_retrying_when_non_basler_device_is_not_video_available(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Missing Camera"], auto_preview=True)

        class FailedPreviewProcess:
            preview_requested_options = False
            preview_error_text = "Could not find video device with name [Missing Camera] among source devices of type video."

            def state(self):
                return QProcess.NotRunning

        process = FailedPreviewProcess()
        widget.preview_processes[0] = process
        widget.preview_sources[0] = ("directshow", "Missing Camera", widget.preview_source_profile)
        scheduled = []

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._preview_finished(0, 1, process)

        self.assertEqual(scheduled, [])
        self.assertIn("Camera is not available as a DirectShow video device", widget.preview_boxes[0].text())

    def test_basler_preview_keeps_retrying_bind_failures_for_compatibility(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["Basler GenICam Source"], auto_preview=True)

        class FailedPreviewProcess:
            preview_requested_options = False
            preview_error_text = "Could not find video device with name [Basler GenICam Source] among source devices of type video."

            def state(self):
                return QProcess.NotRunning

        process = FailedPreviewProcess()
        widget.preview_processes[0] = process
        widget.preview_sources[0] = ("directshow", "Basler GenICam Source", widget.preview_source_profile)
        scheduled = []

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._preview_finished(0, 1, process)

        self.assertEqual(len(scheduled), 1)
        self.assertIn("Preview interrupted", widget.preview_boxes[0].text())

    def test_unchanged_usb_preview_is_not_restarted_when_dialog_is_applied(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)

        class FakePreviewProcess:
            def __init__(self):
                self.killed = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

        preview = FakePreviewProcess()
        widget.preview_processes[0] = preview
        widget.preview_sources[0] = ("directshow", "HD Pro Webcam C920", widget.preview_source_profile)

        widget.start_directshow_preview(0, "HD Pro Webcam C920")

        self.assertFalse(preview.killed)

    def test_intentional_preview_stop_does_not_show_camera_in_use_message(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.preview_stopping_rows.add(0)

        widget._preview_finished(0, 1)

        self.assertNotIn("Camera may be in use", widget.preview_boxes[0].text())

    def test_unexpected_preview_finish_schedules_retry(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        widget.preview_sources[0] = ("stream", "rtsp://camera/stream", widget.preview_source_profile)
        scheduled = []

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._preview_finished(0, 1)

        self.assertEqual(len(scheduled), 1)
        self.assertIn("Reconnecting", widget.preview_boxes[0].text())

    def test_stream_preview_with_an_unresolvable_host_says_so_and_stops_retrying(self):
        # A mistyped IP (e.g. a four-digit octet) is not an IPv4 literal, so
        # ffmpeg tries DNS and fails; reconnecting every few seconds only
        # hides the real problem.
        widget = MultiSourceRecorderWidget(auto_preview=True)

        class FailedPreviewProcess:
            preview_requested_options = False
            preview_error_text = (
                "[tcp @ 000001] Failed to resolve hostname 10.0.1000.5: "
                "The name does not resolve for the supplied parameters\n"
                "Error opening input files: I/O error")

            def state(self):
                return QProcess.NotRunning

        process = FailedPreviewProcess()
        widget.preview_processes[0] = process
        widget.preview_sources[0] = ("stream", "rtsp://10.0.1000.5:554/axis-media/media.amp", widget.preview_source_profile)
        scheduled = []

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._preview_finished(0, 1, process)

        self.assertEqual(scheduled, [])
        text = widget.preview_boxes[0].text()
        self.assertIn("Cannot resolve the camera address", text)
        self.assertIn("Video Settings", text)

    def test_rtsp_dialog_refuses_an_address_that_is_not_an_ip(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
        warnings = []
        with patch("ui.multi_source_recorder_widget.QMessageBox.warning",
                   lambda *args, **kwargs: warnings.append(args[2])):
            self.assertFalse(dialog._accept_rtsp_host("10.0.1000.5"))
            self.assertTrue(dialog._accept_rtsp_host("10.0.100.5"))
            self.assertTrue(dialog._accept_rtsp_host("camera.local"))
        self.assertEqual(len(warnings), 1)
        self.assertIn("1000", warnings[0])

    def test_preview_retry_restarts_same_source_with_force_restart(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        calls = []
        widget.preview_sources[0] = ("stream", "rtsp://camera/stream", widget.preview_source_profile)
        widget.start_stream_preview = lambda row, source, force_restart=False: calls.append((row, source, force_restart))

        widget._retry_preview(0, ("stream", "rtsp://camera/stream", widget.preview_source_profile))

        self.assertEqual(calls, [(0, "rtsp://camera/stream", True)])

    def test_preview_retry_does_not_restart_healthy_current_preview(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        calls = []
        source_info = ("stream", "rtsp://camera/stream", widget.preview_source_profile)
        widget.preview_sources[0] = source_info

        class HealthyProcess:
            def state(self):
                return QProcess.Running

        widget.preview_processes[0] = HealthyProcess()
        widget.start_stream_preview = lambda row, source, force_restart=False: calls.append((row, source, force_restart))

        widget._retry_preview(0, source_info)

        self.assertEqual(calls, [])

    def test_stale_preview_process_finish_does_not_schedule_retry(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        current_process = object()
        stale_process = object()
        widget.preview_processes[0] = current_process
        widget.preview_sources[0] = ("stream", "rtsp://camera/stream", widget.preview_source_profile)
        scheduled = []

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._preview_finished(0, 1, stale_process)

        self.assertEqual(scheduled, [])
        self.assertNotIn("Reconnecting", widget.preview_boxes[0].text())

    def test_successful_preview_frame_resets_retry_attempts(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        widget.preview_retry_attempts[0] = 3

        class FakeProcess:
            def readAllStandardOutput(self):
                return b"\xff\xd8frame\xff\xd9"

        widget._read_preview_frames(FakeProcess(), 0)

        self.assertNotIn(0, widget.preview_retry_attempts)

    def test_preview_frame_average_luma_identifies_dark_and_bright_frames(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        dark = QPixmap(16, 16)
        bright = QPixmap(16, 16)
        dark.fill(Qt.black)
        bright.fill(Qt.white)

        self.assertLess(widget._preview_frame_average_luma(dark), 2)
        self.assertGreater(widget._preview_frame_average_luma(bright), 250)

    def test_directshow_recording_uses_reliable_single_output_command(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")
        command = widget.build_recording_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4")

        self.assertNotIn("image2pipe", command)
        self.assertEqual(command[-1], "out.mp4")

    def test_preview_reader_keeps_latest_frame_for_timer_rendering(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        first_frame = b"\xff\xd8first-frame\xff\xd9"
        second_frame = b"\xff\xd8second-frame\xff\xd9"

        class FakeProcess:
            def readAllStandardOutput(self):
                return first_frame + second_frame

        widget._read_preview_frames(FakeProcess(), 0)

        self.assertEqual(widget.preview_pending_frames[0], second_frame)
        self.assertEqual(widget.preview_buffers[0], bytearray())

    def test_start_recording_clears_stale_preview_backlog_before_launch(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("directshow"))
        row[3].setText("HD Pro Webcam C920")
        widget.preview_buffers[0] = bytearray(b"old-buffer")
        widget.preview_pending_frames[0] = b"old-frame"
        widget.preview_buffers[1] = bytearray(b"old-axis-buffer")
        widget.preview_pending_frames[1] = b"old-axis-frame"
        widget.release_preview_processes_for_recording = lambda *_args: False
        widget._start_recording_processes = lambda *_args: None

        widget.start_recording()

        self.assertEqual(widget.preview_buffers, {})
        self.assertEqual(widget.preview_pending_frames, {})

    def test_stop_recording_clears_stale_preview_backlog(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.preview_buffers[0] = bytearray(b"old-buffer")
        widget.preview_pending_frames[0] = b"old-frame"
        widget.refresh_previews_from_sources = lambda force_restart=False: None

        with patch.object(widget, "_schedule", lambda *_args: None):
            widget.stop_recording()

        self.assertEqual(widget.preview_buffers, {})
        self.assertEqual(widget.preview_pending_frames, {})

    def test_restarting_stream_preview_clears_stale_row_backlog(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        widget.preview_buffers[1] = bytearray(b"old-buffer")
        widget.preview_pending_frames[1] = b"old-frame"

        class ExistingProcess:
            def state(self):
                return QProcess.Running

            def kill(self):
                pass

        widget.preview_processes[1] = ExistingProcess()
        widget.preview_sources[1] = ("stream", "rtsp://camera/old", widget.preview_source_profile)

        class FakeQProcess:
            NotRunning = QProcess.NotRunning
            Running = QProcess.Running
            SeparateChannels = QProcess.SeparateChannels

            def __init__(self, _parent=None):
                pass

            def setProcessChannelMode(self, _mode):
                pass

            @property
            def readyReadStandardOutput(self):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            @property
            def readyReadStandardError(self):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            @property
            def finished(self):
                class Signal:
                    def connect(self, _callback):
                        pass
                return Signal()

            def start(self, *_args):
                pass

        with patch("ui.multi_source_recorder_widget.QProcess", FakeQProcess):
            widget.start_stream_preview(1, "rtsp://camera/new", force_restart=True)

        self.assertEqual(widget.preview_buffers[1], bytearray())
        self.assertNotIn(1, widget.preview_pending_frames)

    def test_preview_reader_ignores_deleted_qprocess_signal(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class DeletedProcess:
            def readAllStandardOutput(self):
                raise RuntimeError("wrapped C/C++ object of type QProcess has been deleted")

        widget._read_preview_frames(DeletedProcess(), 0)

        self.assertEqual(widget.preview_buffers.get(0), bytearray())

    def test_stop_recording_requests_ffmpeg_finalize_without_blocking_ui(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class FakeRecordProcess:
            def __init__(self):
                self.wrote_quit = False
                self.terminated = False
                self.waited_for_quit = False
                self.closed_input = False
                self.waited_for_finish = False

            def state(self):
                return QProcess.Running

            def write(self, data):
                self.wrote_quit = data == b"q\n"

            def waitForBytesWritten(self, _timeout):
                self.waited_for_quit = True
                return True

            def closeWriteChannel(self):
                self.closed_input = True

            def waitForFinished(self, _timeout):
                self.waited_for_finish = True
                return True

            def terminate(self):
                self.terminated = True

        process = FakeRecordProcess()
        widget.processes = [process]

        widget.stop_recording()

        self.assertTrue(process.wrote_quit)
        self.assertTrue(process.waited_for_quit)
        self.assertTrue(process.closed_input)
        self.assertFalse(process.waited_for_finish)
        self.assertFalse(process.terminated)
        self.assertEqual(widget.processes, [process])
        self.assertEqual(widget.status_label.text(), "Stopping...")

    def test_stop_recording_schedules_force_cleanup_when_ffmpeg_will_not_finish(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class StuckRecordProcess:
            def __init__(self):
                self.terminated = False
                self.killed = False

            def state(self):
                return QProcess.Running

            def write(self, _data):
                pass

            def waitForBytesWritten(self, _timeout):
                return True

            def closeWriteChannel(self):
                pass

            def waitForFinished(self, _timeout):
                return False

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.killed = True

        process = StuckRecordProcess()
        widget.processes = [process]

        scheduled = []
        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget.stop_recording()

        # Stop should feel snappy. q is written first, then the kill path kicks in
        # quickly so the UI never lingers on "Stopping..." for many seconds. A final
        # global watchdog (4000ms) cleans up the UI even if every per-process timer
        # somehow fails to remove the process.
        self.assertEqual(
            [delay for delay, _callback in scheduled],
            [1500, 3000, 4000],
        )
        self.assertFalse(process.terminated)
        self.assertFalse(process.killed)
        self.assertEqual(widget.processes, [process])
        self.assertEqual(widget.status_label.text(), "Stopping...")

    def test_stop_recording_watchdog_clears_stopping_status_after_timeout(self):
        # Final-stop safety net: even if every per-process timer fails (or Qt skips
        # them under load), this watchdog should kill any survivors, resume idle
        # previews, and move the UI off "Stopping..." so the user is never stuck.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Stopping...")
        widget.preview_paused_rows = {0}
        refreshed = []
        widget.refresh_previews_from_sources = lambda force_restart=False: refreshed.append(force_restart)

        class FakeProcess:
            def __init__(self):
                self.killed = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

        survivor = FakeProcess()
        widget.processes = [survivor]

        widget._stop_recording_watchdog()

        self.assertTrue(survivor.killed)
        self.assertEqual(widget.processes, [])
        self.assertNotEqual(widget.status_label.text(), "Stopping...")
        self.assertTrue(widget.start_btn.isEnabled())
        self.assertFalse(widget.stop_btn.isEnabled())
        self.assertEqual(refreshed, [False])
        self.assertEqual(widget.preview_paused_rows, set())

    def test_recording_finish_delays_paused_preview_restart_until_camera_releases(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        widget.status_label.setText("Stopping...")
        widget.preview_paused_rows = {2}
        refreshed = []
        scheduled = []
        widget.refresh_previews_from_sources = lambda force_restart=False: refreshed.append(force_restart)

        class FakeProcess:
            def state(self):
                return QProcess.NotRunning

        process = FakeProcess()
        widget.processes = [process]

        with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
            widget._process_finished(process, "Video_3", 0)

        self.assertEqual(refreshed, [])
        self.assertEqual(widget.preview_paused_rows, {2})
        self.assertEqual(scheduled[0][0], widget.record_start_delay_ms)
        scheduled[0][1]()
        self.assertEqual(refreshed, [False])
        self.assertEqual(widget.preview_paused_rows, set())

    def test_stop_recording_watchdog_is_idempotent_when_recording_already_finished(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Not recording")
        widget.preview_paused_rows = set()
        refreshed = []
        widget.refresh_previews_from_sources = lambda force_restart=False: refreshed.append(force_restart)

        widget._stop_recording_watchdog()

        # When the regular finished path has already cleaned up, the watchdog must not
        # second-guess the UI state or restart previews that are already running.
        self.assertEqual(widget.status_label.text(), "Not recording")
        self.assertEqual(refreshed, [])

    def test_workflow_availability_notification_uses_original_host_reference(self):
        class FakeMainWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def update_single_workflow_availability(self):
                self.calls += 1

        main_window = FakeMainWindow()
        widget = MultiSourceRecorderWidget(parent=main_window, auto_preview=False)

        widget._notify_workflow_availability_change()

        self.assertEqual(main_window.calls, 1)

    def test_workflow_availability_notification_is_safe_without_host(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        widget._notify_workflow_availability_change()

    def test_stop_recording_watchdog_notifies_workflow_ancestor_so_outer_button_updates(self):
        # Regression test for the "stuck on Stopping..." button label: the watchdog
        # must reach an ancestor that owns the outer start/stop button, not just the
        # immediate inert layout-container parent.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Stopping...")
        widget.refresh_previews_from_sources = lambda force_restart=False: None

        class FakeMainWindow:
            def __init__(self):
                self.calls = 0

            def parent(self):
                return None

            def update_single_workflow_availability(self):
                self.calls += 1

        class FakeLayoutContainer:
            def __init__(self, ancestor):
                self._ancestor = ancestor

            def parent(self):
                return self._ancestor

        main_window = FakeMainWindow()
        widget.parent = lambda: FakeLayoutContainer(main_window)

        widget._stop_recording_watchdog()

        self.assertGreaterEqual(main_window.calls, 1)
        self.assertNotEqual(widget.status_label.text(), "Stopping...")

    def test_start_recording_ignored_while_recording_or_stopping(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)
        calls = []
        widget._start_recording_processes = lambda *args: calls.append(args)
        widget.status_label.setText("Stopping...")

        widget.start_recording()

        self.assertEqual(calls, [])

    def test_user_stopped_recording_does_not_show_failure_on_nonzero_exit(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Stopping...")

        class FakeProcess:
            def state(self):
                return QProcess.NotRunning

        widget._process_finished(FakeProcess(), "Video_1", 1)

        self.assertEqual(widget.status_label.text(), "Not recording")

    def test_forced_stop_escalates_to_kill_if_terminate_does_not_finish(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class FakeProcess:
            def __init__(self):
                self.terminated = False
                self.killed = False

            def state(self):
                return QProcess.Running

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.killed = True

        process = FakeProcess()

        widget._terminate_if_running(process)
        widget._kill_if_running(process)

        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)

    def test_forced_stop_cleanup_does_not_leave_stopping_status(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Stopping...")

        class FakeProcess:
            def __init__(self):
                self.killed = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

        process = FakeProcess()
        widget.processes = [process]

        widget._force_finish_if_running(process)

        self.assertTrue(process.killed)
        self.assertEqual(widget.processes, [])
        self.assertIn("failed", widget.status_label.text().lower())

    def test_forced_stop_cleanup_resumes_idle_previews_for_paused_rows(self):
        # When FFmpeg never honored q and we had to escalate to a kill, the previews that
        # were paused for the recording must come back, otherwise the user is left with
        # frozen tiles even though the status label has moved on.
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.status_label.setText("Stopping...")
        widget.preview_paused_rows = {0, 1}
        refreshed = []
        widget.refresh_previews_from_sources = lambda force_restart=False: refreshed.append(force_restart)

        class FakeProcess:
            def state(self):
                return QProcess.Running

            def kill(self):
                pass

        process = FakeProcess()
        widget.processes = [process]

        widget._force_finish_if_running(process)

        self.assertEqual(refreshed, [False])
        self.assertEqual(widget.preview_paused_rows, set())

    def test_release_preview_processes_keeps_unselected_row_preview_alive(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)

        class PreviewProcess:
            def __init__(self):
                self.terminated = False

            def state(self):
                return QProcess.Running

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                return True

            def kill(self):
                pass

        unselected_rtsp = PreviewProcess()
        widget.preview_processes = {1: unselected_rtsp}
        widget.preview_sources = {
            1: ("stream", "rtsp://camera/stream", widget.preview_source_profile),
        }
        selected = [(0, "Video 1", "video=HD Pro Webcam C920")]

        widget.release_preview_processes_for_recording(selected)

        self.assertFalse(unselected_rtsp.terminated)
        self.assertIn(1, widget.preview_processes)
        self.assertEqual(widget.preview_paused_rows, set())

    def test_release_preview_processes_tracks_paused_directshow_rows(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)

        class PreviewProcess:
            def state(self):
                return QProcess.Running

            def terminate(self):
                pass

            def waitForFinished(self, _timeout):
                return True

            def kill(self):
                pass

        widget.preview_processes = {0: PreviewProcess()}
        widget.preview_sources = {0: ("directshow", "HD Pro Webcam C920", widget.preview_source_profile)}
        selected = [(0, "Video 1", "video=HD Pro Webcam C920")]

        widget.release_preview_processes_for_recording(selected)

        self.assertEqual(widget.preview_paused_rows, {0})

    def test_release_preview_processes_marks_basler_tile_as_starting_live_preview(self):
        # The idle Basler preview is still released so the recording graph can re-open
        # the device, but because recording now tees a live preview from that single
        # open, the tile advertises that the live preview is starting rather than that
        # it will only resume once recording stops.
        widget = MultiSourceRecorderWidget(auto_preview=True)

        class PreviewProcess:
            def state(self):
                return QProcess.Running

            def terminate(self):
                pass

            def waitForFinished(self, _timeout):
                return True

            def kill(self):
                pass

        widget.preview_processes = {2: PreviewProcess()}
        widget.preview_sources = {2: ("directshow", "Basler GenICam Source", widget.preview_source_profile)}
        widget.preview_boxes[2].setPixmap(QPixmap(20, 20))
        selected = [(2, "Video 3", "video=Basler GenICam Source")]

        widget.release_preview_processes_for_recording(selected)

        self.assertEqual(widget.preview_paused_rows, {2})
        self.assertIn("Recording", widget.preview_boxes[2].text())
        self.assertIn("live preview", widget.preview_boxes[2].text().lower())

    def test_release_preview_processes_keeps_selected_rtsp_preview_alive(self):
        # RTSP previews keep running during recording because we do not pipe the
        # preview from the recording process for those sources (see
        # test_rtsp_recording_uses_stream_copy_single_process_and_separate_preview).
        # Killing the preview here would freeze the tile for the entire recording.
        widget = MultiSourceRecorderWidget(auto_preview=True)

        class PreviewProcess:
            def __init__(self):
                self.terminated = False

            def state(self):
                return QProcess.Running

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                return True

            def kill(self):
                pass

        process = PreviewProcess()
        widget.preview_processes = {0: process}
        widget.preview_sources = {0: ("stream", "rtsp://camera/stream", widget.preview_source_profile)}
        selected = [(0, "Camera 1", "rtsp://camera/stream")]

        widget.release_preview_processes_for_recording(selected)

        self.assertFalse(process.terminated)
        self.assertIn(0, widget.preview_processes)
        self.assertNotIn(0, widget.preview_paused_rows)

    def test_widget_recording_command_for_rtsp_uses_stable_profile(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("rtsp_ip"))
        row[3].setText("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp")

        command = widget.build_recording_command(
            "ffmpeg.exe",
            "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp",
            "out.mp4",
        )

        self.assertIn("-rtsp_transport", command)
        self.assertEqual(command[command.index("-rtsp_transport") + 1], "tcp")
        self.assertNotIn("-fflags", command)
        self.assertNotIn("-flags", command)

    def test_axis_ptz_move_logs_action_and_dispatches_url(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        captured = {"urls": []}
        original = widget._send_axis_ptz_url

        def capture(url):
            captured["urls"].append(url)

        try:
            widget._send_axis_ptz_url = capture
            widget.axis_ptz_move("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp", "left")
            widget.axis_ptz_move("rtsp://root:pass@192.168.1.50:554/axis-media/media.amp", "stop")
        finally:
            widget._send_axis_ptz_url = original

        self.assertEqual(len(captured["urls"]), 2)
        self.assertIn("move=left", captured["urls"][0])
        self.assertIn("move=stop", captured["urls"][1])
        self.assertTrue(any("[ptz]" in line and "left" in line for line in widget.log_lines))

    def test_ptz_failure_is_logged_visibly(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        def raise_error(_url, timeout=3):
            raise RuntimeError("axis offline")

        with patch("ui.multi_source_recorder_widget.send_axis_vapix_request", raise_error):
            widget._dispatch_axis_ptz_request("http://camera/axis-cgi/com/ptz.cgi?move=left")

        self.assertTrue(any("ptz" in line.lower() and "failed" in line.lower() for line in widget.log_lines))

    def test_start_recording_logs_each_source_command(self):
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"], auto_preview=False)

        class Signal:
            def connect(self, _callback):
                pass

        class FakeProcess:
            errorOccurred = Signal()
            finished = Signal()
            readyReadStandardOutput = Signal()
            readyReadStandardError = Signal()

            def setProcessChannelMode(self, _mode):
                pass

            def start(self, _program, _arguments):
                pass

        widget.create_recording_process = lambda: FakeProcess()

        widget._start_recording_processes(
            "ffmpeg.exe",
            [(0, "Video 1", "video=HD Pro Webcam C920")],
            "C:\\Temp",
            "20260101_120000",
        )

        self.assertTrue(any("ffmpeg" in line.lower() for line in widget.log_lines))

    def test_stop_recording_does_not_kill_running_rtsp_preview(self):
        widget = MultiSourceRecorderWidget(auto_preview=True)
        row = widget.source_rows[0]
        row[2].setCurrentIndex(row[2].findData("rtsp_ip"))
        row[3].setText("rtsp://camera/stream")

        class HealthyPreview:
            def __init__(self):
                self.killed = False
                self.terminated = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

            def terminate(self):
                self.terminated = True

            def waitForFinished(self, _timeout):
                return True

        healthy = HealthyPreview()
        widget.preview_processes[0] = healthy
        widget.preview_sources[0] = ("stream", "rtsp://camera/stream", widget.preview_source_profile)
        widget.preview_paused_rows = set()

        class FakeRecordProcess:
            def state(self):
                return QProcess.NotRunning

        widget.processes = [FakeRecordProcess()]
        widget.status_label.setText("Recording")

        widget._process_finished(FakeRecordProcess(), "Video_1", 0)

        self.assertFalse(healthy.killed)
        self.assertFalse(healthy.terminated)
        self.assertIs(widget.preview_processes.get(0), healthy)

    def test_shutdown_cleanup_kills_preview_and_recording_processes(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class FakeProcess:
            def __init__(self):
                self.killed = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

        preview = FakeProcess()
        recording = FakeProcess()
        widget.preview_processes[0] = preview
        widget.processes = [recording]

        widget.shutdown()

        self.assertTrue(preview.killed)
        self.assertTrue(recording.killed)
        self.assertEqual(widget.preview_processes, {})
        self.assertEqual(widget.processes, [])

    def test_output_settings_sit_left_of_recording_properties_in_both_modes(self):
        widget = self._widget()
        for metrics in (theme.COMPACT, theme.FULL):
            widget.apply_layout_mode(metrics)
            self.assertFalse(widget.groups_stacked(), metrics.name)
            self.assertIs(widget.groups_layout.itemAt(0).widget(), widget.output_group)
            self.assertIs(widget.groups_layout.itemAt(1).widget(), widget.source_group)
            # The properties table takes the spare width; the output form
            # keeps its natural size so the file-location field stays short.
            self.assertEqual(widget.groups_layout.stretch(0), 0)
            self.assertEqual(widget.groups_layout.stretch(1), 1)
            # Both boxes hang from the top edge: a QHBoxLayout would otherwise
            # centre the shorter one and the properties table sat lower.
            for position in (0, 1):
                self.assertTrue(
                    widget.groups_layout.itemAt(position).alignment() & Qt.AlignTop,
                    (metrics.name, position),
                )
        widget.apply_layout_mode(theme.COMPACT)

    def test_preview_tiles_grow_to_fill_the_tab_in_either_mode(self):
        widget = self._widget()
        for metrics in (theme.COMPACT, theme.FULL):
            widget.apply_layout_mode(metrics)
            tile = widget.preview_boxes[0]
            self.assertEqual(tile.sizePolicy().verticalPolicy(), QSizePolicy.Expanding, metrics.name)
            self.assertEqual(tile.maximumHeight(), QWIDGETSIZE_MAX, metrics.name)
        layout = widget.layout()
        grid_index = next(
            i for i in range(layout.count()) if layout.itemAt(i).layout() is widget.preview_grid
        )
        host_index = next(
            i for i in range(layout.count()) if layout.itemAt(i).widget() is widget.groups_host
        )
        self.assertEqual(layout.stretch(grid_index), 1)
        self.assertEqual(layout.stretch(host_index), 0)
        widget.apply_layout_mode(theme.COMPACT)

    def test_a_preview_frame_never_asks_the_layout_for_more_room(self):
        # A QLabel's hints follow its pixmap; frames are scaled to the tile's
        # current size, so the default hints made every frame 2 px taller than
        # the last (pixmap + frame) and a single-source tab crept downwards.
        widget = self._widget()
        tile = widget.preview_boxes[0]
        before = (tile.sizeHint(), tile.minimumSizeHint())
        big = QPixmap(1280, 720)
        big.fill(Qt.blue)
        tile.setPixmap(big)
        self.assertEqual((tile.sizeHint(), tile.minimumSizeHint()), before)
        self.assertEqual(tile.minimumSizeHint().height(), tile.minimumHeight())
        self.assertLess(tile.sizeHint().height(), 200)

    def test_single_source_tile_keeps_its_height_frame_after_frame(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        for index, row in enumerate(widget.source_rows):
            row[0].setChecked(index == 0)
        widget.update_preview_panel_visibility()
        widget.resize(1000, 620)
        widget.move(-7000, -7000)
        widget.show()
        for _ in range(5):
            self.app.processEvents()
        tile = widget.preview_boxes[0]
        start = tile.height()
        frame = QPixmap(1280, 720)
        frame.fill(Qt.darkGray)
        for _ in range(6):
            tile.setPixmap(frame.scaled(tile.contentsRect().size(), Qt.KeepAspectRatio))
            for _ in range(4):
                self.app.processEvents()
        self.assertEqual(tile.height(), start)
        self.assertEqual(widget.height(), 620)
        widget.close()

    def test_output_settings_fields_share_one_width(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)
        widget.apply_layout_mode(theme.FULL)
        widget.resize(1100, 700)
        widget.move(-7000, -7000)   # geometry needs a realized widget; never on the desktop
        widget.show()
        for _ in range(5):
            self.app.processEvents()
        self.assertTrue(widget.isVisible())
        fields = {
            "base_name": widget.base_name_edit.geometry(),
            "codec": widget.codec_combo.geometry(),
            "mode": widget.output_mode_combo.geometry(),
            "timer": widget.duration_edit.geometry(),
        }
        self.assertEqual(len({(r.left(), r.right()) for r in fields.values()}), 1, fields)
        # The folder row spans the same width: edit + open-folder button.
        folder = widget.output_folder_edit.geometry()
        button = widget.open_output_folder_button.geometry()
        self.assertEqual(folder.left(), fields["base_name"].left())
        self.assertEqual(button.right(), fields["base_name"].right())
        self.assertLessEqual(widget.output_group.maximumWidth(), 400)
        # Boxes hang from one top edge; tiles took the height above them.
        self.assertEqual(widget.output_group.y(), widget.source_group.y())
        self.assertGreater(widget.preview_boxes[0].height(), 300)
        widget.close()

    def test_stacked_layout_is_still_available_for_narrow_metrics(self):
        widget = self._widget()
        narrow = replace(theme.COMPACT, recorder_stacked=True)
        widget.apply_layout_mode(narrow)
        self.assertTrue(widget.groups_stacked())
        self.assertIs(widget.groups_layout.itemAt(0).widget(), widget.output_group)
        widget.apply_layout_mode(theme.COMPACT)

    def test_file_location_shows_the_tail_of_a_long_path(self):
        widget = self._widget()
        widget.output_folder_edit.setText(
            r"C:\Videos\a\very\long\path\to\recordings"
        )
        self.assertEqual(
            widget.output_folder_edit.cursorPosition(),
            len(widget.output_folder_edit.text()),
        )
        self.assertEqual(
            widget.output_folder_edit.sizePolicy().horizontalPolicy(),
            QSizePolicy.Expanding,
        )
        # Capped (via the group) so the field never spans the whole window.
        self.assertLessEqual(widget.output_group.maximumWidth(), 400)

    def test_copy_mode_note_only_for_usb_rows_in_copy_mode(self):
        widget = self._widget()
        enabled, _label, type_combo = widget.source_rows[0][:3]
        widget.codec_combo.setCurrentText("copy")
        type_combo.setCurrentIndex(type_combo.findData("rtsp_ip"))
        self.assertTrue(widget.copy_mode_note.isHidden())
        type_combo.setCurrentIndex(type_combo.findData("directshow"))
        self.assertFalse(widget.copy_mode_note.isHidden())
        self.assertEqual(
            widget.copy_mode_note.text(),
            "USB cameras and screen capture are always re-encoded to H.264; copy applies to RTSP and file sources.",
        )
        widget.codec_combo.setCurrentText("h264")
        self.assertTrue(widget.copy_mode_note.isHidden())


if __name__ == "__main__":
    unittest.main()


class TimerAndProcessOwnershipTests(unittest.TestCase):
    """Nothing this widget schedules or launches may outlive it.

    Both bugs pinned here presented identically and misleadingly: the process
    aborted with STATUS_STACK_BUFFER_OVERRUN (0xC0000409), part-way through the
    test suite, at whichever unrelated test happened to be pumping the event
    loop -- and with no traceback, because PyQt reacts to an exception escaping
    a Qt slot by calling qFatal(). In the running app the same two faults show
    up as NVC dying on exit shortly after using the recorder.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._pre_existing = list(self.app.topLevelWidgets())

    def tearDown(self):
        for widget in self.app.topLevelWidgets():
            if widget not in self._pre_existing and widget.parentWidget() is None:
                try:
                    widget.shutdown()
                except Exception:
                    pass
                widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_scheduled_callbacks_are_owned_by_the_widget(self):
        widget = MultiSourceRecorderWidget(auto_preview=False)

        timer = widget._schedule(60_000, lambda: None)

        self.assertIs(timer.parent(), widget)
        self.assertTrue(timer.isSingleShot())
        self.assertTrue(timer.isActive())

    def test_shutdown_kills_the_camera_mode_probes(self):
        """Picking a camera in Video Settings starts an ffmpeg probe whose
        finished handler writes back into the dialog. shutdown() used to leave
        those running: it only walked preview_processes and processes."""
        widget = MultiSourceRecorderWidget(auto_preview=False)

        class RunningProbe:
            def __init__(self):
                self.killed = False

            def state(self):
                return QProcess.Running

            def kill(self):
                self.killed = True

        probe = RunningProbe()
        widget.camera_mode_processes = [probe]

        widget.shutdown()

        self.assertTrue(probe.killed)
        self.assertEqual(widget.camera_mode_processes, [])

    def test_a_detection_callback_survives_a_closed_dialog(self):
        """The probe outlives the dialog that asked for it, so its callback has
        to tolerate the dialog's widgets being gone."""
        widget = MultiSourceRecorderWidget(directshow_devices=["HD Pro Webcam C920"],
                                           auto_preview=False)
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(),
                                     parent=widget)
        dialog.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

        widget.camera_mode_cache.clear()
        with patch.object(widget, "camera_mode_cache", {"directshow:Cam": ["mode"]}):
            # Nothing to assert but "does not raise": before the fix this
            # RuntimeError escaped a Qt slot and aborted the process.
            widget.start_directshow_mode_detection(
                "Cam", lambda modes: dialog.apply_detected_modes(0, modes))
