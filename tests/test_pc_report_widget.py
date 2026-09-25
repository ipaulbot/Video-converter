import inspect
import unittest
from unittest.mock import Mock, patch

from PyQt5.QtCore import QAbstractAnimation
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QSizePolicy

from ui import theme
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

        def fake_run_all(options, progress_cb, cancel):
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
                "updates": False,
                "programs": True,
                "security": False,
                "redact": True,
            },
        )
        self.assertEqual(progress, ["Operating System (1/40)", "Rendering HTML..."])

    def test_shutdown_is_a_noop_without_a_worker(self):
        widget = PCReportWidget()
        widget.shutdown()
        self.assertIsNone(widget.worker)

    def test_worker_cancel_sets_its_event(self):
        worker = _PCReportWorker({})
        self.assertFalse(worker.cancel_event.is_set())
        worker.cancel()
        self.assertTrue(worker.cancel_event.is_set())

    def test_shutdown_cancels_and_waits_for_a_running_worker(self):
        widget = PCReportWidget()
        worker = Mock()
        worker.isRunning.return_value = True
        widget.worker = worker
        widget.shutdown()
        worker.cancel.assert_called_once_with()
        worker.requestInterruption.assert_called_once_with()
        worker.wait.assert_called_once_with(5000)

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

    def test_no_hint_text_and_placeholder_instead_of_prefilled_log(self):
        widget = PCReportWidget()
        texts = [label.text() for label in widget.findChildren(QLabel)]
        self.assertFalse(any(t.startswith("Tip:") for t in texts), texts)
        self.assertEqual(widget.output.toPlainText(), "")
        self.assertEqual(widget.output.placeholderText(), "Report progress appears here.")

    def test_secondary_actions_are_links_and_generate_is_compact(self):
        widget = PCReportWidget()
        for button in (widget.btn_open, widget.btn_folder, widget.btn_admin):
            self.assertTrue(button.property("skipGlobalStyle"), button.text())
            self.assertIn("text-decoration: underline", button.styleSheet(), button.text())
        self.assertTrue(widget.btn_run.property("skipGlobalStyle"))
        self.assertIn("min-height: 24px", widget.btn_run.styleSheet())
        self.assertEqual(widget.btn_open.text(), "Open report")
        self.assertEqual(widget.btn_folder.text(), "Open folder")
        self.assertEqual(widget.btn_admin.text(), "Run as administrator")

    def test_secondary_actions_carry_glyphs_that_follow_the_skin(self):
        widget = PCReportWidget()
        expected = {"report": widget.btn_open, "folder_open": widget.btn_folder, "shield": widget.btn_admin}
        for glyph, button in expected.items():
            self.assertEqual(button.property("glyph"), glyph, button.text())
            self.assertFalse(button.icon().isNull(), button.text())
        self.assertTrue(widget.btn_run.icon().isNull())
        before = widget.btn_open.icon().pixmap(16).toImage()
        widget.update_button_style(locked=True)
        after = widget.btn_open.icon().pixmap(16).toImage()
        self.assertNotEqual(before, after)

    def test_admin_link_hidden_when_already_elevated(self):
        with patch.object(PCReportWidget, "is_elevated", staticmethod(lambda: True)):
            widget = PCReportWidget()
            self.assertTrue(widget.btn_admin.isHidden())
        with patch.object(PCReportWidget, "is_elevated", staticmethod(lambda: False)):
            widget = PCReportWidget()
            self.assertFalse(widget.btn_admin.isHidden())

    def test_heart_pulses_while_running_and_settles_on_finish(self):
        widget = PCReportWidget()
        with patch("ui.pc_report_dialog._PCReportWorker") as worker_cls:
            worker = worker_cls.return_value
            worker.isRunning.return_value = False
            widget.on_run()
            self.assertIsNotNone(widget.heart_anim)
            self.assertEqual(widget.heart_anim.state(), QAbstractAnimation.Running)
            self.assertEqual(widget.heart_anim.loopCount(), -1)
            self.assertFalse(widget.heart_label.isHidden())
        widget._on_worker_finished("<html></html>", "{}")
        self.assertEqual(widget.heart_anim.state(), QAbstractAnimation.Stopped)
        self.assertEqual(widget.heart_effect.opacity(), 1.0)
        widget._settle_heart(success=False)
        self.assertTrue(widget.heart_label.isHidden())

    def test_heart_goes_dark_when_the_worker_reports_failure(self):
        widget = PCReportWidget()
        widget._start_heart()
        widget._on_worker_finished("<html><h1>PC Report Failed</h1></html>", "")
        self.assertTrue(widget.heart_label.isHidden())

    def test_relaunch_elevated_releases_guard_and_quits_on_success(self):
        widget = PCReportWidget()
        guard = Mock()
        app = QApplication.instance()
        app.single_instance_memory = guard
        quit_fn = Mock()
        try:
            with patch.object(PCReportWidget, "window", return_value=Mock(
                    running=False, is_converting=False,
                    is_recorder_recording=lambda: False,
                    quit_application=quit_fn)), \
                    patch("ui.pc_report_dialog.ctypes") as fake_ctypes:
                fake_ctypes.windll.shell32.ShellExecuteW.return_value = 42
                widget.relaunch_elevated()
            verb = fake_ctypes.windll.shell32.ShellExecuteW.call_args[0][1]
            self.assertEqual(verb, "runas")
            guard.detach.assert_called_once()
            guard.create.assert_not_called()
            quit_fn.assert_called_once()
        finally:
            del app.single_instance_memory

    def test_relaunch_elevated_restores_guard_when_uac_is_refused(self):
        widget = PCReportWidget()
        guard = Mock()
        app = QApplication.instance()
        app.single_instance_memory = guard
        quit_fn = Mock()
        try:
            with patch.object(PCReportWidget, "window", return_value=Mock(
                    running=False, is_converting=False,
                    is_recorder_recording=lambda: False,
                    quit_application=quit_fn)), \
                    patch("ui.pc_report_dialog.ctypes") as fake_ctypes:
                fake_ctypes.windll.shell32.ShellExecuteW.return_value = 5  # ERROR_ACCESS_DENIED
                widget.relaunch_elevated()
            guard.detach.assert_called_once()
            guard.create.assert_called_once_with(1)
            quit_fn.assert_not_called()
            self.assertIn("cancelled or refused", widget.status_label.text())
        finally:
            del app.single_instance_memory

    def test_relaunch_elevated_refuses_while_recording_or_converting(self):
        widget = PCReportWidget()
        with patch.object(PCReportWidget, "window", return_value=Mock(
                running=True, is_converting=False,
                is_recorder_recording=lambda: False)), \
                patch("ui.pc_report_dialog.ctypes") as fake_ctypes:
            widget.relaunch_elevated()
        fake_ctypes.windll.shell32.ShellExecuteW.assert_not_called()
        self.assertIn("Stop the current conversion or recording", widget.status_label.text())

    def test_layout_mode_resizes_logo(self):
        widget = PCReportWidget()
        widget.apply_layout_mode(theme.FULL)
        self.assertEqual(widget.logo_label.pixmap().width(), theme.FULL.pc_report_logo_w)
        widget.apply_layout_mode(theme.COMPACT)
        self.assertEqual(widget.logo_label.pixmap().width(), theme.COMPACT.pc_report_logo_w)

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
