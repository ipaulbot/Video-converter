import unittest

from PyQt5.QtWidgets import QApplication

from ui.main_window import VideoConverterApp


class SingleActiveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window_on_recorder_tab(self):
        window = VideoConverterApp()
        recorder_index = window.tabs.indexOf(window.multi_source_recorder_tab_scroll)
        window.tabs.setCurrentIndex(recorder_index)
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

    def test_recorder_controls_disable_while_conversion_workflow_is_busy(self):
        window = self._window_on_recorder_tab()
        try:
            window.running = True
            window.update_single_workflow_availability()

            self.assertFalse(window.multi_source_recorder_widget.isEnabled())
            self.assertIn("conversion", window.multi_source_recorder_widget.status_label.text().lower())
        finally:
            window.shutdown()

    def test_recorder_status_uses_standard_footer_status_label(self):
        window = self._window_on_recorder_tab()
        try:
            self.assertIn("Not recording", window.status_label_multi_source_recorder_tab.text())
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
