import unittest

from pc_report.sections import mmc_snapins as mod
from tests.pc_report import support

RAW = [{"CLSID": "{1234}", "Name": "Device Manager", "NameString": "Device Manager", "About": "{5678}", "Module": "C:\\Windows\\system32\\devmgr.dll",
        "Version": "10.0.1", "Company": "Microsoft Corporation", "Architecture": "x64"}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(RAW)
        self.assertEqual(data["rows"][0]["Name"], "Device Manager")
        self.assertEqual(data["rows"][0]["Module"], "C:\\Windows\\system32\\devmgr.dll")
        self.assertEqual(dict(data["groups"][0]["rows"])["Snap-ins"], 1)

    def test_indirect_name_falls_back(self):
        data = mod.build([{"CLSID": "{1}", "Name": "@devmgr.dll,-4", "NameString": "", "Module": "", "Version": "", "Company": "", "Architecture": "x64"}])
        self.assertEqual(data["rows"][0]["Name"], "@devmgr.dll,-4")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Module</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
