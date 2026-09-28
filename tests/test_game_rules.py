"""BallBuster XT scoring and jackpot rules (pure functions, no Qt)."""

import random
import unittest

from ui.extras import game_rules
from ui.extras.game_rules import (
    LEVEL_CLEAR_BONUS,
    Jackpot,
    drop_points,
    match_points,
    speed_bonus,
    streak_multiplier,
)


class MatchPointsTests(unittest.TestCase):
    def test_each_ball_beyond_the_third_is_worth_ten_more_than_the_last(self):
        self.assertEqual([match_points(n) for n in range(0, 8)], [0, 10, 20, 30, 50, 80, 120, 170])

    def test_drop_points_are_twenty_per_ball(self):
        self.assertEqual(drop_points(0), 0)
        self.assertEqual(drop_points(4), 80)


class StreakTests(unittest.TestCase):
    def test_multiplier_is_one_two_then_three_for_ever(self):
        self.assertEqual([streak_multiplier(s) for s in (0, 1, 2, 3, 4, 9)], [1, 1, 2, 3, 3, 3])


class SpeedBonusTests(unittest.TestCase):
    def test_full_bonus_at_zero_seconds_and_nothing_after_the_limit(self):
        self.assertEqual(speed_bonus(0), 500)
        self.assertEqual(speed_bonus(120), 250)
        self.assertEqual(speed_bonus(240), 0)
        self.assertEqual(speed_bonus(900), 0)

    def test_bonus_is_a_whole_number(self):
        self.assertIsInstance(speed_bonus(37.3), int)

    def test_level_clear_bonus_is_250(self):
        self.assertEqual(LEVEL_CLEAR_BONUS, 250)
        self.assertFalse(hasattr(game_rules, "LEVEL_SCORE_THRESHOLDS"))


def _board(rows):
    """Rows of colour names or None; '.' is empty, letters are colours."""
    grid = []
    for row in rows:
        grid.append([None if ch == "." else {"type": f"ball{ch}", "special": False} for ch in row])
    return grid


class JackpotTests(unittest.TestCase):
    def test_roll_honours_the_weights(self):
        rng = random.Random(7)
        counts = dict.fromkeys(Jackpot.WEIGHTS, 0)
        for _ in range(4000):
            counts[Jackpot.roll(rng)] += 1
        self.assertEqual(set(counts), {"colour_clear", "bomb", "points", "dud"})
        self.assertGreater(counts["colour_clear"], counts["dud"])
        self.assertGreater(counts["bomb"], counts["dud"])
        self.assertGreater(counts["points"], counts["dud"])
        self.assertAlmostEqual(counts["dud"] / 4000, 0.15, delta=0.03)

    def test_colour_clear_drops_every_ball_of_the_commonest_neighbour_colour(self):
        board = _board(["1122", "1.21", "3333"])
        board[1][1] = {"type": "lottery", "special": True}
        neighbours = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 1)]
        result = Jackpot.apply(board, 1, 1, "colour_clear", neighbours=neighbours, rng=random.Random(1))
        # Neighbours: 1,1,2,1,2,3 -> colour 1 is commonest; all three 1s drop
        self.assertEqual(sorted(result.removed), [(0, 0), (0, 1), (1, 0), (1, 1), (1, 3)])
        self.assertEqual(result.points, 0)
        self.assertIsNone(board[1][1])
        self.assertIsNone(board[1][3])
        self.assertIsNotNone(board[0][2])

    def test_bomb_removes_the_neighbours_and_the_jackpot_itself(self):
        board = _board(["1122", "1.21", "3333"])
        board[1][1] = {"type": "lottery", "special": True}
        neighbours = [(0, 0), (0, 1), (1, 0), (1, 2)]
        result = Jackpot.apply(board, 1, 1, "bomb", neighbours=neighbours, rng=random.Random(1))
        self.assertEqual(sorted(result.removed), [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2)])
        self.assertTrue(all(board[r][c] is None for r, c in result.removed))

    def test_bomb_never_removes_bumpers(self):
        board = _board(["11", ".1"])
        board[1][0] = {"type": "lottery", "special": True}
        board[0][0] = {"type": "bumper", "special": True}
        result = Jackpot.apply(board, 1, 0, "bomb", neighbours=[(0, 0), (0, 1), (1, 1)], rng=random.Random(1))
        self.assertNotIn((0, 0), result.removed)
        self.assertEqual(board[0][0]["type"], "bumper")

    def test_points_prize_pays_250_and_drops_only_the_jackpot(self):
        board = _board(["11", ".1"])
        board[1][0] = {"type": "lottery", "special": True}
        result = Jackpot.apply(board, 1, 0, "points", neighbours=[(0, 0), (1, 1)], rng=random.Random(1))
        self.assertEqual(result.points, 250)
        self.assertEqual(result.removed, [(1, 0)])

    def test_dud_turns_the_ball_into_a_neighbour_colour_and_keeps_it(self):
        board = _board(["22", ".2"])
        board[1][0] = {"type": "lottery", "special": True}
        result = Jackpot.apply(board, 1, 0, "dud", neighbours=[(0, 0), (1, 1)], rng=random.Random(1))
        self.assertEqual(result.removed, [])
        self.assertEqual(board[1][0], {"type": "ball2", "special": False})

    def test_dud_with_no_coloured_neighbour_uses_an_available_colour(self):
        board = _board(["..", ".."])
        board[1][0] = {"type": "lottery", "special": True}
        Jackpot.apply(board, 1, 0, "dud", neighbours=[], rng=random.Random(1), available=["ball5"])
        self.assertEqual(board[1][0]["type"], "ball5")


if __name__ == "__main__":
    unittest.main()
