import unittest

from pc_report.sections import processes as mod
from tests.pc_report import support

RAW = [{"Id": 4, "Name": "System", "Description": "", "Company": "", "Version": "", "Path": "", "CommandLine": "",
        "ParentId": 0, "Session": 0, "StartTime": None, "CPU": 1234.5, "WorkingSet": 1048576, "PrivateBytes": 204800,
        "Threads": 200, "Handles": 5000, "Priority": "Normal", "Responding": True, "Owner": ""},
       {"Id": 1000, "Name": "EthoVision", "Description": "EthoVision XT", "Company": "Noldus", "Version": "19.0",
        "Path": "C:\\Program Files\\Noldus\\EV.exe", "CommandLine": "\"C:\\Program Files\\Noldus\\EV.exe\" /x",
        "ParentId": 900, "Session": 1, "StartTime": "/Date(1758000000000)/", "CPU": 10.0, "WorkingSet": 2147483648,
        "PrivateBytes": 1073741824, "Threads": 40, "Handles": 900, "Priority": "High", "Responding": True,
        "Owner": "LAB\\user"}]


class BuildTests(unittest.TestCase):
    def test_rows_and_summary(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Processes"], 2)
        self.assertEqual(rows["Threads"], 240)
        self.assertEqual(rows["Handles"], 5900)
        self.assertEqual(rows["Working Set (total)"], "2.0 GB")
        ev = next(r for r in data["rows"] if r["Name"] == "EthoVision")
        self.assertEqual(ev["Working Set"], "2.0 GB")
        self.assertEqual(ev["CPU Time"], "10 s")
        self.assertEqual(ev["Parent PID"], 900)

    def test_top_lists(self):
        data = mod.build(RAW)
        self.assertEqual(data["top_cpu"][0]["Name"], "System")
        self.assertEqual(data["top_memory"][0]["Name"], "EthoVision")

    def test_owner_is_masked_in_render(self):
        _data, html, _ctx = support.collect_and_render(mod.SECTION)
        self.assertNotIn("\\user<", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Top 10 by CPU time</h3>", html)
        self.assertIn("<th>Command Line</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
