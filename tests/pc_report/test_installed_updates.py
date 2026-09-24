import unittest

from pc_report.sections import installed_updates as mod
from tests.pc_report import support

HOTFIX = [{"HotFixID": "KB5062660", "Description": "Update", "InstalledOn": "/Date(1750000000000)/", "InstalledBy": "NT AUTHORITY\\SYSTEM"}]
HISTORY = [
    {"Date": "/Date(1758000000000)/", "Title": "2026-09 Cumulative Update (KB5124007)", "KB": "KB5124007", "Operation": 1, "Result": 2, "Client": "MoUpdateOrchestrator"},
    {"Date": "/Date(1755000000000)/", "Title": "Defender Antivirus platform", "KB": "", "Operation": 1, "Result": 4, "Client": "UpdateOrchestrator"},
]


class BuildTests(unittest.TestCase):
    def test_hotfix_rows(self):
        data = mod.build(HOTFIX, HISTORY)
        self.assertEqual(data["hotfixes"][0]["KB"], "KB5062660")
        self.assertRegex(data["hotfixes"][0]["Installed On"], r"^\d{4}-\d{2}-\d{2}$")

    def test_history_is_newest_first_and_decoded(self):
        data = mod.build(HOTFIX, HISTORY)
        self.assertEqual(data["history"][0]["KB"], "KB5124007")
        self.assertEqual(data["history"][0]["Operation"], "Installation")
        self.assertEqual(data["history"][0]["Result"], "Succeeded")
        self.assertEqual(data["history"][1]["Result"], "Failed")
        self.assertRegex(data["history"][0]["Month"], r"^\d{4}-\d{2}$")

    def test_render_groups_history_by_month(self):
        html = mod.render(mod.build(HOTFIX, HISTORY), support.render_ctx())
        self.assertIn("<h3>Installed hotfixes</h3>", html)
        self.assertEqual(html.count("<h3>Windows Update history"), 1)
        self.assertGreaterEqual(html.count('class="sub"'), 2)
        self.assertIn("✖ Failed", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>KB</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
