import os
import tempfile
import unittest

from pc_report.collectors import (
    filter_nvc_related_items,
    normalize_logical_disk_rows,
    normalize_nvc_program_row,
    scan_codec_files,
    scan_nvc_filter_files,
)


class NvcCollectorHelperTests(unittest.TestCase):
    def test_matches_noldus_dependency_package(self):
        row = {"Name": "Noldus - LeadTools - X64 Package - 21", "Version": "21.0.16.0"}

        self.assertEqual(filter_nvc_related_items([row]), [row])

    def test_matches_basler_and_pylon_dependencies(self):
        rows = [
            {"Name": "pylon Runtime 8.0.0.16021"},
            {"Name": "Basler pylon GEV Driver"},
            {"Name": "Unrelated Tool"},
        ]

        self.assertEqual(filter_nvc_related_items(rows), rows[:2])

    def test_matches_genicam_environment_style_values(self):
        row = {"Name": "GENICAM_GENTL64_PATH", "Value": r"C:\Program Files\Basler\pylon 8\Runtime\x64"}

        self.assertEqual(filter_nvc_related_items([row]), [row])

    def test_matches_sentinel_hasp_driver(self):
        row = {"DeviceName": "Sentinel HASP License Manager", "Manufacturer": "Thales"}

        self.assertEqual(filter_nvc_related_items([row]), [row])

    def test_does_not_match_windows_ipp_print_driver(self):
        row = {
            "DeviceName": "Microsoft IPP Class Driver",
            "DeviceID": r"SWD\IPP\00000000-0000-1000-8000-001823324BC7",
        }

        self.assertEqual(filter_nvc_related_items([row]), [])

    def test_does_not_match_hypervisor_for_viso(self):
        row = {"DeviceName": "Hypervisor/Virtual Machine Support Driver"}

        self.assertEqual(filter_nvc_related_items([row]), [])

    def test_normalizes_display_name_rows_to_name_rows(self):
        row = {
            "DisplayName": "EthoVision XT 19",
            "DisplayVersion": "19.0.1912",
            "Publisher": "Noldus",
            "InstallDate": "20260522",
        }

        self.assertEqual(
            normalize_nvc_program_row(row),
            {
                "Name": "EthoVision XT 19",
                "Version": "19.0.1912",
                "Publisher": "Noldus",
                "InstallDate": "20260522",
                "InstallLocation": "",
            },
        )

    def test_scan_nvc_filter_files_finds_ax_filters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            noldus_dir = os.path.join(temp_dir, "Noldus Shared")
            os.makedirs(noldus_dir)
            filter_path = os.path.join(noldus_dir, "NoldusSamplegrabberu.ax")
            open(filter_path, "w", encoding="utf-8").close()

            rows = scan_nvc_filter_files([temp_dir])

            self.assertEqual(rows[0]["Name"], "NoldusSamplegrabberu")
            self.assertEqual(rows[0]["File"], filter_path)

    def test_normalizes_get_volume_rows_to_logical_disk_shape(self):
        rows = normalize_logical_disk_rows(
            [
                {
                    "DriveLetter": "C",
                    "FileSystem": "NTFS",
                    "Size": 1000,
                    "SizeRemaining": 250,
                    "FileSystemLabel": "Windows",
                    "DriveType": "Fixed",
                }
            ]
        )

        self.assertEqual(
            rows,
            [
                {
                    "DeviceID": "C:",
                    "DriveType": "Fixed",
                    "FileSystem": "NTFS",
                    "Size": 1000,
                    "FreeSpace": 250,
                    "VolumeName": "Windows",
                }
            ],
        )

    def test_normalize_logical_disk_rows_skips_volumes_without_drive_letters(self):
        rows = normalize_logical_disk_rows([{"DriveLetter": "", "FileSystem": "NTFS"}])

        self.assertEqual(rows, [])

    def test_scan_codec_files_finds_legacy_codec_extensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            codec_path = os.path.join(temp_dir, "sample_codec.ax")
            open(codec_path, "w", encoding="utf-8").close()

            rows = scan_codec_files([temp_dir])

            self.assertEqual(rows[0]["Name"], "sample_codec")
            self.assertEqual(rows[0]["File"], codec_path)


if __name__ == "__main__":
    unittest.main()
