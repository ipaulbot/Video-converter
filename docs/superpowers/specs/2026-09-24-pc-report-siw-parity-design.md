# PC Report: SIW-Depth Redesign

## Goal

Bring the NVC PC Report to the depth of a SIW (System Information for Windows)
HTML export, field for field where built-in Windows sources allow, while
keeping a Noldus-specific summary at the top that highlights what support
engineers need. Restructure `pc_report/` so that adding a field is a local
edit to one section module with its own test.

The reference export is `SIW_WDGS-BH0020_20260922_103917.html`: 37 sections in
three groups (Software, Hardware, Network), key/value tables with human
labels, a grouped contents list and "Top" links.

## Decisions Already Made

| Question | Decision |
|---|---|
| Audience | Both: full SIW parity everywhere, plus a curated Noldus summary first |
| Data sources | Built-in Windows only: WMI/CIM, PowerShell Storage/Net cmdlets, registry, performance counters, `dxdiag /x`, kernel32 calls from Python. No bundled helpers, no vendor tools |
| Privacy | Keep the single redaction toggle, default on; extend the mask list to the new identifying fields |
| Layout | SIW-like: grouped contents, flat sections, Top links, minimal styling, no JavaScript |
| Time budget | Depth over speed. A few minutes is acceptable if progress keeps moving |
| Architecture | Section registry: one module per section with `collect()` and `render()` |
| Admin-only fields | Show "Requires administrator"; Report Health states whether the run was elevated. No UAC prompt in this version |

## Current State

`pc_report/collectors.py` (750 lines) holds 25 collector functions, each a
handful of `run_ps_json` calls. `pc_report/render_html.py` is one 650-line
`render()` function that knows every field of every section. The Noldus
summary re-runs four collectors that also run on their own. Section names
already match SIW; depth does not: Operating System has 7 fields against
SIW's 46, System Summary 3 against 50, CPU 3 against ~80, Storage 3 against 23
per disk. Sensors is effectively empty. There is no Monitors, USB or Cameras
section.

Tests (`tests/test_pc_report_*.py`, `tests/test_nvc_collector_helpers.py`)
cover the orchestrator, privacy, the dialog and a few pure helpers. No test
covers what a section collects or renders.

## Architecture

### Module layout

```
pc_report/
  __init__.py
  registry.py          # SECTIONS (ordered); groups; by_key(); the one place order lives
  section.py           # Section dataclass, RunContext, kv_table/list_table, REQUIRES_ADMIN
  orchestrator.py      # run_all(options, progress_cb) -> (meta, results, errors)  [unchanged signature]
  render_html.py       # page shell: header, grouped contents, group banners, CSS
  render_json.py       # unchanged
  privacy.py           # redact_payload with the extended token list
  ps.py                # run_ps_json (unchanged), cim(), reg_props(), SharedSource: dxdiag(), pnp_entities()
  format.py            # bytes_human, mbps, cim_date, norm_time, uptime, percent, duration
  utils.py             # re-exports bytes_human / bitrate_to_mbps from format.py for one release
  decode.py            # WMI enum tables: chassis, memory type, form factor, PnP error codes, slot usage, ...
  sections/
    __init__.py
    noldus_summary.py                                             # group NVC
    operating_system.py  installed_updates.py  licenses.py
    system_directories.py  system_files.py  installed_programs.py
    security.py  accessibility.py  environment.py  regional_settings.py
    processes.py  services.py  drivers.py  autorun.py  codecs.py
    mmc_snapins.py                                                # group Software
    system_summary.py  motherboard.py  bios.py  cpu.py  memory.py
    sensors.py  devices.py  pci.py  system_slots.py
    network_adapters.py  video.py  monitors.py  sound.py
    storage_devices.py  logical_disks.py  ports.py  usb.py
    printers.py  virtual_machine.py  cameras.py                   # group Hardware
    network_information.py  shares.py  network_connections.py     # group Network
```

`collectors.py` is deleted once every function has moved.

### The Section interface

Each module in `sections/` exposes one object:

