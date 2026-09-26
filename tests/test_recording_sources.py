import subprocess
import unittest
from unittest import mock

from conversion.recording_sources import (
    CAMERA_SOURCE_TYPES,
    _register_probe,
    active_device_probes,
    build_region_source_value,
    build_rtsp_url,
    build_source_text,
    discover_directshow_audio_devices,
    discover_directshow_devices,
    discover_directshow_video_devices,
    is_hidden_directshow_video_device,
    list_capture_windows,
    parse_directshow_audio_devices,
    parse_directshow_video_devices,
    parse_rtsp_url_settings,
    screen_monitor_index,
    screen_region,
    stream_host_problem,
    terminate_device_probes,
)


class RecordingSourceTests(unittest.TestCase):
    def test_stream_host_problem_flags_numeric_hosts_that_are_not_ipv4(self):
        self.assertEqual(stream_host_problem("10.0.100.5"), "")
        self.assertEqual(stream_host_problem("camera.local"), "")
        self.assertEqual(stream_host_problem("rtsp://10.0.100.5:554/axis-media/media.amp"), "")
        self.assertEqual(stream_host_problem(""), "")
        self.assertEqual(stream_host_problem("10.0.100.5:554"), "")
        for bad in ("10.0.1000.5", "10.0.100", "10.0.100.5.6", "10..100.5", "10.0.256.5", "10.0.1000.5:554"):
            with self.subTest(bad=bad):
                self.assertIn(bad.split(":")[0], stream_host_problem(bad))
        # Wrapped in a full URL the host is still checked.
        self.assertIn("10.0.1000.5", stream_host_problem("rtsp://user:pw@10.0.1000.5:554/stream"))

    def test_camera_source_types_include_common_camera_families(self):
        ids = [item["id"] for item in CAMERA_SOURCE_TYPES]

        self.assertIn("rtsp_ip", ids)
        self.assertIn("directshow", ids)
        self.assertIn("basler_genicam", ids)
        self.assertIn("stream_url", ids)
        self.assertIn("screen", ids)

    def test_builds_screen_capture_source(self):
        self.assertEqual(build_source_text("screen", ""), "screen=desktop")
        self.assertEqual(build_source_text("screen", "desktop"), "screen=desktop")
        self.assertEqual(build_source_text("screen", "title=My App"), "screen=title=My App")
        self.assertEqual(build_source_text("screen", "My App"), "screen=title=My App")
        self.assertEqual(build_source_text("screen", "screen=desktop"), "screen=desktop")

    def test_builds_gpu_monitor_screen_source(self):
        # `monitor=N` (1-based, as shown to the user) selects one display through
        # the Desktop Duplication API instead of GDI.
        self.assertEqual(build_source_text("screen", "monitor=2"), "screen=monitor=2")
        self.assertEqual(build_source_text("screen", "Monitor 2"), "screen=monitor=2")
        self.assertEqual(build_source_text("screen", "screen=monitor=1"), "screen=monitor=1")
        self.assertEqual(screen_monitor_index("screen=monitor=2"), 2)
        self.assertIsNone(screen_monitor_index("screen=desktop"))
        self.assertIsNone(screen_monitor_index("screen=title=monitor=2"))
        self.assertIsNone(screen_monitor_index("screen=monitor=0"))

    def test_builds_region_screen_source(self):
        # `region=X,Y,WxH` in virtual-desktop pixels, grabbed through GDI.
        self.assertEqual(build_source_text("screen", "region=100,200,800x600"), "screen=region=100,200,800x600")
        self.assertEqual(build_source_text("screen", "Region = 100, 200, 800 x 600"), "screen=region=100,200,800x600")
        self.assertEqual(screen_region("screen=region=100,200,800x600"), (100, 200, 800, 600))
        self.assertEqual(screen_region("screen=region=-1920,0,1920x1080"), (-1920, 0, 1920, 1080))
        self.assertIsNone(screen_region("screen=desktop"))
        self.assertIsNone(screen_region("screen=region=0,0,0x600"))
        self.assertEqual(build_region_source_value(100, 200, 800, 600), "region=100,200,800x600")

    def test_lists_capture_windows_with_titles_only(self):
        windows = list_capture_windows(enumerate_windows=lambda: [
            (1, "Notepad", True),
            (2, "", True),                      # untitled: skipped
            (3, "Hidden tool window", False),   # invisible: skipped
            (4, "Notepad", True),               # duplicate title: once
            (5, "Program Manager", True),       # the desktop shell window: skipped
        ])
        self.assertEqual(windows, ["Notepad"])

    def test_hides_licensed_capture_filters_from_the_video_device_list(self):
        # A third-party DirectShow filter whose licence check pops a modal dialog
        # inside ffmpeg the moment it is instantiated; the built-in screen source
        # replaces it, so it must not be offered as a camera.
        output = '''
        [dshow @ 000001] "HD Pro Webcam C920" (video)
        [dshow @ 000001] "Medialooks Screen Capture" (video)
        [dshow @ 000001] "OBS Virtual Camera" (video)
        '''

        self.assertEqual(parse_directshow_video_devices(output), ["HD Pro Webcam C920", "OBS Virtual Camera"])
        self.assertTrue(is_hidden_directshow_video_device("Medialooks Screen Capture"))
        self.assertTrue(is_hidden_directshow_video_device("video=Medialooks Screen Capture"))
        self.assertFalse(is_hidden_directshow_video_device("OBS Virtual Camera"))
        self.assertFalse(is_hidden_directshow_video_device(""))

    def test_builds_directshow_video_source(self):
        self.assertEqual(build_source_text("directshow", "Logitech Camera"), "video=Logitech Camera")

    def test_builds_rtsp_ip_source_from_address_and_port(self):
        self.assertEqual(
            build_source_text("rtsp_ip", "192.168.1.20", port="554", username="root", password="pw"),
            "rtsp://root:pw@192.168.1.20:554/stream",
        )

    def test_builds_axis_rtsp_url_with_custom_stream_path(self):
        self.assertEqual(
            build_rtsp_url("192.168.1.20", port="554", username="root", password="pw", path="axis-media/media.amp"),
            "rtsp://root:pw@192.168.1.20:554/axis-media/media.amp",
        )

    def test_builds_axis_rtsp_url_from_http_browser_address(self):
        self.assertEqual(
            build_rtsp_url("http://192.168.200.4/", port="554", username="root", password="root", path="axis-media/media.amp"),
            "rtsp://root:root@192.168.200.4:554/axis-media/media.amp",
        )

    def test_builds_axis_rtsp_url_from_http_address_with_existing_path(self):
        self.assertEqual(
            build_rtsp_url("http://192.168.200.4/axis-media/media.amp", port="554", username="", password="", path=""),
            "rtsp://192.168.200.4:554/axis-media/media.amp",
        )

    def test_parses_rtsp_url_into_media_recorder_style_fields(self):
        settings = parse_rtsp_url_settings("rtsp://root:pw@192.168.200.4:554/axis-media/media.amp")

        self.assertEqual(settings["host"], "192.168.200.4")
        self.assertEqual(settings["port"], "554")
        self.assertEqual(settings["username"], "root")
        self.assertEqual(settings["password"], "pw")
        self.assertEqual(settings["path"], "axis-media/media.amp")

    def test_generic_stream_returns_entered_source(self):
        self.assertEqual(build_source_text("stream_url", "http://camera/live.mjpg"), "http://camera/live.mjpg")

    def test_parses_directshow_video_devices_from_ffmpeg_output(self):
        output = '''
        [dshow @ 000001] DirectShow video devices (some may be both video and audio devices)
        [dshow @ 000001]  "HD Pro Webcam C920"
        [dshow @ 000001]     Alternative name "@device_pnp_\\\\?\\usb#vid_046d"
        [dshow @ 000001]  "Integrated Camera"
        [dshow @ 000001] DirectShow audio devices
        [dshow @ 000001]  "Microphone"
        '''

        self.assertEqual(parse_directshow_video_devices(output), ["HD Pro Webcam C920", "Integrated Camera"])

    def test_parses_directshow_video_devices_from_tagged_ffmpeg_output(self):
        output = '''
        [dshow @ 000001] "HD Pro Webcam C920" (video)
        [dshow @ 000001] "Integrated Webcam" (video)
        [dshow @ 000001] "Daheng Imaging Device 1" (none)
        [dshow @ 000001] "Microphone (HD Pro Webcam C920)" (audio)
        '''

        self.assertEqual(parse_directshow_video_devices(output), ["HD Pro Webcam C920", "Integrated Webcam"])

    def test_keeps_basler_compatibility_device_even_when_tagged_none(self):
        output = '''
        [dshow @ 000001] DirectShow video devices (some may be both video and audio devices)
        [dshow @ 000001] "HD Pro Webcam C920" (video)
        [dshow @ 000001] "Basler GenICam Source" (none)
        [dshow @ 000001] "Basler GenICam Source 2" (none)
        [dshow @ 000001] "Daheng Imaging Device 1" (none)
        [dshow @ 000001] DirectShow audio devices
        [dshow @ 000001] "Microphone"
        '''

        self.assertEqual(
            parse_directshow_video_devices(output),
            ["HD Pro Webcam C920", "Basler GenICam Source", "Basler GenICam Source 2"],
        )


    def test_parses_directshow_audio_devices_from_section_header(self):
        output = '''
        [dshow @ 000001] DirectShow video devices (some may be both video and audio devices)
        [dshow @ 000001]  "HD Pro Webcam C920"
        [dshow @ 000001]     Alternative name "@device_pnp_\\\\?\\usb#vid_046d"
        [dshow @ 000001] DirectShow audio devices
        [dshow @ 000001]  "Microphone (HD Pro Webcam C920)"
        [dshow @ 000001]     Alternative name "@device_cm_{33D9A762}\\wave_{61D8DAB2}"
        [dshow @ 000001]  "Microphone Array (2- Realtek(R) Audio)"
        '''

        self.assertEqual(
            parse_directshow_audio_devices(output),
            ["Microphone (HD Pro Webcam C920)", "Microphone Array (2- Realtek(R) Audio)"],
        )

    def test_parses_directshow_audio_devices_from_tagged_output(self):
        output = '''
        [dshow @ 000001] "HD Pro Webcam C920" (video)
        [dshow @ 000001] "Microphone (HD Pro Webcam C920)" (audio)
        [dshow @ 000001] "Microphone Array (2- Realtek(R) Audio)" (audio)
        '''

        self.assertEqual(
            parse_directshow_audio_devices(output),
            ["Microphone (HD Pro Webcam C920)", "Microphone Array (2- Realtek(R) Audio)"],
        )

    def test_audio_device_parser_ignores_video_only_devices(self):
        output = '''
        [dshow @ 000001] DirectShow video devices
        [dshow @ 000001]  "Integrated Webcam"
        [dshow @ 000001] DirectShow audio devices
        [dshow @ 000001]  "Microphone"
        '''

        devices = parse_directshow_audio_devices(output)
        self.assertEqual(devices, ["Microphone"])
        self.assertNotIn("Integrated Webcam", devices)

    def test_device_discovery_decodes_ffmpeg_output_as_utf8(self):
        # FFmpeg prints DirectShow device names as UTF-8 regardless of the console
        # code page; decoding them with the locale turns "Kent’s" into mojibake that
        # FFmpeg can never match again when the name is passed back as an input.
        listing = (
            "[dshow @ 000001] DirectShow video devices\n"
            '[dshow @ 000001]  "Cámara A"\n'
            "[dshow @ 000001] DirectShow audio devices\n"
            '[dshow @ 000001]  "Microphone (Kent’s Headset)"\n'
        )

        def fake_popen(command, **kwargs):
            self.assertEqual(kwargs.get("encoding"), "utf-8")
            self.assertEqual(kwargs.get("errors"), "replace")
            self.assertNotIn("text", kwargs)
            return _FakeProbe(stderr=listing)

        with mock.patch("conversion.recording_sources.subprocess.Popen", side_effect=fake_popen):
            self.assertEqual(discover_directshow_video_devices("ffmpeg.exe"), ["Cámara A"])
            self.assertEqual(discover_directshow_audio_devices("ffmpeg.exe"), ["Microphone (Kent’s Headset)"])


