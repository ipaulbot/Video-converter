import unittest

from pc_report.sections import accessibility as mod
from tests.pc_report import support

RAW = {"StickyKeys": 510, "ToggleKeys": 62, "FilterKeys": 126, "MouseKeys": 62, "SoundSentry": 2, "HighContrast": 126,
       "Keyboard Response": 126, "TimeOut": 2, "ShowSounds": 0, "Keyboard Preference": 0, "Blind Access": 0,
       "CursorBlinkRate": 530, "CaretWidth": 1, "MouseScheme": "Windows Default", "TextScaleFactor": 100,
       "HighContrastScheme": "High Contrast Black"}


class BuildTests(unittest.TestCase):
    def test_feature_groups_decode_flags(self):
        data = mod.build(RAW)
        titles = [g["title"] for g in data["groups"]]
        self.assertEqual(titles[0], "Settings")
        self.assertIn("Sticky Keys", titles)
        sticky = next(g for g in data["groups"] if g["title"] == "Sticky Keys")["rows"]
        self.assertEqual(sticky["Enabled"], "No")
        self.assertEqual(sticky["Available"], "Yes")
        self.assertEqual(sticky["Hotkey activation enabled"], "Yes")

    def test_settings_rows(self):
        rows = mod.build(RAW)["groups"][0]["rows"]
        self.assertEqual(rows["Cursor Blink Rate"], "530 ms")
        self.assertEqual(rows["Text Scale"], "100 %")
        self.assertEqual(rows["High Contrast Scheme"], "High Contrast Black")
        self.assertEqual(rows["Show Sounds"], "No")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn(">Sticky Keys<", html)
        self.assertIn("<th>Cursor Blink Rate</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
