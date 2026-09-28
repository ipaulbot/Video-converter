"""BallBuster XT 2026-09-28 pass: weighted scoring in play, the Jackpot ball,
the shooter-zone tell for special balls, and sound routing."""
import os
import unittest
from unittest.mock import patch

from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from ui.extras import BallBusterWidget, snood_widget
from ui.extras.game_rules import Jackpot
from ui.extras.game_sounds import SOUND_NAMES, GameSounds, sfx_dir


class GameFixture(unittest.TestCase):
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

    def clear_board(self, game):
        for r in range(snood_widget.MAX_ROWS):
            for c in range(snood_widget.NUM_COLS):
                game.board[r][c] = None

    def put(self, game, r, c, kind, **extra):
        cell = {"type": kind, "special": kind in ("bumper", "cue")}
        cell.update(extra)
        game.board[r][c] = cell

    def render(self, game):
        image = QImage(game.width(), game.height(), QImage.Format_ARGB32)
        game.render(image)
        return image

    def step_until_idle(self, game, limit=600):
        for _ in range(limit):
            if not game.moving and not game.pending_explosion and not game.falling and not game.jackpot_reel:
                return
            game._step()
        self.fail("game did not settle")


class ScoringInPlayTests(GameFixture):
    def test_a_four_ball_match_pays_fifty_and_streaks_multiply(self):
        game = self.make_game()
        self.clear_board(game)
        for c in range(3):
            self.put(game, 0, c, "ball1")
        game.score = 0
        game.clear_streak = 0
        game.moving = {"type": "ball1", "special": False, "x": 0, "y": 0, "vx": 0, "vy": 0}
        game.collided_cell = None
        with patch.object(game, "pos_to_cell", return_value=(0, 3)):
            game.attach_ball()
        self.assertEqual(game.score, 50)  # 4 in the match; nothing else on the board
        self.assertEqual(game.clear_streak, 1)
        self.assertEqual(game.multiplier_chip_text(), "")

        # Second clearing shot in a row: x2.
        for c in range(3):
            self.put(game, 0, c, "ball2")
        game.moving = {"type": "ball2", "special": False, "x": 0, "y": 0, "vx": 0, "vy": 0}
        with patch.object(game, "pos_to_cell", return_value=(0, 3)):
            game.attach_ball()
        self.assertEqual(game.score, 50 + 50 * 2)
        self.assertEqual(game.multiplier_chip_text(), "x2")

    def test_a_miss_resets_the_streak(self):
        game = self.make_game()
        self.clear_board(game)
        self.put(game, 0, 0, "ball1")
        game.clear_streak = 2
        game.moving = {"type": "ball3", "special": False, "x": 0, "y": 0, "vx": 0, "vy": 0}
        game.collided_cell = None
        with patch.object(game, "pos_to_cell", return_value=(0, 1)):
            game.attach_ball()
        self.assertEqual(game.clear_streak, 0)

    def test_level_clear_pays_250_plus_a_scaled_speed_bonus_and_a_toast(self):
        game = self.make_game()
        self.clear_board(game)
        game.score = 0
        game.level_index = 0
        game.falling = []
        game.level_started_at = snood_widget.time.time() - 120  # half the window gone
        with patch.object(game, "_schedule_level_overlay"):
            game.maybe_level_complete()
        self.assertEqual(game.score, 250 + 250)
        self.assertEqual([t for t, _ in game.toasts], ["SPEED +250"])


class JackpotInPlayTests(GameFixture):
    def test_the_lottery_ball_is_a_plain_flyer_that_spins_a_reel_when_it_sticks(self):
        game = self.make_game()
        self.clear_board(game)
        for c in range(3):
            self.put(game, 0, c, "ball1")
        ball = game.create_ball("lottery")
        self.assertFalse(ball.get("cycler"))
        self.assertNotIn("lottery", ("pingpong", "bouncy"))
        game.moving = ball
        game.collided_cell = None
        with patch.object(game, "pos_to_cell", return_value=(1, 0)):
            game.attach_ball()
        self.assertIsNotNone(game.jackpot_reel)
        self.assertEqual(game.jackpot_reel["rc"], (1, 0))
        self.assertEqual(game.board[1][0]["type"], "lottery")
        self.assertFalse(game.can_shoot)

    def test_the_reel_pays_out_after_sixty_steps(self):
        game = self.make_game()
        self.clear_board(game)
        for c in range(3):
            self.put(game, 0, c, "ball1")
        game.score = 0
        game.moving = game.create_ball("lottery")
        game.collided_cell = None
        with patch.object(game, "pos_to_cell", return_value=(1, 0)), \
                patch.object(Jackpot, "roll", return_value="points"):
            game.attach_ball()
            for _ in range(snood_widget.JACKPOT_REEL_STEPS):
                self.assertIsNotNone(game.jackpot_reel)
                game._step()
        self.assertIsNone(game.jackpot_reel)
        self.assertEqual(game.score, 250)
        self.assertIsNone(game.board[1][0])
        self.assertEqual([t for t, _ in game.toasts], ["+250"])
        self.assertTrue(game.can_shoot)

    def test_colour_clear_from_the_reel_drops_the_neighbour_colour(self):
        game = self.make_game()
        self.clear_board(game)
        for c in range(3):
            self.put(game, 0, c, "ball1")
        self.put(game, 0, 10, "ball1")
        self.put(game, 0, 5, "ball2")
        game.moving = game.create_ball("lottery")
        game.collided_cell = None
        with patch.object(game, "pos_to_cell", return_value=(1, 0)), \
                patch.object(Jackpot, "roll", return_value="colour_clear"):
            game.attach_ball()
            for _ in range(snood_widget.JACKPOT_REEL_STEPS):
                game._step()
        self.assertIsNone(game.board[0][0])
        self.assertIsNone(game.board[0][10])
        self.assertIsNotNone(game.board[0][5])
        self.assertIsNone(game.board[1][0])

    def test_level_two_intro_hands_out_a_jackpot_ball(self):
        game = self.make_game()
        self.assertEqual(game.INTRO_INFO[1]["type"], "lottery")
        self.assertEqual(game.INTRO_INFO[1]["name"], "Jackpot Ball")
        game.start_level(1)
        self.assertEqual(game.next["type"], "lottery")

    def test_lottery_never_queues_behind_another_special(self):
        game = self.make_game()
        game.level_index = 3
        game.available_types = ["ball1", "ball2", "lottery"]
        game.current = game.create_ball("cue")
        with patch.object(snood_widget.random, "random", return_value=0.0):
            for _ in range(20):
                nxt = game.pick_next_ball()
                self.assertNotEqual(nxt["type"], "lottery")


