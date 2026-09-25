import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import pci as mod
from tests.pc_report import support

PNP = [{"Name": "Intel(R) Ethernet Connection I219-LM", "Manufacturer": "Intel", "PNPClass": "Net", "DeviceID": "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\3&11583659&0&FE",
        "PNPDeviceID": "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\3&11583659&0&FE", "Status": "OK", "ConfigManagerErrorCode": 0, "Service": "e1dexpress", "Present": True},
       {"Name": "USB Root Hub", "PNPClass": "USB", "DeviceID": "USB\\ROOT_HUB30\\4", "PNPDeviceID": "USB\\ROOT_HUB30\\4", "Status": "OK", "ConfigManagerErrorCode": 0, "Present": True}]
PROPS = [{"InstanceId": "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\3&11583659&0&FE", "Location": "PCI bus 0, device 31, function 6",
          "DriverVersion": "12.19.2.45", "DriverDate": "/Date(1700000000000)/", "Bus": 0, "Address": 2031622}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(PNP, PROPS)
        self.assertEqual(len(data["rows"]), 1)
        r = data["rows"][0]
        self.assertEqual(r["Vendor"], "Intel Corporation")
        self.assertEqual(r["Vendor ID"], "8086")
        self.assertEqual(r["Device ID"], "15BB")
        self.assertEqual(r["Subsystem"], "08B21028")
        self.assertEqual(r["Revision"], "10")
        self.assertEqual(r["Bus / Device / Function"], "0 / 31 / 6")
        self.assertEqual(r["Driver Version"], "12.19.2.45")

    def test_parse_ids(self):
        self.assertEqual(mod.parse_ids("PCI\\VEN_10DE&DEV_2204&SUBSYS_38971462&REV_A1\\4&x"), ("10DE", "2204", "38971462", "A1"))
        self.assertEqual(mod.parse_ids("PCI\\VEN_10DE&DEV_2204\\x"), ("10DE", "2204", "", ""))


class PrivacyTests(unittest.TestCase):
    def test_rendered_instance_ids_lose_their_distinctive_tail(self):
        instance = "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\LABSERIALTAIL"
        pnp = [{**PNP[0], "DeviceID": instance, "PNPDeviceID": instance}]

        data = mod.build(pnp, [])
        html = mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

        self.assertNotIn("LABSERIALTAIL", html)
        # The vendor, device and class context a support engineer needs must survive.
        self.assertIn("VEN_8086", html)
        self.assertIn("Intel Corporation", html)

    def test_bus_topology_segments_stay_readable(self):
        html = mod.render(redact_payload(mod.build(PNP, PROPS), {"redact": True}, env={}),
                          support.render_ctx())

        self.assertIn("3&amp;11583659&amp;0&amp;FE", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Vendor ID</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
