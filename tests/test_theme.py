"""Tests for ui/theme.py.

The point of these is that the theme layer is only worth having if a colour
cannot leak back into a call site, and if a skin change reliably reaches every
widget. Both are easy to regress silently, so they are pinned here.
"""
import os
import unittest

from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

from ui import theme

app = QApplication.instance() or QApplication([])


class SkinDefinitionTests(unittest.TestCase):
    def setUp(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    def test_three_skins_matching_the_apps_three_states(self):
        self.assertEqual([s.name for s in theme.ALL_SKINS],
                         ["idle", "active", "locked"])

    # Fields that are not colours/strings.
    BOOL_FIELDS = ("grad_horizontal",)
    # Legitimately empty: the idle skin uses unprefixed icon filenames.
    MAY_BE_EMPTY = ("icon_prefix",)

    def test_every_skin_defines_every_field(self):
        # A skin with a None field would render "None" into a stylesheet, which
        # Qt ignores silently -- so assert completeness rather than trusting it.
        for s in theme.ALL_SKINS:
            for field, value in vars(s).items():
                if field in self.BOOL_FIELDS:
                    self.assertIsInstance(value, bool, f"{s.name}.{field}")
                    continue
                self.assertIsInstance(value, str, f"{s.name}.{field}")
                if field not in self.MAY_BE_EMPTY:
                    self.assertTrue(value, f"{s.name}.{field} is empty")

    def test_every_colour_field_is_a_valid_hex_triple(self):
        for s in theme.ALL_SKINS:
            for field, value in vars(s).items():
                if not isinstance(value, str) or not value.startswith("#"):
                    continue
                self.assertEqual(len(value), 7, f"{s.name}.{field}={value}")
                int(value[1:], 16)  # raises if not hex

    def test_icon_prefixes_are_the_ones_graphics_uses(self):
        self.assertEqual(theme.IDLE.icon_prefix, "")
        self.assertEqual(theme.ACTIVE.icon_prefix, "GREEN")
        self.assertEqual(theme.LOCKED.icon_prefix, "GRAYSCALE")

    def test_skins_are_immutable(self):
        # Frozen so a widget cannot "fix" a colour locally and leave every
        # other consumer with the old one.
        import dataclasses
        with self.assertRaises(dataclasses.FrozenInstanceError):
            theme.IDLE.accent = "#000000"

    def test_idle_skin_keeps_the_original_brand_teal(self):
        # This value appeared as a literal 51 times before the theme layer.
        # Changing it is a deliberate rebrand, not a refactor.
        self.assertEqual(theme.IDLE.accent, "#43a296")

    def test_active_skin_keeps_the_original_green(self):
        self.assertEqual(theme.ACTIVE.accent, "#92cb4f")

    def test_locked_skin_keeps_the_original_grey(self):
        self.assertEqual(theme.LOCKED.accent, "#8a8a8a")

    def test_gradient_tokens_reproduce_the_original_buttons(self):
        """The three replaced stylesheets, pinned colour for colour.

        They were mutually inconsistent -- the green button used a teal border
        and the grey one ran its gradient vertically. That is preserved on
        purpose, so adopting the theme layer changed nothing on screen. Update
        these only alongside a deliberate visual change.
        """
        self.assertEqual(
            (theme.IDLE.grad_from, theme.IDLE.grad_to, theme.IDLE.grad_border,
             theme.IDLE.grad_horizontal),
            ("#43a296", "#3a9284", "#2d7d6f", True))
        self.assertEqual(
            (theme.ACTIVE.grad_from, theme.ACTIVE.grad_to, theme.ACTIVE.grad_border,
             theme.ACTIVE.grad_horizontal),
            ("#92cb4f", "#33a16d", "#2d7d6f", True))
        self.assertEqual(
            (theme.LOCKED.grad_from, theme.LOCKED.grad_to, theme.LOCKED.grad_border,
             theme.LOCKED.grad_horizontal),
            ("#8a8a8a", "#7f7f7f", "#6a6a6a", False))

    def test_gradient_axis_follows_the_skin(self):
        theme.theme_manager.set_skin("idle")
        self.assertIn("x2:1, y2:0", theme.gradient_button_style())
        theme.theme_manager.set_skin("locked")
        self.assertIn("x2:0, y2:1", theme.gradient_button_style())
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)


