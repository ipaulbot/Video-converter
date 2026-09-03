# NVC Review Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or execute task-by-task with verification after each task.

**Goal:** Implement the review findings across conversion safety, UI threading, PC report privacy, maintainability, and user help documentation.

**Architecture:** Add focused helper modules for behavior that should be testable without PyQt or FFmpeg. Keep UI behavior stable while routing background events through Qt signals and moving risky synchronous work toward worker-based APIs. Use a browser-style non-overwrite policy for converted outputs: `name.ext`, `name (1).ext`, `name (2).ext`.

**Tech Stack:** Python 3.12, PyQt5, watchdog, FFmpeg/FFprobe, PowerShell collectors, standard-library `unittest`.

---

### Task 1: Conversion Safety Helpers

**Files:**
- Create: `utils/file_naming.py`
- Create: `utils/subprocess_helpers.py`
- Create: `tests/test_file_naming.py`
- Modify: `conversion/worker.py`
- Modify: `conversion/ffmpeg_utils.py`

- [ ] Add failing tests for browser-style unique output paths.
- [ ] Implement `get_unique_path(path)` to return the original path when unused, then append ` (1)`, ` (2)`, etc.
- [ ] Use `get_unique_path()` when choosing conversion output files.
- [ ] Replace duplicated Windows subprocess-startup helpers with `utils.subprocess_helpers.get_subprocess_startupinfo()`.
- [ ] Verify with `python -m unittest tests.test_file_naming`.

### Task 2: FFmpeg Command Correctness

**Files:**
- Modify: `conversion/ffmpeg_utils.py`
- Modify: `conversion/worker.py`
- Create: `tests/test_ffmpeg_command.py`

- [ ] Add failing tests for HEVC normalization and GPU codec intent.
- [ ] Normalize UI codec value `hevc` to CPU codec `libx265`.
- [ ] Use HEVC GPU encoders when the selected codec is HEVC and GPU mode is enabled.
- [ ] Keep non-overwrite behavior by not adding FFmpeg `-y` to standard video conversion. Unique file names avoid overwrite prompts.
- [ ] Use unique temporary palette files for GIF conversion.
- [ ] Verify output file exists and is non-empty before reporting conversion success.

### Task 3: Settings Validation

**Files:**
- Modify: `utils/config.py`
- Modify: `ui/settings_dialog.py`
- Create: `tests/test_config.py`

- [ ] Add tests for retention-time coercion and bounds.
- [ ] Persist `retention_time` as an integer from 0 to 30.
- [ ] Use `QSpinBox` for retention days instead of free-text input while preserving the existing easter egg behavior elsewhere if needed.
- [ ] Load/save JSON with UTF-8 encoding and log config errors.

### Task 4: UI Threading and Queue Lifecycle

**Files:**
- Modify: `ui/main_window.py`
- Modify: `ui/inspection_widget.py`

- [ ] Route watchdog file-created events through a Qt signal connected to a main-thread slot.
- [ ] Track in-flight conversion paths to skip duplicate queue entries.
- [ ] Add shutdown cleanup for preview process, observer, report worker, and conversion worker references.
- [ ] Move inspection FFprobe work into a worker thread or defer it behind a clear loading state.

### Task 5: PC Report Privacy and Cleanup

**Files:**
- Modify: `pc_report/privacy.py`
- Modify: `pc_report/render_json.py`
- Modify: `pc_report/render_html.py`
- Modify: `pc_report/orchestrator.py`
- Modify: `pc_report/utils.py`
- Modify: `ui/pc_report_dialog.py`
- Create: `tests/test_pc_report_privacy.py`

- [ ] Add tests proving JSON redaction masks license keys, serials, MAC addresses, and user paths.
- [ ] Add shared `redact_payload(data, options)` and apply it before HTML/JSON exports.
- [ ] Apply `redact_user_paths()` to rendered path and command fields.
- [ ] Remove unreachable legacy dialog renderer code after `_PCReportWorker._generate()`.
- [ ] Use explicit PowerShell `-Command`, `-NonInteractive`, subprocess timeout handling, and per-section error propagation.
- [ ] Pass orchestrator progress into the dialog.

### Task 6: Help Documentation

**Files:**
- Create: `help_document.html`
- Create or update: `help_document.pdf` if a local PDF generator is available
- Modify: `ui/main_window.py`
- Modify: `main.py`

- [ ] Create a detailed user-facing help document covering setup, conversion workflow, settings, overwrite policy, GPU/codec options, GIF creation, inspection tools, PC reports, privacy, troubleshooting, and FAQ.
- [ ] Let the Help menu open `help_document.pdf` when present, otherwise `help_document.html`.
- [ ] Update startup required resources so the app can run with the HTML help document when a PDF is not present.

### Task 7: Verification

**Files:**
- All touched files

- [ ] Run focused unit tests.
- [ ] Run Python compile check for project modules.
- [ ] Run linter diagnostics for modified files.
- [ ] Manually review UI paths that cannot be fully tested without launching PyQt.
