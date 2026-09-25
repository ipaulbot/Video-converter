# Task 22 Report — Storage Devices and Logical Disks

## Implementation

- Added `pc_report/sections/storage_devices.py` with physical disk identity and geometry, deterministic disk/partition ordering, SMART status, administrator-gated reliability counters, GPT partition decoding, optical drives, summary data, and HTML rendering.
- Added `pc_report/sections/logical_disks.py` with the exact System Summary row keys (`Drive`, `Label`, `Type`, `File System`, `Total`, `Used`, `Free`, `Free %`, and the remaining brief fields), volume health/allocation data, backing-disk joins, low-space warnings, administrator-gated BitLocker status, deterministic drive ordering, and HTML rendering.
- Kept numeric conversion tolerant of null/nonnumeric values, supported single-dict PowerShell results through `rows_of`, ignored null join keys, and guarded free-space percentages for zero or missing sizes.
- Added the generic GPT partition and BitLocker protection tables to `pc_report/decode.py` and referenced them as `decode.GPT_PARTITION_TYPES` and `decode.BITLOCKER_PROTECTION`; no decode table remains local to either section.
- Did not import the legacy logical-disk normalizer from `collectors.py`.
- Added a note when the SMART WMI query returns null, since this can occur unelevated.

## Privacy changes

- Added masking for `UniqueId`, disk `Guid`, and `KeyProtectorId`; `RecoveryPassword` was already covered by the existing password token.
- Added `InstanceName` device-path redaction so serial-bearing `SCSI\`/`USBSTOR\` tails are masked.
- Added UNC network-path host redaction. Host names become `<redacted>` and IPv4 hosts retain only the first two octets.
- Physical/Get-Disk serials and logical volume serials continue to use the existing serial masking.
- Added regression tests for all of the above. Fixtures were regenerated through the capture script after fixing the causes; none were hand-edited.
- Volume labels are intentionally retained by design and can be personal. The captured labels were blank or `Data`.

## TDD evidence

1. Added the two brief-supplied section test modules first.
2. Initial section run failed during collection with the expected `ImportError` for both missing section modules.
3. Added privacy tests before privacy implementation:
   - `UniqueId` and SMART `InstanceName` tests failed before masking support.
   - The disk `Guid` test failed before GUID masking support.
   - UNC host/IP tests failed before network-path redaction support.
4. Implemented the minimum section and privacy behavior, then recorded fixtures.
5. Focused section result: `10 passed`.
6. Privacy result: all `43` privacy tests passed.
7. PC-report/orchestration/privacy integration command passed.

No brief test/module string discrepancy was found. The generic tables were moved from the brief's module snippets to `decode.py` as required; their values were unchanged.

## Captured fixtures and privacy review

Unelevated capture was performed with:

`python scripts/dev/capture_pc_report_fixtures.py --section storage_devices logical_disks`

| Fixture | Bytes | Review |
| --- | ---: | --- |
| `storage_devices/physical.json` | 1030 | 2 disks; serials and unique IDs masked |
| `storage_devices/disks.json` | 991 | 2 disks; serials and disk GUIDs masked |
| `storage_devices/partitions.json` | 1434 | 5 partitions; only standard GPT type GUIDs present |
| `storage_devices/smart.json` | 4 | `null`; WMI provider returned no data unelevated and the section records a note |
| `storage_devices/optical.json` | 4 | `null`; no optical drive was reported |
| `logical_disks/logical.json` | 1179 | 4 drives; volume serials masked and network IPs reduced to two octets |
| `logical_disks/volumes.json` | 519 | 2 local volumes |
| `logical_disks/partitions.json` | 289 | 2 backing-disk mappings |

`reliability.json` and `bitlocker.json` were not written because `SectionContext.admin_query` returns `REQUIRES_ADMIN` without invoking or recording an unelevated query. This matches the standard fixture support and the brief's “when elevated” qualification. Rendering still shows “Requires administrator,” and both behaviors have unit coverage.

Every captured file was opened and reviewed. No host name, user name, domain, unmasked disk/volume serial or unique ID, BitLocker identifier, or IP beyond two octets survived. Standard GPT partition type GUIDs are schema constants, not machine identifiers.

## Verification

- `python -m pytest tests/pc_report/test_storage_devices.py tests/pc_report/test_logical_disks.py -q` — passed (`10 passed`).
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q` — passed.
- `python -m pytest -q` — passed with one existing skipped test and one PyPDF2 deprecation warning.
- `python -m ruff check pc_report tests` — passed.
- `git diff --check` — passed.

## Files changed

- `pc_report/decode.py`
- `pc_report/privacy.py`
- `pc_report/sections/storage_devices.py`
- `pc_report/sections/logical_disks.py`
- `tests/test_pc_report_privacy.py`
- `tests/pc_report/test_storage_devices.py`
- `tests/pc_report/test_logical_disks.py`
- Eight fixture JSON files listed above

## Self-review

- Confirmed branch `pc-report-siw`; `master` was not touched.
- Confirmed section filenames, keys, titles, groups, query names, and fixture names match the brief.
- Confirmed exact logical row keys required by System Summary.
- Confirmed no `collectors.py` dependency and no unrelated restructuring.
- Confirmed deterministic disk, partition, and drive ordering.
- Confirmed admin markers render through the foundation's `REQUIRES_ADMIN` path.
- Confirmed the commit contains only Task 22 implementation, tests, privacy fixes, and fixtures.

## Commit

`8cc41ad feat(pc_report): Storage Devices with partitions/SMART/reliability; Logical Disks with usage and BitLocker`

## Concerns

- SMART and optical fixtures are null on this machine, so their fixture-backed HTML has no live rows; synthetic build tests cover SMART and optical rendering behavior.
- Reliability and BitLocker live payloads could not be captured unelevated. Their requires-administrator behavior is covered by tests.
- Volume labels are intentionally not redacted and may be personal on other machines.

## Fix report

- Replaced the first-model-word SMART join with normalized device identity matching between `Get-Disk.Path` and the WMI `InstanceName`. The fallback now runs only when `Path` is missing and accepts exactly one model-token match.
- Added regression tests first and confirmed four expected failures: missing `_device_key`, incorrect same-vendor SMART assignment, ambiguous fallback selection, and unsorted optical drives.
- Added `Path` to the disk query, `_device_key` normalization coverage for the supplied path pair, separate SMART results for same-vendor disks, ambiguous fallback coverage, and optical ordering by `Drive` then `Name`.
- Extended the existing unelevated reliability and BitLocker tests to assert that rendered HTML contains `Requires administrator`.
- Recaptured `storage_devices` through real PowerShell. Only `storage_devices/disks.json` changed; its two paths are generic SCSI identities with no serial-bearing USB segment.
- Verification passed: focused section tests, PC-report/orchestration/privacy tests, the full test suite (one existing skip and one PyPDF2 deprecation warning), Ruff, and `git diff --check`.
