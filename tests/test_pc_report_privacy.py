import json
import re
import unittest

from pc_report.privacy import redact_payload
from pc_report.render_json import render
from pc_report.render_html import render as render_html


class PcReportPrivacyTests(unittest.TestCase):
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

    def test_html_renderer_handles_nvc_report_section(self):
        html = render_html(
            {"generated_at": "now", "machine": "pc"},
            {
                "noldus_nvc_report": {
                    "noldus_software": [{"Name": "Noldus - LeadTools - X64 Package - 21", "Version": "21.0.16.0"}],
                    "noldus_drivers": [{"DeviceName": "Noldus Test Driver", "DriverVersion": "1.2.3"}],
                    "noldus_codecs": [{"Name": "NoldusSamplegrabberu", "File": r"C:\Program Files\Common Files\Noldus\Filter.ax"}],
                    "noldus_environment": [{"Name": "GENICAM_GENTL64_PATH", "Value": r"C:\Program Files\Basler\pylon 8"}],
                    "system_summary": {"OS": "Windows", "CPU": "Test CPU"},
                }
            },
            {"redact": True},
        )

        self.assertIn("NVC Report", html)
        self.assertIn("Noldus - LeadTools", html)
        self.assertIn("Noldus Driver Inventory", html)
        self.assertIn("Noldus Test Driver", html)
        self.assertIn("Noldus Codec / Filter / Dependency Inventory", html)
        self.assertIn("NoldusSamplegrabberu", html)
        self.assertIn("Noldus / Camera Environment", html)
        self.assertIn("GENICAM_GENTL64_PATH", html)

    def test_html_renderer_shows_report_health_nvc_counts_and_uptime(self):
        html = render_html(
            {"generated_at": "now", "machine": "pc"},
            {
                "noldus_nvc_report": {
                    "noldus_software": [{"Name": "Noldus App"}, {"Name": "Sentinel HASP Driver"}],
                    "noldus_drivers": [{"DeviceName": "Sentinel HASP License Manager"}],
                    "noldus_codecs": [{"Name": "NoldusFilter"}, {"Name": "BaslerFilter"}],
                    "noldus_environment": [{"Name": "PATH", "Value": r"C:\Program Files\Common Files\Noldus"}],
                    "system_summary": {"OS": "Windows", "Uptime": "2 days, 3 hours"},
                },
                "codecs": [],
            },
            {"redact": True},
        )

        self.assertIn("Report Health", html)
        self.assertIn("NVC Findings Summary", html)
        self.assertIn("Software / Packages", html)
        self.assertIn(">2<", html)
        self.assertIn("Computer Uptime", html)
        self.assertIn("2 days, 3 hours", html)

    def test_html_renderer_shows_environment_variables_and_parity_sections(self):
        html = render_html(
            {"generated_at": "now", "machine": "pc"},
            {
                "environment": {
                    "env": {"GENICAM_GENTL64_PATH": r"C:\Users\Pat\GenICam"},
                    "culture": {"Name": "en-US"},
                    "system_locale": {"Name": "en-US"},
                    "directories": {},
                    "files": [],
                },
                "codecs": [],
                "snapins": [],
                "sensors": [],
            },
            {"redact": True},
        )

        self.assertIn("Environment Variables", html)
        self.assertIn("GENICAM_GENTL64_PATH", html)
        self.assertIn(r"C:\Users\&lt;redacted&gt;\GenICam", html)
        self.assertIn("Audio and Video Codecs", html)
        self.assertIn("MMC Snap-Ins", html)
        self.assertIn("Sensors", html)

    def test_html_renderer_combines_tcp_and_udp_network_connections(self):
        html = render_html(
            {"generated_at": "now", "machine": "pc"},
            {
                "network_connections": {
                    "tcp": [{"LocalAddress": "127.0.0.1", "LocalPort": 80, "RemoteAddress": "127.0.0.1", "RemotePort": 50000, "State": "Listen"}],
                    "udp": [{"LocalAddress": "0.0.0.0", "LocalPort": 5353}],
                }
            },
            {"redact": True},
        )

        headings = re.findall(r"<h2 id=\"s\d+\">Network Connections", html)
        self.assertEqual(len(headings), 1)
        self.assertIn("TCP", html)
        self.assertIn("UDP", html)

    def test_html_renderer_adds_imaging_devices_section(self):
        html = render_html(
            {"generated_at": "now", "machine": "pc"},
            {
                "devices": [
                    {
                        "Name": "Basler Camera",
                        "Manufacturer": "Basler",
                        "PNPClass": "Image",
                        "ClassGuid": "guid",
                        "DeviceID": "USB\\VID_0000",
                    }
                ],
            },
            {"redact": True},
        )

        self.assertIn("Imaging and Camera Devices", html)
        self.assertIn("Basler Camera", html)


if __name__ == "__main__":
    unittest.main()
