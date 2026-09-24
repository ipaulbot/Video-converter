import unittest

from pc_report.sections import bios as mod
from tests.pc_report import support

BIOS = {"Manufacturer": "Dell Inc.", "Name": "1.2.3", "Version": "DELL   - 1072009", "SMBIOSBIOSVersion": "1.2.3",
        "SMBIOSMajorVersion": 3, "SMBIOSMinorVersion": 4, "ReleaseDate": "20250110000000.000000+000",
        "BiosCharacteristics": [4, 7, 9, 11, 12, 15, 16, 19, 26, 27, 28, 29, 32, 33, 40], "EmbeddedControllerMajorVersion": 1,
        "EmbeddedControllerMinorVersion": 9, "SystemBiosMajorVersion": 1, "SystemBiosMinorVersion": 2,
        "SerialNumber": "ABC123", "PrimaryBIOS": True, "Status": "OK", "CurrentLanguage": "en|US|iso8859-1"}
ACPI = [{"Table": "DSDT"}, {"Table": "FACP"}, {"Table": "SSDT"}]
BOOT = {"FirmwareType": "UEFI", "SecureBoot": 1}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        rows = mod.flatten(mod.build(BIOS, ACPI, BOOT))
        self.assertEqual(rows["Vendor"], "Dell Inc.")
        self.assertEqual(rows["SMBIOS Version"], "3.4")
        self.assertEqual(rows["Release Date"], "2025-01-10")
        self.assertEqual(rows["Embedded Controller Version"], "1.9")
        self.assertEqual(rows["Firmware Type"], "UEFI")
        self.assertEqual(rows["Secure Boot"], "Yes")
        self.assertEqual(rows["ACPI Tables"], "DSDT, FACP, SSDT")
        self.assertIn("Supports PCI", rows["Characteristics"])
        self.assertIn("Reserved (40)", rows["Characteristics"])


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>SMBIOS Version</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
