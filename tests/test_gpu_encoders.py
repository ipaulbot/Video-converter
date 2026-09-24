"""Tests for conversion/gpu_encoders.py.

This used to run `ffmpeg -encoders` at import time, synchronously and with no
timeout, so a wedged binary hung startup before any window appeared. It is
now cached and lazy. These tests pin both properties, and none of them runs
ffmpeg.
"""
import subprocess
import unittest
from unittest.mock import patch

from conversion import gpu_encoders

# A trimmed `ffmpeg -encoders` listing. The real output is a table; the code
# only looks for encoder names as substrings.
NVIDIA_OUTPUT = """
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder
 V....D hevc_nvenc           NVIDIA NVENC hevc encoder
 V....D libx264              libx264 H.264 / AVC
"""
INTEL_OUTPUT = " V....D h264_qsv   H264 (Intel Quick Sync Video)\n"
ALL_VENDORS = NVIDIA_OUTPUT + INTEL_OUTPUT + " V....D h264_amf  AMD AMF\n"
CPU_ONLY_OUTPUT = " V....D libx264   libx264 H.264 / AVC\n"


class _Result:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = 0


def _detect(stdout=None, side_effect=None, ffmpeg_exists=True):
    """Run detection against a stubbed ffmpeg, with the cache cleared."""
    gpu_encoders.get_supported_encoders.cache_clear()
    with patch.object(gpu_encoders.os.path, "exists", return_value=ffmpeg_exists), \
         patch.object(gpu_encoders.subprocess, "run",
                      side_effect=side_effect,
                      return_value=_Result(stdout or "")) as run:
        result = gpu_encoders.get_supported_encoders()
    gpu_encoders.get_supported_encoders.cache_clear()
    return result, run


class DetectionTests(unittest.TestCase):
    def tearDown(self):
        gpu_encoders.get_supported_encoders.cache_clear()

    def test_nvidia_encoders_are_detected(self):
        found, _run = _detect(NVIDIA_OUTPUT)
        self.assertEqual(found, {"nvidia": {"h264": "h264_nvenc",
                                            "hevc": "hevc_nvenc"}})

    def test_a_vendor_with_only_h264_is_reported_without_hevc(self):
        found, _run = _detect(INTEL_OUTPUT)
        self.assertEqual(found, {"intel": {"h264": "h264_qsv"}})

    def test_several_vendors_are_reported_together(self):
        found, _run = _detect(ALL_VENDORS)
        self.assertEqual(set(found), {"nvidia", "intel", "amd"})

    def test_a_cpu_only_build_reports_no_gpu_encoders(self):
        found, _run = _detect(CPU_ONLY_OUTPUT)
        self.assertEqual(found, {})

    def test_a_vendor_with_no_encoders_is_omitted_entirely(self):
        found, _run = _detect(NVIDIA_OUTPUT)
        self.assertNotIn("amd", found)
        self.assertNotIn("intel", found)

    def test_detection_is_case_insensitive(self):
        found, _run = _detect(NVIDIA_OUTPUT.upper())
        self.assertIn("nvidia", found)


class FailureTests(unittest.TestCase):
    def tearDown(self):
        gpu_encoders.get_supported_encoders.cache_clear()

    def test_a_missing_ffmpeg_reports_no_encoders(self):
        found, run = _detect(ffmpeg_exists=False)
        self.assertEqual(found, {})
        run.assert_not_called()

    def test_a_timeout_reports_no_encoders_rather_than_raising(self):
        """The reason this is not at import time any more."""
        found, _run = _detect(
            side_effect=subprocess.TimeoutExpired("ffmpeg", 20))
        self.assertEqual(found, {})

    def test_a_non_zero_exit_reports_no_encoders(self):
        found, _run = _detect(
            side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="boom"))
        self.assertEqual(found, {})

    def test_an_unexpected_error_reports_no_encoders(self):
        found, _run = _detect(side_effect=OSError("exec format error"))
        self.assertEqual(found, {})

    def test_the_subprocess_is_given_a_timeout(self):
        """Without one, a wedged ffmpeg blocks the caller forever."""
        _found, run = _detect(NVIDIA_OUTPUT)
        self.assertIn("timeout", run.call_args.kwargs)
        self.assertGreater(run.call_args.kwargs["timeout"], 0)

    def test_the_console_window_is_hidden(self):
        _found, run = _detect(NVIDIA_OUTPUT)
        self.assertIn("creationflags", run.call_args.kwargs)


