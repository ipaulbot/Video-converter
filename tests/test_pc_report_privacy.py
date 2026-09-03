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
