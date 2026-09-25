import unittest

from ui.media_player_support import (
    DEFAULT_FPS,
    format_readout,
    format_timecode_ms,
    frame_index,
    frame_step_ms,
    parse_frame_rate,
    total_frames,
)


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
