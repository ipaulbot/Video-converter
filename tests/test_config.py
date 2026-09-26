import unittest

from utils.config import (
    coerce_retention_days,
    default_settings,
    normalize_settings,
    normalize_tool_tab_order,
)


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
                "video_converter": True,
                "pc_report": False,
                "lossless_editor": False,
                "multi_source_recorder": True,
                "media_player": True,
            },
        )

    def test_visible_tool_tabs_merge_unknown_or_partial_settings(self):
        settings = normalize_settings({"visible_tool_tabs": {"pc_report": True}})

        self.assertTrue(settings["visible_tool_tabs"]["pc_report"])
        self.assertTrue(settings["visible_tool_tabs"]["video_converter"])
        self.assertTrue(settings["visible_tool_tabs"]["multi_source_recorder"])

    def test_old_log_and_files_tabs_migrate_to_the_video_converter_tab(self):
        # Either old tab on -> the merged tab on; both off -> off.
        on = normalize_settings({"visible_tool_tabs": {"conversion_log": False, "converted_files": True}})
        off = normalize_settings({"visible_tool_tabs": {"conversion_log": False, "converted_files": False}})
        self.assertTrue(on["visible_tool_tabs"]["video_converter"])
        self.assertFalse(off["visible_tool_tabs"]["video_converter"])
        self.assertNotIn("conversion_log", on["visible_tool_tabs"])
        self.assertNotIn("converted_files", on["visible_tool_tabs"])

    def test_old_video_inspection_tab_turns_the_media_player_on(self):
        # The inspector now lives inside the Media Player; nobody should lose it.
        settings = normalize_settings({"visible_tool_tabs": {"video_inspection": True, "media_player": False}})
        self.assertTrue(settings["visible_tool_tabs"]["media_player"])
        self.assertNotIn("video_inspection", settings["visible_tool_tabs"])

        settings = normalize_settings({"visible_tool_tabs": {"video_inspection": False, "media_player": False}})
        self.assertFalse(settings["visible_tool_tabs"]["media_player"])

    def test_existing_recorder_visibility_false_is_preserved(self):
        settings = normalize_settings({
            "visible_tool_tabs": {"multi_source_recorder": False},
        })

        self.assertFalse(settings["visible_tool_tabs"]["multi_source_recorder"])

    def test_media_player_defaults_are_present(self):
        normalized = normalize_settings({})
        self.assertEqual(
            normalized["media_player"],
            {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False,
             "inspect_visible": True, "playlist_visible": False},
        )

    def test_media_player_dock_flags_are_booleans(self):
        normalized = normalize_settings({"media_player": {"inspect_visible": 0, "playlist_visible": "yes"}})
        self.assertIs(normalized["media_player"]["inspect_visible"], False)
        self.assertIs(normalized["media_player"]["playlist_visible"], True)

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

    def test_tool_tab_order_defaults_to_the_visibility_key_order(self):
        keys = list(default_settings["visible_tool_tabs"])
        self.assertEqual(default_settings["tool_tab_order"], keys)
        self.assertEqual(normalize_settings({})["tool_tab_order"], keys)

    def test_tool_tab_order_keeps_known_keys_and_appends_the_missing_ones(self):
        order = normalize_tool_tab_order(["media_player", "bogus", "video_converter", "media_player"])
        self.assertEqual(
            order,
            ["media_player", "video_converter", "pc_report", "lossless_editor", "multi_source_recorder"],
        )
        self.assertEqual(normalize_tool_tab_order("nonsense"), list(default_settings["visible_tool_tabs"]))
        self.assertEqual(
            normalize_settings({"tool_tab_order": ["pc_report"]})["tool_tab_order"][0], "pc_report"
        )


if __name__ == "__main__":
    unittest.main()
