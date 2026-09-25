# Task 25 report: Cameras

## Implemented

- Added the `cameras` Hardware section with `after=("installed_programs",)`.
- Added PnP camera filtering, DirectShow video/audio source enumeration, dxdiag camera details, Windows Camera Frame Server state, webcam/microphone consent, GenICam environment paths, and installed Basler/GigE transport-layer detection.
- Added helper contracts `camera_names(data)`, `frame_server_enabled(data)`, and `denied(data)`.
- Added empty/partial rendering tolerance and tolerance for missing shared data, missing/partial installed-program results, missing consent registry keys, and dict/list dxdiag camera shapes through the existing foundation helpers.
- Used the brief's supplied module and tests. The only code discrepancy is the equivalent Python 3.12 spelling `datetime.UTC` instead of the brief's `datetime.timezone.utc`, required by Ruff UP017.
- The brief defined no generic decode table, so no table was added to `pc_report/decode.py`. No removed `SCOPES` constant was introduced.

## TDD evidence

1. Created `tests/pc_report/test_cameras.py` from the brief before production code.
2. Ran `python -m pytest tests/pc_report/test_cameras.py -q`.
3. Observed the expected collection failure: `ImportError: cannot import name 'cameras' from 'pc_report.sections'`.
4. Added `pc_report/sections/cameras.py`.
5. Captured real fixtures.
6. Re-ran the focused test: 7 tests passed.
7. After the Ruff-only `datetime.UTC` change, re-ran the focused test: 7 tests passed.

No test/module label disagreement or test/decode-table disagreement was found.

## Fixtures

Written by `python scripts/dev/capture_pc_report_fixtures.py --section cameras`:

- `tests/fixtures/pc_report/cameras/directshow_capture.json` — 6,179 bytes; list; 0 null values.
- `tests/fixtures/pc_report/cameras/frame_server.json` — 142 bytes; dict; 2 null values. Both Frame Server registry mode values were absent, which means Windows default behavior.
- `tests/fixtures/pc_report/cameras/consent.json` — 12,905 bytes; list; 44 null values. Nulls are expected where global or packaged-app consent entries have no last-use timestamps.

Capture also rewrote `_shared/pnp_entities.json` and `_shared/dxdiag.json`. Per the task instruction, both were restored with `git checkout -- tests/fixtures/pc_report/_shared/`; they are not Task 25 fixture changes. The restored shared fixtures were still reviewed:

- `_shared/pnp_entities.json` — 138,581 bytes; 118 null values.
- `_shared/dxdiag.json` — 292,186 bytes; 0 null values.

## Privacy review

All five camera-related fixture inputs were opened/reviewed. Automated scans found no current host name, user name, user domain, or DNS domain; no unredacted `C:\Users\<name>` paths; and no actual IPv4 addresses. Version-like dotted strings were the only IPv4-regex matches. Camera `DeviceID`/`PNPDeviceID` values were masked by the existing `redact_instance_id` behavior where applicable, and dxdiag camera hardware IDs were masked by the `Hardware ID` key token. No privacy cause required a change to `pc_report/privacy.py`, and no fixture was hand-edited.

Camera names after masking:

- `HD Pro Webcam C920`
- `Integrated Webcam`
- `Canon TR8500 series`

Consent application entries after masking, in rendered-data ordering:

Camera:

