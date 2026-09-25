# UI iteration 2: window modes, leaf frames, button hierarchy, tab polish, defect fixes

Date: 2026-09-25. Branch: `ui-iteration-2`. Owner decisions were made by the lead under the
user's standing instruction "no need to ask permission, simply do".

## Problem

The user reviewed the 2.3.0 build and asked for:

| # | Observation | Request |
|---|-------------|---------|
| 1 | The Multi-Source Recorder tab is crowded at the current window size (~920x570): the File location field truncates, Recording properties and Output settings fight for width, preview tiles are small. | Improve the layout. |
| 2 | Only one window size exists. | Call the current state **Compact mode**; add a **Full window mode**; switch between them from the burger menu. |
| 3 | PC Report tab: the intro text, the pre-filled log text and the "Tip:" footer push the content below the fold so the tab scrolls. | Remove the hint text. Make the tab slicker: Generate / Open report / Open folder as smaller text links or icons; the heart in the logo should pulse while the report runs (an older build had this). |
| 4 | Every button is a large gradient "bubble" because the window stylesheet and `theme.apply_to_buttons()` push `gradient_button_style()` onto every `QPushButton`. | Bubbles only for outer main actions (Start/Stop, Settings dialog buttons). Tool-tab controls sized and styled for their context: compact buttons, icon buttons, link buttons. The Lossless Editor and Media Player especially. |
| 5 | Design language. | Borrow from VIO: keep the NVC colour scheme; use VIO's "leaf" bevel (rounded top-left and bottom-right, square elsewhere) on the per-tab content card and similar surfaces. |
| 6 | The "things you should know" list from the previous report. | Fix them. |
| 7 | Elevated PC report. | Answer whether it is still needed. (Yes: the 09:36 report says `Elevated: No`; TPM, BitLocker, disk reliability and SMB-server fields are still unexercised. The UI gets a one-click relaunch so the user can do it.) |
| 8 | Help docs and localisation. | Do **not** redo them in this iteration. |

## Scope

In scope: `ui/theme.py`, `ui/main_window.py` (burger, window mode, tab cards, global QSS),
`ui/leaf_frame.py` (new), `ui/glyph_icons.py` (new), `ui/pc_report_dialog.py`,
`ui/lossless_editor_widget.py`, `ui/media_player_widget.py`, `ui/media_player_parts.py`,
`ui/multi_source_recorder_widget.py`, `ui/converted_files_widget.py`, `utils/config.py`,
`utils/paths.py`, `conversion/recording_commands.py`, `pc_report/sections/noldus_summary.py` (or
wherever "Collection Elapsed" is computed), `pyproject.toml`, tests, `docs/CHANGELOG.md`,
`docs/BACKLOG.md`.

Out of scope: help manuals, translations (`vio_nl.ts` etc.), new skins, FFmpeg-decoded playback,
any change to the report collectors' data.

## Design

### 1. Window modes

Two modes, persisted in `config.json` as `"window_mode": "compact" | "full"` (default
`"compact"`; `normalize_settings` coerces anything else to `"compact"`).

