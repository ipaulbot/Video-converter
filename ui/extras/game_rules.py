"""BallBuster XT rules that need no Qt: points, streaks, the speed bonus and
the Jackpot ball's prize table. `snood_widget` calls these; the tests in
`tests/test_game_rules.py` pin the numbers.

Since 2026-09-28 scoring is weighted by play (see
docs/superpowers/specs/2026-09-28-ballbuster-jackpot-scoring-sound-design.md).
Before, every ball was 10 points and two flat +500 bonuses made up half of
any score."""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

BALL_POINTS = 10
DROP_POINTS = 20
LEVEL_CLEAR_BONUS = 250
SPEED_BONUS_MAX = 500
SPEED_BONUS_LIMIT_S = 240
JACKPOT_POINTS = 250


def match_points(n: int) -> int:
    """10 per ball; each ball beyond the third is worth 10 more than the
    one before it (3 = 30, 4 = 50, 5 = 80, 6 = 120)."""
    extra = max(0, n - 3)
    return BALL_POINTS * n + BALL_POINTS * extra * (extra + 1) // 2


def drop_points(n: int) -> int:
    return DROP_POINTS * n


def streak_multiplier(streak: int) -> int:
    """`streak` = clearing shots in a row, this one included: 1, 2, then 3
    for ever."""
    if streak <= 1:
        return 1
    return 2 if streak == 2 else 3


def speed_bonus(elapsed_s: float, limit_s: float = SPEED_BONUS_LIMIT_S) -> int:
    """500 at once, scaling to 0 at `limit_s` and beyond."""
    remaining = max(0.0, 1.0 - elapsed_s / limit_s)
    return int(round(SPEED_BONUS_MAX * remaining))


@dataclass
class JackpotResult:
    prize: str
    removed: list = field(default_factory=list)  # (row, col) cells emptied, jackpot included
    points: int = 0


class Jackpot:
    """The Jackpot (Lottery) ball: lands, spins, pays out one prize."""

    WEIGHTS = {"colour_clear": 30, "bomb": 30, "points": 25, "dud": 15}
    REEL_GLYPHS = ("colour_clear", "bomb", "points", "dud")

    @classmethod
    def roll(cls, rng: random.Random | None = None) -> str:
        rng = rng or random
        names = list(cls.WEIGHTS)
        return rng.choices(names, weights=[cls.WEIGHTS[n] for n in names], k=1)[0]

    @staticmethod
    def _colour_of(cell) -> str | None:
        if not cell or cell.get("special") or cell.get("type") == "bumper":
            return None
        t = cell.get("type", "")
        return t if t.startswith("ball") else None

    @classmethod
    def apply(cls, board, r, c, prize, *, neighbours, rng=None, available=None) -> JackpotResult:
        """Pay `prize` out at (r, c). `neighbours` are the cells around it (the
        widget knows the hex offsets). Empties cells on the board in place and
        reports which, plus any points."""
        rng = rng or random
        result = JackpotResult(prize)
        neighbour_colours = [cls._colour_of(board[nr][nc]) for nr, nc in neighbours]
        neighbour_colours = [t for t in neighbour_colours if t]

        def clear(cell_rc):
            rr, cc = cell_rc
            if board[rr][cc] is not None and board[rr][cc].get("type") != "bumper":
                board[rr][cc] = None
                result.removed.append((rr, cc))

        if prize == "colour_clear":
            if neighbour_colours:
                target = Counter(neighbour_colours).most_common(1)[0][0]
                for rr, row in enumerate(board):
                    for cc, cell in enumerate(row):
                        if cls._colour_of(cell) == target:
                            clear((rr, cc))
            clear((r, c))
        elif prize == "bomb":
            for rc in neighbours:
                clear(rc)
            clear((r, c))
        elif prize == "points":
            result.points = JACKPOT_POINTS
            clear((r, c))
        else:  # dud: becomes a plain ball and stays
            if neighbour_colours:
                colour = Counter(neighbour_colours).most_common(1)[0][0]
            else:
                pool = list(available or [f"ball{i}" for i in range(1, 9)])
                colour = rng.choice(pool)
            board[r][c] = {"type": colour, "special": False}
        return result