class ColourHelperTests(unittest.TestCase):
    def test_contrast_text_picks_a_readable_ink(self):
        self.assertEqual(theme.contrast_text("#000000"), "#ffffff")
        self.assertEqual(theme.contrast_text("#ffffff"), "#000000")
        self.assertEqual(theme.contrast_text("#43a296"), "#ffffff")

    def test_contrast_text_accepts_short_hex(self):
        self.assertEqual(theme.contrast_text("#fff"), "#000000")
        self.assertEqual(theme.contrast_text("#000"), "#ffffff")

    def test_contrast_text_survives_nonsense(self):
        # Called with whatever a caller has; must not raise mid-paint.
        self.assertEqual(theme.contrast_text("not-a-colour"), "#000000")

    def test_rgba_builds_a_qss_string(self):
        self.assertEqual(theme.rgba("#43a296", 0.5), "rgba(67, 162, 150, 0.500)")

    def test_every_accent_has_readable_text_on_it(self):
        for s in theme.ALL_SKINS:
            ink = theme.contrast_text(s.accent)
            self.assertIn(ink, ("#000000", "#ffffff"), s.name)


class ThemeManagerTests(unittest.TestCase):
    def setUp(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    def tearDown(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    def test_set_skin_changes_the_active_skin(self):
        self.assertTrue(theme.theme_manager.set_skin("active"))
        self.assertEqual(theme.skin().name, "active")

    def test_set_skin_is_a_noop_for_the_current_skin(self):
        self.assertFalse(theme.theme_manager.set_skin(theme.skin().name))

    def test_unknown_skin_is_refused_without_changing_state(self):
        before = theme.skin().name
        self.assertFalse(theme.theme_manager.set_skin("chartreuse"))
        self.assertEqual(theme.skin().name, before)

    def test_changed_signal_fires_once_per_real_change(self):
        seen = []
        theme.theme_manager.changed.connect(lambda: seen.append(1))
        try:
            theme.theme_manager.set_skin("active")
            theme.theme_manager.set_skin("active")   # no-op
            theme.theme_manager.set_skin("locked")
        finally:
            theme.theme_manager.changed.disconnect()
        self.assertEqual(len(seen), 2)

    def test_set_state_maps_the_apps_flags_to_skins(self):
        cases = {
            (False, False): "idle",
            (False, True): "active",
            (True, False): "locked",
            # Locked wins over active, matching the original get_icon_path.
            (True, True): "locked",
        }
        for (locked, active), expected in cases.items():
            theme.theme_manager.set_skin("idle")
            theme.theme_manager.set_state(locked=locked, active=active)
            self.assertEqual(theme.skin().name, expected, (locked, active))

    def test_register_styles_immediately(self):
        button = QPushButton()
        theme.theme_manager.register(button, theme.accent_button_style)
        self.assertIn(theme.IDLE.accent, button.styleSheet())

    def test_registered_widget_follows_a_skin_change(self):
        button = QPushButton()
        theme.theme_manager.register(button, theme.accent_button_style)
        theme.theme_manager.set_skin("active")
        self.assertIn(theme.ACTIVE.accent, button.styleSheet())
        self.assertNotIn(theme.IDLE.accent, button.styleSheet())

    def test_reskin_drops_collected_widgets(self):
        # Registrations are weak, so a closed dialog's widgets must not be kept
        # alive or restyled forever.
        import gc
        button = QPushButton()
        theme.theme_manager.register(button, theme.accent_button_style)
        before = len(theme.theme_manager._ops)
        del button
        gc.collect()
        theme.theme_manager.reskin()
        self.assertLess(len(theme.theme_manager._ops), before)


class StyleFunctionTests(unittest.TestCase):
    """Every style function must produce usable QSS in every skin."""

    STYLE_FUNCTIONS = (
        "accent_button_style", "secondary_button_style", "danger_button_style",
        "tab_bar_style", "panel_style", "drop_zone_style", "log_view_style",
        "group_title_style", "muted_label_style", "video_surface_style",
        "video_panel_style", "table_style", "input_style",
        "progress_bar_style", "window_style", "gradient_button_style",
    )

    def setUp(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    def tearDown(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    def test_all_style_functions_return_non_empty_qss_in_every_skin(self):
        for skin_name in ("idle", "active", "locked"):
            theme.theme_manager.set_skin(skin_name)
            for fn_name in self.STYLE_FUNCTIONS:
                qss = getattr(theme, fn_name)()
                self.assertTrue(qss.strip(), f"{fn_name} in {skin_name}")
                self.assertNotIn("None", qss, f"{fn_name} in {skin_name}")

    def test_qt_accepts_every_stylesheet(self):
        # Qt ignores malformed QSS silently, so the real check is that applying
        # it leaves the property intact.
        for skin_name in ("idle", "active", "locked"):
            theme.theme_manager.set_skin(skin_name)
            for fn_name in self.STYLE_FUNCTIONS:
                widget = QWidget()
                qss = getattr(theme, fn_name)()
                widget.setStyleSheet(qss)
                self.assertEqual(widget.styleSheet(), qss, f"{fn_name}/{skin_name}")

    def test_accent_bearing_styles_track_the_skin(self):
        for fn_name in ("accent_button_style", "tab_bar_style", "progress_bar_style"):
            theme.theme_manager.set_skin("idle")
            idle_qss = getattr(theme, fn_name)()
            theme.theme_manager.set_skin("active")
            active_qss = getattr(theme, fn_name)()
            self.assertNotEqual(idle_qss, active_qss, fn_name)
            self.assertIn(theme.ACTIVE.accent, active_qss, fn_name)

    def test_video_styles_stay_dark_in_every_skin(self):
        # A light panel behind a video frame reads as a rendering fault.
        for skin_name in ("idle", "active", "locked"):
            theme.theme_manager.set_skin(skin_name)
            self.assertIn(theme.VIDEO_BG, theme.video_surface_style())
            self.assertIn(theme.VIDEO_PANEL_BG, theme.video_panel_style())

    def test_semantic_colours_do_not_shift_with_the_skin(self):
        # A warning must not turn green because a conversion is running.
        for skin_name in ("idle", "active", "locked"):
            theme.theme_manager.set_skin(skin_name)
            self.assertIn(theme.DANGER, theme.danger_button_style())
            self.assertIn(theme.WARNING, theme.status_label_style("warning"))
            self.assertIn(theme.DANGER, theme.status_label_style("error"))

    def test_status_label_falls_back_to_muted_for_unknown_state(self):
        qss = theme.status_label_style("something-else")
        self.assertIn(theme.skin().text_muted, qss)


class IconTests(unittest.TestCase):
    def setUp(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    def tearDown(self):
        theme.theme_manager.set_skin(theme.DEFAULT_SKIN_NAME)

    ICONS = ("GEAR", "BURGER", "HELP", "INFO", "BROOM", "LOCK", "UNLOCK", "FILE", "GAME")

    def test_every_icon_resolves_to_a_real_file_in_every_skin(self):
        for skin_name in ("idle", "active", "locked"):
            theme.theme_manager.set_skin(skin_name)
            for icon in self.ICONS:
                path = theme.menu_icon(icon)
                self.assertTrue(os.path.exists(path),
                                f"{icon} in {skin_name} -> {path}")

    def test_prefix_matches_the_skin(self):
        theme.theme_manager.set_skin("locked")
        self.assertIn("GRAYSCALE", os.path.basename(theme.menu_icon("GEAR")))
        theme.theme_manager.set_skin("active")
        self.assertIn("GREEN", os.path.basename(theme.menu_icon("GEAR")))

    def test_unknown_icon_returns_a_path_rather_than_raising(self):
        # Callers hand the result to QIcon, which tolerates a missing file.
        path = theme.menu_icon("NO_SUCH_ICON")
        self.assertTrue(path.endswith("NO_SUCH_ICON.ico"))


if __name__ == "__main__":
    unittest.main()
