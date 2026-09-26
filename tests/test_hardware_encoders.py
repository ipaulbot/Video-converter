import subprocess
import unittest

from conversion import hardware_encoders as hw


class _Result:
    def __init__(self, returncode):
        self.returncode = returncode


class HardwareEncoderProbeTests(unittest.TestCase):
    def setUp(self):
        hw.clear_hardware_encoder_cache()

    def test_returns_the_first_encoder_that_initialises(self):
        calls = []

        def run(command, **_kwargs):
            calls.append(command)
            encoder = command[command.index("-c:v") + 1]
            return _Result(0 if encoder == "h264_qsv" else 1)

        self.assertEqual(hw.probe_hardware_h264_encoder("ffmpeg.exe", run=run), "h264_qsv")
        tried = [command[command.index("-c:v") + 1] for command in calls]
        self.assertEqual(tried, ["h264_nvenc", "h264_qsv"])       # stops at the first success
        # Two frames of a synthetic source into a null sink: nothing is written.
        self.assertIn("-f", calls[0])
        self.assertEqual(calls[0][calls[0].index("-i") + 1], "nullsrc=s=256x256:r=5")
        self.assertEqual(calls[0][-2:], ["null", "-"])
        self.assertIn("-frames:v", calls[0])

    def test_returns_empty_when_no_encoder_initialises(self):
        self.assertEqual(hw.probe_hardware_h264_encoder("ffmpeg.exe", run=lambda *_a, **_k: _Result(1)), "")

    def test_a_crashing_or_missing_ffmpeg_counts_as_no_encoder(self):
        def run(_command, **_kwargs):
            raise subprocess.TimeoutExpired("ffmpeg", 8)

        self.assertEqual(hw.probe_hardware_h264_encoder("ffmpeg.exe", run=run), "")

        def missing(_command, **_kwargs):
            raise OSError("no ffmpeg")

        self.assertEqual(hw.probe_hardware_h264_encoder("ffmpeg.exe", run=missing), "")
        self.assertEqual(hw.probe_hardware_h264_encoder("", run=missing), "")

    def test_result_is_cached_per_ffmpeg_path(self):
        counter = {"runs": 0}

        def run(_command, **_kwargs):
            counter["runs"] += 1
            return _Result(0)

        self.assertEqual(hw.probe_hardware_h264_encoder("ffmpeg.exe", run=run), "h264_nvenc")
        self.assertEqual(hw.probe_hardware_h264_encoder("ffmpeg.exe", run=run), "h264_nvenc")
        self.assertEqual(counter["runs"], 1)
        hw.probe_hardware_h264_encoder("other/ffmpeg.exe", run=run)
        self.assertEqual(counter["runs"], 2)

    def test_encoder_failure_markers_cover_the_real_messages(self):
        for message in (
            "[h264_nvenc @ 0x1] Cannot load nvcuda.dll",
            "[h264_nvenc @ 0x1] No capable devices found",
            "[h264_qsv @ 0x1] Error initializing an internal MFX session: unsupported (-3)",
            "[h264_amf @ 0x1] AMF failed to initialise on the given D3D11 device: 1.",
            "Error while opening encoder for output stream #0:0 - maybe incorrect parameters",
        ):
            self.assertTrue(hw.looks_like_encoder_failure(message), message)
        self.assertFalse(hw.looks_like_encoder_failure("Error opening input: Server returned 400 Bad Request"))
        self.assertFalse(hw.looks_like_encoder_failure(""))


if __name__ == "__main__":
    unittest.main()
