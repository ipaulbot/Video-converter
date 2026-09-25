import unittest

from utils.config import coerce_retention_days, default_settings, normalize_settings


class ConfigTests(unittest.TestCase):
    def test_coerces_blank_retention_to_zero(self):
        self.assertEqual(coerce_retention_days(""), 0)

    def test_coerces_numeric_string_to_integer(self):
        self.assertEqual(coerce_retention_days("7"), 7)

    def test_clamps_negative_retention_to_zero(self):
        self.assertEqual(coerce_retention_days("-3"), 0)

    def test_clamps_large_retention_to_thirty(self):
        self.assertEqual(coerce_retention_days("365"), 30)

    def test_non_numeric_retention_becomes_zero(self):
        self.assertEqual(coerce_retention_days("abc"), 0)

    def test_default_visible_tool_tabs_include_multi_source_recorder(self):
        settings = normalize_settings({})

        self.assertTrue(settings["visible_tool_tabs"]["multi_source_recorder"])
        self.assertEqual(
            settings["visible_tool_tabs"],
            {
                "conversion_log": True,
                "converted_files": True,
                "video_inspection": True,
                "pc_report": False,
                "lossless_editor": False,
                "multi_source_recorder": True,
                "media_player": False,
            },
        )

    def test_visible_tool_tabs_merge_unknown_or_partial_settings(self):
        settings = normalize_settings({"visible_tool_tabs": {"pc_report": True}})

        self.assertTrue(settings["visible_tool_tabs"]["pc_report"])
        self.assertTrue(settings["visible_tool_tabs"]["conversion_log"])
        self.assertTrue(settings["visible_tool_tabs"]["multi_source_recorder"])

    def test_existing_recorder_visibility_false_is_preserved(self):
        settings = normalize_settings({
            "visible_tool_tabs": {"multi_source_recorder": False},
        })

        self.assertFalse(settings["visible_tool_tabs"]["multi_source_recorder"])

    def test_media_player_defaults_are_present(self):
        normalized = normalize_settings({})
        self.assertEqual(
            normalized["media_player"],
            {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False},
        )

    def test_media_player_group_is_normalized(self):
        normalized = normalize_settings({"media_player": {
            "last_folder": 123, "panel_count": 3, "volume": 250, "muted": "yes",
        }})
        self.assertEqual(normalized["media_player"]["last_folder"], "123")
        self.assertEqual(normalized["media_player"]["panel_count"], 2)
        self.assertEqual(normalized["media_player"]["volume"], 100)
        self.assertTrue(normalized["media_player"]["muted"])
        normalized = normalize_settings({"media_player": {"panel_count": "4", "volume": -5}})
        self.assertEqual(normalized["media_player"]["panel_count"], 4)
        self.assertEqual(normalized["media_player"]["volume"], 0)

    def test_media_player_group_survives_non_dict(self):
        normalized = normalize_settings({"media_player": "garbage"})
        self.assertEqual(normalized["media_player"]["panel_count"], 2)

    def test_window_mode_defaults_to_compact(self):
        self.assertEqual(default_settings["window_mode"], "compact")
        self.assertEqual(normalize_settings({})["window_mode"], "compact")

    def test_window_mode_normalises_unknown_values(self):
        self.assertEqual(normalize_settings({"window_mode": "full"})["window_mode"], "full")
        self.assertEqual(normalize_settings({"window_mode": "FULL"})["window_mode"], "full")
        self.assertEqual(normalize_settings({"window_mode": "giant"})["window_mode"], "compact")
        self.assertEqual(normalize_settings({"window_mode": 3})["window_mode"], "compact")


if __name__ == "__main__":
    unittest.main()
