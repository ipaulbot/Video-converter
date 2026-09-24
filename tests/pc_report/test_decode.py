import unittest

from pc_report import decode as D


class DecodeTests(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(D.to_int("3"), 3)
        self.assertEqual(D.to_int(4.0), 4)
        self.assertIsNone(D.to_int("x"))
        self.assertEqual(D.to_int(None, 0), 0)

    def test_lookup_falls_back_to_other_with_code(self):
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, 3), "Desktop")
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, 999), "Other (999)")
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, None), "")
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, [3, 10]), "Desktop, Notebook")

    def test_memory_and_form_factor(self):
        self.assertEqual(D.lookup(D.MEMORY_TYPES, 34), "DDR5")
        self.assertEqual(D.lookup(D.MEMORY_TYPES, 26), "DDR4")
        self.assertEqual(D.lookup(D.FORM_FACTORS, 8), "DIMM")
        self.assertEqual(D.lookup(D.FORM_FACTORS, 12), "SODIMM")

    def test_pnp_error_codes(self):
        self.assertEqual(D.lookup(D.PNP_ERROR_CODES, 0), "Working properly")
        self.assertEqual(D.lookup(D.PNP_ERROR_CODES, 28), "Drivers not installed")
        self.assertEqual(D.lookup(D.PNP_ERROR_CODES, 22), "Disabled")

    def test_bios_characteristics(self):
        text = D.bios_characteristics([7, 9, 32, 40])
        self.assertIn("Supports PCI", text)
        self.assertIn("Supports Plug and Play", text)
        self.assertIn("Supports ACPI", text)
        self.assertIn("Reserved (40)", text)

    def test_license_status_and_sku(self):
        self.assertEqual(D.lookup(D.LICENSE_STATUS, 1), "Licensed")
        self.assertEqual(D.os_sku(125), "Enterprise LTSC")
        self.assertEqual(D.os_sku(48), "Professional")

    def test_dotnet_release(self):
        self.assertEqual(D.dotnet_release(533320), "4.8.1")
        self.assertEqual(D.dotnet_release(528372), "4.8")
        self.assertEqual(D.dotnet_release(None), "")

    def test_au_options(self):
        self.assertEqual(D.au_options(1, None), "Disabled by policy")
        self.assertEqual(D.au_options(None, 4), "Automatically download and schedule installation")
        self.assertEqual(D.au_options(None, None), "Default (managed by Windows)")

    def test_security_center_state(self):
        # 0x061100 = enabled, up to date (Defender's usual value)
        self.assertEqual(D.security_center_state(397568), ("Enabled", "Up to date"))
        # 0x000000 = disabled
        self.assertEqual(D.security_center_state(0), ("Disabled", "Up to date"))
        self.assertEqual(D.security_center_state(0x1010), ("Enabled", "Out of date"))

    def test_accessibility_flags(self):
        decoded = D.accessibility_flags(0x1E)
        self.assertEqual(decoded["Enabled"], "No")
        self.assertEqual(decoded["Available"], "Yes")
        self.assertEqual(decoded["Hotkey activation enabled"], "Yes")

    def test_os_language(self):
        self.assertEqual(D.os_language(1033), "English (United States)")
        self.assertEqual(D.os_language("1043"), "Dutch (Netherlands)")
        self.assertEqual(D.os_language(9999), "LCID 9999")

    def test_pci_vendor(self):
        self.assertEqual(D.pci_vendor("8086"), "Intel Corporation")
        self.assertEqual(D.pci_vendor("10DE"), "NVIDIA Corporation")
        self.assertEqual(D.pci_vendor("FFFF"), "Vendor FFFF")
