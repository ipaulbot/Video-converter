import re
import unittest

from pc_report.privacy import redact_payload
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

    def test_collect_queries_folders_and_environment_directories(self):
        class Context:
            def __init__(self):
                self.queries = []

            def query(self, name, script):
                self.queries.append((name, script))
                return (
                    [{"Name": "DesktopDirectory", "Path": r"C:\Users\jane\Desktop"}]
                    if name == "folders"
                    else {"SystemRoot": r"C:\Windows"}
                )

        ctx = Context()
        data = mod.collect(ctx)

        self.assertEqual([name for name, _script in ctx.queries], ["folders", "environment_dirs"])
        self.assertIn("GetEnvironmentVariable", ctx.queries[1][1])
        self.assertEqual(data["rows"][0]["Path"], r"C:\Windows")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<td>Desktop Directory</td>", html)
        for row in data["rows"]:
            redacted = redact_payload(row, {"redact": True})
            self.assertIsNone(re.search(r"(?i)[\\/]Users[\\/](?!<redacted>)", redacted["Path"]))

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
