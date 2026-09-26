"""VideoConverterApp.run_command_request: what the MRCmd-style switches do."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication

from ui.main_window import VideoConverterApp
from utils.command_line import parse_command_switches


class CommandRequestWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        window = VideoConverterApp()
        window.settings.setdefault("visible_tool_tabs", {})
        window.settings["visible_tool_tabs"]["multi_source_recorder"] = False
        window.apply_tool_tab_visibility()
        self.addCleanup(window.shutdown)
        return window

    def _run(self, window, *argv):
        return window.run_command_request(parse_command_switches(list(argv)))

    def test_record_switch_shows_the_recorder_tab_and_starts_recording(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        calls = []

        def fake_start():
            calls.append("start")
            recorder.status_label.setText("Starting recording...")

        recorder.start_recording = fake_start
        ok, message = self._run(window, "/R")

        self.assertEqual(calls, ["start"])
        self.assertTrue(ok, message)
        self.assertIs(window.tabs.currentWidget(), window.multi_source_recorder_tab_scroll)
        self.assertTrue(window.tabs.isTabVisible(window.tabs.indexOf(window.multi_source_recorder_tab_scroll)))

    def test_record_while_already_recording_is_not_an_error_and_does_not_restart(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        recorder.status_label.setText("Recording")
        recorder.start_recording = lambda: self.fail("must not restart")
        ok, message = self._run(window, "/R")
        self.assertTrue(ok)
        self.assertIn("already", message)

    def test_record_that_does_not_start_is_reported_as_an_error(self):
        window = self._window()
        window.multi_source_recorder_widget.start_recording = lambda: None   # e.g. no sources enabled
        ok, message = self._run(window, "/R")
        self.assertFalse(ok)
        self.assertIn("did not start", message)

    def test_record_is_refused_while_locked_or_converting(self):
        window = self._window()
        window.multi_source_recorder_widget.start_recording = lambda: self.fail("must not start")
        window.locked = True
        ok, message = self._run(window, "/R")
        self.assertFalse(ok)
        self.assertIn("locked", message)

        window.locked = False
        window.running = True
        ok, message = self._run(window, "/R")
        self.assertFalse(ok)
        self.assertIn("conversion", message)

    def test_stop_switch_stops_a_running_recording(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        recorder.status_label.setText("Recording")
        calls = []
        recorder.stop_recording = lambda: calls.append("stop")
        ok, _message = self._run(window, "/S")
        self.assertTrue(ok)
        self.assertEqual(calls, ["stop"])

    def test_stop_when_not_recording_is_a_no_op_success(self):
        window = self._window()
        window.multi_source_recorder_widget.stop_recording = lambda: self.fail("nothing to stop")
        ok, message = self._run(window, "/S")
        self.assertTrue(ok)
        self.assertIn("not recording", message)

    def test_base_name_switch_sets_the_recording_base_name(self):
        window = self._window()
        ok, _message = self._run(window, "/B=Trial_07")
        self.assertTrue(ok)
        self.assertEqual(window.multi_source_recorder_widget.base_name_edit.text(), "Trial_07")

    def test_preset_switch_loads_a_named_preset(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        loaded = []
        with tempfile.TemporaryDirectory() as presets_dir:
            recorder.recorder_presets_dir = lambda: presets_dir
            with open(os.path.join(presets_dir, "Lab_1.json"), "w", encoding="utf-8") as handle:
                json.dump({}, handle)
            recorder.load_named_recorder_preset = lambda name: loaded.append(name)
            ok, message = self._run(window, "/C=Lab 1")
        self.assertTrue(ok, message)
        self.assertEqual(loaded, ["Lab 1"])

    def test_preset_switch_accepts_a_path_to_a_json_file(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        applied = []
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "Two cameras.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"base_name": "FromFile"}, handle)
            with patch.object(recorder, "apply_recorder_settings", lambda settings, **_kw: applied.append(settings)), \
                    patch.object(recorder, "refresh_previews_from_sources", lambda: None), \
                    patch.object(recorder, "save_current_recorder_settings", lambda: None):
                ok, message = self._run(window, f"/C={path}")
        self.assertTrue(ok, message)
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0].get("base_name"), "FromFile")

    def test_missing_preset_is_an_error_and_stops_the_request(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        recorder.start_recording = lambda: self.fail("must not record with the wrong preset")
        with tempfile.TemporaryDirectory() as presets_dir:
            recorder.recorder_presets_dir = lambda: presets_dir
            ok, message = self._run(window, "/C=Nope", "/R")
        self.assertFalse(ok)
        self.assertIn("Nope", message)

    def test_close_switch_stops_recording_then_quits_after_the_reply(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        recorder.status_label.setText("Recording")
        calls = []
        recorder.stop_recording = lambda: calls.append("stop")
        window.quit_application = lambda: calls.append("quit")
        scheduled = []
        window._schedule = lambda msec, fn: scheduled.append((msec, fn))

        ok, _message = self._run(window, "/X")

        self.assertTrue(ok)
        self.assertEqual(calls, ["stop"])          # quit is deferred so the reply gets out first
        self.assertEqual(len(scheduled), 1)
        scheduled[0][1]()
        self.assertEqual(calls, ["stop", "quit"])

    def test_launch_switch_raises_the_window(self):
        window = self._window()
        raised = []
        window.activateWindow = lambda: raised.append(True)
        ok, _message = self._run(window, "/E")
        self.assertTrue(ok)
        self.assertEqual(raised, [True])

    def test_steps_report_what_they_did(self):
        window = self._window()
        recorder = window.multi_source_recorder_widget
        recorder.start_recording = lambda: recorder.status_label.setText("Recording")
        ok, message = self._run(window, "/B=Run", "/R")
        self.assertTrue(ok)
        self.assertIn("base name", message)
        self.assertIn("recording", message)


if __name__ == "__main__":
    unittest.main()
