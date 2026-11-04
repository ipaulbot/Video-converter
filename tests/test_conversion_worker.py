"""Tests for conversion/worker.py.

This module owns the conversion subprocess lifecycle -- the riskiest code in
the app -- and had no tests at all. These cover the orchestration in `run()`
and the pure helpers, without launching ffmpeg: the two `perform_*` methods
are stubbed, since what matters here is what `run()` does with their result.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from conversion.worker import ConversionWorker


class _Signal:
    """Records emissions, so a test can assert what the worker reported."""

    def __init__(self):
        self.emissions = []

    def emit(self, *args):
        self.emissions.append(args if len(args) != 1 else args[0])


class _Signals:
    def __init__(self):
        self.log = _Signal()
        self.conversion_complete = _Signal()
        self.progress_update = _Signal()

    @property
    def logs(self):
        return list(self.log.emissions)

    @property
    def completions(self):
        return list(self.conversion_complete.emissions)


class _FakeProcess:
    def __init__(self, running=True):
        self._running = running
        self.terminated = False

    def poll(self):
        return None if self._running else 0

    def terminate(self):
        self.terminated = True
        self._running = False


def _worker(settings=None, file_path="C:/in/clip.mov"):
    return ConversionWorker(file_path, settings or {}, _Signals())


class TimeParsingTests(unittest.TestCase):
    """time_to_seconds parses the timestamps ffmpeg prints on its progress lines."""

    def setUp(self):
        self.w = _worker()

    def test_hours_minutes_seconds(self):
        self.assertAlmostEqual(self.w.time_to_seconds("01:02:03.50"), 3723.5)

    def test_minutes_seconds(self):
        self.assertAlmostEqual(self.w.time_to_seconds("02:03.25"), 123.25)

    def test_bare_seconds(self):
        self.assertAlmostEqual(self.w.time_to_seconds("42.5"), 42.5)

    def test_zero(self):
        self.assertAlmostEqual(self.w.time_to_seconds("00:00:00.00"), 0.0)

    def test_garbage_returns_zero_rather_than_raising(self):
        # Parsed from ffmpeg's stderr, so a malformed line must not kill the job.
        for value in ("", "N/A", "not:a:time", "::", "1:2:3:4"):
            self.assertEqual(self.w.time_to_seconds(value), 0, value)


class OutputPathTests(unittest.TestCase):
    def test_output_takes_the_configured_format_and_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _worker({"output_format": "mp4", "destination_folder": tmp},
                        file_path="C:/in/holiday.mov")
            out = w.get_output_file_path()
            self.assertEqual(os.path.basename(out), "holiday.mp4")
            self.assertEqual(os.path.dirname(out), os.path.abspath(tmp))

    def test_output_format_defaults_to_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = _worker({"destination_folder": tmp}, file_path="C:/in/x.avi")
            self.assertTrue(w.get_output_file_path().endswith("x.mp4"))

    def test_existing_output_is_not_overwritten(self):
        """The browser-style non-overwrite policy, at the point it is applied."""
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "clip.mp4"), "w").close()
            w = _worker({"output_format": "mp4", "destination_folder": tmp},
                        file_path="C:/in/clip.mov")
            self.assertEqual(os.path.basename(w.get_output_file_path()), "clip (1).mp4")


class OutputReadyTests(unittest.TestCase):
    """A conversion is only successful if it actually produced bytes."""

    def setUp(self):
        self.w = _worker()

    def test_missing_file_is_not_ready(self):
        self.assertFalse(self.w._output_file_ready("Z:/gone/nothing.mp4"))

    def test_empty_file_is_not_ready(self):
        # ffmpeg can exit 0 having written a zero-byte file.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.mp4")
            open(path, "w").close()
            self.assertFalse(self.w._output_file_ready(path))

    def test_non_empty_file_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ok.mp4")
            with open(path, "wb") as fh:
                fh.write(b"data")
            self.assertTrue(self.w._output_file_ready(path))


class CancelTests(unittest.TestCase):
    def test_cancel_sets_the_flag_with_no_process_running(self):
        w = _worker()
        w.cancel()
        self.assertTrue(w._cancel_requested)

    def test_cancel_terminates_a_running_process(self):
        w = _worker()
        w._process = _FakeProcess(running=True)
        w.cancel()
        self.assertTrue(w._process.terminated)
        self.assertTrue(any("cancel" in str(m).lower() for m in w.signals.logs))

    def test_cancel_leaves_an_already_finished_process_alone(self):
        w = _worker()
        w._process = _FakeProcess(running=False)
        w.cancel()
        self.assertFalse(w._process.terminated)
        self.assertTrue(w._cancel_requested)

    def test_cancel_survives_a_process_that_raises_on_terminate(self):
        class Hostile(_FakeProcess):
            def terminate(self):
                raise OSError("already reaped")

        w = _worker()
        w._process = Hostile(running=True)
        w.cancel()   # must not propagate
        self.assertTrue(w._cancel_requested)


class BackupAndDeleteTests(unittest.TestCase):
    def test_move_to_backup_creates_the_folder_and_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.mov")
            with open(src, "wb") as fh:
                fh.write(b"x")
            backup = os.path.join(tmp, "backup", "nested")
            w = _worker({"backup_folder": backup})

            self.assertTrue(w.move_to_backup(src))
            self.assertFalse(os.path.exists(src))
            self.assertTrue(os.path.exists(os.path.join(backup, "clip.mov")))

    def test_move_to_backup_reports_failure_instead_of_raising(self):
        w = _worker({"backup_folder": "Z:/no/such/place"})
        self.assertFalse(w.move_to_backup("Z:/gone/missing.mov"))
        self.assertTrue(any("Failed to move" in str(m) for m in w.signals.logs))

    def test_delete_file_removes_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "clip.mov")
            open(path, "w").close()
            w = _worker()
            w.delete_file(path)
            self.assertFalse(os.path.exists(path))
            self.assertTrue(any("Deleted" in str(m) for m in w.signals.logs))

    def test_delete_file_logs_rather_than_raising_when_it_cannot(self):
        w = _worker()
        w.delete_file("Z:/gone/missing.mov")
        self.assertTrue(any("Failed to delete" in str(m) for m in w.signals.logs))


class DurationTests(unittest.TestCase):
    def test_duration_is_zero_when_ffprobe_is_absent(self):
        w = _worker()
        with patch("conversion.worker.resource_path", return_value="Z:/no/ffprobe.exe"):
            self.assertEqual(w.get_duration("C:/in/clip.mov"), 0)


class RunOrchestrationTests(unittest.TestCase):
    """What run() does with the result of a conversion.

    perform_conversion / perform_gif_conversion are stubbed throughout: the
    behaviour under test is the surrounding decision-making, not ffmpeg.
    """

    def _run(self, settings, *, valid=True, success=True, gif=False,
             preprocess_ok=True, raises=None):
        w = _worker(settings)
        w.is_file_valid = lambda: valid
        w.get_output_file_path = lambda: "C:/out/clip.mp4"

        def conversion(_in, _out):
            if raises:
                raise raises
            return success

        w.perform_conversion = conversion
        w.perform_gif_conversion = conversion
        with patch("conversion.worker.preprocess_file", return_value=preprocess_ok), \
             patch("conversion.worker.add_pending_deletion"):
            w.run()
        return w

    # -- the happy path -------------------------------------------------
    def test_success_reports_completion_with_both_paths(self):
        w = self._run({})
        name, ok, info = w.signals.completions[-1]
        self.assertEqual(name, "clip.mov")
        self.assertTrue(ok)
        self.assertEqual(info["output_file"], "C:/out/clip.mp4")
        self.assertEqual(info["source_file"], "C:/in/clip.mov")

    def test_failure_reports_not_ok_and_no_output_path(self):
        w = self._run({}, success=False)
        name, ok, info = w.signals.completions[-1]
        self.assertFalse(ok)
        self.assertNotIn("output_file", info)
        self.assertEqual(info["source_file"], "C:/in/clip.mov")

    def test_gif_output_routes_to_the_two_pass_converter(self):
        calls = []
        w = _worker({"output_format": "GIF"})   # deliberately upper case
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.gif"
        w.perform_conversion = lambda i, o: calls.append("standard") or True
        w.perform_gif_conversion = lambda i, o: calls.append("gif") or True
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        self.assertEqual(calls, ["gif"])

    # -- invalid input --------------------------------------------------
    def test_invalid_file_that_cannot_be_repaired_is_skipped(self):
        w = self._run({}, valid=False, preprocess_ok=False)
        name, ok, info = w.signals.completions[-1]
        self.assertFalse(ok)
        self.assertTrue(any("corrupted or invalid" in str(m) for m in w.signals.logs))
        self.assertTrue(any("Failed to fix" in str(m) for m in w.signals.logs))

    def test_invalid_file_that_is_repaired_continues_to_convert(self):
        w = self._run({}, valid=False, preprocess_ok=True)
        _, ok, _ = w.signals.completions[-1]
        self.assertTrue(ok)

    # -- original-file handling -----------------------------------------
    def test_backup_moves_the_original(self):
        moved = []
        w = _worker({"use_backup": True})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        w.move_to_backup = lambda p: moved.append(p) or True
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        self.assertEqual(moved, ["C:/in/clip.mov"])

    def test_a_failed_backup_is_reported_but_the_job_still_succeeds(self):
        w = _worker({"use_backup": True})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        w.move_to_backup = lambda p: False
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        _, ok, _ = w.signals.completions[-1]
        self.assertTrue(ok, "the conversion itself succeeded")
        self.assertTrue(any("Failed to move" in str(m) for m in w.signals.logs))

    def test_backup_takes_precedence_over_delete(self):
        # Both set: the original must be preserved, not deleted.
        moved, deleted = [], []
        w = _worker({"use_backup": True, "delete_after_conversion": True})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        w.move_to_backup = lambda p: moved.append(p) or True
        w.delete_file = lambda p: deleted.append(p)
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        self.assertEqual(moved, ["C:/in/clip.mov"])
        self.assertEqual(deleted, [])

    def test_delete_with_no_retention_removes_immediately(self):
        deleted = []
        w = _worker({"delete_after_conversion": True, "retention_time": 0})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        w.delete_file = lambda p: deleted.append(p)
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        self.assertEqual(deleted, ["C:/in/clip.mov"])

    def test_nothing_is_deleted_when_the_conversion_failed(self):
        deleted = []
        w = _worker({"delete_after_conversion": True, "retention_time": 0})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: False
        w.delete_file = lambda p: deleted.append(p)
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        self.assertEqual(deleted, [], "a failed conversion must not lose the source")

    # -- retention ------------------------------------------------------
    def test_retention_persists_the_deletion_and_reports_the_date(self):
        w = _worker({"delete_after_conversion": True, "retention_time": 7})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        with patch("conversion.worker.preprocess_file", return_value=True), \
             patch("conversion.worker.add_pending_deletion") as add, \
             patch("conversion.worker.threading.Timer") as timer:
            w.run()

        add.assert_called_once()
        self.assertEqual(add.call_args[0][0], "C:/in/clip.mov")
        _, _, info = w.signals.completions[-1]
        self.assertIn("scheduled_deletion", info)
        # 7 days, in seconds.
        self.assertEqual(timer.call_args[0][0], 7 * 86400)

    def test_the_retention_timer_is_a_daemon(self):
        """Retention runs up to 30 days.

        A non-daemon Timer blocks interpreter exit for its entire delay, so
        closing NVC after a conversion with retention set would hang. The
        deletion is persisted separately, so the timer is best-effort only.
        """
        w = _worker({"delete_after_conversion": True, "retention_time": 30})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        with patch("conversion.worker.preprocess_file", return_value=True), \
             patch("conversion.worker.add_pending_deletion"), \
             patch("conversion.worker.threading.Timer") as timer:
            w.run()
        self.assertTrue(timer.return_value.daemon,
                        "the retention timer must not block interpreter exit")
        timer.return_value.start.assert_called_once()

    def test_a_failure_to_persist_retention_does_not_lose_the_conversion(self):
        w = _worker({"delete_after_conversion": True, "retention_time": 3})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"
        w.perform_conversion = lambda i, o: True
        with patch("conversion.worker.preprocess_file", return_value=True), \
             patch("conversion.worker.add_pending_deletion",
                   side_effect=OSError("disk full")), \
             patch("conversion.worker.threading.Timer"):
            w.run()
        _, ok, _ = w.signals.completions[-1]
        self.assertTrue(ok)

    # -- cancellation ---------------------------------------------------
    def test_cancelling_a_succeeded_job_reports_canceled(self):
        w = _worker({})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"

        def conversion(_i, _o):
            w._cancel_requested = True
            return True

        w.perform_conversion = conversion
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        _, ok, info = w.signals.completions[-1]
        self.assertFalse(ok)
        self.assertEqual(info.get("status"), "canceled")

    def test_cancelling_a_failed_job_also_reports_canceled(self):
        w = _worker({})
        w.is_file_valid = lambda: True
        w.get_output_file_path = lambda: "C:/out/clip.mp4"

        def conversion(_i, _o):
            w._cancel_requested = True
            return False

        w.perform_conversion = conversion
        with patch("conversion.worker.preprocess_file", return_value=True):
            w.run()
        _, ok, info = w.signals.completions[-1]
        self.assertFalse(ok)
        self.assertEqual(info.get("status"), "canceled")

    # -- unexpected failure ---------------------------------------------
    def test_an_unexpected_exception_still_reports_completion(self):
        """The queue would stall forever if run() returned without emitting."""
        w = self._run({}, raises=RuntimeError("ffmpeg exploded"))
        self.assertTrue(w.signals.completions, "run() must always report")
        _, ok, info = w.signals.completions[-1]
        self.assertFalse(ok)
        self.assertEqual(info["source_file"], "C:/in/clip.mov")

    def test_exactly_one_completion_is_emitted_per_run(self):
        # Two emissions would double-count in the queue; none would stall it.
        for kwargs in ({}, {"success": False},
                       {"valid": False, "preprocess_ok": False},
                       {"raises": RuntimeError("x")}):
            w = self._run({}, **kwargs)
            self.assertEqual(len(w.signals.completions), 1, kwargs)

    def test_gpu_conversion_failure_retries_once_with_cpu_encoder(self):
        w = _worker({"use_gpu": True, "gpu_encoder": "nvidia", "video_codec": "libx264"})
        w.get_duration = lambda _p: 1.0
        commands_tried = []

        def fake_run(cmd, _in, _out, _dur):
            commands_tried.append(cmd)
            return len(commands_tried) == 2

        w._run_conversion_command = fake_run
        with patch("conversion.worker.os.path.exists", return_value=True), \
             patch("conversion.ffmpeg_utils.GPU_ENCODERS", {"nvidia": {"h264": "h264_nvenc"}}):
            ok = w.perform_conversion("C:/in/clip.mp4", "C:/out/clip.mp4")

        self.assertTrue(ok)
        self.assertEqual(len(commands_tried), 2)
        self.assertIn("h264_nvenc", commands_tried[0])
        self.assertIn("libx264", commands_tried[1])
        self.assertTrue(any("retrying with CPU encoder" in str(m) for m in w.signals.logs))


if __name__ == "__main__":
    unittest.main()
