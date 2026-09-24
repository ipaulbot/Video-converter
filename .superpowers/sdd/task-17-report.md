# Task 17 Report: Memory

## Implemented

- Added the `memory` hardware section with physical-array capacity and slot summary, per-module SMBIOS details, operating-system memory figures, and live commit/cache/pool figures.
- Added resilient numeric formatting for capacities, speeds, voltage, OS memory values, and performance byte counters. Missing, `None`, and nonnumeric values render blank instead of raising or displaying zero.
- Accepted either a single PowerShell dictionary or a list for arrays, modules, OS data, and performance data through `first_dict` and `rows_of`.
- Preferred non-zero `SMBIOSMemoryType` over `MemoryType`, with fallback to `MemoryType`.
- Kept all generic SMBIOS decode tables in `pc_report/decode.py`. The required tables already existed, so no decode table was added; `memory.py` references `decode.MEMORY_TYPES`, `decode.FORM_FACTORS`, `decode.TYPE_DETAIL`, and `decode.ERROR_CORRECTION`.
- Confirmed `Serial Number` is masked by the existing `serial` privacy token while `Part Number` remains visible as a public SKU. No privacy implementation change was needed.

## TDD Evidence

1. Created `tests/pc_report/test_memory.py` before the production module.
2. Ran `python -m pytest tests/pc_report/test_memory.py -q`; collection failed with the expected `ImportError` because `pc_report.sections.memory` did not exist.
3. Added `pc_report/sections/memory.py`, captured fixtures, and reran the focused test: 9 tests passed.
4. Added robustness coverage for missing/nonnumeric values, single-dictionary module output, `TypeDetail=None`, SMBIOS type preference/fallback, and serial-versus-part-number privacy.

## Fixtures and Privacy Review

Written under `tests/fixtures/pc_report/memory/`:

- `array.json`
- `modules.json`
- `os.json`
- `perf.json`

All four files were opened and reviewed. No host name, user name, domain, IP address, or unmasked serial survived. Both module serials are `********`; part numbers remain in clear. `perf.json` is `null` because that WMI query returned no value on this machine, so it contains no `Path` value; no host-bearing performance path survived.

## Verification

- `python -m pytest tests/pc_report/test_memory.py -q`: passed (9 tests).
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q`: passed.
- `python -m pytest -q`: passed; one existing skipped test and one existing PyPDF2 deprecation warning.
- `python -m ruff check pc_report tests`: all checks passed.
- `git diff --check`: passed.

## Files Changed

- Added `pc_report/sections/memory.py`
- Added `tests/pc_report/test_memory.py`
- Added `tests/fixtures/pc_report/memory/array.json`
- Added `tests/fixtures/pc_report/memory/modules.json`
- Added `tests/fixtures/pc_report/memory/os.json`
- Added `tests/fixtures/pc_report/memory/perf.json`
- Added `.superpowers/sdd/task-17-report.md`

## Self-review

- Required module, test, and exactly four fixture names exist.
- Section key/title/group are `memory` / `Memory` / `Hardware`, matching the registry order.
- Query names match fixture names: `array`, `modules`, `os`, and `perf`.
- Empty and partial payload rendering is covered.
- No unrelated source files were changed.
- No test/module label discrepancy or test/decode-table discrepancy was found.

## Concerns

- The captured performance fixture is `null`, reflecting the real query result on this machine. Synthetic tests cover populated, missing, and nonnumeric performance values.
- The full suite emits the pre-existing PyPDF2 deprecation warning noted above.

## Fix report

- Added a non-raising `GlobalMemoryStatusEx` probe and live-value fallback order: performance counters, Windows memory status, then `Win32_OperatingSystem`.
- Added `Commit Limit` and `Live Source` rows, whole-percent memory load, and deterministic fixture coverage for the missing performance-counter condition and collection note.
- TDD red run: the focused memory tests failed on the missing probe, status argument, fallback values, source rows, and collection note before production changes.
- Verification: focused memory tests passed; PC report regression tests passed; the full suite passed with one skip and the pre-existing PyPDF2 warning; Ruff passed.
