# Recorder Button-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Multi-Source Recorder audio capture, disk-backed presets, output-mode cleanup, default visibility, and user documentation without changing the existing source-row structure or preview architecture.

**Architecture:** Extend the pure FFmpeg command builders first, then pass the existing 11-tuple row values through the widget and add one guarded video-only retry for missing audio. Keep discovery asynchronous with a worker thread and a Qt signal, keep presets as normalized JSON files managed by the existing recorder settings module, and make focused UI changes inside the existing widget rather than restructuring it.

**Tech Stack:** Python 3.12, PyQt5, FFmpeg/FFprobe, `unittest`-style pytest tests, Windows DirectShow, JSON settings.

## Global Constraints

- Work on Windows with Python 3.12 and PyQt5.
- Create execution branch `recorder-button-up` from `master`; the repository's main branch is `master`, not `main`.
- Tests run headless because `conftest.py` sets `QT_QPA_PLATFORM=offscreen`.
- Use `python -m pytest -q`; pytest configuration already adds `-q`, and exit code 0 is the pass signal.
- Preserve the existing source-row 11-tuple exactly: `(enabled, label, source_type, source, audio_name, mute, volume, audio_device, frame_rate, resolution, sync_offset)`.
- Do not restructure `ui/multi_source_recorder_widget.py` or change the preview pipeline.
- Keep `_tr()` around every new user-visible string, and pass plain string literals only.
- Never use `QTimer.singleShot`; delayed widget work must use `MultiSourceRecorderWidget._schedule`.
- Never commit real device names or serials from this machine into tests; use generic names such as `Camera A` and `Microphone A`.
- Audio encoding is AAC at 128 kbit/s; volume 0, Mute, and `No Audio` all produce video-only output.
- A non-DirectShow audio input uses `-f dshow -thread_queue_size 1024 -use_wallclock_as_timestamps 1 -i audio="..."`, explicit stream maps, and `-shortest`.
- The MJPEG pipe leg of both tee builders is video-only.
- Existing users' saved visibility settings remain authoritative; only missing/default `visible_tool_tabs.multi_source_recorder` becomes `True`.
- Ruff must be clean on touched code and tests: `python -m ruff check conversion ui/multi_source_recorder_widget.py tests/test_recording_commands.py tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py utils/config.py`.

---

## Files and Interfaces

**Files:**
- Modify: `conversion/recording_commands.py` — build FFmpeg inputs, mappings, codecs, gain, tee outputs, and combined-grid audio.
- Read-only reference: `conversion/recording_sources.py` — the widget calls its existing DirectShow audio discovery and parser interface unchanged.
- Modify: `conversion/recorder_settings.py` — list only parseable preset JSON files.
- Modify: `ui/multi_source_recorder_widget.py` — asynchronous audio discovery, preset UI, output-mode migration, value plumbing, and audio fallback.
- Modify: `utils/config.py` — enable the recorder tab for fresh/default settings.
- Modify: `tests/test_recording_commands.py` — exact command-list tests.
- Modify: `tests/test_recorder_settings.py` — valid/invalid preset listing tests.
- Modify: `tests/test_multi_source_recorder_widget.py` — headless widget, discovery, preset, plumbing, migration, and retry tests.
- Modify: `tests/test_config.py` — default and existing-setting visibility tests.
- Modify: `docs/CHANGELOG.md` — dated recorder completion entry.
- Modify: `docs/BACKLOG.md` — complete build-order step 4 and retain explicit non-goals.
- Modify: `docs/help/source/locales/en/help.py` — English audio and preset workflow help.

**Interfaces:**
- `build_record_command(ffmpeg_path, source, output_file, codec_mode="copy", duration_seconds="", preview_pipe=False, frame_rate="", resolution="", audio_device="", mute=False, volume="100") -> list[str]`
- `build_directshow_record_with_preview_command(ffmpeg_path, source, output_file, duration_seconds="", fps=5, preview_pipe=False, frame_rate="", resolution="", audio_device="", mute=False, volume="100") -> list[str]`
- `build_combined_grid_record_command(ffmpeg_path, sources, output_file, duration_seconds="", preview_pipe=False, preview_fps=PREVIEW_FPS, preview_width=PREVIEW_WIDTH, output_fps=COMBINED_GRID_FPS, offsets_per_source=None, audio_device="", mute=False, volume="100") -> list[str]`
- `discover_directshow_audio_devices(ffmpeg_path, timeout_seconds=12) -> list[str]` remains unchanged.
- `list_recorder_presets(preset_dir) -> list[str]` keeps its signature and skips/logs malformed JSON.
- `MultiSourceRecorderWidget.build_recording_command(..., audio_device="", mute=False, volume="100") -> list[str]`
- Selected source records remain `(row_index: int, label: str, source: str, options: dict[str, str])`; audio values are read from `self.source_rows[row_index][5:8]`, not added to the tuple.

---

### Task 1: DirectShow Same-Input Audio

**Files:**
- Modify: `conversion/recording_commands.py:123-177,565-605`
- Test: `tests/test_recording_commands.py`

**Interfaces:**
- Consumes: existing `_add_input(command, source_text, network_profile="preview", frame_rate="", resolution="", use_wallclock=False, itsoffset="")`.
- Produces: the extended `build_record_command(...)` and `build_directshow_record_with_preview_command(...)` signatures listed above.

- [ ] **Step 1: Create the execution branch from `master`**

Run:

```bash
git checkout master
git pull --ff-only
git checkout -b recorder-button-up
```

Expected: `git branch --show-current` prints `recorder-button-up`.

- [ ] **Step 2: Write failing exact-list tests for DirectShow audio**

Add to `RecordingCommandTests` in `tests/test_recording_commands.py`:

```python
def test_directshow_record_uses_video_and_audio_in_one_input(self):
    command = build_record_command(
        "ffmpeg.exe",
        "video=Camera A",
        "out.mp4",
        "h264",
        "",
        audio_device="Microphone A",
    )

    self.assertEqual(
        command,
        [
            "ffmpeg.exe", "-hide_banner", "-y",
            "-rtbufsize", "512M", "-f", "dshow",
            "-i", 'video="Camera A":audio="Microphone A"',
            "-map", "0:v", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "out.mp4",
        ],
    )

def test_directshow_specialized_builder_uses_same_input_audio(self):
    command = build_directshow_record_with_preview_command(
        "ffmpeg.exe",
        "video=Camera A",
        "out.mp4",
        audio_device="Microphone A",
    )

    self.assertEqual(command.count("-i"), 1)
    self.assertEqual(command[command.index("-i") + 1], 'video="Camera A":audio="Microphone A"')
    self.assertIn(["-map", "0:v", "-map", "0:a"], [command[index:index + 4] for index in range(len(command) - 3)])
    self.assertEqual(command[command.index("-b:a") + 1], "128k")
```

- [ ] **Step 3: Run the focused tests and verify failure**

Run: `python -m pytest tests/test_recording_commands.py::RecordingCommandTests::test_directshow_record_uses_video_and_audio_in_one_input tests/test_recording_commands.py::RecordingCommandTests::test_directshow_specialized_builder_uses_same_input_audio`

Expected: FAIL because the builders do not accept `audio_device`.

- [ ] **Step 4: Add shared audio normalization and same-input DirectShow construction**

Add above `build_record_command` in `conversion/recording_commands.py`:

