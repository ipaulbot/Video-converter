import unittest

from pc_report.sections import autorun as mod
from tests.pc_report import support

RUN = [{"Name": "SecurityHealth", "Command": "%windir%\\system32\\SecurityHealthSystray.exe", "Location": "HKLM:\\...\\Run",
        "Enabled": True, "Kind": "Registry"},
       {"Name": "OneDrive", "Command": "C:\\Users\\user\\AppData\\OneDrive.exe /background", "Location": "HKCU:\\...\\Run",
        "Enabled": False, "Kind": "Registry"}]
TASKS = [{"Name": "NoldusUpdate", "Path": "\\Noldus\\", "State": "Ready", "Author": "Noldus", "Action": "C:\\x.exe /u",
          "Triggers": "Daily", "LastRun": "/Date(1758000000000)/", "NextRun": "/Date(1758100000000)/", "LastResult": 0,
          "Run As (account name)": "SYSTEM"}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(RUN, TASKS)
        one = next(r for r in data["entries"] if r["Name"] == "OneDrive")
        self.assertEqual(one["Enabled"], "No")
        self.assertEqual(data["tasks"][0]["Last Result"], "0x0")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Startup Entries"], 2)
        self.assertEqual(rows["Disabled Entries"], 1)
        self.assertEqual(rows["Scheduled Tasks (non-Microsoft)"], 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Startup entries</h3>", html)
        self.assertIn("<h3>Scheduled tasks</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