class CachingTests(unittest.TestCase):
    def tearDown(self):
        gpu_encoders.get_supported_encoders.cache_clear()

    def test_detection_runs_only_once_per_process(self):
        gpu_encoders.get_supported_encoders.cache_clear()
        with patch.object(gpu_encoders.os.path, "exists", return_value=True), \
             patch.object(gpu_encoders.subprocess, "run",
                          return_value=_Result(NVIDIA_OUTPUT)) as run:
            first = gpu_encoders.get_supported_encoders()
            second = gpu_encoders.get_supported_encoders()
            third = gpu_encoders.get_supported_encoders()
        self.assertEqual(run.call_count, 1, "ffmpeg should be probed once")
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_choosing_the_best_encoder_does_not_probe_again(self):
        """get_best_gpu_encoder used to call the detector a second time."""
        gpu_encoders.get_supported_encoders.cache_clear()
        with patch.object(gpu_encoders.os.path, "exists", return_value=True), \
             patch.object(gpu_encoders.subprocess, "run",
                          return_value=_Result(ALL_VENDORS)) as run:
            gpu_encoders.get_supported_encoders()
            gpu_encoders.get_best_gpu_encoder()
            gpu_encoders.get_best_gpu_encoder()
        self.assertEqual(run.call_count, 1)


class BestEncoderTests(unittest.TestCase):
    def tearDown(self):
        gpu_encoders.get_supported_encoders.cache_clear()

    def _best(self, stdout):
        gpu_encoders.get_supported_encoders.cache_clear()
        with patch.object(gpu_encoders.os.path, "exists", return_value=True), \
             patch.object(gpu_encoders.subprocess, "run",
                          return_value=_Result(stdout)):
            return gpu_encoders.get_best_gpu_encoder()

    def test_nvidia_is_preferred(self):
        vendor, encoders = self._best(ALL_VENDORS)
        self.assertEqual(vendor, "nvidia")
        self.assertEqual(encoders["h264"], "h264_nvenc")

    def test_amd_is_preferred_over_intel(self):
        vendor, _encoders = self._best(
            INTEL_OUTPUT + " V....D h264_amf  AMD AMF\n")
        self.assertEqual(vendor, "amd")

    def test_intel_is_used_when_it_is_the_only_option(self):
        vendor, _encoders = self._best(INTEL_OUTPUT)
        self.assertEqual(vendor, "intel")

    def test_nothing_available_returns_a_pair_of_nones(self):
        # ffmpeg_utils unpacks two values from this, so the shape matters.
        vendor, encoders = self._best(CPU_ONLY_OUTPUT)
        self.assertIsNone(vendor)
        self.assertIsNone(encoders)


class ImportTimeTests(unittest.TestCase):
    """Importing the module must not shell out.

    It used to end with `GPU_ENCODERS = get_supported_encoders()`, so simply
    importing it ran ffmpeg -- on the main thread, during startup, with no
    timeout.
    """

    def test_the_module_does_not_probe_at_import(self):
        import inspect
        source = inspect.getsource(gpu_encoders)
        calls = [line for line in source.splitlines()
                 if line and not line[0].isspace()
                 and "get_supported_encoders()" in line
                 and not line.startswith(("def ", "@", "#"))]
        self.assertEqual(calls, [],
                         "a module-level call would run ffmpeg on import")

    def test_ffmpeg_utils_resolves_encoders_lazily(self):
        from conversion import ffmpeg_utils
        self.assertIsNone(ffmpeg_utils.GPU_ENCODERS,
                          "importing ffmpeg_utils should not have probed")

    def test_an_explicit_override_is_honoured_without_probing(self):
        """This is how the tests pin an encoder map without running ffmpeg."""
        from conversion import ffmpeg_utils
        with patch.object(ffmpeg_utils, "GPU_ENCODERS",
                          {"nvidia": {"h264": "h264_nvenc"}}), \
             patch.object(gpu_encoders.subprocess, "run") as run:
            self.assertEqual(ffmpeg_utils._gpu_encoders(),
                             {"nvidia": {"h264": "h264_nvenc"}})
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