```python
SECTION = Section(
    key="operating_system",     # results-dict key and options on/off key
    title="Operating System",
    group="Software",           # "NVC" | "Software" | "Hardware" | "Network"
    collect=collect,            # (ctx: RunContext) -> {"data": ..., "notes": [str, ...]}
    render=render,              # (data, ctx: RenderContext) -> str  (HTML fragment)
    timeout=30,                 # seconds; PowerShell budget for this section
    default_on=True,
    after=(),                   # keys this section reads from ctx.results
)
```

Registry invariants, enforced by a test: unique keys; known group names;
callable `collect` and `render`; `render` returns without raising for `{}`,
`None`, and `{"status": "partial", "error": "..."}`; `after` names existing
keys and contains no cycles.

Existing result keys are preserved. `hardware` splits into `system_summary`,
`motherboard`, `bios`, `cpu`, `memory`, `video`, `sound`, `storage_devices`,
`logical_disks`; `network` splits into `network_adapters` and `shares`. The
dialog's option keys `hardware` and `network` are aliases that switch the
whole split group on or off, so `pc_report_dialog.py` keeps working.

### RunContext

Created once per `run_all` and passed to every `collect`:

- `is_admin`: `ctypes.windll.shell32.IsUserAnAdmin()` evaluated once.
- `results`: read-only view of completed sections, for `after` consumers.
- `shared`: memoised shared sources (`ctx.shared.dxdiag()`,
  `ctx.shared.pnp_entities()`). First caller pays; a failure is recorded once
  and each later caller receives `None` plus the error string so it can note
  the affected fields as unavailable.
- `options`: the caller's options dict (for `services_limit`,
  `processes_limit`).

### Orchestration

`run_all` filters `registry.SECTIONS` by `options.get(key, default_on)`,
honouring the `hardware`/`network` aliases. Sections with empty `after` are
submitted to the existing 6-thread pool first; a section with `after` is
submitted as soon as every dependency has completed (successfully or as a
partial). Progress is still reported once per section with
`(title, completed, total)`, so the dialog's progress text now shows the
section title rather than its key.

A section that raises becomes `{"status": "partial", "error": str(exc)}` in
`results` and an entry in `errors`, exactly as today. `meta` gains
`elevated: bool` and `elapsed_by_section: {key: seconds}`.

### Per-query notes

`collect` returns `{"data": ..., "notes": [...]}`. Every `run_ps_json` that
returns `None` with an error, or that times out, appends a note such as
`"SoftwareLicensingProduct: timed out after 30 s"`. Admin-only queries check
`ctx.is_admin` first and, when false, put the sentinel `REQUIRES_ADMIN` in the
data and a note `"BitLocker: requires administrator"` without spawning
PowerShell. The renderer prints notes in an italic block under the section;
Report Health totals them.

### PowerShell helpers (`ps.py`)

`run_ps_json(script, timeout)` is unchanged, since tests patch it. Added:

- `cim(class_name, props=None, namespace=None, where=None, timeout=30)`:
  builds the `Get-CimInstance ... | Select-Object ...` script.
- `reg_props(path, timeout=15)`: returns the value names and data under a key.
- `SharedSource` for `dxdiag /whql:off /x <tmp>.xml` (90 s, parsed with
  `xml.etree`) and for `Win32_PnPEntity` with the properties every consumer
  needs.

Default section timeout 30 s; 90 s for dxdiag, Windows Update history,
drivers and scheduled tasks.

### Python-side collection

Two items are collected in Python rather than PowerShell because it is
simpler and instant: CPU instruction sets via
`kernel32.IsProcessorFeaturePresent` (SSE3, SSSE3, SSE4.1, SSE4.2, AVX, AVX2,
AVX-512F, and the older SSE/SSE2/MMX/3DNow flags), and `is_admin`.

## Field Catalogue

Items marked (admin) render "Requires administrator" when unelevated. Items
marked * are masked when redaction is on.

### NVC group

