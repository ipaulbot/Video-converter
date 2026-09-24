import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import operating_system as mod
from tests.pc_report import support

OS = {"Caption": "Microsoft Windows 11 Enterprise LTSC", "Version": "10.0.26100", "BuildNumber": "26100",
      "OSArchitecture": "64-bit", "InstallDate": "/Date(1750000000000)/", "LastBootUpTime": "/Date(1758500000000)/",
      "WindowsDirectory": "C:\\Windows", "SystemDirectory": "C:\\Windows\\system32", "BootDevice": "\\Device\\HarddiskVolume2",
      "SystemDevice": "\\Device\\HarddiskVolume4", "SystemStartOptions": "NOEXECUTE=OPTIN", "OSLanguage": 1033,
      "MUILanguages": ["en-US", "nl-NL"], "CSName": "PC-NAME", "Description": "Lab PC", "OperatingSystemSKU": 125,
      "ProductType": 1, "DataExecutionPrevention_Available": True, "DataExecutionPrevention_SupportPolicy": 2,
      "EncryptionLevel": 256, "RegisteredUser": "user", "Organization": "Lab"}
VER = {"ProductName": "Windows 10 Enterprise LTSC 2024", "EditionID": "EnterpriseS", "DisplayVersion": "24H2",
       "CurrentBuild": "26100", "UBR": 9445, "BuildLab": "26100.ge_release.240331-1435",
       "BuildLabEx": "26100.1.amd64fre.ge_release.240331-1435", "BuildBranch": "ge_release",
       "InstallationType": "Client", "RegisteredOwner": "user", "RegisteredOrganization": "Lab"}
POL = {"EnableLUA": 0, "ConsentPromptBehaviorAdmin": 5, "SecureBoot": 1, "LongPathsEnabled": 1, "HiberbootEnabled": 0,
       "HibernateEnabled": 1, "NoAutoUpdate": None, "AUOptions": 4, "InsiderBranch": None, "DisableSR": 1,
       "RebootPendingCBS": False, "RebootRequiredWU": True, "PendingFileRename": False, "FirmwareType": "UEFI",
       "SafeMode": None, "KernelVersion": "10.0.26100.9444", "DotNetRelease": 533320}
LIC = {"Name": "Windows(R), Enterprise edition", "Description": "Windows(R) Operating System, VOLUME_KMSCLIENT channel",
       "LicenseStatus": 1, "GracePeriodRemaining": 259041, "PartialProductKey": "ABCDE", "ProductKeyChannel": "Volume:GVLK"}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.rows = mod.flatten(mod.build(OS, VER, POL, LIC))

    def test_windows_group(self):
        self.assertEqual(self.rows["Name"], "Microsoft Windows 11 Enterprise LTSC")
        self.assertEqual(self.rows["Version"], "24H2 (OS Build 26100.9445)")
        self.assertEqual(self.rows["SKU"], "Enterprise LTSC")
        self.assertEqual(self.rows["Kernel Version"], "10.0.26100.9444")
        self.assertEqual(self.rows["Product Type"], "Workstation")
        self.assertEqual(self.rows["Language"], "English (United States)")
        self.assertEqual(self.rows["Computer Name"], "PC-NAME")

    def test_activation_group(self):
        self.assertEqual(self.rows["Activation Status"], "Licensed")
        self.assertEqual(self.rows["License Channel"], "Volume:GVLK")
        self.assertEqual(self.rows["Remaining Grace Period"], "179 days, 21 hours, 21 minutes")

    def test_boot_and_policy_groups(self):
        self.assertEqual(self.rows["Boot Device"], "\\Device\\HarddiskVolume2")
        self.assertEqual(self.rows["Pending Reboot"], "Yes")
        self.assertEqual(self.rows["UAC Enabled"], "No")
        self.assertEqual(self.rows["UAC Prompt (Administrators)"], "Prompt for consent for non-Windows binaries")
        self.assertEqual(self.rows["Secure Boot"], "Yes")
        self.assertEqual(self.rows["DEP Policy"], "Opt in (Windows programs only)")
        self.assertEqual(self.rows["Automatic Updates"], "Automatically download and schedule installation")
        self.assertEqual(self.rows["System Restore"], "Disabled")
        self.assertEqual(self.rows[".NET Framework 4.x"], "4.8.1")
        self.assertEqual(self.rows["Fast Startup"], "No")
        self.assertEqual(self.rows["Safe Mode"], "No")

    def test_missing_inputs_do_not_raise(self):
        rows = mod.flatten(mod.build({}, {}, {}, {}))
        self.assertEqual(rows["Activation Status"], "Unknown")
        self.assertEqual(rows["Version"], "")

    def test_value_of(self):
        data = mod.build(OS, VER, POL, LIC)
        self.assertEqual(mod.value_of(data, "Name"), "Microsoft Windows 11 Enterprise LTSC")
        self.assertEqual(mod.value_of(None, "Name"), "")

    def test_value_of_first_match_across_groups(self):
        data = {
            "groups": [
                {"title": "A", "rows": {"Name": "first"}},
                {"title": "B", "rows": {"Name": "second"}},
            ]
        }
        self.assertEqual(mod.value_of(data, "Name"), "first")

    def test_version_without_build_fields(self):
        rows = mod.flatten(mod.build({}, {"DisplayVersion": "24H2"}, {}, {}))
        self.assertEqual(rows["Version"], "24H2")

    def test_version_with_build_no_ubr(self):
        rows = mod.flatten(mod.build({}, {"DisplayVersion": "24H2", "CurrentBuild": "26100"}, {}, {}))
        self.assertEqual(rows["Version"], "24H2 (OS Build 26100)")

    def test_computer_name_masked_when_rendered(self):
        data = mod.build(OS, VER, POL, LIC)
        html = mod.render(redact_payload(data, {"redact": True}), support.render_ctx())
        self.assertIn("<th>Computer Name</th>", html)
        self.assertNotIn(OS["CSName"], html, "computer name must be masked")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Name", "Version", "Kernel Version", "Build Lab Ex", "Activation Status",
                      "Boot Time", "Up Time", "UAC Enabled", "Secure Boot", "Pending Reboot"):
            self.assertIn(f"<th>{label}</th>", html, label)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
