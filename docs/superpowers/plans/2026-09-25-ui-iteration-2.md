# UI Iteration 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give NVC two window modes (Compact / Full window), VIO's leaf card on every tool tab, a three-tier button hierarchy replacing the all-bubble look, a slick PC Report tab with a pulsing heart, compact Media Player / Lossless Editor / Recorder controls, and fix the defects carried over from the last report.

**Architecture:** `ui/theme.py` stays the single source of layout metrics and button-tier stylesheets; new `ui/leaf_frame.py` and `ui/glyph_icons.py` are small pure-Qt helpers. `VideoConverterApp.set_window_mode()` is the one place that changes mode: it updates theme metrics, resizes the window, and calls `apply_layout_mode(metrics)` on each tool widget that defines it. Tool widgets stop taking the gradient style from `apply_to_buttons` by opting out and applying their own tier styles.

**Tech Stack:** Python 3.12, PyQt5, pytest (headless via `tests/conftest.py`), ruff.

Spec: `docs/superpowers/specs/2026-09-25-ui-iteration-2-design.md`. Repo: `D:\Python Projects\NVC 4`, branch `ui-iteration-2`, merge target `master`.

## Global Constraints

- Never `QTimer.singleShot`; use a `QTimer(self)` object with `setSingleShot(True)` (the AST guard in `tests/test_qt_object_ownership.py` enforces this).
- `_tr()` takes plain string literals only.
- Tests are headless: import `tests/conftest.py` fixtures implicitly by living under `tests/`; construct widgets with a `QApplication` from `conftest`.
- Pass signal for a task: `python -m pytest -q -p no:cacheprovider <files>` exit 0, then the full suite `python -m pytest -q -p no:cacheprovider` exit 0.
- `python -m ruff check <touched files>` clean. `ui/main_window.py` has ~109 pre-existing findings: run ruff on it with `--diff` only for lines you added; do not fix old findings.
- Never commit real identifying values from this machine (user name, machine name, device names, personal paths). Use `C:\Videos`, `Camera A`, `Microphone A` as stand-ins in tests.
- Copy for new UI strings is exactly as written in the spec/tasks; wrap in `_tr()`.
- Keep the existing attribute names tests use (`play_btn`, `stop_btn`, `mute_btn`, `playlist_btn`, `load_btn`, `clear_btn`, `add_files_btn`, `add_folder_btn`, `remove_btn`, `source_group`, `output_group`, `btn_run`, `btn_open`, `btn_folder`).
- Do not touch `docs/help/**` or `virtual_iobox/**` (out of scope; VIO is a different repo anyway).
- Commit after each task with the message given; one task = one commit unless the task says otherwise.

---

### Task 1: Theme foundations — layout metrics, button tiers, leaf QSS, `window_mode` setting

**Files:**
- Modify: `ui/theme.py` (append after `preview_overlay_button_style`, before the `qss()` helper)
- Modify: `utils/config.py` (`default_settings`, `normalize_settings`)
- Test: `tests/test_theme.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `theme.LayoutMetrics`, `theme.COMPACT`, `theme.FULL`, `theme.metrics() -> LayoutMetrics`, `theme.set_layout_mode(name: str) -> LayoutMetrics`, `theme.LAYOUT_MODES = ("compact", "full")`, `theme.compact_button_style(radius=RADIUS_SM) -> str`, `theme.link_button_style() -> str`, `theme.icon_button_style(size: int = 28) -> str`, `theme.leaf_radii(radius: int) -> str`, `theme.leaf_style(radius: int = 28, dashed: bool = False) -> str`; settings key `window_mode`.

- [ ] **Step 1: Failing tests**

Append to `tests/test_theme.py`:

```python
class LayoutMetricsTests(unittest.TestCase):
    def tearDown(self):
        theme.set_layout_mode("compact")

    def test_default_mode_is_compact(self):
        self.assertEqual(theme.metrics().name, "compact")

    def test_set_layout_mode_round_trips_and_rejects_unknown(self):
        self.assertEqual(theme.set_layout_mode("full").name, "full")
        self.assertEqual(theme.metrics(), theme.FULL)
        with self.assertRaises(ValueError):
            theme.set_layout_mode("huge")
        self.assertEqual(theme.metrics().name, "full")

    def test_metrics_grow_in_full_mode(self):
        self.assertGreater(theme.FULL.margin, theme.COMPACT.margin)
        self.assertGreater(theme.FULL.recorder_tile_max_h, theme.COMPACT.recorder_tile_max_h)
        self.assertTrue(theme.COMPACT.recorder_stacked)
        self.assertFalse(theme.FULL.recorder_stacked)


class ButtonTierTests(unittest.TestCase):
    def test_compact_button_has_small_height_and_no_min_width(self):
        style = theme.compact_button_style()
        self.assertIn("min-height: 24px", style)
        self.assertNotIn("min-width", style)
        self.assertIn("QPushButton:disabled", style)

    def test_link_button_is_underlined_and_transparent(self):
        style = theme.link_button_style()
        self.assertIn("text-decoration: underline", style)
        self.assertIn("background: transparent", style)
        self.assertIn("border: none", style)

    def test_icon_button_targets_tool_buttons(self):
        style = theme.icon_button_style(28)
        self.assertIn("QToolButton", style)
        self.assertIn("min-width: 28px", style)
        self.assertIn("QToolButton:hover", style)


class LeafStyleTests(unittest.TestCase):
    def test_leaf_radii_round_only_top_left_and_bottom_right(self):
        radii = theme.leaf_radii(28)
        self.assertIn("border-top-left-radius: 28px", radii)
        self.assertIn("border-bottom-right-radius: 28px", radii)
        self.assertIn("border-top-right-radius: 0px", radii)
        self.assertIn("border-bottom-left-radius: 0px", radii)

    def test_leaf_style_solid_and_dashed(self):
        self.assertIn("1px solid", theme.leaf_style(28))
        self.assertIn("1px dashed", theme.leaf_style(18, dashed=True))
        self.assertIn("QFrame#leaf", theme.leaf_style(28))
```

Append to `tests/test_config.py` (inside the existing test class or a new one that imports `default_settings, normalize_settings`):

```python
    def test_window_mode_defaults_to_compact(self):
        self.assertEqual(default_settings["window_mode"], "compact")
        self.assertEqual(normalize_settings({})["window_mode"], "compact")

    def test_window_mode_normalises_unknown_values(self):
        self.assertEqual(normalize_settings({"window_mode": "full"})["window_mode"], "full")
        self.assertEqual(normalize_settings({"window_mode": "FULL"})["window_mode"], "full")
        self.assertEqual(normalize_settings({"window_mode": "giant"})["window_mode"], "compact")
        self.assertEqual(normalize_settings({"window_mode": 3})["window_mode"], "compact")
```

- [ ] **Step 2: Run, expect failure**

`python -m pytest -q -p no:cacheprovider tests/test_theme.py tests/test_config.py` → AttributeError / KeyError.

- [ ] **Step 3: Implement in `ui/theme.py`**

Add `from dataclasses import dataclass` if not already imported (the file already defines `Skin` as a dataclass; reuse that import). Append:

```python
# ---------------------------------------------------------------------------
# Layout modes. "compact" is the historical window; "full" is maximised with
# roomier metrics. The main window owns switching; widgets read metrics().
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LayoutMetrics:
    name: str
    margin: int
    spacing: int
    recorder_tile_max_h: int
    recorder_stacked: bool
    player_panel_min_h: int
    pc_report_logo_w: int


COMPACT: Final[LayoutMetrics] = LayoutMetrics("compact", 6, 4, 98, True, 160, 96)
FULL: Final[LayoutMetrics] = LayoutMetrics("full", 12, 8, 260, False, 240, 140)
LAYOUT_MODES: Final[tuple[str, ...]] = (COMPACT.name, FULL.name)
_layout_by_name: Final[dict[str, LayoutMetrics]] = {COMPACT.name: COMPACT, FULL.name: FULL}
_current_layout: LayoutMetrics = COMPACT


def metrics() -> LayoutMetrics:
    """The layout metrics for the current window mode."""
    return _current_layout


def set_layout_mode(name: str) -> LayoutMetrics:
    """Select the window mode by name. Raises ValueError for unknown names."""
    global _current_layout
    try:
        _current_layout = _layout_by_name[name]
    except KeyError:
        raise ValueError(f"unknown layout mode {name!r}; expected one of {LAYOUT_MODES}") from None
    return _current_layout


# ---------------------------------------------------------------------------
# Button tiers below the primary gradient bubble. Tool tabs opt out of
# apply_to_buttons() and pick one of these.
# ---------------------------------------------------------------------------
def compact_button_style(radius: int = RADIUS_SM) -> str:
    """A small filled action button for tool tabs (24 px tall, sized to its label)."""
    s = skin()
    return (
        f"QPushButton {{ background-color: {s.accent}; color: {s.text_on_accent}; "
        f"border: 1px solid {s.accent_dark}; border-radius: {radius}px; "
        f"padding: 3px 10px; min-height: 24px; font-family: {FONT_UI}; "
        f"font-size: 9pt; font-weight: 600; }} "
        f"QPushButton:hover {{ background-color: {s.accent_hover}; }} "
        f"QPushButton:pressed {{ background-color: {s.accent_pressed}; }} "
        f"QPushButton:disabled {{ background-color: {s.separator}; "
        f"border-color: {s.separator}; color: {s.text_disabled}; }}"
    )


def link_button_style() -> str:
    """A text link masquerading as a button: no chrome, underlined accent text."""
    s = skin()
    return (
        f"QPushButton {{ background: transparent; color: {s.accent_dark}; border: none; "
        f"text-decoration: underline; padding: 0px; min-width: 0px; min-height: 0px; "
        f"font-family: {FONT_UI}; font-size: 9pt; text-align: left; }} "
        f"QPushButton:hover {{ color: {s.accent_deep}; }} "
        f"QPushButton:disabled {{ color: {s.text_disabled}; text-decoration: none; }}"
    )


def icon_button_style(size: int = 28) -> str:
    """A flat square QToolButton that tints on hover; icon supplied by glyph_icons."""
    s = skin()
    return (
        f"QToolButton {{ background: transparent; border: none; border-radius: {RADIUS_SM}px; "
        f"min-width: {size}px; max-width: {size}px; min-height: {size}px; max-height: {size}px; "
        f"padding: 0px; }} "
        f"QToolButton:hover {{ background: {s.accent_tint}; }} "
        f"QToolButton:pressed, QToolButton:checked {{ background: {rgba(s.accent, 0.25)}; }} "
        f"QToolButton:disabled {{ background: transparent; }} "
        f"QToolButton::menu-indicator {{ image: none; }}"
    )


# ---------------------------------------------------------------------------
# The leaf: VIO's silhouette with the top-left and bottom-right corners
# rounded and the other two square.
# ---------------------------------------------------------------------------
def leaf_radii(radius: int) -> str:
    return (f"border-top-left-radius: {radius}px; border-bottom-right-radius: {radius}px; "
            f"border-top-right-radius: 0px; border-bottom-left-radius: 0px;")


