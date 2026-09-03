"""The single source of truth for NVC's colours, fonts and stylesheets.

Widgets ask this module for a style; they never spell a colour. That is the
whole point: before this existed the brand teal appeared as a literal in 51
places, alongside four near-duplicate teals doing the work of about two roles,
so changing the accent meant a careful find-and-replace across six spellings.

## The three skins

NVC already had a three-state visual system, spread across `get_icon_path`,
`update_highlight_colors` and `update_preview_controls_style`. This module
names it:

    IDLE     teal       nothing running
    ACTIVE   green      monitoring, converting or recording
    LOCKED   grayscale  the app is locked

Those states are exactly what the `GRAYSCALE*` / `GREEN*` / unprefixed icon
filenames in graphics/ encode, which is why `Skin.icon_prefix` lives here
alongside the colours instead of being rebuilt from strings at each call site.

## Using it

    from ui import theme

    button.setStyleSheet(theme.accent_button_style())
    label.setForeground(theme.skin().text_muted)

To keep a widget correct across a skin change, register it rather than
restyling it by hand:

    theme.theme_manager.register(button, theme.accent_button_style)

`theme_manager.changed` fires on every skin change and `reskin()` re-applies
every registered style function. Registrations hold weak references, so a
closed dialog does not keep its widgets alive.
"""
from __future__ import annotations

import os
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from PyQt5.QtCore import QObject, pyqtSignal

from utils.logger import logger
from utils.resources import resource_path

# ---------------------------------------------------------------------------
# Metrics. Named so a spacing change is one edit, not a hunt for magic numbers.
# ---------------------------------------------------------------------------
RADIUS_SM: Final[int] = 4
RADIUS_MD: Final[int] = 6
RADIUS_LG: Final[int] = 8

PAD_SM: Final[str] = "4px 8px"
PAD_MD: Final[str] = "6px 12px"
PAD_LG: Final[str] = "8px 16px"

FONT_UI: Final[str] = '"Segoe UI", Arial, sans-serif'
FONT_MONO: Final[str] = '"Consolas", "Courier New", monospace'

FONT_SM: Final[int] = 10
FONT_BASE: Final[int] = 11
FONT_LG: Final[int] = 13

# ---------------------------------------------------------------------------
# Semantic colours. These mean the same thing whatever the skin, so they are
# deliberately not per-skin: a warning must not turn green because a conversion
# happens to be running.
# ---------------------------------------------------------------------------
SUCCESS: Final[str] = "#28a745"
WARNING: Final[str] = "#ffc107"
DANGER: Final[str] = "#dc3545"
DANGER_STRONG: Final[str] = "#d10c0c"
INFO: Final[str] = "#0077b5"

# Dark surfaces for video. A video tile stays dark in every skin -- a light
# panel behind a video frame reads as a rendering fault.
VIDEO_BG: Final[str] = "#101417"
VIDEO_PANEL_BG: Final[str] = "#1b2227"
VIDEO_BORDER: Final[str] = "#2c353b"
VIDEO_TEXT: Final[str] = "#cfd6da"        # labels on a dark panel
VIDEO_TEXT_MUTED: Final[str] = "#8a9298"  # placeholder text on a dark panel


@dataclass(frozen=True)
class Skin:
    """One complete visual state. Fields are grouped by role, not by colour."""

    name: str
    display_name: str

    # Which graphics/ icon variant belongs to this state: "", "GREEN" or
    # "GRAYSCALE". See menu_icon().
    icon_prefix: str

    # --- accent ---------------------------------------------------------
    accent: str            # the primary brand colour for this state
    accent_hover: str      # lighter, for :hover
    accent_pressed: str    # darker, for :pressed
    accent_bright: str     # for emphasis on a dark ground
    accent_dark: str       # deepest, for borders against the accent
    accent_tint: str       # a very pale wash, for selected rows and callouts

    # --- surfaces -------------------------------------------------------
    window_bg: str
    panel_bg: str
    panel_alt_bg: str      # zebra striping, headers, sunken wells
    panel_border: str
    inner_border: str      # lighter divider inside a panel
    separator: str

    # --- primary-button gradient ----------------------------------------
    # Spelled out per skin rather than derived from the accents above,
    # because the original three stylesheets were not consistent with each
    # other: the green button borrowed the teal border, and the grey one ran
    # its gradient vertically while the other two ran horizontally. These
    # fields preserve that exactly, so adopting the theme layer changes
    # nothing on screen. Tidy them up as a deliberate visual change.
    grad_from: str
    grad_to: str
    grad_hover_from: str
    grad_hover_to: str
    grad_pressed_from: str
    grad_pressed_to: str
    grad_border: str
    grad_horizontal: bool

    # --- text -----------------------------------------------------------
    text_primary: str      # headings
    text_body: str
    text_muted: str        # secondary and helper text
    text_disabled: str
    text_on_accent: str    # text drawn on top of `accent`


