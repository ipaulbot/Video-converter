import unittest

from PyQt5.QtWidgets import QApplication

from ui.main_window import VideoConverterApp


class SingleActiveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window_on_recorder_tab(self):
        window = VideoConverterApp()
        # The recorder is an optional tool tab and off by default, so
        # apply_tool_tab_visibility hides it -- and Qt silently refuses to make
        # a hidden tab current, which left the window on tab 0 and every
        # assertion below reading the conversion-mode button. These tests used
        # to pass only because this developer's saved settings happened to have
        # the recorder enabled; enable it explicitly instead.
        window.settings.setdefault("visible_tool_tabs", {})
        window.settings["visible_tool_tabs"]["multi_source_recorder"] = True
        window.apply_tool_tab_visibility()

        recorder_index = window.tabs.indexOf(window.multi_source_recorder_tab_scroll)
        window.tabs.setCurrentIndex(recorder_index)
        assert window.tabs.currentIndex() == recorder_index, (
            "the recorder tab did not become current; is it still hidden?")
        window.on_tab_changed(recorder_index)
        return window

    def test_start_button_switches_to_recording_action_on_recorder_tab(self):
        window = self._window_on_recorder_tab()
        try:
            self.assertEqual(window.start_button.text(), "Start Recording")
            self.assertIn("recording", window.start_button.toolTip().lower())
        finally:
            window.shutdown()

    def test_global_start_button_routes_to_recorder_when_recorder_tab_is_active(self):
        window = self._window_on_recorder_tab()
        calls = {"record": 0, "convert": 0}
        window.multi_source_recorder_widget.start_recording = lambda: calls.__setitem__("record", calls["record"] + 1)
        window.start_conversion = lambda: calls.__setitem__("convert", calls["convert"] + 1)
        try:
            window.toggle_process()

            self.assertEqual(calls["record"], 1)
            self.assertEqual(calls["convert"], 0)
        finally:
            window.shutdown()

    def test_conversion_blocks_only_start_recording_and_says_why(self):
        # Rule 3: the recorder stays usable (previews, settings); only Start
        # Recording is unavailable, and the recorder's own status line says why.
        window = self._window_on_recorder_tab()
        try:
            window.is_converting = True
            window.update_single_workflow_availability()

            self.assertTrue(window.multi_source_recorder_widget.isEnabled())
            self.assertIn("conversion", window.multi_source_recorder_widget.status_label.text().lower())
            self.assertFalse(window.start_button.isEnabled())
            self.assertEqual(window.start_button.text(), "Converting...")
            self.assertIn("conversion", window.start_button.toolTip().lower())

            window.is_converting = False
            window.update_single_workflow_availability()
            self.assertEqual(window.multi_source_recorder_widget.status_label.text(), "Not recording")
            self.assertTrue(window.start_button.isEnabled())
        finally:
            window.shutdown()

    def test_recording_blocks_the_converter_start_button_with_a_reason(self):
        # Rule 2: the sidebar Start on the converter tab is greyed out while recording.
        window = self._window_on_recorder_tab()
        try:
            window.multi_source_recorder_widget.status_label.setText("Recording")
            window.tabs.setCurrentIndex(window.tabs.indexOf(window.converter_tab_scroll))
            window.on_tab_changed(window.tabs.currentIndex())

            self.assertFalse(window.start_button.isEnabled())
            self.assertEqual(window.start_button.text(), "Recording...")
            self.assertIn("recording", window.start_button.toolTip().lower())
            # Every tab stays reachable (rule 1).
            for index in range(window.tabs.count()):
                self.assertTrue(window.tabs.isTabEnabled(index))

            window.multi_source_recorder_widget.status_label.setText("Not recording")
            window.update_single_workflow_availability()
            self.assertTrue(window.start_button.isEnabled())
            self.assertEqual(window.start_button.text(), "Start")
        finally:
            window.shutdown()

    def test_recording_greys_out_lossless_edits_with_a_reason(self):
        window = self._window_on_recorder_tab()
        try:
            editor = window.lossless_editor_widget
            window.multi_source_recorder_widget.status_label.setText("Recording")
            window.update_single_workflow_availability()
            for button in (editor.trim_btn, editor.merge_btn, editor.remux_btn):
                self.assertFalse(button.isEnabled())
                self.assertIn("recording", button.toolTip().lower())
            self.assertTrue(editor.add_merge_btn.isEnabled())   # browsing is fine

            window.multi_source_recorder_widget.status_label.setText("Not recording")
            window.update_single_workflow_availability()
            self.assertTrue(editor.trim_btn.isEnabled())
            self.assertEqual(editor.trim_btn.toolTip(), "Cut Start to End without re-encoding")
        finally:
            window.shutdown()

    def test_toggle_process_refuses_a_conversion_while_recording(self):
        window = self._window_on_recorder_tab()
        calls = {"convert": 0}
        window.start_conversion = lambda: calls.__setitem__("convert", calls["convert"] + 1)
        try:
            window.multi_source_recorder_widget.status_label.setText("Recording")
            window.tabs.setCurrentIndex(window.tabs.indexOf(window.converter_tab_scroll))
            window.on_tab_changed(window.tabs.currentIndex())
            window.toggle_process()
            self.assertEqual(calls["convert"], 0)
            self.assertIn("recording", window.console_output.toPlainText().lower())
        finally:
            window.shutdown()

    def test_every_footer_shows_the_same_status_line(self):
        window = self._window_on_recorder_tab()
        try:
            labels = window.footer_status_labels()
            self.assertEqual(len(labels), 5)
            self.assertTrue(all("Status: Idle" in label.text() for label in labels))

            window.multi_source_recorder_widget.status_label.setText("Recording")
            window.update_single_workflow_availability()
            self.assertTrue(all("Recording" in label.text() for label in labels))
            self.assertEqual(len({label.text() for label in labels}), 1)

            window.multi_source_recorder_widget.status_label.setText("Not recording")
            window.running = True
            window.update_single_workflow_availability()
            self.assertTrue(all("Monitoring" in label.text() for label in labels))
        finally:
            window.shutdown()

    def test_recorder_status_uses_standard_footer_status_label(self):
        window = self._window_on_recorder_tab()
        try:
            self.assertIn("Idle", window.status_label_multi_source_recorder_tab.text())
            window.multi_source_recorder_widget.status_label.setText("Recording")
            window.update_single_workflow_availability()

            self.assertIn("Recording", window.status_label_multi_source_recorder_tab.text())
        finally:
            window.shutdown()

    def test_recorder_recording_uses_active_green_app_theme(self):
        window = self._window_on_recorder_tab()
        try:
            window.multi_source_recorder_widget.status_label.setText("Recording")
            window.update_single_workflow_availability()
            window.update_all_button_styles()
            window.update_highlight_colors()

            self.assertIn("#92cb4f", window.current_button_style)
            self.assertIn("#92cb4f", window.tabs.styleSheet())
            self.assertIn("GREEN", window.get_icon_path("INFO").upper())
        finally:
            window.shutdown()

    def test_stopping_a_recording_returns_the_start_button_and_app_to_teal(self):
        window = self._window_on_recorder_tab()
        try:
            recorder = window.multi_source_recorder_widget
            recorder.status_label.setText("Recording")
            recorder._notify_workflow_availability_change()
            self.assertIn("#92cb4f", window.current_button_style)
            self.assertIn("#92cb4f", window.tabs.styleSheet())

            # What stop_recording() does once the last ffmpeg has exited.
            recorder.status_label.setText("Not recording")
            recorder._notify_workflow_availability_change()

            self.assertEqual(window.start_button.text(), "Start Recording")
            self.assertIn("#43a296", window.start_button.styleSheet())
            self.assertNotIn("#92cb4f", window.start_button.styleSheet())
            self.assertIn("#43a296", window.current_button_style)
            self.assertIn("#43a296", window.tabs.styleSheet())
            self.assertNotIn("GREEN", window.get_icon_path("INFO").upper())
        finally:
            window.shutdown()

    def test_recorder_starting_status_uses_standard_footer_status_label(self):
        window = self._window_on_recorder_tab()
        try:
            window.multi_source_recorder_widget.status_label.setText("Starting recording...")
            window.update_single_workflow_availability()

            self.assertIn("Starting", window.status_label_multi_source_recorder_tab.text())
        finally:
            window.shutdown()

    def test_recorder_failure_status_uses_standard_footer_status_label(self):
        window = self._window_on_recorder_tab()
        try:
            window.multi_source_recorder_widget.status_label.setText("Recording failed - check camera availability")
            window.update_single_workflow_availability()

            self.assertIn("Recording failed", window.status_label_multi_source_recorder_tab.text())
        finally:
            window.shutdown()

    def test_global_record_button_disables_while_recording_is_stopping(self):
        window = self._window_on_recorder_tab()
        try:
            window.multi_source_recorder_widget.status_label.setText("Stopping...")
            window.update_single_workflow_availability()

            self.assertEqual(window.start_button.text(), "Stopping...")
            self.assertFalse(window.start_button.isEnabled())
        finally:
            window.shutdown()

    def test_global_record_button_disables_while_recording_is_starting(self):
        window = self._window_on_recorder_tab()
        try:
            window.multi_source_recorder_widget.status_label.setText("Starting recording...")
            window.update_single_workflow_availability()

            self.assertEqual(window.start_button.text(), "Starting...")
            self.assertFalse(window.start_button.isEnabled())
        finally:
            window.shutdown()

    def test_game_icon_is_added_to_recorder_footer_with_other_footers(self):
        window = self._window_on_recorder_tab()
        try:
            window.add_game_icons()

            self.assertEqual(len(window.game_icon_labels), len(window.footer_lock_labels))
        finally:
            window.shutdown()


if __name__ == "__main__":
    unittest.main()
