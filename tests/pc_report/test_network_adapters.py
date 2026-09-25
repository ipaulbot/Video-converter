import unittest

from pc_report.sections import network_adapters as mod
from tests.pc_report import support

ADAPTERS = [{"Name": "Ethernet", "InterfaceDescription": "Intel(R) Ethernet Connection I219-LM", "ifIndex": 12, "Status": "Up",
             "MacAddress": "AA-BB-CC-DD-EE-FF", "LinkSpeed": "1 Gbps", "MediaType": "802.3", "PhysicalMediaType": "802.3",
             "MtuSize": 1500, "DriverVersion": "12.19.2.45", "DriverDate": "2023-10-05", "DriverProvider": "Intel",
             "DriverFileName": "e1d68x64.sys", "DriverDescription": "Intel(R) Ethernet Connection I219-LM", "PnPDeviceID": "PCI\\VEN_8086&DEV_15BB\\3",
             "InterfaceGuid": "{guid}", "Virtual": False, "Hidden": False, "FullDuplex": True, "PromiscuousMode": False,
             "ReceiveLinkSpeed": 1000000000, "TransmitLinkSpeed": 1000000000, "ConnectorPresent": True, "NdisVersion": "6.85"}]
ADVANCED = [{"Name": "Ethernet", "DisplayName": "Jumbo Packet", "DisplayValue": "9014 Bytes", "RegistryKeyword": "*JumboPacket", "RegistryValue": ["9014"]},
            {"Name": "Ethernet", "DisplayName": "Receive Buffers", "DisplayValue": "2048", "RegistryKeyword": "*ReceiveBuffers", "RegistryValue": ["2048"]},
            {"Name": "Ethernet", "DisplayName": "Interrupt Moderation", "DisplayValue": "Enabled", "RegistryKeyword": "*InterruptModeration", "RegistryValue": ["1"]}]
IPIF = [{"ifIndex": 12, "AddressFamily": 2, "NlMtu": 1500, "InterfaceMetric": 25, "Dhcp": 1, "ConnectionState": 1},
        {"ifIndex": 12, "AddressFamily": 23, "NlMtu": 1500, "InterfaceMetric": 25, "Dhcp": 1, "ConnectionState": 1}]
WMI = [{"Name": "Intel(R) Ethernet Connection I219-LM", "NetConnectionID": "Ethernet", "NetConnectionStatus": 2, "PhysicalAdapter": True,
        "AdapterType": "Ethernet 802.3", "Speed": 1000000000, "MACAddress": "AA:BB:CC:DD:EE:FF", "Manufacturer": "Intel",
        "PNPDeviceID": "PCI\\VEN_8086&DEV_15BB\\3", "Index": 3, "InterfaceIndex": 12, "TimeOfLastReset": "/Date(1758000000000)/"}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(ADAPTERS, ADVANCED, IPIF, WMI)

    def test_adapter_groups(self):
        a = self.data["adapters"][0]
        rows = {}
        for g in a["groups"]:
            rows.update(g["rows"])
        self.assertEqual(a["name"], "Ethernet")
        self.assertEqual(rows["Description"], "Intel(R) Ethernet Connection I219-LM")
        self.assertEqual(rows["Link Speed"], "1 Gbps")
        self.assertEqual(rows["Connection Status"], "Connected")
        self.assertEqual(rows["IPv4 Metric"], 25)
        self.assertEqual(rows["IPv4 DHCP"], "Enabled")
        self.assertEqual(rows["Physical"], "Yes")
        self.assertEqual(rows["Adapter Type"], "Ethernet 802.3")

    def test_advanced_and_gige(self):
        self.assertEqual(self.data["adapters"][0]["advanced"][0]["Property"], "Jumbo Packet")
        g = self.data["gige"][0]
        self.assertEqual(g["Jumbo Packet"], "9014 Bytes")
        self.assertEqual(g["Receive Buffers"], "2048")
        self.assertEqual(g["Interrupt Moderation"], "Enabled")
        self.assertEqual(g["Transmit Buffers"], "")

    def test_summary(self):
        rows = dict(self.data["groups"][0]["rows"])
        self.assertEqual(rows["Adapters"], 1)
        self.assertEqual(rows["Physical Adapters"], 1)
        self.assertEqual(rows["Connected"], 1)

    def test_single_rows_missing_joins_sorting_and_link_speed(self):
        virtual = {
            "Name": "vEthernet (Default Switch)", "ifIndex": "bad", "Status": "Down",
            "LinkSpeed": 1000000000, "Virtual": True, "Hidden": True, "ConnectorPresent": False,
        }
        data = mod.build([virtual, ADAPTERS[0]], ADVANCED[0], IPIF[0], WMI[0])

        self.assertEqual([row["name"] for row in data["adapters"]], ["Ethernet", "vEthernet (Default Switch)"])
        self.assertEqual(data["adapters"][1]["groups"][1]["rows"]["Link Speed"], "1000.0 Mbps")
        self.assertEqual(len(data["gige"]), 1)
        self.assertEqual(data["gige"][0]["Adapter"], "Ethernet")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Link Speed</th>", html)
        self.assertIn("<th>MAC Address</th>", html)
        self.assertNotIn("AA-BB-CC-DD-EE-FF", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
