# Media Player: Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Media Player tab into a usable review player: volume/mute, fullscreen, keyboard shortcuts, ffprobe-backed frame stepping with a millisecond/frame readout, a per-panel playlist, a *Play in Media Player* route from the Converted Files tab, an inline convert-to-MP4 offer when Windows cannot decode a file, and persisted player settings.

**Architecture:** `ui/media_player_widget.py` stays the `QMediaPlayer`/`QVideoWidget` host (`MediaPlayerWidget` + `PlayerPanel`). Pure, Qt-free logic (timecode/frame math, ffprobe parsing, unsupported-file message, fixed convert preset, playlist model) moves into a new `ui/media_player_support.py` so it is unit-tested without a display. Small Qt sub-widgets (playlist dock, unsupported-file overlay, fullscreen host) live in a new `ui/media_player_parts.py`. The Converted Files widget gains a `play_requested` signal that `ui/main_window.py` routes to the player. Persistence is a `media_player` group in `utils/config.py`.

**Tech Stack:** Python 3.12, PyQt5 (`QtMultimedia`, `QtMultimediaWidgets`), FFmpeg/FFprobe binaries at the repo root (`utils.resources.resource_path("ffprobe.exe")`), pytest (headless, `QT_QPA_PLATFORM=offscreen` set by `conftest.py`), ruff.

Spec: `docs/superpowers/specs/2026-09-25-media-player-complete-design.md`.

## Global Constraints

- Never call `QTimer.singleShot`. Use a `QTimer(self)` instance with `setSingleShot(True)`, or the pattern `self._schedule(msec, callback)` defined in Task 5 below.
- Every user-facing string goes through the module's `_tr()` with a plain string literal; interpolate with `%` *after* `_tr(...)`. Never `_tr(f"...")`.
- Tests are headless. The pytest exit code is the pass signal (`-q` is set by config; the summary line is suppressed). Under PowerShell, wildcards in pytest paths do **not** expand: list files explicitly.
- `python -m ruff check <every file you touched>` must exit 0. Do not lint-clean files you did not otherwise touch.
- Never write real identifying values from this machine (hostnames, user names, real paths containing the user name, serials) into code, tests or fixtures. Use `C:\\Videos\\clip.mp4`-style stand-ins.
- Do not touch `visible_tool_tabs.media_player` default (stays `False`), the sidebar `PreviewController`, or `ui/multi_source_recorder_widget.py`.
- Follow TDD: write the failing test, run it and see it fail, implement, run it and see it pass, commit.
- Work on branch `media-player-complete` created from `master`; never `git pull` (no remote).
- PowerShell quirk: complex one-liners with quotes/brackets break. Write probe scripts to `$env:TEMP\*.py` and run them.

## File Structure

| File | Responsibility |
|------|----------------|
| `utils/config.py` (modify) | `media_player` defaults + normalisation. |
| `ui/media_player_support.py` (create) | Qt-free helpers: `format_timecode_ms`, `parse_frame_rate`, `frame_step_ms`, `frame_index`, `total_frames`, `format_readout`, `probe_media_info`, `unsupported_message`, `player_convert_settings`, `PlaylistModel`, `MEDIA_PLAYER_DEFAULTS`, `DEFAULT_FPS`. |
| `ui/media_player_parts.py` (create) | Qt sub-widgets: `PlaylistDock`, `UnsupportedOverlay`, `FullscreenHost`. |
| `ui/media_player_widget.py` (modify) | Host: volume/mute, fullscreen, shortcuts, frame step + readout, selected panel, playlist wiring, error path + convert, persistence. `PlayerPanel` gains probe cache, selection, error/overlay hooks. |
| `ui/converted_files_widget.py` (modify) | `play_requested` signal, *Play in Media Player* menu item, *Play* button. |
| `ui/main_window.py` (modify) | Passes settings/save/threadpool to the player; `play_in_media_player(path)`. |
| `tests/test_media_player_support.py` (create) | Pure-function tests. |
| `tests/test_media_player_parts.py` (create) | Sub-widget tests. |
| `tests/test_media_player_widget.py` (modify) | Widget behaviour tests + real-file smoke. |
| `tests/test_converted_files_widget.py` (create) | Signal/menu/button tests. |
| `tests/test_main_window_media_player.py` (create) | Converted → player routing. |
| `tests/test_config.py` (modify) | `media_player` group round-trip. |
| `docs/CHANGELOG.md`, `docs/BACKLOG.md` (modify) | Release notes and follow-ups. |

---

### Task 0: Branch

- [ ] **Step 1: Create the branch**

```bash
git checkout master
git status --short
git checkout -b media-player-complete
```

Expected: clean status, `Switched to a new branch 'media-player-complete'`.

---

### Task 1: `media_player` Settings Group

**Files:**
- Modify: `utils/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `default_settings["media_player"] == {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False}`; `normalize_settings` clamps `volume` to 0–100, coerces `panel_count` to one of `1, 2, 4` (else 2), `muted` to bool, `last_folder` to str.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py` inside the existing test class (read the file first; mirror how it imports `normalize_settings` and `default_settings`):

```python
    def test_media_player_defaults_are_present(self):
        normalized = normalize_settings({})
        self.assertEqual(
            normalized["media_player"],
            {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False},
        )

    def test_media_player_group_is_normalized(self):
        normalized = normalize_settings({"media_player": {
            "last_folder": 123, "panel_count": 3, "volume": 250, "muted": "yes",
        }})
        self.assertEqual(normalized["media_player"]["last_folder"], "123")
        self.assertEqual(normalized["media_player"]["panel_count"], 2)
        self.assertEqual(normalized["media_player"]["volume"], 100)
        self.assertTrue(normalized["media_player"]["muted"])
        normalized = normalize_settings({"media_player": {"panel_count": "4", "volume": -5}})
        self.assertEqual(normalized["media_player"]["panel_count"], 4)
        self.assertEqual(normalized["media_player"]["volume"], 0)

    def test_media_player_group_survives_non_dict(self):
        normalized = normalize_settings({"media_player": "garbage"})
        self.assertEqual(normalized["media_player"]["panel_count"], 2)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_config.py -k media_player`
Expected: exit 1, `KeyError: 'media_player'`.

- [ ] **Step 3: Implement**

In `utils/config.py`, add after the `visible_tool_tabs` entry inside `default_settings` (keep the closing brace structure):

```python
    "media_player": {
        "last_folder": "",
        "panel_count": 2,
        "volume": 100,
        "muted": False,
    },
```

Add a helper above `normalize_settings`:

```python
MEDIA_PLAYER_PANEL_COUNTS = (1, 2, 4)


def normalize_media_player_settings(group):
    defaults = default_settings["media_player"]
    if not isinstance(group, dict):
        group = {}
    try:
        panel_count = int(group.get("panel_count", defaults["panel_count"]))
    except (TypeError, ValueError):
        panel_count = defaults["panel_count"]
    if panel_count not in MEDIA_PLAYER_PANEL_COUNTS:
        panel_count = defaults["panel_count"]
    try:
        volume = int(group.get("volume", defaults["volume"]))
    except (TypeError, ValueError):
        volume = defaults["volume"]
    return {
        "last_folder": str(group.get("last_folder", "") or ""),
        "panel_count": panel_count,
        "volume": max(0, min(100, volume)),
        "muted": bool(group.get("muted", False)),
    }
```

In `normalize_settings`, before `return normalized`:

```python
    normalized["media_player"] = normalize_media_player_settings(normalized.get("media_player"))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_config.py` then `python -m ruff check utils/config.py tests/test_config.py`
Expected: exit 0 both.

- [ ] **Step 5: Commit**

```bash
git add utils/config.py tests/test_config.py
git commit -m "feat: add media_player settings group"
```

---

### Task 2: Timecode and Frame Math

**Files:**
- Create: `ui/media_player_support.py`
- Create: `tests/test_media_player_support.py`

**Interfaces:**
- Produces (all in `ui/media_player_support.py`):
  - `DEFAULT_FPS = 25.0`
  - `format_timecode_ms(milliseconds) -> str` — always `H:MM:SS.mmm`, e.g. `0:00:01.500`; bad/negative → `0:00:00.000`.
  - `parse_frame_rate(text) -> float` — `"30000/1001"` → `29.97002997…`, `"25"` → `25.0`, `"0/0"`, `""`, `None`, `"abc"` → `0.0`.
  - `frame_step_ms(fps) -> int` — `round(1000 / fps)`; `fps <= 0` → `frame_step_ms(DEFAULT_FPS)` = 40.
  - `frame_index(position_ms, fps) -> int` — `floor(position_ms * fps / 1000)`, never negative.
  - `total_frames(duration_ms, fps, nb_frames=0) -> int` — `nb_frames` when `> 0`, else `floor(duration_ms * fps / 1000)`.
  - `format_readout(position_ms, duration_ms, fps, nb_frames=0) -> str` — `"<pos> / <dur> · frame N / total"` when `fps > 0`, else `"<pos> / <dur>"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_media_player_support.py`:

```python
import unittest

from ui.media_player_support import (
    DEFAULT_FPS,
    format_readout,
    format_timecode_ms,
    frame_index,
    frame_step_ms,
    parse_frame_rate,
    total_frames,
)


class TimecodeTests(unittest.TestCase):
    def test_format_timecode_ms_always_has_hours_and_millis(self):
        self.assertEqual(format_timecode_ms(0), "0:00:00.000")
        self.assertEqual(format_timecode_ms(1_500), "0:00:01.500")
        self.assertEqual(format_timecode_ms(3_661_007), "1:01:01.007")

    def test_format_timecode_ms_handles_bad_input(self):
        self.assertEqual(format_timecode_ms(None), "0:00:00.000")
        self.assertEqual(format_timecode_ms(-20), "0:00:00.000")


class FrameMathTests(unittest.TestCase):
    def test_parse_frame_rate_accepts_ratios_and_numbers(self):
        self.assertAlmostEqual(parse_frame_rate("30000/1001"), 29.97, places=2)
        self.assertEqual(parse_frame_rate("25"), 25.0)
        self.assertEqual(parse_frame_rate("60/1"), 60.0)

    def test_parse_frame_rate_rejects_garbage(self):
        for text in ("0/0", "", None, "abc", "1/0"):
            self.assertEqual(parse_frame_rate(text), 0.0, text)

    def test_frame_step_ms_per_rate(self):
        self.assertEqual(frame_step_ms(25), 40)
        self.assertEqual(frame_step_ms(parse_frame_rate("24000/1001")), 42)
        self.assertEqual(frame_step_ms(parse_frame_rate("30000/1001")), 33)
        self.assertEqual(frame_step_ms(60), 17)
        self.assertEqual(frame_step_ms(0), frame_step_ms(DEFAULT_FPS))

    def test_frame_index_floors_and_never_negative(self):
        self.assertEqual(frame_index(0, 25), 0)
        self.assertEqual(frame_index(39, 25), 0)
        self.assertEqual(frame_index(40, 25), 1)
        self.assertEqual(frame_index(1000, 29.97), 29)
        self.assertEqual(frame_index(-500, 25), 0)

    def test_total_frames_prefers_probe_count(self):
        self.assertEqual(total_frames(2000, 25, nb_frames=51), 51)
        self.assertEqual(total_frames(2000, 25), 50)
        self.assertEqual(total_frames(0, 0), 0)

    def test_format_readout_with_and_without_frame_rate(self):
        self.assertEqual(
            format_readout(1_000, 2_000, 25, nb_frames=50),
            "0:00:01.000 / 0:00:02.000 · frame 25 / 50",
        )
        self.assertEqual(format_readout(1_000, 2_000, 0), "0:00:01.000 / 0:00:02.000")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_support.py`
Expected: exit 1/2, `ModuleNotFoundError: No module named 'ui.media_player_support'`.

- [ ] **Step 3: Implement**

Create `ui/media_player_support.py`:

