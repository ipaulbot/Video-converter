import unittest

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


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Free %</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
