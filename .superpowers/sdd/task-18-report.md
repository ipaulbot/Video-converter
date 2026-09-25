# Task 18 Report: Sensors

## Implementation

- Added the `sensors` hardware section with ACPI thermal zones, fans, temperature/voltage probes, battery details, and a one-second performance-counter sample.
- Added defensive numeric conversion throughout. Missing, negative, and nonnumeric readings render blank rather than raising or displaying fabricated zero values.
- Added explicit collection notes when ACPI thermal zones or all performance counters are unavailable.
- Moved the generic WMI battery status and battery chemistry tables into `pc_report.decode` as `BATTERY_STATUS` and `BATTERY_CHEMISTRY`; the section references those shared tables.
- Kept the labels and strings from the supplied tests. No test/module or test/decode discrepancy was found.

## TDD Evidence

1. Created the supplied test module first.
2. Initial focused run failed during collection with the expected `ImportError` because `pc_report.sections.sensors` did not exist.
3. After implementing the module, the focused run had five build/render tests passing and only the fixture test failing because all five fixture files were absent.
4. Captured the real fixtures, then reran the focused test: all 6 tests passed.

## Fixtures and Privacy Review

Files written under `tests/fixtures/pc_report/sensors/`:

- `thermal.json`: `null`; this unelevated machine did not return `MSAcpi_ThermalZoneTemperature`, and collection emitted the expected availability note.
- `fans.json`: one `Win32_Fan` object; desired speed was null.
- `probes.json`: six temperature probes with null readings and no voltage probes.
- `battery.json`: one battery object.
- `counters.json`: partial live results. CPU utility, GPU engines, and GPU adapter memory were returned; Memory, PhysicalDisk, and Network Interface counter sets returned no samples on this machine.

Every fixture was opened and reviewed. An automated scan also found no current computer name, user name, domain, logon server, or IPv4 address. Counter paths contain the required `\\PC-NAME\` replacement. No host-identifying thermal zone or serial was present. The battery query intentionally does not collect `DeviceID` or any serial field, so no `deviceid` privacy token was added and `privacy.py` required no change.

## Verification

- `python -m pytest tests/pc_report/test_sensors.py -q`: passed.
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q`: passed.
- `python -m pytest -q`: passed with one expected skip and one existing PyPDF2 deprecation warning.
- `python -m ruff check pc_report tests`: passed.
- `git diff --check`: passed.

## Files Changed

- `pc_report/decode.py`
- `pc_report/sections/sensors.py`
- `tests/pc_report/test_sensors.py`
- `tests/fixtures/pc_report/sensors/thermal.json`
- `tests/fixtures/pc_report/sensors/fans.json`
- `tests/fixtures/pc_report/sensors/probes.json`
- `tests/fixtures/pc_report/sensors/battery.json`
- `tests/fixtures/pc_report/sensors/counters.json`
- `.superpowers/sdd/task-18-report.md`

## Self-review

- Confirmed the branch is `pc-report-siw`.
- Confirmed section key/title/group and all required fixture names match the brief.
- Confirmed only Task 18 files are changed and no extra documentation was created.
- Confirmed empty inputs render without raising.
- Confirmed the exact supplied test labels are used.
- Confirmed the shared decode tables are not duplicated locally.

## Concerns

- The machine returned only a subset of requested performance-counter families, so the recorded fixture cannot exercise live Memory, PhysicalDisk, or Network Interface output. The supplied in-memory test covers those transformations.
- ACPI thermal-zone behavior is covered by the supplied in-memory test because the real unelevated query returned null.

## Fix report

- Changed GPU collection to sample every engine type, aggregate utilization by display engine name, clamp totals at 100%, omit inactive non-3D engines, and render engines in the required order.
- Added ordered missing-counter-family detection and a partial-availability collection note. The refreshed fixture reports Memory, PhysicalDisk, and Network Interface as unavailable.
- Rejected converted ACPI temperatures outside -40.0 through 150.0 °C.
- TDD red phase produced the expected eight focused failures before implementation; the added unknown-engine display test also failed before its minimal fix. The focused suite now has 13 passing tests.
- Recaptured and reopened all five sensors fixtures. All 669 counter paths use `\\PC-NAME\`; scans found no machine name, user, domain, logon server, serial/device identifier, or related privacy field.
- Fixture-backed rendering contains 24 `<tr>` rows. The PC-report regression suite, full test suite, and Ruff checks all pass; the full suite retains one expected skip and the existing PyPDF2 deprecation warning.
