# Task 29 Report: Noldus Summary and Legacy Collector Removal

## Status

Implemented Task 29 on `pc-report-siw` in three commits:

1. `6a6c269` — `refactor(pc_report): move Noldus vocabulary to noldus_terms; delete legacy collectors`
2. `82e2d3d` — `refactor(pc_report): share elapsed timings through RunContext`
3. `46e75e9` — `feat(pc_report): Noldus Summary with attention items, specs and inventories`

## Implementation

- Moved the Noldus vocabulary and scanner helpers into `pc_report/noldus_terms.py`, with `_nvc_filter_roots` exposed as `nvc_filter_roots`.
- Moved the helper tests to `tests/pc_report/test_noldus_terms.py`.
- Deleted `pc_report/collectors.py` and `pc_report/utils.py`.
- Replaced the remaining compatibility imports with direct `pc_report.format` and `pc_report.ps` imports, removed the obsolete re-export test, and updated the package/test docstrings.
- Kept section timing in the shared `RunContext.elapsed` mapping and used that same mapping for `meta["elapsed_by_section"]`.
- Added `pc_report/sections/noldus_summary.py`, registered through normal section discovery.
- Added attention detection, system specifications, collection timing, Noldus software/runtime/driver/codec/environment inventories, cameras, Sentinel dongles, and GigE settings.
- `collect` only reads dependency results, `ctx.run.elapsed`, and `ctx.is_admin`; it makes no PowerShell, text, shared-source, or filesystem calls.
- `build` is pure. Noldus filter files already represented by the Codecs dependency are used from that built section data; no filesystem scan occurs in `build`.
- No new fixture capture was needed because Noldus Summary issues no queries of its own.
- The `.ok` CSS rule required by the brief was already present in the foundation and was retained.

## Label Drift and Adaptations

| Requirement/brief label | Real foundation label/shape | Adaptation |
|---|---|---|
| Pending reboot | `operating_system.flatten()["Pending Reboot"]` | Accepts `Pending Reboot` and `Reboot Pending`. |
| UAC disabled | Current OS section emits `UAC Enabled`; corrected synthetic data may expose `User Account Control (UAC)` from Security | Checks tolerant candidates in `security.flatten`, then falls back to `operating_system.flatten`. |
| Low disk summary only | `logical_disks["rows"]` uses `Drive`, `Free`, and `Free %`; low percentages may carry a `⚠` prefix | Parses the real row values and flags either `< 10 %` or `< 10 GB`; falls back to summary labels if rows are absent. |
| Service `Start Mode` | Built service rows use `Name`, `State`, and `Start Mode` | Accepts `Start Mode` and legacy `StartMode`. |
| Frame Server enabled | `cameras.frame_server_enabled(data)` interprets `Frame Server Mode` | Uses the public helper rather than duplicating label logic. |
| Consent denied | `cameras.denied(data)` interprets `Camera/Microphone Access (<scope>)` | Uses the public helper and reports its scoped names. |
| Camera names | Built PnP rows plus `cameras.camera_names(data)` | Uses the public helper so camera filtering matches the Cameras section. |
| Dongles | USB device rows plus `usb.hasp_devices(data)` | Uses the public helper for specification names and VID/name matching for table rows. |
| GigE settings | `network_adapters["gige"]` with `Jumbo Packet` and `Interrupt Moderation` | Reads the real built rows; jumbo lookup also tolerates `Jumbo Frames`/`Jumbo Frame`. |
| Memory counter source | `memory.flatten()["Live Source"]` | Reports Info when not `Performance counters`. |
| Sensor counter note | Notes are not exposed by `ctx.result`, while `collect` is forbidden from reading wrapped run results | Detects the equivalent built-data state: a present sensor live group with all counter-derived values empty. |
| VM verdict | `virtual_machine.flatten()["Running Inside a VM"]` and `Interpretation` | Uses the public flatten helper and real verdict labels. |
| Summary memory/GPU | `system_summary.flatten()` uses `Installed Memory` and `Video Adapters` | Prefers System Summary, then falls back to Memory and Video helpers. |
| System drive free | System Summary `drives` rows use `Drive`, `Free`, `Free %` | Selects `C:` and formats free space plus percentage. |
| Slowest sections | Corrected requirement is slowest 3, not the brief's 5 | Sorts `ctx.run.elapsed` descending and keeps three. |

