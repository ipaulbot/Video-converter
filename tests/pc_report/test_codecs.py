import unittest

from pc_report.sections import codecs as mod
from tests.pc_report import support

DS = [{"Category": "DirectShow Filters", "Name": "Noldus Resizer Filter", "CLSID": "{AAAA}", "File": "C:\\Program Files\\Common Files\\Noldus\\Resizer.ax",
       "Version": "1.2.3.4", "Company": "Noldus", "Merit": 2097152, "Architecture": "x64"},
      {"Category": "Video Compressors", "Name": "Cinepak", "CLSID": "{BBBB}", "File": "", "Version": "", "Company": "", "Merit": None, "Architecture": "x86"}]
D32 = [{"Name": "vidc.cvid", "File": "iccvid.dll", "Version": "10.0.1", "Company": "Microsoft", "Architecture": "x64"},
       {"Name": "msacm.l3acm", "File": "l3codeca.acm", "Version": "1.9", "Company": "Fraunhofer", "Architecture": "x86"}]
MF = [{"Category": "Media Foundation Transforms", "Name": "H264 Encoder MFT", "CLSID": "{CCCC}", "File": "mfh264enc.dll",
       "Version": "10.0", "Company": "Microsoft", "Architecture": "x64"}]


class BuildTests(unittest.TestCase):
    def test_categories_and_merit(self):
        data = mod.build(DS, D32, MF)
        self.assertIn("DirectShow Filters", data["categories"])
        self.assertIn("Video Compressors", data["categories"])
        self.assertIn("Video for Windows (VCM)", data["categories"])
        self.assertIn("Audio Compression Manager (ACM)", data["categories"])
        self.assertIn("Media Foundation Transforms", data["categories"])
        resizer = data["categories"]["DirectShow Filters"][0]
        self.assertEqual(resizer["Merit"], "0x200000 (Normal)")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["DirectShow Filters"], 1)
        self.assertEqual(rows["Total Entries"], 5)

    def test_merit_names(self):
        self.assertEqual(mod.merit(0x800000), "0x800000 (Preferred)")
        self.assertEqual(mod.merit(0x200001), "0x200001 (Normal+1)")
        self.assertEqual(mod.merit(None), "")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>CLSID</th>", html)
        self.assertIn("Video Compressors", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
