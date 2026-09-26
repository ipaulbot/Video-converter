import json
import subprocess
import unittest

from ui.media_player_support import (
    DEFAULT_FPS,
    PlaylistModel,
    collect_video_files,
    format_readout,
    format_timecode_ms,
    frame_index,
    frame_step_ms,
    parse_frame_rate,
    player_convert_settings,
    prefer_windows_media_foundation,
    probe_media_info,
    total_frames,
    unsupported_message,
)


class BackendPreferenceTests(unittest.TestCase):
    def test_prefers_wmf_on_windows_when_nothing_is_set(self):
        env = {}
        self.assertTrue(prefer_windows_media_foundation(env, os_name="nt"))
        self.assertEqual(env["QT_MULTIMEDIA_PREFERRED_PLUGINS"], "windowsmediafoundation")

    def test_respects_an_explicit_choice_and_other_platforms(self):
        env = {"QT_MULTIMEDIA_PREFERRED_PLUGINS": "directshow"}
        self.assertFalse(prefer_windows_media_foundation(env, os_name="nt"))
        self.assertEqual(env["QT_MULTIMEDIA_PREFERRED_PLUGINS"], "directshow")
        env = {}
        self.assertFalse(prefer_windows_media_foundation(env, os_name="posix"))
        self.assertEqual(env, {})


class TimecodeTests(unittest.TestCase):
    def test_format_timecode_ms_always_has_hours_and_millis(self):
        self.assertEqual(format_timecode_ms(0), "0:00:00.000")
        self.assertEqual(format_timecode_ms(1_500), "0:00:01.500")
        self.assertEqual(format_timecode_ms(3_661_007), "1:01:01.007")

    def test_format_timecode_ms_handles_bad_input(self):
        self.assertEqual(format_timecode_ms(None), "0:00:00.000")
        self.assertEqual(format_timecode_ms(-20), "0:00:00.000")


class FrameMathTests(unittest.TestCase):
    def test_parse_frame_rate_accepts_ratios_and_numbers(self):
        self.assertAlmostEqual(parse_frame_rate("30000/1001"), 29.97, places=2)
        self.assertEqual(parse_frame_rate("25"), 25.0)
        self.assertEqual(parse_frame_rate("60/1"), 60.0)

    def test_parse_frame_rate_rejects_garbage(self):
        for text in ("0/0", "", None, "abc", "1/0"):
            self.assertEqual(parse_frame_rate(text), 0.0, text)

    def test_frame_step_ms_per_rate(self):
        self.assertEqual(frame_step_ms(25), 40)
        self.assertEqual(frame_step_ms(parse_frame_rate("24000/1001")), 42)
        self.assertEqual(frame_step_ms(parse_frame_rate("30000/1001")), 33)
        self.assertEqual(frame_step_ms(60), 17)
        self.assertEqual(frame_step_ms(0), frame_step_ms(DEFAULT_FPS))

    def test_frame_index_floors_and_never_negative(self):
        self.assertEqual(frame_index(0, 25), 0)
        self.assertEqual(frame_index(39, 25), 0)
        self.assertEqual(frame_index(40, 25), 1)
        self.assertEqual(frame_index(1000, 29.97), 29)
        self.assertEqual(frame_index(-500, 25), 0)

    def test_total_frames_prefers_probe_count(self):
        self.assertEqual(total_frames(2000, 25, nb_frames=51), 51)
        self.assertEqual(total_frames(2000, 25), 50)
        self.assertEqual(total_frames(0, 0), 0)

    def test_format_readout_with_and_without_frame_rate(self):
        self.assertEqual(
            format_readout(1_000, 2_000, 25, nb_frames=50),
            "0:00:01.000 / 0:00:02.000 · frame 25 / 50",
        )
        self.assertEqual(format_readout(1_000, 2_000, 0), "0:00:01.000 / 0:00:02.000")


PROBE_JSON = {
    "streams": [
        {"codec_type": "video", "codec_name": "hevc", "r_frame_rate": "30000/1001",
         "avg_frame_rate": "30000/1001", "nb_frames": "300"},
        {"codec_type": "audio", "codec_name": "opus", "r_frame_rate": "0/0"},
    ],
    "format": {"format_name": "matroska,webm", "duration": "10.010000"},
}


class ProbeTests(unittest.TestCase):
    def test_probe_media_info_parses_streams_and_format(self):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(PROBE_JSON), stderr="")

        info = probe_media_info("C:\\Videos\\clip.mkv", runner=runner)
        self.assertTrue(info["ok"])
        self.assertAlmostEqual(info["fps"], 29.97, places=2)
        self.assertEqual(info["nb_frames"], 300)
        self.assertEqual(info["duration_ms"], 10_010)
        self.assertEqual(info["container"], "matroska")
        self.assertEqual(info["vcodec"], "hevc")
        self.assertEqual(info["acodec"], "opus")
        self.assertEqual(calls[0][-1], "C:\\Videos\\clip.mkv")
        self.assertIn("-show_entries", calls[0])
        self.assertIn("json", calls[0])

    def test_probe_media_info_falls_back_to_avg_frame_rate(self):
        payload = {"streams": [{"codec_type": "video", "codec_name": "h264",
                                "r_frame_rate": "0/0", "avg_frame_rate": "25/1"}],
                   "format": {"format_name": "mov,mp4,m4a", "duration": "2"}}
        info = probe_media_info("x.mp4", runner=lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(payload), ""))
        self.assertEqual(info["fps"], 25.0)
        self.assertEqual(info["container"], "mov")
        self.assertEqual(info["acodec"], "")

    def test_probe_media_info_reports_failure(self):
        def boom(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)

        info = probe_media_info("x.mp4", runner=boom)
        self.assertFalse(info["ok"])
        self.assertEqual(info["fps"], 0.0)
        failed = probe_media_info("x.mp4", runner=lambda c, **k: subprocess.CompletedProcess(c, 1, "", "bad"))
        self.assertFalse(failed["ok"])
        garbage = probe_media_info("x.mp4", runner=lambda c, **k: subprocess.CompletedProcess(c, 0, "not json", ""))
        self.assertFalse(garbage["ok"])