def leaf_style(radius: int = 28, dashed: bool = False) -> str:
    """QSS for a LeafFrame (objectName 'leaf')."""
    s = skin()
    border = f"1px dashed {s.accent}" if dashed else f"1px solid {s.separator}"
    return (f"QFrame#leaf {{ background: {s.panel_bg}; border: {border}; "
            f"{leaf_radii(radius)} }}")
```

Check the `Skin` dataclass has `accent_dark`, `accent_deep`, `accent_tint`, `text_disabled`, `separator`, `panel_bg`; the recorder's inline link QSS already uses `$accent_dark` / `$accent_deep`, and `secondary_button_style` uses `accent_tint`. If a name differs, use the existing field name and keep the test expectations.

- [ ] **Step 4: Implement in `utils/config.py`**

In `default_settings`, after `"close_on_x": True,` add:

```python
    "window_mode": "compact",
```

In `normalize_settings`, before `return normalized`, add:

```python
    mode = normalized.get("window_mode")
    mode = mode.strip().lower() if isinstance(mode, str) else ""
    normalized["window_mode"] = mode if mode in ("compact", "full") else "compact"
```

- [ ] **Step 5: Run, expect pass; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_theme.py tests/test_config.py
python -m ruff check ui/theme.py utils/config.py tests/test_theme.py tests/test_config.py
git add ui/theme.py utils/config.py tests/test_theme.py tests/test_config.py
git commit -m "feat(theme): layout metrics, compact/link/icon button tiers, leaf QSS, window_mode setting"
```

---

### Task 2: `ui/glyph_icons.py` — painted, tintable icons

**Files:**
- Create: `ui/glyph_icons.py`
- Test: `tests/test_glyph_icons.py`

**Interfaces:**
- Produces: `glyph_icon(name: str, color: str, size: int = 20) -> QIcon`; `GLYPHS: tuple[str, ...]` = `("play", "pause", "stop", "restart", "fullscreen", "playlist", "volume", "muted", "add_file", "add_folder", "remove", "clear", "folder_open", "report", "shield")`; `make_icon_button(name, tooltip, color, size=28, parent=None) -> QToolButton` (styled with `theme.icon_button_style(size)`, icon size `size - 8`, `setAutoRaise(True)`, `Qt.PointingHandCursor`).

- [ ] **Step 1: Failing test**

```python
# tests/test_glyph_icons.py
import unittest

from PyQt5.QtGui import QColor

from ui import glyph_icons


def _opaque_pixels(pixmap):
    image = pixmap.toImage()
    return sum(
        1
        for x in range(image.width())
        for y in range(image.height())
        if QColor(image.pixel(x, y)).alpha() > 0 and image.pixelColor(x, y).alpha() > 0
    )


class GlyphIconTests(unittest.TestCase):
    def test_every_glyph_renders_something(self):
        for name in glyph_icons.GLYPHS:
            pixmap = glyph_icons.glyph_icon(name, "#43a296", 20).pixmap(20, 20)
            self.assertFalse(pixmap.isNull(), name)
            self.assertGreater(_opaque_pixels(pixmap), 8, name)

    def test_unknown_glyph_raises(self):
        with self.assertRaises(KeyError):
            glyph_icons.glyph_icon("banana", "#000000")

    def test_make_icon_button_is_square_tool_button(self):
        button = glyph_icons.make_icon_button("play", "Play all", "#43a296", size=28)
        self.assertEqual(button.toolTip(), "Play all")
        self.assertFalse(button.icon().isNull())
        self.assertEqual(button.text(), "")
        self.assertIn("QToolButton", button.styleSheet())
```

- [ ] **Step 2: Run, expect ImportError**

- [ ] **Step 3: Implement**

```python
# ui/glyph_icons.py
"""Small vector glyphs painted at runtime so they tint with the skin.

The repository ships only skin-prefixed .ico files (bare / GREEN / GRAYSCALE)
for its big chrome icons; tool-tab controls need a dozen tiny glyphs in the
accent colour, which is cheaper to paint than to maintain as 36 bitmaps.
"""
from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QToolButton

from ui import theme

GLYPHS: tuple[str, ...] = (
    "play", "pause", "stop", "restart", "fullscreen", "playlist", "volume", "muted",
    "add_file", "add_folder", "remove", "clear", "folder_open", "report", "shield",
)


def _pen(color: QColor, width: float = 1.8) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _paint(name: str, painter: QPainter, s: float, color: QColor) -> None:
    """Draw `name` into a s x s box. Coordinates are fractions of s."""
    def P(x, y):
        return QPointF(x * s, y * s)

    def R(x, y, w, h):
        return QRectF(x * s, y * s, w * s, h * s)

    painter.setPen(_pen(color, max(1.4, s * 0.09)))
    painter.setBrush(color)
    if name == "play":
        painter.drawPolygon(QPolygonF([P(0.28, 0.18), P(0.80, 0.50), P(0.28, 0.82)]))
    elif name == "pause":
        painter.drawRoundedRect(R(0.24, 0.20, 0.18, 0.60), 1.5, 1.5)
        painter.drawRoundedRect(R(0.58, 0.20, 0.18, 0.60), 1.5, 1.5)
    elif name == "stop":
        painter.drawRoundedRect(R(0.24, 0.24, 0.52, 0.52), 2, 2)
    elif name == "restart":
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(R(0.22, 0.22, 0.56, 0.56), 40 * 16, 280 * 16)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([P(0.66, 0.12), P(0.84, 0.30), P(0.60, 0.34)]))
    elif name == "fullscreen":
        painter.setBrush(Qt.NoBrush)
        for (x, y, dx, dy) in ((0.2, 0.2, 1, 1), (0.8, 0.2, -1, 1), (0.2, 0.8, 1, -1), (0.8, 0.8, -1, -1)):
            painter.drawLine(P(x, y), P(x + 0.18 * dx, y))
            painter.drawLine(P(x, y), P(x, y + 0.18 * dy))
    elif name == "playlist":
        painter.setBrush(Qt.NoBrush)
        for y in (0.28, 0.50, 0.72):
            painter.drawLine(P(0.22, y), P(0.62, y))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([P(0.68, 0.40), P(0.84, 0.50), P(0.68, 0.60)]))
    elif name in ("volume", "muted"):
        painter.drawPolygon(QPolygonF([P(0.18, 0.40), P(0.34, 0.40), P(0.50, 0.24), P(0.50, 0.76), P(0.34, 0.60), P(0.18, 0.60)]))
        painter.setBrush(Qt.NoBrush)
        if name == "volume":
            painter.drawArc(R(0.40, 0.30, 0.40, 0.40), -60 * 16, 120 * 16)
            painter.drawArc(R(0.34, 0.20, 0.60, 0.60), -60 * 16, 120 * 16)
        else:
            painter.drawLine(P(0.62, 0.38), P(0.84, 0.62))
            painter.drawLine(P(0.84, 0.38), P(0.62, 0.62))
    elif name in ("add_file", "add_folder"):
        painter.setBrush(Qt.NoBrush)
        if name == "add_file":
            path = QPainterPath(P(0.28, 0.16))
            path.lineTo(P(0.60, 0.16)); path.lineTo(P(0.74, 0.30)); path.lineTo(P(0.74, 0.84))
            path.lineTo(P(0.28, 0.84)); path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(R(0.14, 0.30, 0.72, 0.50), 2, 2)
            painter.drawLine(P(0.14, 0.30), P(0.30, 0.20)); painter.drawLine(P(0.30, 0.20), P(0.46, 0.20)); painter.drawLine(P(0.46, 0.20), P(0.52, 0.30))
        painter.drawLine(P(0.50, 0.46), P(0.50, 0.70))
        painter.drawLine(P(0.38, 0.58), P(0.62, 0.58))
    elif name == "remove":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(P(0.26, 0.50), P(0.74, 0.50))
    elif name == "clear":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(P(0.22, 0.30), P(0.78, 0.30))
        painter.drawLine(P(0.42, 0.30), P(0.42, 0.20)); painter.drawLine(P(0.42, 0.20), P(0.58, 0.20)); painter.drawLine(P(0.58, 0.20), P(0.58, 0.30))
        painter.drawRect(R(0.28, 0.30, 0.44, 0.52))
        painter.drawLine(P(0.42, 0.42), P(0.42, 0.72)); painter.drawLine(P(0.58, 0.42), P(0.58, 0.72))
    elif name == "folder_open":
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(R(0.14, 0.30, 0.72, 0.50), 2, 2)
        painter.drawLine(P(0.14, 0.30), P(0.30, 0.20)); painter.drawLine(P(0.30, 0.20), P(0.46, 0.20)); painter.drawLine(P(0.46, 0.20), P(0.52, 0.30))
        painter.drawLine(P(0.14, 0.48), P(0.86, 0.48))
    elif name == "report":
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(R(0.26, 0.14, 0.48, 0.72), 2, 2)
        for y in (0.36, 0.50, 0.64):
            painter.drawLine(P(0.36, y), P(0.64, y))
    elif name == "shield":
        path = QPainterPath(P(0.50, 0.12))
        path.lineTo(P(0.80, 0.24)); path.lineTo(P(0.76, 0.58)); path.quadTo(P(0.70, 0.78), P(0.50, 0.88))
        path.quadTo(P(0.30, 0.78), P(0.24, 0.58)); path.lineTo(P(0.20, 0.24)); path.closeSubpath()
        painter.drawPath(path)
    else:
        raise KeyError(name)


def glyph_icon(name: str, color: str, size: int = 20) -> QIcon:
    """A QIcon of `name` in `color`. Raises KeyError for unknown names."""
    if name not in GLYPHS:
        raise KeyError(name)
    qcolor = QColor(color)
    icon = QIcon()
    for px in (size, size * 2):  # a 2x pixmap keeps high-DPI screens crisp
        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        _paint(name, painter, float(px), qcolor)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def make_icon_button(name: str, tooltip: str, color: str, size: int = 28, parent=None) -> QToolButton:
    """A flat square QToolButton carrying `glyph_icon(name)` and `tooltip`."""
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setIcon(glyph_icon(name, color, size - 8))
    button.setIconSize(QSize(size - 8, size - 8))
    button.setFixedSize(size, size)
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet(theme.icon_button_style(size))
    return button
```

Add `QSize` to the `PyQt5.QtCore` import. `_opaque_pixels` in the test double-checks alpha two ways because `image.pixel()` drops alpha on some formats; keep it as written.

