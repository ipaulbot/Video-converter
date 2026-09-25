# Task 20 Report: Network Adapters

## Status and commits

Implemented and committed on `pc-report-siw`:

- `e863a92 fix(pc_report): mask network adapter identifiers`
- `5c87e09 feat(pc_report): Network Adapters with IP interface, driver and advanced properties`

## Implementation

Added the `network_adapters` Hardware section with four PowerShell/CIM sources:

- `Get-NetAdapter -IncludeHidden` for visible, virtual, and hidden NDIS adapters.
- `Get-NetAdapterAdvancedProperty` for every advanced property.
- `Get-NetIPInterface` for IPv4/IPv6 MTU, metric, DHCP, and connection state.
- `Win32_NetworkAdapter` for WMI identity and connection details.

`build()` tolerates `None`, nonnumeric values, single-dict PowerShell results, and missing join partners. It joins advanced properties by adapter name and IP/WMI data by interface index. Numeric link speeds use `bitrate_to_mbps`; already formatted values such as `1 Gbps` are preserved. Adapters sort physical first and then case-insensitively by name.

The per-adapter output contains Adapter, Link, and Driver groups plus the complete advanced-property table. The GigE summary has one row per physical adapter and the brief's Adapter, Link Speed, Jumbo Packet, Receive Buffers, Transmit Buffers, Interrupt Moderation, Flow Control, Energy-Efficient Ethernet, Speed and Duplex, and Receive Side Scaling keys. Virtual/hidden adapters and WAN Miniport, Bluetooth PAN, vEthernet, and Npcap adapters are excluded from `gige` while remaining in the per-adapter list.

No generic WMI decode table was added locally: `NetConnectionStatus` uses `decode.NET_CONNECTION_STATUS`. The local DHCP and IP-interface connection maps decode `Get-NetIPInterface` values, not WMI values.

## TDD evidence

1. Added the brief's test module verbatim, then ran `python -m pytest tests/pc_report/test_network_adapters.py -q`; collection failed with the expected `ImportError` because the section did not exist.
2. Added robustness coverage for single-dict inputs, missing joins, deterministic physical-first sorting, numeric link speed conversion, and virtual adapter exclusion from `gige`.
3. Added the network privacy test first. It failed because `PermanentAddress` was not masked.
4. Implemented the section and privacy fixes. Build/privacy tests then passed (`37 passed`), and the final section run passed (`6 passed`).

There were no test/module label or string discrepancies and no test/decode-table disagreements.

## Fixtures and privacy review

Captured from real PowerShell with:

`python scripts/dev/capture_pc_report_fixtures.py --section network_adapters`

Files:

- `adapters.json` — 14,208 bytes, 18 rows.
- `advanced.json` — 12,434 bytes, 67 rows.
- `ip_interfaces.json` — 1,731 bytes, 13 rows.
- `wmi.json` — 6,415 bytes, 16 rows.

Expected nulls:

- `adapters.json`: unavailable duplex/link values on virtual and tunnel adapters; driver and PnP fields absent on three not-present tunnel interfaces.
- `advanced.json`: two unset optional network-address properties have null display/raw values.
- `ip_interfaces.json`: no nulls.
- `wmi.json`: connection, speed, MAC, adapter type, manufacturer, and PnP values are absent where Windows does not expose them for virtual, disconnected, or system adapters.

Every fixture was opened and reviewed. Adapter names present are: Local Area Connection* 9, Noldus Switch, Local Area Connection* 2, masked Bluetooth Network Connection, Ethernet 2, Local Area Connection* 5, Teredo Tunneling Pseudo-Interface, Local Area Connection* 10, Local Area Connection* 6, Local Area Connection* 4, Local Area Connection* 8, Local Area Connection* 3, Local Area Connection* 7, Ethernet (Kernel Debugger), Microsoft IP-HTTPS Platform Interface, Local Area Connection* 1, Wi-Fi, and 6to4 Adapter.

Masked fields:

- `InterfaceGuid` was masked for every adapter.
- Every nonempty `MacAddress`/`MACAddress` was masked, including Noldus Switch, Bluetooth PAN, Ethernet 2, Wi-Fi, both Wi-Fi Direct virtual adapters, and WMI-only miniport addresses.
- Embedded GUIDs in the two Wi-Fi Direct `PnPDeviceID` values were masked.
- The Bluetooth adapter `Name`/WMI `Name` was masked by the existing Bluetooth-name protection.
- Unit coverage verifies `MacAddress`, `PermanentAddress`, and `PhysicalAddress` all use MAC masking; full and embedded GUIDs under `InterfaceGuid`, `DeviceID`, and `PnPDeviceID` are masked.
- The selected queries yielded no IP address, DHCP server, SSID, host name, user name, or domain fields.

Regex and explicit identity scans found no unmasked MAC address, GUID, machine name, user name, domain, IPv4 address, or IPv6 address. Privacy causes were fixed in `pc_report/privacy.py` and covered by tests; no fixture was hand-edited.

## Verification

- Focused PC report suite: `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py tests/test_pc_report_privacy.py -q` — 314 passed.
- Full suite: `python -m pytest -q` — 939 passed, 1 skipped; one existing PyPDF2 deprecation warning.
- Ruff: `python -m ruff check pc_report tests` — all checks passed.
- `git diff --check` — clean before commits.

## Files changed

- `pc_report/privacy.py`
- `pc_report/sections/network_adapters.py`
- `tests/test_pc_report_privacy.py`
- `tests/pc_report/test_network_adapters.py`
- `tests/fixtures/pc_report/network_adapters/adapters.json`
- `tests/fixtures/pc_report/network_adapters/advanced.json`
- `tests/fixtures/pc_report/network_adapters/ip_interfaces.json`
- `tests/fixtures/pc_report/network_adapters/wmi.json`

## Self-review and concerns

- Confirmed the required module, test, and four fixture names exist with no extra task files.
- Confirmed the registry discovers the section and focused orchestration/offline-tolerance tests pass.
- Confirmed hidden/virtual adapters render but cannot enter `gige`.
- Confirmed `gige` contains exactly one row for each physical adapter after deterministic sorting.
- Confirmed all fixtures were reviewed after the final recapture.
- The capture was non-elevated, but none of these four queries is admin-only and capture reported zero notes.
- No unresolved concerns.

## Fix report

- MAC addresses now preserve only the OUI (`XX:XX:XX:**:**:**`), and Bluetooth 12-hex tokens preserve only their first six hex digits (`XXXXXX******`).
- Canonical `Bluetooth Network Connection` names remain readable; personal Bluetooth names remain masked.
- Empty adapter names and missing interface indices cannot create false advanced-property, IP-interface, or WMI joins.
- Hidden adapters are collapsed into one summary table; visible adapters retain grouped details and sorted advanced properties under an explicit heading.
- The fixture-backed Network Adapters render now contains 229 `<tr>` rows (down from 744).
- Fixture recapture changed only `network_adapters/adapters.json`, `network_adapters/wmi.json`, and `_shared/pnp_entities.json`.
- Focused PC report tests, the full test suite, and Ruff all passed.
