"""BallBuster must play at the same pace whatever the window size.

Two things made a bigger window feel slow. The physics advanced one fixed
step per timer tick, so any frame the painter could not finish in 16 ms cost
the ball distance. And the painter rescaled the full-window background and
every ball pixmap with SmoothTransformation on every frame, which at
1920x1080 alone took longer than a tick.
"""
import math
import unittest

from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from ui.extras import BallBusterWidget, snood_widget


class PaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_game(self, width=1000, height=700):
        game = BallBusterWidget(theme="teal")
        game.timer.stop()
        game.resize(width, height)
        game.recalculate_geometry()
        self.addCleanup(game.deleteLater)
        return game

    def launch_straight_up(self, game):
        game.mouse_angle = -math.pi / 2
        game.launch_ball()
        self.assertIsNotNone(game.moving)
        return game.moving["y"]

    def test_one_tick_at_60_hz_moves_the_ball_one_step(self):
        game = self.make_game()
        y0 = self.launch_straight_up(game)
        game._clock = lambda: 1.000
        game._last_tick = 1.000 - snood_widget.STEP_S
        game.game_tick()
        self.assertAlmostEqual(y0 - game.moving["y"], snood_widget.SPEED, delta=0.01)

    def test_a_slow_frame_catches_up_so_the_ball_keeps_its_speed(self):
        # A frame that took three tick lengths advances the ball three steps.
        game = self.make_game()
        y0 = self.launch_straight_up(game)
        game._clock = lambda: 1.000
        game._last_tick = 1.000 - 3 * snood_widget.STEP_S
        game.game_tick()
        self.assertAlmostEqual(y0 - game.moving["y"], 3 * snood_widget.SPEED, delta=0.01)

    def test_catch_up_is_capped_after_a_stall(self):
        # After a long stall (a modal dialog, a suspended laptop) the game must
        # not fast-forward through the whole gap in one frame.
        game = self.make_game()
        y0 = self.launch_straight_up(game)
        game._clock = lambda: 5.0
        game._last_tick = 1.0
        game.game_tick()
        self.assertLessEqual(y0 - game.moving["y"], snood_widget.MAX_STEPS_PER_TICK * snood_widget.SPEED + 0.01)

    def test_pixmaps_are_scaled_once_per_size(self):
        game = self.make_game(1920, 1080)
        image = QImage(1920, 1080, QImage.Format_ARGB32)
        game.render(image)
        first = dict(game._scaled_cache)
        self.assertTrue(first, "the painter should have filled the scale cache")
        game.render(image)
        self.assertEqual(set(game._scaled_cache), set(first))
        for key, pixmap in first.items():
            self.assertIs(game._scaled_cache[key], pixmap, key)

    def test_resize_drops_the_cached_background(self):
        game = self.make_game(800, 600)
        image = QImage(800, 600, QImage.Format_ARGB32)
        game.render(image)
        self.assertIn(("bg", 1), [k[0] for k in game._scaled_cache])
        game.resize(1200, 800)
        game.recalculate_geometry()
        self.assertNotIn((("bg", 1), 800, 600), game._scaled_cache)


if __name__ == "__main__":
    unittest.main()
