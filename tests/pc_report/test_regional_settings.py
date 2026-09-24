import unittest

from pc_report.sections import regional_settings as mod
from tests.pc_report import support

RAW = {"Culture": "en-US", "CultureDisplay": "English (United States)", "UICulture": "en-US", "UICultureDisplay": "English (United States)",
       "SystemLocale": "en-US", "SystemLocaleDisplay": "English (United States)", "HomeLocation": "Netherlands", "GeoId": 176,
       "TimeZoneId": "W. Europe Standard Time", "TimeZoneDisplay": "(UTC+01:00) Amsterdam", "BaseUtcOffset": "01:00:00",
       "SupportsDst": True, "IsDst": True, "ShortDate": "yyyy-MM-dd", "LongDate": "dddd, MMMM d, yyyy", "ShortTime": "HH:mm",
       "TimeFormat": "HH:mm:ss", "Decimal": ".", "Thousand": ",", "ListSeparator": ",", "Currency": "€", "Measure": 0,
       "FirstDayOfWeek": 0, "CalendarType": 1, "NativeDigits": "0123456789", "NegativeSign": "-",
       "DateSample": "2026-09-24", "LongDateSample": "Thursday, September 24, 2026", "TimeSample": "10:11:12",
       "NumberSample": "1,234,567.89", "CurrencySample": "€1,234.50",
       "Languages": [{"Tag": "en-US", "Name": "English (United States)", "Autonym": "English (United States)", "InputMethods": "0409:00000409"}]}


class BuildTests(unittest.TestCase):
    def test_groups(self):
        data = mod.build(RAW)
        rows = {}
        for g in data["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["User Locale"], "English (United States) [en-US]")
        self.assertEqual(rows["Time Zone"], "(UTC+01:00) Amsterdam")
        self.assertEqual(rows["Daylight Saving Time"], "Supported, currently active")
        self.assertEqual(rows["Measurement System"], "Metric")
        self.assertEqual(rows["First Day of Week"], "Monday")
        self.assertEqual(rows["Calendar"], "Gregorian (localized)")
        self.assertEqual(data["languages"][0]["Keyboard Layouts"], "0409:00000409")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Time Zone</th>", html)
        self.assertIn("<th>Keyboard Layouts</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
