"""Tests for utils/retention.py.

This module deletes the user's original video files, on a schedule, at every
startup. It had no tests. A bug here loses data permanently, so the cases
below lean towards "what could destroy something that should have been kept".

Every test redirects the pending-deletions file into a temporary directory;
none of them touch the real one.
"""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from utils import retention


class _Pending:
    """Redirect the pending-deletions file at a temp path for one test."""

    def __init__(self):
        self._tmp = None

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "pending_deletions.json")
        self._patch = patch.object(retention, "_PENDING_FILE", self.path)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()

    def write(self, items):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(items, fh)

    def read(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def make_file(self, name="clip.mov", content=b"data"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(content)
        return path


class ReadWriteTests(unittest.TestCase):
    def test_missing_file_reads_as_empty(self):
        with _Pending():
            self.assertEqual(retention._read_pending(), [])

    def test_corrupt_json_reads_as_empty_rather_than_raising(self):
        # Called at startup; a truncated file must not stop the app.
        with _Pending() as p:
            with open(p.path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            self.assertEqual(retention._read_pending(), [])

    def test_a_null_file_reads_as_empty(self):
        with _Pending() as p:
            with open(p.path, "w", encoding="utf-8") as fh:
                fh.write("null")
            self.assertEqual(retention._read_pending(), [])

    def test_write_then_read_round_trips(self):
        with _Pending():
            retention._write_pending([{"path": "C:/a.mov", "due_utc": 123.0}])
            self.assertEqual(retention._read_pending(),
                             [{"path": "C:/a.mov", "due_utc": 123.0}])

    def test_write_leaves_no_temp_file_behind(self):
        with _Pending() as p:
            retention._write_pending([{"path": "C:/a.mov", "due_utc": 1.0}])
            self.assertFalse(os.path.exists(p.path + ".tmp"))


class ScheduleTests(unittest.TestCase):
    def test_adding_a_deletion_records_path_and_due_time(self):
        with _Pending():
            retention.add_pending_deletion("C:/a.mov", 1000.0)
            items = retention._read_pending()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["path"], "C:/a.mov")
            self.assertEqual(items[0]["due_utc"], 1000.0)

    def test_scheduling_the_same_path_twice_updates_rather_than_duplicates(self):
        with _Pending():
            retention.add_pending_deletion("C:/a.mov", 1000.0)
            retention.add_pending_deletion("C:/a.mov", 2000.0)
            items = retention._read_pending()
            self.assertEqual(len(items), 1, "the entry should be updated, not doubled")
            self.assertEqual(items[0]["due_utc"], 2000.0)

    def test_different_paths_are_kept_separately(self):
        with _Pending():
            retention.add_pending_deletion("C:/a.mov", 1000.0)
            retention.add_pending_deletion("C:/b.mov", 1000.0)
            self.assertEqual(len(retention._read_pending()), 2)

    def test_an_integer_due_time_is_stored_as_a_float(self):
        with _Pending():
            retention.add_pending_deletion("C:/a.mov", 1000)
            self.assertIsInstance(retention._read_pending()[0]["due_utc"], float)


class ProcessTests(unittest.TestCase):
    def test_nothing_pending_deletes_nothing(self):
        with _Pending():
            self.assertEqual(retention.process_pending_deletions(), 0)

    def test_an_overdue_file_is_deleted_and_dropped_from_the_list(self):
        with _Pending() as p:
            target = p.make_file()
            p.write([{"path": target, "due_utc": time.time() - 60}])

            self.assertEqual(retention.process_pending_deletions(), 1)
            self.assertFalse(os.path.exists(target))
            self.assertEqual(retention._read_pending(), [])

    def test_a_file_not_yet_due_is_kept_and_stays_scheduled(self):
        """The single most important case: do not delete early."""
        with _Pending() as p:
            target = p.make_file()
            due = time.time() + 3600
            p.write([{"path": target, "due_utc": due}])

            self.assertEqual(retention.process_pending_deletions(), 0)
            self.assertTrue(os.path.exists(target), "deleted before its due time")
            self.assertEqual(retention._read_pending(),
                             [{"path": target, "due_utc": due}])

    def test_a_due_time_exactly_now_is_treated_as_due(self):
        with _Pending() as p:
            target = p.make_file()
            p.write([{"path": target, "due_utc": time.time()}])
            retention.process_pending_deletions()
            self.assertFalse(os.path.exists(target))

    def test_only_the_overdue_entries_are_processed(self):
        with _Pending() as p:
            old = p.make_file("old.mov")
            new = p.make_file("new.mov")
            p.write([{"path": old, "due_utc": time.time() - 60},
                     {"path": new, "due_utc": time.time() + 3600}])

            retention.process_pending_deletions()
            self.assertFalse(os.path.exists(old))
            self.assertTrue(os.path.exists(new))
            remaining = retention._read_pending()
            self.assertEqual([i["path"] for i in remaining], [new])

    def test_an_already_missing_file_is_dropped_rather_than_retried(self):
        # The user may have deleted it themselves; do not keep the entry.
        with _Pending() as p:
            p.write([{"path": os.path.join(p._tmp.name, "gone.mov"),
                      "due_utc": time.time() - 60}])
            retention.process_pending_deletions()
            self.assertEqual(retention._read_pending(), [])

    def test_a_file_that_cannot_be_deleted_is_kept_for_a_later_attempt(self):
        with _Pending() as p:
            target = p.make_file()
            p.write([{"path": target, "due_utc": time.time() - 60}])
            with patch.object(retention.os, "remove",
                              side_effect=PermissionError("in use")):
                self.assertEqual(retention.process_pending_deletions(), 0)
            self.assertTrue(os.path.exists(target))
            self.assertEqual([i["path"] for i in retention._read_pending()], [target],
                             "a locked file must stay scheduled")

    def test_the_log_callback_is_told_about_each_deletion(self):
        with _Pending() as p:
            target = p.make_file()
            p.write([{"path": target, "due_utc": time.time() - 60}])
            messages = []
            retention.process_pending_deletions(log_cb=messages.append)
            self.assertTrue(any(target in m for m in messages))

    def test_a_raising_log_callback_does_not_stop_the_deletion(self):
        with _Pending() as p:
            target = p.make_file()
            p.write([{"path": target, "due_utc": time.time() - 60}])

            def hostile(_message):
                raise RuntimeError("UI is gone")

            retention.process_pending_deletions(log_cb=hostile)
            self.assertFalse(os.path.exists(target))


class MalformedEntryTests(unittest.TestCase):
    """A corrupted list must not stop retention working.

    process_pending_deletions runs at startup. Before these tests it read
    `float(it.get('due_utc', 0))` outside the try, so a single entry with a
    non-numeric due time raised out of the whole function -- no deletions
    happened, the list was never rewritten, and the bad entry blocked
    retention permanently on every subsequent start.
    """

    def test_a_non_numeric_due_time_does_not_block_the_other_entries(self):
        with _Pending() as p:
            good = p.make_file("good.mov")
            p.write([{"path": "C:/bad.mov", "due_utc": "not-a-number"},
                     {"path": good, "due_utc": time.time() - 60}])

            deleted = retention.process_pending_deletions()
            self.assertEqual(deleted, 1, "the good entry should still be processed")
            self.assertFalse(os.path.exists(good))

    def test_a_missing_due_time_does_not_block_the_other_entries(self):
        with _Pending() as p:
            good = p.make_file("good.mov")
            p.write([{"path": "C:/bad.mov"},
                     {"path": good, "due_utc": time.time() - 60}])
            retention.process_pending_deletions()
            self.assertFalse(os.path.exists(good))

    def test_an_entry_with_no_path_is_discarded(self):
        with _Pending() as p:
            p.write([{"due_utc": time.time() - 60}])
            retention.process_pending_deletions()
            self.assertEqual(retention._read_pending(), [],
                             "an entry with no path can never be actioned")

    def test_a_non_dict_entry_is_discarded(self):
        with _Pending() as p:
            p.write(["just a string", 42, None])
            retention.process_pending_deletions()
            self.assertEqual(retention._read_pending(), [])

    def test_a_directory_is_not_retried_forever(self):
        # os.remove refuses a directory, so the entry would be kept and
        # retried at every startup for as long as the folder exists.
        with _Pending() as p:
            folder = os.path.join(p._tmp.name, "a_folder")
            os.makedirs(folder)
            p.write([{"path": folder, "due_utc": time.time() - 60}])
            retention.process_pending_deletions()
            self.assertTrue(os.path.isdir(folder), "must not remove a directory")
            self.assertEqual(retention._read_pending(), [],
                             "a directory entry should be discarded, not retried")


if __name__ == "__main__":
    unittest.main()
