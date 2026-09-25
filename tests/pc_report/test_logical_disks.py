import unittest

from pc_report.privacy import redact_payload
from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import logical_disks as mod
from tests.pc_report import support

LD = [{"DeviceID": "C:", "VolumeName": "Windows", "DriveType": 3, "FileSystem": "NTFS", "Size": 998000000000, "FreeSpace": 49000000000,
       "VolumeSerialNumber": "1A2B3C4D", "Compressed": False, "ProviderName": None, "Description": "Local Fixed Disk", "MediaType": 12},
      {"DeviceID": "Z:", "VolumeName": "share", "DriveType": 4, "FileSystem": "NTFS", "Size": 2000000000000, "FreeSpace": 1000000000000,
       "VolumeSerialNumber": "0000", "Compressed": False, "ProviderName": "\\\\server\\share", "Description": "Network Connection", "MediaType": 0}]
VOL = [{"DriveLetter": "C", "FileSystemLabel": "Windows", "FileSystem": "NTFS", "HealthStatus": "Healthy", "OperationalStatus": "OK",
        "AllocationUnitSize": 4096, "Size": 998000000000, "SizeRemaining": 49000000000, "DriveType": "Fixed"}]
PARTS = [{"DriveLetter": "C", "DiskNumber": 0, "PartitionNumber": 3, "BusType": "NVMe", "DiskModel": "Samsung SSD 980 PRO 1TB"}]
BL = [{"MountPoint": "C:", "ProtectionStatus": 1, "VolumeStatus": 1, "EncryptionPercentage": 100}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(LD, VOL, PARTS, BL)
        c = data["rows"][0]
        self.assertEqual(c["Drive"], "C:")
        self.assertEqual(c["Type"], "Local disk")
        self.assertEqual(c["Total"], "929.5 GB")
        self.assertEqual(c["Free %"], "⚠ 4.9 %")
        self.assertEqual(c["Allocation Unit"], "4096 B")
        self.assertEqual(c["Bus Type"], "NVMe")
        self.assertEqual(c["Disk"], "0 (Samsung SSD 980 PRO 1TB)")
        self.assertEqual(c["BitLocker"], "On")
        z = data["rows"][1]
        self.assertEqual(z["Type"], "Network drive")
        self.assertEqual(z["Network Path (host name)"], "\\\\server\\share")
        self.assertEqual(z["Free %"], "50.0 %")

    def test_requires_admin_bitlocker(self):
        data = mod.build(LD, VOL, PARTS, REQUIRES_ADMIN)
        self.assertEqual(data["rows"][0]["BitLocker"], REQUIRES_ADMIN)
        self.assertIn("Requires administrator", mod.render(data, support.render_ctx()))

    def test_summary(self):
        rows = dict(mod.build(LD, VOL, PARTS, BL)["groups"][0]["rows"])
        self.assertEqual(rows["Volumes"], 2)
        self.assertEqual(rows["Low Space (<10 %)"], "C:")

    def test_inconsistent_capacity_leaves_used_and_free_percent_blank(self):
        data = mod.build([{"DeviceID": "X:", "Size": 100, "FreeSpace": 150}], [], [], [])
        row = data["rows"][0]
        self.assertEqual(row["Used"], "")
        self.assertEqual(row["Free %"], "")


class PrivacyTests(unittest.TestCase):
    def _html(self, logical, volumes=()):
        data = mod.build(logical, volumes, PARTS, BL)
        return mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

    def test_a_personal_volume_label_is_masked_wherever_it_comes_from(self):
        logical = [{**LD[0], "DeviceID": "E:", "VolumeName": "Jan's iPhone", "DriveType": 2}]
        volumes = [{"DriveLetter": "E", "FileSystemLabel": "Jan's iPhone"}]

        for html in (self._html(logical), self._html([{**logical[0], "VolumeName": None}], volumes)):
            self.assertNotIn("Jan", html)
            self.assertIn("E:", html)

    def test_ordinary_volume_labels_stay_readable(self):
        logical = [{**LD[0], "VolumeName": "OSDisk"}, {**LD[0], "DeviceID": "D:", "VolumeName": "Data"}]

        html = self._html(logical)

        self.assertIn("OSDisk", html)
        self.assertIn("Data", html)

    def test_system_summary_consumes_the_same_redacted_label(self):
        from pc_report.sections import system_summary

        disks = mod.build([{**LD[0], "VolumeName": "Jan's iPhone"}], VOL, PARTS, BL)
        data = system_summary.build({}, {}, {}, {}, {}, {}, "", {"logical_disks": disks})
        html = system_summary.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

        self.assertNotIn("Jan", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Free %</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