- [ ] **Step 4: Run, expect pass; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_glyph_icons.py
python -m ruff check ui/glyph_icons.py tests/test_glyph_icons.py
git add ui/glyph_icons.py tests/test_glyph_icons.py
git commit -m "feat(ui): painted glyph icons and icon-button factory"
```

---

### Task 3: `LeafFrame` and the tab cards; trim the global bubble rule

**Files:**
- Create: `ui/leaf_frame.py`
- Modify: `ui/main_window.py` — window stylesheet (lines 121–142), the seven `self.tabs.addTab(...)` scroll wrappers (lines ~509–729), the tab-bar QSS at line 269 (`QTabWidget::pane {{ margin: 4px; border-radius: 8px; }}`), the dashed drop-zone QSS blocks (lines 340, 1085, 1099, 1975, 2705, 2722, 2735, 2756, 2769, 3019), `theme.drop_zone_style` / `theme.preview_box_style` in `ui/theme.py`
- Test: `tests/test_main_window_layout.py` (new)

**Interfaces:**
- Produces: `LeafFrame(parent=None, radius=28, dashed=False)` with `objectName "leaf"`, a `QVBoxLayout` at margins 12 reachable as `frame.body`; `VideoConverterApp.tool_tab_cards: dict[str, LeafFrame]` keyed by tab key (`conversion_log`, `converted_files`, `video_inspection`, `pc_report`, `lossless_editor`, `multi_source_recorder`, `media_player`).

- [ ] **Step 1: Failing test**

```python
# tests/test_main_window_layout.py
import unittest

from ui.leaf_frame import LeafFrame
from ui.main_window import VideoConverterApp


class LeafFrameTests(unittest.TestCase):
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
        cls.window = VideoConverterApp()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()

    def test_every_tool_tab_sits_in_a_leaf_card(self):
        keys = {"conversion_log", "converted_files", "video_inspection", "pc_report",
                "lossless_editor", "multi_source_recorder", "media_player"}
        self.assertEqual(set(self.window.tool_tab_cards), keys)
        for key, card in self.window.tool_tab_cards.items():
            self.assertIsInstance(card, LeafFrame, key)

    def test_tab_pane_has_no_border_of_its_own(self):
        self.assertIn("QTabWidget::pane { border: none; background: transparent; }",
                      " ".join(self.window.styleSheet().split()))

    def test_global_push_button_rule_no_longer_forces_a_bubble(self):
        rule = self.window.styleSheet()
        self.assertNotIn("min-width: 100px", rule)
        self.assertNotIn("min-height: 32px", rule)
```

Check how other tests build the main window headlessly (`tests/test_main_window_media_player.py`) and mirror any required patching there (e.g. settings path); copy that setup into `setUpClass`.

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: `ui/leaf_frame.py`**

```python
"""A card with VIO's leaf silhouette: rounded top-left and bottom-right corners."""
from PyQt5.QtWidgets import QFrame, QVBoxLayout

from ui import theme


class LeafFrame(QFrame):
    def __init__(self, parent=None, radius: int = 28, dashed: bool = False):
        super().__init__(parent)
        self.radius = radius
        self.dashed = dashed
        self.setObjectName("leaf")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(12, 12, 12, 12)
        self.body.setSpacing(6)
        self.reskin()

    def reskin(self) -> None:
        """Re-read the skin; call after theme changes."""
        self.setStyleSheet(theme.leaf_style(self.radius, self.dashed))
```

- [ ] **Step 4: Main window — global QSS**

In the `modern_stylesheet` (line 121–142) change the `QPushButton` rule to:

```
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent, stop:1 $accent_pressed);
                border: 1px solid $accent_dark;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                color: white;
            }
```

and the pane rule to:

```
            QTabWidget::pane {
                border: none;
                background: transparent;
                margin-top: 4px;
            }
```

At line 269, replace `QTabWidget::pane {{ margin: 4px; border-radius: 8px; }}` with `QTabWidget::pane {{ margin: 4px; border: none; background: transparent; }}`.

- [ ] **Step 5: Main window — wrap each tab page in a `LeafFrame`**

Add `from ui.leaf_frame import LeafFrame` to the imports and `self.tool_tab_cards = {}` right after `self.tabs = QTabWidget()` (line ~272). Then for each of the seven tabs, immediately before `self.<x>_tab_scroll.setWidget(<page>)`, insert:

```python
        card = LeafFrame(radius=28)
        card.body.addWidget(<page>)
        self.tool_tab_cards["<key>"] = card
```

and change `setWidget(<page>)` to `setWidget(card)`. Pages/keys: `self.log_tab` → `conversion_log`; `self.converted_files_tab` → `converted_files`; the inspection page widget → `video_inspection`; the PC report page → `pc_report`; lossless editor page → `lossless_editor`; recorder page → `multi_source_recorder`; media player page → `media_player` (the media player tab is lazily built: put the card creation in the same code path that creates its scroll wrapper so the key exists at construction; if the page itself is created lazily, wrap a placeholder `QWidget` now and `card.body.addWidget(widget)` when the real widget arrives in `_ensure_media_player_widget`).

Set each page's own layout margins to `(0, 0, 0, 0)` where they were `(11, 11, 11, 11)` or `(16, 16, 16, 16)`, since the card now provides 12 px.

- [ ] **Step 6: Drop zones and preview box take the leaf**

In `ui/theme.py`, in `drop_zone_style` and `preview_box_style`, replace `border-radius: {radius}px;` with `{leaf_radii(radius)}` and change the default `radius` parameter of both to `18`. In `ui/main_window.py`, in every QSS block that contains `2px dashed` (lines 340, 1085, 1099, 1975, 2722, 2735, 2756, 2769, 3019) and the panel at 2705, replace `border-radius: 8px;` with `$leaf` and pass `leaf=theme.leaf_radii(18)` as an extra keyword to that `theme.qss(...)` call (the helper accepts `**extra`).

- [ ] **Step 7: Run, expect pass; full suite; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_main_window_layout.py tests/test_theme.py
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/leaf_frame.py tests/test_main_window_layout.py
git add ui/leaf_frame.py ui/main_window.py ui/theme.py tests/test_main_window_layout.py
git commit -m "feat(ui): leaf cards on every tool tab; drop zones and preview take the leaf; global button rule no longer forces a bubble"
```

---

### Task 4: Window modes — `set_window_mode`, burger Window submenu, dead compact code removed

**Files:**
- Modify: `ui/main_window.py` — burger menu (lines 820–835), the dead compact block (lines 867–989: everything from `# Add Compact Mode toggle to burger menu` through `self.is_compact = False`), startup (after `self.center_on_screen()`), settings save path
- Test: `tests/test_main_window_layout.py`

**Interfaces:**
- Consumes: `theme.set_layout_mode`, `theme.metrics`, `theme.LAYOUT_MODES`, settings key `window_mode`.
- Produces: `VideoConverterApp.set_window_mode(name: str, persist: bool = True) -> None`; `VideoConverterApp.window_mode_actions: dict[str, QAction]`; `VideoConverterApp.layout_mode_widgets() -> list` (tool widgets that define `apply_layout_mode`). Tool widgets may define `apply_layout_mode(self, metrics: theme.LayoutMetrics) -> None` (Tasks 5, 7, 8 add them).

- [ ] **Step 1: Failing tests** (append to `TabCardTests` or a new class sharing its `setUpClass`)

```python
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
```

Add `from ui import theme` to the test imports.

- [ ] **Step 2: Run, expect AttributeError**

- [ ] **Step 3: Delete the dead compact block**

Remove lines 867–987 (all commented `compact_*` scaffolding) and the line `self.is_compact = False`. Keep `self.setStyleSheet(self.styleSheet() + '\nQMainWindow { border-radius: 8px; background: #F5F5F5; }')`. Grep for `is_compact` and `compact_` afterwards; remove any remaining `hasattr(self, 'compact_...')` guards that now reference nothing (the explorer noted sync helpers guard with `hasattr` — those guards are dead code, delete the branches).

- [ ] **Step 4: Burger submenu**

Replace the block from `burger_menu.addAction(_tr("Settings"), self.show_settings)` to `self._add_language_menu(burger_menu)` with:

```python
        burger_menu.addAction(_tr("Settings"), self.show_settings)
        window_menu = burger_menu.addMenu(_tr("Window"))
        from PyQt5.QtWidgets import QActionGroup
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        self.window_mode_actions = {}
        for mode, label in (("compact", _tr("Compact mode")), ("full", _tr("Full window mode"))):
            action = window_menu.addAction(label)
            action.setCheckable(True)
            action.setData(mode)
            mode_group.addAction(action)
            action.triggered.connect(lambda _checked, m=mode: self.set_window_mode(m))
            self.window_mode_actions[mode] = action
        self._add_language_menu(burger_menu)
```

- [ ] **Step 5: `set_window_mode` and startup**

Add methods to `VideoConverterApp`:

```python
    def layout_mode_widgets(self):
        """Tool widgets that adapt to the window mode."""
        candidates = (
            getattr(self, "multi_source_recorder_widget", None),
            getattr(self, "media_player_widget", None),
            getattr(self, "pc_report_widget", None),
            getattr(self, "lossless_editor_widget", None),
        )
        return [w for w in candidates if w is not None and hasattr(w, "apply_layout_mode")]

    def set_window_mode(self, name, persist=True):
        """Switch between Compact (960x600, normal) and Full window (maximised).

        Raises ValueError for unknown names so a typo in settings cannot leave
        the window half-applied.
        """
        metrics = theme.set_layout_mode(name)
        self.settings["window_mode"] = metrics.name
        for mode, action in getattr(self, "window_mode_actions", {}).items():
            action.setChecked(mode == metrics.name)
        central = self.centralWidget()
        if central is not None and central.layout() is not None:
            m = metrics.margin
            central.layout().setContentsMargins(m, m, m, m)
        for widget in self.layout_mode_widgets():
            widget.apply_layout_mode(metrics)
        if metrics.name == "full":
            self.showMaximized()
        else:
            self.showNormal()
            self.resize(960, 600)
        if persist:
            save_settings(self.settings)
```

Check the module already imports `save_settings` from `utils.config` (it saves settings elsewhere; reuse the same function name). If the window is shown via `show()` elsewhere after construction, call `self.set_window_mode(self.settings.get("window_mode", "compact"), persist=False)` at the end of `__init__` right after `self.center_on_screen()`; the `showNormal()`/`showMaximized()` inside replaces the later `show()` harmlessly. In `main.py`, if it calls `window.show()` after constructing, leave it — `show()` on a maximised window keeps it maximised.

Also, when the media player widget is created lazily (`_ensure_media_player_widget`), call `widget.apply_layout_mode(theme.metrics())` if it has the method.