class UnsupportedMessageTests(unittest.TestCase):
    def test_message_names_codecs_and_container(self):
        info = {"ok": True, "vcodec": "hevc", "acodec": "opus", "container": "matroska"}
        self.assertEqual(unsupported_message(info), "Windows cannot play hevc/opus in matroska.")

    def test_message_without_audio_and_with_gaps(self):
        self.assertEqual(
            unsupported_message({"ok": True, "vcodec": "prores", "acodec": "", "container": "mov"}),
            "Windows cannot play prores in mov.",
        )
        self.assertEqual(
            unsupported_message({"ok": True, "vcodec": "", "acodec": "", "container": ""}),
            "Windows cannot play unknown in unknown.",
        )

    def test_message_when_probe_failed(self):
        self.assertEqual(unsupported_message({"ok": False}), "Windows cannot play this file.")


class ConvertPresetTests(unittest.TestCase):
    def test_player_convert_settings_pins_the_fixed_preset(self):
        base = {"destination_folder": "C:\\Videos\\Out", "video_codec": "libx265", "use_gpu": True,
                "copy_only": True, "text_overlay": "Elapsed Time", "delete_after_conversion": True,
                "use_backup": True, "custom_console_command": "-vf hflip", "output_format": "gif"}
        settings = player_convert_settings(base)
        self.assertEqual(settings["destination_folder"], "C:\\Videos\\Out")
        self.assertEqual(settings["output_format"], "mp4")
        self.assertEqual(settings["video_codec"], "libx264")
        self.assertEqual(settings["audio_codec"], "aac")
        self.assertEqual(settings["audio_bitrate"], "160k")
        self.assertFalse(settings["use_gpu"])
        self.assertFalse(settings["copy_only"])
        self.assertFalse(settings["delete_after_conversion"])
        self.assertFalse(settings["use_backup"])
        self.assertEqual(settings["text_overlay"], "None")
        self.assertEqual(settings["custom_console_command"], "-crf 20 -preset veryfast -movflags +faststart")
        # The caller's dict is not mutated.
        self.assertEqual(base["video_codec"], "libx265")


class PlaylistModelTests(unittest.TestCase):
    def test_add_skips_duplicates_and_blanks(self):
        model = PlaylistModel()
        self.assertEqual(model.add(["a.mp4", "b.mp4", "a.mp4", ""]), 2)
        self.assertEqual(model.items, ["a.mp4", "b.mp4"])

    def test_remove_clear_and_move(self):
        model = PlaylistModel()
        model.add(["a", "b", "c"])
        model.move(0, 2)
        self.assertEqual(model.items, ["b", "c", "a"])
        model.remove(1)
        self.assertEqual(model.items, ["b", "a"])
        model.remove(99)
        self.assertEqual(model.items, ["b", "a"])
        model.clear()
        self.assertEqual(model.items, [])

    def test_next_and_previous_wrap(self):
        model = PlaylistModel()
        self.assertIsNone(model.next_index(0))
        self.assertIsNone(model.previous_index(0))
        model.add(["a", "b", "c"])
        self.assertEqual(model.next_index(0), 1)
        self.assertEqual(model.next_index(2), 0)
        self.assertEqual(model.previous_index(0), 2)
        self.assertEqual(model.previous_index(-1), 0)
        self.assertEqual(model.index_of("c"), 2)
        self.assertEqual(model.index_of("zzz"), -1)

    def test_offsets_default_to_zero_and_follow_their_clip(self):
        model = PlaylistModel()
        model.add(["a", "b"])
        self.assertEqual(model.offset_for("a"), 0.0)
        model.set_offset("a", 1.5)
        model.set_offset("b", "-0.4")
        self.assertEqual(model.offset_for("a"), 1.5)
        self.assertEqual(model.offset_for("b"), -0.4)
        model.set_offset("zzz", 9.0)            # unknown clip: ignored
        self.assertEqual(model.offsets, {"a": 1.5, "b": -0.4})
        model.set_offset("a", 0)                # back to zero drops the entry
        self.assertEqual(model.offsets, {"b": -0.4})
        model.remove(1)                         # removing the clip removes its offset
        self.assertEqual(model.offsets, {})

    def test_offsets_are_clamped_and_cleared_with_the_playlist(self):
        model = PlaylistModel()
        model.add(["a"])
        model.set_offset("a", 5000)
        self.assertEqual(model.offset_for("a"), PlaylistModel.OFFSET_LIMIT_S)
        model.set_offset("a", "not a number")
        self.assertEqual(model.offset_for("a"), 0.0)
        model.set_offset("a", -2.0)
        model.clear()
        self.assertEqual(model.offsets, {})
        self.assertEqual(model.offset_for("a"), 0.0)

    def test_collect_video_files_filters_and_sorts(self):
        tree = [
            ("root", ["sub"], ["B.MP4", "notes.txt", "a.mkv"]),
            ("root\\sub", [], ["c.webm", "image.png"]),
        ]
        files = collect_video_files("root", walker=lambda folder: iter(tree))
        self.assertEqual(files, ["root\\B.MP4", "root\\a.mkv", "root\\sub\\c.webm"])
