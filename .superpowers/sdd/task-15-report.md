# Task 15 Report: Motherboard and BIOS

## Implemented

- Added the `motherboard` section with baseboard identity, processor sockets, physical-memory arrays, expansion-slot usage and widths, onboard devices, and external connectors.
- Added the `bios` section with BIOS and SMBIOS versions, release date, embedded-controller and system BIOS versions, decoded BIOS characteristics, firmware and Secure Boot state, and ACPI tables.
- Added each module's `flatten` helper for System Summary lookups.
- Added the exact tests supplied by the task brief.

## TDD evidence

1. Before adding the modules:
   - `python -m pytest tests/pc_report/test_motherboard.py -q` failed during collection with the expected `ImportError`.
   - `python -m pytest tests/pc_report/test_bios.py -q` failed during collection with the expected `ImportError`.
2. After implementation and fixture capture:
   - `python -m pytest tests/pc_report/test_motherboard.py -q` passed all 4 tests.
   - `python -m pytest tests/pc_report/test_bios.py -q` passed all 3 tests.

There was no test/module label discrepancy and no test/decode-table discrepancy.

## Fixtures and privacy review

Recorded using:

`python scripts/dev/capture_pc_report_fixtures.py --section motherboard bios`

The non-elevated capture completed with no notes and wrote:

- `tests/fixtures/pc_report/motherboard/baseboard.json`
- `tests/fixtures/pc_report/motherboard/sockets.json`
- `tests/fixtures/pc_report/motherboard/memory_array.json`
- `tests/fixtures/pc_report/motherboard/slots.json`
- `tests/fixtures/pc_report/motherboard/onboard.json`
- `tests/fixtures/pc_report/motherboard/connectors.json`
- `tests/fixtures/pc_report/bios/bios.json`
- `tests/fixtures/pc_report/bios/acpi.json`
- `tests/fixtures/pc_report/bios/boot.json`

I opened and reviewed every fixture in full. The baseboard and BIOS serial numbers are masked. No host name, user name, domain, unmasked serial or asset tag, UUID, key, credential, or IP address survived. The onboard and connector fixtures are legitimately `null` on this machine. No privacy-code fix was needed.

## Verification

- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py -q`: passed.
- `python -m pytest -q`: passed with 1 skipped test and one existing PyPDF2 deprecation warning.
- `python -m ruff check pc_report tests`: all checks passed.
- `git diff --check`: passed.

## Files changed

- `pc_report/sections/motherboard.py`
- `pc_report/sections/bios.py`
- `tests/pc_report/test_motherboard.py`
- `tests/pc_report/test_bios.py`
- `tests/fixtures/pc_report/motherboard/baseboard.json`
- `tests/fixtures/pc_report/motherboard/sockets.json`
- `tests/fixtures/pc_report/motherboard/memory_array.json`
- `tests/fixtures/pc_report/motherboard/slots.json`
- `tests/fixtures/pc_report/motherboard/onboard.json`
- `tests/fixtures/pc_report/motherboard/connectors.json`
- `tests/fixtures/pc_report/bios/bios.json`
- `tests/fixtures/pc_report/bios/acpi.json`
- `tests/fixtures/pc_report/bios/boot.json`
- `.superpowers/sdd/task-15-report.md` (task report; repository ignore rules may exclude it from the commit)

## Self-review

- Confirmed the branch is `pc-report-siw` and the working tree was clean before the task.
- Confirmed all required module, test, and fixture names match the brief.
- Confirmed registry discovery recognizes both sections through their existing keys in `registry.ORDER`.
- Confirmed no unrelated or extra implementation files were added.
- Confirmed both renderers tolerate empty and partial payloads.
- Confirmed fixture-backed collection finds every named query without invoking real commands.
- Confirmed Motherboard and BIOS both expose the required `groups` payload and `flatten` helper.

## Concerns

None.

## Fix report

- Changed `mask_string` so values shorter than 12 characters with the default `keep=4` are fully masked; longer values retain the existing two-character prefix and four-character suffix shape.
- Preserved well-known built-in service accounts under `StartName` while continuing to mask domain or custom service accounts.
- Moved the motherboard decode tables into `pc_report/decode.py` and updated the motherboard section to reference them there.
- TDD evidence: the two targeted privacy tests failed before the implementation and passed afterward together with the motherboard tests.
- Verification: the focused PC report suite passed, the full test suite passed with 1 skipped test and the existing PyPDF2 deprecation warning, and `python -m ruff check pc_report tests` passed.
- Fixture privacy: `bios/bios.json` and `services/services.json` changed; the seven-character BIOS serial is now fully masked, the baseboard serial remains more than half hidden, built-in service accounts are readable, and the short-partial-mask scan found no matches.
- Files changed: `.superpowers/sdd/task-15-report.md`, `pc_report/privacy.py`, `pc_report/decode.py`, `pc_report/sections/motherboard.py`, `tests/test_pc_report_privacy.py`, `tests/fixtures/pc_report/bios/bios.json`, and `tests/fixtures/pc_report/services/services.json`.
