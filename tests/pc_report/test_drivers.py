import unittest

from pc_report.sections import drivers as mod
from tests.pc_report import support

SIGNED = [{"DeviceName": "Basler pylon GigE", "DeviceClass": "NET", "DriverVersion": "7.1.0.1", "DriverDate": "20240101000000.000000-000",
           "DriverProviderName": "Basler AG", "Manufacturer": "Basler", "InfName": "oem42.inf", "IsSigned": True,
           "Signer": "Microsoft Windows Hardware Compatibility Publisher", "DeviceID": "PCI\\VEN_8086&DEV_1533\\1234"},
          {"DeviceName": "Generic Monitor", "DeviceClass": "MONITOR", "DriverVersion": "10.0.1", "DriverDate": None,
           "DriverProviderName": "Microsoft", "Manufacturer": "(Standard monitor types)", "InfName": "monitor.inf",
           "IsSigned": True, "Signer": "Microsoft Windows", "DeviceID": "DISPLAY\\ABC"}]
SYSTEM = [{"Name": "hasplms", "DisplayName": "Sentinel", "State": "Running", "StartMode": "Auto",
           "PathName": "C:\\Windows\\system32\\drivers\\hardlock.sys", "ServiceType": "Kernel Driver", "Started": True}]


class BuildTests(unittest.TestCase):
    def test_grouped_by_class_and_summary(self):
        data = mod.build(SIGNED, SYSTEM)
        self.assertEqual(sorted(data["by_class"]), ["Monitor", "NET"])
        net = data["by_class"]["NET"][0]
        self.assertEqual(net["Date"], "2024-01-01")
        self.assertEqual(net["Signed"], "Yes")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["PnP Drivers"], 2)
        self.assertEqual(rows["Unsigned Drivers"], 0)
        self.assertEqual(rows["System Drivers"], 1)
        self.assertEqual(data["system"][0]["Started"], "Yes")

    def test_rows_are_capped_with_shown_and_total(self):
        signed = [{"DeviceName": f"Device {index:04d}", "DeviceClass": "TEST"}
                  for index in range(mod.ROW_CAP + 1)]
        data = mod.build(signed, [])
        summary = data["groups"][0]["rows"]
        self.assertEqual(sum(len(rows) for rows in data["by_class"].values()), mod.ROW_CAP)
        self.assertEqual(summary["Shown"], mod.ROW_CAP)
        self.assertEqual(summary["Total"], mod.ROW_CAP + 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>INF</th>", html)
        self.assertIn("<h3>System drivers</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
