import os
import tempfile
import unittest
from unittest.mock import patch

from utils import paths


class LogDirTests(unittest.TestCase):
    def test_prefers_a_writable_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            wanted = os.path.join(tmp, "nvc-logs")
            self.assertEqual(paths.log_dir({"log_folder": wanted}), wanted)
            self.assertTrue(os.path.isdir(wanted))

    def test_falls_back_when_empty_or_unwritable(self):
        default = paths.get_data_dir("logs")
        self.assertEqual(paths.log_dir({"log_folder": ""}), default)
        self.assertEqual(paths.log_dir(None), default)
        # Only the configured folder must fail to be created; the fallback
        # itself is stubbed so the test cannot depend on what already exists.
        with patch.object(paths.os, "makedirs", side_effect=OSError("nope")), \
                patch.object(paths, "get_data_dir", return_value=default):
            self.assertEqual(paths.log_dir({"log_folder": r"Z:\nowhere"}), default)
