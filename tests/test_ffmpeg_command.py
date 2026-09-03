import unittest
from unittest.mock import patch

import conversion.ffmpeg_utils as ffmpeg_utils


class FfmpegCommandTests(unittest.TestCase):
    def _base_settings(self, **overrides):
        settings = {
            "copy_only": False,
            "use_gpu": False,
            "gpu_encoder": "Auto",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "Auto",
            "audio_bitrate": "Auto",
            "volume_percentage": 100,
            "text_overlay": "None",
            "video_size": "Auto",
            "framerate": "Auto",
            "keyframe_interval": 0,
            "output_format": "mp4",
            "custom_console_command": "",
        }
        settings.update(overrides)
        return settings

    def test_cpu_hevc_alias_uses_libx265(self):
        command = ffmpeg_utils.build_ffmpeg_command(
            self._base_settings(video_codec="hevc"),
            "input.mov",
            "output.mp4",
        )

        self.assertIn("-c:v", command)
        self.assertEqual(command[command.index("-c:v") + 1], "libx265")

    def test_gpu_hevc_uses_hevc_encoder_when_available(self):
        with patch.object(
            ffmpeg_utils,
            "GPU_ENCODERS",
            {"nvidia": {"h264": "h264_nvenc", "hevc": "hevc_nvenc"}},
        ):
            command = ffmpeg_utils.build_ffmpeg_command(
                self._base_settings(
                    use_gpu=True,
                    gpu_encoder="nvidia",
                    video_codec="hevc",
                ),
                "input.mov",
                "output.mp4",
            )

        self.assertEqual(command[command.index("-c:v") + 1], "hevc_nvenc")

    def test_gpu_hevc_falls_back_to_cpu_when_hevc_encoder_is_unavailable(self):
        with patch.object(
            ffmpeg_utils,
            "GPU_ENCODERS",
            {"nvidia": {"h264": "h264_nvenc"}},
        ):
            command = ffmpeg_utils.build_ffmpeg_command(
                self._base_settings(
                    use_gpu=True,
                    gpu_encoder="nvidia",
                    video_codec="hevc",
                ),
                "input.mov",
                "output.mp4",
            )

        self.assertEqual(command[command.index("-c:v") + 1], "libx265")

    def test_standard_video_command_does_not_force_overwrite(self):
        command = ffmpeg_utils.build_ffmpeg_command(
            self._base_settings(),
            "input.mov",
            "output.mp4",
        )

        self.assertNotIn("-y", command)


if __name__ == "__main__":
    unittest.main()
