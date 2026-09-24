# Task 16 Report: CPU

## Implementation

- Added the `cpu` section with processor identity, topology and clocks, cache details, virtualization state, microcode revisions, sampled processor utility, per-core performance, and processor feature probing.
- Kept `build()` pure and called `probe_features()` only from `collect()`.
- Used the existing shared decode tables in `pc_report/decode.py`: `CPU_ARCHITECTURE`, `CACHE_LEVEL`, `CACHE_ASSOCIATIVITY`, `CACHE_TYPE`, and `CPU_STATUS`. The brief did not define any new generic WMI/SMBIOS value table, so no decode table was added.
- Added `processorid` to `SENSITIVE_TOKENS` because `ProcessorId` is a hardware identifier, with a regression test proving it is masked.
- No module/test label discrepancies and no test/decode-table discrepancies were found.

## TDD Evidence

1. Added `tests/pc_report/test_cpu.py` from the brief and ran `python -m pytest tests/pc_report/test_cpu.py -q`.
   - Expected RED: collection failed with `ImportError: cannot import name 'cpu' from 'pc_report.sections'`.
2. Added the processor-ID privacy regression and ran `python -m pytest tests/test_pc_report_privacy.py -q`.
   - Expected RED: `ProcessorId` remained `BFEBFBFF000906A2`.
3. Implemented `pc_report/sections/cpu.py` and added the privacy token.
4. Before fixture capture, the CPU build tests passed and the sole failure was the expected four missing fixture files.
5. After fixture capture, the CPU section tests passed: 7 passed.
6. The privacy suite passed: 25 passed.

## Fixtures and Privacy Review

Captured with:

`python scripts/dev/capture_pc_report_fixtures.py --section cpu`

Files written:

- `tests/fixtures/pc_report/cpu/processors.json`
- `tests/fixtures/pc_report/cpu/caches.json`
- `tests/fixtures/pc_report/cpu/registry.json`
- `tests/fixtures/pc_report/cpu/performance.json`

Every file was opened and reviewed. No host name, user name, domain, unmasked hardware identifier, or IP address survived. `ProcessorId` is masked as `BF**********06A3`. Every performance `Path` uses `\\PC-NAME\`, confirming identity scrubbing of the computer name. Capture was non-elevated, but the CPU section has no administrator-only query and capture reported zero notes.

## Verification

- Focused CPU test: 7 passed.
- Focused PC report suite: `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q` passed (260 tests).
- Full suite: `python -m pytest -q` passed (885 passed, 1 skipped).
- Ruff: `python -m ruff check pc_report tests` passed with no findings.
- `git diff --check` passed.
- The full suite emitted one pre-existing `PyPDF2` deprecation warning.

## Files Changed

- `pc_report/sections/cpu.py`
- `pc_report/privacy.py`
- `tests/pc_report/test_cpu.py`
- `tests/test_pc_report_privacy.py`
- `tests/fixtures/pc_report/cpu/processors.json`
- `tests/fixtures/pc_report/cpu/caches.json`
- `tests/fixtures/pc_report/cpu/registry.json`
- `tests/fixtures/pc_report/cpu/performance.json`
- `.superpowers/sdd/task-16-report.md`

## Self-review

- Confirmed branch `pc-report-siw`; `master` was not touched.
- Confirmed the section key and fixture directory are both `cpu`.
- Confirmed all four required fixture names exist and no extra CPU fixture was created.
- Confirmed the supplied test and module interfaces match the brief.
- Confirmed `build()` has no feature probing or platform dependency.
- Confirmed `probe_features()` returns a dictionary and handles unsupported platforms/API calls without propagating ordinary API errors.
- Confirmed registry discovery includes the new `cpu` section and orchestration/offline tests pass.
- Confirmed only task files and the required report are changed.

## Concerns

- No task-blocking concerns.
- The complete suite has one unrelated `PyPDF2` deprecation warning.

## Fix report

### What changed

- Hardened `microcode()` so only exact eight-byte lists are decoded and invalid list/scalar values return blank.
- Added `_pct()` and used it for processor utility and per-core performance so missing or nonnumeric samples render blank.
- Accepted singleton performance dictionaries through `rows_of()` and excluded case-insensitive `_total` and `*,_total` aggregate instances from per-core rows.
- Added regression coverage for all review findings, including the committed fixture's `0,_total` row.

### Test evidence

- RED: focused CPU tests failed for invalid microcode fallback, missing performance values, aggregate filtering, and fixture rendering.
- GREEN: `python -m pytest tests/pc_report/test_cpu.py -q` passed.
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q` passed.
- `python -m pytest -q` passed with one pre-existing `PyPDF2` deprecation warning.
- `python -m ruff check pc_report tests` passed.

### Files changed

- `pc_report/sections/cpu.py`
- `tests/pc_report/test_cpu.py`
- `.superpowers/sdd/task-16-report.md`
