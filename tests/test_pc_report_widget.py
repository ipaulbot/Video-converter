import inspect
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication, QDialog, QSizePolicy

from ui.main_window import VideoConverterApp
from ui.pc_report_dialog import PCReportWidget, _PCReportWorker


class PCReportWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    # No tearDown: conftest's reap_hidden_top_level_widgets calls shutdown()
    # and destroys this test's windows. What used to be here called shutdown()
    # but never deleted anything, so every VideoConverterApp built below
    # stayed alive for the rest of the session.

    def test_embedded_pc_report_widget_is_not_a_dialog(self):
        widget = PCReportWidget()

        self.assertNotIsInstance(widget, QDialog)

    def test_embedded_pc_report_widget_uses_flexible_size_policy(self):
        widget = PCReportWidget()

        self.assertEqual(widget.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)
        self.assertEqual(widget.sizePolicy().verticalPolicy(), QSizePolicy.Expanding)

    def test_default_report_path_uses_browser_style_unique_names(self):
        widget = PCReportWidget()

        path = widget.default_report_path()

        self.assertTrue(path.endswith(".html"))
        self.assertIn("PC_Report", path)

    def test_worker_uses_registry_options_and_section_progress(self):
        worker = _PCReportWorker(
            {
                "updates": False,
                "programs": True,
                "security": False,
                "redact": True,
            }
        )
        progress = []
        worker.progress.connect(progress.append)

        def fake_run_all(options, progress_cb):
            progress_cb("Operating System", 1, 40)
            return {"total_seconds": 0.1}, {}, {}

        with (
            patch("ui.pc_report_dialog.run_all", side_effect=fake_run_all) as run_all,
            patch("ui.pc_report_dialog.render_html", return_value="<html></html>"),
        ):
            worker._generate()

        self.assertEqual(
            run_all.call_args.args[0],
            {
                "installed_updates": False,
                "installed_programs": True,
                "security": False,
            },
        )
        self.assertEqual(progress, ["Operating System (1/40)", "Rendering HTML..."])

    def test_worker_failure_page_is_escaped_redacted_and_logged(self):
        worker = _PCReportWorker({"redact": True})
        pages = []
        worker.finished.connect(lambda html, _json: pages.append(html))
        message = r"<b>boom</b> & C:\Users\jane\AppData\report.html missing"

        with (
            patch.object(_PCReportWorker, "_generate", side_effect=RuntimeError(message)),
            patch("ui.pc_report_dialog.logger") as logger,
        ):
            worker.run()

        page = pages[0]
        self.assertNotIn("jane", page)
        self.assertNotIn("<b>boom</b>", page)
        self.assertIn("&lt;b&gt;boom&lt;/b&gt;", page)
        self.assertIn("&amp;", page)
        self.assertIn("<h1>PC Report Failed</h1>", page)
        logger.exception.assert_called_once()

    def test_worker_failure_page_keeps_paths_when_redaction_is_off(self):
        worker = _PCReportWorker({"redact": False})
        pages = []
        worker.finished.connect(lambda html, _json: pages.append(html))

        with (
            patch.object(_PCReportWorker, "_generate", side_effect=RuntimeError(r"C:\Users\jane\x")),
            patch("ui.pc_report_dialog.logger"),
        ):
            worker.run()

        self.assertIn("jane", pages[0])

    def test_main_window_pc_report_entrypoint_stays_embedded(self):
        source = inspect.getsource(VideoConverterApp.open_pc_report_dialog)

        self.assertNotIn("PCReportDialog", source)
        self.assertNotIn("exec_", source)
        self.assertIn("pc_report_widget", source)

    def test_main_window_new_tool_tabs_have_standard_footer_icons(self):
        window = VideoConverterApp()
        try:
            self.assertGreaterEqual(len(window.footer_lock_labels), 6)
            self.assertGreaterEqual(len(window.footer_file_labels), 6)
            self.assertGreaterEqual(len(window.footer_broom_labels), 6)
        finally:
            window.shutdown()

    def test_main_window_registers_media_player_tool_tab(self):
        window = VideoConverterApp()
        try:
            self.assertIn("media_player", window.tool_tab_widgets)
            self.assertTrue(hasattr(window, "media_player_widget"))
        finally:
            window.shutdown()

    def test_recording_tab_lock_and_layout_preview(self):
        window = VideoConverterApp()
        try:
            # Recording grays out every other tab but keeps the recorder usable.
            window.multi_source_recorder_widget.status_label.setText("Recording")
            window._apply_recording_tab_lock()
            recorder_index = window.tabs.indexOf(window.multi_source_recorder_tab_scroll)
            self.assertTrue(window.tabs.isTabEnabled(recorder_index))
            other_indices = [i for i in range(window.tabs.count()) if i != recorder_index]
            self.assertTrue(other_indices)
            for index in other_indices:
                self.assertFalse(window.tabs.isTabEnabled(index))

            # Stopping recording re-enables everything.
            window.multi_source_recorder_widget.status_label.setText("Not recording")
            window._apply_recording_tab_lock()
            for index in range(window.tabs.count()):
                self.assertTrue(window.tabs.isTabEnabled(index))

            # The sidebar shows a rendered layout schematic for the recorder.
            window.multi_source_recorder_widget.output_mode_combo.setCurrentText("Combined grid")
            window._show_recorder_layout_preview()
            self.assertTrue(window._showing_recorder_layout_preview)
            self.assertIsNotNone(window.preview_label.pixmap())
            self.assertFalse(window.preview_label.pixmap().isNull())
        finally:
            window.shutdown()


if __name__ == "__main__":
    unittest.main()
