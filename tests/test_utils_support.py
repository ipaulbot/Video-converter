"""Tests for the small support modules: paths, resources, subprocess_helpers,
system_state and log_bus.

These are short and mostly pure, but three of them decide where the app's data
lives and one persists the user's saved game state, so "small" is not the same
as "does not matter".

The data directory is redirected per test rather than relying on conftest's
session-wide redirect, so a test can assert what a fresh state file does.
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication

from ui.log_bus import LogBus
from utils import paths, resources, subprocess_helpers, system_state

app = QApplication.instance() or QApplication([])


class _DataDir:
    """Point NVC's data directory at a fresh temp folder for one test."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._previous = os.environ.get("NVC_DATA_DIR")
        os.environ["NVC_DATA_DIR"] = self._tmp.name
        self.path = self._tmp.name
        return self

    def __exit__(self, *exc):
        if self._previous is None:
            os.environ.pop("NVC_DATA_DIR", None)
        else:
            os.environ["NVC_DATA_DIR"] = self._previous
        self._tmp.cleanup()


class PathsTests(unittest.TestCase):
    def test_the_override_wins_and_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nested", "data")
            with patch.dict(os.environ, {"NVC_DATA_DIR": target}):
                self.assertEqual(paths.get_data_dir(), target)
                self.assertTrue(os.path.isdir(target))

    def test_a_subfolder_is_created_beneath_it(self):
        with _DataDir() as d:
            logs = paths.get_data_dir("logs")
            self.assertEqual(logs, os.path.join(d.path, "logs"))
            self.assertTrue(os.path.isdir(logs))

    def test_calling_it_twice_is_stable(self):
        with _DataDir():
            self.assertEqual(paths.get_data_dir(), paths.get_data_dir())

    def test_without_an_override_it_uses_a_per_user_location(self):
        env = {k: v for k, v in os.environ.items() if k != "NVC_DATA_DIR"}
        with patch.dict(os.environ, env, clear=True):
            base = paths.get_data_dir()
        self.assertTrue(base.endswith("NVC"), base)
        self.assertTrue(os.path.isabs(base))

    def test_the_windows_fallback_is_used_when_appdata_is_unset(self):
        if os.name != "nt":
            self.skipTest("Windows-only fallback")
        env = {k: v for k, v in os.environ.items()
               if k not in ("NVC_DATA_DIR", "APPDATA")}
        with patch.dict(os.environ, env, clear=True):
            base = paths.get_data_dir()
        self.assertIn("Roaming", base)


class ResourcePathTests(unittest.TestCase):
    def test_it_resolves_relative_to_the_working_directory(self):
        # The relative part is joined verbatim, so its separators survive --
        # callers pass forward slashes throughout the app and Windows accepts
        # them.
        result = resources.resource_path("graphics/INFO.ico")
        self.assertTrue(os.path.isabs(result))
        self.assertTrue(result.endswith("graphics/INFO.ico"), result)
        self.assertTrue(os.path.exists(result), "the icon should resolve")

    def test_it_uses_the_pyinstaller_bundle_directory_when_frozen(self):
        """_MEIPASS is where PyInstaller extracts bundled data at runtime."""
        import sys
        with patch.object(sys, "_MEIPASS", os.path.join("C:", "bundle"),
                          create=True):
            result = resources.resource_path("help_document.html")
        self.assertTrue(result.startswith(os.path.join("C:", "bundle")))

    def test_a_nested_path_is_preserved(self):
        result = resources.resource_path("docs/help/x.pdf")
        self.assertTrue(result.endswith("docs/help/x.pdf"), result)


