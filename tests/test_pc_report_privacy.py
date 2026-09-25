import json
import unittest

from pc_report import privacy
from pc_report.privacy import mask_string, redact_command_line, redact_payload, redact_user_paths
from pc_report.render_json import render


class PcReportPrivacyTests(unittest.TestCase):
    def test_redact_user_paths_handles_any_drive_and_slash_style(self):
        cases = {
            r"\Users\jane\x": r"\Users\<redacted>\x",
            "D:/Users/jane/x": "D:/Users/<redacted>/x",
            r"C:\Users\Public\x": r"C:\Users\<redacted>\x",
            r"C:\Windows\Users2\x": r"C:\Windows\Users2\x",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(redact_user_paths(value), expected)

    def test_identity_tokens_use_explicit_environment(self):
        env = {
            "COMPUTERNAME": "LAB-PC7",
            "USERNAME": "jane",
            "USERDNSDOMAIN": "corp.example.org",
            "USERDOMAIN": "CORP",
        }
        self.assertEqual(
            privacy.identity_tokens(env),
            [
                ("LAB-PC7", "PC-NAME"),
                ("jane", "user"),
                ("corp.example.org", "example.local"),
                ("CORP", "WORKGROUP"),
            ],
        )

    def test_redact_payload_scrubs_identities_before_sensitive_label_masking(self):
        env = {
            "COMPUTERNAME": "LAB-PC7",
            "USERNAME": "jane",
            "USERDNSDOMAIN": "corp.example.org",
            "USERDOMAIN": "CORP",
        }
        computer = redact_payload({"ComputerName": "LAB-PC7"}, {"redact": True}, env=env)["ComputerName"]
        self.assertNotIn("LAB", computer)
        self.assertNotIn("PC7", computer)

        rows = redact_payload(
            [
                {"Name": "LOGONSERVER", "Value": r"\\LAB-PC7"},
                {"Name": "USERDNSDOMAIN", "Value": "corp.example.org"},
            ],
            {"redact": True},
            env=env,
        )
        logon_value = rows[0]["Value"]
        self.assertNotIn("LAB", logon_value)
        self.assertNotIn("PC7", logon_value)
        dns_value = rows[1]["Value"]
        self.assertNotIn("corp", dns_value)
        self.assertNotIn("example.org", dns_value)

    def test_redact_payload_scrubs_logon_server_host_before_masking(self):
        env = {
            "COMPUTERNAME": "LAB-PC7",
            "LOGONSERVER": r"\\DC01",
            "USERNAME": "jane",
        }
        value = redact_payload(
            [{"Name": "LOGONSERVER", "Value": r"\\DC01"}],
            {"redact": True},
            env=env,
        )[0]["Value"]
        self.assertNotIn("DC01", value)

    def test_redact_payload_scrubs_identity_tokens_in_string_values(self):
        env = {
            "COMPUTERNAME": "LAB-PC7",
            "USERNAME": "jane",
            "USERDNSDOMAIN": "corp.example.org",
            "USERDOMAIN": "CORP",
        }
        payload = {
            "share": r"\\LAB-PC7\share",
            "people": ["jane", "janet"],
            "jane": "harmless",
        }

        redacted = redact_payload(payload, {"redact": True}, env=env)

        self.assertEqual(redacted["share"], r"\\PC-NAME\share")
        self.assertEqual(redacted["people"], ["user", "janet"])
        self.assertIn("jane", redacted)

    def test_redact_payload_identity_scrub_respects_redact_off_and_empty_env(self):
        payload = {"value": r"\\LAB-PC7\share", "people": ["jane"]}
        env = {"COMPUTERNAME": "LAB-PC7", "USERNAME": "jane"}
        self.assertEqual(redact_payload(payload, {"redact": False}, env=env), payload)
        self.assertEqual(redact_payload(payload, {"redact": True}, env={}), payload)

    def test_redact_payload_scrubs_account_sids_in_string_values(self):
        sid = "S-1-5-21-2734529186-23328706-2630127308-5137"
        payload = {"Name": f"OneDrive Startup Task-{sid}"}

        redacted = redact_payload(payload, {"redact": True}, env={})

        value = redacted["Name"].removeprefix("OneDrive Startup Task-")
        self.assertTrue(value.startswith("S-1-5-21-"))
        for private_part in ("2734529186", "23328706", "2630127308", "5137"):
            self.assertNotIn(private_part, value)

    def test_redact_payload_leaves_well_known_sids_readable(self):
        payload = {"system": "S-1-5-18", "administrators": "S-1-5-32-544"}

        self.assertEqual(redact_payload(payload, {"redact": True}, env={}), payload)

    def test_mask_string_fully_masks_short_sensitive_strings(self):
        self.assertEqual(mask_string("ABCDE"), "*****")
        self.assertEqual(mask_string("ABCDEF"), "******")
        self.assertEqual(mask_string("ABCDEFG"), "*******")
        self.assertEqual(mask_string("WDGS-BH0020"), "***********")
        self.assertEqual(mask_string("ABCDEFGHIJKL"), "AB******IJKL")
        self.assertEqual(mask_string("ABCDEFGHIJKLMNOP"), "AB**********MNOP")
        self.assertEqual(mask_string("ab"), "**")

    def test_processor_id_is_masked_as_a_hardware_identifier(self):
        redacted = redact_payload(
            {"ProcessorId": "BFEBFBFF000906A2"},
            {"redact": True},
            env={},
        )

        self.assertNotEqual(redacted["ProcessorId"], "BFEBFBFF000906A2")

    def test_device_instance_ids_mask_trailing_serial_segments(self):
        ids = [
            r"USB\VID_1234&PID_5678\PHONE-SERIAL",
            r"USBSTOR\DISK&VEN_TEST&PROD_DRIVE\DISK-SERIAL",
            r"SCSI\DISK&VEN_TEST&PROD_DRIVE\4&PRIVATE&0&000000",
            r"SWD\WPDBUSENUM\{PRIVATE-PHONE-ID}",
            r"BTHENUM\DEV_001122334455\7&PRIVATE&0&BLUETOOTHDEVICE_001122334455",
            r"BTHLE\DEV_001122334455\8&PRIVATE&0&001122334455",
            r"DISPLAY\DEL1234\MONITOR-SERIAL",
        ]
        for key in ("InstanceId", "DeviceID", "PNPDeviceID"):
            for value in ids:
                with self.subTest(key=key, value=value):
                    redacted = redact_payload({key: value}, {"redact": True}, env={})[key]
                    self.assertEqual(redacted.rsplit("\\", 1)[0], value.rsplit("\\", 1)[0])
                    self.assertNotEqual(redacted.rsplit("\\", 1)[1], value.rsplit("\\", 1)[1])

    def test_device_instance_ids_preserve_generic_and_nonportable_paths(self):
        ids = [
            r"USB\VID_1234&PID_5678\7&1A2B3C4D&0&2",
            r"PCI\VEN_8086&DEV_15BB\3&11583659&0&FE",
            r"ACPI\PNP0A0A\0",
            r"ROOT\SYSTEM\0000",
            r"HID\VID_1234&PID_5678\7&1A2B3C4D&0&0000",
        ]
        for value in ids:
            with self.subTest(value=value):
                self.assertEqual(
                    redact_payload({"InstanceId": value}, {"redact": True}, env={})["InstanceId"],
                    value,
                )

    def test_bluetooth_personal_friendly_names_are_masked(self):
        rows = [
            {"InstanceId": r"BTHENUM\DEV_001122334455\7&PRIVATE&0&001122334455", "FriendlyName": "Jane's iPhone", "Name": "Jane's iPhone"},
            {"DeviceID": r"BTHLE\DEV_001122334455\8&PRIVATE&0&001122334455", "FriendlyName": "Pat Galaxy S24", "Name": "Pat Galaxy S24"},
            {"DeviceID": r"USB\VID_1234&PID_5678\7&1A2B3C4D&0&2", "Name": "USB - Clark Kent\u2019s Headphones"},
            {"DeviceID": r"SWD\MMDEVAPI\{endpoint}", "FriendlyName": "Jane's iPhone Microphone"},
            {"InstanceId": r"PCI\VEN_8086&DEV_15BB\3&11583659&0&FE", "Name": "Intel Ethernet"},
        ]

        redacted = redact_payload(rows, {"redact": True}, env={})

        self.assertNotEqual(redacted[0]["FriendlyName"], rows[0]["FriendlyName"])
        self.assertNotEqual(redacted[0]["Name"], rows[0]["Name"])
        self.assertNotEqual(redacted[1]["FriendlyName"], rows[1]["FriendlyName"])
        self.assertNotEqual(redacted[1]["Name"], rows[1]["Name"])
        self.assertNotEqual(redacted[2]["Name"], rows[2]["Name"])
        self.assertNotEqual(redacted[3]["FriendlyName"], rows[3]["FriendlyName"])
        self.assertEqual(redacted[4]["Name"], rows[4]["Name"])

    def test_start_name_leaves_well_known_accounts_readable(self):
        payload = [
            {"StartName": "LocalSystem"},
            {"StartName": r"NT AUTHORITY\SYSTEM"},
            {"StartName": r"NT SERVICE\TrustedInstaller"},
            {"StartName": r"CORP\svc_backup"},
        ]

        redacted = redact_payload(payload, {"redact": True}, env={})

        self.assertEqual(redacted[:3], payload[:3])
        self.assertNotEqual(redacted[3]["StartName"], payload[3]["StartName"])

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
                {"Name": "LOGONSERVER", "Value": r"\\DC01"},
                {"Name": "IGCCSVC_DB", "Value": "AQAAANCM..."}]
        r = redact_payload(rows, {"redact": True})
        self.assertNotEqual(r[0]["Value"], "pat")
        self.assertEqual(r[1]["Value"], r"C:\Users\<redacted>\bin")
        self.assertNotEqual(r[2]["Value"], r"\\DC01")
        self.assertNotEqual(r[3]["Value"], "AQAAANCM...")

    def test_name_value_rows_mask_editor_session_and_pipe_identifiers(self):
        rows = [
            {"Name": "__CURSOR_SANDBOX_ENV_RESTORE", "Value": "export CURSOR_CONVERSATION_ID='uuid'"},
            {"Name": "CURSOR_CONVERSATION_ID", "Value": "0cb8551d-be1d-4a9a-9d72-8acc203a8625"},
            {"Name": "CHROME_CRASHPAD_PIPE_NAME", "Value": r"\\.\pipe\crashpad_65712_unique"},
            {"Name": "VSCODE_IPC_HOOK", "Value": r"\\.\pipe\unique-main-sock"},
        ]

        redacted = redact_payload(rows, {"redact": True}, env={})

        for original, row in zip(rows, redacted, strict=True):
            self.assertNotEqual(row["Value"], original["Value"], original["Name"])

    def test_command_line_masks_credential_option_separators(self):
        cases = [
            ("tool.exe -token abc123", "tool.exe -token ***"),
            ("tool.exe --pwd=hunter2", "tool.exe --pwd=***"),
            ('tool.exe --api-key="AKIA XYZ"', "tool.exe --api-key=***"),
            ("tool.exe /password:secret1", "tool.exe /password:***"),
            ("tool.exe --Auth-Token: xyz", "tool.exe --Auth-Token: ***"),
            ("tool.exe --pwdfile=creds.txt", "tool.exe --pwdfile=***"),
            ("tool.exe --license-key=ABC-123", "tool.exe --license-key=***"),
            ("tool.exe --basic-auth user:pass", "tool.exe --basic-auth ***"),
            ('tool.exe --auth-header "Bearer x"', 'tool.exe --auth-header ***'),
            ("tool.exe --hotkey=F5", "tool.exe --hotkey=***"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(redact_command_line(raw), expected)

        unchanged = [
            r"C:\Program Files\Keyboard\app.exe --mode=key-remap",
            r"notepad.exe C:\keys\readme.txt",
            r"C:\data\token\file.txt --verbose",
            "tool.exe --author=jane",
            "tool.exe --keyboard=us",
        ]
        for raw in unchanged:
            with self.subTest(raw=raw):
                self.assertEqual(redact_command_line(raw), raw)

    def test_command_line_masks_sensitive_arguments_and_pipe_names(self):
        command = (
            r'worker.exe --session-id=run-123 --api-token="secret-value" '
            r'--trace-process-track-uuid=3190708988185955192 '
            r'--native_msg_channel=private-channel --mojo-named-platform-channel-pipe=private-pipe '
            r'--vscode-window-config=vscode:private-window < \\.\pipe\chrome.nativeMessaging.in.unique'
        )

        redacted = redact_payload({"CommandLine": command}, {"redact": True}, env={})["CommandLine"]

        self.assertIn("worker.exe", redacted)
        for sensitive in (
            "run-123", "secret-value", "3190708988185955192", "private-channel", "private-pipe",
            "private-window", "nativeMessaging.in.unique",
        ):
            self.assertNotIn(sensitive, redacted)

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
