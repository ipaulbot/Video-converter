import unittest

from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import storage_devices as mod
from tests.pc_report import support

PHYS = [{"DeviceId": "0", "FriendlyName": "Samsung SSD 980 PRO 1TB", "Model": "Samsung SSD 980 PRO 1TB", "Manufacturer": "", "SerialNumber": "S5GX",
         "MediaType": "SSD", "BusType": "NVMe", "Size": 1000204886016, "HealthStatus": "Healthy", "OperationalStatus": "OK",
         "FirmwareVersion": "5B2QGXA7", "SpindleSpeed": 0, "PhysicalSectorSize": 512, "LogicalSectorSize": 512, "Usage": "Auto-Select", "UniqueId": "eui.1"}]
DISKS = [{"Number": 0, "FriendlyName": "Samsung SSD 980 PRO 1TB", "SerialNumber": "S5GX", "PartitionStyle": "GPT", "IsBoot": True, "IsSystem": True,
          "IsReadOnly": False, "IsOffline": False, "NumberOfPartitions": 4, "Size": 1000204886016, "AllocatedSize": 1000204886016,
          "Location": "PCI Slot 4 : Bus 3 : Device 0 : Function 0 : Adapter 0 : Port 0", "Guid": "{g}", "OperationalStatus": "Online"}]
PARTS = [{"DiskNumber": 0, "PartitionNumber": 3, "DriveLetter": "C", "Size": 998000000000, "Type": "Basic", "GptType": "{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}",
          "IsActive": False, "IsBoot": True, "IsSystem": False, "IsHidden": False, "Offset": 123},
         {"DiskNumber": 0, "PartitionNumber": 1, "DriveLetter": None, "Size": 104857600, "Type": "System", "GptType": "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}",
          "IsActive": False, "IsBoot": False, "IsSystem": True, "IsHidden": False, "Offset": 1}]
SMART = [{"InstanceName": "SCSI\\Disk&Ven_NVMe&Prod_Samsung_SSD_980\\5&1_0", "PredictFailure": False, "Reason": 0}]
REL = [{"DeviceId": "0", "Temperature": 41, "TemperatureMax": 62, "PowerOnHours": 5121, "Wear": 2, "ReadErrorsTotal": 0, "WriteErrorsTotal": 0,
        "ReadErrorsUncorrected": 0, "WriteErrorsUncorrected": 0, "StartStopCycleCount": 300}]
OPT = [{"Name": "HL-DT-ST DVDRAM", "Drive": "E:", "MediaType": "DVD Writer", "Manufacturer": "(Standard CD-ROM drives)", "Status": "OK", "MediaLoaded": False}]


class BuildTests(unittest.TestCase):
    def test_disk_rows(self):
        data = mod.build(PHYS, DISKS, PARTS, SMART, REL, OPT)
        d = data["disks"][0]
        rows = {}
        for g in d["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["Size"], "931.5 GB")
        self.assertEqual(rows["Media Type"], "SSD")
        self.assertEqual(rows["Bus Type"], "NVMe")
        self.assertEqual(rows["Partition Style"], "GPT")
        self.assertEqual(rows["Boot / System Disk"], "Yes / Yes")
        self.assertEqual(rows["Sector Size (logical / physical)"], "512 / 512")
        self.assertEqual(rows["SMART Predict Failure"], "No")
        self.assertEqual(rows["Temperature"], "41 °C (max 62 °C)")
        self.assertEqual(rows["Power-on Hours"], "5121 h (213 days)")
        self.assertEqual(rows["Wear"], "2 %")
        parts = d["partitions"]
        self.assertEqual(parts[0]["Partition"], 1)
        self.assertEqual(parts[0]["GPT Type"], "EFI System")
        self.assertEqual(parts[1]["Drive"], "C:")
        self.assertEqual(parts[1]["GPT Type"], "Basic Data")

    def test_requires_admin_reliability(self):
        data = mod.build(PHYS, DISKS, PARTS, SMART, REQUIRES_ADMIN, OPT)
        rows = {}
        for g in data["disks"][0]["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["Reliability Counters"], REQUIRES_ADMIN)

    def test_optical(self):
        data = mod.build([], [], [], [], [], OPT)
        self.assertEqual(data["optical"][0]["Drive"], "E:")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Bus Type</th>", html)
        self.assertIn("<h3>Optical drives</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
