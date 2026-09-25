# Task 21 Report: Video, Monitors and Sound

## Status

Implemented and committed on `pc-report-siw`:

- `661c0d4 fix(pc_report): mask dxdiag machine identifiers`
- `5459591 feat(pc_report): Video with corrected memory and DirectX detail; Monitors from EDID; Sound endpoints`

## Implementation

- Added the Video section with deterministic adapter ordering, registry `HardwareInformation.qwMemorySize` preference, an explicit per-adapter RAM source, WMI capped-memory display, PCI decoding, current mode, driver detail, DirectX detail, and `video.names(data)`.
- Added the Monitors section with deterministic monitor/screen ordering, EDID identity, safe decoding of zero-terminated UInt16 arrays, physical diagonal, dxdiag mode/output association, and desktop layout.
- Added the Sound section with deterministic device/endpoint ordering, signed-driver details, playback/capture direction, DirectX default endpoints, and tolerant single-object/list handling.
- All three collectors consume the shared `dxdiag` source, note `dxdiag: unavailable` when it is `None`, and still build/render.
- Moved the generic PnP monitor vendor decode table to `decode.PNP_MONITOR_VENDORS` and referenced it from the monitor section.
- Added `machineid` to `privacy.SENSITIVE_TOKENS`; fixture capture therefore masks dxdiag `MachineId` at the cause rather than hand-editing the fixture.

The brief's monitor module expression rounded a 60 x 34 cm diagonal to `27.2"`, while the supplied test requires `27.1"`. Per the task rule, the implementation follows the test and truncates to one decimal. No decode-table/test discrepancy was found.

## TDD Evidence

1. Added the three supplied test modules verbatim.
2. Ran each before its module existed; all failed during collection with the expected `ImportError`.
3. Added the modules and ran build tests. Video and Sound passed; Monitor exposed the documented `27.2"` versus `27.1"` brief/test discrepancy.
4. Adjusted the monitor calculation to the test expectation; all six build tests passed.
5. Added `test_machine_id_is_masked_as_an_identifier`; the privacy suite failed because `MachineId` was unchanged.
6. Added the privacy token; all 35 privacy tests passed.
7. After fixture capture, all 12 focused Video/Monitors/Sound tests passed.

## Fixtures and Privacy Review

Capture command:

`python scripts/dev/capture_pc_report_fixtures.py --section video monitors sound`

The non-elevated capture completed without notes: Video 12.3 s, Monitors 0.8 s, Sound 2.4 s. None of these section queries requires elevation.

| Fixture | Bytes | Nulls / reason |
| --- | ---: | --- |
| `_shared/dxdiag.json` | 292,209 | 0 |
| `video/controllers.json` | 3,209 | 9: two DisplayLink rows do not report RAM, DAC type, or video processor; DisplayLink MI_01, Intel, and NVIDIA do not report minimum refresh rate |
| `video/registry.json` | 1,033 | 3: registry `qwMemorySize` is absent for two DisplayLink entries and Intel; NVIDIA reports it |
| `monitors/wmi_monitors.json` | 206 | 0 |
| `monitors/params.json` | 141 | 0 |
| `monitors/screens.json` | 134 | 0 |
| `sound/devices.json` | 1,593 | 0 |
| `sound/endpoints.json` | 3,210 | 0 |
| `sound/drivers.json` | 1,982 | 0 |

Every fixture was parsed and reviewed. Exact host, user, and domain searches returned no hits; no raw identifying GUIDs or IP addresses were found. Monitor serial, sound endpoint GUIDs, portable sound PnP identifiers, and personal audio endpoint names are masked. No `C:\Users\...` path survived. DirectShow application/filter entries and LogicalDisks were inspected; they contain product/device information but no host/user identity or unmasked device serial.

Required dxdiag grep:

- `MachineName`: one occurrence, value `PC-NAME` from identity scrubbing.
- `MachineId`: one occurrence, masked as `{B********************************0C0}` by `redact_payload`.
- `UserName`: no occurrences.
- `UserDNSDomain`: no occurrences.

No fixture was hand-edited.

## Verification

- `python -m pytest tests/pc_report/test_video.py tests/pc_report/test_monitors.py tests/pc_report/test_sound.py -q`: 12 passed.
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q`: passed (329 tests).
- `python -m pytest -q`: passed to 100%, with one existing skipped test and one existing PyPDF2 deprecation warning.
- `python -m ruff check pc_report tests`: all checks passed.
- `git diff --check`: passed.
- All fixture JSON parsed successfully and `pc_report` compiled successfully.

## Files Changed

- `pc_report/decode.py`
- `pc_report/privacy.py`
- `pc_report/sections/video.py`
- `pc_report/sections/monitors.py`
- `pc_report/sections/sound.py`
- `tests/test_pc_report_privacy.py`
- `tests/pc_report/test_video.py`
- `tests/pc_report/test_monitors.py`
- `tests/pc_report/test_sound.py`
- `tests/fixtures/pc_report/_shared/dxdiag.json`
- `tests/fixtures/pc_report/video/controllers.json`
- `tests/fixtures/pc_report/video/registry.json`
- `tests/fixtures/pc_report/monitors/wmi_monitors.json`
- `tests/fixtures/pc_report/monitors/params.json`
- `tests/fixtures/pc_report/monitors/screens.json`
- `tests/fixtures/pc_report/sound/devices.json`
- `tests/fixtures/pc_report/sound/endpoints.json`
- `tests/fixtures/pc_report/sound/drivers.json`

## Self-review

- Confirmed the branch is `pc-report-siw`; `master` was not touched.
- Confirmed all required modules, tests, and exactly the requested fixture names exist.
- Confirmed section keys and query names match the fixture paths.
- Confirmed dict/list and null/nonnumeric tolerance, shared-source failure notes, EDID decoding, corrected RAM source reporting, deterministic ordering, and empty rendering.
- Confirmed the registry discovers all three sections and the offline-tolerance/invariant tests pass.
- No unrelated source files or extra fixtures were added.

## Concerns

- The real NVIDIA registry value is exactly 4 GiB on this machine, so the captured fixture demonstrates registry preference/source reporting but not a greater-than-4-GiB card; the supplied unit test covers 12 GiB.
- The capture was non-elevated, but none of the nine required section queries is administrator-only.

## Fix report

- Added `_flag` handling for dxdiag boolean values (`True`, `1`, `"1"`, `"true"`, and `"yes"`), and read real sound data from the nested `DirectSound` block. Fixture-backed rendering now includes non-blank default playback and capture devices.
- Preserved endpoint `InstanceId` as the payload key while retaining `Instance` as the rendered column label, so endpoint GUIDs pass through shared instance-ID redaction.
- Added key-scoped personal-device-name redaction for descriptions, names, friendly/device/instance/product names, and captions. Possessive owners and iPhone/iPad/Galaxy owner prefixes become `***`; unrelated descriptions and possessive text under other keys remain unchanged.
- Recaptured sound, video, monitors, and shared dxdiag fixtures. Only `_shared/dxdiag.json` and `sound/endpoints.json` changed; the required privacy search found no unmasked personal-name or possessive matches.
- Verification passed: focused PC-report suite, complete pytest suite (one existing skip and one PyPDF2 deprecation warning), Ruff, and `git diff --check`.
