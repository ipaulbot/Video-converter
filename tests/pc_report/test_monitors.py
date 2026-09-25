import unittest

from pc_report.sections import monitors as mod
from tests.pc_report import support

WMI = [{"InstanceName": "DISPLAY\\DELA1C4\\5&1&0&UID4353_0", "Manufacturer": "DEL", "Model": "DELL U2722D", "Serial": "ABC123",
        "ProductCode": "A1C4", "Year": 2022, "Week": 12, "Active": True}]
PARAMS = [{"InstanceName": "DISPLAY\\DELA1C4\\5&1&0&UID4353_0", "MaxHorizontalImageSize": 60, "MaxVerticalImageSize": 34, "Active": True}]
SCREENS = [{"DeviceName": "\\\\.\\DISPLAY1", "Primary": True, "Width": 2560, "Height": 1440, "X": 0, "Y": 0, "BitsPerPixel": 32}]
DX = {"DisplayDevices": {"DisplayDevice": {"CardName": "GPU", "MonitorName": "Generic PnP Monitor", "MonitorModel": "DELL U2722D",
                                           "MonitorId": "DELA1C4", "NativeMode": "2560 x 1440(p) (59.951Hz)", "OutputType": "Displayport External",
                                           "CurrentMode": "2560 x 1440 (32 bit) (60Hz)"}}}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(WMI, PARAMS, SCREENS, DX)
        m = data["monitors"][0]
        self.assertEqual(m["Manufacturer"], "Dell")
        self.assertEqual(m["Model"], "DELL U2722D")
        self.assertEqual(m["Manufactured"], "2022, week 12")
        self.assertEqual(m["Diagonal"], '27.1" (60 x 34 cm)')
        self.assertEqual(m["Native Mode"], "2560 x 1440(p) (59.951Hz)")
        self.assertEqual(m["Output"], "Displayport External")
        self.assertEqual(data["screens"][0]["Resolution"], "2560 x 1440")
        self.assertEqual(data["screens"][0]["Primary"], "Yes")

    def test_pnp_vendor(self):
        self.assertEqual(mod.pnp_vendor("SAM"), "Samsung")
        self.assertEqual(mod.pnp_vendor("XYZ"), "XYZ")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Diagonal</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
