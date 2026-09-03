import os
import tempfile
import unittest

from utils.file_naming import get_unique_path


class UniquePathTests(unittest.TestCase):
    def test_returns_original_path_when_it_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "video.mp4")

            self.assertEqual(get_unique_path(target), target)

    def test_adds_browser_style_suffix_when_file_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "video.mp4")
            open(target, "w", encoding="utf-8").close()

            self.assertEqual(
                get_unique_path(target),
                os.path.join(temp_dir, "video (1).mp4"),
            )

    def test_increments_suffix_until_unused_name_is_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for filename in ("video.mp4", "video (1).mp4", "video (2).mp4"):
                open(os.path.join(temp_dir, filename), "w", encoding="utf-8").close()

            self.assertEqual(
                get_unique_path(os.path.join(temp_dir, "video.mp4")),
                os.path.join(temp_dir, "video (3).mp4"),
            )

    def test_preserves_multi_dot_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "camera.export.mp4")
            open(target, "w", encoding="utf-8").close()

            self.assertEqual(
                get_unique_path(target),
                os.path.join(temp_dir, "camera.export (1).mp4"),
            )


if __name__ == "__main__":
    unittest.main()
