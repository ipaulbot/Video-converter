import unittest

from pc_report.sections import system_files as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_rows_are_formatted(self):
        data = mod.build([{"Name": "hosts", "Path": "C:\\Windows\\System32\\drivers\\etc\\hosts", "Size": 824,
                           "Modified": "/Date(1700000000000)/", "Entries": 2},
                          {"Name": "win.ini", "Path": "C:\\Windows\\win.ini", "Size": "", "Modified": "", "Entries": "missing"}])
        self.assertEqual(data["rows"][0]["Size"], "824.0 B")
        self.assertEqual(data["rows"][0]["Hosts Entries"], 2)
        self.assertEqual(data["rows"][1]["Status"], "Missing")
        self.assertEqual(data["rows"][0]["Status"], "Present")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for name in ("hosts", "services", "win.ini", "system.ini"):
            self.assertIn(f"<td>{name}</td>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
