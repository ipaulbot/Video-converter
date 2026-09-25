import unittest

from pc_report.sections import devices as mod
from tests.pc_report import support

PNP = [{"Name": "Basler ace acA1920", "Manufacturer": "Basler", "PNPClass": "Camera", "ClassGuid": "{ca3e7ab9}", "DeviceID": "USB\\VID_2676&PID_BA02\\123",
        "PNPDeviceID": "USB\\VID_2676&PID_BA02\\123", "Status": "OK", "ConfigManagerErrorCode": 0, "Service": "usbvideo", "Present": True, "Description": "Basler camera"},
       {"Name": "Unknown device", "Manufacturer": "", "PNPClass": None, "ClassGuid": None, "DeviceID": "ACPI\\PNP0A0A\\0",
        "PNPDeviceID": "ACPI\\PNP0A0A\\0", "Status": "Error", "ConfigManagerErrorCode": 28, "Service": None, "Present": True, "Description": "Unknown device"},
       {"Name": "Old printer", "Manufacturer": "HP", "PNPClass": "Printer", "ClassGuid": "{x}", "DeviceID": "SWD\\PRINTENUM\\1",
        "PNPDeviceID": "SWD\\PRINTENUM\\1", "Status": "Unknown", "ConfigManagerErrorCode": 0, "Service": None, "Present": False, "Description": "Printer"}]


class BuildTests(unittest.TestCase):
    def test_problems_first_and_grouping(self):
        data = mod.build(PNP)
        self.assertEqual(data["problems"][0]["Problem"], "28: Drivers not installed")
        self.assertIn("Camera", data["by_class"])
        self.assertIn("(No class)", data["by_class"])
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Devices"], 3)
        self.assertEqual(rows["Present"], 2)
        self.assertEqual(rows["Problem Devices"], 1)
        self.assertEqual(rows["Not Present (phantom)"], 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Problem devices</h3>", html)
        self.assertIn("<th>Service</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