```python
def _audio_enabled(audio_device, mute=False, volume="100"):
    device = str(audio_device or "").strip()
    try:
        gain = int(str(volume or "100"))
    except ValueError:
        gain = 100
    return bool(device and device != "No Audio" and not mute and gain > 0)


def _directshow_av_source(video_source, audio_device):
    video_name = str(video_source or "").strip()
    if video_name.lower().startswith("video="):
        video_name = video_name[6:]
    video_name = video_name.strip('"')
    audio_name = str(audio_device or "").strip().strip('"')
    return f'video="{video_name}":audio="{audio_name}"'


def _append_audio_encoding_options(command, volume="100"):
    command.extend(["-c:a", "aac", "-b:a", "128k"])
    if str(volume or "100") != "100":
        command.extend(["-af", f"volume={int(str(volume)) / 100:g}"])
```

Extend both builder signatures with `audio_device=""`, `mute=False`, and `volume="100"`. In each builder, calculate:

```python
has_audio = _audio_enabled(audio_device, mute=mute, volume=volume)
if has_audio:
    source_text = _directshow_av_source(source_text, audio_device)
```

For the non-preview DirectShow output, emit:

```python
command.extend(["-map", "0:v"])
if has_audio:
    command.extend(["-map", "0:a"])
else:
    command.append("-an")
command.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])
if has_audio:
    _append_audio_encoding_options(command, volume)
command.append(output_file)
```

Keep `fps` in `build_directshow_record_with_preview_command` for API compatibility.

- [ ] **Step 5: Run command-builder tests**

Run: `python -m pytest tests/test_recording_commands.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add conversion/recording_commands.py tests/test_recording_commands.py
git commit -m "feat: add DirectShow recorder audio"
```

---

### Task 2: Secondary Audio Inputs and Gain

**Files:**
- Modify: `conversion/recording_commands.py:94-177`
- Test: `tests/test_recording_commands.py`

**Interfaces:**
- Consumes: `_audio_enabled`, `_append_audio_encoding_options`, and extended `build_record_command`.
- Produces: secondary DirectShow input audio for non-DirectShow video and consistent video-only behavior.

- [ ] **Step 1: Add exact-list tests for secondary audio, mute, gain, and copy mode**

Add:

```python
def test_rtsp_record_adds_directshow_audio_as_second_input(self):
    command = build_record_command(
        "ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "h264", "",
        audio_device="Microphone A",
    )

    self.assertEqual(
        command,
        [
            "ffmpeg.exe", "-hide_banner", "-y",
            "-rtsp_transport", "tcp", "-timeout", "5000000",
            "-i", "rtsp://camera/stream",
            "-f", "dshow", "-thread_queue_size", "1024",
            "-use_wallclock_as_timestamps", "1",
            "-i", 'audio="Microphone A"',
            "-map", "0:v", "-map", "1:a", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "out.mp4",
        ],
    )

def test_file_copy_mode_keeps_video_copy_and_encodes_audio(self):
    command = build_record_command(
        "ffmpeg.exe", "sample.mp4", "out.mp4", "copy", "",
        audio_device="Microphone A",
    )

    self.assertEqual(
        command,
        [
            "ffmpeg.exe", "-hide_banner", "-y", "-i", "sample.mp4",
            "-f", "dshow", "-thread_queue_size", "1024",
            "-use_wallclock_as_timestamps", "1",
            "-i", 'audio="Microphone A"',
            "-map", "0:v", "-map", "1:a", "-shortest",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "out.mp4",
        ],
    )

def test_audio_volume_fifty_adds_half_gain(self):
    command = build_record_command(
        "ffmpeg.exe", "sample.mp4", "out.mp4", "h264", "",
        audio_device="Microphone A", volume="50",
    )

    self.assertIn(["-af", "volume=0.5"], [command[index:index + 2] for index in range(len(command) - 1)])

def test_no_audio_mute_and_zero_volume_all_emit_an(self):
    cases = [
        {"audio_device": "No Audio"},
        {"audio_device": "Microphone A", "mute": True},
        {"audio_device": "Microphone A", "volume": "0"},
    ]
    for kwargs in cases:
        with self.subTest(kwargs=kwargs):
            command = build_record_command(
                "ffmpeg.exe", "sample.mp4", "out.mp4", "h264", "", **kwargs,
            )
            self.assertEqual(command.count("-i"), 1)
            self.assertIn("-an", command)
            self.assertNotIn("-c:a", command)
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `python -m pytest tests/test_recording_commands.py -k "second_input or keeps_video_copy or half_gain or no_audio_mute"`

Expected: FAIL because non-DirectShow audio is not added.

- [ ] **Step 3: Add the secondary audio input helper**

Add:

```python
def _add_directshow_audio_input(command, audio_device):
    audio_name = str(audio_device or "").strip().strip('"')
    command.extend([
        "-f", "dshow",
        "-thread_queue_size", "1024",
        "-use_wallclock_as_timestamps", "1",
        "-i", f'audio="{audio_name}"',
    ])
```

In `build_record_command`, after `_add_input(...)`, add:

```python
audio_map = ""
if has_audio:
    if is_directshow:
        audio_map = "0:a"
    else:
        _add_directshow_audio_input(command, audio_device)
        audio_map = "1:a"
```

Replace the non-preview codec branch with:

```python
command.extend(["-map", "0:v"])
if has_audio:
    command.extend(["-map", audio_map])
    if not is_directshow:
        command.append("-shortest")
else:
    command.append("-an")

is_network_source = source_text.lower().startswith(("rtsp://", "http://", "https://"))
if codec_mode == "copy" and (is_network_source or not is_directshow):
    command.extend(["-c:v", "copy"])
else:
    command.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])
if has_audio:
    command.extend(["-c:a", "aac", "-b:a", "128k"])
    if str(volume or "100") != "100":
        command.extend(["-af", f"volume={int(str(volume)) / 100:g}"])
command.append(output_file)
```

This deliberately replaces the old `["-c", "copy"]` path so an external microphone is always AAC while the video remains copied.

- [ ] **Step 4: Run all recording command tests**

Run: `python -m pytest tests/test_recording_commands.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add conversion/recording_commands.py tests/test_recording_commands.py
git commit -m "feat: mux external recorder audio"
```

---

### Task 3: Video-Only Preview Tee Legs

**Files:**
- Modify: `conversion/recording_commands.py:140-166,582-600`
- Test: `tests/test_recording_commands.py`

**Interfaces:**
- Consumes: explicit `audio_map` from Tasks 1-2.
- Produces: file-leg audio and pipe-leg video-only mappings in both tee builders.

- [ ] **Step 1: Write failing exact-list tee tests**

Add:

```python
def test_record_preview_tee_maps_audio_only_to_file_leg(self):
    command = build_record_command(
        "ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "h264", "",
        preview_pipe=True, audio_device="Microphone A",
    )

    self.assertEqual(
        command,
        [
            "ffmpeg.exe", "-hide_banner", "-y",
            "-rtsp_transport", "tcp", "-timeout", "5000000",
            "-i", "rtsp://camera/stream",
            "-f", "dshow", "-thread_queue_size", "1024",
            "-use_wallclock_as_timestamps", "1",
            "-i", 'audio="Microphone A"',
            "-filter_complex",
            "[0:v]split=2[v][preview];[preview]fps=20,scale=480:-1[p]",
            "-map", "[v]", "-map", "1:a", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k", "out.mp4",
            "-map", "[p]", "-q:v", "7",
            "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
        ],
    )
    pipe_map = command.index("[p]")
    self.assertNotIn("1:a", command[pipe_map:])

def test_directshow_preview_tee_pipe_leg_is_video_only(self):
    command = build_directshow_record_with_preview_command(
        "ffmpeg.exe", "video=Camera A", "out.mp4",
        preview_pipe=True, audio_device="Microphone A",
    )

    self.assertEqual(command.count("0:a"), 1)
    pipe_map = command.index("[p]")
    self.assertNotIn("0:a", command[pipe_map:])
    self.assertEqual(command[-1], "pipe:1")