- [ ] **Step 6: Run, expect pass; full suite; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_main_window_layout.py
python -m pytest -q -p no:cacheprovider
git add ui/main_window.py tests/test_main_window_layout.py
git commit -m "feat(ui): Compact / Full window modes from the burger menu; remove dead compact-mode scaffolding"
```

---

### Task 5: PC Report tab — heart pulse, links, no hint text, run-as-administrator

**Files:**
- Modify: `ui/pc_report_dialog.py` — `PCReportWidget.__init__` (lines 89–179), `_set_logo`, `on_run`, the worker-finished/failed handlers, `update_button_style`
- Test: `tests/test_pc_report_widget.py`

**Interfaces:**
- Consumes: `theme.compact_button_style`, `theme.link_button_style`, `theme.opt_out_of_button_style`, `theme.metrics`, `glyph_icons` (not required here).
- Produces: `PCReportWidget.heart_label`, `PCReportWidget.heart_anim` (a `QPropertyAnimation` or `None`), `PCReportWidget.btn_admin`, `PCReportWidget.apply_layout_mode(metrics)`, `PCReportWidget.is_elevated() -> bool` (static, patched in tests), `PCReportWidget.relaunch_elevated()`.

- [ ] **Step 1: Failing tests** (append to `tests/test_pc_report_widget.py`; reuse its widget fixture pattern)

```python
    def test_no_hint_text_and_placeholder_instead_of_prefilled_log(self):
        widget = PCReportWidget()
        texts = [label.text() for label in widget.findChildren(QLabel)]
        self.assertFalse(any(t.startswith("Tip:") for t in texts), texts)
        self.assertEqual(widget.output.toPlainText(), "")
        self.assertEqual(widget.output.placeholderText(), "Report progress appears here.")

    def test_secondary_actions_are_links_and_generate_is_compact(self):
        widget = PCReportWidget()
        for button in (widget.btn_open, widget.btn_folder, widget.btn_admin):
            self.assertTrue(button.property("skipGlobalStyle"), button.text())
            self.assertIn("text-decoration: underline", button.styleSheet(), button.text())
        self.assertTrue(widget.btn_run.property("skipGlobalStyle"))
        self.assertIn("min-height: 24px", widget.btn_run.styleSheet())
        self.assertEqual(widget.btn_open.text(), "Open report")
        self.assertEqual(widget.btn_folder.text(), "Open folder")
        self.assertEqual(widget.btn_admin.text(), "Run as administrator")

    def test_admin_link_hidden_when_already_elevated(self):
        with patch.object(PCReportWidget, "is_elevated", staticmethod(lambda: True)):
            self.assertTrue(PCReportWidget().btn_admin.isHidden())
        with patch.object(PCReportWidget, "is_elevated", staticmethod(lambda: False)):
            self.assertFalse(PCReportWidget().btn_admin.isHidden())

    def test_heart_pulses_while_running_and_settles_on_finish(self):
        widget = PCReportWidget()
        with patch("ui.pc_report_dialog._PCReportWorker") as worker_cls:
            worker = worker_cls.return_value
            worker.isRunning.return_value = False
            widget.on_run()
            self.assertIsNotNone(widget.heart_anim)
            self.assertEqual(widget.heart_anim.state(), QAbstractAnimation.Running)
            self.assertEqual(widget.heart_anim.loopCount(), -1)
            self.assertFalse(widget.heart_label.isHidden())
        widget._on_worker_finished("<html></html>", "")
        self.assertEqual(widget.heart_anim.state(), QAbstractAnimation.Stopped)
        self.assertEqual(widget.heart_effect.opacity(), 1.0)
        widget._on_worker_failed("boom")
        self.assertTrue(widget.heart_label.isHidden())

    def test_layout_mode_resizes_logo(self):
        widget = PCReportWidget()
        widget.apply_layout_mode(theme.FULL)
        self.assertEqual(widget.logo_label.pixmap().width(), theme.FULL.pc_report_logo_w)
        widget.apply_layout_mode(theme.COMPACT)
        self.assertEqual(widget.logo_label.pixmap().width(), theme.COMPACT.pc_report_logo_w)
