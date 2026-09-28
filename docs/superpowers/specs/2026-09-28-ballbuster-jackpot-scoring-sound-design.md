# BallBuster XT: Jackpot ball, skill-weighted scoring, special-ball tell, sound

Date: 2026-09-28. Branch `ballbuster-1640`. Approved by the owner in chat
after four multiple-choice questions (Jackpot; skill-weighted scoring;
shooter-zone tint; synthesised sounds with a toggle and auto-mute) and a
written design ("Yes, build it").

Also in this pass, already committed (5aa657b): the ASCII banner in the
conversion log wrapped every row because the settings table beside the log
left a 488 px viewport for a 520 px row; the intro now hides the table and
sizes the banner font to the viewport.

## 1. Why

The game is a good easter egg but its numbers do not reward play: 10 points
per ball whatever the match, then +500 for the level and +500 for speed, so
half of any score is "reached the next level". The Lottery ball is a ping
ball for 0.6 s and a colour-timing ball after that, and the overlay text
describes neither. Nothing tells the player the ball in the shooter is
special, and the only sound is the win music.

## 2. Scoring (`ui/extras/game_rules.py`, pure functions)

- `match_points(n)`: 10 per ball, and each ball beyond the third is worth
  10 more than the one before it: 3 = 30, 4 = 50, 5 = 80, 6 = 120, 7 = 170.
  Formula `10*n + 10 * k*(k+1)/2` with `k = max(0, n-3)`. Below 3 it is
  `10*n` (blast removals are counted as singles).
- `drop_points(n)` = 20 per ball (unchanged value, now one place).
- `streak_multiplier(streak)`: 1 for the first clearing shot, 2 for the
  second in a row, 3 for the third and after. Applies to match and drop
  points of that shot only. A shot that clears nothing resets the streak.
  The existing 3-streak super blast stays.
- `speed_bonus(elapsed_s, limit_s=240)` = `round(500 * max(0, 1 -
  elapsed/limit))`, whole number, shown as "SPEED +nnn" where the old
  fixed toast was.
- `LEVEL_CLEAR_BONUS = 250`.
- Blast payouts keep their shape: charged blast 2x per ball, nuke / bumper
  bomb 10 per ball plus the flat bonus. Removed: `LEVEL_SCORE_THRESHOLDS`,
  `BALL_POINT_VALUE` (dead), `FALL_SCORE` moves into `drop_points`.
- HUD: a small chip "x2" / "x3" beside the score while the multiplier is
  above 1.
- High scores stay; the help says scores from 2.3.0 on are weighted.

## 3. Lottery ball becomes the Jackpot

- The internal type is renamed from `pingpong` to `lottery`; the ping-mode
  code keeps `bouncy` only, and `bouncy` keeps the ping-pong image. Custom
  level masks never contained specials, so nothing to migrate.
- Appears from level 2 as the *next* ball with the nuke's odds; never when
  the current ball is already a special.
- Flies and sticks like a plain ball (no ping mode, no cycler). On sticking,
  `board[r][c]` gets `{'type': 'lottery', 'reel': {'ticks': 60, 'index':
  0}}`; the reel advances its glyph every 6 steps, slowing to every 12 for
  the last 24 steps, then `Jackpot.roll(rng)` picks a prize and
  `Jackpot.apply(board, r, c, prize)` pays out.
- Prize table (weights): `colour_clear` 30 -- every non-special ball of the
  colour that is most common among the jackpot's neighbours drops (ties:
  first in neighbour order); `bomb` 30 -- radius-1 blast like the bumper
  bomb; `points` 25 -- +250 and a floating "+250" toast; `dud` 15 -- the
  ball turns into a plain ball of a neighbour colour (or a random available
  colour if it has no coloured neighbour) and stays. On a win the jackpot
  ball itself drops.
- Look: `graphics/balls/lottery.png` is not needed; the ball is drawn in
  code -- gold disc with a white "?" -- so the asset set stays as is.
- Overlay text (`INTRO_INFO[1]`): name "Jackpot Ball", description "Lands,
  spins, pays out: colour clear, bomb, points -- or nothing."
- Super ball (timing cycler, nuke included from level 5), Bouncy, Charged
  and Nuke are unchanged.

## 4. Special-ball tell

- `special_tint(ball)` -> colour or None: gold `#e0b33c` lottery, teal
  `#43a296` bouncy, red `#e05a5a` cue, violet `#8a6fd6` super (cycler),
  orange `#f0903c` charged.
- While the shooter's ball has a tint: a radial wash of that colour at 22 %
  alpha over the strip below the lose line, and a 3 px ring behind the
  shooter ball. The Next preview ball gets the same ring. Alpha eases in and
  out over 250 ms (per-step lerp) so a change of ball does not pop.

## 5. Sound

- `scripts/make_game_sounds.py` writes ten 22 050 Hz 16-bit mono WAVs into
  `graphics/balls/sfx/` (pure `wave` + `math`, no numpy): `shoot`, `bounce`,
  `stick`, `pop` (base; pitch is raised per streak by playing `pop2` /
  `pop3`), `drop`, `bomb`, `reel`, `payout`, `level`, `over`. Each under
  0.6 s, square or noise with a linear decay. Files are committed; the
  PyInstaller spec already bundles all of `graphics/`.
- `ui/extras/game_sounds.py`: `GameSounds(parent)` loads each file into a
  `QSoundEffect`; `play(name)` is a no-op when muted or the file failed to
  load (logged once). `enabled` property mirrors `settings['game_sound']`
  (default True). `set_auto_muted(bool)` from the main window: True while
  `current_activity()` reports converting or a recording phase.
- Speaker glyph button (24 px) in the board's top-right corner toggles
  `enabled`; a slashed glyph shows muted or auto-muted (tooltip says which).
- Events: shoot on launch; bounce on wall; stick on attach without a clear;
  pop on a clear (pop / pop2 / pop3 by multiplier); drop when floaters fall;
  bomb for charged / nuke / bumper / jackpot bomb; reel each glyph change;
  payout on any jackpot win; level on clear; over on game over.

## 6. Tests

- `tests/test_game_rules.py`: match_points table, streak multiplier, speed
  bonus edges, jackpot roll with a seeded RNG honours weights, each prize's
  effect on a 3x3 board fixture, dud picks a neighbour colour.
- `tests/test_snood_widget.py` (widget, offscreen): shooter tint per ball
  type; reel ticks then pays out; multiplier chip text; sound toggle writes
  the setting; auto-mute; all ten WAVs exist and `GameSounds` reports them
  loaded (or skips if QtMultimedia has no backend).
- Existing `test_video_converter_tab` game tests keep passing.

## 7. Docs

Help (en / nl / zh-CN) gets a short "BallBuster XT" paragraph in the
Video Converter section: how to start it, the specials, the sound toggle
and that scoring is weighted from 2.3.0. CHANGELOG under 2026-09-28.
