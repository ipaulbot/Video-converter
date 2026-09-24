import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import licenses as mod
from tests.pc_report import support

RAW = {"ProductId": "00329-00000-00003-AA123", "OA3xOriginalProductKey": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
       "OA3xOriginalProductKeyDescription": "Win 10 Pro OEM", "KeyManagementServiceMachine": "kms.example.local",
       "Products": [{"Name": "Windows(R), Enterprise edition", "Description": "VOLUME_KMSCLIENT channel",
                     "LicenseStatus": 1, "PartialProductKey": "ABCDE", "ProductKeyChannel": "Volume:GVLK",
                     "LicenseFamily": "Enterprise", "GracePeriodRemaining": 100}]}


class BuildTests(unittest.TestCase):
    def test_summary_and_products(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Windows Product ID"], "00329-00000-00003-AA123")
        self.assertEqual(rows["OEM Original Product Key"], "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY")
        self.assertEqual(rows["KMS Host Name"], "kms.example.local")
        self.assertEqual(data["products"][0]["Status"], "Licensed")
        self.assertEqual(data["products"][0]["Partial Product Key"], "ABCDE")

    def test_render_masks_keys(self):
        raw = {
            "ProductId": "00330-80000-00000-AA111",
            "OA3xOriginalProductKey": "",
            "OA3xOriginalProductKeyDescription": "",
            "KeyManagementServiceMachine": "",
            "Products": [
                {
                    "Name": "Windows Test",
                    "Description": "",
                    "LicenseStatus": 1,
                    "PartialProductKey": "ABCDE",
                    "ProductKeyChannel": "",
                    "LicenseFamily": "",
                    "GracePeriodRemaining": 0,
                }
            ],
        }
        data = mod.build(raw)
        html = mod.render(redact_payload(data, {"redact": True}), support.render_ctx())
        self.assertIn("<th>Partial Product Key</th>", html)
        self.assertIn("<th>Windows Product ID</th>", html)
        self.assertNotIn("ABCDE", html)
        self.assertNotIn("00330-80000-00000-AA111", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Windows Product ID</th>", html)
        self.assertIn("<th>Product</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