```python
"""Qt-free helpers for the Media Player tab.

Everything here is plain Python so it can be unit-tested without a display:
timecode/frame arithmetic, ffprobe parsing, the unsupported-file message, the
fixed "convert and play" preset, and the playlist model.
"""
import math

DEFAULT_FPS = 25.0

MEDIA_PLAYER_DEFAULTS = {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False}


def format_timecode_ms(milliseconds):
    """Format a millisecond position as H:MM:SS.mmm (hours always shown)."""
    try:
        total_ms = int(max(0, milliseconds))
    except (TypeError, ValueError):
        total_ms = 0
    total_seconds, millis = divmod(total_ms, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def parse_frame_rate(text):
    """Turn ffprobe's r_frame_rate ("30000/1001", "25") into a float; 0.0 when unusable."""
    if text is None:
        return 0.0
    value = str(text).strip()
    if not value:
        return 0.0
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator = float(denominator)
            if denominator == 0:
                return 0.0
            fps = float(numerator) / denominator
        else:
            fps = float(value)
    except (TypeError, ValueError):
        return 0.0
    return fps if fps > 0 else 0.0


def frame_step_ms(fps):
    if not fps or fps <= 0:
        fps = DEFAULT_FPS
    return max(1, int(round(1000.0 / fps)))


def frame_index(position_ms, fps):
    if not fps or fps <= 0 or not position_ms or position_ms <= 0:
        return 0
    return int(math.floor(position_ms * fps / 1000.0))


def total_frames(duration_ms, fps, nb_frames=0):
    try:
        if int(nb_frames) > 0:
            return int(nb_frames)
    except (TypeError, ValueError):
        pass
    return frame_index(duration_ms, fps)


def format_readout(position_ms, duration_ms, fps, nb_frames=0):
    text = f"{format_timecode_ms(position_ms)} / {format_timecode_ms(duration_ms)}"
    if fps and fps > 0:
        text += f" · frame {frame_index(position_ms, fps)} / {total_frames(duration_ms, fps, nb_frames)}"
    return text
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_media_player_support.py` and `python -m ruff check ui/media_player_support.py tests/test_media_player_support.py`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add ui/media_player_support.py tests/test_media_player_support.py
git commit -m "feat: media player timecode and frame math helpers"
```

---

### Task 3: ffprobe Info, Unsupported Message, Convert Preset

**Files:**
- Modify: `ui/media_player_support.py`
- Test: `tests/test_media_player_support.py`

**Interfaces:**
- Produces:
  - `probe_media_info(path, runner=subprocess.run) -> dict` with keys `ok: bool, fps: float, nb_frames: int, duration_ms: int, container: str, vcodec: str, acodec: str`. Runs `ffprobe -v error -show_entries stream=codec_type,codec_name,r_frame_rate,avg_frame_rate,nb_frames:format=format_name,duration -of json <path>` through `runner(command, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT, startupinfo=..., creationflags=...)`. Any exception or non-zero return → `{"ok": False, ...zeros/empties}`.
  - `unsupported_message(info) -> str` — `"Windows cannot play <vcodec>/<acodec> in <container>."` (missing parts fall back to `"unknown"`; audio-less: `"Windows cannot play <vcodec> in <container>."`); `info["ok"] is False` → `"Windows cannot play this file."`.
  - `player_convert_settings(base_settings) -> dict` — copy of `base_settings` with the fixed preset applied (see Step 3).
  - `FFPROBE_TIMEOUT` re-exported from `utils.subprocess_helpers`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_player_support.py` (add `import json`, `import subprocess` at top and extend the import list with `probe_media_info, unsupported_message, player_convert_settings`):

```python
PROBE_JSON = {
    "streams": [
        {"codec_type": "video", "codec_name": "hevc", "r_frame_rate": "30000/1001",
         "avg_frame_rate": "30000/1001", "nb_frames": "300"},
        {"codec_type": "audio", "codec_name": "opus", "r_frame_rate": "0/0"},
    ],
    "format": {"format_name": "matroska,webm", "duration": "10.010000"},
}


class ProbeTests(unittest.TestCase):
    def test_probe_media_info_parses_streams_and_format(self):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(PROBE_JSON), stderr="")

        info = probe_media_info("C:\\Videos\\clip.mkv", runner=runner)
        self.assertTrue(info["ok"])
        self.assertAlmostEqual(info["fps"], 29.97, places=2)
        self.assertEqual(info["nb_frames"], 300)
        self.assertEqual(info["duration_ms"], 10_010)
        self.assertEqual(info["container"], "matroska")
        self.assertEqual(info["vcodec"], "hevc")
        self.assertEqual(info["acodec"], "opus")
        self.assertEqual(calls[0][-1], "C:\\Videos\\clip.mkv")
        self.assertIn("-show_entries", calls[0])
        self.assertIn("json", calls[0])

    def test_probe_media_info_falls_back_to_avg_frame_rate(self):
        payload = {"streams": [{"codec_type": "video", "codec_name": "h264",
                                "r_frame_rate": "0/0", "avg_frame_rate": "25/1"}],
                   "format": {"format_name": "mov,mp4,m4a", "duration": "2"}}
        info = probe_media_info("x.mp4", runner=lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(payload), ""))
        self.assertEqual(info["fps"], 25.0)
        self.assertEqual(info["container"], "mov")
        self.assertEqual(info["acodec"], "")

    def test_probe_media_info_reports_failure(self):
        def boom(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)

        info = probe_media_info("x.mp4", runner=boom)
        self.assertFalse(info["ok"])
        self.assertEqual(info["fps"], 0.0)
        failed = probe_media_info("x.mp4", runner=lambda c, **k: subprocess.CompletedProcess(c, 1, "", "bad"))
        self.assertFalse(failed["ok"])
        garbage = probe_media_info("x.mp4", runner=lambda c, **k: subprocess.CompletedProcess(c, 0, "not json", ""))
        self.assertFalse(garbage["ok"])


class UnsupportedMessageTests(unittest.TestCase):
    def test_message_names_codecs_and_container(self):
        info = {"ok": True, "vcodec": "hevc", "acodec": "opus", "container": "matroska"}
        self.assertEqual(unsupported_message(info), "Windows cannot play hevc/opus in matroska.")

    def test_message_without_audio_and_with_gaps(self):
        self.assertEqual(
            unsupported_message({"ok": True, "vcodec": "prores", "acodec": "", "container": "mov"}),
            "Windows cannot play prores in mov.",
        )
        self.assertEqual(
            unsupported_message({"ok": True, "vcodec": "", "acodec": "", "container": ""}),
            "Windows cannot play unknown in unknown.",
        )

    def test_message_when_probe_failed(self):
        self.assertEqual(unsupported_message({"ok": False}), "Windows cannot play this file.")


class ConvertPresetTests(unittest.TestCase):
    def test_player_convert_settings_pins_the_fixed_preset(self):
        base = {"destination_folder": "C:\\Videos\\Out", "video_codec": "libx265", "use_gpu": True,
                "copy_only": True, "text_overlay": "Elapsed Time", "delete_after_conversion": True,
                "use_backup": True, "custom_console_command": "-vf hflip", "output_format": "gif"}
        settings = player_convert_settings(base)
        self.assertEqual(settings["destination_folder"], "C:\\Videos\\Out")
        self.assertEqual(settings["output_format"], "mp4")
        self.assertEqual(settings["video_codec"], "libx264")
        self.assertEqual(settings["audio_codec"], "aac")
        self.assertEqual(settings["audio_bitrate"], "160k")
        self.assertFalse(settings["use_gpu"])
        self.assertFalse(settings["copy_only"])
        self.assertFalse(settings["delete_after_conversion"])
        self.assertFalse(settings["use_backup"])
        self.assertEqual(settings["text_overlay"], "None")
        self.assertEqual(settings["custom_console_command"], "-crf 20 -preset veryfast -movflags +faststart")
        # The caller's dict is not mutated.
        self.assertEqual(base["video_codec"], "libx265")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_support.py`
Expected: `ImportError: cannot import name 'probe_media_info'`.

- [ ] **Step 3: Implement**

Add to `ui/media_player_support.py` (imports at top: `import json`, `import subprocess`, `from utils.resources import resource_path`, `from utils.subprocess_helpers import FFPROBE_TIMEOUT, get_subprocess_startupinfo`, `from utils.logger import logger`):

```python
PLAYER_CONVERT_CUSTOM_ARGS = "-crf 20 -preset veryfast -movflags +faststart"


def _empty_probe():
    return {"ok": False, "fps": 0.0, "nb_frames": 0, "duration_ms": 0,
            "container": "", "vcodec": "", "acodec": ""}


def probe_media_info(path, runner=subprocess.run):
    """Ask ffprobe for the frame rate, frame count, duration and codecs of `path`.

    `runner` is injectable so tests never spawn a process. Any failure returns a dict
    with ok=False and zero/empty fields; callers treat that as "unknown".
    """
    command = [
        resource_path("ffprobe.exe"), "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,r_frame_rate,avg_frame_rate,nb_frames:format=format_name,duration",
        "-of", "json", path,
    ]
    startupinfo, creationflags = get_subprocess_startupinfo()
    try:
        result = runner(command, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT,
                        startupinfo=startupinfo, creationflags=creationflags)
        if result.returncode != 0:
            return _empty_probe()
        payload = json.loads(result.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        logger.debug("probe_media_info failed for %s", path, exc_info=True)
        return _empty_probe()
    info = _empty_probe()
    info["ok"] = True
    video = next((s for s in payload.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in payload.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video:
        info["vcodec"] = str(video.get("codec_name") or "")
        info["fps"] = parse_frame_rate(video.get("r_frame_rate")) or parse_frame_rate(video.get("avg_frame_rate"))
        try:
            info["nb_frames"] = max(0, int(video.get("nb_frames") or 0))
        except (TypeError, ValueError):
            info["nb_frames"] = 0
    if audio:
        info["acodec"] = str(audio.get("codec_name") or "")
    fmt = payload.get("format", {}) or {}
    info["container"] = str(fmt.get("format_name") or "").split(",")[0].strip()
    try:
        info["duration_ms"] = max(0, int(round(float(fmt.get("duration") or 0) * 1000)))
    except (TypeError, ValueError):
        info["duration_ms"] = 0
    return info


def unsupported_message(info):
    """Tile text shown when the Windows backend cannot decode a file."""
    if not info or not info.get("ok"):
        return "Windows cannot play this file."
    vcodec = info.get("vcodec") or "unknown"
    container = info.get("container") or "unknown"
    acodec = info.get("acodec") or ""
    codecs = f"{vcodec}/{acodec}" if acodec else vcodec
    return f"Windows cannot play {codecs} in {container}."


def player_convert_settings(base_settings):
    """Converter settings for "Convert to MP4 (H.264) and play": fixed, predictable preset."""
    settings = dict(base_settings or {})
    settings.update({
        "output_format": "mp4",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "160k",
        "video_bitrate": "Auto",
        "video_size": "Auto",
        "framerate": "Auto",
        "keyframe_interval": 0,
        "volume_percentage": 100,
        "copy_only": False,
        "use_gpu": False,
        "text_overlay": "None",
        "delete_after_conversion": False,
        "use_backup": False,
        "custom_console_command": PLAYER_CONVERT_CUSTOM_ARGS,
    })
    return settings
```

Note for the implementer: `unsupported_message` returns English text; the widget wraps it in `_tr()` **per template** (Task 9) — keep this function Qt-free.

- [ ] **Step 4: Run tests and lint**

Run: `python -m pytest tests/test_media_player_support.py` and `python -m ruff check ui/media_player_support.py tests/test_media_player_support.py`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add ui/media_player_support.py tests/test_media_player_support.py
git commit -m "feat: ffprobe media info, unsupported message and convert preset"
```

---

### Task 4: Playlist Model

**Files:**
- Modify: `ui/media_player_support.py`
- Test: `tests/test_media_player_support.py`

**Interfaces:**
- Produces `class PlaylistModel`:
  - `items: list[str]` (paths, in order, no duplicates).
  - `add(paths) -> int` — appends new paths (skips duplicates and empty strings), returns count added.
  - `remove(index) -> None` (ignores bad index); `clear()`.
  - `move(source_index, destination_index) -> None` — reorder (destination is the index the item ends up at).
  - `next_index(current_index) -> int | None` — wraps to 0 at the end; `None` for empty list.
  - `previous_index(current_index) -> int | None` — wraps to last; `None` for empty.
  - `index_of(path) -> int` (`-1` when absent).
  - `VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg", ".flv")` and `collect_video_files(folder, walker=os.walk) -> list[str]` — sorted recursive listing filtered by extension (case-insensitive).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_player_support.py` (extend the import with `PlaylistModel, collect_video_files`):

