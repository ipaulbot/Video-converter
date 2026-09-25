import unittest

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


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Direction</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