# =========================================================================
# IDLE -- the default teal look. Values taken from the pre-theme code, so
# adopting this module is not meant to change what the app looks like. DO NOT
# change these without intending a visible change.
# =========================================================================
IDLE = Skin(
    name="idle",
    display_name="Idle (teal)",
    icon_prefix="",
    accent="#43a296",
    accent_hover="#4bb3a7",
    accent_pressed="#3a9284",
    accent_bright="#4bb3a7",
    accent_dark="#2d7d6f",
    accent_tint="#e8f3f1",
    window_bg="#f5f5f5",
    panel_bg="#ffffff",
    panel_alt_bg="#f0f0f0",
    panel_border="#dee2e6",
    inner_border="#e9ecef",
    separator="#e0e0e0",
    grad_from="#43a296",
    grad_to="#3a9284",
    grad_hover_from="#4bb3a7",
    grad_hover_to="#43a296",
    grad_pressed_from="#3a9284",
    grad_pressed_to="#2d7d6f",
    grad_border="#2d7d6f",
    grad_horizontal=True,
    text_primary="#2d7d6f",
    text_body="#333333",
    text_muted="#6c757d",
    text_disabled="#9a9a9a",
    text_on_accent="#ffffff",
)

# =========================================================================
# ACTIVE -- green, while monitoring, converting or recording. Same structure,
# green accents, so "something is running" reads at a glance from any widget.
# =========================================================================
ACTIVE = Skin(
    name="active",
    display_name="Active (green)",
    icon_prefix="GREEN",
    accent="#92cb4f",
    accent_hover="#9dd55a",
    accent_pressed="#33a16d",
    accent_bright="#9dd55a",
    accent_dark="#3ca37b",
    accent_tint="#f0fff8",
    window_bg="#f5f5f5",
    panel_bg="#ffffff",
    panel_alt_bg="#f0f0f0",
    panel_border="#dee2e6",
    inner_border="#e9ecef",
    separator="#e0e0e0",
    grad_from="#92cb4f",
    grad_to="#33a16d",
    grad_hover_from="#9dd55a",
    grad_hover_to="#92cb4f",
    grad_pressed_from="#33a16d",
    grad_pressed_to="#2d7d6f",
    grad_border="#2d7d6f",     # teal, as in the original green button
    grad_horizontal=True,
    text_primary="#33a16d",
    text_body="#333333",
    text_muted="#6c757d",
    text_disabled="#9a9a9a",
    text_on_accent="#ffffff",
)

# =========================================================================
# LOCKED -- grayscale. Deliberately desaturated so a locked app is obviously
# inert rather than merely idle.
# =========================================================================
LOCKED = Skin(
    name="locked",
    display_name="Locked (grayscale)",
    icon_prefix="GRAYSCALE",
    accent="#8a8a8a",
    accent_hover="#9a9a9a",
    accent_pressed="#6a6a6a",
    accent_bright="#c5c5c5",
    accent_dark="#7f7f7f",
    accent_tint="#f2f2f2",
    window_bg="#f5f5f5",
    panel_bg="#ffffff",
    panel_alt_bg="#f0f0f0",
    panel_border="#dee2e6",
    inner_border="#e9ecef",
    separator="#e0e0e0",
    grad_from="#8a8a8a",
    grad_to="#7f7f7f",
    grad_hover_from="#9a9a9a",
    grad_hover_to="#8a8a8a",
    grad_pressed_from="#7f7f7f",
    grad_pressed_to="#6a6a6a",
    grad_border="#6a6a6a",
    grad_horizontal=False,     # vertical, as in the original locked button
    text_primary="#6a6a6a",
    text_body="#333333",
    text_muted="#8a8a8a",
    text_disabled="#c5c5c5",
    text_on_accent="#ffffff",
)

