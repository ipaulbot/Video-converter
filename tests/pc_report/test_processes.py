import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import processes as mod
from tests.pc_report import support

RAW = [{"Id": 4, "Name": "System", "Description": "", "Company": "", "Version": "", "Path": "", "CommandLine": "",
        "ParentId": 0, "Session": 0, "StartTime": None, "CPU": 1234.5, "WorkingSet": 1048576, "PrivateBytes": 204800,
        "Threads": 200, "Handles": 5000, "Priority": "Normal", "Responding": True, "Owner": ""},
       {"Id": 1000, "Name": "EthoVision", "Description": "EthoVision XT", "Company": "Noldus", "Version": "19.0",
        "Path": "C:\\Program Files\\Noldus\\EV.exe", "CommandLine": "\"C:\\Program Files\\Noldus\\EV.exe\" /x",
        "ParentId": 900, "Session": 1, "StartTime": "/Date(1758000000000)/", "CPU": 10.0, "WorkingSet": 2147483648,
        "PrivateBytes": 1073741824, "Threads": 40, "Handles": 900, "Priority": "High", "Responding": True,
        "Owner": "LAB\\user"}]


class BuildTests(unittest.TestCase):
    def test_rows_and_summary(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Processes"], 2)
        self.assertEqual(rows["Threads"], 240)
        self.assertEqual(rows["Handles"], 5900)
        self.assertEqual(rows["Working Set (total)"], "2.0 GB")
        ev = next(r for r in data["rows"] if r["Name"] == "EthoVision")
        self.assertEqual(ev["Working Set"], "2.0 GB")
        self.assertEqual(ev["CPU Time"], "10 s")
        self.assertEqual(ev["Parent PID"], 900)

    def test_top_lists(self):
        data = mod.build(RAW)
        self.assertEqual(data["top_cpu"][0]["Name"], "System")
        self.assertEqual(data["top_memory"][0]["Name"], "EthoVision")

    def test_owner_is_masked_in_render(self):
        _data, html, _ctx = support.collect_and_render(mod.SECTION)
        self.assertNotIn("\\user<", html)

    def test_rows_are_capped_with_shown_and_total(self):
        raw = [{"Id": index, "Name": f"Process {index:04d}"} for index in range(mod.ROW_CAP + 1)]
        data = mod.build(raw)
        summary = data["groups"][0]["rows"]
        self.assertEqual(len(data["rows"]), mod.ROW_CAP)
        self.assertEqual(summary["Shown"], mod.ROW_CAP)
        self.assertEqual(summary["Total"], mod.ROW_CAP + 1)

    def test_collect_notes_when_rows_are_truncated(self):
        class Ctx:
            notes = []

            def query(self, *_args, **_kwargs):
                return [{"Id": index, "Name": f"Process {index:04d}"} for index in range(mod.ROW_CAP + 1)]

            def note(self, text):
                self.notes.append(text)

        ctx = Ctx()
        mod.collect(ctx)
        self.assertEqual(ctx.notes, [f"processes: showing {mod.ROW_CAP} of {mod.ROW_CAP + 1} rows"])


class PrivacyTests(unittest.TestCase):
    def _html(self, command):
        data = mod.build([{**RAW[1], "CommandLine": command}])
        return mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

    def test_command_lines_lose_credentials_in_every_option_form(self):
        for form in ("--password hunter2", "--token=hunter2", "/key:hunter2"):
            with self.subTest(form=form):
                html = self._html(f"collector.exe {form}")
                self.assertNotIn("hunter2", html)
                self.assertIn("collector.exe", html)

    def test_command_lines_lose_remote_hosts_addresses_and_identities(self):
        html = self._html(
            "collector.exe --db postgres://svc:pw@db.corp.example:5432/x --peer 203.0.113.44 "
            r"--share \\FILESRV\data --alert ops@corp.example"
        )

        for sensitive in ("db.corp.example", "svc:pw", "203.0.113.44", "FILESRV", "ops@corp.example"):
            self.assertNotIn(sensitive, html)
        self.assertIn("collector.exe", html)
        self.assertIn("postgres://", html)
        self.assertIn(":5432", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Top 10 by CPU time</h3>", html)
        self.assertIn("<th>Command Line</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