```

Imports needed: `from unittest.mock import patch`, `from PyQt5.QtCore import QAbstractAnimation`, `from PyQt5.QtWidgets import QLabel`, `from ui import theme`. Read the widget for the actual names of the finished/failed slot methods and use those (if they are not `_on_worker_finished` / `_on_worker_failed`, rename them to these names in Step 3 — they are internal).

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Rebuild the widget header, actions and heart**

Replace the body of `__init__` from `layout = QVBoxLayout(self)` through the `self.btn_folder.clicked.connect(...)` line with:

```python
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(14)
        # The heart sits under the monitor logo's transparent cut-out and pulses
        # while a report runs (restored from the pre-343d9c1 dialog).
        logo_stack = QGridLayout()
        logo_stack.setContentsMargins(0, 0, 0, 0)
        self.heart_label = QLabel()
        self.heart_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.heart_label.setAlignment(Qt.AlignCenter)
        self.heart_effect = QGraphicsOpacityEffect(self.heart_label)
        self.heart_effect.setOpacity(0.0)
        self.heart_label.setGraphicsEffect(self.heart_effect)
        self.heart_label.hide()
        self.heart_anim = None
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        logo_stack.addWidget(self.heart_label, 0, 0, Qt.AlignCenter)
        logo_stack.addWidget(self.logo_label, 0, 0, Qt.AlignCenter)
        self.logo_width = theme.metrics().pc_report_logo_w
        self._set_logo()
        header.addLayout(logo_stack, 0)

        intro = QVBoxLayout()
        intro.setSpacing(2)
        title = QLabel(_tr("PC Report"))
        title.setStyleSheet(theme.tab_title_style())
        intro.addWidget(title)
        description = QLabel(_tr("Collects system details for support. Redaction is always on."))
        description.setStyleSheet(theme.qss("color: $text_body; font-size: 9pt;"))
        intro.addWidget(description)

        actions = QHBoxLayout()
        actions.setSpacing(14)
        self.btn_run = QPushButton(_tr("Generate PC Report"))
        self.btn_open = QPushButton(_tr("Open report"))
        self.btn_folder = QPushButton(_tr("Open folder"))
        self.btn_admin = QPushButton(_tr("Run as administrator"))
        self.btn_admin.setToolTip(_tr("Restart NVC with administrator rights so the report can read TPM, BitLocker, disk reliability and SMB server details."))
        for button in (self.btn_run, self.btn_open, self.btn_folder, self.btn_admin):
            button.setCursor(Qt.PointingHandCursor)
            theme.opt_out_of_button_style(button)
        self.btn_open.setEnabled(False)
        self.btn_folder.setEnabled(False)
        self.btn_admin.setVisible(not self.is_elevated())
        actions.addWidget(self.btn_run)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_folder)
        actions.addStretch(1)
        actions.addWidget(self.btn_admin)
        intro.addLayout(actions)
        header.addLayout(intro, 1)
        layout.addLayout(header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        self._set_progress_color(theme.skin_for_state(locked=locked, active=converting).accent)
        layout.addWidget(self.progress)

        self.status_label = QLabel(_tr("Ready. Reports are saved to your Desktop by default."))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(theme.qss("color: $grey_700; font-size: 9pt;"))
        layout.addWidget(self.status_label)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.output.setPlaceholderText(_tr("Report progress appears here."))
        layout.addWidget(self.output, 1)

        self._apply_tier_styles()
        self.btn_run.clicked.connect(self.on_run)
        self.btn_open.clicked.connect(self.open_report)
        self.btn_folder.clicked.connect(self.open_report_folder)
        self.btn_admin.clicked.connect(self.relaunch_elevated)
```

Add imports: `QGridLayout`, `QGraphicsOpacityEffect` from `PyQt5.QtWidgets`; `QEasingCurve`, `QPropertyAnimation` from `PyQt5.QtCore`; `import ctypes`, `import sys`, `import subprocess` as needed. If `theme.tab_title_style` does not exist, use `theme.qss("font-size: 14pt; font-weight: bold; color: $accent;")`.

In `_set_progress_color`, change `height: 16px;` to `height: 6px;` and `border-radius: 4px` → `3px`, chunk radius `2px`, margin `0px`.

Add methods:

```python
    def _apply_tier_styles(self):
        self.btn_run.setStyleSheet(theme.compact_button_style())
        for link in (self.btn_open, self.btn_folder, self.btn_admin):
            link.setStyleSheet(theme.link_button_style())

    def apply_layout_mode(self, metrics):
        self.logo_width = metrics.pc_report_logo_w
        self._set_logo()

    @staticmethod
    def is_elevated():
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def relaunch_elevated(self):
        """Ask UAC to start a second NVC as administrator, then quit this one."""
        try:
            if getattr(sys, "frozen", False):
                exe, params = sys.executable, ""
            else:
                exe, params = sys.executable, subprocess.list2cmdline(sys.argv)
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        except Exception:
            logger.debug("PCReportWidget.relaunch_elevated: suppressed error", exc_info=True)
            result = 0
        if result > 32:
            window = self.window()
            quit_fn = getattr(window, "quit_application", None)
            if callable(quit_fn):
                quit_fn()
        else:
            self.status_label.setText(_tr("Elevation was cancelled or refused; the report will run without administrator rights."))
```

Replace `_set_logo` so it sizes both pixmaps to `self.logo_width`:

```python
    def _set_logo(self):
        from PyQt5.QtGui import QPixmap
        from utils.resources import resource_path
        if self.locked:
            logo, heart = 'graphics/GRAYSCALEPCREPORT.png', 'graphics/PCREPORTHEART.png'
        elif self.converting:
            logo, heart = 'graphics/GREENPCREPORT.png', 'graphics/GREENPCREPORTHEART.png'
        else:
            logo, heart = 'graphics/PCREPORT.png', 'graphics/PCREPORTHEART.png'
        for label, rel in ((self.logo_label, logo), (self.heart_label, heart)):
            path = resource_path(rel)
            if os.path.exists(path):
                label.setPixmap(QPixmap(path).scaledToWidth(self.logo_width, Qt.SmoothTransformation))
```

In `on_run`, after `self.progress.show()`, add `self._start_heart()`; remove `self.output.appendPlainText(f"Report will be saved to: {self.report_path}")`? No — keep it; it is progress, not a hint. In the finished handler add `self._settle_heart(success=True)`; in the failed/cancelled handler add `self._settle_heart(success=False)`:

```python
    def _start_heart(self):
        self.heart_label.show()
        if self.heart_anim is not None:
            self.heart_anim.stop()
        anim = QPropertyAnimation(self.heart_effect, b"opacity", self)
        anim.setDuration(2400)
        anim.setKeyValueAt(0.0, 0.2)
        anim.setKeyValueAt(0.5, 1.0)
        anim.setKeyValueAt(1.0, 0.2)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setLoopCount(-1)
        anim.start()
        self.heart_anim = anim

    def _settle_heart(self, success):
        if self.heart_anim is not None:
            self.heart_anim.stop()
        if success:
            self.heart_effect.setOpacity(1.0)
        else:
            self.heart_effect.setOpacity(0.0)
            self.heart_label.hide()
```

In `update_button_style(...)`, after updating `self.converting` / `self.locked` and calling `_set_logo()`, call `self._apply_tier_styles()` instead of applying `button_style` to the three buttons (they opt out now). Keep the signature.

- [ ] **Step 4: Run, expect pass; full suite; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_pc_report_widget.py tests/test_single_active_workflow.py
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/pc_report_dialog.py tests/test_pc_report_widget.py
git add ui/pc_report_dialog.py tests/test_pc_report_widget.py
git commit -m "feat(pc-report): pulsing heart, link-style secondary actions, no hint text, run-as-administrator relaunch"
```

---

### Task 6: Lossless Editor — compact tools

**Files:**
- Modify: `ui/lossless_editor_widget.py` `_init_ui` (lines 72–148), `update_button_style` (150–156)
- Test: `tests/test_lossless_editor_widget.py` (create if absent; check `tests/` first)

**Interfaces:**
- Consumes: `theme.compact_button_style`, `theme.opt_out_of_button_style`, `glyph_icons.make_icon_button`.
- Produces: attributes `browse_btn`, `trim_btn`, `remux_btn`, `extract_audio_btn`, `remove_audio_btn`, `merge_btn`, `add_merge_btn` (QToolButton), `clear_merge_btn` (QToolButton).

- [ ] **Step 1: Failing test**

```python
# tests/test_lossless_editor_widget.py
import unittest

from PyQt5.QtWidgets import QToolButton

from ui.lossless_editor_widget import LosslessEditorWidget


class LosslessEditorLayoutTests(unittest.TestCase):
    def setUp(self):
        self.widget = LosslessEditorWidget(["mp4", "mkv"])

    def test_tool_buttons_are_compact_and_opt_out_of_global_style(self):
        for button in (self.widget.browse_btn, self.widget.trim_btn, self.widget.remux_btn,
                       self.widget.extract_audio_btn, self.widget.remove_audio_btn, self.widget.merge_btn):
            self.assertTrue(button.property("skipGlobalStyle"), button.text())
            self.assertLessEqual(button.sizeHint().height(), 28, button.text())
        self.assertEqual(self.widget.trim_btn.text(), "Trim")
        self.assertEqual(self.widget.extract_audio_btn.text(), "Extract audio")
        self.assertEqual(self.widget.remove_audio_btn.text(), "Remove audio")
        self.assertEqual(self.widget.merge_btn.text(), "Merge")

    def test_merge_list_actions_are_icon_buttons_with_tooltips(self):
        self.assertIsInstance(self.widget.add_merge_btn, QToolButton)
        self.assertIsInstance(self.widget.clear_merge_btn, QToolButton)
        self.assertEqual(self.widget.add_merge_btn.toolTip(), "Add files to the merge list")
        self.assertEqual(self.widget.clear_merge_btn.toolTip(), "Clear the merge list")

    def test_update_button_style_keeps_compact_tier(self):
        self.widget.update_button_style("QPushButton { min-height: 32px; }")
        self.assertNotIn("32px", self.widget.trim_btn.styleSheet())
        self.assertIn("min-height: 24px", self.widget.trim_btn.styleSheet())
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Rework `_init_ui`**

Replace `_init_ui` and `update_button_style` with:

```python
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(_tr("Lossless FFmpeg Editor"))
        title.setStyleSheet(theme.tab_title_style())
        layout.addWidget(title)
        description = QLabel(_tr("Trim, remux, extract or remove audio, and merge clips without re-encoding."))
        description.setStyleSheet(theme.qss("color: $text_body; font-size: 9pt;"))
        layout.addWidget(description)

        file_row = QHBoxLayout()
        file_row.setSpacing(6)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(_tr("Select a source media file"))
        self.browse_btn = QPushButton(_tr("Browse..."))
        self.browse_btn.clicked.connect(self.browse_input)
        file_row.addWidget(QLabel(_tr("Input:")))
        file_row.addWidget(self.input_edit, 1)
        file_row.addWidget(self.browse_btn)
        layout.addLayout(file_row)

        time_row = QHBoxLayout()
        time_row.setSpacing(6)
        self.start_edit = QLineEdit(_tr("00:00:00"))
        self.start_edit.setMaximumWidth(110)
        self.end_edit = QLineEdit("")
        self.end_edit.setMaximumWidth(110)
        self.end_edit.setPlaceholderText(_tr("end of file"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "mov", "avi", "m4a"])
        time_row.addWidget(QLabel(_tr("Start:")))
        time_row.addWidget(self.start_edit)
        time_row.addWidget(QLabel(_tr("End:")))
        time_row.addWidget(self.end_edit)
        time_row.addStretch(1)
        time_row.addWidget(QLabel(_tr("Output:")))
        time_row.addWidget(self.format_combo)
        layout.addLayout(time_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.trim_btn = QPushButton(_tr("Trim"))
        self.trim_btn.setToolTip(_tr("Cut Start to End without re-encoding"))
        self.remux_btn = QPushButton(_tr("Remux"))
        self.remux_btn.setToolTip(_tr("Copy every stream into the chosen container"))
        self.extract_audio_btn = QPushButton(_tr("Extract audio"))
        self.remove_audio_btn = QPushButton(_tr("Remove audio"))
        for button, handler in (
            (self.trim_btn, self.trim_losslessly),
            (self.remux_btn, self.remux),
            (self.extract_audio_btn, self.extract_audio),
            (self.remove_audio_btn, self.remove_audio),
        ):
            button.clicked.connect(handler)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            action_row.addWidget(button)
        layout.addLayout(action_row)

        merge_header = QHBoxLayout()
        merge_header.setSpacing(4)
        merge_label = QLabel(_tr("Merge list"))
        merge_label.setStyleSheet(theme.group_title_style())
        merge_header.addWidget(merge_label)
        merge_header.addStretch(1)
        accent = theme.skin().accent
        self.add_merge_btn = make_icon_button("add_file", _tr("Add files to the merge list"), accent, size=24)
        self.clear_merge_btn = make_icon_button("clear", _tr("Clear the merge list"), accent, size=24)
        self.merge_btn = QPushButton(_tr("Merge"))
        self.merge_btn.setToolTip(_tr("Concatenate the listed clips losslessly"))
        self.add_merge_btn.clicked.connect(self.add_merge_files)
        self.clear_merge_btn.clicked.connect(self.merge_list.clear if hasattr(self, "merge_list") else (lambda: None))
        merge_header.addWidget(self.add_merge_btn)
        merge_header.addWidget(self.clear_merge_btn)
        merge_header.addWidget(self.merge_btn)
        layout.addLayout(merge_header)

        self.merge_list = QListWidget()
        self.merge_list.setAcceptDrops(False)
        self.merge_list.setMaximumHeight(120)
        layout.addWidget(self.merge_list)
        self.clear_merge_btn.clicked.disconnect()
        self.clear_merge_btn.clicked.connect(self.merge_list.clear)
        self.merge_btn.clicked.connect(self.merge_losslessly)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText(_tr("FFmpeg output appears here."))
        layout.addWidget(self.log_output, 1)

        self._apply_tier_styles()

    def _apply_tier_styles(self):
        compact = theme.compact_button_style()
        accent = theme.skin().accent
        for button in (self.browse_btn, self.trim_btn, self.remux_btn, self.extract_audio_btn,
                       self.remove_audio_btn, self.merge_btn):
            theme.opt_out_of_button_style(button)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(compact)
        for tool in (self.add_merge_btn, self.clear_merge_btn):
            tool.setIcon(glyph_icon(tool.property("glyph") or "add_file", accent, 16))

    def update_button_style(self, button_style):
        """Called by the main window on skin change; re-derive tiers from the skin."""
        self.button_style = button_style
        self._apply_tier_styles()
```

Simplify the clear-button wiring: create `self.merge_list` **before** the header so the awkward connect/disconnect is unnecessary — reorder the code so the `QListWidget` is created first, then the header row, then `layout.addLayout(merge_header)` followed by `layout.addWidget(self.merge_list)`. Set `button.setProperty("glyph", name)` inside `make_icon_button` in `ui/glyph_icons.py` (one-line addition: `button.setProperty("glyph", name)`) so `_apply_tier_styles` can re-tint. Imports: `from ui.glyph_icons import glyph_icon, make_icon_button`, `QSizePolicy`, `QToolButton` not needed. If `theme.group_title_style` does not exist, use `theme.qss("font-weight: bold; color: $grey_800;")`.

- [ ] **Step 4: Run, expect pass; full suite; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_lossless_editor_widget.py
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/lossless_editor_widget.py ui/glyph_icons.py tests/test_lossless_editor_widget.py
git add ui/lossless_editor_widget.py ui/glyph_icons.py tests/test_lossless_editor_widget.py
git commit -m "feat(editor): compact tool buttons, icon actions for the merge list"
```

---

### Task 7: Media Player — icon transport, per-panel icon actions, icon playlist dock

**Files:**
- Modify: `ui/media_player_widget.py` — `PlayerPanel._build_ui` (lines 172–186), `MediaPlayerWidget._build_transport_bar` (473–569), `_on_mute_toggled` (721), `play_all`/`pause_all`/`stop_all` (`setText` at 953, 960, 967), `update_button_style` if present
- Modify: `ui/media_player_parts.py` — `PlaylistDock.__init__` (lines 96–113)
- Test: `tests/test_media_player_widget.py` (line 99 `.text()` → tooltip), `tests/test_media_player_parts.py`

**Interfaces:**
- Consumes: `glyph_icons.make_icon_button`, `glyph_icon`, `theme.icon_button_style`, `theme.metrics`.
- Produces: `MediaPlayerWidget.play_btn/stop_btn/restart_btn/fullscreen_btn/playlist_btn/mute_btn` are `QToolButton`s; `MediaPlayerWidget.apply_layout_mode(metrics)`; `PlayerPanel.load_btn/clear_btn` are `QToolButton`s; `PlaylistDock.add_files_btn/add_folder_btn/remove_btn/clear_btn` are `QToolButton`s.

- [ ] **Step 1: Failing tests**

In `tests/test_media_player_widget.py` line 99, change `self.assertEqual(widget.play_btn.text(), "Play all")` to `self.assertEqual(widget.play_btn.toolTip(), "Play all")`. Add:

```python
    def test_transport_is_an_icon_toolbar(self):
        widget = self._widget()
        for button, tip in ((widget.play_btn, "Play all"), (widget.stop_btn, "Stop all"),
                            (widget.restart_btn, "Restart"), (widget.fullscreen_btn, "Fullscreen (F)"),
                            (widget.playlist_btn, "Playlist"), (widget.mute_btn, "Mute (M)")):
            self.assertIsInstance(button, QToolButton, tip)
            self.assertFalse(button.icon().isNull(), tip)
            self.assertEqual(button.toolTip(), tip)
            self.assertEqual(button.text(), "", tip)
        widget.play_all()
        self.assertEqual(widget.play_btn.toolTip(), "Pause all")
        widget.stop_all()
        self.assertEqual(widget.play_btn.toolTip(), "Play all")
        widget.mute_btn.setChecked(True)
        self.assertEqual(widget.mute_btn.toolTip(), "Unmute (M)")

    def test_panel_actions_are_icon_buttons(self):
        widget = self._widget()
        panel = widget.panels[0]
        self.assertIsInstance(panel.load_btn, QToolButton)
        self.assertIsInstance(panel.clear_btn, QToolButton)
        self.assertEqual(panel.load_btn.toolTip(), "Load a file into this panel")

    def test_layout_mode_sets_panel_min_height(self):
        widget = self._widget()
        widget.apply_layout_mode(theme.FULL)
        self.assertEqual(widget.panels[0].video_container.minimumHeight(), theme.FULL.player_panel_min_h)
        widget.apply_layout_mode(theme.COMPACT)
        self.assertEqual(widget.panels[0].video_container.minimumHeight(), theme.COMPACT.player_panel_min_h)
```

Use whatever fixture the file already uses to construct the widget (replace `self._widget()` with it). Add imports `QToolButton`, `theme`.

In `tests/test_media_player_parts.py` add:

```python
    def test_dock_actions_are_icon_buttons_that_fit(self):
        dock = PlaylistDock()
        for button, tip in ((dock.add_files_btn, "Add files..."), (dock.add_folder_btn, "Add folder..."),
                            (dock.remove_btn, "Remove selected"), (dock.clear_btn, "Clear playlist")):
            self.assertIsInstance(button, QToolButton, tip)
            self.assertEqual(button.toolTip(), tip)
        self.assertLessEqual(dock.sizeHint().width(), 320)
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Transport bar**

In `_build_transport_bar`, replace the creation of the six `QPushButton`s with:

```python
        accent = theme.skin().accent
        self._icon_color = accent
        self.play_btn = make_icon_button("play", _tr("Play all"), accent)
        self.play_btn.clicked.connect(self.toggle_play_all)
        self.stop_btn = make_icon_button("stop", _tr("Stop all"), accent)
        self.stop_btn.clicked.connect(self.stop_all)
        self.restart_btn = make_icon_button("restart", _tr("Restart"), accent)
        self.restart_btn.clicked.connect(self.restart_all)
        self.fullscreen_btn = make_icon_button("fullscreen", _tr("Fullscreen (F)"), accent)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.playlist_btn = make_icon_button("playlist", _tr("Playlist"), accent)
        self.playlist_btn.setCheckable(True)
        self.playlist_btn.toggled.connect(self._on_playlist_toggled)
        ...
        self.mute_btn = make_icon_button("volume", _tr("Mute (M)"), accent)
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._on_mute_toggled)
```

Change `button_row.setSpacing(8)` to `4`; put a 12 px `addSpacing` between the transport group and the fullscreen/playlist pair. Delete the `if self.button_style:` block at the end (icons carry their own style). Replace the `setText` calls:

- `_on_mute_toggled`: `self.mute_btn.setIcon(glyph_icon("muted" if checked else "volume", self._icon_color, 20)); self.mute_btn.setToolTip(_tr("Unmute (M)") if checked else _tr("Mute (M)"))`
- `play_all` (line 953): `self._set_play_glyph(playing=True)`; `pause_all`/`stop_all`: `self._set_play_glyph(playing=False)` with

```python
    def _set_play_glyph(self, playing):
        self.play_btn.setIcon(glyph_icon("pause" if playing else "play", self._icon_color, 20))
        self.play_btn.setToolTip(_tr("Pause all") if playing else _tr("Play all"))
```

Add:

```python
    def apply_layout_mode(self, metrics):
        for panel in self.panels:
            panel.video_container.setMinimumHeight(metrics.player_panel_min_h)
```

and call `self.apply_layout_mode(theme.metrics())` at the end of `_build_ui`. If the widget has an `update_button_style` hook the main window calls, make it re-tint: `self._icon_color = theme.skin().accent` and re-set every transport icon (`play` per `_is_playing`, `stop`, `restart`, `fullscreen`, `playlist`, mute per `mute_btn.isChecked()`).

- [ ] **Step 4: Per-panel actions**

In `PlayerPanel._build_ui` replace the two `QPushButton`s with:

```python
        accent = theme.skin().accent
        self.load_btn = make_icon_button("folder_open", _tr("Load a file into this panel"), accent, size=24)
        self.load_btn.clicked.connect(self.browse_for_media)
        self.clear_btn = make_icon_button("clear", _tr("Clear this panel"), accent, size=24)
        self.clear_btn.clicked.connect(self.clear_media)
```

- [ ] **Step 5: Playlist dock**

In `PlaylistDock.__init__` replace the four `QPushButton`s and the loop with:

```python
        accent = theme.skin().accent
        self.add_files_btn = make_icon_button("add_file", _tr("Add files..."), accent, size=24)
        self.add_folder_btn = make_icon_button("add_folder", _tr("Add folder..."), accent, size=24)
        self.remove_btn = make_icon_button("remove", _tr("Remove selected"), accent, size=24)
        self.clear_btn = make_icon_button("clear", _tr("Clear playlist"), accent, size=24)
        buttons.addStretch(1)
        for button in (self.add_files_btn, self.add_folder_btn, self.remove_btn, self.clear_btn):
            buttons.addWidget(button)
```

Imports in both files: `from ui.glyph_icons import glyph_icon, make_icon_button`. Remove `QPushButton` from imports if no longer used (ruff F401).

- [ ] **Step 6: Run, expect pass; full suite; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_media_player_widget.py tests/test_media_player_parts.py tests/test_main_window_media_player.py
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/media_player_widget.py ui/media_player_parts.py tests/test_media_player_widget.py tests/test_media_player_parts.py
git add ui/media_player_widget.py ui/media_player_parts.py tests/test_media_player_widget.py tests/test_media_player_parts.py
git commit -m "feat(player): icon transport bar, per-panel icon actions, icon playlist dock (fixes clipped buttons)"
```

---

### Task 8: Recorder tab — stacked/side-by-side groups per mode, readable file path, copy-mode note

**Files:**
- Modify: `ui/multi_source_recorder_widget.py` — `_init_ui` (lines 999–1230), plus new methods
- Test: `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Consumes: `theme.metrics`, `theme.LayoutMetrics`, `glyph_icons.make_icon_button`, `theme.link_button_style`.
- Produces: `MultiSourceRecorderWidget.apply_layout_mode(metrics)`, `.copy_mode_note` (QLabel), `.groups_stacked() -> bool`, `.open_output_folder_button` (QToolButton; keep `open_output_folder_link` as an alias to it).

- [ ] **Step 1: Failing tests** (append; use the file's existing widget factory, which constructs with `load_saved_settings=False` or equivalent)

```python
    def test_compact_mode_stacks_the_groups_and_full_mode_places_them_side_by_side(self):
        widget = self._widget()
        widget.apply_layout_mode(theme.COMPACT)
        self.assertTrue(widget.groups_stacked())
        self.assertEqual(widget.preview_boxes[0].maximumHeight(), theme.COMPACT.recorder_tile_max_h)
        widget.apply_layout_mode(theme.FULL)
        self.assertFalse(widget.groups_stacked())
        self.assertEqual(widget.preview_boxes[0].maximumHeight(), theme.FULL.recorder_tile_max_h)
        widget.apply_layout_mode(theme.COMPACT)

    def test_file_location_shows_the_tail_of_a_long_path(self):
        widget = self._widget()
        widget.output_folder_edit.setText(r"C:\Videos\a\very\long\path\to\recordings")
        self.assertEqual(widget.output_folder_edit.cursorPosition(), len(widget.output_folder_edit.text()))
        self.assertEqual(widget.output_folder_edit.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)

    def test_copy_mode_note_only_for_usb_rows_in_copy_mode(self):
        widget = self._widget()
        enabled, _label, type_combo = widget.source_rows[0][:3]
        widget.codec_combo.setCurrentText("copy")
        type_combo.setCurrentIndex(type_combo.findData("rtsp_ip"))
        self.assertTrue(widget.copy_mode_note.isHidden())
        type_combo.setCurrentIndex(type_combo.findData("directshow"))
        self.assertFalse(widget.copy_mode_note.isHidden())
        self.assertEqual(widget.copy_mode_note.text(),
                         "USB cameras are always re-encoded to H.264; copy applies to RTSP and file sources.")
        widget.codec_combo.setCurrentText("h264")
        self.assertTrue(widget.copy_mode_note.isHidden())
```

Add `from ui import theme` and `QSizePolicy` imports.

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement**

In `_init_ui`:

1. Replace `middle_row = QHBoxLayout()` … `layout.addLayout(middle_row)` (lines 1034–1206) so the two group boxes are created as today but added to a **host widget** whose layout is swapped by mode:

```python
        self.groups_host = QWidget()
        self.groups_layout = None  # set by apply_layout_mode
        ...  # build source_group and output_group exactly as before, but do not add them to a layout yet
        layout.addWidget(self.groups_host)
```

2. Replace the `output_folder_edit` policy and the `Open` link:

```python
        self.output_folder_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_folder_edit.textChanged.connect(
            lambda _t: self.output_folder_edit.setCursorPosition(len(self.output_folder_edit.text())))
        self.output_folder_edit.setCursorPosition(len(self.output_folder_edit.text()))
        self.open_output_folder_button = make_icon_button(
            "folder_open", _tr("Open the recording folder in your file browser"), theme.skin().accent, size=24)
        self.open_output_folder_button.clicked.connect(self.open_output_folder)
        self.open_output_folder_link = self.open_output_folder_button  # older callers
        folder_line.addWidget(self.output_folder_edit, 1)
        folder_line.addWidget(self.open_output_folder_button, 0)
```

3. After `output_form.addRow("Timer:", self.duration_edit)`, add the note as the form's last row spanning both columns:

```python
        self.copy_mode_note = QLabel(_tr("USB cameras are always re-encoded to H.264; copy applies to RTSP and file sources."))
        self.copy_mode_note.setWordWrap(True)
        self.copy_mode_note.setStyleSheet(theme.qss("color: $grey_650; font-size: 9pt;"))
        self.copy_mode_note.hide()
        output_form.addRow(self.copy_mode_note)
        self.codec_combo.currentTextChanged.connect(lambda _t: self.update_copy_mode_note())
        for enabled, _label, type_combo, *_rest in self.source_rows:
            enabled.toggled.connect(lambda _c: self.update_copy_mode_note())
            type_combo.currentIndexChanged.connect(lambda _i: self.update_copy_mode_note())
```

4. Replace the two link buttons' inline QSS with `theme.link_button_style()`.

5. At the end of `_init_ui`, call `self.apply_layout_mode(theme.metrics())` and `self.update_copy_mode_note()`.

Add methods:

```python
    def groups_stacked(self):
        return isinstance(self.groups_layout, QVBoxLayout)

    def apply_layout_mode(self, metrics):
        """Compact stacks Recording properties over Output settings; Full puts them side by side."""
        for preview in self.preview_boxes:
            preview.setMaximumHeight(metrics.recorder_tile_max_h)
        old = self.groups_layout
        if old is not None:
            old.removeWidget(self.source_group)
            old.removeWidget(self.output_group)
            QWidget().setLayout(old)  # detach the old layout from groups_host
        if metrics.recorder_stacked:
            new = QVBoxLayout(self.groups_host)
            new.addWidget(self.source_group)
            new.addWidget(self.output_group)
        else:
            new = QHBoxLayout(self.groups_host)
            new.setAlignment(Qt.AlignTop)
            new.addWidget(self.source_group, 2)
            new.addWidget(self.output_group, 1)
        new.setContentsMargins(0, 0, 0, 0)
        new.setSpacing(metrics.spacing * 2)
        self.groups_layout = new
        self.source_group.show()
        self.output_group.show()

    def update_copy_mode_note(self):
        usb_enabled = any(
            enabled.isChecked() and self._source_type_id(type_combo) == "directshow"
            for enabled, _label, type_combo, *_rest in self.source_rows
        )
        self.copy_mode_note.setVisible(self.codec_combo.currentText() == "copy" and usb_enabled)
```

`_source_type_id(combo)` already exists (used at line 1955). `QWidget().setLayout(old)` is the standard Qt idiom to release a layout from its parent; the temporary widget is garbage-collected with the layout. The recorder `sizeHint` test (≤ 700x460) must still pass in compact: adjust `sizeHint()` to `QSize(640, 440)` unchanged and verify.

- [ ] **Step 4: Run, expect pass; full suite; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_multi_source_recorder_widget.py tests/test_single_active_workflow.py
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/multi_source_recorder_widget.py tests/test_multi_source_recorder_widget.py
git add ui/multi_source_recorder_widget.py tests/test_multi_source_recorder_widget.py
git commit -m "feat(recorder): stack groups in compact mode, readable file location, copy-mode note for USB cameras"
```

---

### Task 9: Recorder Video Settings — Output quality wired, Timer bound, dead fields removed

**Files:**
- Modify: `conversion/recording_commands.py` (the seven `libx264 … veryfast … 18` sites at lines 226, 256, 308, 370–372, 541, 706, 723; signatures of `build_record_command`, `build_combined_grid_record_command`, `build_multi_source_record_command`, `build_directshow_record_with_preview_command`)
- Modify: `ui/multi_source_recorder_widget.py` — `VideoSettingsDialog.__init__` (lines 417–449), `apply_to_sources`, `collect_current_settings` (~1965), `apply_recorder_settings` (~1978), `build_recording_command` (2231), the two `build_combined_grid_record_command` calls (2611, 2624); `conversion/recorder_settings.py` `normalize_recorder_settings` if that is where `output` keys are normalised
- Test: `tests/test_recording_commands.py` (or the existing builder test file), `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Produces: `recording_commands.H264_QUALITY: dict[str, tuple[str, str]]`, `recording_commands.h264_encode_args(quality: str) -> list[str]`; every builder accepts `quality: str = "Default"`; recorder settings `output.quality` (string, default `"Default"`); `MultiSourceRecorderWidget.output_quality` attribute (str) and `VideoSettingsDialog.output_quality_combo`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_recording_commands.py (append; adapt import to the file's existing style)
from conversion import recording_commands as rc

class OutputQualityTests(unittest.TestCase):
    def test_quality_table_and_default(self):
        self.assertEqual(rc.h264_encode_args("High"), ["-c:v", "libx264", "-preset", "medium", "-crf", "16"])
        self.assertEqual(rc.h264_encode_args("Compact"), ["-c:v", "libx264", "-preset", "faster", "-crf", "24"])
        self.assertEqual(rc.h264_encode_args("nonsense"), ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])

    def test_every_builder_emits_the_chosen_quality(self):
        cmd = rc.build_record_command("ffmpeg", "rtsp://cam/stream", "out.mp4", "h264", "", quality="Balanced")
        self.assertIn("-crf", cmd)
        self.assertEqual(cmd[cmd.index("-crf") + 1], "20")
        cmd = rc.build_directshow_record_with_preview_command("ffmpeg", "Camera A", "out.mp4", "", quality="High")
        self.assertEqual(cmd[cmd.index("-crf") + 1], "16")
        grid = rc.build_combined_grid_record_command("ffmpeg", ["rtsp://a", "rtsp://b"], "out.mp4", "", quality="Compact")
        self.assertEqual(grid[grid.index("-crf") + 1], "24")
```

Read each builder's positional signature first and pass the required positional arguments as they are defined (the calls above show the intent; match the real parameter order).

```python
# tests/test_multi_source_recorder_widget.py (append)
    def test_video_settings_dialog_drops_time_format_and_binds_maximum_time_to_timer(self):
        widget = self._widget()
        widget.duration_edit.setText("00:10:00")
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), widget, widget.button_style)
        self.assertFalse(hasattr(dialog, "time_format_combo"))
        self.assertFalse(hasattr(dialog, "decimals_combo"))
        self.assertTrue(dialog.maximum_time_check.isChecked())
        self.assertEqual(dialog.maximum_time_edit.text(), "00:10:00")
        dialog.maximum_time_edit.setText("00:05:00")
        dialog.apply_to_sources()
        self.assertEqual(widget.duration_edit.text(), "00:05:00")
        dialog.maximum_time_check.setChecked(False)
        dialog.apply_to_sources()
        self.assertEqual(widget.duration_edit.text(), "")

    def test_output_quality_round_trips_through_settings_and_commands(self):
        widget = self._widget()
        dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), widget, widget.button_style)
        dialog.output_quality_combo.setCurrentText("High")
        dialog.apply_to_sources()
        self.assertEqual(widget.output_quality, "High")
        self.assertEqual(widget.collect_current_settings()["output"]["quality"], "High")
        widget.codec_combo.setCurrentText("h264")
        cmd = widget.build_recording_command("ffmpeg", "rtsp://cam/stream", "out.mp4")
        self.assertEqual(cmd[cmd.index("-crf") + 1], "16")
        widget.apply_recorder_settings({"output": {"quality": "Compact"}})
        self.assertEqual(widget.output_quality, "Compact")
```

Confirm the real name of the settings-collecting method (`collect_current_settings` at ~1965 per the grep) and of `VideoSettingsDialog`'s constructor arguments (see `capture_screenshots.py` in `docs/help/source`, which constructs it as `VideoSettingsDialog(recorder.source_rows, recorder.output_controls(), recorder, recorder.button_style)`).

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: `recording_commands.py`**

Add near the top (after the constants):

```python
# Output quality presets for the libx264 encode path. Keys are the labels shown
# in the recorder's Video Settings dialog; unknown labels fall back to Default.
H264_QUALITY: dict[str, tuple[str, str]] = {
    "Default": ("veryfast", "18"),
    "High": ("medium", "16"),
    "Balanced": ("veryfast", "20"),
    "Compact": ("faster", "24"),
}


def h264_encode_args(quality: str = "Default") -> list[str]:
    preset, crf = H264_QUALITY.get(quality, H264_QUALITY["Default"])
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf]
```

Add `quality: str = "Default"` as a keyword parameter to `build_record_command`, `build_combined_grid_record_command`, `build_multi_source_record_command`, `build_directshow_record_with_preview_command`, and any private helper between them that emits the encode args; replace each `command.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])` with `command.extend(h264_encode_args(quality))`, and the literal list at 370–372 with `*h264_encode_args(quality)`. Thread `quality` down through internal calls.

- [ ] **Step 4: Dialog and recorder**

In `VideoSettingsDialog.__init__` delete `time_format_combo`, `decimals_combo` and their two `addRow`s; keep `maximum_time_check`/`maximum_time_edit`. After building them:

```python
        current_timer = self.output_controls.get("duration")
        current_text = current_timer.text().strip() if current_timer is not None else ""
        self.maximum_time_check.setChecked(bool(current_text))
        self.maximum_time_edit.setText(current_text)
        self.maximum_time_edit.setEnabled(bool(current_text))
        self.maximum_time_check.toggled.connect(self.maximum_time_edit.setEnabled)
        quality_control = self.output_controls.get("quality")
        if quality_control:
            self.output_quality_combo.setCurrentText(quality_control)
```

Make `MultiSourceRecorderWidget.output_controls()` return `"duration": self.duration_edit` and `"quality": self.output_quality` in addition to what it returns today. Add `self.output_quality = "Default"` in the recorder `__init__` before `_init_ui`.

In `VideoSettingsDialog.apply_to_sources`, after the existing per-row application:

```python
        parent = self.parent()
        if parent is not None:
            parent.output_quality = self.output_quality_combo.currentText()
            if hasattr(parent, "duration_edit"):
                parent.duration_edit.setText(
                    self.maximum_time_edit.text().strip() if self.maximum_time_check.isChecked() else "")
```

In the recorder: `collect_current_settings` output dict gains `"quality": self.output_quality`; `apply_recorder_settings` sets `self.output_quality = output.get("quality", self.output_quality)`; `normalize_recorder_settings` (find it — `conversion/recorder_settings.py` or inline) accepts/keeps the `quality` key with default `"Default"`. `build_recording_command` passes `quality=self.output_quality` to both builders; the two `build_combined_grid_record_command(...)` calls at ~2611 and ~2624 pass `quality=self.output_quality`.

- [ ] **Step 5: Run, expect pass; full suite; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_recording_commands.py tests/test_multi_source_recorder_widget.py
python -m pytest -q -p no:cacheprovider
python -m ruff check conversion/recording_commands.py ui/multi_source_recorder_widget.py tests/test_recording_commands.py tests/test_multi_source_recorder_widget.py
git add conversion ui/multi_source_recorder_widget.py tests/test_recording_commands.py tests/test_multi_source_recorder_widget.py
git commit -m "feat(recorder): wire Output quality to the encoder; bind maximum recording time to the Timer; drop unused time-format fields"
```

---

### Task 10: Carry-over fixes — Converted Files Clear, log folder setting, version drift, help locale, elapsed wording

**Files:**
- Modify: `ui/converted_files_widget.py` (lines 135–158, 226–244, `_handle_selection_changed` 589, `add_queued_file` 275, `add_converted_file` 383, `clear_table` 564)
- Modify: `utils/paths.py`; `ui/main_window.py` lines 535 and 2448 and `update_settings`
- Modify: `pyproject.toml` line 3; create `tests/test_version.py`
- Modify: `ui/main_window.py` `open_help_document` (2521–2526)
- Modify: `pc_report/sections/noldus_summary.py` lines 235–242 and `build(...)` signature to accept `total_seconds`; `pc_report/sections/noldus_summary.py:263` caller passes `ctx.run` wall clock (see `orchestrator.py:109` `total_seconds`); tests in `tests/pc_report/`
- Test: `tests/test_converted_files_widget.py` (create if absent), `tests/test_paths.py`, `tests/test_version.py`, `tests/pc_report/test_noldus_summary.py`

**Interfaces:**
- Produces: `utils.paths.log_dir(settings: dict | None) -> str`; `ConvertedFilesWidget.clear_button` visible iff `rowCount() > 0`; `noldus_summary.build(results, is_admin, elapsed, total_seconds=None)`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_converted_files_widget.py
class ClearButtonTests(unittest.TestCase):
    def test_clear_button_tracks_row_count(self):
        widget = ConvertedFilesWidget()
        self.assertTrue(widget.clear_button.isHidden())
        widget.add_queued_file("Session 1.mp4", r"C:\Videos")
        self.assertFalse(widget.clear_button.isHidden())
        widget.clear_table()
        self.assertTrue(widget.clear_button.isHidden())

# tests/test_paths.py
class LogDirTests(unittest.TestCase):
    def test_prefers_a_writable_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            wanted = os.path.join(tmp, "nvc-logs")
            self.assertEqual(paths.log_dir({"log_folder": wanted}), wanted)
            self.assertTrue(os.path.isdir(wanted))

    def test_falls_back_when_empty_or_unwritable(self):
        default = paths.get_data_dir("logs")
        self.assertEqual(paths.log_dir({"log_folder": ""}), default)
        self.assertEqual(paths.log_dir(None), default)
        with patch("os.makedirs", side_effect=OSError("nope")):
            self.assertEqual(paths.log_dir({"log_folder": r"Z:\nowhere"}), default)

# tests/test_version.py
class VersionTests(unittest.TestCase):
    def test_pyproject_matches_app_version(self):
        import tomllib
        from utils.version import APP_VERSION
        data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text("utf-8"))
        self.assertEqual(data["project"]["version"], APP_VERSION)

# tests/pc_report/test_noldus_summary.py (append)
    def test_collection_rows_separate_wall_clock_from_summed_time(self):
        section = build({}, False, {"a": 60.0, "b": 310.0}, total_seconds=91.3)
        rows = dict(section["groups"][1]["rows"])
        self.assertEqual(rows["Collection"], "91 s wall clock; 370 s summed across sections")
```

Check the `pyproject.toml` table name (`[project]` vs `[tool.poetry]`) and use the right key.

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement**

`ui/converted_files_widget.py`: remove `clear_button.hide()` at line 158; add `clear_button` to `actions_row` before `play_button` with `theme.opt_out_of_button_style` and `theme.compact_button_style()`; apply the same compact style to `play_button` (drop the `setFixedSize(60, 24)`); add

```python
    def _refresh_clear_button(self):
        self.clear_button.setVisible(self.table_widget.rowCount() > 0)
```

and call it at the end of `add_queued_file`, `add_converted_file`, `clear_table`, and once at the end of `__init__`.

`utils/paths.py`:

```python
def log_dir(settings=None) -> str:
    """The folder for per-file conversion logs.

    Honours Settings -> Folders -> Log Folder when it is set and can be created;
    otherwise the application data logs folder. The root application log is not
    affected: it opens before settings are read.
    """
    wanted = (settings or {}).get("log_folder") if isinstance(settings, dict) else None
    if isinstance(wanted, str) and wanted.strip():
        try:
            os.makedirs(wanted, exist_ok=True)
            return wanted
        except OSError:
            pass
    return get_data_dir("logs")
```

`ui/main_window.py`: line 535 → `self.converted_files_widget.set_log_folder(log_dir(self.settings))`; line 2448 → `log_folder = log_dir(self.settings)`; in `update_settings` (the slot connected to `settings_saved`), add `self.converted_files_widget.set_log_folder(log_dir(self.settings))`. Import `from utils.paths import log_dir`.

`pyproject.toml`: `version = "2.3.0"`.

`open_help_document`: `from utils.localization import saved_locale` and `help_path = resolve_help_document(saved_locale())`. Confirm `resolve_help_document(language)` falls back to English when the localized manual is absent; if it does not, add the fallback there: `return _resolve(language) or (_resolve(DEFAULT_LANGUAGE) if language != DEFAULT_LANGUAGE else None)` in the existing structure.

`pc_report/sections/noldus_summary.py`: change `build(results, is_admin, elapsed)` to `build(results, is_admin, elapsed, total_seconds=None)`; replace the `"Elapsed Total"` row with

```python
        "Collection": (
            f"{total_seconds:.0f} s wall clock; {sum(elapsed.values()):.0f} s summed across sections"
            if total_seconds is not None else f"{sum(elapsed.values()):.0f} s summed across sections"
        ),
```

and pass `total_seconds` from the caller at line 263: find the wall-clock start on `ctx.run` (orchestrator sets `started_at`; expose it as `run.started_at` or compute `time.monotonic() - run.started_at` — add `started_at` to the `RunContext`/run object if absent, set where `started_at = time.monotonic()` is assigned at `orchestrator.py:55`).

- [ ] **Step 4: Run, expect pass; full suite; ruff; commit**

```bash
python -m pytest -q -p no:cacheprovider tests/test_converted_files_widget.py tests/test_paths.py tests/test_version.py tests/pc_report
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/converted_files_widget.py utils/paths.py pc_report/sections/noldus_summary.py pc_report/orchestrator.py tests/test_converted_files_widget.py tests/test_paths.py tests/test_version.py
git add ui/converted_files_widget.py utils/paths.py ui/main_window.py pyproject.toml pc_report tests
git commit -m "fix: show Converted Files Clear; honour Log Folder setting; pyproject version 2.3.0; help opens in the active locale; PC report separates wall-clock from summed time"
```

---

### Task 11: Lead — live verification, ledgers, merge

**Files:**
- Modify: `docs/CHANGELOG.md`, `docs/BACKLOG.md`

- [ ] **Step 1: Live check on the real display**

Write `%TEMP%\nvc_ui_iter2_shots.py` (not in the repo) that builds `VideoConverterApp`, calls `set_window_mode("compact", persist=False)`, shows each tool tab and screen-grabs (`QScreen.grabWindow`) to `%TEMP%\iter2\compact-<tab>.png`, then repeats for `"full"`. Open each PNG. Check: no horizontal scrollbar at 960x600; PC Report fits without scrolling; recorder groups stacked in compact and side by side in full; leaf card visible on every tab; transport icons legible; playlist dock buttons not clipped. Run a PC report once and confirm the heart pulses (watch for ~5 s). Fix anything wrong in a `fix(ui): ...` commit.

- [ ] **Step 2: Ledgers**

`docs/CHANGELOG.md` under `## 2026-09-25`:

```
### User interface

- Two window modes from the burger menu's Window submenu: Compact mode (the
  previous 960x600 layout) and Full window mode (maximised, roomier spacing,
  larger recorder previews). The choice is remembered.
- Every tool tab now sits in a "leaf" card (rounded top-left and bottom-right
  corners), borrowed from VIO; the preview box and drop zones share the shape.
- Buttons follow a hierarchy: the gradient bubble is reserved for Start/Stop and
  dialog buttons; tool tabs use compact buttons, text links and flat icon
  buttons sized for their context.
- PC Report: heart pulses in the logo while a report runs; Open report / Open
  folder are links; the intro and tip text are gone so the tab fits without
  scrolling; new "Run as administrator" link relaunches NVC elevated.
- Media Player: icon transport bar, icon Load/Clear per panel, icon playlist
  actions (fixes the clipped playlist buttons).
- Lossless Editor: compact tool row and icon actions for the merge list.
- Multi-Source Recorder: in Compact mode the Recording properties and Output
  settings stack so neither is squeezed; the File location field shows the end
  of the path; a note appears when USB cameras will be re-encoded in copy mode.

### Fixes

- Video Settings "Output quality" now drives the H.264 encoder (Default /
  High / Balanced / Compact map to preset+CRF); "Use maximum recording time"
  is bound to the tab's Timer; the unused Time format and Decimals fields are
  removed.
- Settings -> Folders -> Log Folder is honoured for per-file conversion logs.
- Converted Files: the Clear button is shown when the table has rows.
- `pyproject.toml` version matches the application (2.3.0), pinned by a test.
- Help opens the manual for the active language when one exists.
- PC report Noldus Summary distinguishes wall-clock collection time from the
  sum of per-section times.
```

`docs/BACKLOG.md`: strike (remove) the fixed items: inert Output quality / Timer settings, Log Folder never read, Converted Files Clear hidden, pyproject drift, help locale pass-through, playlist dock clipping. Add under a new `## UI follow-ups`: "Regenerate the Help manual and screenshots for the new layout, button tiers and Window submenu"; "Translate new strings (Window, Compact mode, Full window mode, Run as administrator, copy-mode note, icon tooltips) for nl and zh-CN"; "Consider persisting the compact window geometry".

- [ ] **Step 3: Full verification**

```
python -m pytest -q -p no:cacheprovider
python -m ruff check ui/theme.py ui/leaf_frame.py ui/glyph_icons.py ui/pc_report_dialog.py ui/lossless_editor_widget.py ui/media_player_widget.py ui/media_player_parts.py ui/converted_files_widget.py utils/config.py utils/paths.py conversion/recording_commands.py pc_report tests
git diff --check
rg -i -c "PBH-80|80JDBS3|paham|NITINC|DC03|NOLDUSINC" ui utils conversion pc_report tests docs/CHANGELOG.md docs/BACKLOG.md
```

Expected: suite exit 0; ruff clean; diff --check exit 0; rg exit 1.

- [ ] **Step 4: Commit and merge**

```bash
git add docs/CHANGELOG.md docs/BACKLOG.md
git commit -m "docs: changelog and backlog for UI iteration 2"
git checkout master
git merge --no-ff ui-iteration-2 -m "Merge ui-iteration-2: window modes, leaf cards, button hierarchy, PC report heart, icon toolbars, carry-over fixes"
python -m pytest -q -p no:cacheprovider
git branch -d ui-iteration-2
```

---

## Self-review

- Spec coverage: §1 window modes → Tasks 1, 4 (+ hooks in 5, 7, 8); §2 leaf → Task 3; §3 tiers + glyphs → Tasks 1, 2, and applied in 5–8, 10; §4 PC Report → 5, Lossless → 6, Media Player → 7, Recorder tab → 8, Video Settings → 9, Converted Files → 10; §5 defects → 9, 10, and run-as-admin in 5; §6 tests are embedded per task; §7 live verification → 11; §8 ledgers → 11.
- Names consistent: `apply_layout_mode(metrics)` (Tasks 4, 5, 7, 8), `theme.metrics()/set_layout_mode()/COMPACT/FULL` (1, 4, 5, 7, 8), `make_icon_button(name, tooltip, color, size)` (2, 6, 7, 8), `compact_button_style`/`link_button_style`/`icon_button_style` (1, 5, 6, 10), `h264_encode_args(quality)` (9), `log_dir(settings)` (10), `tool_tab_cards` (3), `window_mode_actions` (4).
- Ordering: 1 → 2 → 3 → 4 serial (shared `main_window.py`/`theme.py`); 5, 6, 7 independent of each other after 4; 8 → 9 serial (same recorder file); 10 after 3 (main_window edits) — run after 4 to avoid conflicts; 11 last.
