import datetime
import unittest

from pc_report import format as fmt


class DatetimeParsingTests(unittest.TestCase):
    def test_ms_json_date(self):
        dt = fmt.parse_datetime("/Date(1700000000000)/")
        self.assertEqual(dt, datetime.datetime.fromtimestamp(1700000000))

    def test_cim_datetime(self):
        self.assertEqual(fmt.parse_datetime("20260922103917.000000+120"),
                         datetime.datetime(2026, 9, 22, 10, 39, 17))

    def test_iso_with_offset_becomes_naive_local(self):
        dt = fmt.parse_datetime("2026-09-22T10:39:17+00:00")
        self.assertIsNone(dt.tzinfo)

    def test_yyyymmdd(self):
        self.assertEqual(fmt.parse_datetime("20260522"), datetime.datetime(2026, 5, 22))

    def test_datetime_wrapper_dict(self):
        self.assertEqual(fmt.parse_datetime({"DateTime": "20260522000000.000000+000"}),
                         datetime.datetime(2026, 5, 22))

    def test_garbage_is_none(self):
        for value in (None, "", "yesterday", True, [], {}):
            self.assertIsNone(fmt.parse_datetime(value))

    def test_fmt_datetime_returns_input_when_unparseable(self):
        self.assertEqual(fmt.fmt_datetime("n/a"), "n/a")
        self.assertEqual(fmt.fmt_datetime(None), "")
        self.assertEqual(fmt.fmt_datetime("20260522103000.000000+000"), "2026-05-22 10:30")


class OtherFormattersTests(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(fmt.percent(25, 100), "25.0 %")
        self.assertEqual(fmt.percent(1, 0), "")
        self.assertEqual(fmt.percent("x", 10), "")

    def test_duration(self):
        self.assertEqual(fmt.duration(3723), "1 h 02 m 03 s")
        self.assertEqual(fmt.duration(65), "1 m 05 s")
        self.assertEqual(fmt.duration(7), "7 s")
        self.assertEqual(fmt.duration("bad"), "")

    def test_mhz(self):
        self.assertEqual(fmt.mhz(3200), "3200 MHz")
        self.assertEqual(fmt.mhz(12000), "12.00 GHz")
        self.assertEqual(fmt.mhz(None), "")

    def test_yes_no(self):
        self.assertEqual(fmt.yes_no(True), "Yes")
        self.assertEqual(fmt.yes_no(0), "No")
        self.assertEqual(fmt.yes_no("True"), "Yes")
        self.assertEqual(fmt.yes_no(None), "")
        self.assertEqual(fmt.yes_no("Maybe"), "Maybe")

    def test_kb_human(self):
        self.assertEqual(fmt.kb_human(1024), "1.0 MB")

    def test_uptime_human_is_empty_for_future_or_missing(self):
        self.assertEqual(fmt.uptime_human(None), "")
        future = (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(fmt.uptime_human(future), "")

    def test_legacy_names_still_exist(self):
        from pc_report.utils import bitrate_to_mbps, bytes_human, run_ps_json
        self.assertEqual(bytes_human(2048), "2.0 KB")
        self.assertEqual(bitrate_to_mbps(1_000_000), "1.0 Mbps")
        self.assertTrue(callable(run_ps_json))