## Attention Items on Real Fixtures

- Warning — Pending reboot — Windows has a reboot pending
- Warning — Low disk space — `D: (2.5 GB, ⚠ 0.3 %)`
- Warning — USB selective suspend — AC and DC enabled
- Info — Camera Frame Server shared mode
- Info — Jumbo frames disabled on GigE adapters — Noldus Switch reports 1514
- Info — Report ran without administrator rights
- Info — Performance counters unavailable — Memory uses `GlobalMemoryStatusEx`

The real fixtures do not report UAC disabled, problem devices, denied camera/microphone access, a stopped `hasplms` service, or a virtual-machine verdict, so those items correctly do not appear.

## TDD Evidence

- Helper move test first failed during collection with `ModuleNotFoundError: No module named 'pc_report.noldus_terms'`; it passed after the helper module was created.
- Noldus Summary test first failed during collection because `pc_report.sections.noldus_summary` did not exist; all summary tests passed after implementation.
- The sensor-counter fallback test then failed with a missing `Performance counters unavailable` item; it passed after the built-data fallback was added.
- Fixture-backed integration recursively built real dependencies (including transitive dependencies for Cameras and System Summary), then verified OS/CPU/memory/video specifications, C920 camera, Sentinel dongles, non-admin warning, USB selective suspend, and the fixture's `D:` 0.3% low-space condition.

## Verification

- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q` — passed.
- `python -m pytest -q` — passed; one test skipped and one pre-existing PyPDF2 deprecation warning.
- `python -m ruff check pc_report tests scripts/dev/capture_pc_report_fixtures.py` — all checks passed.
- Repository-wide Python import grep for `pc_report.utils`, `pc_report.collectors`, and relative `utils`/`collectors` imports — no matches.
- `git diff --check` — clean before the feature commit.

## Files Changed

Created:

- `pc_report/noldus_terms.py`
- `pc_report/sections/noldus_summary.py`
- `tests/pc_report/test_noldus_summary.py`

Moved:

- `tests/test_nvc_collector_helpers.py` → `tests/pc_report/test_noldus_terms.py`

Modified:

- `pc_report/__init__.py`
- `pc_report/orchestrator.py`
- `pc_report/section.py`
- `tests/pc_report/test_format.py`
- `tests/test_pc_report_orchestration.py`

Deleted:

- `pc_report/collectors.py`
- `pc_report/utils.py`

## Self-review

- Confirmed branch is `pc-report-siw`; `master` was not touched.
- Confirmed all requested files and public names exist.
- Confirmed both legacy modules are gone.
- Confirmed registry discovery includes `noldus_summary` in the existing NVC order.
- Confirmed render tolerates `None`, empty dictionaries/lists, and partial placeholders.
- Confirmed severity values/classes are `Warning`, `Info`, and `OK`, with the exact all-clear HTML.
- Confirmed collection timing reports elapsed total, slowest three, elevation, and timed-section count.
- Confirmed no Noldus Summary fixture directory or capture was added because the section has no direct queries.
- No unrelated source restructuring or fixture changes were made.

## Concerns

- Dependency notes are intentionally unavailable through `ctx.result`; the sensors-note requirement is therefore represented by the equivalent empty counter fields in built Sensors data, preserving the rule that `collect` may only consume public built results.
- The elapsed plumbing already existed in earlier branch history. The timing commit narrows its type and makes the metadata and section context share one mapping rather than duplicating writes.

## Fix report

- Added the styled `Error` severity and restricted low-disk attention to local/fixed drives, with details naming the percentage and/or absolute threshold that triggered.
- Added threshold, non-local-drive, per-rule negative, and fixture-backed attention assertions.
