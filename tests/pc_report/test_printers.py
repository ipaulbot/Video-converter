import unittest

from pc_report.sections import printers as mod
from tests.pc_report import support

PR = [{"Name": "Microsoft Print to PDF", "DriverName": "Microsoft Print To PDF", "PortName": "PORTPROMPT:", "Default": True, "Shared": False,
       "ShareName": "", "Network": False, "Local": True, "PrinterStatus": 3, "Location": "", "WorkOffline": False, "Comment": "",
       "PrintProcessor": "winprint", "Priority": 1}]
SP = {"State": "Running", "StartMode": "Auto"}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(PR, SP)
        self.assertEqual(data["rows"][0]["Status"], "Idle")
        self.assertEqual(data["rows"][0]["Default"], "Yes")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Print Spooler"], "Running (Auto)")
        self.assertEqual(rows["Default Printer"], "Microsoft Print to PDF")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Print Spooler</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
