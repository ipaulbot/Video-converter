import unittest

from PyQt5.QtWidgets import QApplication

from ui import theme
from ui.leaf_frame import LeafFrame
from ui.main_window import VideoConverterApp


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
        cls.window = VideoConverterApp()

    @classmethod
    def tearDownClass(cls):
        cls.window.shutdown()
        cls.window.deleteLater()

    def test_every_tool_tab_sits_in_a_leaf_card(self):
        keys = {
            "conversion_log",
            "converted_files",
            "video_inspection",
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
