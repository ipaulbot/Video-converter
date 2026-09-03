import unittest

from conversion.recording_sources import (
    CAMERA_SOURCE_TYPES,
    build_rtsp_url,
    build_source_text,
    parse_directshow_audio_devices,
    parse_directshow_video_devices,
    parse_rtsp_url_settings,
)


class RecordingSourceTests(unittest.TestCase):
    def test_camera_source_types_include_common_camera_families(self):
        ids = [item["id"] for item in CAMERA_SOURCE_TYPES]

        self.assertIn("rtsp_ip", ids)
        self.assertIn("directshow", ids)
        self.assertIn("basler_genicam", ids)
        self.assertIn("stream_url", ids)

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


if __name__ == "__main__":
    unittest.main()
