import unittest

from pc_report.sections import motherboard as mod
from tests.pc_report import support

BB = {"Manufacturer": "Dell Inc.", "Product": "0ABC12", "Version": "A00", "SerialNumber": "/ABC123/", "Tag": "Base Board"}
SOCK = [{"SocketDesignation": "CPU 1", "UpgradeMethod": 1}]
ARR = [{"MaxCapacity": 134217728, "MaxCapacityEx": 134217728, "MemoryDevices": 4, "MemoryErrorCorrection": 3, "Use": 3, "Location": 3}]
SLOTS = [{"SlotDesignation": "PCIEX16_1", "CurrentUsage": 4, "MaxDataWidth": 10},
         {"SlotDesignation": "PCIEX1_1", "CurrentUsage": 3, "MaxDataWidth": 5}]
ONBOARD = [{"Description": "Realtek Audio", "DeviceType": 7, "Enabled": True}]
CONN = [{"ExternalReferenceDesignator": "USB1", "InternalReferenceDesignator": "", "ConnectorType": [16], "PortType": 16}]


class BuildTests(unittest.TestCase):
    def test_groups(self):
        rows = mod.flatten(mod.build(BB, SOCK, ARR, SLOTS, ONBOARD, CONN))
        self.assertEqual(rows["Manufacturer"], "Dell Inc.")
        self.assertEqual(rows["Model"], "0ABC12")
        self.assertEqual(rows["CPU Socket"], "CPU 1")
        self.assertEqual(rows["Maximum Memory"], "128.0 GB")
        self.assertEqual(rows["Memory Slots"], 4)
        self.assertEqual(rows["Error Correction"], "None")
        self.assertEqual(rows["Slots In Use"], "1 of 2")

    def test_tables(self):
        data = mod.build(BB, SOCK, ARR, SLOTS, ONBOARD, CONN)
        self.assertEqual(data["onboard"][0]["Type"], "Sound")
        self.assertEqual(data["connectors"][0]["Port Type"], "USB")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Manufacturer</th>", html)
        self.assertIn("<h3>External connectors</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
