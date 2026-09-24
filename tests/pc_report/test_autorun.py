import json
import subprocess
import unittest

from pc_report.sections import autorun as mod
from tests.pc_report import support

RUN = [{"Name": "SecurityHealth", "Command": "%windir%\\system32\\SecurityHealthSystray.exe", "Location": "HKLM:\\...\\Run",
        "Enabled": True, "Kind": "Registry"},
       {"Name": "OneDrive", "Command": "C:\\Users\\user\\AppData\\OneDrive.exe /background", "Location": "HKCU:\\...\\Run",
        "Enabled": False, "Kind": "Registry"}]
TASKS = [{"Name": "NoldusUpdate", "Path": "\\Noldus\\", "State": "Ready", "Author": "Noldus", "Action": "C:\\x.exe /u",
          "Triggers": "Daily", "LastRun": "/Date(1758000000000)/", "NextRun": "/Date(1758100000000)/", "LastResult": 0,
          "Run As (account name)": "SYSTEM"}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(RUN, TASKS)
        one = next(r for r in data["entries"] if r["Name"] == "OneDrive")
        self.assertEqual(one["Enabled"], "No")
        self.assertEqual(data["tasks"][0]["Last Result"], "0x0")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Startup Entries"], 2)
        self.assertEqual(rows["Disabled Entries"], 1)
        self.assertEqual(rows["Scheduled Tasks (non-Microsoft)"], 1)

    def test_excludes_tasks_by_microsoft_path_or_author(self):
        tasks = [
            {"Name": "Folder task", "Path": "\\Microsoft\\Windows\\", "Author": "Contoso"},
            {"Name": "OneDrive Reporting Task-S-1-5-21-1-2-3-1001", "Path": "\\",
             "Author": "Microsoft Corporation"},
            {"Name": "Basler update", "Path": "\\", "Author": "Basler AG", "State": "Ready"},
        ]

        data = mod.build([], tasks)

        self.assertEqual([task["Name"] for task in data["tasks"]], ["Basler update"])
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Scheduled Tasks (non-Microsoft)"], 1)

    def test_startup_approval_is_scoped_by_hive_kind_and_name(self):
        prelude = r"""
function Get-ItemProperty {
  param([string]$Path)
  switch ($Path) {
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run' {
      return [pscustomobject]@{ Shared = [byte[]](2) }
    }
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run' {
      return [pscustomobject]@{ Shared = [byte[]](3) }
    }
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run' {
      return [pscustomobject]@{ Shared = 'machine.exe' }
    }
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' {
      return [pscustomobject]@{ Shared = 'user.exe'; NoApproval = 'default.exe' }
    }
  }
}
function Test-Path { return $false }
"""
        script = prelude + "\n$result = & {\n" + mod.RUN_SCRIPT + "\n}\n@($result) | ConvertTo-Json -Compress\n"
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            check=True,
        )
        entries = json.loads(completed.stdout)
        by_location_and_name = {(entry["Location"], entry["Name"]): entry for entry in entries}

        self.assertTrue(by_location_and_name[(
            "HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", "Shared"
        )]["Enabled"])
        self.assertFalse(by_location_and_name[(
            "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", "Shared"
        )]["Enabled"])
        self.assertTrue(by_location_and_name[(
            "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", "NoApproval"
        )]["Enabled"])

    def test_queries_every_startup_approval_hive_and_kind(self):
        for hive in ("HKLM", "HKCU"):
            for kind in ("Run", "Run32", "StartupFolder"):
                path = (
                    f"{hive}:\\Software\\Microsoft\\Windows\\CurrentVersion"
                    f"\\Explorer\\StartupApproved\\{kind}"
                )
                with self.subTest(path=path):
                    self.assertIn(path, mod.RUN_SCRIPT)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Startup entries</h3>", html)
        self.assertIn("<h3>Scheduled tasks</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
