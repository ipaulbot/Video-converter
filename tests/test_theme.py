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


class StaleHostAttributeTests(unittest.TestCase):
    """Guard the failure mode that let a real bug ship silently.

    ui/settings_dialog.py asked its parent for `active_conversion_count`,
    which the Phase 4 queue extraction removed. Because the call used
    `getattr(parent, name, 0)`, it degraded to "no conversions running"
    instead of raising, so the dialog quietly stopped showing its green
    active state. A defensive default on an attribute that is supposed to
    exist hides exactly this.
    """

    # Attributes the UI reads off the main window with a getattr default.
    # Every one of these must actually exist, or the default is silently
    # standing in for a rename.
    EXPECTED_ON_MAIN_WINDOW = (
        "locked", "running", "is_converting", "queue",
        "is_active_workflow_visual_state",
    )

    def test_attributes_read_defensively_actually_exist(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.main_window import VideoConverterApp

        window = VideoConverterApp()
        try:
            for name in self.EXPECTED_ON_MAIN_WINDOW:
                self.assertTrue(hasattr(window, name),
                                f"VideoConverterApp has no {name!r}, but the UI "
                                f"reads it with a getattr default")
        finally:
            # shutdown() stops the timers, the watchdog observer and the
            # preview process. Leaving them armed on a hidden window that the
            # session-long QApplication outlives aborts the interpreter with
            # STATUS_STACK_BUFFER_OVERRUN partway through a later test file.
            window.shutdown()
            window.close()
            window.deleteLater()
            from PyQt5.QtCore import QEvent
            app.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()

    def test_no_module_still_asks_for_the_removed_counter(self):
        """active_conversion_count was replaced by queue.active_count."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        offenders = []
        for path in list((root / "ui").rglob("*.py")) + [root / "main.py"]:
            if path.name.startswith("test_"):
                continue
            for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                if "active_conversion_count" in line and not line.strip().startswith("#"):
                    offenders.append(f"{path.relative_to(root).as_posix()}:{lineno}")
        self.assertEqual(offenders, [],
                         f"use queue.active_count instead: {offenders}")


class NoDuplicatedStateChainTests(unittest.TestCase):
    """The locked/active/idle decision must live in one place.

    It was originally spread across ten separate if/elif chains -- in
    get_icon_path, update_highlight_colors, update_preview_controls_style,
    update_all_button_styles, _set_preview_placeholder, _start_star_field,
    get_game_icon_path, launch_ballbuster_game, SettingsDialog.__init__ and
    PCReportWidget -- each independently re-deriving the same three colours.
    One of them had already drifted onto an attribute that no longer existed.
    """

    STATE_COLOURS = ("#43a296", "#92cb4f", "#8a8a8a")

    def test_no_module_hardcodes_all_three_state_colours(self):
        """A file naming all three is almost certainly re-deriving the chain."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        offenders = []
        for path in list((root / "ui").rglob("*.py")):
            if path.name.startswith("test_") or path.name == "theme.py":
                continue
            if "extras" in path.parts:      # the game keeps its own palette
                continue
            # Ignore commented-out lines, which are not live code.
            live = [line for line in path.read_text(encoding="utf-8").lower().splitlines()
                    if not line.strip().startswith("#")]
            joined = chr(10).join(live)
            if all(colour in joined for colour in self.STATE_COLOURS):
                offenders.append(path.relative_to(root).as_posix())
        self.assertEqual(
            offenders, [],
            "these re-derive the state chain; use theme.skin_for_state() or "
            f"theme.highlight_color() instead: {offenders}")

    def test_skin_for_state_is_the_single_decision(self):
        for locked, active, expected in (
            (False, False, theme.IDLE),
            (False, True, theme.ACTIVE),
            (True, False, theme.LOCKED),
            (True, True, theme.LOCKED),      # locked wins
        ):
            self.assertIs(theme.skin_for_state(locked=locked, active=active),
                          expected, (locked, active))


class ButtonSweepTests(unittest.TestCase):
    """theme.apply_to_buttons replaced two recursive walkers.

    main_window's excluded two buttons by name (one of which has been
    commented out of the UI for some time); settings_dialog's excluded nothing
    at all, so any purpose-built button style in that dialog would have been
    overwritten -- the same defect that was live in the main window's preview
    overlay button.
    """

    def _tree(self):
        """A root with a nested button, to prove the walk is recursive."""
        from PyQt5.QtWidgets import QVBoxLayout
        root = QWidget()
        outer = QPushButton("outer", root)
        nested_host = QWidget(root)
        QVBoxLayout(nested_host)
        nested = QPushButton("nested", nested_host)
        return root, outer, nested

    def test_it_styles_buttons_at_every_depth(self):
        root, outer, nested = self._tree()
        try:
            count = theme.apply_to_buttons(root, "QPushButton { color: red; }")
            self.assertEqual(count, 2)
            self.assertIn("red", outer.styleSheet())
            self.assertIn("red", nested.styleSheet())
        finally:
            root.deleteLater()

    def test_an_opted_out_button_keeps_its_own_style(self):
        root, outer, nested = self._tree()
        try:
            nested.setStyleSheet("QPushButton { color: blue; }")
            theme.opt_out_of_button_style(nested)

            count = theme.apply_to_buttons(root, "QPushButton { color: red; }")
            self.assertEqual(count, 1, "the opted-out button should be skipped")
            self.assertIn("red", outer.styleSheet())
            self.assertIn("blue", nested.styleSheet(),
                          "an opted-out button was overwritten")
        finally:
            root.deleteLater()

    def test_the_opt_out_property_is_the_one_the_walkers_used(self):
        # Buttons in the wild already set this by name; renaming the constant
        # without updating them would silently un-protect them.
        self.assertEqual(theme.SKIP_GLOBAL_STYLE, "skipGlobalStyle")

    def test_a_tree_with_no_buttons_is_harmless(self):
        root = QWidget()
        try:
            self.assertEqual(theme.apply_to_buttons(root, "x"), 0)
        finally:
            root.deleteLater()

    def test_both_hosts_route_through_the_shared_helper(self):
        """Neither should reimplement the traversal."""
        import pathlib
        root_dir = pathlib.Path(__file__).resolve().parents[1]
        for rel, method in (("ui/main_window.py", "apply_button_style_to_all_widgets"),
                            ("ui/settings_dialog.py", "apply_button_style_recursively")):
            source = (root_dir / rel).read_text(encoding="utf-8")
            start = source.index(f"def {method}(")
            body = source[start:start + 900]
            self.assertIn("theme.apply_to_buttons", body,
                          f"{rel}:{method} should delegate, not walk the tree")
            self.assertNotIn("for child in widget.children()", body,
                             f"{rel}:{method} still has its own traversal")
