import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import network_information as mod
from tests.pc_report import support

CS = {"Name": "PC-NAME", "Domain": "lab.example.org", "PartOfDomain": True, "DomainRole": 1, "Workgroup": None, "DNSHostName": "pc-name", "Description": ""}
IPC = [{"InterfaceAlias": "Ethernet", "InterfaceIndex": 12, "InterfaceDescription": "Intel I219", "Status": "Up", "MacAddress": "AA-BB-CC-DD-EE-FF",
        "LinkSpeed": "1 Gbps", "IPv4Address": ["192.168.10.55/24"], "IPv6Address": ["fe80::1c2d:3e4f:5a6b:7c8d/64"], "IPv4DefaultGateway": ["192.168.10.1"],
        "IPv6DefaultGateway": [], "DNSServer": ["192.168.10.2", "8.8.8.8"], "NetProfileName": "lab.example.org", "NetProfileCategory": "DomainAuthenticated",
        "IPv4Connectivity": "Internet", "IPv6Connectivity": "NoTraffic"}]
WMI = [{"InterfaceIndex": 12, "Description": "Intel I219", "DHCPEnabled": True, "DHCPServer": "192.168.10.2", "DHCPLeaseObtained": "/Date(1758000000000)/",
        "DHCPLeaseExpires": "/Date(1758086400000)/", "DNSDomain": "lab.example.org", "DNSDomainSuffixSearchOrder": ["lab.example.org"],
        "WINSPrimaryServer": None, "WINSSecondaryServer": None, "TcpipNetbiosOptions": 0, "IPConnectionMetric": 25, "MTU": None, "IPEnabled": True}]
