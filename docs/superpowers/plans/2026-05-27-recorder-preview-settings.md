# Recorder Preview And Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Multi-Source Recorder live preview smoothness/synchronization and add MediaRecorder-style Apply/settings persistence.

**Architecture:** Keep recording process management in `ui/multi_source_recorder_widget.py`, move settings serialization to a new focused helper module, and keep FFmpeg command tuning in `conversion/recording_commands.py`. Preview refresh should flow through existing `update_source_placeholder()` and preview start helpers so Apply, OK, and startup load all use one path.

**Tech Stack:** Python, PyQt5, FFmpeg command builders, JSON settings under Public Documents/Noldus/NVC, `unittest`.

---

### Task 1: Centralize Preview Quality

**Files:**
- Modify: `conversion/recording_commands.py`
- Test: `tests/test_recording_commands.py`

- [ ] **Step 1: Write failing tests for improved preview defaults**

Add tests asserting DirectShow, stream, and combined preview use smoother defaults:

```python
def test_directshow_preview_stream_default_is_smoother():
    command = build_directshow_preview_stream_command("ffmpeg.exe", "HD Pro Webcam C920")
    self.assertIn("fps=20", command)
    self.assertIn("scale=480:-1", command)

def test_rtsp_preview_stream_default_is_smoother():
    command = build_preview_stream_command("ffmpeg.exe", "rtsp://camera/stream")
    self.assertIn("fps=20,scale=480:-1", command)

def test_combined_grid_preview_stream_default_is_smoother():
    command = build_combined_grid_record_command(
        "ffmpeg.exe",
        ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
        "combined.mp4",
        preview_pipe=True,
    )
    filter_complex = command[command.index("-filter_complex") + 1]
    self.assertIn("fps=20,scale=480:-1", filter_complex)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_recording_commands
```

Expected: FAIL because preview commands still use lower FPS/width values.

- [ ] **Step 3: Implement centralized preview defaults**

In `conversion/recording_commands.py`, add constants and use them:

```python
PREVIEW_FPS = 20
PREVIEW_WIDTH = 480
```

Update DirectShow preview to include:

```python
"-vf", f"fps={fps},scale={width}:-1"
```

Update generic stream preview to include:

```python
f"fps={fps},scale={width}:-1"
```

Update combined preview pipe filter to include:

```python
f"[preview]fps={preview_fps},scale={preview_width}:-1[p]"
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_recording_commands
```

Expected: OK.

### Task 2: Add Recorder Settings JSON Model

**Files:**
- Create: `conversion/recorder_settings.py`
- Test: `tests/test_recorder_settings.py`

- [ ] **Step 1: Write failing serializer tests**

Create tests for a model shaped like:

```python
settings = {
    "version": 1,
    "output": {
        "folder": "C:\\Videos",
        "base_name": "Video",
        "encoding": "copy",
        "mode": "Combined grid",
    },
    "timer": {
        "duration": "",
        "time_format": "HH:mm:ss",
        "decimals": "0",
        "use_maximum_time": False,
        "maximum_time": "01:00:00",
    },
    "preview": {
        "fps": 20,
        "width": 480,
    },
    "channels": [
        {
            "enabled": True,
            "video_name": "Video 1",
            "source_type": "rtsp_ip",
            "source": "rtsp://camera/stream",
            "audio_name": "Audio 1",
            "audio_device": "No Audio",
            "mute": False,
            "volume": "100",
            "frame_rate": "30.00",
            "resolution": "1920 x 1080",
        }
    ],
}
```

Assert `save_recorder_settings(path, settings)` writes JSON and `load_recorder_settings(path)` restores it.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_recorder_settings
```

Expected: import failure for `conversion.recorder_settings`.

- [ ] **Step 3: Implement JSON helper**

Create `conversion/recorder_settings.py` with:

```python
import json
import os

RECORDER_SETTINGS_VERSION = 1

def default_recorder_settings():
    return {
        "version": RECORDER_SETTINGS_VERSION,
        "output": {
            "folder": os.path.join(os.path.expanduser("~"), "Videos"),
            "base_name": "Video",
            "encoding": "copy",
            "mode": "Separate videos",
        },
        "timer": {
            "duration": "",
            "time_format": "HH:mm:ss",
            "decimals": "0",
            "use_maximum_time": False,
            "maximum_time": "01:00:00",
        },
        "preview": {"fps": 20, "width": 480},
        "channels": [],
    }

def normalize_recorder_settings(settings):
    normalized = default_recorder_settings()
    settings = settings or {}
    normalized.update({key: value for key, value in settings.items() if key not in ("output", "timer", "preview")})
    normalized["output"].update(settings.get("output") or {})
    normalized["timer"].update(settings.get("timer") or {})
    normalized["preview"].update(settings.get("preview") or {})
    normalized["channels"] = list(settings.get("channels") or [])
    return normalized

def load_recorder_settings(path):
    if not os.path.exists(path):
        return default_recorder_settings()
    with open(path, "r", encoding="utf-8") as handle:
        return normalize_recorder_settings(json.load(handle))

def save_recorder_settings(path, settings):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(normalize_recorder_settings(settings), handle, indent=4)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m unittest tests.test_recorder_settings
```

Expected: OK.

### Task 3: Persist Widget State To Current Settings

**Files:**
- Modify: `ui/multi_source_recorder_widget.py`
- Test: `tests/test_multi_source_recorder_widget.py`

- [ ] **Step 1: Write failing widget save/load tests**

Add tests that set output mode, base name, and two channels; call `capture_recorder_settings()`; then create another widget and call `apply_recorder_settings(settings)`. Assert output controls and source rows match.

- [ ] **Step 2: Run tests to verify fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_multi_source_recorder_widget
```

