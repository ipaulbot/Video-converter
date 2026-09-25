import unittest

from pc_report.sections import system_slots as mod
from tests.pc_report import support

RAW = [{"SlotDesignation": "PCIEX16_1", "CurrentUsage": 4, "MaxDataWidth": 10, "ConnectorType": [43], "Status": "OK",
        "SupportsHotPlug": False, "BusNumber": 1, "DeviceNumber": 0, "FunctionNumber": 0, "Shared": False, "Number": 1}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        r = mod.build(RAW)["rows"][0]
        self.assertEqual(r["Designation"], "PCIEX16_1")
        self.assertEqual(r["Usage"], "In use")
        self.assertEqual(r["Data Width"], "x16")
        self.assertEqual(r["Bus / Device / Function"], "1 / 0 / 0")
        self.assertEqual(r["Hot Plug"], "No")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Designation</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
