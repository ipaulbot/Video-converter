# Task 13 Report: Drivers and Autorun

## Implemented

- Added the Drivers section with signed PnP driver collection, device-class grouping, normalized dates/signature status, summary counts, and system-driver details.
- Added the Autorun section with Run/RunOnce and startup-folder entries, StartupApproved enabled-state handling, non-Microsoft scheduled tasks, formatted run times, hexadecimal result codes, and summary counts.
- Added the exact fixture-backed build/render tests from the brief for both sections.
- Added generic Windows account-SID redaction after captured scheduled-task names exposed a live user SID.

## TDD Evidence

1. Created `tests/pc_report/test_drivers.py` and ran it before implementation. Collection failed with the expected `ImportError` because `pc_report.sections.drivers` did not exist.
2. Created `tests/pc_report/test_autorun.py` and ran it before implementation. Collection failed with the expected `ImportError` because `pc_report.sections.autorun` did not exist.
3. Implemented the two section modules from the brief and captured their real PowerShell fixtures.
4. Fixture review found a user account SID embedded in scheduled-task names. Added `test_redact_payload_scrubs_account_sids_in_string_values`; it failed before the privacy fix and passed after it.
5. Regenerated all four fixtures after the privacy fix.
6. Focused Drivers, Autorun, and privacy tests passed (28 tests).

## Fixtures and Privacy Review

Written:

- `tests/fixtures/pc_report/drivers/signed_drivers.json`
- `tests/fixtures/pc_report/drivers/system_drivers.json`
- `tests/fixtures/pc_report/autorun/run_entries.json`
- `tests/fixtures/pc_report/autorun/scheduled_tasks.json`

All four files were opened and reviewed. An environment-aware scan found no surviving computer name, user name, domain name, account SID, or real user-profile name. User paths use `<redacted>`, scheduled-task account fields are masked, and task-name SIDs use `<redacted-sid>`. No credentials, keys, or tokens survived. No actual IP address beyond two octets survived; IP-shaped findings in driver data were version numbers. Matches for “serial” were generic driver/device names, not serial values. `Noldus` vendor references were retained as allowed.

## Verification

- `python -m pytest tests/pc_report/test_drivers.py -q` — passed.
- `python -m pytest tests/pc_report/test_autorun.py -q` — passed.
- `python -m pytest tests/test_pc_report_privacy.py -q` — 22 passed.
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py -q` — passed.
- `python -m ruff check pc_report tests` — all checks passed.
- `python -m pytest -q` — passed with one existing skipped test and one PyPDF2 deprecation warning.
- `git diff --check` — passed.

## Files Changed

- `pc_report/sections/drivers.py`
- `pc_report/sections/autorun.py`
- `pc_report/privacy.py`
- `tests/pc_report/test_drivers.py`
- `tests/pc_report/test_autorun.py`
- `tests/test_pc_report_privacy.py`
- `tests/fixtures/pc_report/drivers/signed_drivers.json`
- `tests/fixtures/pc_report/drivers/system_drivers.json`
- `tests/fixtures/pc_report/autorun/run_entries.json`
- `tests/fixtures/pc_report/autorun/scheduled_tasks.json`
- `.superpowers/sdd/task-13-report.md`

## Self-review

- Confirmed branch `pc-report-siw`; `master` was not touched.
- Confirmed section keys, module names, test names, fixture directories, and query names are exactly `drivers`/`autorun`, `signed_drivers`/`system_drivers`, and `run_entries`/`scheduled_tasks`.
- Confirmed each fixture directory contains exactly its two expected JSON files.
- Confirmed registry discovery recognizes both keys already present in `registry.ORDER`.
- Confirmed no unrelated files were changed and no extra implementation or documentation files were created.
- The brief's module labels and test expectations did not conflict.

## Concerns

None.

## Fix report

### Changes

- Scheduled tasks are now excluded when their path starts with `\Microsoft\` or their non-empty author contains `Microsoft`, case-insensitively. The same rules are enforced in both collection and `build`; no other vendor is special-cased.
- StartupApproved state now uses hive, kind, and entry name together. Collection reads `Run`, `Run32`, and `StartupFolder` from both HKLM and HKCU; 32-bit Run and common/user startup entries resolve against their corresponding kind and hive. Missing approval records still default to enabled.
- SID redaction now masks only account SIDs (`S-1-5-21-...` and `S-1-12-1-...`), preserving the account-SID prefix while removing private sub-authorities. Well-known SIDs remain readable.
- Regression coverage was added in `tests/pc_report/test_autorun.py` and `tests/test_pc_report_privacy.py`. The focused tests were observed failing before implementation and passing afterward.

### Verification

- `python scripts/dev/capture_pc_report_fixtures.py --section autorun` — exit 0; `autorun: 1.1 s, 0 note(s)`.
- `python -m pytest tests/pc_report tests/test_pc_report_privacy.py -q` — exit 0; 192 tests passed.
- `python -m ruff check pc_report tests` — exit 0; `All checks passed!`.

### Fixture check

Opened and reviewed both autorun fixtures after recapture. No real host name, user name, domain, account-SID sub-authorities, or profile name survived; user paths contain `<redacted>`, and allowed identity placeholders are used. No actual IP address beyond two octets survived. The sole four-octet-shaped value, `131.0.2.0`, is the Google Drive File Stream product-version directory, not an IP address.
