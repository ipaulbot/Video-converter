import math
import os
import random
import time
import json

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import QPainter, QPixmap, QPen, QColor, QFont, QLinearGradient, QTransform, QCursor
from PyQt5.QtWidgets import QWidget, QInputDialog, QDialog, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton

from utils.resources import resource_path
from utils.system_state import get_high_scores, set_high_scores, get_best_level, set_best_level
from utils.logger import logger

# --- Constants ---
MAX_ROWS = 9
NUM_COLS = 15


LEVELS = [
  [
    [None, None, None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball2', None, None, 'ball3', None, 'ball7', None, None, 'ball4', None, 'ball7', 'ball8'],
    [None, 'ball1', 'ball4', None, 'ball2', None, 'ball1', None, 'ball4', None, 'ball1', None, None],
    [None, 'ball5', None, 'ball4', 'ball2', None, 'ball1', 'ball2', None, None, 'ball4', 'ball4', 'ball5'],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball1', None, None, 'ball6', None, None, 'ball4', None, None, 'ball2', None, None],
    [None, None, 'ball3', None, None, 'ball5', None, None, 'ball6', None, None, 'ball7', None],
    [None, None, None, 'ball7', None, None, 'ball3', None, None, 'ball2', None, None, 'ball2'],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball6', None, 'ball5', None, 'ball8', None, 'ball7', None, 'ball6', None, 'ball2', None, 'ball5'],
    [None, None, 'ball6', None, None, None, None, 'ball2', None, None, None, None, 'ball4', None],
    [None, None, None, 'ball1', None, 'ball2', None, 'ball5', None, 'ball4', None, 'ball1', None, None],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball2', 'ball7', 'ball8', 'ball3', 'ball6', 'ball5', 'ball3', 'ball3', 'ball7', 'ball4'],
    [None, 'ball4', None, None, None, None, None, None, None, None, 'ball6'],
    [None, 'ball2', 'ball5', 'ball6', 'ball6', 'ball4', 'ball2', 'ball4', 'ball8', 'ball5', 'ball1'],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, 'ball2', 'ball4', 'ball4', 'ball7', 'ball3', None, None, None],
    [None, None, None, 'ball1', None, None, 'ball6', 'bumper', 'ball8', None, None, 'ball3', None],
    [None, None, 'ball4', 'ball6', 'ball5', None, None, 'ball8', None, None, 'ball5', 'ball4', 'ball7'],
    [None, None, None, 'ball7', None, None, None, None, None, None, None, 'ball5', None],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, 'ball8', 'ball2', 'ball2', 'ball7', 'ball7', None, None, None],
    [None, None, None, 'ball6', None, None, 'ball1', 'ball3', 'ball2', None, None, 'ball8', None],
    [None, None, 'ball7', 'bumper', 'ball3', None, None, 'ball3', None, None, 'ball7', 'bumper', 'ball1'],
    [None, None, None, 'ball4', None, None, None, None, None, None, None, 'ball5', None],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None],
    [None, None, None, 'ball5', 'ball5', 'ball8', 'ball3', 'ball4', 'ball3', 'ball8', None],
    [None, None, 'ball2', 'ball6', 'ball7', 'ball1', 'ball2', 'ball3', 'ball1', 'ball1', 'ball6'],
    [None, None, None, 'ball2', 'ball3', 'ball5', 'ball5', 'ball6', 'ball6', 'ball2', None],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball5', 'ball4', 'ball4', 'ball8', 'ball3', 'ball5', 'ball4', 'ball7', 'ball8', 'ball4', 'ball6'],
    [None, 'bumper', 'ball1', 'ball2', 'ball2', 'ball8', 'bumper', 'ball4', 'ball6', 'ball2', 'ball2', 'bumper'],
    [None, None, None, 'ball2', 'ball3', 'ball3', 'ball7', 'ball5', 'ball8', 'ball4', None, None],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball1', 'ball2', 'ball4', 'ball2', None, None, 'ball8', 'ball4', None, None, 'ball7'],
    [None, 'ball4', None, None, 'ball1', None, None, 'ball4', 'ball8', 'ball2', None, 'ball6'],
    [None, 'ball4', 'ball1', None, 'ball6', None, None, 'ball3', 'ball7', None, 'ball2', 'ball7'],
    [None, 'ball1', None, None, 'ball2', 'ball4', 'ball5', 'ball8', 'ball4', None, None, 'ball7'],
  ],
  [
    [None, None, None, None, None, None, None, None, None, None, None, None, None],
    [None, 'ball8', 'ball7', 'ball4', 'ball3', 'ball5', 'ball8', 'ball1', 'ball7', 'ball4', 'ball7', 'ball5', 'ball8'],
    [None, 'ball1', 'ball6', 'ball4', 'ball7', 'ball8', 'ball2', 'ball2', 'ball8', 'ball7', 'ball1', 'ball8', 'ball3'],
    [None, 'ball2', 'ball2', 'ball4', 'ball3', 'ball4', 'ball1', 'ball4', 'ball8', 'ball1', 'ball7', 'ball5', 'ball4'],
    [None, 'ball1', None, 'ball8', None, 'ball2', None, 'ball3', None, 'ball3', None, 'ball7', None],
  ],
]
# --- Dynamic 10-level progression ------------------------------------------------
# Dynamic bumpers: level 2 gets 2, level 3 gets 3, … level 10 gets 10
LEVEL_DEFS = [(3, 0)]  # Level 1 – 3 rows, 0 bumpers
for lvl in range(2, 11):
    rows = 3 if lvl < 3 else 4  # keep first two levels shorter
    LEVEL_DEFS.append((rows, lvl))

_ROW_LEN = 10  # logical width of level patterns (before centering)
_BALL_TYPES = [f'ball{i}' for i in range(1, 9)]

def _gen_level(rows: int, bumpers: int):
    import random
    pattern = []
    for r in range(rows):
        # simple repeating colour sequence per row for visual variety
        row = [_BALL_TYPES[(c + r) % len(_BALL_TYPES)] for c in range(_ROW_LEN)]
        pattern.append(row)
    if bumpers:
        # Avoid first row (r==0) so bumpers can be cleared
        eligible = [(r, c) for r in range(1, rows) for c in range(_ROW_LEN)] if rows > 1 else []
        positions = random.sample(eligible, min(bumpers, len(eligible)))
        # ensure bumpers are not directly adjacent
        for r, c in positions:
            # check neighbours for existing bumper
            adj = [(r+dr, c+dc) for dr in (-1,0,1) for dc in (-1,0,1) if abs(dr)+abs(dc)==1]
            if any(0<=rr<_ROW_LEN and 0<=cc<_ROW_LEN and rr<len(pattern) and pattern[rr][cc]=='bumper' for rr,cc in adj):
                continue
            pattern[r][c] = 'bumper'
    return pattern

# Build LEVELS list once at import
LEVELS = [_gen_level(rows, bumpers) for rows, bumpers in LEVEL_DEFS]

# Custom level masks persisted to disk, keyed by 1-based level number as strings
CUSTOM_LEVEL_MASKS = {}
CUSTOM_LEVELS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils', 'custom_levels.json'))

def _load_custom_levels():
    global CUSTOM_LEVEL_MASKS
    try:
        if os.path.exists(CUSTOM_LEVELS_FILE):
            with open(CUSTOM_LEVELS_FILE, 'r') as f:
                data = json.load(f)
            levels = data.get('levels')
            if isinstance(levels, dict):
                CUSTOM_LEVEL_MASKS = {str(k): v for k, v in levels.items()}
                logger.info('Loaded custom level masks from disk')
    except Exception as e:
        logger.error(f'Failed to load custom levels: {e}')

_load_custom_levels()

SPEED = 12
GRAVITY = 0.4
BASE_SCORE = 10
BOMB_BONUS = 20      # flat bonus for using a bumper bomb
CUE_BOMB_BONUS = 50  # flat bonus for N bomb
FALL_SCORE = 20
BOMB_RADIUS = 2
N_BOMB_RADIUS = 3  # bigger blast for cue 'N' bomb
# --- Level progression thresholds (per-level target score) ---
LEVEL_SCORE_THRESHOLDS = [300, 600, 900, 1000, 1500]
BALL_POINT_VALUE = 10
# High scores are stored inside unified system state file under AppData\NVC
PADDING = 2
WALL_PADDING = 4  # gap between window edge and wall

class InitialsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New High Score")
        self.setModal(True)
        self.initials = ""
        # Layout
        vbox = QVBoxLayout(self)
        title = QLabel("NEW HIGH SCORE")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color:#3CA37B;")
        vbox.addWidget(title, alignment=Qt.AlignCenter)
        hbox = QHBoxLayout()
        hbox.setSpacing(10)
        self.edits = []
        for idx in range(3):
            edit = QLineEdit()
            edit.setMaxLength(1)
            edit.setFixedWidth(60)
            edit.setFixedHeight(80)
            edit.setAlignment(Qt.AlignCenter)
            edit.setFont(QFont("Segoe UI", 32, QFont.Bold))
            edit.textChanged.connect(self._focus_next)
            # Pressing Return in the last box accepts the dialog
            if idx == 2:
                edit.returnPressed.connect(self.accept)
            self.edits.append(edit)
            hbox.addWidget(edit)
        vbox.addLayout(hbox)
        self.setFixedSize(360, 220)
        self.edits[0].setFocus()

    def _focus_next(self, text):
        sender = self.sender()
        if sender and text:
            char = text[-1].upper()
            sender.blockSignals(True)
            sender.setText(char)
            sender.blockSignals(False)
        # move focus logic
        for idx, edit in enumerate(self.edits):
            if edit is sender and text and idx < 2:
                self.edits[idx+1].setFocus()
                break

    def get_initials(self):
        if self.exec_() == QDialog.Accepted:
            self.initials = "".join(e.text().upper() or " " for e in self.edits).strip()
            return self.initials if self.initials else None
        return None


