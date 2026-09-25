import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import sound as mod
from tests.pc_report import support

DEV = [{"Name": "Realtek(R) Audio", "Manufacturer": "Realtek", "Status": "OK", "StatusInfo": 3, "PNPDeviceID": "HDAUDIO\\FUNC_01&VEN_10EC\\1", "ConfigManagerErrorCode": 0}]
ENDPOINTS = [{"FriendlyName": "Speakers (Realtek(R) Audio)", "Status": "OK", "InstanceId": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{aaaa}", "Present": True},
             {"FriendlyName": "Microphone (USB Camera)", "Status": "OK", "InstanceId": "SWD\\MMDEVAPI\\{0.0.1.00000000}.{bbbb}", "Present": True}]
DRIVERS = [{"DeviceName": "Realtek(R) Audio", "DriverVersion": "6.0.9.1", "DriverDate": "20230301000000.000000-000", "DriverProviderName": "Realtek"}]
DX = {"SoundDevices": {"SoundDevice": {"Description": "Speakers (Realtek(R) Audio)", "DefaultSoundPlayback": "True", "DefaultVoicePlayback": "True",
                                       "HardwareID": "HDAUDIO\\FUNC_01&VEN_10EC", "DriverName": "RTKVHD64.sys", "DriverVersion": "6.0.9.1", "DriverProvider": "Realtek"}},
      "SoundCaptureDevices": {"SoundCaptureDevice": {"Description": "Microphone (USB Camera)", "DefaultSoundRecording": "True", "DriverName": "usbaudio.sys", "DriverVersion": "10.0.1"}}}


class BuildTests(unittest.TestCase):
    def test_devices_endpoints_defaults(self):
        data = mod.build(DEV, ENDPOINTS, DRIVERS, DX)
        d = data["devices"][0]
        self.assertEqual(d["Driver Version"], "6.0.9.1")
        self.assertEqual(d["Driver Date"], "2023-03-01")
        self.assertEqual(data["endpoints"][0]["Direction"], "Playback")
        self.assertEqual(data["endpoints"][1]["Direction"], "Capture")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Default Playback"], "Speakers (Realtek(R) Audio)")
        self.assertEqual(rows["Default Capture"], "Microphone (USB Camera)")

    def test_numeric_dxdiag_flags_select_defaults(self):
        dx = {
            "SoundDevices": {"SoundDevice": [
                {"Description": "Not Default", "DefaultSoundPlayback": "0"},
                {"Description": "Default Speakers", "DefaultSoundPlayback": "1"},
            ]},
            "SoundCaptureDevices": {"SoundCaptureDevice": [
                {"Description": "Default Microphone", "DefaultSoundRecording": "1"},
                {"Description": "Not Default", "DefaultSoundRecording": "0"},
            ]},
        }

        rows = dict(mod.build([], [], [], dx)["groups"][0]["rows"])

        self.assertEqual(rows["Default Playback"], "Default Speakers")
        self.assertEqual(rows["Default Capture"], "Default Microphone")

    def test_endpoint_instance_id_remains_redactable(self):
        endpoint_id = r"SWD\MMDEVAPI\{0.0.0.00000000}.{0123abcd-4567-89ab-cdef-0123456789ab}"

        data = mod.build([], [{"FriendlyName": "Speakers", "InstanceId": endpoint_id}], [], {})
        redacted = redact_payload(data, {"redact": True}, env={})

        self.assertIn("InstanceId", redacted["endpoints"][0])
        self.assertNotEqual(redacted["endpoints"][0]["InstanceId"], endpoint_id)


class PrivacyTests(unittest.TestCase):
    def test_default_endpoint_summaries_mask_a_personal_device_name(self):
        dx = {"SoundDevices": {"SoundDevice": {"Description": "Jan's AirPods", "DefaultSoundPlayback": "1"}},
              "SoundCaptureDevices": {"SoundCaptureDevice": {"Description": "Jan's AirPods", "DefaultSoundRecording": "1"}}}
        endpoints = [{"FriendlyName": "Jan's AirPods", "InstanceId": r"SWD\MMDEVAPI\{0.0.0.00000000}.{a}"}]

        data = mod.build(DEV, endpoints, DRIVERS, dx)
        html = mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

        self.assertNotIn("Jan", html)
        self.assertIn("AirPods", html)
        self.assertIn("<th>Default Playback</th>", html)

    def test_ordinary_endpoint_names_stay_readable(self):
        html = mod.render(redact_payload(mod.build(DEV, ENDPOINTS, DRIVERS, DX), {"redact": True}, env={}),
                          support.render_ctx())

        self.assertIn("Speakers (Realtek(R) Audio)", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Direction</th>", html)
        self.assertRegex(html, r"Default Playback</th><td>(?!\s*</td>)")
        self.assertRegex(html, r"Default Capture</th><td>(?!\s*</td>)")

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