ALL_SKINS: Final[tuple[Skin, ...]] = (IDLE, ACTIVE, LOCKED)
_BY_NAME: Final[dict[str, Skin]] = {s.name: s for s in ALL_SKINS}
DEFAULT_SKIN_NAME: Final[str] = IDLE.name


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
def contrast_text(background: str) -> str:
    """Return black or white, whichever stays readable on `background`.

    Used wherever a label sits on a colour that changes with the skin, so the
    text does not have to be re-picked by hand per skin.
    """
    value = background.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#000000"
    # Perceived luminance (ITU-R BT.601), the usual cheap approximation.
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.6 else "#ffffff"


def rgba(hex_color: str, alpha: float) -> str:
    """Turn '#43a296' plus an alpha into a QSS rgba() string."""
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


# ---------------------------------------------------------------------------
# The manager
# ---------------------------------------------------------------------------
class ThemeManager(QObject):
    """Holds the active skin and re-applies registered styles when it changes."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = DEFAULT_SKIN_NAME
        # (weak widget ref, style callable). Weak so a closed dialog's widgets
        # are collectable; VIO keeps strong refs on the window instead, which
        # would leak here because NVC restyles dialogs too.
        self._ops: list[tuple[weakref.ref, Callable[[], str]]] = []

    @property
    def skin(self) -> Skin:
        return _BY_NAME[self._current]

    @property
    def current_name(self) -> str:
        return self._current

    def set_skin(self, name: str) -> bool:
        """Switch skins. Returns True when the skin actually changed."""
        if name not in _BY_NAME:
            logger.warning("Unknown skin %r; keeping %r.", name, self._current)
            return False
        if name == self._current:
            return False
        self._current = name
        self.reskin()
        self.changed.emit()
        return True

    def set_state(self, *, locked: bool, active: bool) -> bool:
        """Pick the skin from the app's own state flags.

        Locked wins over active: a locked app is inert regardless of what it
        was doing, which is what the original get_icon_path did.
        """
        if locked:
            return self.set_skin(LOCKED.name)
        return self.set_skin(ACTIVE.name if active else IDLE.name)

    def register(self, widget, style_fn: Callable[[], str]) -> None:
        """Restyle `widget` with `style_fn()` now and on every skin change.

        This replaces walking the whole widget tree and re-applying styles by
        hand, which is what apply_button_style_to_all_widgets used to do.
        """
        self._ops.append((weakref.ref(widget), style_fn))
        try:
            widget.setStyleSheet(style_fn())
        except RuntimeError:
            logger.debug("register: widget already deleted", exc_info=True)

    def reskin(self) -> None:
        """Re-apply every registered style, dropping any dead widgets."""
        live: list[tuple[weakref.ref, Callable[[], str]]] = []
        for ref, style_fn in self._ops:
            widget = ref()
            if widget is None:
                continue
            try:
                widget.setStyleSheet(style_fn())
                live.append((ref, style_fn))
            except RuntimeError:
                # Wrapped C++ object gone; drop it rather than raising.
                logger.debug("reskin: widget already deleted", exc_info=True)
        self._ops = live


theme_manager: Final[ThemeManager] = ThemeManager()


def skin() -> Skin:
    """The active skin. Style functions call this, so they read live."""
    return theme_manager.skin


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------
# The unprefixed (teal) variant of these does not exist in graphics/, so the
# idle skin borrows another icon of the right colour.
_IDLE_ICON_FALLBACKS: Final[dict[str, str]] = {
    "BURGER": "INFO",
}


def menu_icon(name: str, s: Skin | None = None) -> str:
    """Resolve a graphics/ icon for the current skin.

    Replaces building `GRAYSCALE`/`GREEN`/bare filenames at each call site.
    Falls back to the unprefixed icon when a skin-specific one is missing, so a
    partially themed icon set degrades instead of showing nothing.
    """
    s = s or skin()
    candidates = [f"{s.icon_prefix}{name}"]
    if name in _IDLE_ICON_FALLBACKS and not s.icon_prefix:
        candidates.append(_IDLE_ICON_FALLBACKS[name])
    candidates.append(name)

    for candidate in candidates:
        path = resource_path(f"graphics/{candidate}.ico")
        if os.path.exists(path):
            return path
    # Return the conventional path even when absent: callers pass it to QIcon,
    # which tolerates a missing file, and the name aids debugging.
    return resource_path(f"graphics/{s.icon_prefix}{name}.ico")


# ---------------------------------------------------------------------------
# Stylesheet functions. Each reads the live skin, so a caller never needs to
# pass colours in, and re-calling after a skin change is all reskin() does.
# ---------------------------------------------------------------------------
def accent_button_style(radius: int = RADIUS_SM) -> str:
    s = skin()
    return (
        f"QPushButton {{ background-color: {s.accent}; color: {s.text_on_accent}; "
        f"border: none; border-radius: {radius}px; padding: {PAD_MD}; "
        f"font-family: {FONT_UI}; font-size: {FONT_BASE}px; font-weight: 600; }} "
        f"QPushButton:hover {{ background-color: {s.accent_hover}; }} "
        f"QPushButton:pressed {{ background-color: {s.accent_pressed}; }} "
        f"QPushButton:disabled {{ background-color: {s.separator}; "
        f"color: {s.text_disabled}; }}"
    )


def secondary_button_style(radius: int = RADIUS_SM) -> str:
    s = skin()
    return (
        f"QPushButton {{ background-color: {s.panel_bg}; color: {s.accent}; "
        f"border: 1px solid {s.accent}; border-radius: {radius}px; "
        f"padding: {PAD_MD}; font-family: {FONT_UI}; font-size: {FONT_BASE}px; }} "
        f"QPushButton:hover {{ background-color: {s.accent_tint}; }} "
        f"QPushButton:pressed {{ background-color: {s.accent}; "
        f"color: {s.text_on_accent}; }} "
        f"QPushButton:disabled {{ border-color: {s.separator}; "
        f"color: {s.text_disabled}; }}"
    )


def danger_button_style(radius: int = RADIUS_SM) -> str:
    return (
        f"QPushButton {{ background-color: {DANGER}; color: #ffffff; border: none; "
        f"border-radius: {radius}px; padding: {PAD_MD}; font-family: {FONT_UI}; "
        f"font-size: {FONT_BASE}px; font-weight: 600; }} "
        f"QPushButton:hover {{ background-color: {DANGER_STRONG}; }}"
    )


def gradient_button_style() -> str:
    """The main action buttons: a gradient in the current skin's colours.

    Replaces three near-identical hardcoded stylesheets selected by an
    if/elif on locked/active state.
    """
    s = skin()
    axis = "x1:0, y1:0, x2:1, y2:0" if s.grad_horizontal else "x1:0, y1:0, x2:0, y2:1"

    def grad(start: str, end: str) -> str:
        return f"qlineargradient({axis}, stop:0 {start}, stop:1 {end})"

    return (
        f"QPushButton {{ background: {grad(s.grad_from, s.grad_to)}; "
        f"color: {s.text_on_accent}; border: 1px solid {s.grad_border}; "
        f"border-radius: {RADIUS_MD}px; padding: {PAD_LG}; "
        f"font-weight: bold; font-size: 9pt; }} "
        f"QPushButton:hover {{ "
        f"background: {grad(s.grad_hover_from, s.grad_hover_to)}; }} "
        f"QPushButton:pressed {{ "
        f"background: {grad(s.grad_pressed_from, s.grad_pressed_to)}; }}"
    )


def dialog_button_style(s: Skin | None = None) -> str:
    """A dialog's OK/Cancel button.

    Differs from gradient_button_style in two ways the originals established:
    the gradient always runs vertically here, and the button carries a minimum
    size so a short label still gives a comfortable target. Takes an explicit
    skin because dialogs pick one from their parent's lock state rather than
    from the global theme.
    """
    s = s or skin()
    def grad(start: str, end: str) -> str:
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {start}, stop:1 {end})"

    return (
        f"QPushButton {{ background: {grad(s.grad_from, s.grad_to)}; "
        f"color: {s.text_on_accent}; border: 1px solid {s.grad_border}; "
        f"border-radius: {RADIUS_MD}px; padding: {PAD_LG}; "
        f"min-width: 80px; min-height: 28px; font-weight: bold; }} "
        f"QPushButton:hover {{ "
        f"background: {grad(s.grad_hover_from, s.grad_hover_to)}; }} "
        f"QPushButton:pressed {{ "
        f"background: {grad(s.grad_pressed_from, s.grad_pressed_to)}; }}"
    )


def skin_for_state(*, locked: bool, active: bool = False) -> Skin:
    """The skin matching a set of state flags, without changing the global one."""
    if locked:
        return LOCKED
    return ACTIVE if active else IDLE


def highlight_color() -> str:
    """The accent used for tab underlines and preview controls."""
    return skin().accent


def tab_bar_style() -> str:
    """The tab strip, underlined in the current accent."""
    s = skin()
    return (
        f"QTabWidget::pane {{ border: 1px solid {s.panel_border}; "
        f"border-radius: {RADIUS_MD}px; background: {s.panel_bg}; }} "
        f"QTabBar::tab {{ background: {s.panel_alt_bg}; color: {s.text_muted}; "
        f"padding: {PAD_MD}; margin-right: 2px; "
        f"border-top-left-radius: {RADIUS_SM}px; "
        f"border-top-right-radius: {RADIUS_SM}px; "
        f"font-family: {FONT_UI}; font-size: {FONT_BASE}px; }} "
        f"QTabBar::tab:selected {{ background: {s.panel_bg}; color: {s.text_primary}; "
        f"border-bottom: 3px solid {s.accent}; font-weight: 600; }} "
        f"QTabBar::tab:hover:!selected {{ color: {s.text_body}; }}"
    )


def panel_style(radius: int = RADIUS_LG) -> str:
    s = skin()
    return (f"background: {s.panel_bg}; border: 1px solid {s.panel_border}; "
            f"border-radius: {radius}px;")


def drop_zone_style(radius: int = RADIUS_LG) -> str:
    """The dashed drag-and-drop target, which highlights on hover."""
    s = skin()
    return (
        f"QWidget {{ background: {s.panel_bg}; "
        f"border: 2px dashed {s.panel_border}; border-radius: {radius}px; "
        f"margin: 10px; }} "
        f"QWidget:hover {{ border-color: {s.accent}; "
        f"background: {rgba(s.accent, 0.1)}; }}"
    )


def preview_box_style(radius: int = RADIUS_LG) -> str:
    """The sidebar preview frame: a dashed drop target that accents on hover."""
    s = skin()
    return (
        f"QFrame {{ background: {s.panel_bg}; "
        f"border: 2px dashed {s.panel_border}; border-radius: {radius}px; }} "
        f"QFrame:hover {{ border: 2px dashed {s.accent}; "
        f"background: {rgba(s.accent, 0.05)}; }}"
    )


def preview_placeholder_style(color: str | None = None) -> str:
    """The 'No Preview' text inside the preview box."""
    return (
        f"QLabel {{ color: {color or skin().accent}; font-size: 14px; "
        f"font-weight: normal; background-color: transparent; border: none; }}"
    )


def preview_overlay_button_style(highlight: str | None = None) -> str:
    """The small play/pause button floating over the preview thumbnail.

    Sits on video, so its resting colour is a translucent black rather than a
    skin surface; only the hover state takes the accent.
    """
    accent = highlight or skin().accent
    return (
        f"QPushButton {{ background-color: rgba(0, 0, 0, 0.6); "
        f"border-radius: 11px; border: 1px solid rgba(255, 255, 255, 0.3); "
        f"padding: 0px; min-width: 22px; max-width: 22px; "
        f"min-height: 22px; max-height: 22px; }} "
        f"QPushButton:hover {{ background-color: {rgba(accent, 0.8)}; "
        f"border: 1px solid {accent}; border-radius: 11px; }}"
    )


def preview_scrubber_style(highlight: str | None = None) -> str:
    """The thin timeline slider over the preview thumbnail."""
    accent = highlight or skin().accent
    return (
        f"QSlider::groove:horizontal {{ height: 4px; "
        f"background: rgba(255, 255, 255, 0.35); border-radius: 2px; }} "
        f"QSlider::sub-page:horizontal {{ height: 4px; "
        f"background: {rgba(accent, 0.9)}; border-radius: 2px; }} "
        f"QSlider::add-page:horizontal {{ height: 4px; "
        f"background: rgba(255, 255, 255, 0.25); border-radius: 2px; }} "
        f"QSlider::handle:horizontal {{ width: 8px; margin: -3px 0; "
        f"border-radius: 4px; background: rgba(255, 255, 255, 0.75); "
        f"border: 1px solid rgba(0, 0, 0, 0.2); }}"
    )


def drop_zone_active_style(radius: int = RADIUS_LG) -> str:
    """A drop zone while a drag is over it: solid accent border, tinted fill."""
    s = skin()
    return (
        f"QWidget {{ background: {rgba(s.accent, 0.1)}; "
        f"border: 2px solid {s.accent}; border-radius: {radius}px; "
        f"margin: 10px; }}"
    )


def drop_zone_label_style(object_name: str) -> str:
    s = skin()
    return (
        f"QLabel#{object_name} {{ color: {s.text_muted}; font-size: {FONT_BASE}px; "
        f"background: {s.panel_bg}; border-radius: {RADIUS_LG}px; "
        f"border: 1px solid {s.panel_border}; padding: 12px; }}"
    )


def log_view_style() -> str:
    s = skin()
    return (
        f"QPlainTextEdit, QTextEdit {{ background: {s.panel_bg}; "
        f"color: {s.text_body}; border: 1px solid {s.panel_border}; "
        f"border-radius: {RADIUS_MD}px; font-family: {FONT_MONO}; "
        f"font-size: {FONT_SM}px; }}"
    )


def tab_title_style() -> str:
    """The large accent heading at the top of a tool tab."""
    s = skin()
    return (f"font-size: 18px; font-weight: bold; color: {s.accent}; "
            f"font-family: {FONT_UI};")


def tab_description_style() -> str:
    """The small explanatory line under a tab title."""
    s = skin()
    return f"color: {s.text_muted}; font-size: {FONT_BASE}px; font-family: {FONT_UI};"


def video_label_style(size: int = FONT_SM, muted: bool = False) -> str:
    """A label sitting on a dark video panel."""
    color = VIDEO_TEXT_MUTED if muted else VIDEO_TEXT
    return f"color: {color}; font-size: {size}px;"


def group_title_style() -> str:
    s = skin()
    return (f"color: {s.text_primary}; font-family: {FONT_UI}; "
            f"font-size: {FONT_LG}px; font-weight: 600;")


def muted_label_style() -> str:
    s = skin()
    return f"color: {s.text_muted}; font-family: {FONT_UI}; font-size: {FONT_SM}px;"


def status_label_style(state: str = "idle") -> str:
    """Footer status text. `state` is idle | active | error | warning."""
    s = skin()
    color = {
        "active": s.accent,
        "error": DANGER,
        "warning": WARNING,
    }.get(state, s.text_muted)
    return (f"color: {color}; font-family: {FONT_UI}; font-size: {FONT_SM}px; "
            f"font-weight: 600;")


def video_surface_style(radius: int = RADIUS_MD) -> str:
    """A video tile. Stays dark in every skin."""
    return f"background: {VIDEO_BG}; border-radius: {radius}px;"


def video_panel_style(radius: int = RADIUS_LG) -> str:
    return (f"background: {VIDEO_PANEL_BG}; border: 1px solid {VIDEO_BORDER}; "
            f"border-radius: {radius}px;")


def table_style() -> str:
    s = skin()
    return (
        f"QTableWidget, QTableView {{ background: {s.panel_bg}; "
        f"alternate-background-color: {s.panel_alt_bg}; "
        f"gridline-color: {s.inner_border}; color: {s.text_body}; "
        f"border: 1px solid {s.panel_border}; border-radius: {RADIUS_MD}px; "
        f"font-family: {FONT_UI}; font-size: {FONT_SM}px; }} "
        f"QHeaderView::section {{ background: {s.panel_alt_bg}; "
        f"color: {s.text_primary}; padding: {PAD_SM}; border: none; "
        f"border-bottom: 1px solid {s.panel_border}; font-weight: 600; }} "
        f"QTableWidget::item:selected {{ background: {s.accent}; "
        f"color: {s.text_on_accent}; }}"
    )


def input_style() -> str:
    s = skin()
    return (
        f"QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ "
        f"background: {s.panel_bg}; color: {s.text_body}; "
        f"border: 1px solid {s.panel_border}; border-radius: {RADIUS_SM}px; "
        f"padding: {PAD_SM}; font-family: {FONT_UI}; font-size: {FONT_BASE}px; }} "
        f"QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ "
        f"border-color: {s.accent}; }} "
        f"QLineEdit:disabled, QComboBox:disabled {{ background: {s.panel_alt_bg}; "
        f"color: {s.text_disabled}; }}"
    )


def progress_bar_style() -> str:
    s = skin()
    return (
        f"QProgressBar {{ background: {s.panel_alt_bg}; border: none; "
        f"border-radius: {RADIUS_SM}px; height: 8px; text-align: center; "
        f"color: {s.text_body}; font-size: {FONT_SM}px; }} "
        f"QProgressBar::chunk {{ background: {s.accent}; "
        f"border-radius: {RADIUS_SM}px; }}"
    )


def window_style() -> str:
    """Application-level defaults, applied once to the main window."""
    s = skin()
    return (
        f"QMainWindow, QDialog {{ background: {s.window_bg}; }} "
        f"QLabel {{ color: {s.text_body}; font-family: {FONT_UI}; }} "
        f"QToolTip {{ background: {s.panel_bg}; color: {s.text_body}; "
        f"border: 1px solid {s.panel_border}; padding: 4px; }}"
    )