- `C:\Program Files (x86)\Logitech\LogiTune\LogiTune.exe`
- `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `C:\Program Files\Noldus\EthoVision XT 17\EthoVision.exe`
- `C:\Program Files\Noldus\EthoVision XT 18\EthoVision.exe`
- `C:\Program Files\Noldus\FaceReader 10\FaceReader.exe`
- `C:\Program Files\Noldus\FaceReader 9.1\FaceReader.exe`
- `C:\Program Files\Noldus\FaceReader 9\FaceReader.exe`
- `C:\Program Files\Noldus\MediaRecorder 6\MediaRecorder.exe`
- `C:\Program Files\obs-studio\bin\64bit\obs64.exe`
- `C:\Program Files\SplitCam\10\splitcam.exe`
- `C:\Users\<redacted>\AppData\Local\CiscoSparkLauncher\CiscoCollabHost.exe`
- `C:\Users\<redacted>\AppData\Local\Microsoft\Teams\current\Teams.exe`
- `C:\Users\<redacted>\AppData\Roaming\Zoom\bin\Zoom.exe`
- `C:\Users\<redacted>\Desktop\Python Projects\NVC 4\ffmpeg.exe`
- `Claude_pzs8sxrjxfjjc`
- `D:\Python Projects\NVC 4\ffmpeg.exe`
- `Microsoft.MixedReality.Portal_8wekyb3d8bbwe`
- `Microsoft.Office.OneNote_8wekyb3d8bbwe`
- `Microsoft.SkypeApp_kzf8qxf38zg5c`
- `Microsoft.Win32WebViewHost_cw5n1h2txyewy`
- `Microsoft.WindowsCamera_8wekyb3d8bbwe`
- `Microsoft.WindowsFeedbackHub_8wekyb3d8bbwe`
- `Microsoft.XboxGamingOverlay_8wekyb3d8bbwe`
- `MSTeams_8wekyb3d8bbwe`
- `NonPackaged`

Microphone:

- `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- `C:\Program Files (x86)\Noldus\UltraVox XT 3.2\UltraVox3.exe`
- `C:\Program Files (x86)\TeamViewer\TeamViewer.exe`
- `C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe`
- `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE`
- `C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE`
- `C:\Program Files\Noldus\FaceReader 10\FaceReader.exe`
- `C:\Program Files\Noldus\FaceReader 9.1\FaceReader.exe`
- `C:\Program Files\Noldus\FaceReader 9\FaceReader.exe`
- `C:\Program Files\Noldus\MediaRecorder 6\MediaRecorder.exe`
- `C:\Program Files\Noldus\Viso Recorder 12\VisoRecorder.exe`
- `C:\Program Files\obs-studio\bin\64bit\obs64.exe`
- `C:\Program Files\SplitCam\10\splitcam.exe`
- `C:\Program Files\TeamViewer\TeamViewer.exe`
- `C:\Users\<redacted>\AppData\Local\CiscoSparkLauncher\CiscoCollabHost.exe`
- `C:\Users\<redacted>\AppData\Local\Microsoft\Teams\current\Teams.exe`
- `C:\Users\<redacted>\AppData\Local\Perplexity\Comet\Application\comet.exe`
- `C:\Users\<redacted>\AppData\Local\Programs\cursor\Cursor.exe`
- `C:\Users\<redacted>\AppData\Roaming\Zoom\bin\Zoom.exe`
- `Claude_pzs8sxrjxfjjc`
- `Microsoft.MicrosoftOfficeHub_8wekyb3d8bbwe`
- `Microsoft.MixedReality.Portal_8wekyb3d8bbwe`
- `Microsoft.Office.OneNote_8wekyb3d8bbwe`
- `Microsoft.SkypeApp_kzf8qxf38zg5c`
- `Microsoft.Win32WebViewHost_cw5n1h2txyewy`
- `Microsoft.Windows.SecureAssessmentBrowser_cw5n1h2txyewy`
- `Microsoft.WindowsCamera_8wekyb3d8bbwe`
- `Microsoft.WindowsFeedbackHub_8wekyb3d8bbwe`
- `Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe`
- `Microsoft.XboxGamingOverlay_8wekyb3d8bbwe`
- `MSTeams_8wekyb3d8bbwe`
- `NonPackaged`
- `windows.immersivecontrolpanel_cw5n1h2txyewy`

## Verification

- `python -m pytest tests/pc_report/test_cameras.py -q` — passed, 7 tests.
- `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q` — passed.
- `python -m ruff check pc_report tests` — all checks passed.
- `python -m pytest -q` — passed; 1 skipped; one pre-existing PyPDF2 deprecation warning.

## Files changed

- `pc_report/sections/cameras.py`
- `tests/pc_report/test_cameras.py`
- `tests/fixtures/pc_report/cameras/directshow_capture.json`
- `tests/fixtures/pc_report/cameras/frame_server.json`
- `tests/fixtures/pc_report/cameras/consent.json`
- `.superpowers/sdd/task-25-report.md`

## Self-review

- Confirmed branch `pc-report-siw`; `master` was not touched.
- Confirmed the section key, title, group, timeout, dependency, fixture query names, test filename, and three fixture filenames match the brief.
- Confirmed no unrelated source files or shared fixtures remain modified.
- Confirmed no documentation files were created; this required task report is the only report artifact.
- Confirmed no extra decode table or `SCOPES` constant was added.
- Confirmed helper contracts return the required types and empty/partial rendering is covered.

## Concerns

None.

## Fix report

- Fixture-backed render: 75 `<tr>` elements.
- `camera_names`: `['HD Pro Webcam C920', 'Integrated Webcam', 'HD Pro Webcam C920']`.
- Consent fixture user paths use the redacted `C:#Users#<redacted>#...` form.

## Fix report 2

- `is_camera` rejects USB audio companion interfaces (`usbaudio`/`usbaudio2`, `audio` in description, audio PnP classes) before the name heuristic; `Camera` and `usbvideo` rows remain included.
- `camera_names` de-duplicates by name while preserving order.
- Fixture-backed `camera_names`: `['HD Pro Webcam C920', 'Integrated Webcam']`.