class SnoodWidget(QWidget):
    # Mapping of level → introduction data shown on NEXT LEVEL overlay
    INTRO_INFO = {
        1: {
            'type': 'pingpong',
            'name': 'Lottery Ball',
            'description': 'Cycles colours and matches any set!'
        },
        2: {
            'type': 'ball1',    # will be marked charged
            'charged': True,
            'name': 'Charged Ball',
            'description': 'Vibrates and detonates when matched.'
        },
        3: {
            'type': 'bouncy',
            'bounces': 3,
            'name': 'Bouncy Ball',
            'description': 'Ricochets off walls for trick shots.'
        },
        4: {
            'type': 'cue',
            'name': 'Nuke Bomb',
            'description': 'Massive explosion. Use wisely!'
        },
        5: {
            'type': 'ball1',
            'charged': 'double',
            'name': 'Double Charged',
            'description': 'Now two balls can be charged at once!'
        }
    }
    ICON_DIAMETER = 60  # larger ball size

    def __init__(self, theme: str = 'green', parent=None):
        super().__init__(parent)
        self.theme = theme.lower()
        # Choose a primary UI color for lines / texts based on theme
        if self.theme == 'gray':
            self.primary_color = QColor('#888888')
        elif self.theme == 'teal':
            self.primary_color = QColor('#43a296')
        else:
            self.primary_color = QColor('#3CA37B')
        self.setMouseTracking(True)
        # Ensure we receive keyboard input when needed
        self.setFocusPolicy(Qt.StrongFocus)
        self.font = QFont("Segoe UI", 15, QFont.Bold)  # adjusted font size for score and level
        self.images = self.load_images()
        # Extract background images per level for quick access
        self.backgrounds = {i: self.images.get(f'level{i}') for i in range(1, 11)}
        
        self.ball_radius = 0
        self.ping_targets = set()
        self.ping_final_rc = None
        self.row_height = 0
        self.margin_x = 0
        self.shooter_y = 0

        self.high_scores = self.load_high_scores()
        # Log high scores on startup
        for name, score, level in self.high_scores:
            logger.info(f"HIGH SCORE: {score}  LEVEL: {level}  TAG: {name}")
        self.restart_button_rect = QRectF()
        self.exit_button_rect = QRectF()

        self.init_game_state()
        self.start_level(0)
        # Initialize best level at least to 1 on first start
        try:
            if get_best_level() < 1:
                set_best_level(1)
        except Exception:
            pass
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_tick)
        self.timer.start(16)

    def init_game_state(self):
        self.level_index = 0
        self.score = 0
        self.board = []
        self.falling = []
        self.current = None
        self.next = None
        self.moving = None
        self.mouse_angle = -math.pi / 2
        self.game_over = False
        self.win = False
        self.loading = False
        self.loading_ball = None
        self.can_shoot = True
        self.clear_streak = 0
        self.high_score_recorded = False
        self.flash_until = 0
        self.flash_intensity = 1
        # Score animation
        self.display_score = 0
        # Track level timer for speed bonus
        self.level_started_at = time.time()
        # Pending charged blast delay
        self.pending_explosion = None
        self.stuck_ball = None
        # Charged-ball timing
        self.last_charge_check = time.time()
        # Initials entry state
        self.entering_initials = False
        self.initial_chars = ["", "", ""]
        self.initial_index = 0
        self.pending_score = 0
        self.pending_level = 0
        self.super_blast_active = False
        # Wiggle timer for effects after explosions
        self.explosion_wiggle_until = 0
        # Forced intro ball for upcoming shot
        self.forced_next_type = None
        self.forced_next_data = None
        self.level_transition = False
        self.transition_score = 0
        self.collided_cell = None  # will store (r,c,dx,dy) on collision
        # Cheats and editor are disabled by default; require Ctrl+C to enable
        self.cheats_enabled = False
        # Celebration particle systems
        self.confetti = []  # list of dicts: {x,y,vx,vy,spin,angle,color,life}
        self.fireworks = [] # list of sparks: {x,y,vx,vy,life,color}

    def load_images(self):
        """Load colored images according to selected theme."""
        images = {}
        # Map theme to filename prefixes
        if self.theme == 'gray':
            ball_prefix = 'grayball'
            bumper_file = 'GrayBumper.png'
            cue_file = 'graycue.png'
        elif self.theme == 'teal':
            ball_prefix = 'tealball'
            bumper_file = 'TealBumper.png'
            cue_file = 'tealcue.png'
        else:
            # default green
            ball_prefix = 'ball'
            bumper_file = 'Greenbumper.png'
            cue_file = 'greencue.png'

        # balls 1-8
        for i in range(1,9):
            name_key = f'ball{i}'
            filename = f'{ball_prefix}{i}.png'
            path = resource_path(f'graphics/balls/{filename}')
            if os.path.exists(path):
                images[name_key] = QPixmap(path)

        # background images per level (level1.png, level2.png, ...)
        for i in range(1, 11):
            bg_path = resource_path(f'graphics/level{i}.png')
            if os.path.exists(bg_path):
                images[f'level{i}'] = QPixmap(bg_path)
        # yellow overlay for ping-charged balls
        yellow_path = resource_path('graphics/yellow.png')
        if os.path.exists(yellow_path):
            images['yellow'] = QPixmap(yellow_path)
        # red overlay for N-bomb landing
        red_path = resource_path('graphics/red.png')
        if os.path.exists(red_path):
            images['red'] = QPixmap(red_path)
        # ping-pong special ball
        ping_map = {
            'gray': 'grayscaleballbuster.png',
            'teal': 'tealballbuster.png',
            'green': 'ballbuster.png'
        }
        ping_file = ping_map.get(self.theme, 'ballbuster.png')
        for cand in [ping_file, ping_file.upper(), ping_file.capitalize()]:
            ping_path = resource_path(f'graphics/{cand}')
            if os.path.exists(ping_path):
                images['pingpong'] = QPixmap(ping_path)
                # Use the same BallBuster icon for the Bouncy ball
                images['bouncy'] = images['pingpong']
                break
        # special bouncy ball icon (teal ballbuster)
        bouncy_path = resource_path('graphics/TEALBALLBUSTER.png')
        if os.path.exists(bouncy_path):
            images['bouncy'] = QPixmap(bouncy_path)
        # bumper
        path_bumper = resource_path(f'graphics/balls/{bumper_file}')
        if os.path.exists(path_bumper):
            images['bumper'] = QPixmap(path_bumper)

        # cue (not currently used but load for completeness)
        path_cue = resource_path(f'graphics/balls/{cue_file}')
        if os.path.exists(path_cue):
            images['cue'] = QPixmap(path_cue)

                        # Win image (same for all themes)
        path_well = resource_path('graphics/WELLJOBDONE.png')
        if os.path.exists(path_well):
            images['well'] = QPixmap(path_well)
        return images

    def start_level(self, idx, keep_score=False):
        self.level_index = idx
        if not keep_score:
            self.score = 0
        self.game_over = False
        self.win = False
        self.high_score_recorded = False
        self.entering_initials = False
        self.falling.clear()
        
        self.recalculate_geometry()
        
        # In editor preview, always load from level 1 template if requested
        # Load custom mask for this level if present (persisted across restarts)
        mask = CUSTOM_LEVEL_MASKS.get(str(idx+1))
        used_custom_mask = bool(mask)
        if used_custom_mask:
            # Convert boolean mask to level template of placeholders
            pattern = []
            for r in range(len(mask)):
                row = []
                for c in range(len(mask[r])):
                    val = mask[r][c]
                    if val == 'bumper':
                        row.append('bumper')
                    elif val:
                        row.append(random.choice([f'ball{i}' for i in range(1,9)]))
                    else:
                        row.append(None)
                pattern.append(row)
        else:
            pattern = [row[:] for row in LEVELS[idx]]  # copy so we can slice without mutating
        # trim rows for specific levels (skip if using custom mask)
        if not used_custom_mask:
            if idx in (0,1):
                pattern = pattern[:3]
            elif idx == 3:
                pattern = pattern[:4]
            elif idx == 4:
                pattern = pattern[:5]
        self.board = []
        for r in range(MAX_ROWS):
            row_pat = pattern[r] if r < len(pattern) else []
            # center the pattern within NUM_COLS
            if len(row_pat) < NUM_COLS:
                left_pad = (NUM_COLS - len(row_pat)) // 2
                row_pat = [None]*left_pad + row_pat + [None]*(NUM_COLS - left_pad - len(row_pat))
            else:
                row_pat = row_pat[:NUM_COLS]
            # Convert placeholders to normal balls (skip special types for custom masks)
            built_row = []
            for t in row_pat:
                if t is None:
                    built_row.append(None)
                elif isinstance(t, str) and t.startswith('ball'):
                    built_row.append({'type': t, 'special': False})
                else:
                    built_row.append({'type': t, 'special': (t in ('bumper','cue'))})
            self.board.append(built_row)
        
        types = list(set(t for row in pattern for t in row if t and t != 'bumper'))
        if not types:
            types = [f'ball{i}' for i in range(1,9)]
        # Unlock Lottery (ping-pong) ball from level 2 onward
        if idx >= 1 and 'pingpong' not in types:
            types.append('pingpong')
        # Unlock Bouncy ball (BallBuster ricochet) from level 4 onward (idx >=3)
        if idx >= 3 and 'bouncy' not in types:
            types.append('bouncy')
        self.available_types = types
        # Include N-bomb ('cue') in cycling list for Super ball.
        # Include N-bomb ('cue') in cycling list for Super ball starting at level 5
        self.cycle_types = self.available_types + (['cue'] if idx >= 4 else [])

        self.current = self.create_ball(random.choice(self.available_types))
        # determine next ball; honor forced introduction if set
        if self.should_spawn_n_bomb():
            self.next = self.create_ball('cue')
        elif self.should_spawn_super_ball():
            self.next = self.create_super_ball()
        else:
            self.next = self.create_ball(random.choice(self.available_types))
        self.loading = False
        self.can_shoot = True

        # ── Introduce special ball for early levels ──
        intro = self.INTRO_INFO.get(idx)
        if intro:
            # Make preview (next) the intro ball so it is shot third
            self.next = self.create_ball(intro['type'])
            if intro.get('charged'):
                # Suppress charged if live balls on board are below threshold
                live = sum(1 for rr in range(MAX_ROWS) for cc in range(NUM_COLS) if self.board[rr][cc])
                if live >= 5:
                    self.next['charged'] = True
            if 'bounces' in intro:
                self.next['bounces'] = intro['bounces']

    def create_ball(self, t):
        ball = {'type': t, 'special': (t in ('bumper','cue')), 
                'x': self.width() / 2, 'y': self.shooter_y, 'vx': 0, 'vy': 0, 'rot': 0}
        if t == 'bouncy':
            # Start with no pre-counted bounces; will increment on each real ricochet
            ball['bounces'] = 0
        elif t == 'pingpong':
            # Lottery ball cycles through colours
            ball['cycler'] = True
            ball['lottery'] = True
            ball['cycle_index'] = 0
            ball['cycle_last'] = time.time()
        return ball

    # ─────────────────────────────────────────────────────────
    #  Super Ball helpers
    # ─────────────────────────────────────────────────────────
    def create_super_ball(self):
        """Return a new ball dict flagged as a cycling Super Ball."""
        ball = self.create_ball(random.choice(self.available_types))
        ball['cycler'] = True
        ball['cycle_index'] = 0
        ball['cycle_last'] = time.time()
        return ball

    def should_spawn_super_ball(self):
        """Return True if Super Ball should appear as next ball (same odds as N-bomb)."""
        return self.should_spawn_n_bomb()

    def resizeEvent(self, event):
        self.recalculate_geometry()
        super().resizeEvent(event)

    def recalculate_geometry(self):
        # Account for taller window by keeping board compact
        max_board_height = self.height() - 100
        radius_by_height = max_board_height / (2 + (MAX_ROWS - 1) * math.sqrt(3))
        # Try to use full width minus WALL_PADDING on each side
        radius_by_width = (self.width() - 2*WALL_PADDING) / (NUM_COLS * 2 + 1)
        # Final radius capped to match other icon sizes (ICON_DIAMETER/2)
        # Favor width over height for larger balls; may overflow vertically
        self.ball_radius = int(min(radius_by_width, self.ICON_DIAMETER/2))
        if self.ball_radius == 0: return
        self.row_height = math.sqrt(3) * self.ball_radius
        board_width = (NUM_COLS * 2 + 1) * self.ball_radius
        self.margin_x = (self.width() - board_width) / 2
        # Add top offset to push board down for taller window
        self.top_offset = 35  # pixels from top
        self.shooter_y = self.height() - 50
        if self.current and not self.moving:
            self.current['x'] = self.width() / 2
            self.current['y'] = self.shooter_y

    def game_tick(self):
        # Allow falling animation even after logical finish
        if self.game_over:
            return
        self.handle_input()
                # Handle delayed charged explosions
        if self.pending_explosion:
            self.pending_explosion['delay'] -= 1
            # Flash red overlay for cue bombs (toggle every ~0.4 s)
            if self.pending_explosion.get('kind')=='cue' and self.pending_explosion.get('rc'):
                pr, pc = self.pending_explosion['rc']
                if self.board[pr][pc]:
                    # Toggle overlay every 12 ticks for even slower flash
                    self.board[pr][pc]['red_overlay'] = (self.pending_explosion['delay'] % 24 < 12)
            if self.pending_explosion['delay'] <= 0:
                kind = self.pending_explosion.get('kind', 'charged')
                rc = self.pending_explosion.get('rc')
                if kind == 'charged' and rc:
                    r,c = rc
                    self.handle_charged_blast(r, c)
                elif kind == 'cue' and rc:
                    r,c = rc
                    # remove red overlay flag to avoid double draw during fall
                    if self.board[r][c]:
                        self.board[r][c]['red_overlay'] = False
                    self.handle_bomb(r, c)
                else:  # 'ping'
                    # Drop only the balls that were hit – no radius blast
                    removed = 0
                    for rr, cc in list(self.ping_targets):
                        if self.board[rr][cc]:
                            cx, cy = self.cell_to_pos(rr, cc)
                            self.falling.append({'type': self.board[rr][cc]['type'], 'x': cx, 'y': cy,
                                                 'vx': random.uniform(-2, 2), 'vy': -4, 'delay': random.randint(0,8)})
                            self.board[rr][cc] = None
                            removed += 1
                    self.ping_targets.clear()
                    # Also drop the ping-pong ball itself if still on board
                    if self.ping_final_rc:
                        rr, cc = self.ping_final_rc
                        if self.board[rr][cc]:
                            cx, cy = self.cell_to_pos(rr, cc)
                            self.falling.append({'type': self.board[rr][cc]['type'], 'x': cx, 'y': cy,
                                                 'vx': random.uniform(-2, 2), 'vy': -4, 'delay': random.randint(0,8)})
                            self.board[rr][cc] = None
                            removed += 1
                        self.ping_final_rc = None
                    # Failsafe: remove any residual pingpong ball still on board
                    for rr in range(MAX_ROWS):
                        for cc in range(NUM_COLS):
                            if self.board[rr][cc] and self.board[rr][cc]['type'] in ('pingpong', 'bouncy'):
                                cx, cy = self.cell_to_pos(rr, cc)
                                self.falling.append({'type': 'pingpong', 'x': cx, 'y': cy,
                                                     'vx': random.uniform(-2, 2), 'vy': -4, 'delay': random.randint(0,8)})
                                self.board[rr][cc] = None
                                removed += 1
                    if removed:
                        self.score += removed * BASE_SCORE
                    self.drop_floating()
                    self.maybe_level_complete()
                self.pending_explosion = None
                self.stuck_ball = None
        # Smooth score animation (count up or down) in increments of 10
        step = 10
        if self.display_score < self.score:
            self.display_score = min(self.score, self.display_score + step)
        elif self.display_score > self.score:
            self.display_score = max(self.score, self.display_score - step)
        # Auto-charge logic every 1s with 5% probability
        now = time.time()
        if now - self.last_charge_check > 1 and not self.entering_initials and not self.level_transition and not self.win:
            self.last_charge_check = now
            # Check if a charged ball already exists
            charged_count = sum(1 for r in range(MAX_ROWS) for c in range(NUM_COLS) if self.board[r][c] and self.board[r][c].get('charged'))
            # Only allow charged balls starting level index 3 (level 4)
            if self.level_index >= 2 and charged_count < 2 and random.random() < 0.05:
                self.charge_random_ball()
        # Update colour cycling for any Super balls waiting to be launched
        for b in (self.next, self.current, self.loading_ball):
            if b and b.get('cycler'):
                self.update_super_ball(b)
        if self.moving:
            self.update_moving()
        if self.loading and self.loading_ball:
            self.update_loading()
        for ball in self.falling[:]:
            # introduce per-ball start delay for staggered falling animation
            delay = ball.get('delay', 0)
            if delay > 0:
                ball['delay'] = delay - 1
                continue
            ball['vy'] += GRAVITY
            ball['y'] += ball['vy']
            if ball['y'] > self.height():
                self.falling.remove(ball)
        # If moving ball exits the arena, trigger game-over
        if self.moving:
            out_left   = self.moving['x'] < -self.ball_radius
            out_right  = self.moving['x'] > self.width() + self.ball_radius
            out_top    = self.moving['y'] < -self.ball_radius
            out_bottom = self.moving['y'] > self.height()
            if out_left or out_right or out_bottom or out_top:
                self.moving = None
                self.finish_game()
                return
        # Check if drop animation finished
        if getattr(self, 'awaiting_level_clear', False) and not self.falling:
            self.awaiting_level_clear = False
            self._schedule_level_overlay()
        if getattr(self, 'drop_animating', False) and not self.falling:
            self.drop_animating = False
            self.game_over = True
        # Request redraw
        self.update_celebration()
        self.update()
        
    def update_loading(self):
        """Animate the next-ball preview rolling toward the shooter.
        It overshoots the mark by ~2 px, then rolls back to settle."""
        dest_x, dest_y = self.width() / 2, self.shooter_y
        ball = self.loading_ball
        dx, dy = dest_x - ball['x'], dest_y - ball['y']
        dist = math.hypot(dx, dy)

        overshoot_forward = 2  # px past centre on first overshoot (2 over, 2 back to settle)
        overshoot_back = 2     # px back in the opposite direction on bounce

        # ── Overshoot / bounce logic ──────────────────────────────────
        if dist <= 0.5:
            stage = ball.get('overshoot_stage', 0)
            # Calculate unit approach vector. If dist==0 use previously stored vector.
            if dist == 0:
                ux, uy = ball.get('overshoot_uvec', (0, -1))
            else:
                ux, uy = dx / max(dist, 1e-6), dy / max(dist, 1e-6)
                ball['overshoot_uvec'] = (ux, uy)
            if stage == 0:
                # First overshoot – go 4 px beyond the centre
                ball['x'] = dest_x + ux * overshoot_forward
                ball['y'] = dest_y + uy * overshoot_forward
                ball['overshoot_stage'] = 1
                return
            elif stage == 1:
                # Bounce back to centre and settle
                ball['x'], ball['y'] = dest_x, dest_y
                # Finalise loading
                self.current = self.loading_ball
                self.current['x'], self.current['y'] = dest_x, dest_y
                self.current['rot'] = 0
                self.loading = False
                self.loading_ball = None
                self.can_shoot = True
                return

        # ── Normal inbound rolling ────────────────────────────────────
        # Increase roll speed back to snappier feel
        # Faster roll-in for snappier feel
        step = min(14, dist)
        ball['x'] += (dx / dist) * step
        ball['y'] += (dy / dist) * step
        # rotate proportionally to distance moved
        circumference = max(1, self.ball_radius * 2 * math.pi)
        delta_rot = - (step / circumference) * 360  # counter-clockwise roll
        ball['rot'] = (ball.get('rot', 0) + delta_rot) % 360

    def update_super_ball(self, ball):
        """Advance colour for cycling balls (Lottery & Super)."""
        if not ball.get('cycler'):
            return
        interval = 0.6  # seconds between colour changes (slowed by 2x)
        now = time.time()
        last = ball.get('cycle_last', 0)
        if now - last < interval:
            return
        # Decide colour pool: Lottery ball should not include specials (bouncy or cue)
        if ball.get('lottery'):
            # Lottery ball should cycle only through standard coloured balls (1–8)
            colour_pool = [t for t in self.available_types
                           if t not in ('bouncy', 'pingpong') and not t.startswith('cue')]
            # Fallback safeguard
            if not colour_pool:
                colour_pool = [f'ball{i}' for i in range(1, 9)]
        else:
            colour_pool = self.cycle_types
        idx = (ball.get('cycle_index', 0) + 1) % len(colour_pool)
        ball['cycle_index'] = idx
        ball['type'] = colour_pool[idx]
        ball['special'] = (ball['type'] in ('bumper', 'cue'))
        ball['cycle_last'] = now

    def handle_input(self):
        pos = self.mapFromGlobal(self.cursor().pos())
        dx = pos.x() - self.width() / 2
        dy = pos.y() - self.shooter_y
        angle = math.atan2(dy, dx)
        if angle > -0.1: angle = -0.1
        if angle < -math.pi + 0.1: angle = -math.pi + 0.1
        self.mouse_angle = angle
        
    def _commit_initials(self):
        initials = "".join(c or " " for c in self.initial_chars).strip() or "YOU"
        self.high_scores.append((initials.upper(), self.pending_score, self.pending_level))
        self.high_scores = sorted(self.high_scores, key=lambda x: x[1], reverse=True)[:5]
        self.save_high_scores()
        logger.info(f"HIGH SCORE: {self.pending_score}  LEVEL: {self.pending_level}  TAG: {initials}")
        self.high_score_recorded = True
        self.entering_initials = False

    def keyPressEvent(self, event):
        if self.entering_initials:
            key = event.key()
            if Qt.Key_A <= key <= Qt.Key_Z and self.initial_index < 3:
                self.initial_chars[self.initial_index] = chr(key)
                self.initial_index += 1
                if self.initial_index == 3:
                    self._commit_initials()
                self.update()
                return
            elif key == Qt.Key_Backspace and self.initial_index > 0:
                self.initial_index -= 1
                self.initial_chars[self.initial_index] = ""
                self.update()
                return
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                self._commit_initials()
                return
        # Cheats: require Ctrl+C once to enable cheat keys and level editor
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_C:
            self.cheats_enabled = True
            logger.info("Cheats enabled (Ctrl+C)")
            self.update()
            return

        # Normal key handling when not entering initials
        # If win overlay is shown, any key progresses
        if self.win:
            self._progress_from_win()
            return
        if event.key() == Qt.Key_N and self.next and self.cheats_enabled:
            self.next['type'] = 'cue'
            self.next['special'] = True
        elif event.key() == Qt.Key_S and self.next and self.cheats_enabled:
            self.next['cycler'] = True
            self.next['cycle_index'] = 0
            self.next['cycle_last'] = time.time()
            self.next['type'] = self.cycle_types[0]
            self.next['special'] = (self.next['type'] in ('bumper', 'cue'))
        # ---- Spawn Ping-Pong ball cheat (P) ---------------------------------
        elif event.key() == Qt.Key_P and self.next and self.cheats_enabled:
            self.next['type'] = 'pingpong'
            self.next['special'] = True
        # Secret level-skip / clear – press 'C'
        elif event.key() == Qt.Key_W and not self.entering_initials and not self.level_transition and self.cheats_enabled:
            self.charge_random_ball()
            self.update()
            return
        elif event.key() == Qt.Key_C and not self.entering_initials and not self.level_transition and self.cheats_enabled:
            # Clear board instantly
            for r in range(MAX_ROWS):
                for c in range(NUM_COLS):
                    self.board[r][c] = None
            self.moving = None
            self.falling.clear()
            self.maybe_level_complete()
            self.update()
            return
        # ---- Enter/exit Level Editor (E) -------------------------------------
        elif event.key() == Qt.Key_E and not self.entering_initials and not self.level_transition and self.cheats_enabled:
            self.toggle_editor()
            return
        # Fireworks test cheat (F)
        elif event.key() == Qt.Key_F and self.cheats_enabled:
            self.trigger_fireworks_cheat()
            self.update()
            return
        # In-editor: 'B' toggles bumper on the cell under cursor
        elif getattr(self, 'editor_active', False) and event.key() == Qt.Key_B:
            pos = self.mapFromGlobal(QCursor.pos())
            r, c = self.pos_to_cell(pos.x(), pos.y())
            if 0 <= r < MAX_ROWS and 0 <= c < NUM_COLS:
                curr = self.editor_mask[r][c]
                self.editor_mask[r][c] = (None if curr == 'bumper' else 'bumper')
                self.editor_dirty = True
                self.update()
            return
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if self.game_over or self.level_transition or self.win:
            if self.restart_button_rect.contains(event.pos()):
                if self.win:
                    # From win overlay: go to high-score list first
                    self._progress_from_win()
                    return
                # Otherwise restart a fresh run
                self.start_level(0)
            elif self.exit_button_rect.contains(event.pos()):
                if self.win:
                    self._progress_from_win()
                else:
                    self.close()
            else:
                # On win overlay, any click progresses
                if self.win:
                    self._progress_from_win()
            return
        # In editor mode, clicking toggles a cell instead of shooting
        if getattr(self, 'editor_active', False):
            self.editor_click(event.pos())
            return
        if not self.moving and not self.loading and self.can_shoot:
            self.launch_ball()

    def should_spawn_n_bomb(self):
        """Return True if N bomb should appear as next ball."""
        # N-bombs are only unlocked starting at level 5
        if self.level_index < 4:
            return False
        # base chance 2%
        base_prob = 0.02
        # count balls in bottom row
        bottom_row_balls = sum(1 for c in range(NUM_COLS) if self.board[MAX_ROWS-1][c])
        if bottom_row_balls > 2:
            base_prob = 0.15  # increase chance when danger
        return random.random() < base_prob

    def launch_ball(self):
        self.moving = self.current
        if self.moving:
            # Preserve any pre-set bounce count (for Bouncy Ball) if present
            if 'bounces' not in self.moving:
                self.moving['bounces'] = 0
            self.moving['rot'] = 0
            # Initialize ping-pong tracking
            if self.moving['type'] in ('pingpong', 'bouncy'):
                self.ping_targets.clear()
                self.ping_final_rc = None
        self.moving['vx'] = math.cos(self.mouse_angle) * SPEED
        self.moving['vy'] = math.sin(self.mouse_angle) * SPEED
        self.current = None
        self.can_shoot = False
        
        self.loading = True
        self.loading_ball = self.next
        self.loading_ball['rot'] = 0
        self.loading_ball['overshoot_stage'] = 0
        preview_x = self.width() - self.ball_radius*2 - 20 
        preview_y = self.shooter_y
        self.loading_ball['x'], self.loading_ball['y'] = preview_x, preview_y
        # determine next ball; honor forced introduction if set
        if getattr(self, 'forced_next_type', None):
            data = self.forced_next_data or {}
            self.next = self.create_ball(self.forced_next_type)
            if data.get('charged') == True:
                self.next['charged'] = True
            if data.get('bouncy'):
                self.next['bounces'] = 3
            # clear flags
            self.forced_next_type = None
            self.forced_next_data = None
            return  # intro ball queued; defer normal selection
        # fallback normal selection
        if self.should_spawn_n_bomb():
            self.next = self.create_ball('cue')
        elif self.should_spawn_super_ball():
            self.next = self.create_super_ball()
        else:
            self.next = self.create_ball(random.choice(self.available_types))

    def update_moving(self):
        ball = self.moving
        ping = (ball['type'] in ('pingpong', 'bouncy'))
        ball['x'] += ball['vx']
        ball['y'] += ball['vy']

        left_wall = WALL_PADDING + self.ball_radius
        right_wall = self.width() - WALL_PADDING - self.ball_radius
        if ball['x'] < left_wall:
            ball['x'] = left_wall
            ball['vx'] *= -1
            ball['bounces'] = ball.get('bounces',0) + 1
        elif ball['x'] > right_wall:
            ball['x'] = right_wall
            ball['vx'] *= -1
            ball['bounces'] = ball.get('bounces',0) + 1
        
                # Stick to ceiling instead of bouncing
        # Ceiling at the same position as row 0 - no gap, no bounce, immediate attachment
        top_offset = getattr(self, 'top_offset', 0)
        ceiling_y = top_offset  # Exactly where row 0 center is
        if ball['y'] < ceiling_y:
            if ping:
                ball['y'] = ceiling_y
                ball['vy'] *= -1
                ball['bounces'] += 1
            else:
                ball['y'] = ceiling_y
                # Immediately attach to grid
                self.attach_ball()
                return
        # Bounce off dashed lose line for ping ball
        if ping:
            # Use same threshold calculation as paintEvent for consistency
            threshold_y = self.shooter_y - (self.ball_radius * 2 * 1.0)
            if ball['y'] > threshold_y:
                ball['y'] = threshold_y
                ball['vy'] *= -1
                ball['bounces'] += 1
        # Finalise ping if bounce limit reached without hitting cell
        if ping and ball['bounces'] >= 20 and self.moving:
            self.attach_ball()
            self.pending_explosion = {'rc': None, 'delay': 30, 'kind': 'ping'}
            return

        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                cell = self.board[r][c]
                if cell:
                    cx, cy = self.cell_to_pos(r, c)
                    dx = cx - ball['x']
                    dy = cy - ball['y']
                    dist = math.hypot(dx, dy)
                    
                    vx, vy = ball['vx'], ball['vy']
                    mag_v = math.hypot(vx, vy)
                    if mag_v == 0: continue
                    
                    cos_theta = (vx * dx + vy * dy) / (mag_v * dist)
                    
                    # Hitbox tuning: bouncy +10%, others -5%
                    if ball['type'] == 'bouncy':
                        threshold = self.ball_radius * 1.65 * 1.10
                    else:
                        base = self.ball_radius * 1.65
                        if cos_theta < 0.4:  # Glancing hit
                            base = self.ball_radius * 1.55
                        threshold = base * 0.95

                    if dist < threshold:
                        if ping:
                            # Bounce: mark cell charged, store target, reflect velocity
                            if not cell.get('charged'):
                                cell['charged'] = True
                                cell['yellow_overlay'] = True
                                self.ping_targets.add((r, c))
                            # Reflect velocity about normal (unless final bounce)
                            nx, ny = dx / dist, dy / dist
                            dot = ball['vx']*nx + ball['vy']*ny
                            ball['bounces'] += 1
                            if ball['bounces'] >= 20:
                                # Final contact – stick like a bumper ball then schedule detonation
                                self.collided_cell = (r, c, -dx, -dy)
                                self.attach_ball()
                                self.ping_final_rc = (r, c)
                                self.pending_explosion = {'rc': None, 'delay': 30, 'kind': 'ping'}
                                return
                            else:
                                ball['vx'] -= 2*dot*nx
                                ball['vy'] -= 2*dot*ny
                            return
                        # ── Bouncy Ball ricochet logic ─────────────────────────
                        if ball['type'] == 'bouncy' and ball.get('bounces',0) < 5:
                            # Reflect similar to ping ball but without charging targets
                            nx, ny = dx / dist, dy / dist
                            dot = ball['vx']*nx + ball['vy']*ny
                            # Push out of overlap so we don't immediately re-collide
                            penetration = ((self.ball_radius*1.65*1.10) - dist) + 0.1
                            ball['x'] -= nx * penetration
                            ball['y'] -= ny * penetration
                            # Reflect velocity
                            ball['vx'] -= 2*dot*nx
                            ball['vy'] -= 2*dot*ny
                            ball['bounces'] = ball.get('bounces',0) + 1
                            return
                        # Immediate explosion if target ball is charged
                        if cell.get('charged'):
                            # Attach ball first, then trigger delayed explosion on the charged target
                            self.attach_ball()
                            self.pending_explosion = {'rc': (r, c), 'delay': 15}
                            return
                        # Store collision cell and incidence vector for better attachment placement
                        self.collided_cell = (r, c, -dx, -dy)  # vector from cell -> ball center
                        self.attach_ball()
                        return

    def attach_ball(self):
        ball = self.moving
        r, c = self.pos_to_cell(ball['x'], ball['y'])

        # Clamp to valid grid range
        r = max(0, min(MAX_ROWS - 1, r))
        c = max(0, min(NUM_COLS - 1, c))

        # If we have collision context, use directional neighbour preference first
        if self.collided_cell is not None:
            base_r, base_c, dir_x, dir_y = self.collided_cell
            cand = self.find_directional_empty(base_r, base_c, dir_x, dir_y)
            if cand:
                r, c = cand
            self.collided_cell = None  # reset

        if self.board[r][c] is not None:
            pos = self.find_empty_neighbour(r, c, ball['x'], ball['y'])
            if not pos:
                # Prefer empty cells that are not lower than the collision point
                pos = self.find_best_empty(ball['x'], ball['y'], max_y=ball['y'])
            if not pos:
                # Absolute closest as last resort
                pos = self.find_best_empty(ball['x'], ball['y'])
            if pos:
                r, c = pos
            else:
                self.moving = None
                return

        self.board[r][c] = {'type': ball['type'], 'special': ball['special'], 'yellow_overlay': (True if ball['type']=='pingpong' else ball.get('yellow_overlay'))}
        if ball['type'] in ('pingpong', 'bouncy'):
            self.ping_final_rc = (r, c)
        self.moving = None
        # ── Bumper interaction: if this ball landed adjacent to any bumper, jiggle the bumper(s)
        #    and immediately drop this ball so the board stays clear.
        adjacent_bumper_cells = [(nr, nc) for nr, nc in self.get_neighbours(r, c)
                                 if self.board[nr][nc] and self.board[nr][nc]['type'] == 'bumper']
        if adjacent_bumper_cells:
            import time as _time
            # Mark bumpers to jiggle for the next 0.4 seconds
            for br, bc in adjacent_bumper_cells:
                self.board[br][bc]['jiggle_until'] = _time.time() + 0.4

        
        bounce_intensity = ball.get('bounces',0)
        if not ball['special'] and bounce_intensity >= 2 and random.random() < 0.5:
            # radius-1 blast including landing cell
            to_remove = set([(r, c)]) | set(self.get_neighbours(r, c))
            # Remember if landed ball was special before deletion
            landed_special = self.board[r][c]['special']
            removed_actual = 0
            for rr, cc in to_remove:
                # Never remove permanent bumpers
                if self.board[rr][cc] and self.board[rr][cc]['type'] != 'bumper':
                    cx, cy = self.cell_to_pos(rr, cc)
                    self.falling.append({'type': self.board[rr][cc]['type'], 'x': cx, 'y': cy,
                                          'vx': random.uniform(-1, 1), 'vy': -2, 'delay': random.randint(0, 8)})
                    self.board[rr][cc] = None
                    removed_actual += 1
            self.score += removed_actual * BASE_SCORE
            self.flash_all_balls(intensity=2)
            # Drop newly floating balls after blast
            self.drop_floating()
            self.maybe_level_complete()
            if self.check_lose():
                self.finish_game()
            return  # skip normal attach logic – ball destroyed
        elif bounce_intensity:
            self.flash_all_balls(intensity=min(6, bounce_intensity+2))

        # proceed with normal logic after attachment
        # If the newly placed ball is adjacent to any charged ball, schedule its detonation
        for nr, nc in self.get_neighbours(r, c):
            if self.board[nr][nc] and self.board[nr][nc].get('charged'):
                if not self.pending_explosion or self.pending_explosion['rc'] != (nr, nc):
                    self.pending_explosion = {'rc': (nr, nc), 'delay': 15, 'kind': 'charged'}
                break
        if self.board[r][c].get('charged'):
            self.handle_charged_blast(r,c)
            return
        # Trigger bomb only for cue balls ("N" bombs), not for bumpers.
        if self.board[r][c]['type'] == 'cue':
            # Flag red overlay and schedule detonation after 1 s (45 ticks)
            self.board[r][c]['red_overlay'] = True
            self.pending_explosion = {'rc': (r, c), 'delay': 45, 'kind': 'cue'}
        else:
            cluster = self.find_cluster(r, c)
            contains_charged = any(self.board[rr][cc] and self.board[rr][cc].get('charged') for rr,cc in cluster)
            if len(cluster) >= 3:
                if contains_charged:
                    # Detonate charged ball but let the triggering ball drop first so it doesn't remain stuck.
                    if not self.board[r][c].get('charged'):
                        cx, cy = self.cell_to_pos(r, c)
                        self.falling.append({'type': self.board[r][c]['type'], 'x': cx, 'y': cy,
                                             'vx': random.uniform(-1, 1), 'vy': -2, 'delay': 0})
                        self.board[r][c] = None
                    # Use first charged cell found to detonate
                    for rr, cc in cluster:
                        cell_ref = self.board[rr][cc]
                        if cell_ref and cell_ref.get('charged'):
                            self.handle_charged_blast(rr, cc)
                            break
                    self.drop_floating()
                    self.maybe_level_complete()
                    return
                elif bounce_intensity >=2:
                    # Power bounce match – clear all of this colour
                    target_type = self.board[r][c]['type']
                    global_cluster = [(rr,cc) for rr in range(MAX_ROWS) for cc in range(NUM_COLS)
                                       if self.board[rr][cc] and not self.board[rr][cc]['special'] and self.board[rr][cc]['type']==target_type]
                    for rr,cc in global_cluster:
                        cx,cy = self.cell_to_pos(rr,cc)
                        self.falling.append({'type': self.board[rr][cc]['type'],'x':cx,'y':cy,'vx':random.uniform(-1,1),'vy':-2,'delay':random.randint(0,8)})
                        self.board[rr][cc]=None
                    self.score += len(global_cluster)*BASE_SCORE
                    self.flash_all_balls(intensity=2)
                    self.maybe_level_complete()
                    self.drop_floating()
                else:
                    # Successful clear – increase streak and start screen flash
                    self.clear_streak += 1
                    if self.clear_streak >= 2:
                        self.flash_all_balls()
                    if self.clear_streak >= 3:
                        # Activate super-blast power up
                        self.do_super_blast(cluster)
                    else:
                        removal = set(cluster) | self._collect_adjacent_bumpers(cluster)
                        for rr, cc in removal:
                            cx, cy = self.cell_to_pos(rr, cc)
                            self.falling.append({'type': self.board[rr][cc]['type'],
                                                 'x': cx,
                                                 'y': cy,
                                                 'vx': random.uniform(-1, 1),
                                                 'vy': -2})
                            self.board[rr][cc] = None
                        self.score += len(removal) * BASE_SCORE
                        self.maybe_level_complete()
                        self.drop_floating()
            else:
                # Missed – reset streak
                self.clear_streak = 0

        # ── Post-placement bumper rejection ────────────────────────────
        # If the ball is still present, sits next to a bumper, and didn’t form a triplet,
        # drop it now so bumpers stay clear.
        non_bumper_neighbour = any(self.board[nr][nc] and self.board[nr][nc]['type'] != 'bumper'
                                   for nr, nc in self.get_neighbours(r, c))
        if self.board[r][c] is not None and adjacent_bumper_cells and not non_bumper_neighbour and len(self.find_cluster(r, c)) < 3:
            cx, cy = self.cell_to_pos(r, c)
            self.falling.append({'type': self.board[r][c]['type'], 'x': cx, 'y': cy,
                                 'vx': random.uniform(-1, 1), 'vy': -2, 'delay': 0})
            self.board[r][c] = None
            # Subtract points for balls knocked off by a bumper
            self.score = max(0, self.score - 300)  # trigger score penalty animation
            self.drop_floating()
            self.maybe_level_complete()
        
        if self.check_lose():
            self.finish_game()

    def find_empty_neighbour(self, row, col, x, y):
        best_pos = None
        min_dist_sq = float('inf')
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                r, c = row + dr, col + dc
                if 0 <= r < MAX_ROWS and 0 <= c < NUM_COLS and self.board[r][c] is None:
                    cx, cy = self.cell_to_pos(r, c)
                    dist_sq = (x - cx)**2 + (y - cy)**2
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        best_pos = (r, c)
        return best_pos

    def get_neighbours(self, r, c):
        deltas = [(0,-1),(0,1),(-1,0),(1,0)]
        if r % 2 == 0:
            deltas.extend([(-1,-1), (1,-1)])
        else:
            deltas.extend([(-1,1), (1,1)])
        
        neighbours = []
        for dr, dc in deltas:
            nr, nc = r + dr, c + dc
            if 0 <= nr < MAX_ROWS and 0 <= nc < NUM_COLS:
                neighbours.append((nr, nc))
        return neighbours

    def find_cluster(self, r, c):
        cell = self.board[r][c]
        if not cell or cell['special']: return []
        target_type = cell['type']
        
        q = [(r,c)]
        visited = set(q)
        cluster = []
        while q:
            curr_r, curr_c = q.pop(0)
            cluster.append((curr_r, curr_c))
            for nr, nc in self.get_neighbours(curr_r, curr_c):
                if (nr, nc) not in visited and self.board[nr][nc] and not self.board[nr][nc]['special'] and self.board[nr][nc]['type'] == target_type:
                    visited.add((nr, nc))
                    q.append((nr, nc))
        return cluster

    def _schedule_level_overlay(self):
        """Show next-level overlay after 2-second pause, then auto-advance after 4 s."""
        QTimer.singleShot(2000, self._begin_level_overlay)

    def _begin_level_overlay(self):
        if self.level_transition or self.game_over:
            return
        self.level_transition = True
        self.transition_score = self.score
        self.can_shoot = False
        QTimer.singleShot(7000, self._start_next_level)

    def maybe_level_complete(self):
        """Advance to next level when board cleared and falling animation finished."""
        if self.game_over or self.level_transition:
            return
        # cleared when no non-bumper balls remain
        cleared = all((self.board[r][c] is None or self.board[r][c]['type']=='bumper')
                      for r in range(MAX_ROWS) for c in range(NUM_COLS))
        if not cleared:
            return
        # last level check
        if self.level_index == len(LEVELS)-1:
            self.win = True
            self.can_shoot = False
            # Launch win celebration effects
            self.spawn_win_celebration()
            QTimer.singleShot(10000, self._after_win)
            return
        # if balls still falling (including anchored bumpers) wait until they finish
        if self.falling:
            self.awaiting_level_clear = True
            return
        # 4-minute speed bonus
        try:
            elapsed = time.time() - getattr(self, 'level_started_at', time.time())
            if elapsed < 240:
                self.score += 500
                # quick on-screen toast
                self.flash_until = time.time() + 1.5
                self.flash_intensity = 1.0
                # Store a transient banner
                self._speed_bonus_banner_until = time.time() + 1.5
        except Exception:
            pass
        # drop bumpers visually during transition
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                if self.board[r][c] and self.board[r][c]['type']=='bumper':
                    cx,cy=self.cell_to_pos(r,c)
                    self.falling.append({'type':'bumper','x':cx,'y':cy,'vx':0,'vy':0,'delay':random.randint(0,8)})
                    self.board[r][c]=None
        # award level-clear bonus
        self.score += 500
        # otherwise schedule overlay
        self._schedule_level_overlay()

    def _after_win(self):
        # Transition from win overlay to normal game over/high-score flow
        # Keep the 'WELL JOB DONE!' window until user interaction.
        # No auto-dismiss timer; progression handled by _progress_from_win.
        return

    def _progress_from_win(self):
        # Advance from win overlay into high-score/game-over flow
        if not self.win:
            return
        self.win = False
        self.drop_animating = False
        # Clear lingering celebration particles
        self.confetti.clear()
        self.fireworks.clear()
        # Stop music if playing
        try:
            if getattr(self, '_win_player', None):
                self._win_player.stop()
        except Exception:
            pass
        self.update_high_scores(self.score)
        self.game_over = True
        self.update()

    def _start_next_level(self):
        # Preserve shooter and preview balls across levels
        prev_current = self.current
        prev_next = self.next
        next_idx = (self.level_index + 1) % len(LEVELS)
        self.level_transition = False
        self.start_level(next_idx, keep_score=True)
        # Track best level reached (1-based)
        try:
            set_best_level(max(get_best_level(), next_idx + 1))
        except Exception:
            pass
        # Restore shooter ball only if new level is not introducing a special ball
        if prev_current and next_idx not in self.INTRO_INFO:
            prev_current['x'] = self.width()/2
            prev_current['y'] = self.shooter_y
            self.current = prev_current
        # Preserve preview ball only when the new level is not introducing a special ball
        if prev_next and next_idx not in self.INTRO_INFO:
            self.next = prev_next

    def drop_floating(self):
        # Cells considered "anchored" (will not drop): any cell in the top row *or* any bumper.
        connected = set()
        seed_queue = []
        # Top-row cells are always anchored.
        for c in range(NUM_COLS):
            if self.board[0][c]:
                seed_queue.append((0, c))
        # Any bumper anywhere on the board is also anchored.
        for rr in range(MAX_ROWS):
            for cc in range(NUM_COLS):
                if self.board[rr][cc] and self.board[rr][cc]['type'] == 'bumper':
                    seed_queue.append((rr, cc))
        visited = set(seed_queue)
        q = list(seed_queue)
        while q:
            r, c_ = q.pop(0)
            if (r, c_) not in connected:
                connected.add((r, c_))
                for nr, nc in self.get_neighbours(r, c_):
                    if (nr, nc) not in visited and self.board[nr][nc]:
                        visited.add((nr, nc))
                        q.append((nr, nc))
        
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                if self.board[r][c] and (r,c) not in connected:
                    cx, cy = self.cell_to_pos(r, c)
                    self.falling.append({'type': self.board[r][c]['type'], 'x': cx, 'y': cy, 'vx': 0, 'vy': 0, 'delay': random.randint(0,8)})
                    self.board[r][c] = None
                    self.score += FALL_SCORE
                    self.maybe_level_complete()
                    
    def charge_random_ball(self):
        """Randomly charge a single normal ball on the board."""
        # Suppress when overall live balls below threshold
        live = sum(1 for rr in range(MAX_ROWS) for cc in range(NUM_COLS) if self.board[rr][cc])
        if live < 5:
            return
        # Allow up to 2 charged balls, ensure new one is ≥2 cells away from others
        charged_cells = [(r,c) for r in range(MAX_ROWS) for c in range(NUM_COLS)
                         if self.board[r][c] and self.board[r][c].get('charged')]
        if len(charged_cells) >= 2:
            return
        def far_enough(r,c):
            for rr,cc in charged_cells:
                if abs(rr-r)+abs(cc-c) < 2:  # Manhattan distance <2 means adjacent/ same
                    return False
            return True
        candidates = [(r,c) for r in range(MAX_ROWS) for c in range(NUM_COLS)
                      if self.board[r][c] and not self.board[r][c]['special'] and far_enough(r,c)]
        if not candidates:
            return
        r,c = random.choice(candidates)
        self.board[r][c]['charged'] = True

    def handle_charged_blast(self, r, c):
        # Explode charged ball in radius 1
        radius = 1
        to_remove = set()
        q = [(r, c, 0)]
        visited = set([(r,c)])
        while q:
            curr_r, curr_c, dist = q.pop(0)
            to_remove.add((curr_r, curr_c))
            if dist < radius:
                for nr, nc in self.get_neighbours(curr_r, curr_c):
                    if (nr,nc) not in visited:
                        visited.add((nr,nc))
                        q.append((nr,nc, dist+1))
        removed_count = 0
        for rr, cc in to_remove:
            # Never remove bumpers – they are permanent.
            if self.board[rr][cc] and self.board[rr][cc]['type'] != 'bumper':
                cx, cy = self.cell_to_pos(rr, cc)
                self.falling.append({'type': self.board[rr][cc]['type'], 'x': cx, 'y': cy,
                                     'vx': random.uniform(-6, 6), 'vy': -4, 'delay': random.randint(0, 8)})
                self.board[rr][cc] = None
                removed_count += 1
        self.score += removed_count * BASE_SCORE * 2
        self.drop_floating()
        self.maybe_level_complete()

    def _collect_adjacent_bumpers(self, cells):
        """Bumpers are now permanent obstacles, so never include them for removal."""
        return set()

    def handle_bomb(self, r, c):
        bomb_type = self.board[r][c]['type'] if self.board[r][c] else 'bumper'
        # Dynamic radius: cue bombs get larger radius; even larger if next to a charged ball
        if bomb_type == 'cue':
            extra = 1 if any(self.board[nr][nc] and self.board[nr][nc].get('charged') for nr, nc in self.get_neighbours(r,c)) else 0
            radius = N_BOMB_RADIUS + extra
        else:
            radius = BOMB_RADIUS
        to_remove = set()
        q = [(r, c, 0)]
        visited = set([(r,c)])
        
        while q:
            curr_r, curr_c, dist = q.pop(0)
            to_remove.add((curr_r, curr_c))
            
            if dist < radius:
                 for nr, nc in self.get_neighbours(curr_r, curr_c):
                    if (nr, nc) not in visited:
                        visited.add((nr, nc))
                        q.append((nr, nc, dist + 1))

        removed_count = 0
        for rr, cc in to_remove:
            # Never remove bumpers – they are permanent.
            if self.board[rr][cc] and self.board[rr][cc]['type'] != 'bumper':
                cx, cy = self.cell_to_pos(rr, cc)
                vel_mult = 2 if bomb_type == 'cue' and extra else 1
                self.falling.append({'type': self.board[rr][cc]['type'], 'x': cx, 'y': cy,
                                     'vx': random.uniform(-2*vel_mult, 2*vel_mult), 'vy': -4*vel_mult,
                                     'delay': random.randint(0,8)})
                self.board[rr][cc] = None
                removed_count += 1
        self.score += removed_count * BASE_SCORE + (CUE_BOMB_BONUS if bomb_type=='cue' else BOMB_BONUS)
        # Trigger global wiggle effect for UI elements
        self.explosion_wiggle_until = time.time() + 0.6
        # Wiggle all balls on N-bomb explosion
        if bomb_type == 'cue':
            self.flash_all_balls(intensity=3)
        self.maybe_level_complete()
        self.drop_floating()

    def cell_to_pos(self, r, c):
        x = c * self.ball_radius * 2 + (r % 2) * self.ball_radius + self.margin_x + self.ball_radius
        top_offset = getattr(self, 'top_offset', 0)  # Get offset or default to 0
        # Position row 0 at the ceiling (top_offset - ball_radius), then add ball_radius for center
        # This simplifies to just top_offset
        y = r * self.row_height + top_offset
        return x, y

    def pos_to_cell(self, x, y):
        top_offset = getattr(self, 'top_offset', 0)
        r = int((y - top_offset) / self.row_height)
        r = max(0, min(MAX_ROWS-1, r))
        x_shifted = x - self.margin_x - (r % 2) * self.ball_radius
        c = int(x_shifted / (self.ball_radius * 2))
        c = max(0, min(NUM_COLS-1, c))
        return r, c

    def find_best_empty(self, x, y, max_y=None):
        """Return the empty cell closest to (x,y). If max_y is given,
        ignore cells whose center y-coordinate is greater (lower on screen) than max_y."""
        best_pos = None
        min_dist_sq = float('inf')
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                if self.board[r][c] is None:
                    cx, cy = self.cell_to_pos(r, c)
                    if max_y is not None and cy > max_y + self.ball_radius:
                        continue
                    dist_sq = (x - cx) ** 2 + (y - cy) ** 2
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        best_pos = (r, c)
        return best_pos

    def find_directional_empty(self, r, c, dir_x, dir_y):
        """Return empty neighbour cell of (r,c) most aligned with direction (dir_x,dir_y)."""
        inc_len = math.hypot(dir_x, dir_y)
        if inc_len == 0:
            return None
        best_dot = -1
        best_pos = None
        base_x, base_y = self.cell_to_pos(r, c)
        for nr, nc in self.get_neighbours(r, c):
            if self.board[nr][nc] is None:
                nx, ny = self.cell_to_pos(nr, nc)
                vx, vy = nx - base_x, ny - base_y
                vlen = math.hypot(vx, vy)
                if vlen == 0:
                    continue
                dot = (vx*dir_x + vy*dir_y) / (inc_len * vlen)
                if dot > best_dot:
                    best_dot = dot
                    best_pos = (nr, nc)
        return best_pos

    def paintEvent(self, event):
        painter = QPainter(self)
        bg = getattr(self, 'backgrounds', {}).get(self.level_index+1)
        if bg:
            scaled = bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled)
        else:
            painter.fillRect(self.rect(), QColor("#F0FFF8"))
        
        if self.ball_radius > 0:
            # Draw ceiling line (solid) half a ball width above row 0
            top_offset = getattr(self, 'top_offset', 0)
            ceiling_line_y = top_offset - self.ball_radius  # Half ball width above centers
            painter.setPen(QPen(self.primary_color, 2, Qt.SolidLine))  # Solid line, slightly thicker
            painter.drawLine(int(WALL_PADDING), int(ceiling_line_y), int(self.width() - WALL_PADDING), int(ceiling_line_y))
            
            # Position threshold line relative to shooter - lowered by one ball width
            # Place it 1 ball diameter above the shooter (closer to shooter)
            threshold_y = self.shooter_y - (self.ball_radius * 2 * 1.0)
            painter.setPen(QPen(self.primary_color, 1, Qt.DashLine))
            painter.drawLine(int(WALL_PADDING), int(threshold_y), int(self.width() - WALL_PADDING), int(threshold_y))
            
            draw_size = self.ball_radius*2 - PADDING*2
            offset = self.ball_radius - draw_size/2
            
            for r in range(MAX_ROWS):
                for c in range(NUM_COLS):
                    cell = self.board[r][c]
                    if cell:
                        x, y = self.cell_to_pos(r, c)
                        # Apply small jitter during flash or charged wiggle
                        jitter = 0
                        # Jiggle effect for bumpers that were recently hit
                        if cell['type'] == 'bumper' and cell.get('jiggle_until', 0) > time.time():
                            jitter += random.uniform(-3, 3)
                        # Wiggle for pending charged or cue explosions
                        if cell.get('charged') or cell['type'] == 'cue':
                            intense = self.pending_explosion and self.pending_explosion['rc'] == (r, c)
                            prob = 0.7 if intense else 0.2
                            amp  = 4 if intense else 2
                            if random.random() < prob:
                                jitter += random.uniform(-amp, amp)
                        if time.time() < self.flash_until:
                            jitter += random.uniform(-0.5 * self.flash_intensity, 0.5 * self.flash_intensity)
                        x += jitter
                        y += jitter
                        # Draw background halo for special balls
                        is_special = cell['type'] in ('pingpong','bouncy','cue') or cell.get('charged')
                        if is_special:
                            white_path = resource_path('graphics/white.png')
                            if os.path.exists(white_path):
                                white_pix = QPixmap(white_path)
                                painter.drawPixmap(int(x - draw_size/2), int(y - draw_size/2),
                                                   white_pix.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        # Draw yellow/red overlays
                        if cell.get('red_overlay') and 'red' in self.images:
                            painter.drawPixmap(int(x - draw_size/2), int(y - draw_size/2),
                                               self.images['red'].scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        if cell.get('yellow_overlay') and 'yellow' in self.images:
                            painter.drawPixmap(int(x - draw_size/2), int(y - draw_size/2),
                                               self.images['yellow'].scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        # Then draw the normal ball on top
                        pixmap = self.images.get(cell['type'])
                        if pixmap:
                            painter.drawPixmap(int(x - draw_size/2), int(y - draw_size/2), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        pixmap = self.images.get(cell['type'])
                        if pixmap:
                            painter.drawPixmap(int(x - draw_size/2), int(y - draw_size/2), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            for ball in self.falling:
                if ball.get('red_overlay') and 'red' in self.images:
                    painter.drawPixmap(int(ball['x'] - draw_size/2), int(ball['y'] - draw_size/2),
                                       self.images['red'].scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                if ball.get('yellow_overlay') and 'yellow' in self.images:
                    painter.drawPixmap(int(ball['x'] - draw_size/2), int(ball['y'] - draw_size/2),
                                       self.images['yellow'].scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                pixmap = self.images.get(ball['type'])
                if pixmap:
                    painter.drawPixmap(int(ball['x'] - draw_size/2), int(ball['y'] - draw_size/2), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            # Draw moving ball first so it appears underneath shooter overlay
            if self.moving:
                pixmap = self.images.get(self.moving['type'])
                if pixmap:
                    painter.drawPixmap(int(self.moving['x'] - draw_size/2), int(self.moving['y'] - draw_size/2), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            # stuck ball visual
            if self.stuck_ball:
                pixmap = self.images.get(self.stuck_ball['type'])
                if pixmap:
                    painter.drawPixmap(int(self.stuck_ball['x'] - draw_size/2), int(self.stuck_ball['y'] - draw_size/2), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            shooter_x, shooter_y = self.width() / 2, self.shooter_y
            # Offset the start so the line begins at the ball surface, not its centre
            start_x = shooter_x + math.cos(self.mouse_angle) * self.ball_radius
            start_y = shooter_y + math.sin(self.mouse_angle) * self.ball_radius
            end_x   = shooter_x + math.cos(self.mouse_angle) * (self.ball_radius + 40)
            end_y   = shooter_y + math.sin(self.mouse_angle) * (self.ball_radius + 40)
            painter.setPen(QPen(QColor("#3CA37B"), 3))
            painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
            
            if self.current:
                pixmap = self.images.get(self.current['type'])
                if pixmap:
                    jitter = random.uniform(-3,3) if getattr(self, 'explosion_wiggle_until', 0) > time.time() else 0
                    painter.drawPixmap(int(self.current['x'] - draw_size/2 + jitter), int(self.current['y'] - draw_size/2 + jitter), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if self.loading_ball:
                pixmap = self.images.get(self.loading_ball['type'])
                if pixmap:
                    scaled = pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    painter.save()
                    painter.translate(self.loading_ball['x'], self.loading_ball['y'])
                    painter.rotate(self.loading_ball.get('rot', 0))
                    painter.translate(-draw_size/2, -draw_size/2)
                    painter.drawPixmap(0, 0, scaled)
                    painter.restore()

            painter.setFont(self.font)
            wiggle_active = getattr(self, 'explosion_wiggle_until', 0) > time.time()
            color = QColor('#d10c0c') if self.display_score > self.score else self.primary_color
            painter.setPen(color)
            score_x, score_y = 20, self.height() - 35
            # Determine gaming level from best level reached
            try:
                best_level = get_best_level()
            except Exception:
                best_level = 0
            if best_level <= 2:
                rank = "Trainee"
            elif best_level <= 4:
                rank = "Trainer"
            elif best_level <= 6:
                rank = "Administrator"
            elif best_level <= 9:
                rank = "Ballbuster"
            else:
                rank = "Master Ballbuster"
            score_text  = f"Score: {self.display_score}"
            level_text  = f"Level: {self.level_index + 1}"
            # Compute dynamic spacing so the two labels don’t crowd each other
            score_width = painter.fontMetrics().horizontalAdvance(score_text)
            level_x_base = score_x + score_width + 40  # 40-px gap after the score
            level_x, level_y = level_x_base, self.height() - 35
            if wiggle_active:
                jitter = random.uniform(-3,3)
                score_y += jitter
                level_y += jitter
            painter.drawText(int(score_x), int(score_y), score_text)
            painter.setPen(self.primary_color)
            painter.drawText(int(level_x), int(level_y), level_text)

            if self.next:
                pixmap = self.images.get(self.next['type'])
                if pixmap:
                    preview_x = self.width() - self.ball_radius*2 - 20 
                    preview_y = self.shooter_y
                    jitter = random.uniform(-3,3) if getattr(self, 'explosion_wiggle_until', 0) > time.time() else 0
                    painter.drawPixmap(int(preview_x - draw_size/2 + jitter), int(preview_y - draw_size/2 + jitter), pixmap.scaled(draw_size, draw_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        # Draw celebration particles (confetti + fireworks)
        self.draw_celebration(painter)

        # Draw editor overlay last
        if getattr(self, 'editor_active', False):
            self.draw_editor_overlay(painter)
        if self.level_transition:
            self.draw_next_level_overlay(painter)
        elif self.win:
            self.draw_win_overlay(painter)
        elif self.game_over:
            self.draw_game_over_overlay(painter)
        
        painter.end()
        
    def check_lose(self):
        # Calculate threshold line same as in paintEvent - relative to shooter position
        threshold_y = self.shooter_y - (self.ball_radius * 2 * 1.0)
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                if self.board[r][c]:
                    _, cy = self.cell_to_pos(r, c)
                    if cy + self.ball_radius >= threshold_y:
                        self.finish_game()
                        return True
        return False

    def load_high_scores(self):
        """Load high scores from system state; fall back to defaults."""
        defaults = [("PBH", 3120, 2), ("BVR", 2000, 3), ("NVC", 2000, 2), ("EVX", 1800, 2), ("T3D", 1200, 1)]
        scores = get_high_scores()
        return scores if scores else defaults

    def save_high_scores(self):
        set_high_scores(self.high_scores)

    def update_high_scores(self, current_score):
        """Check if *current_score* qualifies and prompt for initials."""
        if current_score <= 0:
            return
        if self.high_score_recorded:
            return
        # Determine if the new score makes the leaderboard
        qualifies = (len(self.high_scores) < 5) or (current_score > self.high_scores[-1][1])
        if not qualifies:
            return

        # Switch to inline initials entry mode
        self.entering_initials = True
        self.setFocus()
        self.initial_chars = ["", "", ""]
        self.initial_index = 0
        self.pending_score = current_score
        self.pending_level = self.level_index + 1
        self.game_over = True  # ensure overlay shows

    def finish_game(self):
        # Drop all remaining balls for a satisfying splash animation
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                if self.board[r][c]:
                    cx, cy = self.cell_to_pos(r, c)
                    self.falling.append({
                        'type': self.board[r][c]['type'],
                        'x': cx,
                        'y': cy,
                        'vx': random.uniform(-2, 2),
                        'vy': -4, 'delay': random.randint(0,8)
                    })
                    self.board[r][c] = None

        # Mark that we are waiting for all falling balls to clear before showing overlay
        self.drop_animating = True
        self.game_over = False
        self.update_high_scores(self.score)

    def flash_all_balls(self, intensity=1):
        '''Trigger a brief jiggle effect on all on-screen balls.
           intensity controls how much the balls jiggle.'''
        self.flash_intensity = max(1, intensity)
        self.flash_until = time.time() + 0.25 + 0.025 * intensity

    def do_super_blast(self, cluster):
        '''Power-up that removes the given cluster with bonus points and falling animation.'''
        self.super_blast_active = True
        self.score += len(cluster) * BASE_SCORE * 2
        for rr, cc in cluster:
            x, y = self.cell_to_pos(rr, cc)
            self.falling.append({
                'type': self.board[rr][cc]['type'],
                'x': x,
                'y': y,
                'vx': random.uniform(-4, 4),
                'vy': random.uniform(-6, -3)
            })
            self.board[rr][cc] = None
        self.maybe_level_complete()
        self.drop_floating()
        self.clear_streak = 0
        self.super_blast_active = False

    def draw_next_level_overlay(self, painter):
        # Increment animation counter
        self.overlay_anim_counter = getattr(self, 'overlay_anim_counter', 0) + 1
        dlg_w, dlg_h = 300, 220
        dlg_x = (self.width() - dlg_w)/2
        dlg_y = (self.height() - dlg_h)/2
        rect = QRectF(dlg_x, dlg_y, dlg_w, dlg_h)

        painter.setBrush(QColor('#f7f7f7'))
        painter.setPen(QPen(QColor('#c5c5c5'), 1))
        painter.drawRoundedRect(rect, 6, 6)

        painter.setPen(self.primary_color)
        font = QFont('Segoe UI', 20, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(dlg_x, dlg_y+15, dlg_w, 30), Qt.AlignCenter, 'NEXT LEVEL')

        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(QRectF(dlg_x, dlg_y+60, dlg_w, 24), Qt.AlignCenter, f'Score: {self.transition_score}')

        # ── Introduction of new ball (levels 1-5) ─────────────────────
        next_lvl = self.level_index + 1
        intro = self.INTRO_INFO.get(next_lvl)
        if intro:
            # Title
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(dlg_x, dlg_y+90, dlg_w, 20), Qt.AlignCenter, intro['name'])
            # Draw icon
            icon_type = intro['type']
            pix = self.images.get(icon_type)
            if pix:
                icon_size = 40
                icon_x = int(dlg_x + (dlg_w - icon_size)/2)
                icon_y = int(dlg_y + 120)
                # Animation per type
                if icon_type == 'pingpong':
                    cycle = self.cycle_types
                    idx = (self.overlay_anim_counter // 30) % len(cycle)
                    pix = self.images.get(cycle[idx], pix)
                elif intro.get('charged') == True:
                    # Jitter
                    jitter = (-2 if (self.overlay_anim_counter//6)%2 else 2)
                    icon_x += jitter; icon_y += jitter
                elif icon_type == 'cue':
                    # Flash on/off
                    if (self.overlay_anim_counter//12)%2 == 1:
                        painter.setOpacity(0.35)
                painter.drawPixmap(icon_x, icon_y, pix.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                painter.setOpacity(1.0)
            # Description text
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(QRectF(dlg_x+10, dlg_y+180, dlg_w-20, 30), Qt.AlignCenter | Qt.TextWordWrap, intro['description'])
        else:
            font.setPointSize(11)
            painter.setFont(font)
            # Dynamic motivational messages after unlocking all specials (level >=5)
            if self.level_index >= 4:
                messages = [
                    "Oh my... no one was supposed to get this far",
                    "Only a few levels left - do you got what it takes?",
                    "Should have finished the game if I knew you were going to get this far",
                    "Will you be  the next Master Ballbuster!?",
                ]
                msg = messages[(self.level_index - 4) % len(messages)]
            else:
                msg = 'Get ready...'
            # Add generous margins and word-wrap for readability
            text_rect = QRectF(dlg_x + 16, dlg_y + 92, dlg_w - 32, 46)
            painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, msg)

    def draw_win_overlay(self, painter):
        dlg_w = 360
        dlg_h = 240
        dlg_x = (self.width() - dlg_w)/2
        dlg_y = (self.height() - dlg_h)/2
        rect = QRectF(dlg_x, dlg_y, dlg_w, dlg_h)
        painter.setBrush(QColor('#f7f7f7'))
        painter.setPen(QPen(QColor('#c5c5c5'), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(self.primary_color)
        font = QFont("Segoe UI", 20, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(dlg_x, dlg_y+15, dlg_w, 32), Qt.AlignCenter, "WELL JOB DONE!")
        # draw vibe image if loaded
        pix = self.images.get('well')
        if pix:
            max_w = dlg_w - 40
            max_h = dlg_h - 80
            scaled = pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(dlg_x + (dlg_w - scaled.width())/2), int(dlg_y + 70), scaled)
        # Play celebratory music once when the win overlay first appears
        if not getattr(self, 'win_music_played', False):
            self.win_music_played = True
            try:
                from utils.resources import resource_path
                # Use a single MP3 asset: paradise.mp3
                candidates = ['paradise.mp3', 'Paradise.mp3', 'PARADISE.MP3']
                audio_path = ''
                for name in candidates:
                    p = resource_path(name)
                    if os.path.exists(p):
                        audio_path = p
                        break
                if audio_path:
                    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
                    from PyQt5.QtCore import QUrl
                    self._win_player = getattr(self, '_win_player', QMediaPlayer(self))
                    self._win_player.setMedia(QMediaContent(QUrl.fromLocalFile(audio_path)))
                    self._win_player.setVolume(80)
                    self._win_player.play()
            except Exception:
                pass

    def draw_game_over_overlay(self, painter):
        # centered dialog box like settings UI (no dark overlay)
        dlg_w = 360
        dlg_h = 240
        dlg_x = (self.width() - dlg_w)/2
        dlg_y = (self.height() - dlg_h)/2
        dialog_rect = QRectF(dlg_x, dlg_y, dlg_w, dlg_h)

        painter.setBrush(QColor('#f7f7f7'))
        painter.setPen(QPen(QColor('#c5c5c5'), 1))
        painter.drawRoundedRect(dialog_rect, 6, 6)

        painter.setPen(self.primary_color)
        title_font = QFont("Segoe UI", 20, QFont.Bold)
        painter.setFont(title_font)

        if self.entering_initials:
            # Title
            painter.drawText(QRectF(dlg_x, dlg_y+15, dlg_w, 32), Qt.AlignCenter, "NEW HIGH SCORE")
            # Sub text
            sub_font = QFont("Segoe UI", 12, QFont.Bold)
            painter.setFont(sub_font)
            painter.drawText(QRectF(dlg_x, dlg_y+55, dlg_w, 24), Qt.AlignCenter, "Enter Initials")
            # Draw 3 boxes
            box_w = 60
            box_h = 80
            spacing = 10
            total_w = box_w*3 + spacing*2
            start_x = dlg_x + (dlg_w - total_w)/2
            y = dlg_y + 90
            box_font = QFont("Segoe UI", 32, QFont.Bold)
            for i in range(3):
                rect = QRectF(start_x + i*(box_w+spacing), y, box_w, box_h)
                painter.setPen(QPen(self.primary_color, 2))
                painter.drawRect(rect)
                char = self.initial_chars[i]
                if char:
                    painter.setFont(box_font)
                    painter.drawText(rect, Qt.AlignCenter, char)
            return  # skip normal overlay until initials entered
        # ── Normal Game-Over overlay ───────────────────────────
        # centered dialog box like settings UI (no dark overlay)
        dlg_w = 360
        dlg_h = 240
        dlg_x = (self.width() - dlg_w)/2
        dlg_y = (self.height() - dlg_h)/2
        dialog_rect = QRectF(dlg_x, dlg_y, dlg_w, dlg_h)

        painter.setBrush(QColor('#f7f7f7'))
        painter.setPen(QPen(QColor('#c5c5c5'), 1))
        painter.drawRoundedRect(dialog_rect, 6, 6)

        painter.setPen(self.primary_color)
        font = QFont("Segoe UI", 20, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(dlg_x, dlg_y+15, dlg_w, 32), Qt.AlignCenter, "GAME OVER!")
        
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QRectF(dlg_x, dlg_y+55, dlg_w, 24), Qt.AlignCenter, "High Scores")

        font.setPointSize(11)
        painter.setFont(font)
        left_col_w = 200  # width reserved for score list column
        y_offset = dlg_y + 95
        for i, (name, score, level) in enumerate(self.high_scores):
            text = f"{i+1}. {name:<3} - {score:>4}  LVL {level}"
            painter.drawText(QRectF(dlg_x + 20, y_offset + i * 22, left_col_w - 40, 22), Qt.AlignLeft | Qt.AlignVCenter, text)

        button_w, button_h = 110, 40
        # two-column layout: list left, buttons right
        col_gap = 20
        right_x = dlg_x + left_col_w + col_gap
        button_y_start = dlg_y + 100

        self.restart_button_rect = QRectF(right_x, button_y_start, button_w, button_h)
        self.exit_button_rect = QRectF(right_x, button_y_start + button_h + 10, button_w, button_h)
        
        hover_restart = self.restart_button_rect.contains(self.mapFromGlobal(QCursor.pos()))
        hover_exit = self.exit_button_rect.contains(self.mapFromGlobal(QCursor.pos()))
        self.draw_styled_button(painter, self.restart_button_rect, "Restart", self.primary_color, hover_restart)
        self.draw_styled_button(painter, self.exit_button_rect, "Exit", self.primary_color, hover_exit)

    def draw_styled_button(self, painter, rect, text, base_color: QColor, hover=False):
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if hover:
            gradient.setColorAt(0, base_color.lighter(150))
            gradient.setColorAt(1, base_color.darker(110))
        else:
            gradient.setColorAt(0, base_color.lighter(120))
            gradient.setColorAt(1, base_color.darker(120))

        painter.setBrush(gradient)
        painter.setPen(QPen(base_color.darker(130), 1))
        painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(Qt.white)
        font = QFont("Segoe UI", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, text) 

    # ─────────────────────────────────────────────────────────
    #  Level Editor helpers
    # ─────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────
    #  Celebration effects (confetti + fireworks)
    # ─────────────────────────────────────────────────────────
    def spawn_win_celebration(self):
        # Single celebratory burst (original behavior)
        self.confetti.clear()
        self.fireworks.clear()
        self._spawn_confetti_burst()
        self._spawn_firework_burst()

    def _spawn_confetti_burst(self):
        width = self.width()
        for i in range(180):
            x = random.uniform(0, width)
            y = -10
            vx = random.uniform(-1.8, 1.8)
            vy = random.uniform(2.2, 4.6)
            color = QColor(random.randint(40,255), random.randint(40,255), random.randint(40,255))
            self.confetti.append({'x': x, 'y': y, 'vx': vx, 'vy': vy, 'spin': random.uniform(-8,8), 'angle': random.uniform(0,360), 'color': color, 'life': random.randint(140, 260)})

    def _spawn_firework_burst(self):
        cx = random.uniform(self.width()*0.2, self.width()*0.8)
        cy = self.height()*0.9
        for k in range(120):
            ang = random.uniform(0, 2*math.pi)
            speed = random.uniform(2.5, 6.5)
            vx = math.cos(ang) * speed
            vy = -abs(math.sin(ang)) * speed
            color = QColor(random.randint(120,255), random.randint(120,255), random.randint(120,255))
            self.fireworks.append({'x': cx, 'y': cy, 'vx': vx, 'vy': vy, 'life': random.randint(50, 120), 'color': color})

    def trigger_fireworks_cheat(self):
        # On-demand fireworks test
        self.fireworks.clear()
        cx = self.width()/2
        cy = self.height()*0.85
        for k in range(120):
            ang = random.uniform(0, 2*math.pi)
            speed = random.uniform(2.5, 6.0)
            vx = math.cos(ang) * speed
            vy = -abs(math.sin(ang)) * speed
            color = QColor(random.randint(120,255), random.randint(120,255), random.randint(120,255))
            self.fireworks.append({'x': cx, 'y': cy, 'vx': vx, 'vy': vy, 'life': random.randint(50, 110), 'color': color})

    def update_celebration(self):
        # Gravity and fade for confetti
        next_confetti = []
        for p in self.confetti:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.08
            p['angle'] += p['spin']
            p['life'] -= 1
            if p['life'] > 0 and p['y'] < self.height() + 20:
                next_confetti.append(p)
        self.confetti = next_confetti
        # Fireworks sparks update
        next_fw = []
        for s in self.fireworks:
            s['x'] += s['vx']
            s['y'] += s['vy']
            s['vy'] += 0.05
            s['life'] -= 1
            if s['life'] > 0:
                next_fw.append(s)
        self.fireworks = next_fw

    def draw_celebration(self, painter: QPainter):
        # Draw confetti as small rotated rectangles
        painter.save()
        for p in self.confetti:
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(p['color'])
            size = 6
            painter.translate(float(p['x']), float(p['y']))
            painter.rotate(float(p['angle']))
            painter.drawRect(int(-size/2), int(-size/2), int(size), int(size/2))
            painter.restore()
        # Draw fireworks as glowing points
        for s in self.fireworks:
            c = QColor(s['color'])
            alpha = max(30, min(255, s['life'] * 3))
            c.setAlpha(alpha)
            painter.setPen(QPen(c, 3))
            painter.drawPoint(int(s['x']), int(s['y']))
        painter.restore()
    def toggle_editor(self):
        self.editor_active = not getattr(self, 'editor_active', False)
        if self.editor_active:
            # Build an empty mask for the current grid
            self.editor_mask = [[False for _ in range(NUM_COLS)] for _ in range(MAX_ROWS)]
            self.editor_dirty = False
            # Freeze gameplay state
            self.moving = None
            self.loading = False
            self.can_shoot = False
        else:
            # Exit editor – allow shooting again
            self.can_shoot = True
        self.update()

    def editor_click(self, pos):
        # Toggle the cell under cursor in editor
        r, c = self.pos_to_cell(pos.x(), pos.y())
        if 0 <= r < MAX_ROWS and 0 <= c < NUM_COLS:
            curr = self.editor_mask[r][c]
            # Cycle: None -> True (ball) -> None (clear) unless bumper already set
            if curr == 'bumper':
                self.editor_mask[r][c] = None
            else:
                self.editor_mask[r][c] = (not bool(curr))
            self.editor_dirty = True
            self.update()

    def draw_editor_overlay(self, painter: QPainter):
        # Grid overlay and toggled cell highlights
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        cell_size = self.ball_radius * 2
        # Draw grid
        grid_color = QColor(0, 0, 0, 40)
        painter.setPen(QPen(grid_color, 1, Qt.SolidLine))
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                x, y = self.cell_to_pos(r, c)
                rect_x = int(x - self.ball_radius)
                rect_y = int(y - self.ball_radius)
                painter.drawRect(rect_x, rect_y, cell_size, cell_size)
        # Draw active cells mask
        on_color = QColor(60, 163, 123, 90)
        bumper_color = QColor(220, 80, 47, 160)
        for r in range(MAX_ROWS):
            for c in range(NUM_COLS):
                x, y = self.cell_to_pos(r, c)
                rect_x = int(x - self.ball_radius)
                rect_y = int(y - self.ball_radius)
                val = self.editor_mask[r][c]
                if val == 'bumper':
                    painter.fillRect(rect_x+1, rect_y+1, cell_size-2, cell_size-2, bumper_color)
                elif val:
                    painter.fillRect(rect_x+1, rect_y+1, cell_size-2, cell_size-2, on_color)
        # Draw toolbar hints only when cheats are enabled
        if getattr(self, 'cheats_enabled', False):
            painter.setPen(self.primary_color)
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(10, 22, f"Editor L{self.level_index+1}: Click to toggle ball  |  B = bumper  |  Ctrl+S = Save  |  E = exit")
        painter.restore()

    def keyReleaseEvent(self, event):
        # Capture Ctrl+S for saving in editor
        if getattr(self, 'editor_active', False) and event.key() == Qt.Key_S and (event.modifiers() & Qt.ControlModifier):
            self.save_editor_level()
            return
        super().keyReleaseEvent(event)

    def save_editor_level(self):
        # Build a level pattern from the mask: True -> random ball placeholder, 'bumper' -> bumper, None -> empty
        pattern = []
        for r in range(MAX_ROWS):
            row = []
            for c in range(NUM_COLS):
                val = self.editor_mask[r][c]
                if val == 'bumper':
                    row.append('bumper')
                else:
                    # Use boolean placeholders; each True becomes a random colour when applied
                    row.append(True if val else None)
            pattern.append(row)
        # Save to levels file
        # Update in-memory masks dictionary using 1-based level key
        CUSTOM_LEVEL_MASKS[str(self.level_index+1)] = pattern
        # Persist to disk (merge-friendly structure)
        out = { 'levels': CUSTOM_LEVEL_MASKS }
        try:
            with open(CUSTOM_LEVELS_FILE, 'w') as f:
                json.dump(out, f, indent=2)
            logger.info(f"Saved custom level {self.level_index+1} to {CUSTOM_LEVELS_FILE}")
            # Also apply immediately for preview
            self.apply_editor_level(pattern)
            # Reload persisted masks in case of external edits
            _load_custom_levels()
        except Exception as e:
            logger.error(f"Failed to save custom level: {e}")
        self.update()

    def apply_editor_level(self, pattern):
        # Replace current board with the editor pattern
        self.board = []
        for r in range(MAX_ROWS):
            row_pat = pattern[r] if r < len(pattern) else []
            if len(row_pat) < NUM_COLS:
                left_pad = (NUM_COLS - len(row_pat)) // 2
                row_pat = [None]*left_pad + row_pat + [None]*(NUM_COLS - left_pad - len(row_pat))
            else:
                row_pat = row_pat[:NUM_COLS]
            new_row = []
            for t in row_pat:
                if t == 'bumper':
                    new_row.append({'type': 'bumper', 'special': True})
                elif t:
                    # Any truthy placeholder becomes a random ball colour (not special)
                    rand_type = random.choice([f'ball{i}' for i in range(1,9)])
                    new_row.append({'type': rand_type, 'special': False})
                else:
                    new_row.append(None)
            self.board.append(new_row)
        # Disable next/specials while editing preview
        self.available_types = [f'ball{i}' for i in range(1,9)]
        self.current = self.create_ball(random.choice(self.available_types))
        self.next = self.create_ball(random.choice(self.available_types))
        self.update()