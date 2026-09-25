import unittest

from pc_report.sections import ports as mod
from tests.pc_report import support

CONN = [{"ExternalReferenceDesignator": "USB 1", "ConnectorType": [16], "PortType": 16}]
SERIAL = [{"Name": "Communications Port (COM1)", "DeviceID": "COM1", "Description": "Communications Port", "MaxBaudRate": 115200,
           "ProviderType": "RS232 Serial Port", "Status": "OK", "PNPDeviceID": "ACPI\\PNP0501\\0"}]
SERIALCOMM = [{"Name": "\\Device\\Serial0", "Value": "COM1"}, {"Name": "\\Device\\USBSER000", "Value": "COM5"}]
PARALLEL = []


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(CONN, SERIAL, SERIALCOMM, PARALLEL)
        self.assertEqual(data["connectors"][0]["Port Type"], "USB")
        self.assertEqual(data["serial"][0]["Max Baud Rate"], "115200 baud")
        com5 = next(r for r in data["serialcomm"] if r["Port"] == "COM5")
        self.assertEqual(com5["Device"], "\\Device\\USBSER000")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["COM Ports Registered"], "COM1, COM5")

    def test_serialcomm_dict_and_numeric_port_order(self):
        data = mod.build([], [{"MaxBaudRate": "unknown"}],
                         {"\\Device\\Serial9": "COM10", "\\Device\\Serial2": "COM2"}, [])
        self.assertEqual([row["Port"] for row in data["serialcomm"]], ["COM2", "COM10"])
        self.assertEqual(data["serial"][0]["Max Baud Rate"], "")

    def test_connectors_are_sorted_by_designator_then_type(self):
        connectors = [
            {"ExternalReferenceDesignator": "USB 2", "ConnectorType": [63], "PortType": 16},
            {"ExternalReferenceDesignator": "USB 1", "ConnectorType": [64], "PortType": 16},
            {"ExternalReferenceDesignator": "USB 1", "ConnectorType": [63], "PortType": 16},
        ]
        data = mod.build(connectors, [], [], [])
        self.assertEqual(
            [(row["Designator"], row["Connector"]) for row in data["connectors"]],
            [("USB 1", "USB Type-A"), ("USB 1", "USB Type-B"), ("USB 2", "USB Type-A")],
        )

    def test_parallel_ports_are_sorted_by_device_then_name(self):
        parallel = [
            {"Name": "Second", "DeviceID": "LPT2"},
            {"Name": "Zulu", "DeviceID": "LPT1"},
            {"Name": "Alpha", "DeviceID": "LPT1"},
        ]
        data = mod.build([], [], [], parallel)
        self.assertEqual(
            [(row["Device"], row["Name"]) for row in data["parallel"]],
            [("LPT1", "Alpha"), ("LPT1", "Zulu"), ("LPT2", "Second")],
        )


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Serial ports (registry SERIALCOMM)</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
