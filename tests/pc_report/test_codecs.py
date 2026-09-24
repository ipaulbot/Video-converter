import re
import tempfile
import unittest
from pathlib import Path

from pc_report.sections import codecs as mod
from tests.pc_report import support

DS = [{"Category": "DirectShow Filters", "Name": "Noldus Resizer Filter", "CLSID": "{AAAA}", "File": "C:\\Program Files\\Common Files\\Noldus\\Resizer.ax",
       "Version": "1.2.3.4", "Company": "Noldus", "Merit": 2097152, "Architecture": "x64"},
      {"Category": "Video Compressors (Legacy)", "Name": "Cinepak", "CLSID": "{BBBB}", "File": "", "Version": "", "Company": "", "Merit": None, "Architecture": "x86"}]
D32 = [{"Name": "vidc.cvid", "File": "iccvid.dll", "Version": "10.0.1", "Company": "Microsoft", "Architecture": "x64"},
       {"Name": "msacm.l3acm", "File": "l3codeca.acm", "Version": "1.9", "Company": "Fraunhofer", "Architecture": "x86"}]
MF = [{"Category": "Media Foundation Transforms", "Name": "H264 Encoder MFT", "CLSID": "{CCCC}", "File": "mfh264enc.dll",
       "Version": "10.0", "Company": "Microsoft", "Architecture": "x64"}]


class BuildTests(unittest.TestCase):
    def test_categories_and_merit(self):
        data = mod.build(DS, D32, MF)
        self.assertIn("DirectShow Filters", data["categories"])
        self.assertIn("Video Compressors (Legacy)", data["categories"])
        self.assertIn("Video for Windows (VCM)", data["categories"])
        self.assertIn("Audio Compression Manager (ACM)", data["categories"])
        self.assertIn("Media Foundation Transforms", data["categories"])
        resizer = data["categories"]["DirectShow Filters"][0]
        self.assertEqual(resizer["Merit"], "0x200000 (Do not use)")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["DirectShow Filters"], 1)
        self.assertEqual(rows["Total Entries"], 5)

    def test_merit_names(self):
        self.assertEqual(mod.merit(0x800000), "0x800000 (Preferred)")
        self.assertEqual(mod.merit(0x600000), "0x600000 (Normal)")
        self.assertEqual(mod.merit(0x200000), "0x200000 (Do not use)")
        self.assertEqual(mod.merit(0x100050), "0x100050 (Hardware compressor)")
        self.assertEqual(mod.merit(0x100000), "0x100000 (Software compressor)")
        self.assertEqual(mod.merit(0x200001), "0x200001")
        self.assertEqual(mod.merit(None), "")

    def test_build_keeps_two_media_foundation_transforms(self):
        transforms = [
            {
                "Category": "Video Decoder",
                "Name": "H264 Decoder MFT",
                "CLSID": "11111111-1111-1111-1111-111111111111",
                "File": "decoder.dll",
                "Version": "1.0",
                "Company": "Example",
                "Architecture": "x64",
            },
            {
                "Category": "Audio Encoder",
                "Name": "AAC Encoder MFT",
                "CLSID": "{22222222-2222-2222-2222-222222222222}",
                "File": "",
                "Version": "",
                "Company": "",
                "Architecture": "x86",
            },
        ]

        rows = mod.build([], [], transforms)["categories"]["Media Foundation Transforms"]

        self.assertEqual([row["Name"] for row in rows], ["AAC Encoder MFT", "H264 Decoder MFT"])
        self.assertEqual({row["Category"] for row in rows}, {"Audio Encoder", "Video Decoder"})

    def test_drivers32_keeps_only_vcm_and_acm(self):
        drivers = [
            {"Name": "vidc.XVID", "Architecture": "x86"},
            {"Name": "msacm.l3acm", "Architecture": "x64"},
            {"Name": "midi1", "Architecture": "x64"},
            {"Name": "wave", "Architecture": "x64"},
        ]

        categories = mod.build([], drivers, [])["categories"]

        self.assertEqual(set(categories), {"Video for Windows (VCM)", "Audio Compression Manager (ACM)"})
        self.assertEqual(categories["Video for Windows (VCM)"][0]["Name"], "vidc.XVID")
        self.assertEqual(categories["Audio Compression Manager (ACM)"][0]["Name"], "msacm.l3acm")


class ScriptTests(unittest.TestCase):
    def test_media_foundation_accepts_bare_and_braced_guids(self):
        self.assertIn("-match '^\\{?[0-9A-Fa-f-]{36}\\}?$'", mod.MF_SCRIPT)

    def test_directshow_script_queries_every_declared_category(self):
        cats_block = mod.DIRECTSHOW_SCRIPT.split("$fileCache", 1)[0]
        script_clsids = set(re.findall(r"'(\{[0-9A-Fa-f-]{36}\})'\s*=", cats_block))
        self.assertEqual(script_clsids, set(mod.DS_CATEGORIES))
        self.assertEqual(
            mod.DS_CATEGORIES["{33D9A760-90C8-11D0-BD43-00A0C911CE86}"],
            "Video Compressors",
        )
        self.assertEqual(
            mod.DS_CATEGORIES["{2721AE20-7E70-11D0-A5D6-28DB04C10000}"],
            "Video Compressors (Legacy)",
        )
        self.assertIn("{2721AE20-7E70-11D0-A5D6-28DB04C10000}", mod.DIRECTSHOW_SCRIPT)


class FixtureTests(unittest.TestCase):
    def test_collect_notes_empty_media_foundation_result(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture_dir = Path(directory) / mod.SECTION.key
            fixture_dir.mkdir()
            (fixture_dir / "directshow.json").write_text("[]", encoding="utf-8")
            (fixture_dir / "drivers32.json").write_text("[]", encoding="utf-8")
            (fixture_dir / "media_foundation.json").write_text("null", encoding="utf-8")
            ctx = support.FixtureSectionContext(mod.SECTION, root=Path(directory))

            mod.collect(ctx)

        self.assertIn("media foundation: no transforms enumerated", ctx.notes)

    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>CLSID</th>", html)
        self.assertIn("Video Compressors", html)
        self.assertIn("Media Foundation Transforms", html)
        self.assertRegex(html, r"Media Foundation Transforms \([1-9][0-9]*\).*?<tbody><tr>")

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