```

- [ ] **Step 2: Run the tee tests and verify failure**

Run: `python -m pytest tests/test_recording_commands.py -k "tee_maps_audio or pipe_leg_is_video_only"`

Expected: FAIL because the existing tee path maps optional input audio without the new explicit behavior.

- [ ] **Step 3: Replace both tee output blocks**

In each builder, construct the file leg first:

```python
command.extend([
    "-filter_complex",
    f"[0:v]split=2[v][preview];[preview]fps={PREVIEW_FPS},scale={PREVIEW_WIDTH}:-1[p]",
    "-map", "[v]",
])
if has_audio:
    command.extend(["-map", audio_map])
    if not is_directshow:
        command.append("-shortest")
else:
    command.append("-an")
command.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])
if has_audio:
    command.extend(["-c:a", "aac", "-b:a", "128k"])
    if str(volume or "100") != "100":
        command.extend(["-af", f"volume={int(str(volume)) / 100:g}"])
command.extend([
    output_file,
    "-map", "[p]",
    "-q:v", "7",
    "-f", "image2pipe",
    "-vcodec", "mjpeg",
    "pipe:1",
])
```

For `build_directshow_record_with_preview_command`, `is_directshow` is always `True` and `audio_map` is `"0:a"` when enabled. Remove every `"-map", "0:a?"` occurrence.

- [ ] **Step 4: Run recording command tests**

Run: `python -m pytest tests/test_recording_commands.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add conversion/recording_commands.py tests/test_recording_commands.py
git commit -m "fix: keep recorder preview pipes video only"
```

---

### Task 4: Combined-Grid Audio

**Files:**
- Modify: `conversion/recording_commands.py:182-283`
- Test: `tests/test_recording_commands.py`

**Interfaces:**
- Consumes: `_add_directshow_audio_input`.
- Produces: `build_combined_grid_record_command(..., audio_device="", mute=False, volume="100")`.

- [ ] **Step 1: Write exact-list combined-grid audio tests**

Add:

```python
def test_single_source_combined_grid_maps_optional_audio(self):
    command = build_combined_grid_record_command(
        "ffmpeg.exe", ["video=Camera A"], "combined.mp4",
        audio_device="Microphone A",
    )

    self.assertEqual(
        command,
        [
            "ffmpeg.exe", "-hide_banner", "-y",
            "-rtbufsize", "512M", "-f", "dshow", "-i", "video=Camera A",
            "-f", "dshow", "-thread_queue_size", "1024",
            "-use_wallclock_as_timestamps", "1",
            "-i", 'audio="Microphone A"',
            "-map", "0:v", "-map", "1:a", "-shortest",
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k", "combined.mp4",
        ],
    )

def test_combined_grid_maps_one_audio_stream_and_video_only_preview(self):
    command = build_combined_grid_record_command(
        "ffmpeg.exe",
        ["rtsp://camera/one", "rtsp://camera/two"],
        "combined.mp4",
        preview_pipe=True,
        audio_device="Microphone A",
    )

    self.assertEqual(command.count('audio="Microphone A"'), 1)
    self.assertIn("2:a", command)
    self.assertEqual(command.count("-c:a"), 1)
    self.assertEqual(command[command.index("-b:a") + 1], "128k")
    pipe_map = command.index("[p]")
    self.assertNotIn("2:a", command[pipe_map:])

def test_combined_grid_without_audio_keeps_an(self):
    command = build_combined_grid_record_command(
        "ffmpeg.exe", ["rtsp://camera/one", "rtsp://camera/two"], "combined.mp4",
    )

    self.assertIn("-an", command)
    self.assertNotIn("-c:a", command)

def test_combined_grid_applies_selected_audio_volume(self):
    command = build_combined_grid_record_command(
        "ffmpeg.exe", ["rtsp://camera/one", "rtsp://camera/two"],
        "combined.mp4", audio_device="Microphone A", volume="50",
    )

    self.assertIn(["-af", "volume=0.5"], [command[index:index + 2] for index in range(len(command) - 1)])
```

- [ ] **Step 2: Run the combined-grid audio tests and verify failure**

Run: `python -m pytest tests/test_recording_commands.py -k "combined_grid and audio"`

Expected: FAIL because `audio_device` is not accepted.

- [ ] **Step 3: Add the optional audio input and output mapping**

Extend the signature with `audio_device=""`, `mute=False`, and `volume="100"`. After opening video inputs:

```python
audio_input_index = None
if _audio_enabled(audio_device, mute=mute, volume=volume):
    audio_input_index = len(source_texts)
    _add_directshow_audio_input(command, audio_device)
```

For the one-source fast path, replace `-an` with:

```python
command.extend(["-map", "0:v"])
if audio_input_index is None:
    command.append("-an")
else:
    command.extend(["-map", f"{audio_input_index}:a", "-shortest"])