| | Compact (today's state) | Full window |
|---|---|---|
| Window | `showNormal()`, minimum 900x520, resized to 960x600 when switching into compact | `showMaximized()` |
| Outer margins | 6 px | 12 px |
| Recorder preview tiles | max height 98 | max height 260 |
| Recorder middle row | Recording properties **above** Output settings (stacked, each full width) | side by side (2:1) as today |
| Media Player panel min height | 160 | 240 |
| PC Report logo | 96 px | 140 px |

Mechanism: `ui/theme.py` gains

```python
@dataclass(frozen=True)
class LayoutMetrics:
    name: str                 # "compact" | "full"
    margin: int
    spacing: int
    recorder_tile_max_h: int
    recorder_stacked: bool
    player_panel_min_h: int
    pc_report_logo_w: int

COMPACT = LayoutMetrics("compact", 6, 4, 98, True, 160, 96)
FULL    = LayoutMetrics("full", 12, 8, 260, False, 240, 140)
def metrics() -> LayoutMetrics   # current
def set_layout_mode(name: str)    # validates, stores module-level current
```

`VideoConverterApp.set_window_mode(name, persist=True)` sets the theme metrics, calls
`showMaximized()` / `showNormal()`+`resize(960, 600)`, then calls `apply_layout_mode(metrics)`
on every tool widget that defines it (recorder, media player, PC report; others ignore), saves
settings. Called once at startup after the window is built, before `show()`.

Burger menu: a **Window** submenu directly under Settings with two checkable, mutually
exclusive actions `Compact mode` and `Full window mode` (QActionGroup). Checked state follows
the setting.

Not persisted: window geometry. Full = maximized, compact = 960x600, deterministic.

### 2. Leaf frames

`ui/leaf_frame.py`:

```python
class LeafFrame(QFrame):
    """A card with VIO's leaf silhouette: rounded top-left and bottom-right, square elsewhere."""
    def __init__(self, parent=None, radius: int = 28, dashed: bool = False)
```

Styled by `theme.leaf_style(radius, dashed=False)`, which returns QSS for `QFrame#leaf` with
`background: $panel_bg` (white), `border: 1px solid $separator` (or `1px dashed $accent` when
dashed), `border-top-left-radius: {r}px; border-bottom-right-radius: {r}px;
border-top-right-radius: 0; border-bottom-left-radius: 0`. Contents margins 12.

Applied to:

- **Every tool tab page**: the tab's content widget is placed inside a `LeafFrame(radius=28)`;
  the `QTabWidget::pane` rule loses its border and background (transparent, no radius) so the
  leaf card is the visible surface. The per-tab footer (lock / file / broom icons + status)
  stays inside the card at the bottom.
- **Left preview box** ("No Preview"): `LeafFrame(radius=18, dashed=True)` replaces the current
  dashed rectangle.
- **Drop zones** (Conversion Log and Video Inspection dashed areas): radius 18, dashed.

Stacking rule from VIO is not needed here (one card per tab).

### 3. Button hierarchy

Three tiers, all in `ui/theme.py`:

| Tier | Helper | Use |
|---|---|---|
| Primary bubble | existing `gradient_button_style()` / `dialog_button_style()` | Start/Stop, Settings dialog OK/Cancel/Default/presets, recorder Video Settings dialog buttons |
| Compact | new `compact_button_style(radius=RADIUS_SM)`: accent fill, white text, `padding: 3px 10px`, `min-height: 24px`, no min-width, 9pt semibold; hover/pressed/disabled states | Tool-tab action buttons (Generate PC Report, Trim / Remux / Extract / Remove, Merge, Add files, Browse, Load) |
| Link | new `link_button_style()`: transparent, `$accent_dark`, underline, no border, zero padding, pointing-hand cursor set by the caller | Secondary actions (Open report, Open folder, Video Settings, Show recording log, Open, Run as administrator) |
| Icon | new `icon_button_style(size=28)` for `QToolButton`: flat, `border-radius: 4px`, hover `$accent_tint` background; icon from `glyph_icons` | Media Player transport, per-panel Load/Clear, playlist dock actions, editor list actions |

The window stylesheet's global `QPushButton` rule keeps the gradient colours but drops
`min-width: 100px; min-height: 32px` and reduces padding to `6px 14px`, so a button that is not
explicitly styled is medium, not huge. `apply_to_buttons()` is unchanged; tool widgets opt their
controls out with `theme.opt_out_of_button_style()` and apply the tier style themselves.

`ui/glyph_icons.py`: `glyph_icon(name: str, color: str, size: int = 20) -> QIcon`, painted with
QPainter (antialiased, 1.8 px strokes, filled shapes) so icons tint with the skin. Names:
`play, pause, stop, restart, fullscreen, playlist, volume, muted, add_file, add_folder, remove,
clear, folder_open, report, shield`. Headless-testable: `glyph_icon("play", "#000").pixmap(20)`
is not null and has non-transparent pixels.

### 4. Tab-by-tab

**PC Report** (`ui/pc_report_dialog.py`, `PCReportWidget`):

- Header: logo (96 / 140 px per mode) with the **heart underlay** restored: `heart_label`
  behind `logo_label` in a `QGridLayout` cell, `QGraphicsOpacityEffect`, asset
  `graphics/PCREPORTHEART.png` (`GREENPCREPORTHEART.png` when converting). While the worker runs:
  `QPropertyAnimation(effect, b"opacity")`, 2400 ms, keys 0.0→0.2, 0.5→1.0, 1.0→0.2,
  `InOutSine`, loop −1. On success: stop, opacity 1.0 (solid). On failure/cancel: stop, hide.
- Title "PC Report" and a single-line description "Collects system details for support.
  Redaction is always on." Remove the current two-sentence description, the pre-filled output
  text (use `setPlaceholderText("Report progress appears here.")`) and the "Tip:" footer.
- Action row: `Generate PC Report` (compact tier) · `Open report` (link) · `Open folder` (link)
  · stretch · `Run as administrator` (link; visible only when `not ctypes.windll.shell32.IsUserAnAdmin()`;
  relaunches the app via `ShellExecuteW(None, "runas", sys.executable, args, None, 1)` and, on
  success, closes this instance through the main window's normal quit path). Links are disabled
  until a report exists.
- Progress bar: 6 px tall, no text, directly under the action row.
- Status label stays (one line). Output area takes all remaining height. No scrolling at
  960x600.

**Lossless Editor** (`ui/lossless_editor_widget.py`):

- Title 12pt, description one line 9pt.
- Input row: line edit + `Browse…` (compact).
- Range row: Start / End edits, Output combo.
- Tool row: `Trim`, `Remux`, `Extract audio`, `Remove audio` — compact tier, equal width via
  `QSizePolicy.Expanding`, height 26.
- Merge: list with a right-aligned row of three icon buttons (`add_file`, `clear`) and one compact
  `Merge` button. Text labels move to tooltips.
- Log area unchanged.

**Media Player** (`ui/media_player_widget.py`, `ui/media_player_parts.py`):

- Transport row becomes an icon toolbar of 28 px `QToolButton`s: play/pause (toggles glyph),
  stop, restart · position slider · readout · fullscreen, playlist · Panels combo, Speed combo,
  volume slider (110), mute (toggles glyph). Tooltips carry the former labels ("Play all",
  "Stop all", …) and shortcuts.
- Per panel: the caption row gets `folder_open` (Load) and `clear` icon buttons 24 px at the right;
  the two `QPushButton`s go.
- Playlist dock: the four text buttons become 24 px icon buttons in one row (`add_file`,
  `add_folder`, `remove`, `clear`) with tooltips — this removes the clipping.
- Attribute names used by tests (`play_all_button`, `stop_all_button`, `mute_button`, …) are kept
  but now refer to `QToolButton`s; `tests/test_media_player_widget.py` assertions on `.text()`
  move to `.toolTip()`.

**Multi-Source Recorder** (`ui/multi_source_recorder_widget.py`):

- `apply_layout_mode(metrics)`: preview tile max height; middle row stacked (compact) or side by
  side (full) by re-parenting the two group boxes between a `QVBoxLayout` and a `QHBoxLayout`
  held in a `QStackedLayout`-free way: both layouts exist, the groups are moved with
  `removeWidget`/`addWidget`.
- File location: `QLineEdit` gets `Expanding` policy and shows the **tail** of the path
  (`setCursorPosition(len(text))` after every `setText`) so the folder name is visible; the
  `Open` link becomes a `folder_open` icon button.
- Copy-mode note: a 9pt `$grey_650` label under the Output settings form, visible only when
  Encoding is `copy` **and** any enabled row is a USB (DirectShow) source: "USB cameras are always
  re-encoded to H.264; copy applies to RTSP and file sources." Updated on codec change and on
  row enable/type change.
- Video Settings dialog:
  - **Output quality** wired: `conversion/recording_commands.py` gains
    `H264_QUALITY = {"Default": ("veryfast", "18"), "High": ("medium", "16"),
    "Balanced": ("veryfast", "20"), "Compact": ("faster", "24")}` and
    `h264_encode_args(quality) -> list[str]` (`["-c:v","libx264","-preset",p,"-crf",c]`);
    the seven inline `libx264 … veryfast … 18` sites call it. The recorder passes the dialog's
    quality (persisted in Current Settings / presets under `output_quality`) to every command
    builder. Unknown value → Default.
  - **Timer settings**: `Time format` and `Decimals` are removed (nothing reads them).
    `Use maximum recording time` + its edit are kept and two-way bound to the tab's `Timer`
    field: checking with a value sets `duration_edit`; unchecking clears it; opening the dialog
    pre-fills from `duration_edit`.

**Converted Files** (`ui/converted_files_widget.py`): `Clear` is shown whenever the table has
rows (compact tier, next to `Play`); `Play` still requires a selection.

### 5. Other defects from the previous report

| Item | Fix |
|---|---|
| Settings → Folders "Log Folder" saved but never read | `utils/paths.py` gains `log_dir(settings) -> str`: the setting if non-empty and `os.makedirs(..., exist_ok=True)` succeeds, else `get_data_dir("logs")`. `ui/main_window.py` uses it for the converted-files per-file logs and the conversion log path; re-read on settings save. The root application log (`utils/logger.py`) stays in `%APPDATA%\NVC\logs` (it opens before settings load). |
| `pyproject.toml` 2.2.0 vs `utils/version.py` 2.3.0 | Bump pyproject to 2.3.0; `tests/test_version.py` asserts they match by parsing pyproject with `tomllib`. |
| `open_help_document` ignores the active locale | Pass `current_locale()` to `resolve_help_document`; existing fallback to `en` applies when the localized file does not exist. |
| PC report: Report Health "Total collection time 1 m 31 s" vs Noldus Summary "Collection Elapsed Total 370.0 s" | The 370 s is the sum of per-section durations (sections run in parallel). Noldus Summary row becomes "Collection: 91 s wall clock; 370 s summed across sections". Test asserts both numbers appear with those words. |
| Elevated PC report still not run | "Run as administrator" link (above). The lead cannot trigger UAC autonomously; the user clicks it. |

### 6. Tests

New/changed, all headless via `tests/conftest.py`:

- `tests/test_theme.py`: `compact_button_style` has `min-height: 24px` and no `min-width`;
  `link_button_style` has `text-decoration: underline`; `leaf_style(28)` contains both `28px`
  radii and both `0px` radii; `set_layout_mode` rejects unknown names; `metrics()` round-trips.
- `tests/test_glyph_icons.py`: every name renders a non-null pixmap with opaque pixels; unknown
  name raises `KeyError`.
- `tests/test_config.py`: `window_mode` default and normalisation.
- `tests/test_main_window_layout.py` (new): burger has a Window submenu with two exclusive
  checked actions; `set_window_mode("full")` marks the action and updates `theme.metrics()`;
  each tool tab page's top-level child is a `LeafFrame`.
- `tests/test_pc_report_widget.py`: no widget text starts with "Tip:"; output placeholder set;
  heart animation is running after `on_run` with a stubbed worker and stopped after finish;
  Open report / Open folder have `skipGlobalStyle` and the link style; Run-as-admin link hidden
  when `IsUserAnAdmin` is patched to return 1.
- `tests/test_lossless_editor_widget.py`: tool buttons opt out of the global style and report
  `sizeHint().height() <= 28`.
- `tests/test_media_player_widget.py` / `test_media_player_parts.py`: transport controls are
  `QToolButton`s with non-null icons and the former labels as tooltips; playlist dock has four
  icon buttons and its `sizeHint().width() <= 320`.
- `tests/test_multi_source_recorder_widget.py`: compact metrics stack the groups (the two group
  boxes share a parent `QVBoxLayout`); full metrics put them side by side; copy-mode note
  visibility truth table; `h264_encode_args("High") == [..., "-preset", "medium", "-crf", "16"]`;
  every builder emits the chosen quality; dialog no longer has `time_format_combo`; max-time
  check ↔ `duration_edit` binding.
- `tests/test_converted_files_widget.py`: Clear visible after `add_queued_file`, hidden when empty.
- `tests/test_paths.py`: `log_dir` prefers a writable setting, falls back otherwise.
- `tests/pc_report/test_noldus_summary.py`: wall-clock vs summed wording.

Existing pins to update deliberately: `test_media_player_widget.py` `.text()` → `.toolTip()`;
recorder `sizeHint` ≤ 700x460 stays valid in compact.

### 7. Verification on the real display (lead)

Launch the app in compact and full modes; screenshot every tool tab in both (screen-grab for the
player); confirm no horizontal scrollbars at 960x600, PC Report fits without scrolling, the heart
pulses during a run, the recorder groups stack in compact and sit side by side in full, and the
leaf card is visible on every tab. Full suite exit 0, ruff clean on touched files,
`git diff --check` clean, privacy scan clean.

### 8. Ledgers

`docs/CHANGELOG.md` under `## 2026-09-25`: `### User interface` block (modes, leaf, button
tiers, PC report, player, editor, recorder) and `### Fixes` (log folder, output quality, timer
binding, Clear button, version drift, help locale, elapsed wording). `docs/BACKLOG.md`: strike
the fixed items; add "Help manual must be re-generated for the new layout and controls" and
"translations for new strings (Window submenu, Run as administrator, copy-mode note)".
