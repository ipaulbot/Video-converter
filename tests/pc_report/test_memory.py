import unittest

from pc_report.privacy import redact_payload
from pc_report.section import RenderContext
from pc_report.sections import memory as mod
from tests.pc_report import support

ARR = [{"MaxCapacity": 134217728, "MaxCapacityEx": 134217728, "MemoryDevices": 4, "MemoryErrorCorrection": 3}]
MODS = [{"DeviceLocator": "DIMM 1", "BankLabel": "BANK 0", "Capacity": 17179869184, "Speed": 3200, "ConfiguredClockSpeed": 3200,
         "ConfiguredVoltage": 1200, "MinVoltage": 1200, "MaxVoltage": 1200, "DataWidth": 64, "TotalWidth": 64, "FormFactor": 8,
         "MemoryType": 0, "SMBIOSMemoryType": 26, "TypeDetail": 128, "Manufacturer": "Kingston", "PartNumber": "KF3200C16D4/16GX ",
         "SerialNumber": "1234ABCD", "Tag": "Physical Memory 0"},
        {"DeviceLocator": "DIMM 3", "BankLabel": "BANK 2", "Capacity": 17179869184, "Speed": 3200, "ConfiguredClockSpeed": 2933,
         "ConfiguredVoltage": 1200, "MinVoltage": 1200, "MaxVoltage": 1200, "DataWidth": 64, "TotalWidth": 72, "FormFactor": 8,
         "MemoryType": 0, "SMBIOSMemoryType": 26, "TypeDetail": 8320, "Manufacturer": "Kingston", "PartNumber": "KF3200C16D4/16GX",
         "SerialNumber": "5678EF01", "Tag": "Physical Memory 2"}]
OS = {"TotalVisibleMemorySize": 33357824, "FreePhysicalMemory": 20000000, "TotalVirtualMemorySize": 38000000,
      "FreeVirtualMemory": 24000000, "SizeStoredInPagingFiles": 4718592, "FreeSpaceInPagingFiles": 4600000}
PERF = {"CommittedBytes": 15000000000, "CommitLimit": 38912000000, "AvailableBytes": 20480000000, "CacheBytes": 900000000,
        "PoolPagedBytes": 500000000, "PoolNonpagedBytes": 400000000}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(ARR, MODS, OS, PERF)
        self.rows = mod.flatten(self.data)

    def test_summary(self):
        self.assertEqual(self.rows["Installed Memory"], "32.0 GB")
        self.assertEqual(self.rows["Slots Used"], "2 of 4")
        self.assertEqual(self.rows["Memory Type"], "DDR4")
        self.assertEqual(self.rows["Total Physical"], "31.8 GB")
        self.assertEqual(self.rows["Memory Load"], "40.0 %")
        self.assertEqual(self.rows["Committed"], "14.0 GB of 36.2 GB")

    def test_modules(self):
        m = self.data["modules"][1]
        self.assertEqual(m["Capacity"], "16.0 GB")
        self.assertEqual(m["Speed"], "3200 MT/s")
        self.assertEqual(m["Configured Speed"], "2933 MT/s")
        self.assertEqual(m["Voltage"], "1.2 V")
        self.assertEqual(m["ECC"], "Yes")
        self.assertEqual(m["Form Factor"], "DIMM")
        self.assertEqual(m["Type Detail"], "Synchronous, Registered (Buffered)")
        self.assertEqual(m["Part Number"], "KF3200C16D4/16GX")

    def test_notes_mention_spd(self):
        self.assertIn("SPD", self.rows["Timings"])

    def test_missing_and_nonnumeric_numbers_are_blank(self):
        module = {
            "Capacity": "invalid", "Speed": None, "ConfiguredClockSpeed": "invalid",
            "ConfiguredVoltage": "invalid", "MaxVoltage": None, "DataWidth": "invalid",
            "TotalWidth": None, "TypeDetail": None,
        }
        os_view = {
            "TotalVisibleMemorySize": "invalid", "FreePhysicalMemory": None,
            "TotalVirtualMemorySize": "invalid", "FreeVirtualMemory": None,
            "SizeStoredInPagingFiles": "invalid", "FreeSpaceInPagingFiles": None,
        }
        perf = {
            "CommittedBytes": "invalid", "CommitLimit": None, "AvailableBytes": "invalid",
            "CacheBytes": None, "PoolPagedBytes": "invalid", "PoolNonpagedBytes": None,
        }
        data = mod.build({"MaxCapacity": "invalid", "MemoryDevices": "invalid"}, module, os_view, perf)
        rows = mod.flatten(data)
        self.assertEqual(data["modules"][0]["Capacity"], "")
        self.assertEqual(data["modules"][0]["Speed"], "")
        self.assertEqual(data["modules"][0]["Configured Speed"], "")
        self.assertEqual(data["modules"][0]["Voltage"], "")
        self.assertEqual(data["modules"][0]["Type Detail"], "")
        for label in (
            "Maximum Capacity", "Total Physical", "Free Physical", "Used Physical",
            "Memory Load", "Total Virtual", "Free Virtual", "Paging Files",
            "Paging Files Free", "Committed", "Available", "System Cache",
            "Paged Pool", "Non-paged Pool",
        ):
            self.assertEqual(rows[label], "", label)

    def test_single_module_dict_and_memory_type_preference(self):
        module = dict(MODS[0], SMBIOSMemoryType=34, MemoryType=24)
        data = mod.build(ARR, module, OS, PERF)
        self.assertEqual(len(data["modules"]), 1)
        self.assertEqual(data["modules"][0]["Type"], "DDR5")
        self.assertEqual(mod.flatten(data)["Memory Type"], "DDR5")

    def test_zero_smbios_memory_type_falls_back_to_memory_type(self):
        module = dict(MODS[0], SMBIOSMemoryType=0, MemoryType=24)
        self.assertEqual(mod.build(ARR, module, OS, PERF)["modules"][0]["Type"], "DDR3")

    def test_serial_is_masked_but_part_number_stays_public(self):
        redacted = redact_payload(self.data, {"redact": True}, env={})
        html = mod.render(redacted, RenderContext())
        self.assertNotIn("1234ABCD", html)
        self.assertNotIn("5678EF01", html)
        self.assertIn("KF3200C16D4/16GX", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Installed Memory</th>", html)
        self.assertIn("<th>Part Number</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
