import unittest

from pc_report.sections import cpu as mod
from tests.pc_report import support

PROC = [{"Name": "Intel(R) Core(TM) i7-12700 CPU @ 2.10GHz", "Manufacturer": "GenuineIntel", "Description": "Intel64 Family 6 Model 151 Stepping 2",
         "ProcessorId": "BFEBFBFF000906A2", "SocketDesignation": "U3E1", "Architecture": 9, "AddressWidth": 64, "DataWidth": 64,
         "NumberOfCores": 12, "NumberOfEnabledCore": 12, "NumberOfLogicalProcessors": 20, "ThreadCount": 20,
         "MaxClockSpeed": 2100, "CurrentClockSpeed": 2100, "ExtClock": 100, "L2CacheSize": 12288, "L3CacheSize": 25600,
         "VirtualizationFirmwareEnabled": True, "VMMonitorModeExtensions": True, "SecondLevelAddressTranslationExtensions": True,
         "LoadPercentage": 7, "Status": "OK", "CpuStatus": 1, "CurrentVoltage": 8, "Family": 198, "Level": 6, "Revision": 38914,
         "Stepping": "", "Characteristics": 252, "PartNumber": "", "Caption": "Intel64 Family 6 Model 151 Stepping 2"}]
CACHES = [{"Purpose": "L1 Cache", "Level": 3, "InstalledSize": 1024, "MaxCacheSize": 1024, "Associativity": 7, "CacheType": 5, "CacheSpeed": None, "Status": "OK"},
          {"Purpose": "L2 Cache", "Level": 4, "InstalledSize": 12288, "MaxCacheSize": 12288, "Associativity": 8, "CacheType": 5, "CacheSpeed": None, "Status": "OK"}]
REG = {"ProcessorNameString": "12th Gen Intel(R) Core(TM) i7-12700", "Identifier": "Intel64 Family 6 Model 151 Stepping 2",
       "VendorIdentifier": "GenuineIntel", "Update Revision": [0, 0, 0, 0, 44, 0, 0, 0], "Previous Update Revision": [0, 0, 0, 0, 43, 0, 0, 0],
       "~MHz": 2112, "FeatureSet": 3219913727, "Platform ID": 0}
PERF = [{"Path": "\\\\pc\\processor information(_total)\\% processor utility", "InstanceName": "_total", "CookedValue": 12.5},
        {"Path": "\\\\pc\\processor information(0,0)\\% processor performance", "InstanceName": "0,0", "CookedValue": 145.2},
        {"Path": "\\\\pc\\processor information(0,1)\\% processor performance", "InstanceName": "0,1", "CookedValue": 98.0}]
FEATURES = {"SSE2": True, "AVX2": True, "AVX-512F": False}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(PROC, CACHES, REG, PERF, FEATURES)
        self.rows = mod.flatten(self.data)

    def test_identity(self):
        self.assertEqual(self.rows["Name"], "12th Gen Intel(R) Core(TM) i7-12700")
        self.assertEqual(self.rows["Vendor"], "GenuineIntel")
        self.assertEqual(self.rows["Architecture"], "x64")
        self.assertEqual(self.rows["Family / Model / Stepping"], "6 / 151 / 2")
        self.assertEqual(self.rows["Cores / Threads"], "12 / 20")
        self.assertEqual(self.rows["Max Clock"], "2100 MHz")
        self.assertEqual(self.rows["Microcode Revision"], "0x2C")
        self.assertEqual(self.rows["Voltage"], "0.8 V")

    def test_virtualization_and_load(self):
        self.assertEqual(self.rows["Virtualization Enabled in Firmware"], "Yes")
        self.assertEqual(self.rows["Second Level Address Translation"], "Yes")
        self.assertEqual(self.rows["Load"], "7 %")
        self.assertEqual(self.rows["Processor Utility (sample)"], "12.5 %")
        self.assertEqual(self.data["per_core"][0], {"Core": "0,0", "Performance": "145.2 %"})

    def test_caches_and_features(self):
        self.assertEqual(self.data["caches"][0]["Level"], "L1")
        self.assertEqual(self.data["caches"][0]["Associativity"], "8-way")
        self.assertEqual(self.data["caches"][1]["Size"], "12.0 MB")
        self.assertEqual(self.rows["Instruction Sets"], "SSE2, AVX2")
        self.assertEqual(self.rows["Not Available"], "AVX-512F")

    def test_microcode_from_hex_string(self):
        self.assertEqual(mod.microcode("0x000000B4"), "0xB4")
        self.assertEqual(mod.microcode(None), "")

    def test_microcode_rejects_invalid_values_and_list_lengths(self):
        self.assertEqual(mod.microcode([0, 0, 0, 0, 44, 0, 0, 0]), "0x2C")
        self.assertEqual(mod.microcode([1, 2, 3]), "")
        self.assertEqual(mod.microcode([0, 0, 0, 0, 44, 0, 0, 0, 0]), "")
        self.assertEqual(mod.microcode(None), "")
        self.assertEqual(mod.microcode("abc"), "")
        self.assertEqual(mod.microcode(44), "0x2C")

    def test_missing_and_nonnumeric_performance_samples_are_blank(self):
        perf = [
            {"Path": "% processor utility", "InstanceName": "_total", "CookedValue": None},
            {"Path": "% processor performance", "InstanceName": "0,0"},
            {"Path": "% processor performance", "InstanceName": "0,1", "CookedValue": "invalid"},
        ]
        data = mod.build(PROC, CACHES, REG, perf, FEATURES)
        self.assertEqual(mod.flatten(data)["Processor Utility (sample)"], "")
        self.assertEqual(
            data["per_core"],
            [{"Core": "0,0", "Performance": ""}, {"Core": "0,1", "Performance": ""}],
        )

    def test_single_performance_sample_dict_produces_one_core_row(self):
        perf = {"Path": "% processor performance", "InstanceName": "0,0", "CookedValue": 101.25}
        data = mod.build(PROC, CACHES, REG, perf, FEATURES)
        self.assertEqual(data["per_core"], [{"Core": "0,0", "Performance": "101.2 %"}])

    def test_all_aggregate_instances_are_excluded(self):
        perf = [
            {"Path": "% processor performance", "InstanceName": "_total", "CookedValue": 1},
            {"Path": "% processor performance", "InstanceName": "0,_total", "CookedValue": 2},
            {"Path": "% processor performance", "InstanceName": "_Total", "CookedValue": 3},
            {"Path": "% processor performance", "InstanceName": "0,0", "CookedValue": 4},
            {"Path": "% processor performance", "InstanceName": "0,10", "CookedValue": 5},
        ]
        data = mod.build(PROC, CACHES, REG, perf, FEATURES)
        self.assertEqual([row["Core"] for row in data["per_core"]], ["0,0", "0,10"])

    def test_probe_features_returns_dict(self):
        self.assertIsInstance(mod.probe_features(), dict)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Name", "Cores / Threads", "Max Clock", "Instruction Sets"):
            self.assertIn(f"<th>{label}</th>", html)
        self.assertIn("<h3>Cache</h3>", html)
        self.assertNotIn(",_total", html.casefold())

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
