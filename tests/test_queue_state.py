"""Tests for conversion/queue_state.py.

The admission rules used to be four inline `if` statements in the middle of
convert_file, only reachable by building the whole main window. They decide
whether a user's file gets converted or silently ignored, so they are worth
testing directly.
"""
import os
import unittest

from conversion.queue_state import Admission, ConversionQueueState


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.q = ConversionQueueState()

    def test_accepted_while_running_and_unlocked(self):
        self.assertIs(self.q.admit("a.mov", locked=False, running=True),
                      Admission.OK)

    def test_refused_while_locked(self):
        self.assertIs(self.q.admit("a.mov", locked=True, running=True),
                      Admission.LOCKED)

    def test_refused_while_not_running(self):
        self.assertIs(self.q.admit("a.mov", locked=False, running=False),
                      Admission.NOT_RUNNING)

    def test_refused_outside_the_allowed_window(self):
        self.assertIs(
            self.q.admit("a.mov", locked=False, running=True,
                         within_allowed_time=False),
            Admission.OUTSIDE_TIME)

    def test_refused_when_already_in_flight(self):
        self.q.start("a.mov")
        self.assertIs(self.q.admit("a.mov", locked=False, running=True),
                      Admission.DUPLICATE)

    # -- force ----------------------------------------------------------
    def test_force_overrides_the_lock(self):
        self.assertIs(self.q.admit("a.mov", locked=True, running=True, force=True),
                      Admission.OK)

    def test_force_overrides_not_running(self):
        self.assertIs(self.q.admit("a.mov", locked=False, running=False, force=True),
                      Admission.OK)

    def test_force_does_not_override_a_duplicate(self):
        """Two concurrent runs of one file would fight over the output name."""
        self.q.start("a.mov")
        self.assertIs(
            self.q.admit("a.mov", locked=True, running=False, force=True),
            Admission.DUPLICATE)

    def test_lock_is_checked_before_duplicate(self):
        # A locked app should say "locked", not leak that something is running.
        self.q.start("a.mov")
        self.assertIs(self.q.admit("a.mov", locked=True, running=True),
                      Admission.LOCKED)

    def test_accepted_reports_true_only_for_ok(self):
        self.assertTrue(Admission.OK.accepted)
        for other in (Admission.LOCKED, Admission.DUPLICATE,
                      Admission.NOT_RUNNING, Admission.OUTSIDE_TIME):
            self.assertFalse(other.accepted, other)

    def test_the_same_file_named_two_ways_is_one_entry(self):
        self.q.start(os.path.join("C:/media", "clip.mov"))
        self.assertIs(
            self.q.admit("C:/media/./clip.mov", locked=False, running=True),
            Admission.DUPLICATE)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.q = ConversionQueueState()

    def test_the_active_count_tracks_start_and_finish(self):
        self.assertEqual(self.q.active_count, 0)
        self.q.start("a.mov")
        self.q.start("b.mov")
        self.assertEqual(self.q.active_count, 2)
        self.q.finish("a.mov")
        self.assertEqual(self.q.active_count, 1)
        self.q.finish("b.mov")
        self.assertEqual(self.q.active_count, 0)

    def test_the_count_cannot_go_negative(self):
        """The old code decremented a counter and clamped with max(0, ...).

        Deriving the count from the in-flight set makes the clamp unnecessary:
        a stray completion cannot push it below zero.
        """
        self.q.finish("never-started.mov")
        self.assertEqual(self.q.active_count, 0)

    def test_finishing_twice_is_harmless(self):
        self.q.start("a.mov")
        self.q.finish("a.mov")
        self.q.finish("a.mov")
        self.assertEqual(self.q.active_count, 0)

    def test_starting_the_same_file_twice_counts_once(self):
        self.q.start("a.mov")
        self.q.start("a.mov")
        self.assertEqual(self.q.active_count, 1)

    def test_is_converting_reflects_the_queue(self):
        self.assertFalse(self.q.is_converting)
        self.q.start("a.mov")
        self.assertTrue(self.q.is_converting)
        self.q.finish("a.mov")
        self.assertFalse(self.q.is_converting)

    def test_workers_are_returned_for_shutdown_and_dropped_on_finish(self):
        worker = object()
        self.q.start("a.mov", worker)
        self.assertEqual(self.q.workers(), [worker])
        self.q.finish("a.mov")
        self.assertEqual(self.q.workers(), [])

    def test_a_start_without_a_worker_is_allowed(self):
        self.q.start("a.mov")
        self.assertEqual(self.q.workers(), [])
        self.assertTrue(self.q.is_in_flight("a.mov"))


