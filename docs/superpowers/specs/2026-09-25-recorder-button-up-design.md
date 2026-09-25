# Multi-Source Recorder: button-up — design

Date: 2026-09-25. Status: approved in brainstorming (audio, presets, output modes, tab default).

## Goal

Make the Multi-Source Recorder tab do everything its UI already promises, and stop
promising what it does not do. Three things are visibly unfinished today:

1. **Audio is UI-only.** Each source row shows Audio name / Mute / Volume and the
   Video Settings dialog has an audio-device combo, but every combo contains only
   `No Audio`, `discover_directshow_audio_devices` is never called, and none of these
   values reach the FFmpeg command (`conversion/recording_commands.py:build_record_command`
   emits `-an` or `-c:a aac` on whatever the input happens to carry).
2. **Presets are hard-coded.** The Video Settings dialog's *Video Preset* group lists
   `Custom 1…4`; `refresh_preset_list` re-adds those four names instead of reading
   `…\MediaRecorder\Presets\*.json`, so presets saved with *Save as…* are not offered
   back.
3. **Picture-in-picture is a no-op.** Selecting it records separate files and logs
   "saved for later".

Also: the tab is hidden by default (`utils/config.py` → `visible_tool_tabs.multi_source_recorder: False`).

## Non-goals (explicitly out of scope, kept in BACKLOG)

Timer-dialog fields (time format, decimals, maximum time), screen capture (gdigrab),
implementing picture-in-picture, showing source type/address in the main grid, splitting
the 2,600-line widget into modules, wiring `build_multi_source_record_command`, live
verification on Axis / Basler / Daheng hardware (lab checklist), changing the preview
pipeline.

## Design

### 1. Audio per source

**Model.** Each of the four source rows may name one DirectShow audio device. The audio
is muxed into *that row's* output file. `Mute` drops audio for that row; `Volume`
(100/75/50/25/0) applies a gain.

**Device list.** On widget creation (and on a *Refresh devices* action in Video
Settings) the recorder calls `discover_directshow_audio_devices(ffmpeg_path)` once —
in the same background pattern the video-device discovery already uses, never on the
UI thread — and fills every audio combo (main grid rows are not changed; the combo
lives in Video Settings as today) with `No Audio` followed by the device names. The
persisted `audio_device` string is restored even if the device is currently absent
(the combo gets the stored name appended, marked `(not found)`), so a preset made in
the lab still loads on another PC.

**Command shape** (`recording_commands.py`; pure functions, tested):

| Video source | Audio | FFmpeg input | Mapping |
|---|---|---|---|
| DirectShow (`video=Cam`) | device | `-f dshow -i video="Cam":audio="Mic"` (same input; A/V share one clock) | `-map 0:v -map 0:a` |
| RTSP / HTTP / GenICam / file | device | existing video input, plus `-f dshow -thread_queue_size 1024 -use_wallclock_as_timestamps 1 -i audio="Mic"` as a second input | `-map 0:v -map 1:a -shortest` |
| any | `No Audio` or `Mute` | unchanged video input | `-an` |

Audio is encoded `-c:a aac -b:a 128k`; a gain other than 100 adds `-af volume=<v/100>`.
Volume 0 is treated as mute. Stream-copy mode (`copy`) keeps the *video* copy and
still encodes audio to AAC (a raw dshow audio stream cannot be copied into MP4).

**Preview tee.** `build_record_command(preview_pipe=True)` and
`build_directshow_record_with_preview_command` keep the MJPEG pipe leg video-only:
`-map [p]` only; the file leg gets `-map [v]` plus the audio map above. The existing
`-map 0:a?` is replaced by the explicit mapping so a mic on input 1 is never sent to
the pipe.

**Combined grid.** `build_combined_grid_record_command` gains an optional
`audio_device` argument: the first selected, unmuted row with a device supplies the
mic as an extra input mapped to the single output. If none, `-an` as today. The log
line names which row's audio was used.

**Where the values come from.** `_start_recording_processes` reads
`audio_device`, `mute`, `volume` from the row tuple (indices 5–7 today) and passes
them to the builders. No new settings keys: `channels[i].audio_device / mute /
volume` already exist in `Current Settings.json`.

**Failure handling.** If FFmpeg exits within the start watchdog with an audio-related
error (`Could not find audio device`, `I/O error` on `audio=`), the recorder retries
that row once without audio and appends `"<row>: audio device '<name>' unavailable,
recording video only"` to the recording log and status line. Video is never lost to
a missing microphone.

### 2. Presets that round-trip

`recorder_settings.list_recorder_presets(preset_dir)` already exists. The Video
Settings dialog's preset group becomes:

- Combo: entries from `list_recorder_presets(self.recorder_presets_dir())`, sorted;
  empty when none exist; `Custom 1…4` are gone. Selecting an entry updates the
  read-only path field. *Load* applies the preset (`apply_recorder_settings`),
  *Set* saves the current settings over the selected preset, *Save as…* asks for a
  name (`safe_preset_name`) and adds it to the combo, *Delete* removes the file
  after a Yes/No confirmation. `refresh_preset_list` re-reads the directory and is
  called after every save/delete and when the dialog opens.
- The combo text shows `<name> *` when the current settings differ from the loaded
  preset (compared as normalised dicts, ignoring `version`); cleared on load/save.
- Legacy: `Current Settings.json` is unaffected; a preset file that fails to parse is
  skipped with a log line, not a crash.

### 3. Output modes

`output_mode_combo` items: `Separate videos`, `Combined grid` (both places it is
built: dialog and main panel). `apply_recorder_settings` maps a stored
`Picture-in-picture` to `Separate videos` and logs it. `recording_layout_preview_rects`
keeps the `pip` branch (used by the main-window tile layout) but nothing offers it.
The "saved for later" log branch and its tooltip are deleted.

### 4. Tab default

`utils/config.py` default `visible_tool_tabs.multi_source_recorder: True`. Existing
users' settings are not rewritten (the normaliser only fills missing keys), so the
change applies to fresh installs and to anyone who never touched the toggle.

### 5. Tests

- `tests/test_recording_commands.py`: every row of the command table above
  (DirectShow same-input, second-input for RTSP/file, mute, volume 0 and 50, copy +
  audio → AAC, preview tee mapping is video-only on the pipe, combined-grid audio
  pick and `-an` fallback).
- `tests/test_recorder_settings.py`: preset list/save/delete round trip in a temp
  dir; unparseable preset skipped; PiP → Separate mapping.
- `tests/test_multi_source_recorder_widget.py` (headless, `auto_preview=False`):
  audio combos populated from a stubbed discovery; stored device not found is shown
  and kept; dialog preset combo reflects the directory; dirty marker; output-mode
  combo has two items; one-retry-without-audio path with a stubbed process.
- Live check (developer, Logitech C920 + its microphone): record 10 s in *Separate
  videos* with audio at volume 50, then `ffprobe -show_streams`: one `h264` video
  stream and one `aac` audio stream, duration ≈ 10 s; repeat with Mute → no audio
  stream; repeat in *Combined grid* with two rows → one file, one audio stream.

### 6. Docs

`docs/CHANGELOG.md` entry; `docs/BACKLOG.md`: strike "Add a multi-source video
recording tab", list the non-goals above as recorder follow-ups; help chapter
`multi-source-recorder` gains an *Audio* paragraph and the preset workflow (help
docs are rebuilt in the documentation sub-project that follows).
