import unittest

from pc_report.sections import environment as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_variables_are_grouped_by_scope(self):
        data = mod.build([{"Scope": "Machine", "Name": "Path", "Value": "C:\\Windows"},
                          {"Scope": "User", "Name": "TEMP", "Value": "C:\\Users\\user\\Temp"},
                          {"Scope": "Process", "Name": "USERNAME", "Value": "user"}])
        self.assertEqual([r["Name"] for r in data["Machine"]], ["Path"])
        self.assertEqual([r["Name"] for r in data["User"]], ["TEMP"])
        self.assertEqual(data["Process"][0]["Name"], "USERNAME")

    def test_render_has_three_headings_and_masks_username(self):
        data = mod.build([{"Scope": "Process", "Name": "USERNAME", "Value": "patrick"}])
        from pc_report.privacy import redact_payload
        html = mod.render(redact_payload(data, {"redact": True}), support.render_ctx())
        self.assertIn("<h3>Process</h3>", html)
        self.assertNotIn("patrick", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<td>Path</td>", html)
        self.assertIn("<h3>Machine</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