class SubprocessHelperTests(unittest.TestCase):
    def test_it_returns_a_pair(self):
        startupinfo, creationflags = subprocess_helpers.get_subprocess_startupinfo()
        self.assertIsInstance(creationflags, int)
        if os.name == "nt":
            self.assertIsNotNone(startupinfo)
        else:
            self.assertIsNone(startupinfo)
            self.assertEqual(creationflags, 0)

    def test_on_windows_it_hides_the_console(self):
        if os.name != "nt":
            self.skipTest("Windows-only flags")
        import subprocess
        startupinfo, creationflags = subprocess_helpers.get_subprocess_startupinfo()
        self.assertTrue(startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertTrue(creationflags & subprocess.CREATE_NO_WINDOW)

    def test_the_timeouts_are_ordered_sensibly(self):
        # A metadata probe should not be allowed longer than a whole remux.
        self.assertLess(subprocess_helpers.FFPROBE_TIMEOUT,
                        subprocess_helpers.FFMPEG_RENDER_TIMEOUT)
        self.assertLess(subprocess_helpers.FFMPEG_RENDER_TIMEOUT,
                        subprocess_helpers.FFMPEG_REMUX_TIMEOUT)

    def test_every_timeout_is_a_positive_number_of_seconds(self):
        for name in ("FFPROBE_TIMEOUT", "FFMPEG_RENDER_TIMEOUT",
                     "FFMPEG_REMUX_TIMEOUT"):
            value = getattr(subprocess_helpers, name)
            self.assertIsInstance(value, int, name)
            self.assertGreater(value, 0, name)


class SystemStateTests(unittest.TestCase):
    def test_a_fresh_install_has_no_state(self):
        with _DataDir():
            self.assertFalse(system_state.get_game_unlocked())
            self.assertEqual(system_state.get_high_scores(), [])
            self.assertEqual(system_state.get_best_level(), 0)

    def test_the_unlock_flag_round_trips(self):
        with _DataDir():
            system_state.set_game_unlocked(True)
            self.assertTrue(system_state.get_game_unlocked())
            system_state.set_game_unlocked(False)
            self.assertFalse(system_state.get_game_unlocked())

    def test_the_best_level_round_trips(self):
        with _DataDir():
            system_state.set_best_level(7)
            self.assertEqual(system_state.get_best_level(), 7)

    def test_writing_one_key_preserves_the_others(self):
        with _DataDir():
            system_state.set_game_unlocked(True)
            system_state.set_best_level(4)
            system_state.set_high_scores([("abc", 100, 2)])
            self.assertTrue(system_state.get_game_unlocked())
            self.assertEqual(system_state.get_best_level(), 4)
            self.assertEqual(len(system_state.get_high_scores()), 1)

    def test_initials_are_normalised_to_three_upper_case_letters(self):
        with _DataDir():
            system_state.set_high_scores([("paulhamblin", 10, 1)])
            self.assertEqual(system_state.get_high_scores()[0][0], "PAU")

    def test_scores_and_levels_are_stored_as_integers(self):
        with _DataDir():
            system_state.set_high_scores([("abc", "250", "3")])
            name, score, level = system_state.get_high_scores()[0]
            self.assertEqual((score, level), (250, 3))

    # -- corrupted state -------------------------------------------------
    def _write_raw(self, directory, payload):
        path = os.path.join(directory, system_state.SYSTEM_FILE_NAME)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(payload)

    def test_a_corrupt_state_file_reads_as_empty(self):
        with _DataDir() as d:
            self._write_raw(d.path, "{not json")
            self.assertFalse(system_state.get_game_unlocked())
            self.assertEqual(system_state.get_high_scores(), [])
            self.assertEqual(system_state.get_best_level(), 0)

    def test_a_non_numeric_best_level_reads_as_zero(self):
        with _DataDir() as d:
            self._write_raw(d.path, json.dumps({"best_level": "lots"}))
            self.assertEqual(system_state.get_best_level(), 0)

    def test_a_malformed_entry_does_not_discard_the_valid_scores(self):
        """One bad row used to wipe the whole table.

        get_high_scores wrapped the entire loop in a single try, so a row with
        a non-numeric score returned [] -- silently losing every other score
        the user had earned.
        """
        with _DataDir() as d:
            self._write_raw(d.path, json.dumps({"high_scores": [
                ["AAA", 300, 5],
                ["BBB", "not-a-number", 2],   # the bad row
                ["CCC", 100, 1],
            ]}))
            scores = system_state.get_high_scores()
            self.assertEqual([s[0] for s in scores], ["AAA", "CCC"])

    def test_short_rows_are_skipped(self):
        with _DataDir() as d:
            self._write_raw(d.path, json.dumps({"high_scores": [
                ["AAA", 300],            # missing the level
                ["BBB", 200, 3],
            ]}))
            self.assertEqual([s[0] for s in system_state.get_high_scores()],
                             ["BBB"])

    def test_a_non_list_high_scores_value_reads_as_empty(self):
        with _DataDir() as d:
            self._write_raw(d.path, json.dumps({"high_scores": "nonsense"}))
            self.assertEqual(system_state.get_high_scores(), [])

    def test_an_unwritable_directory_does_not_raise(self):
        # Persistence is best effort: losing a high score must not crash the
        # game mid-play.
        with _DataDir():
            with patch("builtins.open", side_effect=PermissionError("read-only")):
                system_state.set_best_level(9)   # must not propagate


class LogBusTests(unittest.TestCase):
    """The log pipeline: a bounded buffer drained on a timer."""

    def test_appended_lines_come_back_in_order(self):
        bus = LogBus()
        for line in ("one", "two", "three"):
            bus.append(line)
        self.assertEqual(bus.drain(), ["one", "two", "three"])

    def test_draining_empties_the_buffer(self):
        bus = LogBus()
        bus.append("x")
        bus.drain()
        self.assertEqual(bus.drain(), [])

    def test_a_drain_is_capped_so_the_ui_is_not_flooded(self):
        bus = LogBus()
        for i in range(1200):
            bus.append(str(i))
        first = bus.drain(max_items=500)
        self.assertEqual(len(first), 500)
        self.assertEqual(first[0], "0", "oldest lines should drain first")
        self.assertEqual(len(bus.drain(max_items=500)), 500)

    def test_the_buffer_is_bounded_so_a_long_run_cannot_exhaust_memory(self):
        bus = LogBus(maxlen=10)
        for i in range(50):
            bus.append(str(i))
        drained = bus.drain(max_items=100)
        self.assertEqual(len(drained), 10)
        self.assertEqual(drained[-1], "49", "the newest lines should survive")

    def test_draining_an_empty_bus_returns_empty(self):
        self.assertEqual(LogBus().drain(), [])

    def test_delivery_hands_batches_to_the_receiver(self):
        bus = LogBus()
        received = []
        bus.append("a")
        bus.append("b")
        bus._emit_batched(received.extend)
        self.assertEqual(received, ["a", "b"])

    def test_delivery_does_nothing_when_there_is_nothing_to_send(self):
        bus = LogBus()
        calls = []
        bus._emit_batched(calls.append)
        self.assertEqual(calls, [], "an empty batch should not be delivered")

    def test_a_receiver_that_raises_falls_back_to_the_signal(self):
        """The receiver is a UI slot, so it can be gone by delivery time."""
        bus = LogBus()
        emitted = []
        bus.lines_ready.connect(emitted.append)
        bus.append("a")

        def hostile(_lines):
            raise RuntimeError("the widget is gone")

        bus._emit_batched(hostile)
        self.assertEqual(emitted, [["a"]])

    def test_start_delivery_arms_a_timer_and_is_idempotent(self):
        bus = LogBus()
        bus.start_delivery(lambda _lines: None, interval_ms=50)
        self.assertTrue(bus._timer.isActive())
        bus.start_delivery(lambda _lines: None, interval_ms=50)
        self.assertTrue(bus._timer.isActive())
        bus._timer.stop()

    def test_the_delivery_interval_has_a_floor(self):
        # A 0 ms timer would spin the event loop.
        bus = LogBus()
        bus.start_delivery(lambda _lines: None, interval_ms=0)
        self.assertGreaterEqual(bus._timer.interval(), 10)
        bus._timer.stop()


if __name__ == "__main__":
    unittest.main()
