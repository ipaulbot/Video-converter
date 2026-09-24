import unittest

from pc_report.sections import system_directories as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_names_are_humanised_and_env_dirs_come_first(self):
        data = mod.build([{"Name": "ApplicationData", "Path": "C:\\Users\\user\\AppData\\Roaming"},
                          {"Name": "CommonProgramFiles", "Path": "C:\\Program Files\\Common Files"}],
                         {"SystemRoot": "C:\\Windows"})
        self.assertEqual(data["rows"][0], {"Name": "System Root", "Path": "C:\\Windows", "Source": "Environment"})
        names = [r["Name"] for r in data["rows"]]
        self.assertIn("Application Data", names)
        self.assertIn("Common Program Files", names)

    def test_humanise(self):
        self.assertEqual(mod.humanise("MyDocuments"), "My Documents")
        self.assertEqual(mod.humanise("CDBurning"), "CD Burning")
        self.assertEqual(mod.humanise("ProgramFilesX86"), "Program Files X86")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<td>Desktop Directory</td>", html)
        self.assertNotIn("C:\\Users\\user\\", html)  # scrubbed to user, then redacted

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