```python
class PlaylistModelTests(unittest.TestCase):
    def test_add_skips_duplicates_and_blanks(self):
        model = PlaylistModel()
        self.assertEqual(model.add(["a.mp4", "b.mp4", "a.mp4", ""]), 2)
        self.assertEqual(model.items, ["a.mp4", "b.mp4"])

    def test_remove_clear_and_move(self):
        model = PlaylistModel()
        model.add(["a", "b", "c"])
        model.move(0, 2)
        self.assertEqual(model.items, ["b", "c", "a"])
        model.remove(1)
        self.assertEqual(model.items, ["b", "a"])
        model.remove(99)
        self.assertEqual(model.items, ["b", "a"])
        model.clear()
        self.assertEqual(model.items, [])

    def test_next_and_previous_wrap(self):
        model = PlaylistModel()
        self.assertIsNone(model.next_index(0))
        self.assertIsNone(model.previous_index(0))
        model.add(["a", "b", "c"])
        self.assertEqual(model.next_index(0), 1)
        self.assertEqual(model.next_index(2), 0)
        self.assertEqual(model.previous_index(0), 2)
        self.assertEqual(model.previous_index(-1), 0)
        self.assertEqual(model.index_of("c"), 2)
        self.assertEqual(model.index_of("zzz"), -1)

    def test_collect_video_files_filters_and_sorts(self):
        tree = [
            ("root", ["sub"], ["B.MP4", "notes.txt", "a.mkv"]),
            ("root\\sub", [], ["c.webm", "image.png"]),
        ]
        files = collect_video_files("root", walker=lambda folder: iter(tree))
        self.assertEqual(files, ["root\\B.MP4", "root\\a.mkv", "root\\sub\\c.webm"])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_support.py -k "Playlist or collect"`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `ui/media_player_support.py` (add `import os` at top):

```python
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg", ".flv")


def collect_video_files(folder, walker=os.walk):
    """Recursively list video files under `folder`, sorted for a stable playlist order."""
    found = []
    for root, _dirs, files in walker(folder):
        for name in files:
            if name.lower().endswith(VIDEO_EXTENSIONS):
                found.append(os.path.join(root, name))
    return sorted(found)


class PlaylistModel:
    """Ordered, duplicate-free list of file paths with wrap-around navigation."""

    def __init__(self):
        self.items = []

    def add(self, paths):
        added = 0
        for path in paths or []:
            path = str(path or "").strip()
            if path and path not in self.items:
                self.items.append(path)
                added += 1
        return added

    def remove(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]

    def clear(self):
        self.items = []

    def move(self, source_index, destination_index):
        if not (0 <= source_index < len(self.items)):
            return
        item = self.items.pop(source_index)
        destination_index = max(0, min(destination_index, len(self.items)))
        self.items.insert(destination_index, item)

    def next_index(self, current_index):
        if not self.items:
            return None
        return (current_index + 1) % len(self.items)

    def previous_index(self, current_index):
        if not self.items:
            return None
        if current_index < 0:
            return 0
        return (current_index - 1) % len(self.items)

    def index_of(self, path):
        try:
            return self.items.index(path)
        except ValueError:
            return -1
```

- [ ] **Step 4: Run tests and lint**

Run: `python -m pytest tests/test_media_player_support.py` and `python -m ruff check ui/media_player_support.py tests/test_media_player_support.py`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add ui/media_player_support.py tests/test_media_player_support.py
git commit -m "feat: media player playlist model"
```

---

### Task 5: Volume, Mute and Persistence in the Widget

**Files:**
- Modify: `ui/media_player_widget.py`
- Test: `tests/test_media_player_widget.py`

**Interfaces:**
- Consumes: `MEDIA_PLAYER_DEFAULTS` from `ui/media_player_support.py`; `normalize_media_player_settings` from `utils/config.py`.
- Produces on `MediaPlayerWidget`:
  - Constructor `MediaPlayerWidget(parent=None, button_style=None, settings=None, save_settings=None, threadpool=None)`. `settings` is the app's settings dict (the widget reads/writes `settings["media_player"]`); `save_settings` is a zero-arg callable invoked after every change; `threadpool` is a `QThreadPool` (used in Task 9).
  - `self.volume_slider: QSlider` (0–100), `self.mute_btn: QPushButton` (checkable), `set_volume(int)`, `set_muted(bool)`, `volume() -> int`, `is_muted() -> bool`, `adjust_volume(delta)`.
  - `self.settings_group -> dict` (the live `media_player` dict), `last_folder() -> str`, `set_last_folder(path)`.
  - `_schedule(msec, callback)` — delayed call using a `QTimer(self)` (single-shot) that is dropped when the widget dies.
  - `PlayerPanel` applies the host's volume/mute when its player is created lazily (`panel.apply_audio(volume, muted)` and `panel.on_player_created` callback).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_player_widget.py` inside `MediaPlayerWidgetTests` (add `from PyQt5.QtMultimedia import QMediaPlayer` and `import os, tempfile` at the top as needed):

```python
    def _widget(self, settings=None, saves=None):
        widget = MediaPlayerWidget(
            settings=settings if settings is not None else {},
            save_settings=(lambda: saves.append(1)) if saves is not None else None,
        )
        self.addCleanup(widget.shutdown)
        return widget

    def test_volume_and_mute_reach_every_created_player(self):
        widget = self._widget()
        first = widget.panels[0]._ensure_player()
        second = widget.panels[1]._ensure_player()
        widget.set_volume(40)
        widget.set_muted(True)
        for player in (first, second):
            self.assertEqual(player.volume(), 40)
            self.assertTrue(player.isMuted())
        # A panel whose player is created later inherits the current audio state.
        third = widget.panels[2]._ensure_player()
        self.assertEqual(third.volume(), 40)
        self.assertTrue(third.isMuted())

    def test_volume_controls_persist_to_settings_group(self):
        saves = []
        settings = {}
        widget = self._widget(settings=settings, saves=saves)
        widget.volume_slider.setValue(55)
        widget.mute_btn.setChecked(True)
        widget.panels_combo.setCurrentIndex(0)  # 1 panel
        self.assertEqual(settings["media_player"]["volume"], 55)
        self.assertTrue(settings["media_player"]["muted"])
        self.assertEqual(settings["media_player"]["panel_count"], 1)
        self.assertGreaterEqual(len(saves), 3)

    def test_widget_restores_settings_group_on_creation(self):
        settings = {"media_player": {"volume": 20, "muted": True, "panel_count": 4, "last_folder": "C:\\Videos"}}
        saves = []
        widget = self._widget(settings=settings, saves=saves)
        self.assertEqual(widget.volume(), 20)
        self.assertTrue(widget.is_muted())
        self.assertEqual(widget.visible_panel_count(), 4)
        self.assertEqual(widget.last_folder(), "C:\\Videos")
        # Restoring saved values must not write the settings file back.
        self.assertEqual(saves, [])

    def test_adjust_volume_clamps_and_unmutes_on_increase(self):
        widget = self._widget()
        widget.set_volume(98)
        widget.adjust_volume(+5)
        self.assertEqual(widget.volume(), 100)
        widget.adjust_volume(-200)
        self.assertEqual(widget.volume(), 0)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_widget.py -k "volume or restores"`
Expected: `TypeError: __init__() got an unexpected keyword argument 'settings'`.

- [ ] **Step 3: Implement**

In `ui/media_player_widget.py`:

1. Imports: add `from ui.media_player_support import MEDIA_PLAYER_DEFAULTS` and `from utils.config import normalize_media_player_settings`.

2. `PlayerPanel.__init__`: add `self.on_player_created = None` next to the other callbacks. In `_ensure_player`, after `self.player.setNotifyInterval(50)`:

```python
        if callable(self.on_player_created):
            self.on_player_created(self)
```

Add to `PlayerPanel`:

```python
    def apply_audio(self, volume, muted):
        if self.player is not None:
            self.player.setVolume(int(volume))
            self.player.setMuted(bool(muted))
```

3. `MediaPlayerWidget.__init__` becomes:

```python
    def __init__(self, parent=None, button_style=None, settings=None, save_settings=None, threadpool=None):
        super().__init__(parent)
        self.button_style = button_style
        self.settings = settings if settings is not None else {}
        self._save_settings = save_settings if callable(save_settings) else (lambda: None)
        self.threadpool = threadpool
        self.settings["media_player"] = normalize_media_player_settings(self.settings.get("media_player"))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.panels = []
        self._is_playing = False
        self._suppress_seek = False
        self._timers = []
        self._restoring = False
        self._build_ui()

        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(60)
        self.sync_timer.timeout.connect(self._on_tick)
        self.sync_timer.start()

        # Restoring saved values fires the same change slots as user input; do not
        # write the settings file back while doing so.
        self._restoring = True
        try:
            group = self.settings_group
            self.volume_slider.setValue(group["volume"])
            self.mute_btn.setChecked(group["muted"])
            self.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(group["panel_count"]))
            self.set_visible_panel_count(group["panel_count"])
            self._apply_audio_to_panels()
        finally:
            self._restoring = False
```

4. In `_build_ui`, after creating each panel: `panel.on_player_created = self._on_player_created`.

5. In `_build_transport_bar`, after the speed combo block add:

```python
        volume_label = QLabel(_tr("Volume"))
        volume_label.setStyleSheet(theme.video_label_style())
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(MEDIA_PLAYER_DEFAULTS["volume"])
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.setToolTip(_tr("Volume for every panel"))
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self.mute_btn = QPushButton(_tr("Mute"))
        self.mute_btn.setCheckable(True)
        self.mute_btn.setCursor(Qt.PointingHandCursor)
        self.mute_btn.toggled.connect(self._on_mute_toggled)
```

and insert them into `button_row` after the speed combo:

```python
        button_row.addWidget(volume_label)
        button_row.addWidget(self.volume_slider)
        button_row.addWidget(self.mute_btn)
```

Include `self.mute_btn` in the `button_style` loop.

6. Add these methods to `MediaPlayerWidget` (a new `# --- audio & persistence ---` section):

```python
    @property
    def settings_group(self):
        return self.settings["media_player"]

    def _persist(self, **changes):
        self.settings_group.update(changes)
        if not self._restoring:
            self._save_settings()

    def last_folder(self):
        return self.settings_group.get("last_folder", "")

    def set_last_folder(self, path):
        folder = path if os.path.isdir(path or "") else os.path.dirname(path or "")
        if folder and folder != self.last_folder():
            self._persist(last_folder=folder)

    def _schedule(self, msec, callback):
        """Run `callback` after `msec` while this widget lives (no QTimer.singleShot)."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        self._timers.append(timer)

        def fire():
            if timer in self._timers:
                self._timers.remove(timer)
            callback()

        timer.timeout.connect(fire)
        timer.start(max(0, int(msec)))
        return timer

    def volume(self):
        return self.volume_slider.value()

    def is_muted(self):
        return self.mute_btn.isChecked()

    def set_volume(self, value):
        self.volume_slider.setValue(max(0, min(100, int(value))))

    def set_muted(self, muted):
        self.mute_btn.setChecked(bool(muted))

    def adjust_volume(self, delta):
        self.set_volume(self.volume() + int(delta))

    def _apply_audio_to_panels(self):
        for panel in self.panels:
            panel.apply_audio(self.volume(), self.is_muted())

    def _on_volume_slider_changed(self, value):
        self._apply_audio_to_panels()
        self._persist(volume=int(value))

    def _on_mute_toggled(self, checked):
        self.mute_btn.setText(_tr("Unmute") if checked else _tr("Mute"))
        self._apply_audio_to_panels()
        self._persist(muted=bool(checked))

    def _on_player_created(self, panel):
        panel.apply_audio(self.volume(), self.is_muted())
```

7. `_on_panel_count_changed` becomes:

```python
    def _on_panel_count_changed(self, _index):
        count = self.panels_combo.currentData()
        self.set_visible_panel_count(count)
        self._persist(panel_count=int(count))
```

8. `PlayerPanel.browse_for_media` must use and update the host's last folder. Add `self.host = parent` in `PlayerPanel.__init__` (the widget passes itself as parent) and:

```python
    def browse_for_media(self):
        start_dir = self.host.last_folder() if self.host is not None and hasattr(self.host, "last_folder") else ""
        path, _ = QFileDialog.getOpenFileName(self, _tr("Open video"), start_dir, VIDEO_NAME_FILTER)
        if path:
            if self.host is not None and hasattr(self.host, "set_last_folder"):
                self.host.set_last_folder(path)
            self.load_media(path)
```

9. `shutdown()`: also stop every timer in `self._timers`.

- [ ] **Step 4: Run tests and lint**

Run: `python -m pytest tests/test_media_player_widget.py` and `python -m ruff check ui/media_player_widget.py tests/test_media_player_widget.py`
Expected: exit 0 (existing `test_default_shows_two_panels` still passes because the default group has `panel_count: 2`).

