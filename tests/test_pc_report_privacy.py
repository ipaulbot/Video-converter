import json
import re
import unittest

from pc_report import privacy
from pc_report.privacy import mask_hosts, mask_string, redact_command_line, redact_payload, redact_user_paths
from pc_report.render_json import render


class PcReportPrivacyTests(unittest.TestCase):
    def test_redact_user_paths_handles_any_drive_and_slash_style(self):
        cases = {
            r"\Users\jane\x": r"\Users\<redacted>\x",
            "D:/Users/jane/x": "D:/Users/<redacted>/x",
            r"C:\Users\Public\x": r"C:\Users\<redacted>\x",
            "C:#Users#jane#AppData#Local#app.exe": "C:#Users#<redacted>#AppData#Local#app.exe",
            "C:#Users#Public#Documents": "C:#Users#<redacted>#Documents",
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

    def test_machine_id_is_masked_as_an_identifier(self):
        machine_id = "{01234567-89AB-CDEF-0123-456789ABCDEF}"

        redacted = redact_payload({"MachineId": machine_id}, {"redact": True}, env={})

        self.assertNotEqual(redacted["MachineId"], machine_id)

    def test_storage_unique_and_bitlocker_identifiers_are_masked(self):
        values = {
            "UniqueId": "eui.0123456789ABCDEF",
            "Guid": "{89ABCDEF-0123-4567-89AB-CDEF01234567}",
            "KeyProtectorId": "{01234567-89AB-CDEF-0123-456789ABCDEF}",
            "RecoveryPassword": "111111-222222-333333-444444-555555-666666-777777-888888",
        }

        redacted = redact_payload(values, {"redact": True}, env={})

        for key, value in values.items():
            with self.subTest(key=key):
                self.assertNotEqual(redacted[key], value)

    def test_smart_instance_name_masks_trailing_serial_segment(self):
        value = r"SCSI\Disk&Ven_NVMe&Prod_Samsung_SSD_980\PRIVATE-SERIAL"

        redacted = redact_payload({"InstanceName": value}, {"redact": True}, env={})

        self.assertEqual(redacted["InstanceName"].rsplit("\\", 1)[0], value.rsplit("\\", 1)[0])
        self.assertNotEqual(redacted["InstanceName"].rsplit("\\", 1)[1], value.rsplit("\\", 1)[1])

    def test_storage_network_paths_mask_remote_hosts(self):
        values = {
            "ProviderName": r"\\fileserver\share",
            "Network Path (host name)": r"\\192.168.31.12\temp",
        }

        redacted = redact_payload(values, {"redact": True}, env={})

        self.assertEqual(redacted["ProviderName"], r"\\<redacted>\share")
        self.assertEqual(redacted["Network Path (host name)"], r"\\192.168.*.*\temp")

    def test_printer_fields_mask_ip_addresses_and_unc_hosts(self):
        guid = "b8136383-1826-454b-810e-0c4a05d5a2e0"
        values = {
            "PortName": [
                "IP_192.168.1.20",
                "192.168.31.12",
                f"WSD-{guid}",
                "OneNote_S-1-5-21-2734529186-23328706-2630127308-5137",
                r"\\PRINTSRV\HP",
                "USB001",
                "nul:",
                "PORTPROMPT:",
            ],
            "ShareName": r"\\printserver\queue",
            "ServerName": r"\\10.20.30.40\queue",
            "Location": r"\\room-server\lab",
            "Comment": r"Available via \\comment-host\printer at 10.20.30.40",
        }

        redacted = redact_payload(values, {"redact": True}, env={})

        self.assertEqual(redacted["PortName"][0], "IP_192.168.*.*")
        self.assertEqual(redacted["PortName"][1], "192.168.*.*")
        self.assertNotIn(guid, redacted["PortName"][2])
        self.assertNotIn("2734529186", redacted["PortName"][3])
        self.assertNotIn("5137", redacted["PortName"][3])
        self.assertEqual(redacted["PortName"][4], r"\\<redacted>\HP")
        self.assertEqual(redacted["PortName"][5:], ["USB001", "nul:", "PORTPROMPT:"])
        self.assertEqual(redacted["ShareName"], r"\\<redacted>\queue")
        self.assertEqual(redacted["ServerName"], r"\\10.20.*.*\queue")
        self.assertEqual(redacted["Location"], r"\\<redacted>\lab")
        self.assertNotIn("comment-host", redacted["Comment"])
        self.assertNotIn("10.20.30.40", redacted["Comment"])

    def test_version_like_ipv4_is_untouched_outside_ip_scoped_keys(self):
        payload = {"Version": "12.19.2.66"}

        self.assertEqual(redact_payload(payload, {"redact": True}, env={}), payload)

    def test_device_instance_ids_mask_trailing_serial_segments(self):
        ids = [
            r"USB\VID_1234&PID_5678\PHONE-SERIAL",
            r"USBSTOR\DISK&VEN_TEST&PROD_DRIVE\DISK-SERIAL",
            r"SCSI\DISK&VEN_TEST&PROD_DRIVE\4&PRIVATE&0&000000",
            r"SWD\WPDBUSENUM\{PRIVATE-PHONE-ID}",
            r"DISPLAY\DEL1234\MONITOR-SERIAL",
        ]
        for key in ("InstanceId", "DeviceID", "PNPDeviceID"):
            for value in ids:
                with self.subTest(key=key, value=value):
                    redacted = redact_payload({key: value}, {"redact": True}, env={})[key]
                    self.assertEqual(redacted.rsplit("\\", 1)[0], value.rsplit("\\", 1)[0])
                    self.assertNotEqual(redacted.rsplit("\\", 1)[1], value.rsplit("\\", 1)[1])

    def test_usb_parent_instance_ids_mask_trailing_serial_segments(self):
        value = r"USB\VID_1234&PID_5678\PRIVATE-PARENT-SERIAL"

        redacted = redact_payload({"ParentInstanceId": value}, {"redact": True}, env={})

        self.assertEqual(redacted["ParentInstanceId"].rsplit("\\", 1)[0], value.rsplit("\\", 1)[0])
        self.assertNotEqual(redacted["ParentInstanceId"].rsplit("\\", 1)[1], value.rsplit("\\", 1)[1])

    def test_bluetooth_instance_ids_mask_mac_tokens_outside_guids(self):
        ids = [
            r"BTHENUM\DEV_183F708F38FB\7&22FD4E5&0&BLUETOOTHDEVICE_183F708F38FB",
            r"BTHENUM\{0000110C-0000-1000-8000-00805F9B34FB}_VID&0001004C_PID&200F\7&22FD4E5&0&183F708F38FB_C00000000",
            r"BTHLE\DEV_4A9EBDC39A33\7&9377338&0&4A9EBDC39A33",
            r"BTHLEDEVICE\{0000FE78-0000-1000-8000-00805F9B34FB}_4A9EBDC39A33\8&1DFE3610&0&0012",
        ]
        expected_mac = [
            "183F70******",
            "183F70******",
            "4A9EBD******",
            "4A9EBD******",
        ]
        token = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{12}(?![0-9A-Fa-f])")
        braces = re.compile(r"\{[^{}]*\}")

        for key in ("InstanceId", "DeviceID", "PNPDeviceID"):
            for value, masked_mac in zip(ids, expected_mac, strict=True):
                with self.subTest(key=key, value=value):
                    redacted = redact_payload({key: value}, {"redact": True}, env={})[key]
                    self.assertIsNone(token.search(braces.sub("", redacted)))
                    self.assertIn(masked_mac, redacted)
                    if "{" in value:
                        self.assertIn("00805F9B34FB", redacted)

    def test_bluetooth_instance_id_masking_does_not_change_other_id_rules(self):
        pci = r"PCI\VEN_8086&DEV_51EF&SUBSYS_0B4A1028&REV_01\3&11583659&0&A0"
        usb = r"USB\VID_290B&PID_0900\J9AB12CD266W"

        self.assertEqual(redact_payload({"DeviceID": pci}, {"redact": True}, env={})["DeviceID"], pci)
        self.assertNotEqual(
            redact_payload({"DeviceID": usb}, {"redact": True}, env={})["DeviceID"],
            usb,
        )

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

    def test_possessive_owner_is_masked_in_device_description(self):
        payload = {"Description": "Clark Kent\u2019s Beats Studio P"}

        redacted = redact_payload(payload, {"redact": True}, env={})

        self.assertEqual(redacted["Description"], "***\u2019s Beats Studio P")

    def test_possessive_owner_is_masked_in_wrapped_device_description(self):
        payload = {"Description": "Speakers (USB - Clark Kent\u2019s Beats Studio P)"}

        redacted = redact_payload(payload, {"redact": True}, env={})

        self.assertEqual(redacted["Description"], "Speakers (USB - ***\u2019s Beats Studio P)")

    def test_owner_prefix_is_masked_for_personal_device_family(self):
        payload = {"FriendlyName": "Pat Galaxy S24"}

        redacted = redact_payload(payload, {"redact": True}, env={})

        self.assertEqual(redacted["FriendlyName"], "*** Galaxy S24")

    def test_nonpersonal_device_description_is_unchanged(self):
        payload = {"Description": "Speakers (Realtek(R) Audio)"}

        self.assertEqual(redact_payload(payload, {"redact": True}, env={}), payload)

    def test_possessive_text_outside_device_name_keys_is_unchanged(self):
        payload = {"Path": "Bob's folder"}

        self.assertEqual(redact_payload(payload, {"redact": True}, env={}), payload)

    def test_bluetooth_names_matching_descriptions_are_kept(self):
        row = {
            "Name": "  Bluetooth   Peripheral Device ",
            "FriendlyName": "BLUETOOTH PERIPHERAL DEVICE",
            "Description": "Bluetooth Peripheral Device",
            "DeviceID": r"BTHENUM\{0000110C-0000-1000-8000-00805F9B34FB}",
        }

        redacted = redact_payload(row, {"redact": True}, env={})

        self.assertEqual(redacted["Name"], row["Name"])
        self.assertEqual(redacted["FriendlyName"], row["FriendlyName"])

    def test_bluetooth_names_differing_from_descriptions_are_masked(self):
        rows = [
            {
                "Name": "Clint's AirPods Pro",
                "Description": "Bluetooth Device",
                "DeviceID": r"BTHENUM\DEV_183F708F38FB\7&22FD4E5&0&183F708F38FB",
            },
            {
                "Name": "AirPods Pro Avrcp Transport",
                "Description": "Microsoft Bluetooth Avrcp Transport Driver",
                "PNPDeviceID": r"BTHENUM\DEV_183F708F38FB\7&22FD4E5&0&183F708F38FB",
            },
        ]

        redacted = redact_payload(rows, {"redact": True}, env={})

        self.assertNotEqual(redacted[0]["Name"], rows[0]["Name"])
        self.assertNotEqual(redacted[1]["Name"], rows[1]["Name"])

    def test_canonical_bluetooth_network_names_are_not_masked(self):
        rows = [
            {
                "Name": "Bluetooth Network Connection",
                "Description": "Bluetooth Device (Personal Area Network)",
                "DeviceID": r"BTHENUM\DEV_183F708F38FB\7&22FD4E5&0&183F708F38FB",
            },
            {
                "Name": "bluetooth network connection 2",
                "Description": "Bluetooth Device (Personal Area Network)",
                "DeviceID": r"BTHENUM\DEV_183F708F38FB\7&22FD4E5&0&183F708F38FB",
            },
            {
                "Name": "Pat's Bluetooth Connection",
                "Description": "Bluetooth Device (Personal Area Network)",
                "DeviceID": r"BTHENUM\DEV_183F708F38FB\7&22FD4E5&0&183F708F38FB",
            },
        ]

        redacted = redact_payload(rows, {"redact": True}, env={})

        self.assertEqual(redacted[0]["Name"], rows[0]["Name"])
        self.assertEqual(redacted[1]["Name"], rows[1]["Name"])
        self.assertNotEqual(redacted[2]["Name"], rows[2]["Name"])

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
        self.assertEqual(redacted["network"]["MACAddress"], "AA:BB:CC:**:**:**")
        self.assertEqual(redacted["processes"][0]["Path"], r"C:\Users\<redacted>\Desktop\secret.exe")

    def test_network_adapter_identifiers_are_masked(self):
        guid = "{01234567-89AB-CDEF-0123-456789ABCDEF}"
        payload = {
            "MacAddress": "AA-BB-CC-DD-EE-FF",
            "PermanentAddress": "11-22-33-44-55-66",
            "PhysicalAddress": "77:88:99:AA:BB:CC",
            "InterfaceGuid": guid,
            "DeviceID": guid,
            "PnPDeviceID": rf"{guid}\VWIFIMP_WFD\4&PRIVATE&0&17",
        }

        redacted = redact_payload(payload, {"redact": True}, env={})

        self.assertEqual(redacted["MacAddress"], "AA:BB:CC:**:**:**")
        self.assertEqual(redacted["PermanentAddress"], "11:22:33:**:**:**")
        self.assertEqual(redacted["PhysicalAddress"], "77:88:99:**:**:**")
        self.assertNotEqual(redacted["InterfaceGuid"], guid)
        self.assertNotEqual(redacted["DeviceID"], guid)
        self.assertNotIn(guid, redacted["PnPDeviceID"])

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

    def test_dns_suffix_and_network_profile_are_masked(self):
        out = redact_payload(
            {
                "DNS Suffix": "lab.example.org",
                "Network Profile": "lab.example.org (Domain)",
                "DNSDomain": "private.lan",
                "DNSDomainSuffixSearchOrder": ["private.lan"],
                "NetProfileName": "Private Wi-Fi",
            },
            {"redact": True},
        )
        self.assertNotIn("example", out["DNS Suffix"])
        self.assertNotIn("example", out["Network Profile"])
        self.assertNotIn("private", out["DNSDomain"])
        self.assertNotIn("private", out["DNSDomainSuffixSearchOrder"][0])
        self.assertNotIn("Private", out["NetProfileName"])

    def test_well_known_network_profile_names_remain_readable(self):
        payload = {
            "Network Profile": "  Unidentified   network  ",
            "NetProfileName": "HomeWiFi-5G",
        }

        out = redact_payload(payload, {"redact": True}, env={})

        self.assertEqual(out["Network Profile"], payload["Network Profile"])
        self.assertNotEqual(out["NetProfileName"], payload["NetProfileName"])

    def test_network_raw_text_masks_addresses_mac_and_wireless_names(self):
        text = (
            "Name : Wi-Fi\n"
            "SSID : PrivateNetwork\n"
            "BSSID : AA-BB-CC-DD-EE-FF\n"
            "Physical address : AA:BB:CC:DD:EE:FF\n"
            "IPv4 Address : 192.168.10.55\n"
            "IPv6 Address : fe80::1c2d:3e4f:5a6b:7c8d\n"
            "GUID : 01234567-89AB-CDEF-0123-456789ABCDEF\n"
            "Profile : PrivateProfile\n"
        )

        out = privacy.redact_text(text)

        self.assertNotIn("PrivateNetwork", out)
        self.assertNotIn("DD-EE-FF", out)
        self.assertIn("AA:BB:CC:**:**:**", out)
        self.assertNotIn("192.168.10.55", out)
        self.assertNotIn("1c2d:3e4f", out)
        self.assertNotIn("01234567", out)
        self.assertNotIn("PrivateProfile", out)

    def test_proxy_server_hosts_are_masked(self):
        payload = {
            "ProxyServer": "http=proxy.private.example:8080;https=secure.private.example:8443",
            "AutoConfigURL": "https://pac.private.example/config.pac",
            "WinHTTP Proxy": "winhttp.private.example:3128 (bypass: local)",
        }

        out = redact_payload(payload, {"redact": True}, env={})

        self.assertNotIn("private.example", out["ProxyServer"])
        self.assertIn(":8080", out["ProxyServer"])
        self.assertNotIn("pac.private.example", out["AutoConfigURL"])
        self.assertIn("/config.pac", out["AutoConfigURL"])
        self.assertNotIn("winhttp.private.example", out["WinHTTP Proxy"])
        self.assertIn(":3128", out["WinHTTP Proxy"])

    def test_mask_hosts_preserves_proxy_syntax_and_masks_hostnames(self):
        cases = {
            "proxy.corp.example:8080": "***.example:8080",
            "*.corp.example;<local>": "*.***.example;<local>",
            "http=proxy.corp.example:8080": "http=***.example:8080",
            "http://pac.corp.example/proxy.pac": "http://***.example/proxy.pac",
            "10.20.30.40:3128": "10.20.*.*:3128",
            "<local>;direct;*;localhost;127.0.0.1": "<local>;direct;*;localhost;127.0.0.1",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(mask_hosts(value), expected)

    def test_proxy_host_tokens_cover_raw_and_rendered_labels(self):
        payload = {
            "ProxyServer": "proxy.corp.example:8080",
            "ProxyOverride": "*.corp.example;<local>",
            "Proxy Bypass": "*.corp.example;<local>",
            "AutoConfigURL": "http://pac.corp.example/proxy.pac",
            "User Proxy": "Enabled: proxy.corp.example:8080",
            "WinHTTP Proxy": "proxy.corp.example:8080 (bypass: *.corp.example;<local>)",
            "Bypass List": "*.corp.example;<local>",
        }

        out = redact_payload(payload, {"redact": True}, env={})

        self.assertNotIn("corp.example", repr(out))
        self.assertEqual(out["ProxyServer"], "***.example:8080")
        self.assertEqual(out["ProxyOverride"], "*.***.example;<local>")
        self.assertIn("Enabled:", out["User Proxy"])
        self.assertIn(":8080", out["WinHTTP Proxy"])
        self.assertIn("<local>", out["Proxy Bypass"])

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