**Report Health** (first): rendered by the page shell in `render_html.py`
from `meta` and `results`, not a section module, since it has nothing to
collect. Shows redaction on/off, elevated yes/no, sections with notes, empty
sections, partial sections, total collection time, three slowest sections.

**Noldus Summary**: reads `ctx.results`; runs after every section it uses.

- Warnings list, each with the section it came from: problem devices;
  volumes under 10 % free; pending reboot; Defender real-time protection off;
  UAC off; virtual machine detected; active power plan not High performance;
  USB selective suspend enabled; Windows camera Frame Server enabled;
  camera or microphone consent denied; `hasplms` service present but not
  running; report ran unelevated.
- System specifications (manufacturer, model, OS, CPU, GPU, RAM, last boot,
  uptime) from the hardware sections.
- Noldus software inventory, Noldus drivers, Noldus filters/codecs (registry
  plus the existing file scan under Noldus/Basler/Daheng roots), Noldus
  environment variables. The existing `NVC_RELATED_TERMS` filter and helper
  functions move here.
- Cameras as DirectShow sees them (from Cameras).
- HASP/Sentinel dongles and `hasplms` state (from USB and Services).
- .NET Framework versions (registry `NDP`) and installed Visual C++
  redistributables (from Installed Programs).
- GigE-relevant NIC settings: jumbo packet, receive buffers per physical
  adapter (from Network Adapters).
- Collection time per section.

### Software group

| Section | Sources | Fields |
|---|---|---|
| Operating System | `Win32_OperatingSystem`, `Get-ComputerInfo`, registry `CurrentVersion`, `SoftwareLicensingProduct`, `ntoskrnl.exe` version, policy/registry keys | Name, product name, edition ID, SKU, DisplayVersion, build + UBR, architecture, install date, install time, last boot, uptime, OS root, boot device, system device, start options, kernel version, BuildLab, BuildLabEx, registered owner*/organisation, language, MUI languages, computer name*/description, activation status, licence status and channel, grace period remaining, partial product key*, UAC enabled, Secure Boot, Long Paths enabled, hardware DEP available, fast startup, hibernation, Automatic Updates policy, Insider ring, System Restore enabled, pending reboot |
| Installed Updates | `Get-HotFix`, `Microsoft.Update.Session` history | Hotfixes (ID, description, installed on, by); update history (date, title, KB, operation, result) grouped by month |
| Licenses | registry `ProductId`, `SoftwareLicensingService`, `SoftwareLicensingProduct` | Windows product ID*, OA3 key*, per licensed product: name, channel, partial key*, status |
| System Directories | `[Environment]::GetFolderPath` for every `SpecialFolder`, registry Shell Folders | Name, path (user paths redacted) |
| System Files | file system | hosts, lmhosts.sam, networks, protocol, services, system.ini, win.ini: path, size, modified; hosts entry count |
| Installed Programs | Uninstall keys (HKLM, WOW6432Node, HKCU), `Get-Package`, `Get-AppxPackage` | Name, version, publisher, install date, install location, estimated size, install source, architecture, scope |
| Security | `root\SecurityCenter2`, `Get-MpComputerStatus`, `Get-NetFirewallProfile`, policy registry, `Win32_DeviceGuard`, `Get-Tpm` (admin), `Get-BitLockerVolume` (admin), `auditpol` (admin), `Get-LocalGroupMember`, `WindowsPrincipal` | AV/antispyware/firewall products with state decoded (enabled, up to date); Defender: real-time, tamper, engine/platform/signature versions and dates, last quick/full scan; firewall per profile: enabled, default inbound/outbound, logging; UAC: EnableLUA, prompt behaviour decoded; Device Guard (existing); DEP; Secure Boot; TPM present/ready/version; BitLocker per volume; current user is administrator; local Administrators members*; audit policy categories |
| Accessibility | `HKCU\Control Panel\Accessibility\*` | Every subkey's `Flags` decoded to available/enabled/hotkey plus timing values, matching SIW's rows |
| Environment | `[Environment]::GetEnvironmentVariables(scope)` | Name, value, scope (Machine/User/Process) |
| Regional Settings | `Get-Culture`, `Get-UICulture`, `Get-WinSystemLocale`, `Get-WinHomeLocation`, `Get-TimeZone`, `Get-WinUserLanguageList`, registry `Nls\CodePage` | Culture, UI culture, system locale, home location, time zone id/display/UTC offset/DST names and bias, short/long date, time patterns, first day of week, calendar, number/currency/list separators and symbols, native digits, day and month names, ACP/OEMCP, input languages and keyboard layouts |
| Running Processes | `Win32_Process`, `Get-Process` (best effort for version info), `GetOwner` (admin) | Name, PID, parent PID, threads, handles, working set, priority, start time, CPU time, executable path, command line, description, company, file version, owner* |
| NT Services | `Win32_Service`, `Get-Service` | Name, display name, description, state, status, start mode, delayed start, service type, account*, PID, path |
| Drivers | `Win32_PnPSignedDriver`, `Win32_SystemDriver` | Device, class, version, date, provider, manufacturer, signed, signer, INF, device ID; system drivers: state, start mode, type, path |
| Autorun | Run/RunOnce keys, Startup folders, Winlogon `Shell`/`Userinit`, `Get-ScheduledTask` with logon/boot triggers | Location, name, command, target version, target company, status (exists/missing) |
| Codecs | `Drivers32`, DirectShow category keys (video compressors, audio compressors, general filters, video capture sources, audio capture sources), Media Foundation transforms, file version info | Name, category, CLSID, file, file version, description |
| MMC Snap-Ins | `HKLM\SOFTWARE\Microsoft\MMC\SnapIns` and CLSID lookup | Name, GUID, description, file name |

