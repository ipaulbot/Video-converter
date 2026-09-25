import unittest

from pc_report.privacy import redact_payload
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


class PrivacyTests(unittest.TestCase):
    def _html(self, variables):
        data = mod.build(variables)
        return mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

    def test_values_are_masked_by_content_when_the_name_says_nothing(self):
        variables = [
            {"Scope": "Machine", "Name": "NVC_SERVER", "Value": "cam-srv-01.corp.example"},
            {"Scope": "Machine", "Name": "DATABASE_URL", "Value": "postgres://u:p@db.corp.example:5432/x"},
            {"Scope": "User", "Name": "SUPPORT_EMAIL", "Value": "ops@corp.example"},
        ]

        html = self._html(variables)

        for sensitive in ("cam-srv-01.corp.example", "db.corp.example", "u:p@", "ops@corp.example"):
            self.assertNotIn(sensitive, html)
        # The variable names stay, so the reader still knows what is configured.
        self.assertIn("DATABASE_URL", html)
        self.assertIn("postgres://", html)

    def test_ordinary_values_are_left_alone(self):
        variables = [
            {"Scope": "Machine", "Name": "Path", "Value": r"C:\Windows\system32;C:\Program Files\dotnet"},
            {"Scope": "Machine", "Name": "PSModulePath", "Value": r"C:\Program Files\WindowsPowerShell\Modules"},
            {"Scope": "Machine", "Name": "NUMBER_OF_PROCESSORS", "Value": "8"},
            {"Scope": "Machine", "Name": "OS", "Value": "Windows_NT"},
        ]

        html = self._html(variables)

        for value in (r"C:\Windows\system32", "WindowsPowerShell", ">8<", "Windows_NT"):
            self.assertIn(value, html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<td>Path</td>", html)
        self.assertIn("<h3>Machine</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