class PerFileLogTests(unittest.TestCase):
    def setUp(self):
        self.q = ConversionQueueState()

    def test_lines_are_buffered_per_conversion(self):
        self.q.start("a.mov")
        self.q.log_line("a.mov", "one")
        self.q.log_line("a.mov", "two")
        self.assertEqual(self.q.lines_for("a.mov"), ["one", "two"])

    def test_finish_returns_and_clears_the_lines(self):
        self.q.start("a.mov")
        self.q.log_line("a.mov", "one")
        self.assertEqual(self.q.finish("a.mov"), ["one"])
        self.assertEqual(self.q.lines_for("a.mov"), [])

    def test_same_basename_in_different_folders_keeps_separate_logs(self):
        """The bug this class fixes.

        handle_conversion_complete matched buffered logs by basename, so
        converting C:/a/clip.mov and C:/b/clip.mov wrote one's log into the
        other's file and deleted the wrong buffer.
        """
        a = os.path.join("C:/a", "clip.mov")
        b = os.path.join("C:/b", "clip.mov")
        self.q.start(a)
        self.q.start(b)
        self.q.log_line(a, "from a")
        self.q.log_line(b, "from b")

        self.assertEqual(self.q.finish(a), ["from a"])
        self.assertEqual(self.q.lines_for(b), ["from b"],
                         "finishing one must not clear the other")
        self.assertEqual(self.q.finish(b), ["from b"])

    def test_no_buffer_leaks_when_a_conversion_finishes(self):
        self.q.start("a.mov")
        self.q.log_line("a.mov", "x")
        self.q.finish("a.mov")
        self.assertEqual(self.q._logs, {}, "the buffer must not be retained")

    def test_logging_for_an_unstarted_file_does_not_raise(self):
        # A worker signal can arrive slightly out of order.
        self.q.log_line("stray.mov", "line")
        self.assertEqual(self.q.lines_for("stray.mov"), ["line"])


class ManualQueueTests(unittest.TestCase):
    def setUp(self):
        self.q = ConversionQueueState()

    def test_taking_drains_the_queue(self):
        self.q.queue_manual("a.mov")
        self.q.queue_manual("b.mov")
        self.assertEqual(self.q.manual_count, 2)
        taken = self.q.take_manual()
        self.assertEqual(len(taken), 2)
        self.assertEqual(self.q.manual_count, 0)

    def test_order_is_preserved_and_duplicates_collapse(self):
        for name in ("a.mov", "b.mov", "a.mov", "c.mov", "b.mov"):
            self.q.queue_manual(name)
        taken = [os.path.basename(p) for p in self.q.take_manual()]
        self.assertEqual(taken, ["a.mov", "b.mov", "c.mov"])

    def test_taking_an_empty_queue_returns_empty(self):
        self.assertEqual(self.q.take_manual(), [])

    def test_duplicates_collapse_across_equivalent_paths(self):
        self.q.queue_manual("C:/media/clip.mov")
        self.q.queue_manual("C:/media/./clip.mov")
        self.assertEqual(len(self.q.take_manual()), 1)


class TeardownTests(unittest.TestCase):
    def test_clear_empties_everything(self):
        q = ConversionQueueState()
        q.start("a.mov", object())
        q.log_line("a.mov", "x")
        q.queue_manual("b.mov")
        q.clear()
        self.assertEqual(q.active_count, 0)
        self.assertEqual(q.workers(), [])
        self.assertEqual(q.manual_count, 0)
        self.assertEqual(q.lines_for("a.mov"), [])


if __name__ == "__main__":
    unittest.main()