command.extend(["-r", str(output_fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])
if audio_input_index is not None:
    command.extend(["-c:a", "aac", "-b:a", "128k"])
    if str(volume or "100") != "100":
        command.extend(["-af", f"volume={int(str(volume)) / 100:g}"])
```

For the filter-complex path, replace the unconditional `"-an"` with:

```python
if audio_input_index is None:
    command.append("-an")
else:
    command.extend([
        "-map", f"{audio_input_index}:a",
        "-shortest",
        "-c:a", "aac",
        "-b:a", "128k",
    ])
    if str(volume or "100") != "100":
        command.extend(["-af", f"volume={int(str(volume)) / 100:g}"])
```

Keep the preview output appended after the file output so it has only `-map [p]`.

- [ ] **Step 4: Run all command tests**

Run: `python -m pytest tests/test_recording_commands.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add conversion/recording_commands.py tests/test_recording_commands.py
git commit -m "feat: add combined-grid recorder audio"
```

---

### Task 5: Background Audio Device Discovery

**Files:**
- Modify: `ui/multi_source_recorder_widget.py:1-41,790-840,930-953,1187-1235,1735-1805`
- Test: `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Consumes: `discover_directshow_audio_devices(ffmpeg_path, timeout_seconds=12) -> list[str]`.
- Produces: `audio_devices_discovered = pyqtSignal(list)`, `start_audio_device_discovery(force=False)`, `_apply_audio_devices(devices)`, and `populate_audio_device_combo(combo, stored_device="")`.

- [ ] **Step 1: Write failing headless discovery and absent-device tests**

Add:

```python
def test_audio_discovery_populates_all_row_combos(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)

    widget._apply_audio_devices(["Microphone A", "Microphone B"])

    for row in widget.source_rows:
        self.assertEqual(
            [row[7].itemText(index) for index in range(row[7].count())],
            ["No Audio", "Microphone A", "Microphone B"],
        )

def test_stored_missing_audio_device_is_displayed_and_preserved(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    settings = widget.capture_recorder_settings()
    settings["channels"][0]["audio_device"] = "Lab Microphone"

    widget.apply_recorder_settings(settings, refresh_previews=False)
    widget._apply_audio_devices(["Microphone A"])

    combo = widget.source_rows[0][7]
    self.assertEqual(combo.currentText(), "Lab Microphone (not found)")
    self.assertEqual(combo.currentData(), "Lab Microphone")
    self.assertEqual(widget.capture_recorder_settings()["channels"][0]["audio_device"], "Lab Microphone")

def test_widget_starts_audio_discovery_on_creation(self):
    started = []
    with patch.object(
        MultiSourceRecorderWidget,
        "start_audio_device_discovery",
        lambda self, force=False: started.append(force),
    ):
        MultiSourceRecorderWidget(auto_preview=False)

    self.assertEqual(started, [False])
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `python -m pytest tests/test_multi_source_recorder_widget.py -k "audio_discovery or missing_audio_device"`

Expected: FAIL because discovery state and combo population methods do not exist.

- [ ] **Step 3: Add the signal, state, and background worker**

Import `discover_directshow_audio_devices` beside video discovery. Add to the class:

```python
audio_devices_discovered = pyqtSignal(list)
```

In `__init__`, before `_init_ui()`:

```python
self.directshow_audio_devices = []
self.audio_discovery_running = False
self.audio_devices_discovered.connect(self._apply_audio_devices)
```

After timers are initialized:

```python
self.start_audio_device_discovery()
```

Add:

```python
def start_audio_device_discovery(self, force=False):
    if self.audio_discovery_running:
        return
    if self.directshow_audio_devices and not force:
        self._apply_audio_devices(self.directshow_audio_devices)
        return
    self.audio_discovery_running = True

    def discover():
        devices = discover_directshow_audio_devices(resource_path("ffmpeg.exe"))
        self.audio_devices_discovered.emit(devices)

    threading.Thread(target=discover, daemon=True).start()

def _apply_audio_devices(self, devices):
    self.audio_discovery_running = False
    self.directshow_audio_devices = list(devices or [])
    for source_row in self.source_rows:
        self.populate_audio_device_combo(source_row[7], self._audio_device_value(source_row[7]))

def _audio_device_value(self, combo):
    return str(combo.currentData() or combo.currentText()).removesuffix(" (not found)").strip()

def populate_audio_device_combo(self, combo, stored_device=""):
    selected = str(stored_device or "").removesuffix(" (not found)").strip()
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(_tr("No Audio"), "No Audio")
    for device in self.directshow_audio_devices:
        combo.addItem(device, device)
    if selected and selected != "No Audio" and selected not in self.directshow_audio_devices:
        combo.addItem(_tr("%(device)s (not found)") % {"device": selected}, selected)
    target = combo.findData(selected or "No Audio")
    combo.setCurrentIndex(max(0, target))
    combo.blockSignals(False)
```

This uses the Qt signal to marshal worker results to the UI thread and does not use `QTimer.singleShot`.

- [ ] **Step 4: Preserve item data through settings and the dialog**

In `capture_recorder_settings`, change:

```python
"audio_device": self._audio_device_value(audio_device_combo),
```

In `apply_recorder_settings`, replace direct `setCurrentText` with:

```python
self.populate_audio_device_combo(
    audio_device_combo,
    channel.get("audio_device", self._audio_device_value(audio_device_combo)),
)
```

In `VideoSettingsDialog.__init__`, replace `row_audio_device.addItems(["No Audio"])` with:

```python
stored_audio = parent._audio_device_value(audio_device_combo) if parent and audio_device_combo else "No Audio"
if parent and hasattr(parent, "populate_audio_device_combo"):
    parent.populate_audio_device_combo(row_audio_device, stored_audio)
else:
    row_audio_device.addItem(_tr("No Audio"), "No Audio")
```

In `apply_to_sources`, preserve item data:

```python
if audio_device_combo:
    selected_audio = row_audio_device.currentData() or row_audio_device.currentText()
    if parent and hasattr(parent, "populate_audio_device_combo"):
        parent.populate_audio_device_combo(audio_device_combo, selected_audio)
    else:
        audio_device_combo.setCurrentText(selected_audio)
```

Add a `Refresh devices` button to the dialog and connect it to:

```python
def refresh_audio_devices(self):
    parent = self.parent()
    if parent and hasattr(parent, "start_audio_device_discovery"):
        parent.start_audio_device_discovery(force=True)
```

Use `_tr("Refresh devices")` for its text.

Connect an open dialog to the parent signal:

```python
if parent and hasattr(parent, "audio_devices_discovered"):
    parent.audio_devices_discovered.connect(self.apply_discovered_audio_devices)
```

Add the receiver so refresh results update the dialog as well as the hidden row combos:

```python
def apply_discovered_audio_devices(self, _devices):
    parent = self.parent()
    if not parent:
        return
    for dialog_row in self.dialog_rows:
        combo = dialog_row[7]
        parent.populate_audio_device_combo(combo, parent._audio_device_value(combo))
```

Because the receiver is a `QDialog` method, Qt disconnects it automatically when the dialog is destroyed.

- [ ] **Step 5: Run widget tests**

Run: `python -m pytest tests/test_multi_source_recorder_widget.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/multi_source_recorder_widget.py tests/test_multi_source_recorder_widget.py
git commit -m "feat: discover recorder audio devices"
```

---

### Task 6: Pass Row Audio into Recording Builders

**Files:**
- Modify: `ui/multi_source_recorder_widget.py:2000-2320`
- Test: `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Consumes: row indices 5 (`mute`), 6 (`volume`), 7 (`audio_device`) and extended command builders.
- Produces: per-row audio commands and first-selected-unmuted combined-grid audio.

- [ ] **Step 1: Write failing per-row and combined plumbing tests**

Add:

```python
def test_separate_recording_passes_row_audio_controls_to_builder(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    row = widget.source_rows[0]
    widget.populate_audio_device_combo(row[7], "Microphone A")
    row[6].setCurrentText("50")
    calls = []
    widget.build_recording_command = lambda *args, **kwargs: calls.append(kwargs) or ["ffmpeg.exe", "out.mp4"]
    widget.recording_fallback_commands = lambda *args, **kwargs: []

    class FakeProcess:
        def __getattr__(self, _name):
            return type("Signal", (), {"connect": lambda *_args: None})()
        def setProcessChannelMode(self, _mode):
            pass
        def start(self, _program, _args):
            pass

    widget.create_recording_process = FakeProcess
    widget._start_recording_processes(
        "ffmpeg.exe", [(0, "Camera", "rtsp://camera/stream", {})], "C:\\Temp", "stamp",
    )

    self.assertEqual(calls[0]["audio_device"], "Microphone A")
    self.assertFalse(calls[0]["mute"])
    self.assertEqual(calls[0]["volume"], "50")

def test_combined_grid_uses_first_selected_unmuted_audio_row(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    widget.output_mode_combo.setCurrentText("Combined grid")
    widget.populate_audio_device_combo(widget.source_rows[0][7], "Muted Microphone")
    widget.source_rows[0][5].setChecked(True)
    widget.populate_audio_device_combo(widget.source_rows[1][7], "Microphone B")
    captured = []

    with patch(
        "ui.multi_source_recorder_widget.build_combined_grid_record_command",
        lambda *args, **kwargs: captured.append(kwargs) or ["ffmpeg.exe", "combined.mp4"],
    ):
        widget.create_recording_process = lambda: type(
            "FakeProcess", (),
            {
                "errorOccurred": type("Signal", (), {"connect": lambda *_args: None})(),
                "finished": type("Signal", (), {"connect": lambda *_args: None})(),
                "readyReadStandardOutput": type("Signal", (), {"connect": lambda *_args: None})(),
                "readyReadStandardError": type("Signal", (), {"connect": lambda *_args: None})(),
                "setProcessChannelMode": lambda self, mode: None,
                "start": lambda self, program, args: None,
            },
        )()
        selected = [
            (0, "One", "rtsp://camera/one", {}),
            (1, "Two", "rtsp://camera/two", {}),
        ]
        widget._start_recording_processes("ffmpeg.exe", selected, "C:\\Temp", "stamp")

    self.assertEqual(captured[0]["audio_device"], "Microphone B")
    self.assertFalse(captured[0]["mute"])
    self.assertEqual(captured[0]["volume"], "100")
    self.assertIn("Two", "\n".join(widget.log_lines))
```

- [ ] **Step 2: Run the plumbing tests and verify failure**

Run: `python -m pytest tests/test_multi_source_recorder_widget.py -k "passes_row_audio or first_selected_unmuted"`

Expected: FAIL because audio keyword arguments are not passed.

- [ ] **Step 3: Extend widget command wrappers**

Change the signature:

```python
def build_recording_command(
    self,
    ffmpeg,
    source,
    output_file,
    preview_pipe=False,
    frame_rate="",
    resolution="",
    audio_device="",
    mute=False,
    volume="100",
):
```

Pass the three values to both pure builders:

```python
audio_device=audio_device,
mute=mute,
volume=volume,
```

Extend `recording_fallback_commands` with the same three parameters and forward them on every call.

- [ ] **Step 4: Read audio controls in separate and combined paths**

Inside the separate loop:

```python
mute = self.source_rows[row_index][5].isChecked()
volume = self.source_rows[row_index][6].currentText()
audio_device = self._audio_device_value(self.source_rows[row_index][7])
```

Pass those values into both `build_recording_command` and `recording_fallback_commands`.

At the top of `_start_combined_grid_process`:

```python
audio_device = ""
audio_row_label = ""
audio_volume = "100"
for row_index, label, _source, *_options in selected:
    source_row = self.source_rows[row_index]
    candidate = self._audio_device_value(source_row[7])
    if candidate != "No Audio" and not source_row[5].isChecked() and source_row[6].currentText() != "0":
        audio_device = candidate
        audio_row_label = label
        audio_volume = source_row[6].currentText()
        break
if audio_device:
    self._append_log(f"[Combined] using audio from {audio_row_label}")
```

Pass all three controls to `build_combined_grid_record_command`:

```python
audio_device=audio_device,
mute=not bool(audio_device),
volume=audio_volume,
```

- [ ] **Step 5: Run widget and command tests**

Run: `python -m pytest tests/test_recording_commands.py tests/test_multi_source_recorder_widget.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/multi_source_recorder_widget.py tests/test_multi_source_recorder_widget.py
git commit -m "feat: wire recorder row audio"
```

---

### Task 7: Retry Early Audio Failure Video-Only

**Files:**
- Modify: `ui/multi_source_recorder_widget.py:2160-2475`
- Test: `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Consumes: `build_recording_command(..., audio_device="", mute=False, volume="100")` and `_schedule`.
- Produces: `_is_audio_start_failure(error_text, audio_device) -> bool` and one audio-only fallback attempt.

- [ ] **Step 1: Write a failing one-retry test with a stubbed process**

Add:

```python
def test_audio_start_failure_retries_once_without_audio(self):
    import types
    import time

    widget = MultiSourceRecorderWidget(auto_preview=False)
    widget.status_label.setText("Recording")
    replacement_commands = []
    scheduled = []

    class Signal:
        def connect(self, _callback):
            pass

    class FakeProcess:
        def __init__(self):
            self.errorOccurred = Signal()
            self.finished = Signal()
            self.readyReadStandardOutput = Signal()
            self.readyReadStandardError = Signal()
        def setProcessChannelMode(self, _mode):
            pass
        def start(self, program, args):
            replacement_commands.append([program] + list(args))

    widget.create_recording_process = FakeProcess
    failed = types.SimpleNamespace(
        recording_error_text='Could not find audio device with name [Microphone A]',
        recording_audio_device="Microphone A",
        recording_audio_fallback_command=[
            "ffmpeg.exe", "-hide_banner", "-y", "-i", "sample.mp4",
            "-map", "0:v", "-an", "-c:v", "copy", "out.mp4",
        ],
        recording_audio_retry_attempted=False,
        recording_started_at=time.monotonic(),
        recording_preview_pipe=False,
        recording_row_index=0,
        recording_safe_label="Camera",
        recording_fallback_commands=[],
        recording_retry_delay_ms=0,
        state=lambda: QProcess.NotRunning,
    )
    widget.processes = [failed]

    with patch.object(widget, "_schedule", lambda delay, callback: scheduled.append((delay, callback))):
        widget._process_finished(failed, "Camera", 1)

    self.assertEqual(len(scheduled), 1)
    scheduled[0][1]()
    self.assertEqual(replacement_commands[0], failed.recording_audio_fallback_command)
    self.assertIn("audio device 'Microphone A' unavailable, recording video only", "\n".join(widget.log_lines))
    self.assertIn("video only", widget.status_label.text().lower())
```

- [ ] **Step 2: Run the retry test and verify failure**

Run: `python -m pytest tests/test_multi_source_recorder_widget.py::MultiSourceRecorderWidgetTests::test_audio_start_failure_retries_once_without_audio`

Expected: FAIL because audio fallback metadata and retry logic do not exist.

- [ ] **Step 3: Build and attach a video-only fallback command**

When configuring a row with enabled audio, build:

```python
audio_fallback_command = self.build_recording_command(
    ffmpeg,
    source,
    output_file,
    preview_pipe=preview_pipe,
    frame_rate=options.get("frame_rate", ""),
    resolution=options.get("resolution", ""),
    audio_device="",
    mute=True,
    volume="0",
)
```

Extend `_start_configured_recording_process` with:

```python
audio_device="",
audio_fallback_command=None,
audio_retry_attempted=False,
```

Store:

```python
process.recording_started_at = time.monotonic()
process.recording_audio_device = audio_device
process.recording_audio_fallback_command = audio_fallback_command
process.recording_audio_retry_attempted = audio_retry_attempted
```

Import `time` at module scope.

- [ ] **Step 4: Add specific audio error detection and retry**

Add:

```python
def _is_audio_start_failure(self, error_text, audio_device):
    text = str(error_text or "").lower()
    device = str(audio_device or "").lower()
    return (
        "could not find audio device" in text
        or ("i/o error" in text and ("audio=" in text or (device and device in text)))
    )

def _retry_recording_without_audio(self, process, name):
    command = getattr(process, "recording_audio_fallback_command", None)
    audio_device = getattr(process, "recording_audio_device", "")
    if not command or getattr(process, "recording_audio_retry_attempted", False):
        return False
    started_at = getattr(process, "recording_started_at", 0.0)
    early_window = self.record_start_watchdog_delay_ms / 1000
    if not started_at or time.monotonic() - started_at > early_window:
        return False
    if not self._is_audio_start_failure(
        getattr(process, "recording_error_text", ""),
        audio_device,
    ):
        return False
    message = _tr("%(row)s: audio device '%(device)s' unavailable, recording video only") % {
        "row": name,
        "device": audio_device,
    }
    self._append_log(message)
    self.status_label.setText(message)

    def start_retry():
        if "recording video only" not in self.status_label.text().lower():
            return
        replacement = self.create_recording_process()
        self._start_configured_recording_process(
            replacement,
            command,
            getattr(process, "recording_safe_label", name),
            getattr(process, "recording_row_index", None),
            getattr(process, "recording_preview_pipe", False),
            fallback_commands=[],
            retry_delay_ms=0,
            audio_device="",
            audio_fallback_command=None,
            audio_retry_attempted=True,
        )

    self._schedule(0, start_retry)
    self._notify_workflow_availability_change()
    return True
```

Call it before format fallbacks:

```python
if exit_code and self._retry_recording_without_audio(process, name):
    return
```

For combined recording, attach the same audio metadata and build the no-audio combined command from the same sources and offsets; set `combined_can_retry` independently so the existing Basler retry remains available after an unrelated failure.

- [ ] **Step 5: Verify only audio-related failures take this path**

Add:

```python
def test_non_audio_io_error_does_not_use_audio_fallback(self):
    import time

    widget = MultiSourceRecorderWidget(auto_preview=False)
    process = type("Failed", (), {
        "recording_audio_fallback_command": ["ffmpeg.exe", "video-only"],
        "recording_audio_device": "Microphone A",
        "recording_audio_retry_attempted": False,
        "recording_started_at": time.monotonic(),
        "recording_error_text": "I/O error while opening video=Camera A",
    })()

    self.assertFalse(widget._retry_recording_without_audio(process, "Camera"))
```

Run: `python -m pytest tests/test_multi_source_recorder_widget.py -k "audio_start_failure or non_audio_io_error"`

Expected: PASS.

Also add:

```python
def test_late_audio_failure_does_not_restart_recording(self):
    import time

    widget = MultiSourceRecorderWidget(auto_preview=False)
    process = type("Failed", (), {
        "recording_audio_fallback_command": ["ffmpeg.exe", "video-only"],
        "recording_audio_device": "Microphone A",
        "recording_audio_retry_attempted": False,
        "recording_started_at": time.monotonic() - 10,
        "recording_error_text": "Could not find audio device",
    })()

    self.assertFalse(widget._retry_recording_without_audio(process, "Camera"))
```

This proves only the start-watchdog window triggers the retry.

- [ ] **Step 6: Run all recorder tests**

Run: `python -m pytest tests/test_recording_commands.py tests/test_multi_source_recorder_widget.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ui/multi_source_recorder_widget.py tests/test_multi_source_recorder_widget.py
git commit -m "feat: retry recorder without missing audio"
```

---

### Task 8: Disk-Backed Video Presets

**Files:**
- Modify: `conversion/recorder_settings.py:1-75`
- Modify: `ui/multi_source_recorder_widget.py:325-485,1813-1829,1900-1904`
- Test: `tests/test_recorder_settings.py`
- Test: `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Consumes: `normalize_recorder_settings`, `safe_preset_name`, `preset_file_path`, and recorder widget capture/apply methods.
- Produces: valid preset listing, Load/Set/Save as/Delete, confirmation, and normalized dirty-state comparison.

- [ ] **Step 1: Test malformed preset filtering**

Add `safe_preset_name` to the recorder-settings test imports and add:

```python
def test_list_recorder_presets_skips_unparseable_json(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        save_recorder_settings(
            os.path.join(temp_dir, "Valid.json"),
            default_recorder_settings(),
        )
        with open(os.path.join(temp_dir, "Broken.json"), "w", encoding="utf-8") as handle:
            handle.write("{not json")

        self.assertEqual(list_recorder_presets(temp_dir), ["Valid"])

def test_safe_preset_name_removes_path_characters(self):
    self.assertEqual(safe_preset_name("Lab / Camera: One"), "Lab_Camera_One")
```

Run: `python -m pytest tests/test_recorder_settings.py -k "unparseable or safe_preset"`

Expected: FAIL because malformed `.json` names are currently returned.

- [ ] **Step 2: Validate JSON while listing presets**

Import `logger` and replace the list loop with:

```python
for filename in os.listdir(preset_dir):
    if not filename.lower().endswith(".json"):
        continue
    path = os.path.join(preset_dir, filename)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            normalize_recorder_settings(json.load(handle))
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Skipping unreadable recorder preset %s: %s", path, exc)
        continue
    presets.append(os.path.splitext(filename)[0])
```

Run: `python -m pytest tests/test_recorder_settings.py`

Expected: PASS.

- [ ] **Step 3: Write failing widget tests for disk entries, actions, and dirty marker**

Add:

```python
def test_video_settings_lists_disk_presets_and_refreshes_on_open(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    widget.list_recorder_presets = lambda: ["Alpha", "Beta"]

    dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

    self.assertEqual(
        [dialog.preset_combo.itemText(index) for index in range(dialog.preset_combo.count())],
        ["Alpha", "Beta"],
    )

def test_video_settings_dirty_marker_ignores_version(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    widget.list_recorder_presets = lambda: ["Alpha"]
    widget.load_named_recorder_preset = lambda name: widget.capture_recorder_settings()
    dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)
    dialog.loaded_preset_settings = widget.capture_recorder_settings()
    dialog.loaded_preset_settings["version"] = 999

    dialog.update_preset_dirty_marker()
    self.assertEqual(dialog.preset_combo.currentText(), "Alpha")

    widget.source_rows[0][2].setCurrentIndex(1)
    dialog.update_preset_dirty_marker()
    self.assertEqual(dialog.preset_combo.currentText(), "Alpha *")

def test_delete_selected_preset_confirms_and_refreshes(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    widget.list_recorder_presets = lambda: ["Alpha"]
    deleted = []
    widget.delete_named_recorder_preset = lambda name: deleted.append(name)
    dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

    with patch("ui.multi_source_recorder_widget.QMessageBox.question", return_value=QMessageBox.Yes):
        dialog.delete_selected_preset()

    self.assertEqual(deleted, ["Alpha"])
```

Import `QMessageBox` in the test module.

- [ ] **Step 4: Run preset widget tests and verify failure**

Run: `python -m pytest tests/test_multi_source_recorder_widget.py -k "disk_presets or dirty_marker or delete_selected_preset"`

Expected: FAIL because the dialog still creates four hard-coded slots and lacks delete/dirty behavior.

- [ ] **Step 5: Build the preset controls from disk**

Import `safe_preset_name` from `conversion.recorder_settings`. Remove `Custom 1…4`. Keep the read-only path field visible by deleting `self.preset_path_edit.hide()`. Add buttons with these translated labels:

```python
self.preset_save_as_button = QPushButton(_tr("Save as..."))
self.preset_delete_button = QPushButton(_tr("Delete"))
```

Connect:

```python
self.preset_save_as_button.clicked.connect(self.save_preset_as)
self.preset_delete_button.clicked.connect(self.delete_selected_preset)
```

At the end of dialog construction call:

```python
self.loaded_preset_name = ""
self.loaded_preset_settings = None
self.refresh_preset_list()
```

Replace the existing tests that expect fixed `Custom 1…4` slots and no Save as/Delete controls with:

```python
def test_video_settings_dialog_uses_disk_preset_actions(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    widget.list_recorder_presets = lambda: ["Alpha", "Beta"]
    dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

    self.assertEqual(
        [dialog.preset_combo.itemText(index) for index in range(dialog.preset_combo.count())],
        ["Alpha", "Beta"],
    )
    self.assertTrue(hasattr(dialog, "preset_save_as_button"))
    self.assertTrue(hasattr(dialog, "preset_delete_button"))
    self.assertFalse(dialog.preset_path_edit.isHidden())
```

Replace `refresh_preset_list` with:

```python
def refresh_preset_list(self, selected_name=""):
    parent = self.parent()
    names = parent.list_recorder_presets() if parent and hasattr(parent, "list_recorder_presets") else []
    current = selected_name or self.selected_preset_name().removesuffix(" *")
    self.preset_combo.blockSignals(True)
    self.preset_combo.clear()
    self.preset_combo.addItems(names)
    if current in names:
        self.preset_combo.setCurrentText(current)
    self.preset_combo.blockSignals(False)
    self.update_selected_preset_path()
```

Change `selected_preset_name` to:

```python
def selected_preset_name(self):
    return self.preset_combo.currentText().removesuffix(" *").strip()
```

- [ ] **Step 6: Implement Load, Set, Save as, Delete, and dirty comparison**

Make widget preset methods return settings:

```python
def list_recorder_presets(self):
    return list_recorder_presets(self.recorder_presets_dir())

def save_named_recorder_preset(self, name):
    settings = self.capture_recorder_settings()
    save_recorder_settings(self.recorder_preset_path(name), settings)
    return settings

def load_named_recorder_preset(self, name):
    settings = load_recorder_settings(self.recorder_preset_path(name))
    self.apply_recorder_settings(settings)
    self.refresh_previews_from_sources()
    self.save_current_recorder_settings()
    return settings

def delete_named_recorder_preset(self, name):
    path = self.recorder_preset_path(name)
    if os.path.exists(path):
        os.remove(path)
```

Use these dialog methods:

```python
def _comparable_settings(self, settings):
    value = normalize_recorder_settings(settings)
    value.pop("version", None)
    return value

def load_selected_preset(self):
    name = self.selected_preset_name()
    parent = self.parent()
    if not name or not parent:
        return
    self.loaded_preset_settings = parent.load_named_recorder_preset(name)
    self.loaded_preset_name = name
    self.apply_parent_state_to_dialog()
    self.refresh_preset_list(name)

def set_selected_preset(self):
    name = self.selected_preset_name()
    parent = self.parent()
    if not name or not parent:
        return
    self.apply_changes()
    self.loaded_preset_settings = parent.save_named_recorder_preset(name)
    self.loaded_preset_name = name
    self.refresh_preset_list(name)

def save_preset_as(self):
    name, accepted = QInputDialog.getText(
        self,
        _tr("Save Video Preset"),
        _tr("Preset name:"),
        text=self.selected_preset_name(),
    )
    if not accepted or not name.strip():
        return
    safe_name = safe_preset_name(name)
    self.apply_changes()
    self.loaded_preset_settings = self.parent().save_named_recorder_preset(safe_name)
    self.loaded_preset_name = safe_name
    self.refresh_preset_list(safe_name)

def delete_selected_preset(self):
    name = self.selected_preset_name()
    if not name:
        return
    answer = QMessageBox.question(
        self,
        _tr("Delete Video Preset"),
        _tr("Delete preset '%(name)s'?") % {"name": name},
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return
    self.parent().delete_named_recorder_preset(name)
    self.loaded_preset_name = ""
    self.loaded_preset_settings = None
    self.refresh_preset_list()

def update_preset_dirty_marker(self):
    if not self.loaded_preset_name or self.loaded_preset_settings is None:
        return
    current = self.parent().capture_recorder_settings()
    dirty = self._comparable_settings(current) != self._comparable_settings(self.loaded_preset_settings)
    text = f"{self.loaded_preset_name} *" if dirty else self.loaded_preset_name
    index = self.preset_combo.currentIndex()
    if index < 0:
        return
    self.preset_combo.blockSignals(True)
    self.preset_combo.setItemText(index, text)
    self.preset_combo.blockSignals(False)
    self.update_selected_preset_path()
```

Connect dialog field changes to `update_preset_dirty_marker`; call it after `apply_to_sources()` so comparison uses current widget state. Refresh on dialog open, after save, and after delete.

- [ ] **Step 7: Run settings and widget tests**

Run: `python -m pytest tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add conversion/recorder_settings.py ui/multi_source_recorder_widget.py tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py
git commit -m "feat: round-trip recorder presets"
```

---

### Task 9: Remove No-Op Picture-in-Picture Choice

**Files:**
- Modify: `conversion/recorder_settings.py:30-42`
- Modify: `ui/multi_source_recorder_widget.py:385-395,1036-1048,1768-1778,2118-2128`
- Test: `tests/test_recorder_settings.py`
- Test: `tests/test_multi_source_recorder_widget.py`

**Interfaces:**
- Consumes: existing normalized recorder settings.
- Produces: two-item output-mode combos and normalized legacy PiP migration to Separate videos.

- [ ] **Step 1: Write failing combo and migration tests**

Add to `tests/test_recorder_settings.py`:

```python
def test_normalize_maps_legacy_picture_in_picture_to_separate_videos(self):
    settings = normalize_recorder_settings({
        "output": {"mode": "Picture-in-picture"},
    })

    self.assertEqual(settings["output"]["mode"], "Separate videos")
```

Import `normalize_recorder_settings`. Add to widget tests:

```python
def test_output_mode_combos_offer_only_implemented_modes(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    dialog = VideoSettingsDialog(widget.source_rows, widget.output_controls(), parent=widget)

    expected = ["Separate videos", "Combined grid"]
    self.assertEqual(
        [widget.output_mode_combo.itemText(index) for index in range(widget.output_mode_combo.count())],
        expected,
    )
    self.assertEqual(
        [dialog.output_mode_combo.itemText(index) for index in range(dialog.output_mode_combo.count())],
        expected,
    )

def test_apply_settings_maps_legacy_picture_in_picture(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    settings = widget.capture_recorder_settings()
    settings["output"]["mode"] = "Picture-in-picture"

    widget.apply_recorder_settings(settings, refresh_previews=False)

    self.assertEqual(widget.output_mode_combo.currentText(), "Separate videos")
    self.assertIn("Picture-in-picture", "\n".join(widget.log_lines))
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m pytest tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py -k "implemented_modes or legacy_picture or normalize_maps_legacy"`

Expected: FAIL because both combos still offer PiP and setting it is not logged/migrated.

- [ ] **Step 3: Restrict both combos and migrate legacy settings**

In `normalize_recorder_settings`, after updating `normalized["output"]`, add:

```python
if normalized["output"].get("mode") == "Picture-in-picture":
    normalized["output"]["mode"] = "Separate videos"
```

Use in both UI locations:

```python
self.output_mode_combo.addItems(["Separate videos", "Combined grid"])
```

In `apply_recorder_settings`, inspect the input before normalizing so the migration is still logged:

```python
legacy_output_mode = (settings or {}).get("output", {}).get("mode")
normalized = normalize_recorder_settings(settings)
output = normalized.get("output", {})
if legacy_output_mode == "Picture-in-picture":
    self._append_log(
        _tr("[recorder] legacy Picture-in-picture mode mapped to Separate videos")
    )
self.output_mode_combo.setCurrentText(
    output.get("mode", self.output_mode_combo.currentText())
)
```

Delete the tooltip that says layouts are saved for later and delete the `start_recording` branch that logs `"output is saved for later"`. Keep `recording_layout_preview_rects` and its `pip` branch unchanged.

Update the existing signal test so it selects an offered mode:

```python
def test_changing_output_mode_emits_layout_preview_changed(self):
    widget = MultiSourceRecorderWidget(auto_preview=False)
    fired = []
    widget.layout_preview_changed.connect(lambda: fired.append(True))
    widget.output_mode_combo.setCurrentText("Combined grid")
    self.assertTrue(fired)
```

- [ ] **Step 4: Run focused and layout tests**

Run: `python -m pytest tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py tests/test_recording_commands.py -k "output_mode or picture_in_picture or layout"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add conversion/recorder_settings.py ui/multi_source_recorder_widget.py tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py
git commit -m "fix: remove no-op recorder output mode"
```

---

### Task 10: Enable Recorder Tab by Default

**Files:**
- Modify: `utils/config.py:60-68`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `normalize_settings(settings)`.
- Produces: fresh/missing recorder visibility defaults to `True`, explicit existing `False` remains `False`.

- [ ] **Step 1: Update tests first**

Change the expected default and add explicit preservation:

```python
def test_default_visible_tool_tabs_include_multi_source_recorder(self):
    settings = normalize_settings({})

    self.assertTrue(settings["visible_tool_tabs"]["multi_source_recorder"])

def test_existing_recorder_visibility_false_is_preserved(self):
    settings = normalize_settings({
        "visible_tool_tabs": {"multi_source_recorder": False},
    })

    self.assertFalse(settings["visible_tool_tabs"]["multi_source_recorder"])
```

Also change the existing full-dict expectation from `"multi_source_recorder": False` to `True`, and change the partial-settings assertion to `assertTrue`.

- [ ] **Step 2: Run config tests and verify failure**

Run: `python -m pytest tests/test_config.py`

Expected: FAIL because the default remains false.

- [ ] **Step 3: Change only the default**

In `utils/config.py`:

```python
"multi_source_recorder": True,
```

Do not alter the normalizer; its `supplied_tabs.get(key, default_value)` behavior already preserves an explicit existing false value.

- [ ] **Step 4: Run config tests**

Run: `python -m pytest tests/test_config.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/config.py tests/test_config.py
git commit -m "feat: show recorder tab by default"
```

---

### Task 11: Recorder Documentation

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/help/source/locales/en/help.py:264-280`

**Interfaces:**
- Consumes: implemented UI labels and behavior from Tasks 5-10.
- Produces: release notes, follow-up boundaries, and English user help.

- [ ] **Step 1: Add the dated changelog entry**

Insert after the title and before older entries:

```markdown
## 2026-09-25

### Multi-Source Recorder

- Added per-source DirectShow audio selection, mute and volume control, including
  AAC audio for stream-copy video and automatic video-only retry when a selected
  microphone is unavailable.
- Recorder presets now load from and save to the MediaRecorder Presets folder,
  with Load, Set, Save as and Delete actions plus unsaved-change indication.
- Removed the non-functional Picture-in-picture choice, retained Separate videos
  and Combined grid, and made the recorder tab visible by default for fresh
  settings.
```

- [ ] **Step 2: Complete backlog step 4 and record every non-goal**

Replace build-order item 4 with:

```markdown
4. ~~Add a multi-source video recording tab.~~ Done 2026-09-25; see "Recorder follow-ups".
```

Add before `## Done`:

```markdown
## Recorder follow-ups

- Timer-dialog fields: time format, decimals, maximum time.
- Screen capture through FFmpeg gdigrab.
- Picture-in-picture recording.
- Source type and address columns in the main grid.
- Splitting the 2,600-line recorder widget into modules.
- Wiring `build_multi_source_record_command` into the live recorder.
- Live verification on Axis, Basler and Daheng hardware using the lab checklist.
- Preview-pipeline changes.
```

- [ ] **Step 3: Expand the English help chapter**

Replace the Multi-Source Recorder steps with:

```python
{"type": "steps", "items": [
    "Use RTSP, HTTP or file URLs directly, for example rtsp://192.168.1.10/stream.",
    "Use Windows DirectShow input strings for local capture devices, for example "
    "video=Camera Name.",
    "Open Video Settings to choose a DirectShow microphone for each source. Mute "
    "or Volume 0 records that source without audio; lower volume values reduce "
    "the recorded audio gain.",
    "Choose Separate videos to write one file per source, or Combined grid to "
    "write one file whose audio comes from the first enabled, unmuted row with "
    "a selected microphone.",
    "Use Load to apply a preset, Set to overwrite the selected preset, Save as... "
    "to create one, and Delete to remove one. An asterisk marks settings changed "
    "since the selected preset was loaded or saved.",
    "Leave duration blank to record until you press Stop.",
]},
{"type": "note", "items": [
    "If a saved microphone is not connected, it appears as (not found). NVC keeps "
    "the saved name and retries an early audio-device failure as video-only so the "
    "camera recording is not lost.",
]},
```

Do not edit Dutch or Simplified Chinese help; those are handled by the documentation sub-project.

- [ ] **Step 4: Verify Python syntax and documentation diff**

Run:

```bash
python -m py_compile docs/help/source/locales/en/help.py
git diff --check
git diff -- docs/CHANGELOG.md docs/BACKLOG.md docs/help/source/locales/en/help.py
```

Expected: `py_compile` and `git diff --check` exit 0; the diff contains the 2026-09-25 entry, struck step 4, all eight non-goals, and English audio/preset help.

- [ ] **Step 5: Commit**

```bash
git add docs/CHANGELOG.md docs/BACKLOG.md docs/help/source/locales/en/help.py
git commit -m "docs: document recorder button-up"
```

---

### Task 12: Verification, Live C920 Check, and Merge

**Files:**
- Verify: all files listed in this plan.
- Live output: a developer-selected temporary recording folder outside the repository.

**Interfaces:**
- Consumes: completed `recorder-button-up` branch.
- Produces: automated verification evidence, three live recording checks, and a `--no-ff` merge into `master`.

- [ ] **Step 1: Run focused recorder tests**

Run:

```bash
python -m pytest tests/test_recording_commands.py tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py tests/test_config.py
```

Expected: exit code 0.

- [ ] **Step 2: Run the required touched-file Ruff check**

Run:

```bash
python -m ruff check conversion ui/multi_source_recorder_widget.py tests/test_recording_commands.py tests/test_recorder_settings.py tests/test_multi_source_recorder_widget.py utils/config.py
```

Expected: exit code 0 with `All checks passed!`.

- [ ] **Step 3: Run the full automated suite on the feature branch**

Run:

```bash
python -m pytest -q
```

Expected: exit code 0. Treat the exit code, not repeated `-q` text, as the pass signal.

- [ ] **Step 4: Record 10 seconds from the Logitech C920 with volume 50**

In NVC:

1. Open Multi-Source Recorder.
2. Select the C920 video device and its microphone without copying either real device name into tests or source files.
3. Set output mode to `Separate videos`, Mute off, Volume `50`, duration `10`.
4. Record to `C:\Temp\NVC-recorder-live\audio-50.mp4`.

Run:

```powershell
ffprobe.exe -v error -show_entries stream=index,codec_type,codec_name -of json "C:\Temp\NVC-recorder-live\audio-50.mp4"
ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "C:\Temp\NVC-recorder-live\audio-50.mp4"
```

Expected: exactly one `video` stream with `codec_name` `h264`, exactly one `audio` stream with `codec_name` `aac`, and duration approximately 10 seconds.

- [ ] **Step 5: Record 10 seconds muted and verify no audio stream**

In NVC, keep the same source, enable Mute, and record to `C:\Temp\NVC-recorder-live\muted.mp4`.

Run:

```powershell
ffprobe.exe -v error -show_entries stream=index,codec_type,codec_name -of json "C:\Temp\NVC-recorder-live\muted.mp4"
ffprobe.exe -v error -select_streams a -show_entries stream=index -of csv=p=0 "C:\Temp\NVC-recorder-live\muted.mp4"
```

Expected: the JSON contains one H.264 video stream; the second command prints no rows and exits 0.

- [ ] **Step 6: Record a two-row combined grid and verify one file with one audio stream**

In NVC:

1. Enable two video rows.
2. Set `Combined grid`.
3. Select the C920 microphone on one unmuted row.
4. Record 10 seconds to `C:\Temp\NVC-recorder-live\combined.mp4`.

Run:

```powershell
Get-ChildItem "C:\Temp\NVC-recorder-live\combined*.mp4" | Select-Object Name,Length
ffprobe.exe -v error -show_entries stream=index,codec_type,codec_name -of json "C:\Temp\NVC-recorder-live\combined.mp4"
ffprobe.exe -v error -select_streams a -show_entries stream=index -of csv=p=0 "C:\Temp\NVC-recorder-live\combined.mp4"
```

Expected: one combined output file, one H.264 video stream, and exactly one CSV audio-stream row whose codec is AAC in the JSON.

- [ ] **Step 7: Inspect branch state before merge**

Run:

```bash
git status --short
git log --oneline master..recorder-button-up
git diff --check master...recorder-button-up
```

Expected: clean status, the task commits listed, and `git diff --check` exit code 0.

- [ ] **Step 8: Merge with an explicit merge commit**

Run:

```bash
git checkout master
git merge --no-ff recorder-button-up
```

Expected: merge succeeds and `git log -1 --pretty=%s` reports a merge commit.

- [ ] **Step 9: Run the full suite on merged `master`**

Run:

```bash
python -m pytest -q
```

Expected: exit code 0.

- [ ] **Step 10: Confirm final repository state**

Run:

```bash
git status --short --branch
git log -1 --oneline
```

Expected: branch is `master`, the working tree is clean, and the latest commit is the recorder-button-up merge.
