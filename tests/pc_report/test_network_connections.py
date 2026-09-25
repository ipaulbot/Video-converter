import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import network_connections as mod
from tests.pc_report import support

MAPPED = [
    {
        "Name": "Z:",
        "ProviderName": r"\\server\share",
        "FileSystem": "NTFS",
        "Size": 2000000000000,
        "FreeSpace": 1000000000000,
        "VolumeName": "share",
    }
]
SMB = [{"LocalPath": "Z:", "RemotePath": r"\\server\share", "Status": "OK"}]
VPN = [
    {
        "Name": "Office",
        "ServerAddress": "vpn.example.org",
        "ConnectionStatus": "Disconnected",
        "TunnelType": "Automatic",
        "AuthenticationMethod": ["Eap"],
        "SplitTunneling": False,
    }
]
TCP = [
    {
        "LocalAddress": "0.0.0.0",
        "LocalPort": 135,
        "RemoteAddress": "0.0.0.0",
        "RemotePort": 0,
        "State": "Listen",
        "OwningProcess": 1000,
    },
    {
        "LocalAddress": "192.168.10.55",
        "LocalPort": 51000,
        "RemoteAddress": "52.1.2.3",
        "RemotePort": 443,
        "State": "Established",
        "OwningProcess": 2000,
    },
]
UDP = [{"LocalAddress": "0.0.0.0", "LocalPort": 5353, "OwningProcess": 3000}]
PROCS = [
    {"Id": 1000, "ProcessName": "svchost"},
    {"Id": 2000, "ProcessName": "msedge"},
    {"Id": 3000, "ProcessName": "svchost"},
]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(MAPPED, SMB, VPN, TCP, UDP, PROCS)

    def test_tables(self):
        self.assertEqual(self.data["mapped"][0]["Remote Path (host name)"], r"\\server\share")
        self.assertEqual(self.data["mapped"][0]["Free"], "931.3 GB")
        self.assertEqual(self.data["vpn"][0]["Server (host name)"], "vpn.example.org")
        self.assertEqual(self.data["listening"][0]["Process"], "svchost (1000)")
        self.assertEqual(self.data["established"][0]["Process"], "msedge (2000)")
        self.assertEqual(self.data["established"][0]["Connections"], 1)
        self.assertEqual(self.data["established"][0]["Remote Hosts"], 1)
        self.assertNotIn("Remote Address", self.data["established"][0])
        self.assertEqual(self.data["udp"][0]["Local Port"], 5353)
        rows = dict(self.data["groups"][0]["rows"])
        self.assertEqual(rows["Listening TCP Ports"], 1)
        self.assertEqual(rows["Established TCP Connections"], 1)

    def test_deduplicates_and_aggregates_large_socket_sets(self):
        tcp = TCP + [
            {**TCP[0], "LocalAddress": "::"},
            {**TCP[1], "RemoteAddress": "52.1.2.4"},
            {**TCP[1], "RemoteAddress": "52.1.2.4"},
            {
                "LocalPort": "bad",
                "State": 5,
                "RemoteAddress": None,
                "OwningProcess": None,
            },
        ]
        udp = UDP + [{**UDP[0], "LocalAddress": "::"}]
        data = mod.build(MAPPED, SMB, VPN, tcp, udp, PROCS)
        self.assertEqual(len(data["listening"]), 1)
        self.assertEqual(data["established"][0]["Connections"], 3)
        self.assertEqual(data["established"][0]["Remote Hosts"], 2)
        self.assertEqual(len(data["udp"]), 1)
        states = dict(data["groups"][1]["rows"])
        self.assertEqual(states["Established"], 4)
        self.assertEqual(states["Listen"], 2)

    def test_single_dict_inputs_and_process_misses(self):
        row = mod.build(
            None,
            None,
            None,
            {
                "LocalPort": None,
                "State": 2,
                "OwningProcess": "9999",
            },
            {"LocalPort": "53", "OwningProcess": "bad"},
            {"Id": "1000", "ProcessName": "svchost"},
        )
        self.assertEqual(row["listening"][0]["Process"], "unknown (9999)")
        self.assertEqual(row["udp"][0]["Process"], "")

    def test_redaction(self):
        red = redact_payload(self.data, {"redact": True}, env={})
        self.assertEqual(red["listening"][0]["Local Address"], "0.0.0.0")
        self.assertNotIn("server", red["mapped"][0]["Remote Path (host name)"])
        self.assertNotIn("example", red["vpn"][0]["Server (host name)"])
        self.assertNotIn("Remote Address", repr(red["established"]))


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertTrue(
            any(
                "Mapped drives (WMI) unavailable or timed out" in note
                for note in ctx.notes
            )
        )
        self.assertIn("<h3>Listening TCP ports</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
