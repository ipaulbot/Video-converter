import unittest

from pc_report.sections import video as mod
from tests.pc_report import support

CTRL = [{"Name": "NVIDIA GeForce RTX 3060", "Status": "OK", "AdapterRAM": 4293918720, "AdapterDACType": "Integrated RAMDAC",
         "VideoProcessor": "NVIDIA GeForce RTX 3060", "VideoArchitecture": 5, "PNPDeviceID": "PCI\\VEN_10DE&DEV_2503&SUBSYS_00000001&REV_A1\\4",
         "CurrentHorizontalResolution": 2560, "CurrentVerticalResolution": 1440, "CurrentRefreshRate": 60, "CurrentBitsPerPixel": 32,
         "CurrentNumberOfColors": 4294967296, "DriverVersion": "32.0.15.6094", "DriverDate": "20240801000000.000000-000",
         "InfFilename": "oem12.inf", "InfSection": "Section123", "VideoModeDescription": "2560 x 1440 x 4294967296 colors",
         "Availability": 3, "MaxRefreshRate": 165, "MinRefreshRate": 24, "ConfigManagerErrorCode": 0, "AdapterCompatibility": "NVIDIA"}]
REG = [{"Key": "0000", "DriverDesc": "NVIDIA GeForce RTX 3060", "MatchingDeviceId": "PCI\\VEN_10DE&DEV_2503&SUBSYS_00000001",
        "qwMemorySize": 12884901888, "DriverVersion": "32.0.15.6094", "DriverDate": "8-1-2024", "ProviderName": "NVIDIA"}]
DX = {"SystemInformation": {"DirectXVersion": "DirectX 12"},
      "DisplayDevices": {"DisplayDevice": {"CardName": "NVIDIA GeForce RTX 3060", "Manufacturer": "NVIDIA", "ChipType": "NVIDIA GeForce RTX 3060",
                                           "DACType": "Integrated RAMDAC", "DeviceType": "Full Device (POST)", "DisplayMemory": "20387 MB",
                                           "DedicatedMemory": "12100 MB", "SharedMemory": "8287 MB", "CurrentMode": "2560 x 1440 (32 bit) (60Hz)",
                                           "HDR": "Not Supported", "DriverName": "nvldumdx.dll", "DriverFileVersion": "32.00.0015.6094",
                                           "DriverVersion": "32.0.15.6094", "DDIVersion": "12", "FeatureLevels": "12_1,12_0,11_1,11_0",
                                           "DriverModel": "WDDM 3.1", "DriverDate": "8/1/2024 02:00:00", "VendorID": "0x10DE", "DeviceID": "0x2503",
                                           "SubSysID": "0x00000001", "RevisionID": "0x00A1", "MonitorName": "Generic PnP Monitor",
                                           "MonitorModel": "DELL U2722D", "OutputType": "Displayport External", "NativeMode": "2560 x 1440(p) (59.951Hz)"}}}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(CTRL, REG, DX)
        self.rows = {}
        for g in self.data["adapters"][0]["groups"]:
            self.rows.update(g["rows"])

    def test_memory_is_corrected_from_registry(self):
        self.assertEqual(self.rows["Adapter RAM"], "12.0 GB")
        self.assertEqual(self.rows["Adapter RAM (WMI, 32-bit capped)"], "4.0 GB")
        self.assertEqual(self.rows["Dedicated Memory (DirectX)"], "12100 MB")
        self.assertEqual(self.rows["Shared Memory (DirectX)"], "8287 MB")

    def test_mode_and_driver(self):
        self.assertEqual(self.rows["Current Mode"], "2560 x 1440, 32 bit, 60 Hz")
        self.assertEqual(self.rows["Refresh Rate Range"], "24 - 165 Hz")
        self.assertEqual(self.rows["Driver Model"], "WDDM 3.1")
        self.assertEqual(self.rows["Feature Levels"], "12_1,12_0,11_1,11_0")
        self.assertEqual(self.rows["Driver Date"], "2024-08-01")
        self.assertEqual(self.rows["PCI IDs"], "VEN 10DE / DEV 2503 / SUBSYS 00000001 / REV A1")
        self.assertEqual(self.rows["Architecture"], "VGA")

    def test_summary_and_names(self):
        self.assertEqual(dict(self.data["groups"][0]["rows"])["DirectX Version"], "DirectX 12")
        self.assertEqual(mod.names(self.data), ["NVIDIA GeForce RTX 3060"])


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Adapter RAM</th>", html)
        self.assertIn("<th>DirectX Version</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
