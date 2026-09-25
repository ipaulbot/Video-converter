import json
import os
import tempfile
import unittest

from conversion.recorder_settings import (
    default_recorder_settings,
    list_recorder_presets,
    load_recorder_settings,
    preset_file_path,
    safe_preset_name,
    save_recorder_settings,
)


class RecorderSettingsTests(unittest.TestCase):
    def test_default_recorder_settings_match_media_recorder_style_shape(self):
        settings = default_recorder_settings()

        self.assertEqual(settings["version"], 1)
        self.assertEqual(settings["output"]["mode"], "Separate videos")
        self.assertEqual(settings["output"]["base_name"], "Video")
        self.assertEqual(settings["preview"]["fps"], 20)
        self.assertEqual(settings["preview"]["width"], 480)
        self.assertEqual(settings["channels"], [])

    def test_save_and_load_recorder_settings_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "Current Settings.json")
            settings = default_recorder_settings()
            settings["output"].update({
                "folder": "C:\\Videos",
                "base_name": "Task",
                "encoding": "h264",
                "mode": "Combined grid",
            })
            settings["channels"] = [{
                "enabled": True,
                "video_name": "Video 1",
                "source_type": "rtsp_ip",
                "source": "rtsp://camera/stream",
                "audio_name": "Audio 1",
                "audio_device": "No Audio",
                "mute": False,
                "volume": "100",
                "frame_rate": "30.00",
                "resolution": "1920 x 1080",
            }]

            save_recorder_settings(path, settings)

            with open(path, encoding="utf-8") as handle:
                raw = json.load(handle)
            self.assertEqual(raw["output"]["base_name"], "Task")
            self.assertEqual(load_recorder_settings(path), settings)

    def test_load_missing_recorder_settings_returns_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_recorder_settings(os.path.join(temp_dir, "missing.json"))

        self.assertEqual(settings["output"]["mode"], "Separate videos")

    def test_preset_file_path_uses_json_extension_and_safe_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = preset_file_path(temp_dir, "Microscope / Axis")

        self.assertTrue(path.endswith(os.path.join("Microscope_Axis.json")))

    def test_list_recorder_presets_returns_json_names_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_recorder_settings(os.path.join(temp_dir, "Default.json"), default_recorder_settings())
            save_recorder_settings(os.path.join(temp_dir, "Axis.json"), default_recorder_settings())
            with open(os.path.join(temp_dir, "notes.txt"), "w", encoding="utf-8") as handle:
                handle.write("ignore")

            presets = list_recorder_presets(temp_dir)

        self.assertEqual(presets, ["Axis", "Default"])

    def test_list_recorder_presets_skips_unparseable_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_recorder_settings(
                os.path.join(temp_dir, "Valid.json"),
                default_recorder_settings(),
            )
            with open(os.path.join(temp_dir, "Broken.json"), "w", encoding="utf-8") as handle:
                handle.write("{not json")

            self.assertEqual(list_recorder_presets(temp_dir), ["Valid"])

    def test_safe_preset_name_removes_path_characters(self):
        self.assertEqual(safe_preset_name("Lab / Camera: One"), "Lab_Camera_One")


if __name__ == "__main__":
    unittest.main()
