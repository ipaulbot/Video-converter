import unittest

from pc_report.privacy import redact_payload
from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import shares as mod
from tests.pc_report import support

SH = [
    {
        "Name": "Data",
        "Path": r"D:\Data",
        "Description": "Lab data",
        "ShareType": 0,
        "ShareState": 1,
        "CurrentUsers": 2,
        "CachingMode": 0,
        "EncryptData": False,
        "FolderEnumerationMode": 0,
        "Special": False,
    },
    {
        "Name": "ADMIN$",
        "Path": r"C:\Windows",
        "Description": "Remote Admin",
        "ShareType": 0,
        "ShareState": 1,
        "CurrentUsers": 0,
        "CachingMode": 0,
        "EncryptData": False,
        "FolderEnumerationMode": 0,
        "Special": True,
    },
]
ACC = [
    {
        "Name": "Data",
        "AccountName": r"LAB\Researchers",
        "AccessControlType": 0,
        "AccessRight": 1,
    }
]
CLIENT = {
    "EnableInsecureGuestLogons": False,
    "RequireSecuritySignature": False,
    "EnableSecuritySignature": True,
    "EnableMultiChannel": True,
    "SMB1": None,
}
SERVER = {
    "EnableSMB1Protocol": False,
    "EnableSMB2Protocol": True,
    "RequireSecuritySignature": False,
    "EnableSecuritySignature": False,
    "AutoShareServer": True,
    "AutoShareWorkstation": True,
}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(SH, ACC, CLIENT, SERVER)
        d = data["rows"][0]
        self.assertEqual(d["Type"], "Disk")
        self.assertEqual(d["State"], "Online")
        self.assertEqual(d["Special"], "No")
        self.assertEqual(data["access"][0]["Right"], "Change")
        self.assertEqual(data["access"][0]["Control"], "Allow")
        rows = mod.flatten(data)
        self.assertEqual(rows["Insecure Guest Logons"], "No")
        self.assertEqual(rows["SMB1 Protocol (server)"], "No")
        self.assertEqual(dict(data["groups"][0]["rows"])["Shares"], 2)

    def test_server_requires_admin(self):
        data = mod.build(SH, ACC, CLIENT, REQUIRES_ADMIN)
        rows = mod.flatten(data)
        self.assertEqual(rows["Server Configuration"], REQUIRES_ADMIN)
        self.assertIn("Requires administrator", mod.render(data, support.render_ctx()))

    def test_hidden_administrative_shares_are_flagged(self):
        rows = mod.build(
            [
                {"Name": "C$", "Special": False},
                {"Name": "IPC$", "Special": False},
                {"Name": "print$", "Special": False},
            ],
            [],
            None,
            None,
        )["rows"]
        self.assertEqual([row["Special"] for row in rows], ["Yes", "Yes", "Yes"])

    def test_share_privacy_and_well_known_accounts(self):
        data = mod.build(
            [{"Name": "Data", "Path": r"C:\Users\Jane\Private"}],
            [
                {"Name": "Data", "AccountName": "Everyone"},
                {"Name": "Data", "AccountName": r"BUILTIN\Administrators"},
                {"Name": "Data", "AccountName": "Authenticated Users"},
                {"Name": "Data", "AccountName": r"LAB\Researchers"},
            ],
            None,
            None,
        )
        redacted = redact_payload(data, {"redact": True}, env={})
        self.assertEqual(redacted["rows"][0]["Path"], r"C:\Users\<redacted>\Private")
        accounts = {row["Account Name"] for row in redacted["access"]}
        self.assertTrue(
            {"Everyone", r"BUILTIN\Administrators", "Authenticated Users"} <= accounts
        )
        self.assertNotIn(r"LAB\Researchers", accounts)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION, is_admin=False)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Share permissions</h3>", html)
        self.assertIn("Requires administrator", html)
        self.assertIn("SMB Server", html)
        self.assertIn("Server Configuration", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
