import unittest

from pc_report.sections import sensors as mod
from tests.pc_report import support

THERMAL = [{"InstanceName": "ACPI\\ThermalZone\\TZ00_0", "CurrentTemperature": 3132, "CriticalTripPoint": 3782, "PassiveTripPoint": 0, "ActiveTripPoint": [0]}]
FANS = [{"Name": "Cooling Device", "DesiredSpeed": None, "Status": "OK", "ActiveCooling": True}]
PROBES = {"Temperature": [], "Voltage": [{"Name": "VCORE", "CurrentReading": 1200, "Status": "OK"}]}
BATTERY = [{"Name": "DELL 1234", "BatteryStatus": 2, "EstimatedChargeRemaining": 87, "EstimatedRunTime": 71582788, "DesignVoltage": 11400, "Chemistry": 6}]
COUNTERS = [{"Path": "\\\\pc\\processor information(_total)\\% processor utility", "InstanceName": "_total", "CookedValue": 9.7},
            {"Path": "\\\\pc\\memory\\% committed bytes in use", "InstanceName": "", "CookedValue": 38.2},
            {"Path": "\\\\pc\\memory\\available mbytes", "InstanceName": "", "CookedValue": 19532},
            {"Path": "\\\\pc\\physicaldisk(0 c:)\\% disk time", "InstanceName": "0 c:", "CookedValue": 3.1},
            {"Path": "\\\\pc\\physicaldisk(_total)\\% disk time", "InstanceName": "_total", "CookedValue": 3.1},
            {"Path": "\\\\pc\\gpu engine(pid_1234_luid_0x0_0x1_phys_0_engtype_3d)\\utilization percentage", "InstanceName": "pid_1234_luid_0x0_0x1_phys_0_engtype_3d", "CookedValue": 4.0},
            {"Path": "\\\\pc\\gpu engine(pid_99_luid_0x0_0x1_phys_0_engtype_3d)\\utilization percentage", "InstanceName": "pid_99_luid_0x0_0x1_phys_0_engtype_3d", "CookedValue": 1.5},
            {"Path": "\\\\pc\\gpu adapter memory(luid_0x0_0x1_phys_0)\\dedicated usage", "InstanceName": "luid_0x0_0x1_phys_0", "CookedValue": 1073741824},
            {"Path": "\\\\pc\\network interface(intel ethernet)\\bytes total/sec", "InstanceName": "intel ethernet", "CookedValue": 125000}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(THERMAL, FANS, PROBES, BATTERY, COUNTERS)

    def test_thermal_zone_in_celsius(self):
        tz = self.data["thermal"][0]
        self.assertEqual(tz["Zone"], "TZ00_0")
        self.assertEqual(tz["Temperature"], "40.05 °C")
        self.assertEqual(tz["Critical"], "105.05 °C")

    def test_battery(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Battery Status"], "Unknown / AC power")
        self.assertEqual(rows["Charge"], "87 %")
        self.assertEqual(rows["Estimated Runtime"], "")  # 71582788 means "on AC"
        self.assertEqual(rows["Chemistry"], "Lithium-ion")

    def test_counters(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["CPU Utility"], "9.7 %")
        self.assertEqual(rows["Memory Committed"], "38.2 %")
        self.assertEqual(rows["Memory Available"], "19532 MB")
        self.assertEqual(rows["GPU 3D Utilization (all processes)"], "5.5 %")
        self.assertEqual(self.data["disks"][0], {"Disk": "0 c:", "Active": "3.1 %"})
        self.assertEqual(self.data["gpus"][0]["Dedicated Memory In Use"], "1.0 GB")
        self.assertEqual(self.data["nics"][0]["Throughput"], "1.0 Mbps")

    def test_voltage_probe(self):
        self.assertEqual(self.data["probes"][0], {"Kind": "Voltage", "Name": "VCORE", "Reading": "1.200 V", "Status": "OK"})


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>CPU Utility</th>", html)
        self.assertIn("vendor tool", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
