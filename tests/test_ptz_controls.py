import unittest
from unittest.mock import patch

from conversion import ptz_controls
from conversion.ptz_controls import (
    axis_vapix_continuous_url,
    axis_vapix_ptz_url,
    parse_axis_ptz_presets,
    send_axis_vapix_request,
)


class PTZControlsTests(unittest.TestCase):
    def test_axis_vapix_move_url_uses_camera_host_and_credentials(self):
        url = axis_vapix_ptz_url(
            "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp",
            "move",
            move="left",
        )

        self.assertEqual(
            url,
            "http://root:pass@192.168.1.50/axis-cgi/com/ptz.cgi?move=left",
        )

    def test_axis_vapix_preset_url_escapes_preset_name(self):
        url = axis_vapix_ptz_url(
            "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp",
            "goto_preset",
            preset_name="Home View",
        )

        self.assertIn("gotoserverpresetname=Home+View", url)

    def test_parse_axis_ptz_presets_reads_vapix_key_value_response(self):
        presets = parse_axis_ptz_presets("serverpresetname1=Home\nserverpresetname2=Door\n")

        self.assertEqual(presets, ["Home", "Door"])

    def test_axis_vapix_continuous_url_uses_signed_pan_tilt_components(self):
        url = axis_vapix_continuous_url(
            "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp",
            pan=50,
            tilt=-25,
        )

        self.assertTrue(url.startswith("http://root:pass@192.168.1.50/axis-cgi/com/ptz.cgi?"))
        self.assertIn("continuouspantiltmove=50%2C-25", url)

    def test_axis_vapix_continuous_url_stop_uses_zero_components(self):
        url = axis_vapix_continuous_url(
            "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp",
            pan=0,
            tilt=0,
        )

        self.assertIn("continuouspantiltmove=0%2C0", url)

    def test_axis_vapix_continuous_url_supports_zoom_component(self):
        url = axis_vapix_continuous_url(
            "rtsp://root:pass@192.168.1.50:554/axis-media/media.amp",
            zoom=80,
        )

        self.assertIn("continuouszoommove=80", url)

    def test_send_axis_vapix_request_uses_basic_and_digest_auth_handlers(self):
        captured = {}

        class FakeResponse:
            def __init__(self, data=b"OK"):
                self.data = data

            def read(self):
                return self.data

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class FakeOpener:
            def open(self, url, timeout=None):
                captured["url"] = url
                captured["timeout"] = timeout
                return FakeResponse()

        def fake_build_opener(*handlers):
            captured["handlers"] = handlers
            return FakeOpener()

        with patch.object(ptz_controls, "build_opener", fake_build_opener):
            result = send_axis_vapix_request(
                "http://root:pass@192.168.1.50/axis-cgi/com/ptz.cgi?move=left",
                timeout=2,
            )

        handler_types = {type(handler).__name__ for handler in captured["handlers"]}
        self.assertIn("HTTPDigestAuthHandler", handler_types)
        self.assertIn("HTTPBasicAuthHandler", handler_types)
        self.assertEqual(captured["url"], "http://192.168.1.50/axis-cgi/com/ptz.cgi?move=left")
        self.assertEqual(captured["timeout"], 2)
        self.assertEqual(result, "OK")

    def test_send_axis_vapix_request_returns_empty_for_blank_url(self):
        with patch.object(ptz_controls, "build_opener", lambda *args: None):
            self.assertEqual(send_axis_vapix_request(""), "")


if __name__ == "__main__":
    unittest.main()
