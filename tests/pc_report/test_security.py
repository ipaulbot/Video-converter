import json
import os
import tempfile
import unittest
from pathlib import Path

from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import security as mod
from tests.pc_report import support

SC = [{"Kind": "AntiVirusProduct", "Name": "Windows Defender", "State": 397568, "Path": "C:\\x.exe", "Timestamp": "Mon"},
      {"Kind": "FirewallProduct", "Name": "Vendor FW", "State": 266256, "Path": "", "Timestamp": ""}]
DEF = {"AMProductVersion": "4.18.1", "AMEngineVersion": "1.1.2", "AntivirusSignatureVersion": "1.4",
       "AntivirusSignatureLastUpdated": "/Date(1758000000000)/", "RealTimeProtectionEnabled": True,
       "IsTamperProtected": True, "NISEnabled": True, "QuickScanEndTime": None, "FullScanEndTime": None,
       "QuickScanAge": 2, "FullScanAge": 4294967295}
FW = [{"Name": "Domain", "Enabled": 1, "DefaultInboundAction": 4, "DefaultOutboundAction": 2, "NotifyOnListen": 0,
       "LogFileName": "%systemroot%\\pfirewall.log", "LogMaxSizeKilobytes": 4096}]
DG = {"VirtualizationBasedSecurityStatus": 2, "SecurityServicesConfigured": [1, 2], "SecurityServicesRunning": [2],
      "AvailableSecurityProperties": [1, 2, 3, 5, 7], "RequiredSecurityProperties": [0],
      "CodeIntegrityPolicyEnforcementStatus": 2, "UsermodeCodeIntegrityPolicyEnforcementStatus": 0}
ADMINS = {"Members": [{"Name": "PC-NAME\\Administrator", "ObjectClass": "User", "PrincipalSource": "Local"}],
          "Source": "LocalAccounts", "Error": ""}
NET = "Force user logoff how long after time expires?:       Never\nMinimum password length:                              8\nLockout threshold:                                    Never\nThe command completed successfully.\n"


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(SC, DEF, FW, DG, {"TpmPresent": True, "TpmReady": True, "ManufacturerIdTxt": "IFX "},
                              [{"MountPoint": "C:", "ProtectionStatus": 1, "EncryptionMethod": 7, "EncryptionPercentage": 100,
                                "VolumeStatus": 1, "KeyProtector": "Tpm, RecoveryPassword"}], ADMINS, NET)

    def test_security_center_rows(self):
        av = self.data["security_center"][0]
        self.assertEqual(av["Kind"], "Antivirus")
        self.assertEqual(av["State"], "Enabled")
        self.assertEqual(av["Signatures"], "Up to date")

    def test_defender_and_firewall(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Real-time Protection"], "Yes")
        self.assertEqual(rows["Last Full Scan"], "Never")
        fw = self.data["firewall"][0]
        self.assertEqual(fw["Enabled"], "Yes")
        self.assertEqual(fw["Inbound"], "Block")
        self.assertEqual(fw["Outbound"], "Allow")

    def test_device_guard_decoded(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Virtualization-based Security"], "Running")
        self.assertEqual(rows["Security Services Running"], "Hypervisor Code Integrity (HVCI)")
        self.assertEqual(rows["Kernel-mode Code Integrity"], "Enforced")

    def test_tpm_bitlocker_and_accounts(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["TPM Present"], "Yes")
        self.assertEqual(rows["TPM Manufacturer"], "IFX")
        self.assertEqual(rows["Minimum password length"], "8")
        bl = self.data["bitlocker"][0]
        self.assertEqual(bl["Protection"], "On")
        self.assertEqual(bl["Method"], "XTS-AES 256")

    def test_requires_admin_placeholders(self):
        data = mod.build([], {}, [], {}, REQUIRES_ADMIN, REQUIRES_ADMIN,
                         {"Members": [], "Source": "LocalAccounts", "Error": ""}, "")
        self.assertEqual(mod.flatten(data)["TPM"], REQUIRES_ADMIN)
        self.assertEqual(data["bitlocker"], REQUIRES_ADMIN)
        html = mod.render(data, support.render_ctx())
        self.assertEqual(html.count("Requires administrator"), 2)

    def test_local_administrator_members_render(self):
        data = mod.build([], {}, [], {}, {}, [],
                         {"Members": [{"Name": "PC\\Administrator", "ObjectClass": "User",
                                      "PrincipalSource": "Local"}],
                          "Source": "LocalAccounts", "Error": ""}, "")
        html = mod.render(data, support.render_ctx())
        self.assertEqual(len(data["admins"]), 1)
        self.assertIn("Administrator", data["admins"][0]["Local Administrators"])
        self.assertIn("Administrator", html)

    def test_local_administrator_error_renders_unavailable(self):
        data = mod.build([], {}, [], {}, {}, [],
                         {"Members": [], "Source": "", "Error": "boom"}, "")
        html = mod.render(data, support.render_ctx())
        self.assertIn("Unavailable (see notes)", html)


class FixtureTests(unittest.TestCase):
    def test_collect_notes_local_administrator_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp) / "security"
            fixture_dir.mkdir()
            (fixture_dir / "local_admins.json").write_text(
                json.dumps({"Members": [], "Source": "", "Error": "boom"}),
                encoding="utf-8",
            )
            ctx = support.FixtureSectionContext(mod.SECTION, root=Path(tmp))
            mod.collect(ctx)
        self.assertIn("local administrators: boom", ctx.notes)

    def test_collect_and_render_from_fixtures(self):
        data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Antivirus", "Real-time Protection", "Inbound", "Virtualization-based Security",
                      "Local Administrators", "Requires administrator"):
            self.assertIn(label, html, label)
        admins_html = html.split("<h3>Local Administrators</h3>", 1)[1]
        expected = "<tbody><tr>" if data["admins"] else "Unavailable (see notes)"
        self.assertIn(expected, admins_html)
        username = os.environ.get("USERNAME")
        if username:
            self.assertNotIn(username.lower(), html.lower())

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