class _FakeProbe:
    """Stands in for the ffmpeg Popen: one listing, optional hang, kill tracking."""

    def __init__(self, stderr="", hang=False):
        self._stderr = stderr
        self._hang = hang
        self.killed = False
        self.returncode = None

    def communicate(self, timeout=None):
        if self._hang and not self.killed:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        self.returncode = 1
        return "", self._stderr

    def kill(self):
        self.killed = True

    def poll(self):
        return self.returncode


class DeviceScanTests(unittest.TestCase):
    LISTING = (
        "[dshow @ 000001] DirectShow video devices\n"
        '[dshow @ 000001]  "Camera A"\n'
        '[dshow @ 000001]  "Camera B"\n'
        "[dshow @ 000001] DirectShow audio devices\n"
        '[dshow @ 000001]  "Microphone A"\n'
    )

    def test_one_ffmpeg_run_yields_both_device_lists(self):
        probes = []

        def fake_popen(command, **kwargs):
            probes.append(_FakeProbe(stderr=self.LISTING))
            return probes[-1]

        with mock.patch("conversion.recording_sources.subprocess.Popen", side_effect=fake_popen):
            scan = discover_directshow_devices("ffmpeg.exe")

        self.assertEqual(len(probes), 1)
        self.assertTrue(scan.ok)
        self.assertEqual(scan.video, ["Camera A", "Camera B"])
        self.assertEqual(scan.audio, ["Microphone A"])

    def test_timed_out_scan_is_killed_and_reported_as_failed(self):
        probe = _FakeProbe(hang=True)
        with mock.patch("conversion.recording_sources.subprocess.Popen", return_value=probe):
            scan = discover_directshow_devices("ffmpeg.exe", timeout_seconds=0.01)

        self.assertTrue(probe.killed)
        self.assertFalse(scan.ok)
        self.assertEqual((scan.video, scan.audio), ([], []))
        self.assertEqual(active_device_probes(), [])

    def test_missing_ffmpeg_is_a_failed_scan_not_an_exception(self):
        with mock.patch("conversion.recording_sources.subprocess.Popen", side_effect=OSError("no ffmpeg")):
            scan = discover_directshow_devices("ffmpeg.exe")
        self.assertFalse(scan.ok)
        self.assertFalse(discover_directshow_devices("").ok)

    def test_terminate_device_probes_kills_a_scan_still_in_flight(self):
        # What shutdown() and atexit rely on: a scan interrupted by the process
        # exiting must not leave ffmpeg behind (549 of them were found queued
        # on DirectShow enumeration, which made every later scan time out).
        probe = _FakeProbe(stderr=self.LISTING)
        _register_probe(probe)
        self.assertIn(probe, active_device_probes())

        terminate_device_probes()

        self.assertTrue(probe.killed)
        self.assertEqual(active_device_probes(), [])


if __name__ == "__main__":
    unittest.main()
