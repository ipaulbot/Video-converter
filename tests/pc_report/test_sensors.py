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
        self.assertEqual(rows["GPU 3D Utilization"], "5.5 %")
        self.assertEqual(self.data["disks"][0], {"Disk": "0 c:", "Active": "3.1 %"})
        self.assertEqual(self.data["gpus"][0]["Dedicated Memory In Use"], "1.0 GB")
        self.assertEqual(self.data["nics"][0]["Throughput"], "1.0 Mbps")

    def test_voltage_probe(self):
        self.assertEqual(self.data["probes"][0], {"Kind": "Voltage", "Name": "VCORE", "Reading": "1.200 V", "Status": "OK"})


class GpuEngineTests(unittest.TestCase):
    @staticmethod
    def sample(engine, value, pid=1):
        instance = f"pid_{pid}_luid_0x0_0x1_phys_0_engtype_{engine}"
        return {"Path": f"\\\\pc\\gpu engine({instance})\\utilization percentage",
                "InstanceName": instance, "CookedValue": value}

    def test_groups_clamps_filters_and_orders_gpu_engines(self):
        samples = [
            self.sample("VideoDecode", 12.5),
            self.sample("3D", 60, pid=1),
            self.sample("Copy", 0),
            self.sample("3D", 90, pid=2),
        ]

        self.assertEqual(mod.gpu_by_engine(samples), {"Video Decode": 12.5, "3D": 100.0, "Copy": 0.0})
        rows = mod.flatten(mod.build([], [], {}, [], samples))
        gpu_labels = [label for label in rows if label.startswith("GPU ")]
        self.assertEqual(gpu_labels, ["GPU 3D Utilization", "GPU Video Decode Utilization"])
        self.assertEqual(rows["GPU 3D Utilization"], "100.0 %")
        self.assertEqual(rows["GPU Video Decode Utilization"], "12.5 %")

    def test_ignores_malformed_instance_and_nonnumeric_values(self):
        samples = [
            {"Path": "\\\\pc\\gpu engine(pid_1)\\utilization percentage",
             "InstanceName": "pid_1", "CookedValue": 50},
            self.sample("Compute", None),
            self.sample("Security", "abc"),
        ]

        self.assertEqual(mod.gpu_by_engine(samples), {})

    def test_orders_unknown_engine_types_alphabetically_after_common_types(self):
        samples = [
            self.sample("beta_engine", 2),
            self.sample("compute", 3),
            self.sample("alpha_engine", 1),
        ]

        rows = mod.flatten(mod.build([], [], {}, [], samples))
        gpu_labels = [label for label in rows if label.startswith("GPU ")]
        self.assertEqual(gpu_labels, [
            "GPU 3D Utilization", "GPU Compute Utilization",
            "GPU Alpha_Engine Utilization", "GPU Beta_Engine Utilization",
        ])

    def test_counter_script_samples_all_gpu_engine_types(self):
        self.assertIn(r"'\GPU Engine(*)\Utilization Percentage'", mod.COUNTERS_SCRIPT)
        self.assertNotIn("engtype_3D", mod.COUNTERS_SCRIPT)


class CounterFamilyTests(unittest.TestCase):
    def test_reports_all_families_except_present_processor(self):
        samples = [{"Path": "\\\\pc\\processor information(_total)\\% processor utility"}]

        self.assertEqual(mod.missing_counter_families(samples), [
            "Memory", "PhysicalDisk", "GPU Engine", "GPU Adapter Memory", "Network Interface",
        ])

    def test_reports_no_missing_families_for_full_set(self):
        samples = [{"Path": f"\\\\pc\\{fragment}"} for fragment in (
            "% processor utility", "% committed bytes in use", "physicaldisk",
            "gpu engine", "gpu adapter memory", "network interface",
        )]

        self.assertEqual(mod.missing_counter_families(samples), [])


class TemperatureTests(unittest.TestCase):
    def test_rejects_implausible_temperatures(self):
        expected = {2732: "0.05 °C", 0: "", 65535: "", 3100: "36.85 °C", None: "", "abc": ""}

        for value, result in expected.items():
            with self.subTest(value=value):
                self.assertEqual(mod._celsius(value), result)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>CPU Utility</th>", html)
        self.assertIn("vendor tool", html)
        self.assertIn(
            "Performance counter sets unavailable on this system: Memory, PhysicalDisk, Network Interface.",
            ctx.notes,
        )

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