- [ ] **Step 5: Commit**

```bash
git add ui/media_player_widget.py tests/test_media_player_widget.py
git commit -m "feat: media player volume, mute and persisted settings"
```

---

### Task 6: Frame Step and Readout

**Files:**
- Modify: `ui/media_player_widget.py`
- Test: `tests/test_media_player_widget.py`

**Interfaces:**
- Consumes: `probe_media_info`, `frame_step_ms`, `format_readout`, `DEFAULT_FPS` from `ui/media_player_support.py`.
- Produces:
  - `PlayerPanel.probe_info: dict` (empty until the probe returns), `PlayerPanel.fps() -> float` (0.0 when unknown), `PlayerPanel.nb_frames() -> int`, `PlayerPanel.set_probe_info(info)`, `PlayerPanel.on_probe_finished` callback `(panel, info)`.
  - `MediaPlayerWidget.probe_runner` — callable `(path) -> dict`, defaults to `probe_media_info`; tests replace it. Probing runs on a daemon `threading.Thread` and posts the result through `MediaPlayerWidget.probe_finished = pyqtSignal(int, dict)` (panel index, info) — the same daemon-thread-plus-signal pattern the recorder uses.
  - `MediaPlayerWidget.step_frames(delta)` — pauses all, seeks by `delta * frame_step_ms(reference.fps())` on the shared timeline, clamped to `[0, timeline_duration_ms()]`.
  - `MediaPlayerWidget.seek_relative_ms(delta_ms)` — same clamp, no pause.
  - `_update_time_label(master_ms)` renders `format_readout(master_ms, timeline_duration_ms(), reference.fps(), reference.nb_frames())`.

- [ ] **Step 1: Write the failing tests**

Append to `MediaPlayerWidgetTests`:

```python
    def _loaded_widget_with_fake_player(self, duration_ms=10_000, fps=25.0, nb_frames=250):
        """A widget whose first panel reports media without touching the Windows backend."""
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": True, "fps": fps, "nb_frames": nb_frames,
                                            "duration_ms": duration_ms, "container": "mp4",
                                            "vcodec": "h264", "acodec": "aac"}
        panel = widget.panels[0]

        class FakePlayer:
            def __init__(self):
                self._position = 0
                self.paused = False
                self.playing = False

            def duration(self):
                return duration_ms

            def position(self):
                return self._position

            def setPosition(self, value):
                self._position = int(value)

            def pause(self):
                self.paused = True

            def play(self):
                self.playing = True

            def stop(self):
                pass

            def setPlaybackRate(self, _rate):
                pass

            def setVolume(self, _v):
                pass

            def setMuted(self, _m):
                pass

        panel.player = FakePlayer()
        panel._media_path = "C:\\Videos\\clip.mp4"
        panel.set_probe_info(widget.probe_runner(panel._media_path))
        widget._on_any_duration_changed(duration_ms)
        return widget, panel

    def test_step_frames_pauses_and_moves_by_one_frame(self):
        widget, panel = self._loaded_widget_with_fake_player(fps=25.0)
        widget.seek_all(1_000)
        widget.step_frames(1)
        self.assertTrue(panel.player.paused)
        self.assertEqual(panel.player.position(), 1_040)
        widget.step_frames(-2)
        self.assertEqual(panel.player.position(), 960)

    def test_step_frames_clamps_to_timeline(self):
        widget, panel = self._loaded_widget_with_fake_player(duration_ms=100, fps=25.0)
        widget.seek_all(90)
        widget.step_frames(1)
        self.assertEqual(panel.player.position(), 100)
        widget.seek_all(10)
        widget.step_frames(-1)
        self.assertEqual(panel.player.position(), 0)

    def test_step_uses_default_fps_before_probe_arrives(self):
        widget, panel = self._loaded_widget_with_fake_player(fps=0.0, nb_frames=0)
        widget.seek_all(0)
        widget.step_frames(1)
        self.assertEqual(panel.player.position(), 40)
        self.assertNotIn("frame", widget.time_label.text())

    def test_readout_shows_millis_and_frame_numbers(self):
        widget, _panel = self._loaded_widget_with_fake_player(duration_ms=2_000, fps=25.0, nb_frames=50)
        widget.seek_all(1_000)
        self.assertEqual(widget.time_label.text(), "0:00:01.000 / 0:00:02.000 · frame 25 / 50")

    def test_load_media_probes_in_background_and_updates_panel(self):
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": True, "fps": 29.97, "nb_frames": 10, "duration_ms": 333,
                                            "container": "mov", "vcodec": "h264", "acodec": "aac"}
        panel = widget.panels[0]
        panel._ensure_player = lambda: panel.player or type("P", (), {
            "setMedia": lambda self, *_: None, "setVolume": lambda self, *_: None,
            "setMuted": lambda self, *_: None, "duration": lambda self: 0})()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertTrue(panel.load_media(path))
        deadline = time.monotonic() + 5
        while not panel.probe_info and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertAlmostEqual(panel.fps(), 29.97, places=2)
        self.assertEqual(panel.nb_frames(), 10)
```

