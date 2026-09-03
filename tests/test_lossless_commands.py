import unittest

from conversion.lossless_commands import (
    build_concat_command,
    build_extract_audio_command,
    build_remove_audio_command,
    build_remux_command,
    build_trim_command,
    format_concat_file_line,
)


class LosslessCommandTests(unittest.TestCase):
    def test_build_trim_command_uses_stream_copy(self):
        command = build_trim_command("ffmpeg.exe", "in.mp4", "out.mp4", "00:00:05", "00:00:10")

        self.assertIn("-c", command)
        self.assertEqual(command[command.index("-c") + 1], "copy")
        self.assertIn("-ss", command)
        self.assertIn("-to", command)

    def test_build_remux_command_uses_stream_copy(self):
        command = build_remux_command("ffmpeg.exe", "in.mkv", "out.mp4")

        self.assertEqual(command[-1], "out.mp4")
        self.assertEqual(command[command.index("-c") + 1], "copy")

    def test_build_extract_audio_command_disables_video(self):
        command = build_extract_audio_command("ffmpeg.exe", "in.mp4", "audio.m4a")

        self.assertIn("-vn", command)
        self.assertEqual(command[command.index("-c:a") + 1], "copy")

    def test_build_remove_audio_command_disables_audio(self):
        command = build_remove_audio_command("ffmpeg.exe", "in.mp4", "silent.mp4")

        self.assertIn("-an", command)
        self.assertEqual(command[command.index("-c:v") + 1], "copy")

    def test_build_concat_command_uses_concat_demuxer(self):
        command = build_concat_command("ffmpeg.exe", "files.txt", "merged.mp4")

        self.assertIn("concat", command)
        self.assertIn("-safe", command)
        self.assertEqual(command[-1], "merged.mp4")

    def test_format_concat_file_line_normalizes_windows_paths(self):
        line = format_concat_file_line(r"C:\Video Files\Bob's clip.mp4")

        self.assertEqual(line, "file 'C:/Video Files/Bob\\'s clip.mp4'")


if __name__ == "__main__":
    unittest.main()
