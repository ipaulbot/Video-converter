import copy
import unittest

from pc_report import registry
from pc_report.sections import noldus_summary as mod
from tests.pc_report import support

RESULTS = {
    "operating_system": {
        "groups": [
            {"title": "Windows", "rows": {"Name": "Windows 11", "Version": "24H2"}},
            {"title": "Boot", "rows": {"Pending Reboot": "Yes", "Boot Time": "2026-09-22 08:00", "Up Time": "2 days"}},
        ]
    },
    "installed_programs": {
        "rows": [
            {"Name": "EthoVision XT 19", "Version": "19.0", "Publisher": "Noldus", "Install Date": "2026-05-22", "Install Location": r"C:\EV"},
            {"Name": "Microsoft Visual C++ 2015-2022 Redistributable (x64)", "Version": "14.40", "Publisher": "Microsoft"},
            {"Name": "7-Zip", "Version": "23", "Publisher": "Igor Pavlov"},
        ]
    },
    "drivers": {
        "by_class": {
            "NET": [{"Device": "Basler pylon GigE Filter", "Version": "7.1", "Date": "2024-01-01", "Provider": "Basler AG", "INF": "oem42.inf", "Signed": "Yes"}],
            "USB": [{"Device": "Sentinel HASP Key", "Version": "8.5", "Date": "2023-01-01", "Provider": "SafeNet", "INF": "oem9.inf", "Signed": "Yes"}],
        }
    },
    "codecs": {"categories": {"DirectShow Filters": [{"Name": "Noldus Resizer Filter", "File": r"C:\x\Resizer.ax", "Version": "1.0", "Company": "Noldus", "Architecture": "x64"}]}},
    "environment": {"Machine": [{"Name": "GENICAM_GENTL64_PATH", "Value": r"C:\Program Files\Basler"}], "User": [], "Process": []},
    "cameras": {
        "pnp": [{"Name": "Basler ace acA1920", "Class": "Camera", "Status": "OK", "Problem": ""}],
        "groups": [
            {"title": "Windows Camera Frame Server", "rows": {"Frame Server Mode": "Enabled (shared camera access through Frame Server)"}},
            {"title": "Camera and Microphone Consent", "rows": {"Camera Access (user)": "Deny"}},
        ],
    },
    "usb": {
        "devices": [{"Name": "SafeNet Inc. Sentinel HASP Key", "VID / PID": "0529 / 0001", "Status": "OK", "Present": "Yes"}],
        "groups": [{"title": "Summary", "rows": {"Selective Suspend (AC)": "Enabled", "Selective Suspend (DC)": "Enabled"}}],
    },
    "services": {"rows": [{"Name": "hasplms", "Display Name": "Sentinel LDK License Manager", "State": "Stopped", "Start Mode": "Automatic"}]},
    "network_adapters": {"gige": [{"Adapter": "Ethernet", "Link Speed": "1 Gbps", "Jumbo Packet": "Disabled", "Interrupt Moderation": "Enabled"}]},
    "security": {"groups": [{"title": "Policies", "rows": {"User Account Control (UAC)": "Disabled"}}]},
    "memory": {"groups": [{"title": "Summary", "rows": {"Installed Memory": "32.0 GB"}}, {"title": "Operating System View", "rows": {"Live Source": "GlobalMemoryStatusEx"}}]},
    "cpu": {"groups": [{"title": "Processor", "rows": {"Name": "i7-12700"}}]},
    "video": {"adapters": [{"name": "RTX 3060"}]},
    "logical_disks": {
        "groups": [{"title": "Summary", "rows": {"Low Space (<10 %)": "C:"}}],
        "rows": [
            {"Drive": "C:", "Type": "Local Fixed Disk", "Free": "8.0 GB", "Free %": "8.0 %"},
            {"Drive": "D:", "Type": "Local Fixed Disk", "Free": "20.0 GB", "Free %": "20.0 %"},
        ],
    },
    "devices": {"groups": [{"title": "Summary", "rows": {"Problem Devices": 1}}], "problems": [{"Name": "Unknown device", "Problem": "28: Drivers not installed"}]},
    "system_summary": {
        "groups": [
            {"title": "Computer", "rows": {"Manufacturer": "Dell Inc.", "Model": "Precision 3660"}},
            {"title": "Overview", "rows": {"Operating System": "Windows 11, 24H2", "Processor": "i7-12700", "Installed Memory": "32.0 GB", "Video Adapters": "RTX 3060"}},
        ],
        "drives": [{"Drive": "C:", "Free": "8.0 GB", "Free %": "8.0 %"}],
    },
    "sensors": {"groups": [{"title": "Live Sample (1 s)", "rows": {"CPU Utility": ""}}]},
    "virtual_machine": {"groups": [{"title": "Detection", "rows": {"Running Inside a VM": "Yes", "Interpretation": "Virtual machine (VMware)"}}]},
}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(RESULTS, is_admin=False, elapsed={"processes": 12.3, "cpu": 2.0, "memory": 1.0, "video": 0.5})

    def test_attention_items_use_real_section_labels(self):
        items = {item["Item"]: item for item in self.data["attention"]}
        self.assertEqual(items["Pending reboot"]["Severity"], "Warning")
        self.assertEqual(items["UAC disabled"]["Severity"], "Warning")
        self.assertIn("C: (8.0 GB, 8.0 %)", items["Low disk space"]["Detail"])
        self.assertIn("Free % below 10%", items["Low disk space"]["Detail"])
        self.assertIn("Free space below 10 GB", items["Low disk space"]["Detail"])
        self.assertIn("1 device", items["Problem devices"]["Detail"])
        self.assertIn("Unknown device", items["Problem devices"]["Detail"])
        self.assertIn("Enabled", items["USB selective suspend"]["Detail"])
        self.assertEqual(items["Camera Frame Server shared mode"]["Severity"], "Info")
        self.assertEqual(items["Camera or microphone access denied"]["Detail"], "Camera (user)")
        self.assertEqual(items["Sentinel LDK License Manager not running"]["Severity"], "Warning")
        self.assertIn("Ethernet", items["Jumbo frames disabled on GigE adapters"]["Detail"])
        self.assertEqual(items["Report ran without administrator rights"]["Severity"], "Info")
        self.assertEqual(items["Performance counters unavailable"]["Severity"], "Info")
        self.assertIn("VMware", items["Running inside a virtual machine"]["Detail"])

    def test_specifications_collection_and_inventories(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Manufacturer"], "Dell Inc.")
        self.assertEqual(rows["Operating System"], "Windows 11, 24H2")
        self.assertEqual(rows["Processor"], "i7-12700")
        self.assertEqual(rows["Memory"], "32.0 GB")
        self.assertEqual(rows["Video"], "RTX 3060")
        self.assertEqual(rows["System Drive Free"], "8.0 GB (8.0 %)")
        self.assertEqual(rows["Cameras"], ["Basler ace acA1920"])
        self.assertEqual(rows["HASP / Sentinel Dongles"], "SafeNet Inc. Sentinel HASP Key")
        self.assertEqual(rows["GigE Adapters"], "Ethernet")
        self.assertEqual(rows["Elapsed Total"], "15.8 s")
        self.assertEqual(rows["Slowest Sections"], "processes (12.3 s), cpu (2.0 s), memory (1.0 s)")
        self.assertEqual(rows["Sections Timed"], 4)
        self.assertEqual([row["Name"] for row in self.data["software"]], ["EthoVision XT 19"])
        self.assertEqual([row["Name"] for row in self.data["runtimes"]], ["Microsoft Visual C++ 2015-2022 Redistributable (x64)"])
        self.assertEqual(self.data["drivers"][0]["Device"], "Basler pylon GigE Filter")
        self.assertEqual(self.data["codecs"][0]["Name"], "Noldus Resizer Filter")
        self.assertEqual(self.data["environment"][0]["Name"], "GENICAM_GENTL64_PATH")

    def test_all_clear_when_nothing_is_wrong(self):
        data = mod.build({}, is_admin=True, elapsed={})
        self.assertEqual(data["attention"], [])
        self.assertIn('<p class="ok">No items need attention.</p>', mod.render(data, support.render_ctx()))

    def test_missing_sensor_counter_values_raise_performance_info(self):
        results = {
            "memory": {"groups": [{"title": "Operating System View", "rows": {"Live Source": "Performance counters"}}]},
            "sensors": {"groups": [{"title": "Live Sample (1 s)", "rows": {
                "CPU Utility": "", "Memory Committed": "", "Memory Available": "",
            }}]},
        }
        items = {item["Item"]: item for item in mod.build(results, is_admin=True, elapsed={})["attention"]}
        self.assertEqual(items["Performance counters unavailable"]["Severity"], "Info")

    def test_low_disk_rule_is_local_fixed_only_and_reports_trigger(self):
        cases = [
            (
                "percentage threshold",
                {
                    "Drive": "C:", "Type": "Local Fixed Disk", "Total": "2 TB",
                    "Free": "100 GB", "Free %": "5 %",
                },
                True,
                "Free % below 10%",
            ),
            (
                "absolute threshold",
                {
                    "Drive": "C:", "Type": "Fixed", "Total": "20 GB",
                    "Free": "8 GB", "Free %": "40 %",
                },
                True,
                "Free space below 10 GB",
            ),
            (
                "healthy local disk",
                {"Drive": "C:", "Type": "Local Disk", "Free": "50 GB", "Free %": "12 %"},
                False,
                None,
            ),
            (
                "network disk",
                {"Drive": "Z:", "Type": "Network", "Free": "1 GB", "Free %": "1 %"},
                False,
                None,
            ),
        ]
        for name, row, expected, threshold in cases:
            with self.subTest(name=name):
                attention = mod.build(
                    {"logical_disks": {"rows": [row]}}, is_admin=True, elapsed={}
                )["attention"]
                low_disk = next(
                    (item for item in attention if item["Item"] == "Low disk space"), None
                )
                self.assertEqual(low_disk is not None, expected)
                if threshold:
                    self.assertIn(threshold, low_disk["Detail"])

    def test_each_attention_rule_has_a_negative_case(self):
        cases = [
            (
                "Pending reboot",
                {"operating_system": {"groups": [{"title": "Boot", "rows": {"Pending Reboot": "No"}}]}},
                True,
            ),
            (
                "UAC disabled",
                {"security": {"groups": [{"title": "Policies", "rows": {"UAC Enabled": "Yes"}}]}},
                True,
            ),
            (
                "Low disk space",
                {"logical_disks": {"rows": [
                    {"Drive": "C:", "Type": "Fixed", "Free": "50 GB", "Free %": "12 %"}
                ]}},
                True,
            ),
            ("Problem devices", {"devices": {"problems": []}}, True),
            (
                "USB selective suspend",
                {"usb": {"groups": [{"title": "Summary", "rows": {
                    "Selective Suspend (AC)": "Disabled",
                    "Selective Suspend (DC)": "Disabled",
                }}]}},
                True,
            ),
            (
                "Camera Frame Server shared mode",
                {"cameras": {"groups": [{"title": "Windows Camera Frame Server", "rows": {
                    "Frame Server Mode": "Disabled (exclusive camera access for legacy applications)"
                }}]}},
                True,
            ),
            (
                "Camera or microphone access denied",
                {"cameras": {"groups": [{"title": "Camera and Microphone Consent", "rows": {
                    "Camera Access (user)": "Allow",
                    "Microphone Access (user)": "Allow",
                }}]}},
                True,
            ),
            (
                "Sentinel LDK License Manager not running",
                {"services": {"rows": [{"Name": "hasplms", "State": "Running"}]}},
                True,
            ),
            (
                "Jumbo frames disabled on GigE adapters",
                {"network_adapters": {"gige": [{"Adapter": "Ethernet", "Jumbo Packet": "9014 Bytes"}]}},
                True,
            ),
            ("Report ran without administrator rights", {}, True),
            (
                "Performance counters unavailable",
                {
                    "memory": {"groups": [{"title": "Operating System View", "rows": {
                        "Live Source": "Performance counters"
                    }}]},
                    "sensors": {"groups": [{"title": "Live Sample (1 s)", "rows": {
                        "CPU Utility": "4 %",
                        "Memory Committed": "8 GB",
                        "Memory Available": "24 GB",
                    }}]},
                },
                True,
            ),
            (
                "Running inside a virtual machine",
                {"virtual_machine": {"groups": [{"title": "Detection", "rows": {
                    "Running Inside a VM": "No"
                }}]}},
                True,
            ),
        ]
        for item, results, is_admin in cases:
            with self.subTest(item=item):
                attention_items = {
                    value["Item"] for value in mod.build(
                        copy.deepcopy(results), is_admin=is_admin, elapsed={}
                    )["attention"]
                }
                self.assertNotIn(item, attention_items)

    def test_render_uses_severity_classes(self):
        html = mod.render(self.data, support.render_ctx())
        self.assertIn('class="warn"', html)
        self.assertIn('class="bad"', mod._attention_table([
            {"Severity": "Error", "Item": "Collection failure", "Detail": "Failed"}
        ]))
        self.assertIn("<h3>Needs attention</h3>", html)
        self.assertIn("<h3>Noldus software</h3>", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_results(self):
        results = {key: {"data": value, "notes": []} for key, value in RESULTS.items()}
        _data, html, ctx = support.collect_and_render(mod.SECTION, results=results)
        self.assertEqual(ctx.notes, [])
        self.assertIn("<h3>Needs attention</h3>", html)

    def test_real_dependency_fixtures_feed_summary(self):
        results = {}
        collected = set()

        def collect_dependency(key):
            if key in collected:
                return
            section = registry.by_key(key)
            self.assertIsNotNone(section, key)
            for dependency_key in section.after:
                collect_dependency(dependency_key)
            data, _html, _ctx = support.collect_and_render(section, results=results, root=support.FIXTURES)
            results[key] = {"data": data, "notes": []}
            collected.add(key)

        for key in mod.SECTION.after:
            collect_dependency(key)
        data, html, ctx = support.collect_and_render(mod.SECTION, results=results, root=support.FIXTURES)

        self.assertEqual(ctx.notes, [])
        self.assertIn("<h3>Needs attention</h3>", html)
        specs = mod.flatten(data)
        for label in ("Operating System", "Processor", "Memory", "Video"):
            self.assertTrue(specs[label], label)
        self.assertIn("HD Pro Webcam C920", specs["Cameras"])
        self.assertIn("Sentinel", specs["HASP / Sentinel Dongles"])
        attention = {item["Item"]: item["Detail"] for item in data["attention"]}
        self.assertIn("Pending reboot", attention)
        self.assertIn("Camera Frame Server shared mode", attention)
        self.assertIn("Jumbo frames disabled on GigE adapters", attention)
        self.assertIn("Performance counters unavailable", attention)
        self.assertIn("Report ran without administrator rights", attention)
        self.assertIn("USB selective suspend", attention)
        self.assertIn("D:", attention["Low disk space"])
        self.assertIn("0.3 %", attention["Low disk space"])

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
