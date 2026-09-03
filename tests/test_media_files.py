import os
import tempfile
import unittest

from utils.media_files import collect_supported_media_paths


SUPPORTED = (".mp4", ".mov")


class CollectSupportedMediaPathsTests(unittest.TestCase):
    def test_collects_direct_media_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = os.path.join(temp_dir, "clip.mp4")
            note = os.path.join(temp_dir, "note.txt")
            open(video, "w", encoding="utf-8").close()
            open(note, "w", encoding="utf-8").close()

            self.assertEqual(collect_supported_media_paths([video, note], SUPPORTED), [video])

    def test_expands_dropped_folder_recursively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            nested = os.path.join(temp_dir, "nested")
            os.makedirs(nested)
            first = os.path.join(temp_dir, "a.mp4")
            second = os.path.join(nested, "b.mov")
            ignored = os.path.join(nested, "c.txt")
            for path in (first, second, ignored):
                open(path, "w", encoding="utf-8").close()

            self.assertEqual(
                collect_supported_media_paths([temp_dir], SUPPORTED),
                [first, second],
            )

    def test_deduplicates_preserving_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = os.path.join(temp_dir, "clip.mp4")
            open(video, "w", encoding="utf-8").close()

            self.assertEqual(collect_supported_media_paths([video, video], SUPPORTED), [video])


if __name__ == "__main__":
    unittest.main()
