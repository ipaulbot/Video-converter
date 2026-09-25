# Fix wave B report

Branch: `pc-report-siw`

## Items

1. `run_ps_json` now preserves bounded stderr for empty and valid JSON output; `run_text` reports its effective timeout. Tests cover empty output, data plus stderr, and note propagation. No drift.
2. Native command output is captured as bytes and decoded with the Windows console output code page, with UTF-8 fallback and replacement errors. A cp850 regression test covers accented output. No drift.
3. Cancellation now flows from `_PCReportWorker` through `run_all` and `RunContext`; cancelled queries do not spawn, unstarted sections become partial/cancelled, widget shutdown cancels and waits, and main-window shutdown drains the widget. Tests cover pre-cancelled orchestration, idle/running shutdown, and the worker event. The optional Cancel button was omitted as allowed by the brief.
4. The dead `PCReportDialog` was deleted. The worker passes its complete options mapping through; `updates` and `programs` aliases were added to the registry and tested. No drift.
5. Numeric formatters use shared `decode.to_int` / `decode.to_float` coercion while preserving their documented fallbacks. Existing formatter tests pass. No drift.
6. File-wide Ruff suppressions were removed, `_h2` escapes anchors, and the registry rejects a `report_health` section key by test. No drift.
7. Security Center packed state/signature bytes are decoded as specified, including Snoozed for `0x061100`; all state/signature combinations are table-tested. No drift.
8. Device Guard service/property/VBS tables use the Microsoft mappings and include unknown-value coverage. No drift.
9. Installed programs, processes, drivers, and codec tables have deterministic caps, Shown/Total summaries, and truncation notes. Boundary and note tests cover cap+1 rows. No drift.
10. Safe Mode values decode to Minimal, Network, or Other (n), with tests. No drift.
11. Firewall, VBS, code-integrity, encryption, and protection mappings live in `decode.py`; BitLocker reuses the shared protection table. No drift.
12. USB controller protocol uses the CIM enum, while generation is explicitly derived from controller names. Tests cover protocol values, unknowns, and name patterns. Value 46 is reported as the obsolete CIM USB 3.0 value, consistent with Windows semantics.
13. Logical-disk Used and Free % stay blank for invalid capacities, including free greater than size. Tested. No drift.
14. Failed pagefile-settings queries report Not available; successful empty results report Automatic (system managed). Tested. No drift.
15. `flatten_groups` is shared by all duplicate section helpers; section-local `flatten` aliases remain for existing imports/tests. No drift.

## Verification

- Full suite: exit code 0.
- Required Ruff command: exit code 0.
- Fixture leak grep: no matches.
- Live report: passed in 90.0 s; redacted Security rendered decoded states (`Snoozed`, `Off`) and current Device Guard property labels.
- Three slowest sections: Codecs 87.3 s; Processes 53.1 s; Logical Disks 46.7 s.
- Live HTML: `%TEMP%\nvc_live_pc_report.html`.

## Commits

- `343d9c1` `fix(pc_report): harden execution and Windows state decoding`
- `cb41dac` `fix(pc_report): cap large software inventories`
- `cb7690b` `fix(pc_report): centralize grouped row flattening`
- `cf82af5` `fix(pc_report): align decoder regression expectations`
- `6f4eda8` `fix(pc_report): cover option aliases and truncation notes`