Expected: missing methods.

- [ ] **Step 3: Implement capture/apply methods**

Add methods:

```python
def capture_recorder_settings(self):
    channels = []
    for source_row in self.source_rows:
        enabled, label_edit, type_combo, source_edit = source_row[:4]
        audio_name_edit = source_row[4]
        mute_check = source_row[5]
        volume_combo = source_row[6]
        audio_device_combo = source_row[7]
        frame_rate_combo = source_row[8]
        resolution_combo = source_row[9]
        channels.append({
            "enabled": enabled.isChecked(),
            "video_name": label_edit.text(),
            "source_type": type_combo.currentData(),
            "source": source_edit.text(),
            "audio_name": audio_name_edit.text(),
            "audio_device": audio_device_combo.currentText(),
            "mute": mute_check.isChecked(),
            "volume": volume_combo.currentText(),
            "frame_rate": frame_rate_combo.currentText(),
            "resolution": resolution_combo.currentText(),
        })
    return {
        "output": {
            "folder": self.output_folder_edit.text(),
            "base_name": self.base_name_edit.text(),
            "encoding": self.codec_combo.currentText(),
            "mode": self.output_mode_combo.currentText(),
        },
        "timer": {"duration": self.duration_edit.text()},
        "preview": {"fps": 20, "width": 480},
        "channels": channels,
    }
```

Implement `apply_recorder_settings()` to set controls and call `update_source_placeholder()` for each restored row.

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_multi_source_recorder_widget
```

Expected: OK.

### Task 4: Add Apply Button And Preview Refresh

**Files:**
- Modify: `ui/multi_source_recorder_widget.py`
- Test: `tests/test_multi_source_recorder_widget.py`

- [ ] **Step 1: Write failing Apply tests**

Add tests that construct `VideoSettingsDialog`, change a device, trigger Apply, and assert the parent receives refreshed preview updates without closing the dialog.

- [ ] **Step 2: Implement Apply button**

Change dialog buttons from OK/Cancel to OK/Cancel/Apply. Connect Apply to a new `apply_changes()` method that calls `apply_to_sources()` and notifies parent:

```python
def apply_changes(self):
    self.apply_to_sources()
    parent = self.parent()
    if parent and hasattr(parent, "refresh_previews_from_sources"):
        parent.refresh_previews_from_sources()
    if parent and hasattr(parent, "save_current_recorder_settings"):
        parent.save_current_recorder_settings()
```

Connect OK to `apply_changes()` then accept.

- [ ] **Step 3: Add parent refresh helper**

Add:

```python
def refresh_previews_from_sources(self):
    for index, source_row in enumerate(self.source_rows):
        _enabled, _label, type_combo, source_edit = source_row[:4]
        self.update_source_placeholder(type_combo, source_edit, index)
```

- [ ] **Step 4: Run widget tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_multi_source_recorder_widget
```

Expected: OK.

### Task 5: Add Main Video Settings Link

**Files:**
- Modify: `ui/multi_source_recorder_widget.py`
- Test: `tests/test_multi_source_recorder_widget.py`

- [ ] **Step 1: Write failing link test**

Assert the widget has a visible link/button with text `Video Settings` below the recording properties table and that clicking it calls `open_video_settings()`.

- [ ] **Step 2: Implement link**

Add a compact `QPushButton("Video Settings")` or link-styled `QLabel` under the recording properties group, connect to `open_video_settings`, and expose it as `self.video_settings_link`.

- [ ] **Step 3: Run widget tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_multi_source_recorder_widget
```

Expected: OK.

### Task 6: Auto-Save And Load Current Recorder Settings

**Files:**
- Modify: `ui/multi_source_recorder_widget.py`
- Modify: `utils/config.py` if a shared path helper is needed
- Test: `tests/test_multi_source_recorder_widget.py`

- [ ] **Step 1: Write failing path/load/save tests**

Patch the settings path to a temp file. Assert `save_current_recorder_settings()` writes JSON, and constructing/applying from that JSON restores settings.

- [ ] **Step 2: Implement current settings path**

Use Public Documents/Noldus/NVC/MediaRecorder/Current Settings.json on Windows, falling back to app data on non-Windows. Add methods:

```python
def recorder_settings_path(self):
    return os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Documents", "Noldus", "NVC", "MediaRecorder", "Current Settings.json")

def save_current_recorder_settings(self):
    save_recorder_settings(self.recorder_settings_path(), self.capture_recorder_settings())

def load_current_recorder_settings(self):
    settings = load_recorder_settings(self.recorder_settings_path())
    self.apply_recorder_settings(settings)
```

Call load at the end of `__init__` after timers are created, with exceptions logged rather than shown.

- [ ] **Step 3: Save on Apply and recording option changes**

Call `save_current_recorder_settings()` from `VideoSettingsDialog.apply_changes()`. Save output controls when recording starts, since that is a clear user commitment point.

- [ ] **Step 4: Run widget and recorder settings tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_multi_source_recorder_widget tests.test_recorder_settings
```

Expected: OK.

### Task 7: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run recorder-related tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest tests.test_multi_source_recorder_widget tests.test_recording_commands tests.test_recording_sources tests.test_single_active_workflow tests.test_recorder_settings
```

Expected: OK.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m unittest discover tests
```

Expected: OK.

- [ ] **Step 3: Check lints**

Run IDE lint check on:

- `conversion/recording_commands.py`
- `conversion/recorder_settings.py`
- `ui/multi_source_recorder_widget.py`
- `tests/test_recording_commands.py`
- `tests/test_recorder_settings.py`
- `tests/test_multi_source_recorder_widget.py`

Expected: no new linter errors.