ROUTES = [{"InterfaceAlias": "Ethernet", "DestinationPrefix": "0.0.0.0/0", "NextHop": "192.168.10.1", "RouteMetric": 0, "InterfaceMetric": 25, "AddressFamily": 2}]
PROXY = {"ProxyEnable": 0, "ProxyServer": None, "ProxyOverride": None, "AutoConfigURL": None}
WINHTTP = "\nCurrent WinHTTP proxy settings:\n\n    Direct access (no proxy server).\n\n"
WLAN = "\nThere is 1 interface on the system:\n\n    Name                   : Wi-Fi\n    Description            : Intel(R) Wi-Fi 6\n    State                  : connected\n    SSID                   : LabNet\n    Radio type             : 802.11ax\n    Channel                : 44\n    Receive rate (Mbps)    : 1200\n    Transmit rate (Mbps)   : 1200\n    Signal                 : 91%\n"


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(CS, IPC, WMI, ROUTES, PROXY, WINHTTP, WLAN)

    def test_identity(self):
        rows = dict(self.data["groups"][0]["rows"])
        self.assertEqual(rows["Computer Name"], "PC-NAME")
        self.assertEqual(rows["Domain Name"], "lab.example.org")
        self.assertEqual(rows["Role"], "Member Workstation")

    def test_interface(self):
        iface = self.data["interfaces"][0]
        rows = {}
        for g in iface["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["IPv4 Address"], ["192.168.10.55/24"])
        self.assertEqual(rows["Default Gateway"], ["192.168.10.1"])
        self.assertEqual(rows["DHCP Enabled"], "Yes")
        self.assertEqual(rows["DHCP Server"], "192.168.10.2")
        self.assertEqual(rows["NetBIOS over TCP/IP"], "Default (from DHCP)")
        self.assertEqual(rows["Network Profile"], "lab.example.org (DomainAuthenticated)")

    def test_proxy_routes_wifi(self):
        rows = dict(self.data["groups"][1]["rows"])
        self.assertEqual(rows["User Proxy"], "Disabled")
        self.assertEqual(rows["WinHTTP Proxy"], "Direct access (no proxy server)")
        self.assertEqual(self.data["routes"][0]["Next Hop"], "192.168.10.1")
        wifi = dict(self.data["groups"][2]["rows"])
        self.assertEqual(wifi["SSID"], "LabNet")
        self.assertEqual(wifi["Signal"], "91%")
        self.assertEqual(wifi["Radio Type"], "802.11ax")

    def test_redaction_masks_addresses(self):
        red = redact_payload(self.data, {"redact": True})
        rows = {}
        for g in red["interfaces"][0]["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["IPv4 Address"], ["192.168.*.*/24"])
        self.assertEqual(rows["DHCP Server"], "192.168.*.*")
        self.assertEqual(rows["Default Gateway"], ["192.168.*.*"])
        self.assertNotEqual(dict(red["groups"][0]["rows"])["Computer Name"], "PC-NAME")
        self.assertNotEqual(dict(red["groups"][2]["rows"])["SSID"], "LabNet")

    def test_flattens_nested_ip_configuration_from_single_dict(self):
        ipc = {
            **IPC[0],
            "IPv4Address": [{"IPAddress": "10.20.30.40", "PrefixLength": 24}],
            "IPv6Address": {"IPAddress": "fe80::1234", "PrefixLength": 64},
            "IPv4DefaultGateway": [{"NextHop": "10.20.30.1"}],
            "DNSServer": [{"ServerAddresses": ["10.20.30.2", "1.1.1.1"]}],
        }

        data = mod.build(CS, ipc, WMI, ROUTES, PROXY, WINHTTP, WLAN)
        rows = {}
        for group in data["interfaces"][0]["groups"]:
            rows.update(group["rows"])

        self.assertEqual(rows["IPv4 Address"], ["10.20.30.40/24"])
        self.assertEqual(rows["IPv6 Address"], ["fe80::1234/64"])
        self.assertEqual(rows["Default Gateway"], ["10.20.30.1"])
        self.assertEqual(rows["DNS Servers"], ["10.20.30.2", "1.1.1.1"])

    def test_sorts_connected_interfaces_first_then_alias(self):
        interfaces = [
            {**IPC[0], "InterfaceAlias": "Zulu", "InterfaceIndex": "not-a-number", "Status": "Down"},
            {**IPC[0], "InterfaceAlias": "Beta", "InterfaceIndex": None, "Status": "Up"},
            {**IPC[0], "InterfaceAlias": "Alpha", "InterfaceIndex": 12, "Status": "Up"},
        ]

        data = mod.build(CS, interfaces, WMI, ROUTES, PROXY, WINHTTP, WLAN)

        self.assertEqual([item["name"] for item in data["interfaces"]], ["Alpha", "Beta", "Zulu"])

    def test_unparsed_command_text_degrades_to_not_available(self):
        data = mod.build(CS, IPC, WMI, ROUTES, PROXY, "Paramètres proxy inconnus", "Sans interface")

        self.assertEqual(dict(data["groups"][1]["rows"])["WinHTTP Proxy"], "Not available")
        self.assertEqual(dict(data["groups"][2]["rows"])["Wi-Fi"], "Not available")

    def test_wlan_parser_is_case_and_spacing_tolerant(self):
        text = " ssid: LabNet\n RADIO TYPE : 802.11ax\n signal: 91%\n"

        wifi = dict(mod.build(CS, IPC, WMI, ROUTES, PROXY, WINHTTP, text)["groups"][2]["rows"])

        self.assertEqual(wifi["SSID"], "LabNet")
        self.assertEqual(wifi["Signal"], "91%")
        self.assertEqual(wifi["Radio Type"], "802.11ax")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>IPv4 Address</th>", html)
        self.assertIn("<th>WinHTTP Proxy</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)

    def test_collect_notes_unparsed_command_text(self):
        class Context:
            def __init__(self):
                self.notes = []

            def query(self, name, script, timeout=None):
                return None

            def text(self, name, args, timeout=None):
                return "unrecognised localised output"

            def note(self, text):
                self.notes.append(text)

        ctx = Context()

        data = mod.collect(ctx)

        self.assertEqual(dict(data["groups"][1]["rows"])["WinHTTP Proxy"], "Not available")
        self.assertEqual(dict(data["groups"][2]["rows"])["Wi-Fi"], "Not available")
        self.assertTrue(any("winhttp" in note.lower() for note in ctx.notes))
        self.assertTrue(any("wlan" in note.lower() for note in ctx.notes))
