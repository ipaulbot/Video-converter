import unittest
from unittest.mock import patch

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication

from ui import theme
from ui.leaf_frame import LeafFrame
from ui.main_window import VideoConverterApp
from ui.tab_header import TabHeader


class LeafFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_leaf_frame_is_named_and_styled(self):
        frame = LeafFrame(radius=28)
        self.assertEqual(frame.objectName(), "leaf")
        self.assertIn("border-top-left-radius: 28px", frame.styleSheet())
        self.assertIn("border-bottom-left-radius: 0px", frame.styleSheet())
        self.assertEqual(frame.body.contentsMargins().left(), 12)

    def test_dashed_variant(self):
        self.assertIn("dashed", LeafFrame(radius=18, dashed=True).styleSheet())


class TabCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # changeEvent persists the mode whenever the window state flips, so a
        # test that shows / maximizes the window would otherwise write "full"
        # into the real config.json and leak into every later test that builds
        # a main window.
        cls._no_save = patch("ui.main_window.save_settings")
        cls._no_save.start()
        cls.window = VideoConverterApp()

    @classmethod
    def tearDownClass(cls):
        cls.window.shutdown()
        cls.window.deleteLater()
        cls._no_save.stop()

    def test_every_tool_tab_sits_in_a_leaf_card(self):
        keys = {
            "video_converter",
            "pc_report",
            "lossless_editor",
            "multi_source_recorder",
            "media_player",
        }
        self.assertEqual(set(self.window.tool_tab_cards), keys)
        for key, card in self.window.tool_tab_cards.items():
            self.assertIsInstance(card, LeafFrame, key)

    def test_tab_pane_has_no_border_of_its_own(self):
        self.assertIn(
            "QTabWidget::pane { border: none; background: transparent;",
            " ".join(self.window.styleSheet().split()),
        )

    def test_global_push_button_rule_no_longer_forces_a_bubble(self):
        rule = self.window.styleSheet()
        self.assertNotIn("min-width: 100px", rule)
        self.assertNotIn("min-height: 32px", rule)

    def test_burger_has_exclusive_window_mode_actions(self):
        actions = self.window.window_mode_actions
        self.assertEqual(set(actions), {"compact", "full"})
        self.assertTrue(all(a.isCheckable() for a in actions.values()))
        self.assertTrue(actions["compact"].isChecked())
        self.assertEqual(actions["compact"].text(), "Compact mode")
        self.assertEqual(actions["full"].text(), "Full window mode")

    def test_set_window_mode_updates_theme_actions_and_settings(self):
        try:
            self.window.set_window_mode("full", persist=False)
            self.assertEqual(theme.metrics().name, "full")
            self.assertTrue(self.window.window_mode_actions["full"].isChecked())
            self.assertFalse(self.window.window_mode_actions["compact"].isChecked())
            self.assertEqual(self.window.settings["window_mode"], "full")
        finally:
            self.window.set_window_mode("compact", persist=False)
        self.assertEqual(theme.metrics().name, "compact")

    def test_set_window_mode_rejects_unknown(self):
        with self.assertRaises(ValueError):
            self.window.set_window_mode("giant", persist=False)

    def test_set_window_mode_persists_only_when_asked(self):
        with patch("ui.main_window.save_settings") as save:
            self.window.set_window_mode("compact", persist=False)
            save.assert_not_called()
            self.window.set_window_mode("compact", persist=True)
        save.assert_called_once()
        self.assertEqual(save.call_args[0][0]["window_mode"], "compact")

    def test_construction_does_not_show_the_window(self):
        # main.py decides when to show; __init__ only records the mode.
        self.assertFalse(self.window.isVisible())
        self.window.set_window_mode("full", persist=False)
        try:
            self.assertFalse(self.window.isVisible())
            self.assertTrue(self.window.isMaximized())
        finally:
            self.window.set_window_mode("compact", persist=False)
        self.assertFalse(self.window.isMaximized())
        self.assertEqual(self.window.size().width(), theme.COMPACT.window_size[0])

    def test_mode_switch_holds_repaints_until_the_relayout_and_resize_are_done(self):
        # Full -> compact used to paint the re-flowed tabs at the old size,
        # then the restored window, then the resized one: half a second of
        # jitter. The whole switch now happens with updates off.
        window = self.window
        seen = []
        real_apply = window.multi_source_recorder_widget.apply_layout_mode
        real_center = window.center_on_screen

        def spy_apply(metrics):
            seen.append(("relayout", window.updatesEnabled()))
            return real_apply(metrics)

        def spy_center():
            seen.append(("center", window.updatesEnabled()))
            return real_center()

        try:
            window.set_window_mode("full", persist=False)
            with patch.object(window.multi_source_recorder_widget, "apply_layout_mode", spy_apply), \
                    patch.object(window, "center_on_screen", spy_center):
                window.set_window_mode("compact", persist=False)
        finally:
            window.set_window_mode("compact", persist=False)
        self.assertEqual(seen, [("relayout", False), ("center", False)])
        self.assertTrue(window.updatesEnabled())

    def test_mode_switch_re_enables_repaints_even_if_a_tab_relayout_fails(self):
        window = self.window
        with patch.object(
            window.multi_source_recorder_widget, "apply_layout_mode", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                window.set_window_mode("compact", persist=False)
        self.assertTrue(window.updatesEnabled())
        window.set_window_mode("compact", persist=False)

    def test_title_bar_offers_maximize(self):
        self.assertTrue(self.window.windowFlags() & Qt.WindowMaximizeButtonHint)

    def test_title_bar_restore_switches_mode_without_resizing(self):
        window = self.window
        window.show()
        try:
            window.set_window_mode("full", persist=False)
            self.app.processEvents()
            with patch("ui.main_window.save_settings"):
                # What the title-bar restore button does: state changes first,
                # then changeEvent brings the mode along, leaving geometry alone.
                window.showNormal()
                window.resize(1300, 800)
                self.app.processEvents()
                self.assertEqual(theme.metrics().name, "compact")
                self.assertEqual(window.width(), 1300)
                window.showMaximized()
                self.app.processEvents()
                self.assertEqual(theme.metrics().name, "full")
                self.assertTrue(window.window_mode_actions["full"].isChecked())
        finally:
            window.hide()
            window.set_window_mode("compact", persist=False)

    def test_recorder_layout_schematic_leaves_the_leaf_frame_visible(self):
        # The schematic used to be painted on an opaque near-black pixmap that
        # covered the dashed leaf frame; it now sits on a transparent canvas.
        pixmap = self.window._build_layout_preview_pixmap(
            "Separate videos", [(0.0, 0.0, 1.0, 1.0)], 180, 101
        )
        image = pixmap.toImage()
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(1, 1).alpha(), 0)          # corner stays see-through
        centre = image.pixelColor(90, 60)
        self.assertGreater(centre.lightness(), 200)                    # tile is white, not black

    def test_burger_button_fits_the_tab_bar_corner_in_both_modes(self):
        # QTabWidget gives its corner widget the tab bar's height and clips the
        # rest; a 43 px button in a 31 px slot lost the bottom of its round icon.
        try:
            for mode in ("full", "compact"):
                self.window.set_window_mode(mode, persist=False)
                self.app.processEvents()
                button = self.window.burger_button
                slot = self.window.tabs.tabBar().sizeHint().height()
                self.assertLessEqual(button.height(), slot, mode)
                padding = button.property("glyph_padding") or 0
                self.assertLessEqual(
                    button.iconSize().height() + 2 * padding, button.height(), mode
                )
        finally:
            self.window.set_window_mode("compact", persist=False)

    def test_settings_folder_change_buttons_carry_a_folder_glyph(self):
        from ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(dict(self.window.settings), self.window)
        try:
            self.assertEqual(len(dialog.folder_change_buttons), 4)
            for button in dialog.folder_change_buttons:
                self.assertEqual(button.property("glyph"), "folder_open")
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.text(), "Change")
        finally:
            # Delete now: a deferred delete of a child of the class-level window
            # fires alongside the window's own and crashes a later test.
            dialog.setParent(None)
            del dialog

    def test_reskin_reaches_opted_out_tiers(self):
        window = self.window
        widgets = window.reskin_widgets()
        self.assertIn(window.lossless_editor_widget, widgets)
        self.assertIn(window.multi_source_recorder_widget, widgets)
        self.assertIn(window.converted_files_widget, widgets)
        for card in window.tool_tab_cards.values():
            self.assertIn(card, widgets)
        with patch.object(window.lossless_editor_widget, "reskin") as reskin:
            window.update_all_button_styles()
        reskin.assert_called_once()


class TabHeaderUnityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_every_tool_tab_opens_with_the_same_header_glyph_and_its_title(self):
        with patch("ui.main_window.save_settings"):
            window = VideoConverterApp()
        self.addCleanup(window.shutdown)
        window._ensure_media_player_widget()
        headers = window.tab_headers()
        self.assertEqual(set(headers), set(window.tool_tab_widgets))
        expected = {
            "video_converter": ("convert", "Video Converter"),
            "pc_report": ("pc", "PC Report"),
            "lossless_editor": ("scissors", "Lossless Editor"),
            "multi_source_recorder": ("record", "Multi-Source Recorder"),
            "media_player": ("player", "Media Player"),
        }
        for key, (glyph, title) in expected.items():
            header = headers[key]
            self.assertIsInstance(header, TabHeader, key)
            self.assertEqual(header.glyph_name, glyph, key)
            self.assertEqual(header.title_label.text(), title, key)
            self.assertEqual(header.title_label.text(), window.tabs.tabText(
                window.tabs.indexOf(window.tool_tab_widgets[key])), key)
            self.assertEqual(header.glyph_label.width(), TabHeader.GLYPH_PX, key)
            self.assertFalse(header.description_label.isHidden(), key)
        self.assertIn(window.converter_header, window.reskin_widgets())

    def test_every_tool_tab_header_sits_at_the_same_spot_in_the_window(self):
        # The recorder's and the player's headers sat 6 / 16 px lower and
        # further right than the others: their widgets kept their own outer
        # layout margins while the other tabs use none.
        with patch("ui.main_window.save_settings"):
            window = VideoConverterApp()
        self.addCleanup(window.shutdown)
        window.settings["visible_tool_tabs"] = dict.fromkeys(
            window.settings.get("visible_tool_tabs", {}), True)
        window.apply_tool_tab_visibility()
        window._ensure_media_player_widget()
        window.move(-7000, -7000)
        window.show()
        try:
            spots = {}
            for key, header in window.tab_headers().items():
                window.tabs.setCurrentWidget(window.tool_tab_widgets[key])
                for _ in range(6):
                    self.app.processEvents()
                origin = header.mapTo(window, QPoint(0, 0))
                glyph = header.glyph_label.mapTo(window, QPoint(0, 0))
                spots[key] = (origin.x(), origin.y(), glyph.y() - origin.y())
            self.assertEqual(len(set(spots.values())), 1, spots)
        finally:
            window.hide()


class MovableTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, saved_order=None):
        with patch("ui.main_window.save_settings"):
            window = VideoConverterApp()
        self.addCleanup(window.shutdown)
        if saved_order is not None:
            window.settings["tool_tab_order"] = list(saved_order)
            window.apply_tool_tab_order()
        return window

    def test_tabs_can_be_dragged_and_the_order_is_saved(self):
        window = self._window()
        self.assertTrue(window.tabs.isMovable())
        self.assertEqual(window.current_tool_tab_order(), list(window.tool_tab_widgets))
        with patch("ui.main_window.save_settings") as save:
            window.tabs.tabBar().moveTab(0, 4)          # Video Converter to the far right
        save.assert_called_once()
        expected = ["pc_report", "lossless_editor", "multi_source_recorder", "media_player", "video_converter"]
        self.assertEqual(window.current_tool_tab_order(), expected)
        self.assertEqual(window.settings["tool_tab_order"], expected)

    def test_a_saved_order_is_applied_at_start_and_hidden_tabs_keep_their_place(self):
        order = ["media_player", "multi_source_recorder", "video_converter", "pc_report", "lossless_editor"]
        window = self._window(order)
        self.assertEqual(window.current_tool_tab_order(), order)
        # Visibility toggles work on whichever index the tab now has.
        window.settings["visible_tool_tabs"]["pc_report"] = True
        window.apply_tool_tab_visibility()
        index = window.tabs.indexOf(window.tool_tab_widgets["pc_report"])
        self.assertEqual(index, 3)
        self.assertTrue(window.tabs.isTabVisible(index))