class SpecialTellTests(GameFixture):
    def test_each_special_has_a_tint_and_plain_balls_have_none(self):
        game = self.make_game()
        self.assertIsNone(game.special_tint({"type": "ball3"}))
        self.assertEqual(game.special_tint({"type": "lottery"}).name(), "#e0b33c")
        self.assertEqual(game.special_tint({"type": "bouncy"}).name(), "#43a296")
        self.assertEqual(game.special_tint({"type": "cue"}).name(), "#e05a5a")
        self.assertEqual(game.special_tint({"type": "ball1", "cycler": True}).name(), "#8a6fd6")
        self.assertEqual(game.special_tint({"type": "ball1", "charged": True}).name(), "#f0903c")

    def test_the_tint_eases_in_while_a_special_is_loaded_and_out_after(self):
        game = self.make_game()
        game.current = game.create_ball("lottery")
        for _ in range(3):
            game._step()
        self.assertGreater(game.tell_alpha, 0.0)
        self.assertLess(game.tell_alpha, 1.0)
        for _ in range(60):
            game._step()
        self.assertAlmostEqual(game.tell_alpha, 1.0, places=3)
        self.assertEqual(game.tell_color.name(), "#e0b33c")
        game.current = game.create_ball("ball2")
        for _ in range(60):
            game._step()
        self.assertAlmostEqual(game.tell_alpha, 0.0, places=3)

    def test_the_wash_is_painted_below_the_lose_line_only(self):
        game = self.make_game()
        game.current = game.create_ball("cue")
        game.tell_alpha = 1.0
        game.tell_color = game.special_tint(game.current)
        image = self.render(game)
        game.current = game.create_ball("ball1")
        game.tell_alpha = 0.0
        plain = self.render(game)
        threshold_y = int(game.shooter_y - game.ball_radius * 2)
        x = int(game.width() * 0.25)
        below = image.pixelColor(x, threshold_y + 12)
        below_plain = plain.pixelColor(x, threshold_y + 12)
        above = image.pixelColor(x, threshold_y - 40)
        above_plain = plain.pixelColor(x, threshold_y - 40)
        self.assertNotEqual(below.name(), below_plain.name())
        self.assertEqual(above.name(), above_plain.name())


class SoundTests(GameFixture):
    def test_the_ten_effects_exist_on_disk(self):
        for name in SOUND_NAMES:
            self.assertTrue(os.path.exists(os.path.join(sfx_dir(), f"{name}.wav")), name)

    def test_play_is_silent_when_disabled_or_auto_muted(self):
        sounds = GameSounds()
        self.addCleanup(sounds.deleteLater)
        played = []
        sounds._play_effect = lambda name: played.append(name)
        sounds.set_enabled(True)
        sounds.play("pop")
        sounds.set_enabled(False)
        sounds.play("pop")
        sounds.set_enabled(True)
        sounds.set_auto_muted(True)
        sounds.play("pop")
        self.assertEqual(played, ["pop"])
        self.assertTrue(sounds.muted)
        sounds.set_auto_muted(False)
        self.assertFalse(sounds.muted)

    def test_unknown_names_are_ignored(self):
        sounds = GameSounds()
        self.addCleanup(sounds.deleteLater)
        sounds.play("not-a-sound")  # no raise

    def test_the_game_routes_events_to_its_sounds(self):
        game = self.make_game()
        played = []
        game.sounds = type("S", (), {"play": staticmethod(played.append)})()
        game.launch_ball()
        self.assertIn("shoot", played)

    def test_the_speaker_button_toggles_and_remembers(self):
        game = self.make_game()
        sounds = GameSounds()
        self.addCleanup(sounds.deleteLater)
        saved = {}
        sounds.persist = saved.__setitem__
        game.sounds = sounds
        self.assertTrue(sounds.enabled)
        game.toggle_sound()
        self.assertFalse(sounds.enabled)
        self.assertEqual(saved, {"game_sound": False})
        game.toggle_sound()
        self.assertTrue(sounds.enabled)


if __name__ == "__main__":
    unittest.main()