(Add `import time` at the top of the test file.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_widget.py -k "step or readout or probes"`
Expected: `AttributeError: 'MediaPlayerWidget' object has no attribute 'probe_runner'` / `set_probe_info`.

- [ ] **Step 3: Implement**

In `ui/media_player_widget.py`:

1. Imports: `import threading`; `from PyQt5.QtCore import pyqtSignal` (extend the existing import); from support import `frame_step_ms, format_readout, probe_media_info`.

2. `PlayerPanel.__init__`: add `self.probe_info = {}` and `self.on_probe_finished = None`. Add methods:

```python
    def fps(self):
        return float(self.probe_info.get("fps") or 0.0)

    def nb_frames(self):
        return int(self.probe_info.get("nb_frames") or 0)

    def set_probe_info(self, info):
        self.probe_info = dict(info or {})
        if callable(self.on_probe_finished):
            self.on_probe_finished(self, self.probe_info)
```

In `load_media`, before `return True`: `self.probe_info = {}` and then `if self.host is not None and hasattr(self.host, "start_probe"): self.host.start_probe(self)`. In `clear_media`: `self.probe_info = {}`.

3. `MediaPlayerWidget`: class attribute `probe_finished = pyqtSignal(int, dict)`. In `__init__`, before `_build_ui()`: `self.probe_runner = probe_media_info` and `self.probe_finished.connect(self._on_probe_finished)`. Add:

```python
    # --- probing -----------------------------------------------------------
    def start_probe(self, panel):
        path = panel._media_path
        index = panel.index

        def run():
            info = self.probe_runner(path)
            try:
                self.probe_finished.emit(index, info)
            except RuntimeError:
                logger.debug("Media player closed before probe finished", exc_info=True)

        threading.Thread(target=run, daemon=True).start()

    def _on_probe_finished(self, index, info):
        if not (0 <= index < len(self.panels)):
            return
        panel = self.panels[index]
        if not panel.has_media():
            return
        panel.set_probe_info(info)
        self._update_time_label(self.position_slider.value())
```

4. Frame stepping (in the transport section):

```python
    def _clamp_master(self, master_ms):
        return max(0, min(int(master_ms), self.timeline_duration_ms() or int(master_ms)))

    def seek_relative_ms(self, delta_ms):
        target = self._clamp_master(self.position_slider.value() + int(delta_ms))
        self._set_slider_value(target)
        self.seek_all(target)

    def step_frames(self, delta):
        reference = self._reference_panel()
        if reference is None:
            return
        # Stepping always pauses (spec §2): a paused, frame-exact position is the point.
        self.pause_all()
        self.seek_relative_ms(int(delta) * frame_step_ms(reference.fps()))
```

5. Replace `_update_time_label`:

```python
    def _update_time_label(self, master_ms):
        reference = self._reference_panel()
        fps = reference.fps() if reference is not None else 0.0
        nb_frames = reference.nb_frames() if reference is not None else 0
        self.time_label.setText(format_readout(master_ms, self.timeline_duration_ms(), fps, nb_frames))
```

Set `self.time_label.setMinimumWidth(260)` and initial text `_tr("0:00:00.000 / 0:00:00.000")`.

- [ ] **Step 4: Run tests and lint**

Run: `python -m pytest tests/test_media_player_widget.py` and `python -m ruff check ui/media_player_widget.py tests/test_media_player_widget.py`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add ui/media_player_widget.py tests/test_media_player_widget.py
git commit -m "feat: frame stepping and millisecond frame readout"
```

---

### Task 7: Shortcuts and Fullscreen

**Files:**
- Create: `ui/media_player_parts.py` (`FullscreenHost`)
- Create: `tests/test_media_player_parts.py`
- Modify: `ui/media_player_widget.py`
- Test: `tests/test_media_player_widget.py`

**Interfaces:**
- Produces in `ui/media_player_parts.py`:
  - `class FullscreenHost(QWidget)` — frameless, top-level (`Qt.Window | Qt.FramelessWindowHint`), black background, `mouse_moved = pyqtSignal()`, `exit_requested = pyqtSignal()`. `take(widget)` adds `widget` to its vertical layout; `release()` removes and returns all taken widgets in order. Mouse tracking on; `mouseMoveEvent` emits `mouse_moved`; `mouseDoubleClickEvent` and `keyPressEvent` for `Qt.Key_Escape`/`Qt.Key_F` emit `exit_requested`.
- Produces on `MediaPlayerWidget`:
  - `self.stage: QWidget` wraps the panel grid; `self.transport_widget: QWidget` wraps the transport bar (both are what fullscreen moves).
  - `self.fullscreen_btn`, `toggle_fullscreen()`, `enter_fullscreen()`, `exit_fullscreen()`, `is_fullscreen() -> bool`, `self._fullscreen_host: FullscreenHost | None`, `self._bar_hide_timer: QTimer` (3000 ms single-shot) hiding `transport_widget` while fullscreen; any `mouse_moved` shows it and restarts the timer.
  - `self.shortcuts: dict[str, QShortcut]` keyed by key text: `"Space", "Home", "Left", "Right", "Shift+Left", "Shift+Right", "Up", "Down", "M", "F", "Escape", "N", "P"` with context `Qt.WidgetWithChildrenShortcut`. Slots: `toggle_play_all`, `restart_all`, `step_frames(-1)`, `step_frames(1)`, `seek_relative_ms(-5000)`, `seek_relative_ms(5000)`, `adjust_volume(5)`, `adjust_volume(-5)`, `toggle_mute`, `toggle_fullscreen`, `exit_fullscreen`, `playlist_next`, `playlist_previous` (the last two are stubs here — `pass` bodies replaced in Task 8).
  - `toggle_mute()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_media_player_parts.py`:

```python
import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QLabel

from ui.media_player_parts import FullscreenHost


class FullscreenHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_take_and_release_round_trip_widgets_in_order(self):
        host = FullscreenHost()
        self.addCleanup(host.close)
        first, second = QLabel("a"), QLabel("b")
        host.take(first)
        host.take(second)
        self.assertIs(first.parent(), host)
        released = host.release()
        self.assertEqual(released, [first, second])
        self.assertIsNone(first.parent())

    def test_escape_and_f_request_exit(self):
        host = FullscreenHost()
        self.addCleanup(host.close)
        requests = []
        host.exit_requested.connect(lambda: requests.append(1))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_F, Qt.NoModifier))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.NoModifier))
        self.assertEqual(len(requests), 2)
```

Append to `MediaPlayerWidgetTests`:

```python
    def test_shortcut_table_maps_keys_to_slots(self):
        widget = self._widget()
        calls = []
        widget.toggle_play_all = lambda: calls.append("play")
        widget.step_frames = lambda delta: calls.append(("step", delta))
        widget.seek_relative_ms = lambda delta: calls.append(("seek", delta))
        widget.adjust_volume = lambda delta: calls.append(("vol", delta))
        widget.toggle_mute = lambda: calls.append("mute")
        widget.toggle_fullscreen = lambda: calls.append("fs")
        widget.playlist_next = lambda: calls.append("next")
        widget.playlist_previous = lambda: calls.append("prev")
        widget._rebind_shortcuts()
        for key in ("Space", "Left", "Right", "Shift+Left", "Shift+Right", "Up", "Down", "M", "F", "N", "P"):
            widget.shortcuts[key].activated.emit()
        self.assertEqual(calls, ["play", ("step", -1), ("step", 1), ("seek", -5000), ("seek", 5000),
                                 ("vol", 5), ("vol", -5), "mute", "fs", "next", "prev"])
        self.assertEqual(widget.shortcuts["Space"].context(), Qt.WidgetWithChildrenShortcut)

    def test_fullscreen_reparents_stage_and_restores(self):
        widget = self._widget()
        widget.show()
        stage_parent = widget.stage.parentWidget()
        widget.toggle_fullscreen()
        self.assertTrue(widget.is_fullscreen())
        self.assertIs(widget.stage.parentWidget(), widget._fullscreen_host)
        self.assertIs(widget.transport_widget.parentWidget(), widget._fullscreen_host)
        widget.toggle_fullscreen()
        self.assertFalse(widget.is_fullscreen())
        self.assertIs(widget.stage.parentWidget(), stage_parent)
        self.assertIsNone(widget._fullscreen_host)
        self.assertTrue(widget.transport_widget.isVisibleTo(widget))

    def test_fullscreen_bar_hides_after_timeout_and_returns_on_mouse(self):
        widget = self._widget()
        widget.show()
        widget.enter_fullscreen()
        widget._bar_hide_timer.timeout.emit()
        self.assertFalse(widget.transport_widget.isVisibleTo(widget._fullscreen_host))
        widget._fullscreen_host.mouse_moved.emit()
        self.assertTrue(widget.transport_widget.isVisibleTo(widget._fullscreen_host))
        self.assertTrue(widget._bar_hide_timer.isActive())
        widget.exit_fullscreen()
```

(Add `from PyQt5.QtCore import Qt` to the test imports.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_parts.py tests/test_media_player_widget.py -k "Fullscreen or shortcut or fullscreen"`
Expected: `ModuleNotFoundError: ui.media_player_parts`.

- [ ] **Step 3: Implement `FullscreenHost`**

Create `ui/media_player_parts.py`:

```python
"""Small Qt building blocks for the Media Player tab."""
from PyQt5.QtCore import QCoreApplication, Qt, pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget


def _tr(source: str) -> str:
    """Translate under the stable "MediaPlayer" context (plain literals only)."""
    return QCoreApplication.translate("MediaPlayer", source)


class FullscreenHost(QWidget):
    """A frameless top-level window that temporarily hosts the player's stage and bar."""

    mouse_moved = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background: black;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._taken = []

    def take(self, widget):
        self._taken.append(widget)
        stretch = 1 if not self._taken[:-1] else 0
        self._layout.addWidget(widget, stretch)
        widget.setMouseTracking(True)

    def release(self):
        released = list(self._taken)
        for widget in released:
            self._layout.removeWidget(widget)
            widget.setParent(None)
        self._taken = []
        return released

    def mouseMoveEvent(self, event):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.exit_requested.emit()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_F):
            self.exit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
```

- [ ] **Step 4: Implement shortcuts and fullscreen in the widget**

In `ui/media_player_widget.py`:

1. Imports: `from PyQt5.QtGui import QKeySequence`; `from PyQt5.QtWidgets import QShortcut` (add to the existing list); `from ui.media_player_parts import FullscreenHost`.

2. In `_build_ui`, replace `layout.addLayout(self.grid, 1)` with a stage container, and wrap the transport bar:

```python
        self.stage = QWidget(self)
        stage_layout = QHBoxLayout(self.stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(8)
        stage_layout.addLayout(self.grid, 1)
        self._stage_layout = stage_layout
        layout.addWidget(self.stage, 1)

        self.transport_widget = QWidget(self)
        self.transport_widget.setLayout(self._build_transport_bar())
        layout.addWidget(self.transport_widget)
        self._main_layout = layout
        self._fullscreen_host = None
        self._bar_hide_timer = QTimer(self)
        self._bar_hide_timer.setSingleShot(True)
        self._bar_hide_timer.setInterval(3000)
        self._bar_hide_timer.timeout.connect(self._hide_transport_bar)
        self.shortcuts = {}
        self._rebind_shortcuts()
```

(`_build_transport_bar` must still return the `QVBoxLayout`; `QWidget.setLayout` accepts it.)

3. In `_build_transport_bar`, add a fullscreen button after the restart button and include it in the style loop:

```python
        self.fullscreen_btn = QPushButton(_tr("Fullscreen"))
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.setToolTip(_tr("Show the panels fullscreen (F). Esc returns."))
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        button_row.addWidget(self.fullscreen_btn)
```

4. Methods:

```python
    # --- shortcuts -----------------------------------------------------------
    def _shortcut_table(self):
        return {
            "Space": self.toggle_play_all,
            "Home": self.restart_all,
            "Left": lambda: self.step_frames(-1),
            "Right": lambda: self.step_frames(1),
            "Shift+Left": lambda: self.seek_relative_ms(-5000),
            "Shift+Right": lambda: self.seek_relative_ms(5000),
            "Up": lambda: self.adjust_volume(5),
            "Down": lambda: self.adjust_volume(-5),
            "M": self.toggle_mute,
            "F": self.toggle_fullscreen,
            "Escape": self.exit_fullscreen,
            "N": self.playlist_next,
            "P": self.playlist_previous,
        }

    def _rebind_shortcuts(self):
        for shortcut in self.shortcuts.values():
            shortcut.setParent(None)
            shortcut.deleteLater()
        self.shortcuts = {}
        for key, slot in self._shortcut_table().items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)
            self.shortcuts[key] = shortcut

    def toggle_mute(self):
        self.set_muted(not self.is_muted())

    def playlist_next(self):
        pass  # Task 8

    def playlist_previous(self):
        pass  # Task 8

    # --- fullscreen ----------------------------------------------------------
    def is_fullscreen(self):
        return self._fullscreen_host is not None

    def toggle_fullscreen(self):
        if self.is_fullscreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.is_fullscreen():
            return
        host = FullscreenHost()
        host.exit_requested.connect(self.exit_fullscreen)
        host.mouse_moved.connect(self._show_transport_bar)
        self._stage_index = self._main_layout.indexOf(self.stage)
        self._main_layout.removeWidget(self.stage)
        self._main_layout.removeWidget(self.transport_widget)
        host.take(self.stage)
        host.take(self.transport_widget)
        self._fullscreen_host = host
        self.fullscreen_btn.setText(_tr("Exit fullscreen"))
        host.showFullScreen()
        host.setFocus()
        self._show_transport_bar()

    def exit_fullscreen(self):
        host = self._fullscreen_host
        if host is None:
            return
        self._bar_hide_timer.stop()
        host.release()
        self._fullscreen_host = None
        self._main_layout.insertWidget(self._stage_index, self.stage, 1)
        self._main_layout.insertWidget(self._stage_index + 1, self.transport_widget)
        self.stage.show()
        self.transport_widget.show()
        self.fullscreen_btn.setText(_tr("Fullscreen"))
        host.close()
        host.deleteLater()
        self._rebind_shortcuts()

    def _show_transport_bar(self):
        self.transport_widget.show()
        if self.is_fullscreen():
            self._bar_hide_timer.start()

    def _hide_transport_bar(self):
        if self.is_fullscreen():
            self.transport_widget.hide()
```

Because the stage moves to another top-level window, shortcuts with `WidgetWithChildrenShortcut` on `self` would not fire there; that is why `FullscreenHost.keyPressEvent` handles `Esc`/`F` itself. Also make `MediaPlayerWidget.shutdown()` call `self.exit_fullscreen()` first and stop `_bar_hide_timer`.

5. Double-clicking a video surface toggles fullscreen (spec §1). Add to `PlayerPanel`:

```python
    def mouseDoubleClickEvent(self, event):
        if self.host is not None and hasattr(self.host, "toggle_fullscreen"):
            self.host.toggle_fullscreen()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
```

and a test in `MediaPlayerWidgetTests`:

```python
    def test_double_clicking_a_panel_toggles_fullscreen(self):
        widget = self._widget()
        toggles = []
        widget.toggle_fullscreen = lambda: toggles.append(1)
        widget.panels[0].mouseDoubleClickEvent(QMouseEvent(
            QEvent.MouseButtonDblClick, QPointF(5, 5), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        self.assertEqual(toggles, [1])
```

(imports: `from PyQt5.QtCore import QEvent, QPointF`, `from PyQt5.QtGui import QMouseEvent`).

- [ ] **Step 5: Run tests and lint**

Run: `python -m pytest tests/test_media_player_parts.py tests/test_media_player_widget.py` and `python -m ruff check ui/media_player_parts.py ui/media_player_widget.py tests/test_media_player_parts.py tests/test_media_player_widget.py`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add ui/media_player_parts.py ui/media_player_widget.py tests/test_media_player_parts.py tests/test_media_player_widget.py
git commit -m "feat: media player keyboard shortcuts and fullscreen"
```

---

### Task 8: Selected Panel and Playlist

**Files:**
- Modify: `ui/media_player_parts.py` (`PlaylistDock`)
- Modify: `ui/media_player_widget.py`
- Test: `tests/test_media_player_parts.py`, `tests/test_media_player_widget.py`

**Interfaces:**
- Consumes: `PlaylistModel`, `collect_video_files`, `VIDEO_NAME_FILTER`.
- Produces in `ui/media_player_parts.py`:
  - `class PlaylistDock(QWidget)` with `model: PlaylistModel | None`, `list: QListWidget` (`InternalMove` drag, `ExtendedSelection`), buttons `add_files_btn`, `add_folder_btn`, `remove_btn`, `clear_btn`, `title_label`. Signals: `activate_requested = pyqtSignal(str)` (double-click), `files_requested = pyqtSignal()`, `folder_requested = pyqtSignal()`. Methods: `set_model(model, title)`, `refresh()`, `add_paths(paths)`, `remove_selected()`, `clear()`, `select_path(path)`; accepts Explorer URL drops (`dragEnterEvent`/`dropEvent` → `add_paths`); internal drag reorder syncs the model via `_on_rows_moved`.
- Produces on `MediaPlayerWidget`:
  - `PlayerPanel.playlist: PlaylistModel`, `PlayerPanel.selected: bool`, `PlayerPanel.set_selected(bool)` (accent border), `PlayerPanel.on_selected` callback, `mousePressEvent` → `on_selected(panel)`.
  - `selected_panel() -> PlayerPanel | None` (only visible panels), `select_panel(index)`, `self.selected_index: int` (default 0).
  - `self.playlist_dock: PlaylistDock` in `stage` to the right of the grid; `self.playlist_btn` (checkable) toggles it; `toggle_playlist()`; shown by default only when `panel_count == 1`.
  - `playlist_next()`, `playlist_previous()` — load the wrapped neighbour of the selected panel's current file into the selected panel, keep playing if it was playing.
  - Auto-advance: `_on_media_status_changed(status)` receives `(status, panel)` now — `PlayerPanel` connects `mediaStatusChanged` to a lambda that passes itself. On `EndOfMedia`: if `visible_panel_count() == 1` and the selected panel has a playlist with > 1 items → `playlist_next()` and continue playing; else the existing pause behaviour.
  - `add_playlist_files()` / `add_playlist_folder()` use `QFileDialog` with `last_folder()` and update it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_player_parts.py` (extend imports: `from ui.media_player_parts import FullscreenHost, PlaylistDock` and `from ui.media_player_support import PlaylistModel`):

```python
class PlaylistDockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dock(self):
        dock = PlaylistDock()
        self.addCleanup(dock.close)
        model = PlaylistModel()
        dock.set_model(model, "Panel 1")
        return dock, model

    def test_refresh_lists_model_items_and_title(self):
        dock, model = self._dock()
        model.add(["C:\\Videos\\a.mp4", "C:\\Videos\\b.mp4"])
        dock.refresh()
        self.assertEqual(dock.list.count(), 2)
        self.assertEqual(dock.list.item(0).text(), "a.mp4")
        self.assertEqual(dock.list.item(0).toolTip(), "C:\\Videos\\a.mp4")
        self.assertIn("Panel 1", dock.title_label.text())

    def test_remove_selected_and_clear_update_model(self):
        dock, model = self._dock()
        dock.add_paths(["a", "b", "c"])
        dock.list.setCurrentRow(1)
        dock.remove_selected()
        self.assertEqual(model.items, ["a", "c"])
        dock.clear()
        self.assertEqual(model.items, [])
        self.assertEqual(dock.list.count(), 0)

    def test_double_click_emits_activate_with_path(self):
        dock, _model = self._dock()
        dock.add_paths(["C:\\Videos\\a.mp4"])
        activated = []
        dock.activate_requested.connect(activated.append)
        dock.list.itemDoubleClicked.emit(dock.list.item(0))
        self.assertEqual(activated, ["C:\\Videos\\a.mp4"])

    def test_rows_moved_reorders_model(self):
        dock, model = self._dock()
        dock.add_paths(["a", "b", "c"])
        dock._on_rows_moved(None, 0, 0, None, 3)  # Qt's rowsMoved for "a" dropped after "c"
        self.assertEqual(model.items, ["b", "c", "a"])
```

Append to `MediaPlayerWidgetTests`:

```python
    def test_clicking_a_panel_selects_it_and_shows_its_playlist(self):
        widget = self._widget()
        widget.panels[1].on_selected(widget.panels[1])
        self.assertIs(widget.selected_panel(), widget.panels[1])
        self.assertTrue(widget.panels[1].selected)
        self.assertFalse(widget.panels[0].selected)
        self.assertIs(widget.playlist_dock.model, widget.panels[1].playlist)

    def test_playlist_visible_by_default_only_for_one_panel(self):
        widget = self._widget()
        widget.show()
        self.assertFalse(widget.playlist_dock.isVisibleTo(widget))
        widget.panels_combo.setCurrentIndex(0)
        self.assertTrue(widget.playlist_dock.isVisibleTo(widget))
        widget.playlist_btn.setChecked(False)
        self.assertFalse(widget.playlist_dock.isVisibleTo(widget))

    def test_playlist_next_and_previous_load_into_selected_panel(self):
        widget = self._widget()
        panel = widget.panels[0]
        loaded = []
        panel.load_media = lambda path: loaded.append(path) or True
        panel.playlist.add(["a.mp4", "b.mp4", "c.mp4"])
        panel._media_path = "a.mp4"
        widget.playlist_next()
        panel._media_path = loaded[-1]
        widget.playlist_next()
        panel._media_path = loaded[-1]
        widget.playlist_next()
        widget.playlist_previous()
        self.assertEqual(loaded, ["b.mp4", "c.mp4", "a.mp4", "c.mp4"])

    def test_auto_advance_only_with_one_visible_panel(self):
        widget = self._widget()
        panel = widget.panels[0]
        loaded = []
        panel.load_media = lambda path: loaded.append(path) or True
        panel.playlist.add(["a.mp4", "b.mp4"])
        panel._media_path = "a.mp4"
        widget._is_playing = True
        widget.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(2))
        widget._on_media_status_changed(QMediaPlayer.EndOfMedia, panel)
        self.assertEqual(loaded, [])
        self.assertFalse(widget._is_playing)
        widget._is_playing = True
        widget.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(1))
        widget.play_all = lambda: loaded.append("play")
        widget._on_media_status_changed(QMediaPlayer.EndOfMedia, panel)
        self.assertEqual(loaded, ["b.mp4", "play"])
```

(Import `PANEL_COUNT_OPTIONS` from the widget module in the test file.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_parts.py tests/test_media_player_widget.py -k "Playlist or playlist or selects or advance"`
Expected: `ImportError: cannot import name 'PlaylistDock'`.

- [ ] **Step 3: Implement `PlaylistDock`**

Append to `ui/media_player_parts.py` (extend imports: `import os`; `from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton`; `from ui import theme`):

```python
class PlaylistDock(QWidget):
    """Playlist for one panel: a reorderable list plus Add/Remove/Clear controls."""

    activate_requested = pyqtSignal(str)
    files_requested = pyqtSignal()
    folder_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.setAcceptDrops(True)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.title_label = QLabel(_tr("Playlist"))
        self.title_label.setStyleSheet(theme.group_title_style())
        layout.addWidget(self.title_label)
        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self.add_files_btn = QPushButton(_tr("Add files..."))
        self.add_folder_btn = QPushButton(_tr("Add folder..."))
        self.remove_btn = QPushButton(_tr("Remove"))
        self.clear_btn = QPushButton(_tr("Clear"))
        for button in (self.add_files_btn, self.add_folder_btn, self.remove_btn, self.clear_btn):
            button.setCursor(Qt.PointingHandCursor)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.add_files_btn.clicked.connect(self.files_requested.emit)
        self.add_folder_btn.clicked.connect(self.folder_requested.emit)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear)

    def set_model(self, model, title):
        self.model = model
        self.title_label.setText(_tr("Playlist - %(panel)s") % {"panel": title})
        self.refresh()

    def refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for path in (self.model.items if self.model else []):
            item = QListWidgetItem(os.path.basename(path) or path)
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def add_paths(self, paths):
        if self.model is None:
            return 0
        added = self.model.add(paths)
        self.refresh()
        return added

    def remove_selected(self):
        if self.model is None:
            return
        rows = sorted({index.row() for index in self.list.selectedIndexes()}, reverse=True)
        for row in rows:
            self.model.remove(row)
        self.refresh()

    def clear(self):
        if self.model is not None:
            self.model.clear()
        self.refresh()

    def select_path(self, path):
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.UserRole) == path:
                self.list.setCurrentRow(row)
                return

    def _on_item_double_clicked(self, item):
        self.activate_requested.emit(str(item.data(Qt.UserRole)))

    def _on_rows_moved(self, _parent, start, _end, _destination, row):
        if self.model is None:
            return
        destination = row - 1 if row > start else row
        self.model.move(start, destination)
        self.refresh()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()])
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
```

- [ ] **Step 4: Implement selection and playlist wiring in the widget**

In `ui/media_player_widget.py`:

1. Imports: `from ui.media_player_parts import FullscreenHost, PlaylistDock`; from support add `PlaylistModel, collect_video_files`.

2. `PlayerPanel.__init__`: `self.playlist = PlaylistModel()`, `self.selected = False`, `self.on_selected = None`. Add:

```python
    def set_selected(self, selected):
        self.selected = bool(selected)
        border = theme.qss("2px solid $accent") if self.selected else "1px solid transparent"
        self.setStyleSheet("PlayerPanel { " + theme.video_panel_style() + f" border: {border}; " + " }")

    def mousePressEvent(self, event):
        if callable(self.on_selected):
            self.on_selected(self)
        super().mousePressEvent(event)
```

In `_ensure_player`, change the media-status hookup so the host learns which panel finished:

```python
        if callable(self.on_media_status_changed):
            self.player.mediaStatusChanged.connect(
                lambda status, panel=self: self.on_media_status_changed(status, panel))
```

3. `MediaPlayerWidget._build_ui`: for each panel set `panel.on_selected = self._on_panel_selected`; after the stage layout add the dock:

```python
        self.playlist_dock = PlaylistDock(self.stage)
        self.playlist_dock.activate_requested.connect(self._play_from_playlist)
        self.playlist_dock.files_requested.connect(self.add_playlist_files)
        self.playlist_dock.folder_requested.connect(self.add_playlist_folder)
        stage_layout.addWidget(self.playlist_dock)
        self.playlist_dock.hide()
        self.selected_index = 0
        self.select_panel(0)
```

4. Transport bar: a checkable `self.playlist_btn = QPushButton(_tr("Playlist"))` after the fullscreen button; `toggled.connect(self._on_playlist_toggled)`. In `__init__`, inside the `_restoring` block after the panel count is applied, add `self.playlist_btn.setChecked(group["panel_count"] == 1)` so a saved 1-panel layout opens with its playlist showing (the combo's `currentIndexChanged` does not fire when the saved index equals the default).

5. Methods:

```python
    # --- selection & playlist ------------------------------------------------
    def select_panel(self, index):
        if not (0 <= index < len(self.panels)):
            return
        self.selected_index = index
        for panel in self.panels:
            panel.set_selected(panel.index == index)
        panel = self.panels[index]
        self.playlist_dock.set_model(panel.playlist, _tr("Panel %(number)s") % {"number": index + 1})
        self.playlist_dock.select_path(panel._media_path)

    def selected_panel(self):
        panel = self.panels[self.selected_index]
        if panel.isHidden():
            return self.panels[0]
        return panel

    def _on_panel_selected(self, panel):
        self.select_panel(panel.index)

    def toggle_playlist(self):
        self.playlist_btn.setChecked(not self.playlist_btn.isChecked())

    def _on_playlist_toggled(self, checked):
        self.playlist_dock.setVisible(bool(checked))

    def add_playlist_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, _tr("Add videos to playlist"), self.last_folder(), VIDEO_NAME_FILTER)
        if paths:
            self.set_last_folder(paths[0])
            self.playlist_dock.add_paths(paths)

    def add_playlist_folder(self):
        folder = QFileDialog.getExistingDirectory(self, _tr("Add a folder of videos"), self.last_folder())
        if folder:
            self.set_last_folder(folder)
            self.playlist_dock.add_paths(collect_video_files(folder))

    def _play_from_playlist(self, path):
        panel = self.selected_panel()
        if panel.load_media(path):
            self.playlist_dock.select_path(path)
            self.play_all()

    def _advance_playlist(self, step):
        panel = self.selected_panel()
        model = panel.playlist
        current = model.index_of(panel._media_path)
        target = model.next_index(current) if step > 0 else model.previous_index(current)
        if target is None:
            return False
        path = model.items[target]
        if not panel.load_media(path):
            return False
        self.playlist_dock.select_path(path)
        return True

    def playlist_next(self):
        was_playing = self._is_playing
        if self._advance_playlist(1) and was_playing:
            self.play_all()

    def playlist_previous(self):
        was_playing = self._is_playing
        if self._advance_playlist(-1) and was_playing:
            self.play_all()
```

Replace the Task-7 `pass` stubs with these. `_on_panel_count_changed` additionally sets `self.playlist_btn.setChecked(int(count) == 1)`. Replace `_on_media_status_changed`:

```python
    def _on_media_status_changed(self, status, panel=None):
        if status != QMediaPlayer.EndOfMedia or not self._is_playing:
            return
        selected = self.selected_panel()
        if (self.visible_panel_count() == 1 and panel is selected
                and len(selected.playlist.items) > 1 and self._advance_playlist(1)):
            self.play_all()
            return
        self.pause_all()
```

- [ ] **Step 5: Run tests and lint**

Run: `python -m pytest tests/test_media_player_parts.py tests/test_media_player_widget.py` and `python -m ruff check ui/media_player_parts.py ui/media_player_widget.py tests/test_media_player_parts.py tests/test_media_player_widget.py`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add ui/media_player_parts.py ui/media_player_widget.py tests/test_media_player_parts.py tests/test_media_player_widget.py
git commit -m "feat: media player panel selection and per-panel playlist"
```

---

### Task 9: Unsupported Format Tile and Convert-and-Play

**Files:**
- Modify: `ui/media_player_parts.py` (`UnsupportedOverlay`)
- Modify: `ui/media_player_widget.py`
- Test: `tests/test_media_player_parts.py`, `tests/test_media_player_widget.py`

**Interfaces:**
- Consumes: `unsupported_message`, `player_convert_settings`; `conversion.worker.ConversionWorker(file_path, settings, signals)` and `WorkerSignals` (`log(str)`, `conversion_complete(str, bool, dict)`, `progress_update(str, int)`).
- Produces in `ui/media_player_parts.py`: `class UnsupportedOverlay(QWidget)` — child of the panel's `video_container`, hidden by default; `message_label`, `convert_btn`, `dismiss_btn`, `progress_label`; signals `convert_requested`, `dismissed`; methods `show_message(text)`, `show_progress(percent)`, `show_error(text)`, `reset()`.
- Produces on `PlayerPanel`: `self.overlay: UnsupportedOverlay`, `on_player_error` callback `(panel, error_code)`, `show_unsupported(text)`, `hide_unsupported()`; `_ensure_player` connects `player.error` (the `int` overload: `self.player.error[int]`? PyQt5 exposes `QMediaPlayer.error` both as method and signal — connect via `self.player.error.connect(...)` is ambiguous; use `self.player.errorOccurred` if present else `self.player.error[QMediaPlayer.Error]`. **Use exactly:** `signal = getattr(self.player, "error"); signal[QMediaPlayer.Error].connect(...)` wrapped in `try/except TypeError` falling back to `signal.connect(...)`), and `mediaStatusChanged` → `InvalidMedia` also routes to the host's error handler.
- Produces on `MediaPlayerWidget`:
  - `_on_player_error(panel, code)` — for `FormatError`, `ResourceError`, `AccessDeniedError` or `InvalidMedia`: run `probe_runner` in the background (reuse `start_probe` machinery with a `purpose="error"` flag → `probe_finished_for_error = pyqtSignal(int, dict)`), then `panel.show_unsupported(self._unsupported_text(info))`.
  - `_unsupported_text(info) -> str` — `_tr("Windows cannot play %(codecs)s in %(container)s.")`-style templates mirroring `unsupported_message` (keeps `_tr` literal).
  - `convert_and_play(panel)` — builds `player_convert_settings(self.settings)`, creates `WorkerSignals`, connects `progress_update` → `panel.overlay.show_progress`, `conversion_complete` → `_on_convert_finished(panel, ...)`, and calls `self._start_conversion_worker(path, settings, signals)`.
  - `_start_conversion_worker(path, settings, signals)` — default: `ConversionWorker(path, settings, signals)` started on `self.threadpool or QThreadPool.globalInstance()`; tests replace this method.
  - `_on_convert_finished(panel, file_name, success, deletion_info)` — success → `panel.hide_unsupported()`, `panel.load_media(deletion_info["output_file"])`, `play_all()`; failure → `panel.overlay.show_error(...)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_media_player_parts.py` (import `UnsupportedOverlay`):

```python
class UnsupportedOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_show_message_progress_and_error(self):
        overlay = UnsupportedOverlay()
        self.addCleanup(overlay.close)
        overlay.show_message("Windows cannot play x in y.")
        self.assertEqual(overlay.message_label.text(), "Windows cannot play x in y.")
        self.assertTrue(overlay.convert_btn.isEnabled())
        overlay.show_progress(42)
        self.assertIn("42", overlay.progress_label.text())
        self.assertFalse(overlay.convert_btn.isEnabled())
        overlay.show_error("boom")
        self.assertIn("boom", overlay.progress_label.text())
        self.assertTrue(overlay.convert_btn.isEnabled())

    def test_buttons_emit_signals(self):
        overlay = UnsupportedOverlay()
        self.addCleanup(overlay.close)
        events = []
        overlay.convert_requested.connect(lambda: events.append("convert"))
        overlay.dismissed.connect(lambda: events.append("dismiss"))
        overlay.convert_btn.click()
        overlay.dismiss_btn.click()
        self.assertEqual(events, ["convert", "dismiss"])
```

Append to `MediaPlayerWidgetTests`:

```python
    def test_format_error_probes_and_shows_tile_message(self):
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": True, "fps": 25.0, "nb_frames": 0, "duration_ms": 0,
                                            "container": "matroska", "vcodec": "hevc", "acodec": "opus"}
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.mkv"
        widget._on_player_error(panel, QMediaPlayer.FormatError)
        deadline = time.monotonic() + 5
        while not panel.overlay.isVisibleTo(panel) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertEqual(panel.overlay.message_label.text(), "Windows cannot play hevc/opus in matroska.")

    def test_failed_probe_still_offers_convert(self):
        widget = self._widget()
        widget.probe_runner = lambda path: {"ok": False}
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.bin"
        widget._on_probe_finished_for_error(0, {"ok": False})
        self.assertEqual(panel.overlay.message_label.text(), "Windows cannot play this file.")
        self.assertTrue(panel.overlay.convert_btn.isEnabled())

    def test_convert_enqueues_one_job_with_fixed_preset_and_plays_result(self):
        settings = {"destination_folder": "C:\\Videos\\Out", "video_codec": "libx265", "use_gpu": True}
        widget = self._widget(settings=settings)
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.mkv"
        jobs = []
        widget._start_conversion_worker = lambda path, job_settings, signals: jobs.append((path, job_settings, signals))
        widget.convert_and_play(panel)
        self.assertEqual(len(jobs), 1)
        path, job_settings, signals = jobs[0]
        self.assertEqual(path, "C:\\Videos\\clip.mkv")
        self.assertEqual(job_settings["video_codec"], "libx264")
        self.assertEqual(job_settings["destination_folder"], "C:\\Videos\\Out")
        self.assertIn("-crf 20", job_settings["custom_console_command"])
        signals.progress_update.emit(path, 30)
        self.assertIn("30", panel.overlay.progress_label.text())
        loaded = []
        panel.load_media = lambda new_path: loaded.append(new_path) or True
        widget.play_all = lambda: loaded.append("play")
        signals.conversion_complete.emit("clip.mkv", True, {"output_file": "C:\\Videos\\Out\\clip.mp4"})
        self.assertEqual(loaded, ["C:\\Videos\\Out\\clip.mp4", "play"])
        self.assertFalse(panel.overlay.isVisibleTo(panel))

    def test_convert_failure_shows_error_in_tile(self):
        widget = self._widget()
        panel = widget.panels[0]
        panel._media_path = "C:\\Videos\\clip.mkv"
        widget._start_conversion_worker = lambda *args: None
        widget.convert_and_play(panel)
        widget._on_convert_finished(panel, "clip.mkv", False, {"source_file": "C:\\Videos\\clip.mkv"})
        self.assertIn("failed", panel.overlay.progress_label.text().lower())
        self.assertTrue(panel.overlay.convert_btn.isEnabled())
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_media_player_parts.py tests/test_media_player_widget.py -k "Unsupported or convert or error or probe"`
Expected: `ImportError: cannot import name 'UnsupportedOverlay'`.

- [ ] **Step 3: Implement `UnsupportedOverlay`**

Append to `ui/media_player_parts.py`:

```python
class UnsupportedOverlay(QWidget):
    """Inline message shown over a tile when the Windows backend cannot decode a file."""

    convert_requested = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(theme.qss("background: rgba(0, 0, 0, 180); color: white; border-radius: 6px;"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        layout.addWidget(self.message_label)
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("color: white; font-size: 11px; background: transparent;")
        layout.addWidget(self.progress_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.convert_btn = QPushButton(_tr("Convert to MP4 (H.264) and play"))
        self.convert_btn.setStyleSheet(theme.accent_button_style())
        self.convert_btn.setCursor(Qt.PointingHandCursor)
        self.convert_btn.clicked.connect(self.convert_requested.emit)
        self.dismiss_btn = QPushButton(_tr("Dismiss"))
        self.dismiss_btn.setStyleSheet(theme.secondary_button_style())
        self.dismiss_btn.setCursor(Qt.PointingHandCursor)
        self.dismiss_btn.clicked.connect(self.dismissed.emit)
        buttons.addWidget(self.convert_btn)
        buttons.addWidget(self.dismiss_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.hide()

    def reset(self):
        self.progress_label.setText("")
        self.convert_btn.setEnabled(True)

    def show_message(self, text):
        self.reset()
        self.message_label.setText(text)
        self.show()
        self.raise_()

    def show_progress(self, percent):
        self.convert_btn.setEnabled(False)
        self.progress_label.setText(_tr("Converting... %(percent)s%%") % {"percent": int(percent)})

    def show_error(self, text):
        self.convert_btn.setEnabled(True)
        self.progress_label.setText(_tr("Conversion failed: %(error)s") % {"error": text})
```

- [ ] **Step 4: Implement the error path in the widget**

In `ui/media_player_widget.py`:

1. Imports: `from PyQt5.QtCore import QThreadPool`; `from ui.media_player_parts import FullscreenHost, PlaylistDock, UnsupportedOverlay`; from support add `player_convert_settings`; `from conversion.worker import ConversionWorker, WorkerSignals`.

2. `PlayerPanel._build_ui`: after the placeholder, `self.overlay = UnsupportedOverlay(self.video_container)`; in `resizeEvent` also `self.overlay.setGeometry(self.video_container.rect())`. `PlayerPanel.__init__`: `self.on_player_error = None`. Methods:

```python
    def show_unsupported(self, text):
        self.overlay.show_message(text)
        self.overlay.setGeometry(self.video_container.rect())

    def hide_unsupported(self):
        self.overlay.reset()
        self.overlay.hide()
```

In `_ensure_player`, after the status hookup:

```python
        error_signal = self.player.error
        try:
            error_signal[QMediaPlayer.Error].connect(self._on_player_error_code)
        except (TypeError, KeyError):
            error_signal.connect(self._on_player_error_code)
        self.player.mediaStatusChanged.connect(self._on_status_for_errors)
```

and:

```python
    def _on_player_error_code(self, code):
        if callable(self.on_player_error):
            self.on_player_error(self, code)

    def _on_status_for_errors(self, status):
        if status == QMediaPlayer.InvalidMedia and callable(self.on_player_error):
            self.on_player_error(self, QMediaPlayer.FormatError)
```

`load_media` calls `self.hide_unsupported()` before setting media; `clear_media` too.

3. `MediaPlayerWidget`: class attribute `probe_finished_for_error = pyqtSignal(int, dict)`; connect to `_on_probe_finished_for_error` in `__init__`. In `_build_ui` per panel: `panel.on_player_error = self._on_player_error`, `panel.overlay.convert_requested.connect(lambda checked=False, p=panel: self.convert_and_play(p))`, `panel.overlay.dismissed.connect(panel.hide_unsupported)`.

Generalise `start_probe(self, panel, for_error=False)`: the thread emits `probe_finished_for_error` instead of `probe_finished` when `for_error` is true.

```python
    UNSUPPORTED_ERRORS = (QMediaPlayer.FormatError, QMediaPlayer.ResourceError, QMediaPlayer.AccessDeniedError)

    def _on_player_error(self, panel, code):
        if code not in self.UNSUPPORTED_ERRORS or not panel.has_media():
            return
        if self._is_playing:
            self.pause_all()
        self.start_probe(panel, for_error=True)

    def _unsupported_text(self, info):
        if not info or not info.get("ok"):
            return _tr("Windows cannot play this file.")
        vcodec = info.get("vcodec") or _tr("unknown")
        container = info.get("container") or _tr("unknown")
        acodec = info.get("acodec") or ""
        codecs = f"{vcodec}/{acodec}" if acodec else vcodec
        return _tr("Windows cannot play %(codecs)s in %(container)s.") % {"codecs": codecs, "container": container}

    def _on_probe_finished_for_error(self, index, info):
        if not (0 <= index < len(self.panels)):
            return
        panel = self.panels[index]
        if not panel.has_media():
            return
        panel.set_probe_info(info)
        panel.show_unsupported(self._unsupported_text(info))

    def convert_and_play(self, panel):
        path = panel._media_path
        if not path:
            return
        settings = player_convert_settings(self.settings)
        signals = WorkerSignals()
        signals.progress_update.connect(lambda _path, percent, p=panel: p.overlay.show_progress(percent))
        signals.conversion_complete.connect(
            lambda name, success, info, p=panel: self._on_convert_finished(p, name, success, info))
        panel.overlay.show_progress(0)
        panel._conversion_signals = signals  # keep the QObject alive for the worker's lifetime
        self._start_conversion_worker(path, settings, signals)

    def _start_conversion_worker(self, path, settings, signals):
        worker = ConversionWorker(path, settings, signals)
        pool = self.threadpool or QThreadPool.globalInstance()
        pool.start(worker)

    def _on_convert_finished(self, panel, _file_name, success, deletion_info):
        output = (deletion_info or {}).get("output_file", "")
        if success and output:
            panel.hide_unsupported()
            if panel.load_media(output):
                self.play_all()
            return
        panel.overlay.show_error(_tr("the converter could not produce an MP4; see the Conversion Log"))
```

Note: `test_convert_failure_shows_error_in_tile` asserts `"failed"` appears — `show_error` prefixes `Conversion failed:` so this holds.

- [ ] **Step 5: Run tests and lint**

Run: `python -m pytest tests/test_media_player_parts.py tests/test_media_player_widget.py` and `python -m ruff check ui/media_player_parts.py ui/media_player_widget.py tests/test_media_player_parts.py tests/test_media_player_widget.py`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add ui/media_player_parts.py ui/media_player_widget.py tests/test_media_player_parts.py tests/test_media_player_widget.py
git commit -m "feat: unsupported-format tile with convert-to-MP4-and-play"
```

---

### Task 10: Converted Files → Media Player

**Files:**
- Modify: `ui/converted_files_widget.py`
- Modify: `ui/main_window.py` (`_ensure_media_player_widget` ~line 1373; converted widget wiring ~line 529)
- Create: `tests/test_converted_files_widget.py`
- Create: `tests/test_main_window_media_player.py`

**Interfaces:**
- Produces on `ConvertedFilesWidget`: `play_requested = pyqtSignal(str)`; `self.play_button: QPushButton` (text `Play`, hidden until a row is selected, same style path as the clear button); `selected_file_path() -> str`; `request_play_selected()`; context menu first item *Play in Media Player*.
- Produces on `VideoConverterApp`: `play_in_media_player(path)` — ensures the widget, `self.tabs.setTabVisible(index, True)` for the media player tab **without** calling `save_settings`, `setCurrentIndex`, loads into `widget.selected_panel()` and calls `widget.play_all()`. `_ensure_media_player_widget` passes `settings=self.settings`, `save_settings=lambda: save_settings(self.settings)`, `threadpool=self.threadpool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_converted_files_widget.py`:

```python
import shutil
import tempfile
import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ui.converted_files_widget import ConvertedFilesWidget


class ConvertedFilesPlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _widget_with_row(self):
        widget = ConvertedFilesWidget()
        self.addCleanup(widget.close)
        # add_converted_file writes a per-file log; keep it out of the real AppData logs folder.
        log_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(log_dir, ignore_errors=True))
        widget.set_log_folder(log_dir)
        widget.add_converted_file("clip.mp4", {"output_file": "C:\\Videos\\Out\\clip.mp4"}, "C:\\Videos\\Out", True)
        return widget

    def test_play_button_hidden_until_a_row_is_selected(self):
        widget = self._widget_with_row()
        widget.show()
        self.assertFalse(widget.play_button.isVisibleTo(widget))
        widget.table_widget.selectRow(0)
        self.assertTrue(widget.play_button.isVisibleTo(widget))
        widget.table_widget.clearSelection()
        self.assertFalse(widget.play_button.isVisibleTo(widget))

    def test_play_button_emits_selected_path(self):
        widget = self._widget_with_row()
        widget.table_widget.selectRow(0)
        received = []
        widget.play_requested.connect(received.append)
        widget.play_button.click()
        self.assertEqual(received, [widget.table_widget.item(0, 0).data(Qt.UserRole)])
        self.assertTrue(received[0].endswith("clip.mp4"))
```

Create `tests/test_main_window_media_player.py`:

```python
import os
import tempfile
import unittest
from unittest import mock

from PyQt5.QtWidgets import QApplication

import ui.main_window as main_window_module
from ui.main_window import VideoConverterApp


class PlayInMediaPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_play_requested_shows_tab_for_session_and_loads_selected_panel(self):
        window = VideoConverterApp()
        self.addCleanup(window.shutdown)
        window.settings.setdefault("visible_tool_tabs", {})["media_player"] = False
        window.apply_tool_tab_visibility()
        index = window.tabs.indexOf(window.media_player_tab_scroll)
        self.assertFalse(window.tabs.isTabVisible(index))
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with mock.patch.object(main_window_module, "save_settings") as save:
            window.converted_files_widget.play_requested.emit(path)
            self.assertFalse(save.called)
        self.assertTrue(window.tabs.isTabVisible(index))
        self.assertEqual(window.tabs.currentIndex(), index)
        widget = window.media_player_widget
        self.assertIsNotNone(widget)
        self.assertEqual(widget.selected_panel()._media_path, path)
        self.assertFalse(window.settings["visible_tool_tabs"]["media_player"])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_converted_files_widget.py tests/test_main_window_media_player.py`
Expected: `AttributeError: 'ConvertedFilesWidget' object has no attribute 'play_button'` / `play_requested`.

- [ ] **Step 3: Implement in `ConvertedFilesWidget`**

1. Signal: `play_requested = pyqtSignal(str)  # file path the user wants to open in the Media Player`.
2. In `init_ui`, after `layout.addWidget(self.table_container)`:

```python
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 6, 0, 0)
        actions_row.addStretch(1)
        self.play_button = QPushButton(_tr("Play"))
        self.play_button.setFixedSize(60, 24)
        self.play_button.setCursor(Qt.PointingHandCursor)
        self.play_button.setToolTip(_tr("Open the selected file in the Media Player tab"))
        self.play_button.setStyleSheet(clear_button.styleSheet())
        self.play_button.setProperty('skipGlobalStyle', True)
        self.play_button.clicked.connect(self.request_play_selected)
        self.play_button.hide()
        actions_row.addWidget(self.play_button)
        layout.addLayout(actions_row)
```

3. Helpers:

```python
    def selected_file_path(self):
        indexes = self.table_widget.selectionModel().selectedRows()
        if not indexes:
            return ""
        item = self.table_widget.item(indexes[0].row(), 0)
        return str(item.data(Qt.UserRole) or "") if item else ""

    def request_play_selected(self):
        path = self.selected_file_path()
        if path:
            self.play_requested.emit(path)
```

4. `_handle_selection_changed`: show/hide the button — at the start of the `try`: `self.play_button.setVisible(bool(self.table_widget.selectionModel().selectedRows()))`.
5. `show_context_menu`: first item `play_action = menu.addAction(_tr("Play in Media Player"))` followed by `menu.addSeparator()`, and `if action == play_action: self.play_requested.emit(file_path or "")` as the first branch (only when `file_path`).
6. `update_button_style`: also restyle `self.play_button`.

- [ ] **Step 4: Implement in `VideoConverterApp`**

In `__init__` near the `preview_requested` hookup (~line 540): `self.converted_files_widget.play_requested.connect(self.play_in_media_player)`.

`_ensure_media_player_widget`:

```python
        widget = MediaPlayerWidget(
            self,
            button_style=getattr(self, 'current_button_style', None),
            settings=self.settings,
            save_settings=lambda: save_settings(self.settings),
            threadpool=self.threadpool,
        )
```

Add next to it:

```python
    def play_in_media_player(self, path):
        """Converted Files -> Media Player: show the tab for this session and play `path`."""
        if not path or not os.path.exists(path):
            return
        widget = self._ensure_media_player_widget()
        index = self.tabs.indexOf(self.media_player_tab_scroll)
        if index >= 0:
            try:
                self.tabs.setTabVisible(index, True)
            except AttributeError:
                self.media_player_tab_scroll.setVisible(True)
            self.tabs.setCurrentIndex(index)
        panel = widget.selected_panel()
        if panel.load_media(path):
            widget.play_all()
```

Check `save_settings` is already imported in `ui/main_window.py` (it is used at line ~1273); do not add a second import.

- [ ] **Step 5: Run tests and lint**

Run: `python -m pytest tests/test_converted_files_widget.py tests/test_main_window_media_player.py tests/test_media_player_widget.py` and `python -m ruff check ui/converted_files_widget.py tests/test_converted_files_widget.py tests/test_main_window_media_player.py`
Expected: exit 0. (`ui/main_window.py` has ~100 pre-existing ruff findings; run `python -m ruff check ui/main_window.py --diff` only to confirm your added lines introduce none — do not fix the rest.)

- [ ] **Step 6: Commit**

```bash
git add ui/converted_files_widget.py ui/main_window.py tests/test_converted_files_widget.py tests/test_main_window_media_player.py
git commit -m "feat: play converted files in the Media Player tab"
```

---

### Task 11: Real-File Smoke Test and Docs

**Files:**
- Test: `tests/test_media_player_widget.py`
- Modify: `docs/CHANGELOG.md` (append at the end — the file is oldest-first), `docs/BACKLOG.md`

- [ ] **Step 1: Add the real-file smoke test**

Append to `tests/test_media_player_widget.py` (imports: `import subprocess`, `from utils.resources import resource_path`):

```python
class MediaPlayerRealFileSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.clip = ""
        ffmpeg = resource_path("ffmpeg.exe")
        if not os.path.exists(ffmpeg):
            return
        handle = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        handle.close()
        command = [ffmpeg, "-hide_banner", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=25",
                   "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-shortest", handle.name]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            cls.clip = handle.name
        else:
            os.remove(handle.name)

    @classmethod
    def tearDownClass(cls):
        if cls.clip and os.path.exists(cls.clip):
            os.remove(cls.clip)

    def test_load_reports_duration_and_one_frame_step_moves_one_frame(self):
        if not self.clip:
            self.skipTest("ffmpeg.exe not available to synthesise a clip")
        widget = MediaPlayerWidget(settings={})
        self.addCleanup(widget.shutdown)
        panel = widget.panels[0]
        self.assertTrue(panel.load_media(self.clip))
        deadline = time.monotonic() + 8
        while (panel.duration_ms() <= 0 or not panel.probe_info) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        if panel.duration_ms() <= 0:
            self.skipTest("QMediaPlayer backend reported no duration in the headless session")
        self.assertGreater(panel.duration_ms(), 1_500)
        self.assertAlmostEqual(panel.fps(), 25.0, places=1)
        widget.seek_all(400)
        widget.step_frames(1)
        deadline = time.monotonic() + 3
        while abs(panel.player.position() - 440) > 40 and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        self.assertLessEqual(abs(panel.player.position() - 440), 40)
```

Run: `python -m pytest tests/test_media_player_widget.py -k RealFile -rs`
Expected: exit 0 — either passing or reporting one skip with the backend reason. Record which in your report.

- [ ] **Step 2: Changelog**

Append to the end of `docs/CHANGELOG.md`, under the existing `## 2026-09-25` heading (add the sub-heading after the Multi-Source Recorder block):

```markdown
### Media Player

- Added volume and mute for all panels, fullscreen (F / Esc / double-click, auto-hiding
  transport bar), and keyboard shortcuts: Space, Home, Left/Right frame step,
  Shift+Left/Right 5 s, Up/Down volume, M, F, N/P.
- Frame-accurate stepping using the clip's real frame rate (ffprobe), with a
  H:MM:SS.mmm and frame N / total readout.
- Per-panel playlist (add files or a folder, reorder, drag from Explorer); auto-advance
  only in single-panel mode.
- Converted Files gains "Play in Media Player" (context menu and Play button); the tab is
  shown for the session even if hidden in settings.
- Files Windows cannot decode show an inline "Convert to MP4 (H.264) and play" offer
  instead of a blank tile.
- Player settings (last folder, panel count, volume, mute) persist between sessions.
```

- [ ] **Step 3: Backlog**

In `docs/BACKLOG.md`, add before `## Done`:

```markdown
## Media player follow-ups

- FFmpeg-decoded playback (play anything without converting).
- Snapshot current frame to PNG.
- Subtitle tracks and audio track selection.
- Per-panel independent transport (today every panel shares one timeline).
- Persist playlists between sessions.
- Turning the Media Player tab on by default.
```

In `## Feature Ideas`, change the recorder line to strike the finished part:

```markdown
- Multi-source live preview tiles, device discovery, source health indicators, synchronized start/stop~~, and recording presets~~ (presets done 2026-09-25).
```

- [ ] **Step 4: Verify and commit**

Run: `git diff --check` (exit 0) then

```bash
git add tests/test_media_player_widget.py docs/CHANGELOG.md docs/BACKLOG.md
git commit -m "test: media player real-file smoke; docs: media player release notes"
```

---

### Task 12: Verification and Merge

- [ ] **Step 1: Focused suites**

Run: `python -m pytest tests/test_media_player_support.py tests/test_media_player_parts.py tests/test_media_player_widget.py tests/test_converted_files_widget.py tests/test_main_window_media_player.py tests/test_config.py`
Expected: exit 0.

- [ ] **Step 2: Lint touched files**

Run: `python -m ruff check ui/media_player_support.py ui/media_player_parts.py ui/media_player_widget.py ui/converted_files_widget.py utils/config.py tests/test_media_player_support.py tests/test_media_player_parts.py tests/test_media_player_widget.py tests/test_converted_files_widget.py tests/test_main_window_media_player.py tests/test_config.py`
Expected: `All checks passed!`

- [ ] **Step 3: Full suite on the branch**

Run: `python -m pytest -q -p no:cacheprovider` (redirect to `$env:TEMP\pytest_full.txt`)
Expected: exit 0.

- [ ] **Step 4: Manual smoke (developer, real display)**

Launch `python main.py`, enable the Media Player tab in Settings, load two clips, check: volume slider changes loudness; M mutes; F goes fullscreen and the bar hides after 3 s and returns on mouse move; Esc returns; Left/Right step and the readout shows frame numbers; Playlist button shows the dock; in 1-panel mode with two playlist items the second starts after the first ends; Converted Files → right-click → Play in Media Player switches tabs and plays; loading a `.mkv` with HEVC (or any file Windows refuses) shows the tile with the Convert offer. Note any failure in the report; do not merge with a failing manual item.

- [ ] **Step 5: Merge**

```bash
git status --short
git log --oneline master..media-player-complete
git diff --check master...media-player-complete
git checkout master
git merge --no-ff media-player-complete -m "Merge branch 'media-player-complete': volume, fullscreen, shortcuts, frame step, playlist, converted-tab hookup, convert offer"
python -m pytest -q -p no:cacheprovider
git branch -d media-player-complete
git status --short --branch
```

Expected: clean status before merge, merge commit created, suite exit 0 on `master`, branch deleted.
