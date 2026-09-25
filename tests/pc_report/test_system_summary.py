import unittest

from pc_report.sections import (
    bios,
    cpu,
    logical_disks,
    memory,
    motherboard,
    operating_system,
    video,
)
from pc_report.sections import system_summary as mod
from tests.pc_report import support

CS = {
    "Manufacturer": "Dell Inc.",
    "Model": "Precision 3660",
    "SystemFamily": "Precision",
    "SystemSKUNumber": "0ABC",
    "Name": "PC-NAME",
    "Domain": "lab.example.org",
    "PartOfDomain": True,
    "DomainRole": 1,
    "Workgroup": None,
    "PCSystemType": 1,
    "TotalPhysicalMemory": 34158411776,
    "UserName": "LAB\\user",
    "NumberOfProcessors": 1,
    "NumberOfLogicalProcessors": 20,
    "HypervisorPresent": True,
    "BootupState": "Normal boot",
    "PowerSupplyState": 3,
    "ThermalState": 3,
    "Description": "",
}
CSP = {
    "Name": "Precision 3660",
    "Vendor": "Dell Inc.",
    "Version": "1.0",
    "IdentifyingNumber": "ABC1234",
    "UUID": "4C4C4544-0000-1010-8020-B1C04F123456",
    "SKUNumber": "0ABC",
}
ENC = [
    {
        "ChassisTypes": [3],
        "SerialNumber": "ABC1234",
        "SMBIOSAssetTag": "",
        "Manufacturer": "Dell Inc.",
        "LockPresent": False,
    }
]
PFU = [
    {
        "Name": "C:\\pagefile.sys",
        "AllocatedBaseSize": 4864,
        "CurrentUsage": 120,
        "PeakUsage": 300,
    }
]
PFS = []
WINSAT = {
    "CPUScore": 9.1,
    "D3DScore": 9.9,
    "DiskScore": 9.2,
    "GraphicsScore": 9.0,
    "MemoryScore": 9.1,
    "WinSPRLevel": 9.0,
    "WinSATAssessmentState": 1,
}
POWER = (
    "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)\n"
)
RESULTS = {
    "operating_system": {
        "groups": [
            {
                "title": "Windows",
                "rows": {
                    "Name": "Microsoft Windows 11 Enterprise",
                    "Version": "24H2 (OS Build 26100.9445)",
                    "Kernel Version": "10.0.26100.9444",
                },
            },
            {
                "title": "Boot",
                "rows": {
                    "Boot Time": "2026-09-22 08:00",
                    "Up Time": "2 days, 1 hour, 5 minutes",
                    "Firmware Type": "UEFI",
                },
            },
            {
                "title": "Security and Policies",
                "rows": {"Secure Boot": "Yes"},
            },
        ]
    },
    "cpu": {
        "groups": [
            {
                "title": "Processor",
                "rows": {"Name": "12th Gen Intel(R) Core(TM) i7-12700"},
            },
            {
                "title": "Topology and Clocks",
                "rows": {"Cores / Threads": "12 / 20", "Max Clock": "2100 MHz"},
            },
            {"title": "Load", "rows": {"Load": "7 %"}},
        ]
    },
    "memory": {
        "groups": [
            {
                "title": "Summary",
                "rows": {"Installed Memory": "32.0 GB", "Memory Type": "DDR4"},
            },
            {
                "title": "Operating System View",
                "rows": {
                    "Total Physical": "31.8 GB",
                    "Free Physical": "19.1 GB",
                    "Memory Load": "40.0 %",
                    "Committed": "14.0 GB of 36.2 GB",
                    "Total Virtual": "36.2 GB",
                    "Free Virtual": "22.9 GB",
                },
            },
        ]
    },
    "video": {
        "adapters": [{"name": "NVIDIA GeForce RTX 3060", "groups": []}]
    },
    "logical_disks": {
        "rows": [
            {
                "Drive": "C:",
                "Label": "Windows",
                "Total": "929.5 GB",
                "Free": "45.6 GB",
                "Free %": "⚠ 4.9 %",
                "Type": "Local disk",
            }
        ]
    },
    "motherboard": {
        "groups": [
            {
                "title": "Board",
                "rows": {"Manufacturer": "Dell Inc.", "Model": "0ABC12"},
            }
        ]
    },
    "bios": {
        "groups": [
            {
                "title": "BIOS",
                "rows": {
                    "Vendor": "Dell Inc.",
                    "Version": "DELL - 1",
                    "SMBIOS BIOS Version": "1.2.3",
                    "Release Date": "2025-01-10",
                },
            }
        ]
    },
}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(CS, CSP, ENC, PFU, PFS, WINSAT, POWER, RESULTS)
        self.rows = mod.flatten(self.data)

    def test_identity(self):
        self.assertEqual(self.rows["Manufacturer"], "Dell Inc.")
        self.assertEqual(self.rows["Model"], "Precision 3660")
        self.assertEqual(self.rows["Chassis Type"], "Desktop")
        self.assertEqual(self.rows["PC System Type"], "Desktop")
        self.assertEqual(
            self.rows["UUID"], "4C4C4544-0000-1010-8020-B1C04F123456"
        )
        self.assertEqual(self.rows["Role"], "Member Workstation")
        self.assertEqual(self.rows["User Name"], "LAB\\user")

    def test_cross_section_rows(self):
        self.assertEqual(
            self.rows["Operating System"],
            "Microsoft Windows 11 Enterprise, 24H2 (OS Build 26100.9445)",
        )
        self.assertEqual(
            self.rows["Processor"],
            "12th Gen Intel(R) Core(TM) i7-12700 "
            "(12 / 20 cores / threads, 2100 MHz)",
        )
        self.assertEqual(
            self.rows["Physical Memory"],
            "31.8 GB total, 19.1 GB free (40.0 % load)",
        )
        self.assertEqual(self.rows["Video Adapters"], "NVIDIA GeForce RTX 3060")
        self.assertEqual(self.rows["Motherboard"], "Dell Inc. 0ABC12")
        self.assertEqual(self.rows["BIOS"], "Dell Inc. 1.2.3 (2025-01-10)")
        self.assertEqual(self.rows["Up Time"], "2 days, 1 hour, 5 minutes")

    def test_pagefile_power_winsat(self):
        self.assertEqual(
            self.rows["Page File"],
            "C:\\pagefile.sys: 4.8 GB allocated, 120.0 MB in use, 300.0 MB peak",
        )
        self.assertEqual(
            self.rows["Page File Management"], "Automatic (system managed)"
        )
        self.assertEqual(self.rows["Active Power Plan"], "Balanced")
        self.assertEqual(self.rows["Windows Experience Index (base)"], "9.0")
        self.assertEqual(self.data["drives"][0]["Drive"], "C:")

    def test_power_plan_parser_tolerates_localised_prefix(self):
        text = (
            "Aktives Energieschema: "
            "381b4222-f694-41f0-9685-ff5bb260df2e  (Ausbalanciert)"
        )
        rows = mod.flatten(mod.build({}, {}, [], [], [], {}, text, {}))
        self.assertEqual(rows["Active Power Plan"], "Ausbalanciert")

    def test_winsat_not_run(self):
        for winsat in (None, {"WinSATAssessmentState": "Not run"}):
            with self.subTest(winsat=winsat):
                rows = mod.flatten(
                    mod.build({}, {}, [], [], [], winsat, "", {})
                )
                self.assertEqual(
                    rows["Windows Experience Index (base)"], "Not assessed"
                )

    def test_missing_results(self):
        rows = mod.flatten(mod.build({}, {}, [], [], [], {}, "", {}))
        self.assertEqual(rows["Operating System"], "")
        self.assertEqual(rows["Active Power Plan"], "")
        self.assertEqual(
            rows["Page File Management"], "Automatic (system managed)"
        )

    def test_pagefile_management_distinguishes_failure_from_empty_success(self):
        self.assertEqual(mod._pagefile_management(None), "Not available")
        self.assertEqual(mod._pagefile_management([]), "Automatic (system managed)")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        results = {k: {"data": v, "notes": []} for k, v in RESULTS.items()}
        _data, html, ctx = support.collect_and_render(
            mod.SECTION, results=results
        )
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in (
            "Manufacturer",
            "Operating System",
            "Processor",
            "Physical Memory",
            "Active Power Plan",
        ):
            self.assertIn(f"<th>{label}</th>", html, label)
        self.assertIn("<h3>Drives</h3>", html)
        self.assertNotIn(CSP["UUID"], html)
        self.assertNotIn(CS["UserName"], html)

    def test_real_dependency_fixtures_feed_summary(self):
        dependencies = (
            operating_system,
            cpu,
            memory,
            video,
            logical_disks,
            motherboard,
            bios,
        )
        results = {
            dependency.SECTION.key: support.collect_and_render(
                dependency.SECTION, root=support.FIXTURES
            )[0]
            for dependency in dependencies
        }
        data, _html, ctx = support.collect_and_render(
            mod.SECTION, results=results, root=support.FIXTURES
        )
        rows = mod.flatten(data)
        for label in (
            "Operating System",
            "Processor",
            "Installed Memory",
            "Video Adapters",
            "Motherboard",
            "BIOS",
        ):
            self.assertTrue(rows[label], label)
        self.assertTrue(rows["Boot Time"])
        self.assertIn("cores / threads", rows["Processor"])
        self.assertTrue(rows["Memory Type"])
        self.assertIn("% load", rows["Physical Memory"])
        self.assertIn("20", rows["BIOS"])
        c_drive = next(
            (row for row in data["drives"] if row.get("Drive") == "C:"), None
        )
        self.assertIsNotNone(c_drive)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
