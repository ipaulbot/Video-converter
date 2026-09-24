import json
import unittest

from pc_report.privacy import mask_string, redact_payload
from pc_report.render_json import render


class PcReportPrivacyTests(unittest.TestCase):
    def test_mask_string_fully_masks_short_sensitive_strings(self):
        self.assertEqual(mask_string("ABCDE"), "*****")
        self.assertEqual(mask_string("ABCDEF"), "******")
        self.assertEqual(mask_string("ABCDEFG"), "AB*DEFG")
        self.assertEqual(mask_string("WDGS-BH0020"), "WD*****0020")
        self.assertEqual(mask_string("ab"), "**")

    def test_registered_user_is_redacted(self):
        r = redact_payload({"RegisteredUser": "Jane Example"}, {"redact": True})
        self.assertNotIn("Example", r["RegisteredUser"])

    def test_registered_organization_is_redacted(self):
        r = redact_payload({"Registered Organization": "Acme Secret"}, {"redact": True})
        self.assertNotIn("Secret", r["Registered Organization"])

    def test_redact_payload_masks_sensitive_keys_and_user_paths(self):
        payload = {
            "licenses": {"ProductKey": "AAAAA-BBBBB-CCCCC-DDDDD"},
            "hardware": {"SerialNumber": "SERIAL123456"},
            "network": {"MACAddress": "AA:BB:CC:DD:EE:FF"},
            "environment": {"API_TOKEN": "super-secret-token"},
            "processes": [{"Path": r"C:\Users\Pat\Desktop\secret.exe"}],
        }

        redacted = redact_payload(payload, {"redact": True})

        self.assertNotEqual(redacted["licenses"]["ProductKey"], "AAAAA-BBBBB-CCCCC-DDDDD")
        self.assertNotEqual(redacted["hardware"]["SerialNumber"], "SERIAL123456")
        self.assertNotEqual(redacted["environment"]["API_TOKEN"], "super-secret-token")
        self.assertEqual(redacted["network"]["MACAddress"], "AA:BB:**:**:EE:FF")
        self.assertEqual(redacted["processes"][0]["Path"], r"C:\Users\<redacted>\Desktop\secret.exe")

    def test_new_identifying_fields_are_masked_by_human_label(self):
        payload = {"summary": {"UUID": "4C4C4544-0000-1234-8000-ABCDEF123456", "Asset Tag": "A123456",
                               "Computer Name": "WDGS-BH0020", "Registered Owner": "Pat Example",
                               "User Name": "pat", "Logon Server": r"\\DC01", "SSID": "LabWiFi",
                               "Volume Serial Number": "1A2B-3C4D", "Hardware ID": "ABCDEFGHIJ"}}
        r = redact_payload(payload, {"redact": True})["summary"]
        for key, original in payload["summary"].items():
            self.assertNotEqual(r[key], original, key)

    def test_decoded_text_fields_are_not_masked(self):
        payload = {"x": {"Domain Role": "Member Workstation", "License Status": "Licensed",
                         "Key Type": "Volume:GVLK", "Machine Type": "Desktop", "Owning Process": "svchost"}}
        self.assertEqual(redact_payload(payload, {"redact": True}), payload)

    def test_ip_addresses_keep_two_octets_and_loopback_is_untouched(self):
        payload = {"n": {"IPv4 Address": "192.168.10.55, 10.0.0.7", "IPv6 Address": "fe80::1c2d:3e4f:5a6b:7c8d",
                         "Default Gateway": "192.168.10.1", "Local Address": "0.0.0.0",
                         "Remote Address": "127.0.0.1", "DNS Servers": ["8.8.8.8", "1.1.1.1"]}}
        r = redact_payload(payload, {"redact": True})["n"]
        self.assertEqual(r["IPv4 Address"], "192.168.*.*, 10.0.*.*")
        self.assertEqual(r["IPv6 Address"], "fe80::*")
        self.assertEqual(r["Default Gateway"], "192.168.*.*")
        self.assertEqual(r["Local Address"], "0.0.0.0")
        self.assertEqual(r["Remote Address"], "127.0.0.1")
        self.assertEqual(r["DNS Servers"], ["8.8.*.*", "1.1.*.*"])

    def test_name_value_rows_mask_sensitive_names_only(self):
        rows = [{"Name": "USERNAME", "Value": "pat"}, {"Name": "Path", "Value": r"C:\Users\pat\bin"},
                {"Name": "LOGONSERVER", "Value": r"\\DC01"}]
        r = redact_payload(rows, {"redact": True})
        self.assertNotEqual(r[0]["Value"], "pat")
        self.assertEqual(r[1]["Value"], r"C:\Users\<redacted>\bin")
        self.assertNotEqual(r[2]["Value"], r"\\DC01")

    def test_requires_admin_sentinel_and_numbers_survive(self):
        from pc_report.section import REQUIRES_ADMIN
        payload = {"d": {"Serial Number": REQUIRES_ADMIN, "Size": 1024, "Serial Count": 3, "Ok": True}}
        r = redact_payload(payload, {"redact": True})["d"]
        self.assertEqual(r["Serial Number"], REQUIRES_ADMIN)
        self.assertEqual(r["Size"], 1024)
        self.assertEqual(r["Serial Count"], 3)
        self.assertIs(r["Ok"], True)

    def test_lists_under_sensitive_keys_are_masked_elementwise(self):
        r = redact_payload({"Members": ["DOMAIN\\alice", "DOMAIN\\bob"]}, {"redact": True})
        self.assertEqual(r, {"Members": ["DOMAIN\\alice", "DOMAIN\\bob"]})  # 'members' is not a token
        r = redact_payload({"Local Administrators": ["DOMAIN\\alice"]}, {"redact": True})
        self.assertNotEqual(r["Local Administrators"], ["DOMAIN\\alice"])

    def test_redact_off_returns_a_deep_copy(self):
        payload = {"a": {"Serial Number": "X1234567"}}
        r = redact_payload(payload, {"redact": False})
        self.assertEqual(r, payload)
        self.assertIsNot(r["a"], payload["a"])

    def test_json_renderer_uses_redacted_payload(self):
        data = {
            "licenses": {"ProductKey": "AAAAA-BBBBB-CCCCC-DDDDD"},
            "environment": {"directories": {"UserProfile": r"C:\Users\Pat"}},
        }

        rendered = json.loads(render({"generated_at": "now", "machine": "pc"}, data, {"redact": True}))

        self.assertNotEqual(rendered["sections"]["licenses"]["ProductKey"], "AAAAA-BBBBB-CCCCC-DDDDD")
        self.assertEqual(rendered["sections"]["environment"]["directories"]["UserProfile"], r"C:\Users\<redacted>")

if __name__ == "__main__":
    unittest.main()
