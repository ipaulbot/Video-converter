import unittest

from pc_report.sections import usb as mod
from tests.pc_report import support

CTRL = [{"Name": "Intel(R) USB 3.20 eXtensible Host Controller", "Manufacturer": "Intel", "Status": "OK", "PNPDeviceID": "PCI\\VEN_8086&DEV_7AE0\\3", "ProtocolSupported": 16}]
HUBS = [{"Name": "USB Root Hub (USB 3.0)", "DeviceID": "USB\\ROOT_HUB30\\4", "Status": "OK", "PNPDeviceID": "USB\\ROOT_HUB30\\4", "Description": "USB Root Hub (USB 3.0)"}]
DEV = [{"InstanceId": "USB\\VID_0529&PID_0001\\5&1", "FriendlyName": "SafeNet Inc. Sentinel HASP Key", "Class": "USB", "Manufacturer": "SafeNet Inc.",
        "Status": "OK", "Present": True, "Service": "hardlock", "Parent": "USB\\ROOT_HUB30\\4"},
       {"InstanceId": "USB\\VID_2676&PID_BA02\\123", "FriendlyName": "Basler ace acA1920", "Class": "Camera", "Manufacturer": "Basler",
        "Status": "OK", "Present": True, "Service": "usbvideo", "Parent": "USB\\ROOT_HUB30\\4"}]
SUSPEND = """Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
  Subgroup GUID: 2a737441-1930-4402-8d77-b2bebba308a3  (USB settings)
    Power Setting GUID: 48e6b7a6-50f5-4782-a5d4-53bb50f7e3f1  (USB selective suspend setting)
      Possible Setting Index: 000
      Possible Setting Friendly Name: Disabled
      Possible Setting Index: 001
      Possible Setting Friendly Name: Enabled
    Current AC Power Setting Index: 0x00000000
    Current DC Power Setting Index: 0x00000001
"""


class BuildTests(unittest.TestCase):
    def test_devices_and_suspend(self):
        data = mod.build(CTRL, HUBS, DEV, SUSPEND)
        hasp = next(r for r in data["devices"] if r["Name"].startswith("SafeNet"))
        self.assertEqual(hasp["VID / PID"], "0529 / 0001")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Selective Suspend (AC)"], "Disabled")
        self.assertEqual(rows["Selective Suspend (DC)"], "Enabled")
        self.assertEqual(rows["USB Devices Present"], 2)
        self.assertEqual(mod.hasp_devices(data), ["SafeNet Inc. Sentinel HASP Key"])

    def test_controller_version(self):
        data = mod.build(CTRL, HUBS, DEV, "")
        self.assertEqual(data["controllers"][0]["USB Version"], "USB")
        self.assertEqual(dict(data["groups"][0]["rows"])["Selective Suspend (AC)"], "")

    def test_localised_suspend_and_device_details(self):
        devices = [
            {**DEV[0], "Address": 10, "Speed": "SuperSpeed", "Problem": 10},
            {**DEV[1], "Address": 2, "Parent": "USB\\ROOT_HUB20\\1"},
        ]
        data = mod.build(CTRL, HUBS, devices, "Aktueller Wechselstromeinstellungsindex: 0x00000001")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Selective Suspend (AC)"], "Unknown")
        self.assertEqual(data["devices"][0]["Name"], "Basler ace acA1920")
        self.assertEqual(data["devices"][1]["Speed"], "SuperSpeed")
        self.assertEqual(data["devices"][1]["Problem"], "10: Cannot start")

    def test_hasp_detection_uses_required_vid_or_names(self):
        data = {"devices": [
            {"Name": "License key", "VID / PID": "0529 / 0001"},
            {"Name": "Sentinel Runtime", "VID / PID": ""},
            {"Name": "Hardlock only", "VID / PID": "1234 / 0001"},
        ]}
        self.assertEqual(mod.hasp_devices(data), ["License key", "Sentinel Runtime"])

    def test_collect_reports_unavailable_suspend_as_unknown(self):
        class Ctx:
            def __init__(self):
                self.notes = []

            def text(self, *_args, **_kwargs):
                return ""

            def query(self, *_args, **_kwargs):
                return []

            def note(self, text):
                self.notes.append(text)

        ctx = Ctx()
        data = mod.collect(ctx)

        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Selective Suspend (AC)"], "Unknown")
        self.assertEqual(rows["Selective Suspend (DC)"], "Unknown")
        self.assertTrue(any("selective suspend" in note.lower() for note in ctx.notes))


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>VID / PID</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
