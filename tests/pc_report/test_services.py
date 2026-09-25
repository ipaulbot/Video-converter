import unittest

from pc_report.sections import services as mod
from tests.pc_report import support

RAW = [{"Name": "FrameServer", "DisplayName": "Windows Camera Frame Server", "State": "Stopped", "StartMode": "Manual",
        "StartName": "LocalSystem", "PathName": "C:\\Windows\\system32\\svchost.exe -k Camera",
        "ProcessId": 0, "Description": "Enables multiple clients to access video frames", "ServiceType": "Share Process",
        "DelayedAutoStart": False, "ExitCode": 1077},
       {"Name": "hasplms", "DisplayName": "Sentinel LDK License Manager", "State": "Running", "StartMode": "Auto",
        "StartName": "LocalSystem", "PathName": "C:\\Windows\\system32\\hasplms.exe -run", "ProcessId": 4321,
        "Description": "", "ServiceType": "Own Process", "DelayedAutoStart": True, "ExitCode": 0}]


class BuildTests(unittest.TestCase):
    def test_rows_and_summary(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Services"], 2)
        self.assertEqual(rows["Running"], 1)
        self.assertEqual(rows["Automatic (Delayed)"], 1)
        hasp = next(r for r in data["rows"] if r["Name"] == "hasplms")
        self.assertEqual(hasp["Start Mode"], "Automatic (Delayed)")
        self.assertEqual(hasp["PID"], 4321)
        fs = next(r for r in data["rows"] if r["Name"] == "FrameServer")
        self.assertEqual(fs["PID"], "")
        self.assertEqual(fs["Exit Code"], 1077)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Start Mode</th>", html)
        self.assertIn("<th>Services</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