### Hardware group

| Section | Sources | Fields |
|---|---|---|
| System Summary | `Win32_ComputerSystem`, `Win32_ComputerSystemProduct`, `Win32_SystemEnclosure`, `Win32_BIOS`, `Win32_OperatingSystem`, `Win32_PageFileUsage`, `Win32_PageFileSetting`, `Win32_WinSAT`, `powercfg /getactivescheme`, registry `PEFirmwareType`, `SecureBoot\State` | Manufacturer, family, product name, model, version, UUID*, serial*, asset tag*, SKU, chassis type, PC system type, firmware type, Secure Boot, computer name*/description, domain/workgroup, domain role, current user*, CPU one-line, total/free memory and load %, virtual memory, pagefile: auto-managed, name, allocated, in use, peak; per-drive total/free; WinSAT scores if present; active power plan; last boot, uptime |
| Motherboard | `Win32_BaseBoard`, `Win32_Processor.SocketDesignation`, `Win32_PhysicalMemoryArray`, `Win32_SystemSlot` counts, `Win32_OnBoardDevice`, `Win32_PortConnector` | Manufacturer, product, version, serial*; CPU socket; memory array: max capacity, slots, error correction; slot counts by type; onboard devices; external connectors |
| BIOS | `Win32_BIOS`, registry `HKLM\HARDWARE\ACPI` | Vendor, name, version, SMBIOS version, release date, EC version, firmware type, Secure Boot, every `BiosCharacteristics` value decoded, ACPI tables present |
| CPU | `Win32_Processor`, `Win32_CacheMemory`, registry `CentralProcessor\0`, `IsProcessorFeaturePresent`, `Get-Counter '\Processor Information(*)\% Processor Performance'` | Name, vendor, description, family/model/stepping, ProcessorId, socket, architecture, address/data width, sockets/cores/enabled cores/logical processors, max/current/external clock, L1/L2/L3 cache with associativity, virtualization enabled, VMX, SLAT, microcode revision, load %, per-core performance % sample, instruction sets, status, voltage |
| Memory | `Win32_PhysicalMemoryArray`, `Win32_PhysicalMemory`, `Win32_OperatingSystem` | Array: max capacity, slots, populated, ECC; per module: device locator, bank, capacity, speed, configured speed, configured/min/max voltage, data width, total width (ECC inferred), form factor, memory type (DDR generation), type detail, manufacturer, part number, serial*; OS: total, free, load %, committed, virtual total/free. States that SPD/XMP timings need a vendor driver |
| Sensors | `MSAcpi_ThermalZoneTemperature`, `Win32_Fan`, `Win32_TemperatureProbe`, `Win32_VoltageProbe`, `Win32_Battery`, `Get-Counter` (Processor Information, Memory, PhysicalDisk, GPU Engine, GPU Adapter Memory, Network Interface) | Thermal zones (°C), fans, probes, battery: status, charge %, estimated runtime; CPU load, per-core performance %, memory load, disk active % per disk, GPU 3D utilisation and dedicated memory per adapter, NIC bytes/s sample. States that temperatures need vendor tools |
| Devices | shared `pnp_entities()` | Problem devices first with error code decoded; then grouped by class: name, manufacturer, status, driver service, device ID; class counts |
| PCI | shared `pnp_entities()` filtered to `PCI\`, `Get-PnpDeviceProperty` for location and driver version, embedded vendor-ID table | Windows name, vendor name, VEN/DEV, SUBSYS, class, bus/device/function, driver version |
| System Slots | `Win32_SystemSlot` | Designation, type, data width, current usage, connector type, hot plug, bus/device/function |
| Network Adapters | `Win32_NetworkAdapter` (physical), `Get-NetAdapter`, `Get-NetIPInterface`, `Get-NetAdapterAdvancedProperty` | Name, description, MAC*, status, link speed, media type, physical media, MTU, driver version/date/provider/file, PNP ID; advanced: jumbo packet, receive/transmit buffers, interrupt moderation, flow control, energy-efficient Ethernet |
| Video | `Win32_VideoController`, registry `qwMemorySize`, shared `dxdiag()` | Name, status, adapter RAM (corrected), shared memory, chip type, DAC, video processor, PCI ID, current mode, refresh rate, bits per pixel, driver version/date/model (WDDM)/INF, feature levels, DirectX version |
| Monitors (new) | `root\wmi WmiMonitorID`, `WmiMonitorBasicDisplayParams`, `Win32_DesktopMonitor`, `dxdiag()`, `Screen.AllScreens` | Manufacturer, model, serial*, year/week, diagonal size, native mode, current mode, output type, position, primary, scaling % |
| Sound | `Win32_SoundDevice`, `Get-PnpDevice -Class AudioEndpoint`, `dxdiag()` | Devices: name, manufacturer, status, driver version/date, default playback; endpoints: render and capture with state; default capture device |
| Storage Devices | `Get-PhysicalDisk`, `Get-Disk`, `Win32_DiskDrive`, `Get-Partition`, `MSStorageDriver_FailurePredictStatus`, `Get-StorageReliabilityCounter` (admin), `Win32_CDROMDrive` | Per disk: friendly name, model, manufacturer, media type, bus type, size, health, operational status, serial*, firmware, partition style, boot/system, sector sizes, spindle speed, SMART predict-failure, power-on hours, temperature, wear, read/write errors; partitions: number, letter, size, type, GPT type; optical drives |
| Logical Disks | `Win32_LogicalDisk`, `Get-Volume`, `Get-Partition`/`Get-Disk` for bus, `Get-BitLockerVolume` (admin) | Letter, label, drive type, file system, total, used, free, % free (highlight under 10 %), volume serial*, health, allocation unit, bus type, network path for mapped drives, compressed, BitLocker status |
| Ports | `Win32_PortConnector`, `Win32_SerialPort`, `SERIALCOMM`, `Win32_ParallelPort` | External connectors (designation, type); serial: name, device, max baud, provider type, status; parallel |
| USB (new) | `Win32_USBController`, `Win32_USBControllerDevice`, `Win32_USBHub`, `Get-PnpDeviceProperty DEVPKEY_Device_Parent`, `powercfg /q` selective suspend | Controllers: name, USB version, status; devices: name, VID/PID, class, manufacturer, driver service, status, parent; selective suspend AC/DC |
| Printers | `Win32_Printer`, Spooler service | Name, driver, port, default, shared, network, status, location, offline; spooler state |
| Virtual Machine | `Win32_ComputerSystem.HypervisorPresent`, manufacturer/model markers, services `vmms`/`vmcompute`/`LxssManager`/`CmService`, guest driver markers | Hypervisor present, detected vendor, host indicators, guest indicators, Hyper-V/WSL/Sandbox services |
| Cameras (new) | shared `pnp_entities()` (Camera/Image/Media classes), DirectShow capture-source category keys, `dxdiag()` VideoCaptureDevices, registry `Windows Media Foundation\Platform\EnableFrameServerMode`, `CapabilityAccessManager\ConsentStore\webcam` and `microphone`, environment `GENICAM_GENTL*_PATH`, Basler transport layers from programs | PnP cameras: name, class, status, problem code, driver; DirectShow video and audio capture sources: friendly name, CLSID, device path; dxdiag detail: manufacturer, hardware ID, driver, version, date; Frame Server mode; camera and microphone consent (global, per app, last used start/stop; "in use now" when stop is zero); GenICam producer paths; Basler/GigE transport layers |

### Network group

| Section | Sources | Fields |
|---|---|---|
| Network Information | `Win32_ComputerSystem`, environment, `Get-NetAdapter`, `Get-NetIPConfiguration`, `Win32_NetworkAdapterConfiguration`, `Get-NetConnectionProfile`, `Get-NetRoute`, registry proxy, `netsh winhttp show proxy`, `netsh wlan show interfaces` | Computer name*, description, domain*/workgroup, domain role, logon server*, DNS suffix; per interface: name, description, type, MAC*, MTU, status, Tx/Rx speed, IPv4* with prefix, IPv6*, gateway*, DHCP enabled/server*/lease obtained/expires, DNS servers*, DNS suffix, WINS, NetBIOS setting, metric, connection profile; user and WinHTTP proxy; default routes; Wi-Fi: SSID*, signal, radio type, channel |
| Shares | `Get-SmbShare`, `Get-SmbShareAccess`, `Get-SmbClientConfiguration`, `Get-SmbServerConfiguration` (admin) | Name, path, description, type, state, current users, caching, encryption, permissions (account, right); client: insecure guest logons, signing; server: SMB1/SMB2 enabled |
| Network Connections | `Win32_MappedLogicalDisk`, `Get-SmbMapping`, `Get-VpnConnection`, `Get-NetTCPConnection`, `Get-NetUDPEndpoint`, `Get-Process` | Mapped drives: local, remote path, status, provider, persistent, user*; VPN: name, server*, status; TCP: local*/remote* address and port, state, owning process; UDP: local*, port, process; listening ports table |

IP addresses are masked to the first two octets when redaction is on.

## Rendering

### Page

Header: NVC logo, machine name*, generation time, NVC version,
"Elevated: yes/no". Contents block in four columns, NVC, Software, Hardware,
Network, each listing its sections as anchor links, built from `registry`
groups. Sections follow in registry order; the first section of each group is
preceded by a group banner. Every section has a title row with a "Top" link.
Flat page, no JavaScript, a single `<style>` block, alternating row shading,
row hover, NVC's teal palette.

### Helpers (`section.py`)

- `kv_table(rows)`: `rows` is a list of `(label, value)`. A `(label, None)`
  pair renders as a shaded sub-heading row. Labels are human strings chosen by
  the section, never raw WMI property names.
- `list_table(columns, rows)`: `columns` is a list of `(key, label)`; missing
  keys render blank; a cell over 512 characters is truncated behind
  `<details>`.
- Both escape all content. `REQUIRES_ADMIN` renders as
  "Requires administrator" in the `.warn` class.
- Notes render as an italic block beneath the section's tables.
- Empty data renders `<em>No data</em>`, which Report Health counts.

Three highlight classes only: `.warn` (amber), `.bad` (red), `.ok` (green).
Formatting always goes through `format.py`.

### JSON

`render_json` is unchanged in shape. Because sections now return
`{"data", "notes"}`, the JSON carries notes, and `meta` carries
`elapsed_by_section` and `elevated`.

### Size

A full report is expected to be 1.5–3 MB, dominated by processes, drivers,
devices and update history. The per-section on/off options remain for
trimming.

## Redaction

`privacy.redact_payload` keeps its signature. Key tokens added to the
mask-string list: `uuid`, `assettag`, `asset_tag`, `owner`, `registeredowner`,
`username`, `user_name`, `startname`, `domain`, `logonserver`, `ssid`,
`volumeserial`, `productkey`, `partialproductkey`, `hardwareid`. Keys
containing `ipv4`, `ipv6`, `ipaddress`, `gateway`, `dnsserver`, `dhcpserver`,
`remoteaddress`, `localaddress`, `serveraddress` mask each address to its
first two octets (IPv4) or first two hextets (IPv6). MAC and user-path masking
is unchanged. Fixtures for tests are captured through the same function.

## Testing

### Fixtures

`scripts/dev/capture_pc_report_fixtures.py` runs every query on the current
machine and writes `tests/fixtures/pc_report/<section>/<query>.json`, passing
each payload through `redact_payload` first so the fixtures are safe to
commit. Tests patch `ps.run_ps_json` (and the shared sources) with a
dispatcher that serves fixtures keyed on the script text.

### Per-section tests (`tests/pc_report/test_<section>.py`)

- `collect(ctx)` on fixtures produces the expected keys and decoded values
  (chassis 3 → "Desktop", `SMBIOSMemoryType` 34 → "DDR5", PnP error 28 →
  "Drivers not installed", DirectShow CLSID → friendly name).
- `render(data, ctx)` contains the expected labels and values; on `{}`,
  `None` and the partial placeholder it returns without raising.
- Admin-only queries return `REQUIRES_ADMIN` and do not call `run_ps_json`
  when `ctx.is_admin` is false.

### Registry, orchestrator, rendering

`test_pc_report_orchestration.py` is updated so its collector list is "every
`SECTION` in the registry" and its counts read `len(registry.SECTIONS)`. New
tests: registry invariants; `after` ordering (the summary runs after its
inputs); shared-source memoisation (dxdiag invoked once for Video, Monitors,
Sound, Cameras); shared-source failure degrading to notes; `hardware` and
`network` option aliases; `meta.elevated` and `elapsed_by_section` present.

Rendering tests: the contents block lists the four groups in order; every
section anchor resolves; the new key families are masked; the page parses
with `html.parser` without errors.

### Live smoke test

`tests/pc_report/test_live_report.py`, skipped unless `NVC_PC_REPORT_LIVE=1`,
generates a full report on the real machine and asserts no section is partial
and the run finishes within five minutes.

## Migration

1. Add `registry.py`, `section.py`, `ps.py` additions, `format.py`,
   `decode.py`, and the fixture capture script.
2. Move each existing collector into its section module, splitting `hardware`
   and `network`, keeping result keys.
3. Rewrite `render_html.py` as the page shell over the registry.
4. Repoint `orchestrator.py` at the registry; update its tests.
5. Deepen sections to the catalogue, one section per commit, each with
   fixtures and tests.
6. Add Monitors, USB, Cameras.
7. Rework the Noldus Summary to read `ctx.results` and emit warnings.
8. Delete `collectors.py`; move `test_nvc_collector_helpers.py` to
   `tests/pc_report/test_noldus_summary.py`. Keep `utils.py` re-exports for one
   release.
9. Run the live smoke test on this machine and on a lab PC with Noldus
   software and a Basler camera; compare against the SIW export section by
   section.

## Out of Scope

Recorded in `docs/BACKLOG.md`: UAC-elevated collection for the admin-only
fields; Quick/Full report profiles; PDF export; comparing two reports;
redesign of the PC Report tab; per-core temperatures and SPD/XMP data (need a
vendor driver).
