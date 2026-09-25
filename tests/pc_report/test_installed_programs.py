import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import installed_programs as mod
from tests.pc_report import support

REG = [{"Name": "EthoVision XT 19", "Version": "19.0.1912", "Publisher": "Noldus", "InstallDate": "20260522",
        "InstallLocation": "C:\\Program Files\\Noldus\\EthoVision XT", "InstallSource": "D:\\", "EstimatedSize": 2048000,
        "Uninstall": "MsiExec.exe /X{GUID}", "Architecture": "x64", "Scope": "Machine", "SystemComponent": None},
       {"Name": "Noldus - IPP - X64 Package - 8", "Version": "8.0", "Publisher": "Noldus", "InstallDate": "",
        "InstallLocation": "", "InstallSource": "", "EstimatedSize": None, "Uninstall": "", "Architecture": "x64",
        "Scope": "Machine", "SystemComponent": 1}]
PKG = [{"Name": "EthoVision XT 19", "Version": "19.0.1912", "Publisher": "Noldus", "ProviderName": "msi"}]
APPX = [{"Name": "Microsoft.WindowsCalculator", "Version": "11.0", "Publisher": "Microsoft Corporation",
         "InstallDate": "2026-01-02", "InstallLocation": "C:\\Program Files\\WindowsApps\\Calc", "Architecture": "X64"}]


class BuildTests(unittest.TestCase):
    def test_rows_are_normalised_and_deduplicated(self):
        data = mod.build(REG, PKG, APPX)
        names = [r["Name"] for r in data["rows"]]
        self.assertEqual(names.count("EthoVision XT 19"), 1)
        etho = next(r for r in data["rows"] if r["Name"] == "EthoVision XT 19")
        self.assertEqual(etho["Install Date"], "2026-05-22")
        self.assertEqual(etho["Size"], "2.0 GB")
        self.assertEqual(etho["Hidden"], "No")
        ipp = next(r for r in data["rows"] if r["Name"].startswith("Noldus - IPP"))
        self.assertEqual(ipp["Hidden"], "Yes")
        calc = next(r for r in data["rows"] if r["Name"].startswith("Microsoft.Windows"))
        self.assertEqual(calc["Source"], "Microsoft Store")

    def test_rows_are_sorted_case_insensitively(self):
        data = mod.build([{"Name": "beta"}, {"Name": "Alpha"}], [], [])
        self.assertEqual([r["Name"] for r in data["rows"]], ["Alpha", "beta"])

    def test_summary_counts(self):
        rows = dict(mod.build(REG, PKG, APPX)["groups"][0]["rows"])
        self.assertEqual(rows["Programs"], 3)
        self.assertEqual(rows["Hidden (system components)"], 1)
        self.assertEqual(rows["Microsoft Store apps"], 1)

    def test_dedupe_name_version_merges_publisher_from_registry(self):
        reg = [{"Name": "QuickTime", "Version": "7.79", "Publisher": "Apple Inc."}]
        pkg = [{"Name": "QuickTime", "Version": "7.79", "Publisher": "", "ProviderName": "msi"}]
        data = mod.build(reg, pkg, [])
        qt = [r for r in data["rows"] if r["Name"] == "QuickTime"]
        self.assertEqual(len(qt), 1)
        self.assertEqual(qt[0]["Publisher"], "Apple Inc.")

    def test_dedupe_name_version_merges_install_date_from_package(self):
        reg = [{"Name": "QuickTime", "Version": "7.79", "Publisher": "Apple Inc.", "InstallDate": ""}]
        pkg = [{"Name": "QuickTime", "Version": "7.79", "Publisher": "", "ProviderName": "msi",
                "InstallDate": "20250107"}]
        data = mod.build(reg, pkg, [])
        qt = next(r for r in data["rows"] if r["Name"] == "QuickTime")
        self.assertEqual(qt["Install Date"], "2025-01-07")


class PrivacyTests(unittest.TestCase):
    def test_uninstall_strings_lose_credential_options(self):
        for form in ("--password hunter2", "--token=hunter2", "/key:hunter2"):
            with self.subTest(form=form):
                reg = [{"Name": "Lab Agent", "Uninstall": f"un.exe {form}"}]
                html = mod.render(redact_payload(mod.build(reg, [], []), {"redact": True}, env={}),
                                  support.render_ctx())
                self.assertNotIn("hunter2", html)
                self.assertIn("un.exe", html)

    def test_uninstall_strings_keep_readable_paths_and_switches(self):
        reg = [{"Name": "EthoVision XT 19", "Uninstall": r'"C:\Program Files\Noldus\un.exe" /S --mode=quiet'}]

        html = mod.render(redact_payload(mod.build(reg, [], []), {"redact": True}, env={}), support.render_ctx())

        self.assertIn("--mode=quiet", html)
        self.assertIn("Noldus", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Publisher</th>", html)
        self.assertIn("<th>Programs</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
