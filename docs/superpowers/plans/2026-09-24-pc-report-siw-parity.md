# PC Report SIW-Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `pc_report/` as a registry of self-contained section modules and deepen every section to the field catalogue in `docs/superpowers/specs/2026-09-24-pc-report-siw-parity-design.md`, so the NVC PC Report matches a SIW export.

**Architecture:** Each section is one module under `pc_report/sections/` exposing a `SECTION` object with `collect(ctx)` and `render(data, ctx)`. `registry.py` orders them into NVC / Software / Hardware / Network groups; `orchestrator.py` runs them on a thread pool with dependency phases, shared memoised sources (dxdiag, PnP dump) and per-query notes; `render_html.py` is only the page shell. Every query is named, so tests replay recorded fixtures instead of running PowerShell.

**Tech Stack:** Python 3.12, PowerShell 5.1 (WMI/CIM, Storage and Net cmdlets, registry), `dxdiag /x`, `ctypes` for kernel32/shell32, `unittest` via `python -m pytest`, `ruff`.

## Global Constraints

- Built-in Windows sources only: WMI/CIM, PowerShell cmdlets, registry, performance counters, `dxdiag`, `netsh`, `powercfg`, kernel32. No new binaries or Python dependencies.
- Redaction is one toggle (`options["redact"]`, default `True`) applied to the payload before either renderer.
- Admin-only queries never spawn PowerShell when unelevated; they return `REQUIRES_ADMIN` and add a note.
- Result keys that exist today keep their names: `operating_system`, `installed_updates`, `installed_programs`, `security`, `services`, `processes`, `licenses`, `environment`, `printers`, `accessibility`, `drivers`, `codecs`, `sensors`, `devices`, `pci`, `ports`, `virtual_machine`, `network_connections`. Renamed: `noldus_nvc_report → noldus_summary`, `network_info → network_information`, `autoruns → autorun`, `snapins → mmc_snapins`, `slots → system_slots`; old names are accepted as option aliases. `hardware` and `network` are option aliases for their split groups.
- `run_all(options, progress_cb)` returns `(meta, results, errors)`; a section that raises becomes `{"status": "partial", "error": str}`; progress is reported once per section.
- Human labels in every rendered table; never raw WMI property names. Formatting goes through `pc_report/format.py`.
- Three highlight classes only: `.warn`, `.bad`, `.ok`.
- Every `render` must return without raising for `{}`, `None` and the partial placeholder.
- No test spawns PowerShell or `dxdiag`. Fixtures live in `tests/fixtures/pc_report/` and are redacted at capture.
- Tests run with `python -m pytest -q` from the repository root (`conftest.py` sets up Qt offscreen). Lint with `python -m ruff check pc_report tests/pc_report scripts/dev/capture_pc_report_fixtures.py`.
- Commit after every task with the message shown; the work happens on branch `pc-report-siw`.
- Do not edit `ui/pc_report_dialog.py` except where Task 30 says so.

## File Map

| Path | Responsibility |
|---|---|
| `pc_report/format.py` | Value formatters: bytes, bitrate, datetime parsing/formatting, uptime, percent, duration, MHz, yes/no |
| `pc_report/section.py` | `Section`, `RunContext`, `SectionContext`, `RenderContext`, `SharedSources`, `REQUIRES_ADMIN`, result wrappers, `kv_table`/`kv_groups`/`list_table`/`sub_heading`/`notes_block` |
| `pc_report/ps.py` | `run_ps_json`, `run_text`, `cim`, `reg_props`, `ps_quote`, `dxdiag_xml`, `dx_list`, `pnp_entities`, `SHARED_LOADERS` |
| `pc_report/decode.py` | WMI enumeration tables and small decoders |
| `pc_report/registry.py` | `ORDER`, `ALIASES`, `SECTIONS`, `by_key`, `grouped`, `select` |
| `pc_report/orchestrator.py` | `run_all` over the registry with phases, shared sources, elapsed times |
| `pc_report/render_html.py` | Page shell: header, grouped contents, Report Health, group banners, CSS |
| `pc_report/privacy.py` | `redact_payload` with normalised key tokens, IP masking, Name/Value row masking |
| `pc_report/utils.py` | Re-exports `run_ps_json`, `bytes_human`, `bitrate_to_mbps` for one release |
| `pc_report/sections/*.py` | One section each; see registry order |
| `pc_report/noldus_terms.py` | `NVC_RELATED_TERMS`, `filter_nvc_related_items`, file scanners (moved from `collectors.py`) |
| `tests/pc_report/support.py` | `FixtureSectionContext`, `RecordingSectionContext`, `assert_renders_empty`, `FIXTURES` |
| `tests/pc_report/test_*.py` | One test module per task |
| `tests/fixtures/pc_report/<section>/<query>.json` | Redacted recorded query results |
| `scripts/dev/capture_pc_report_fixtures.py` | Records fixtures from the current machine |

Registry order (also the page order):

```
NVC:      noldus_summary
Software: operating_system installed_updates licenses system_directories system_files
          installed_programs security accessibility environment regional_settings
          processes services drivers autorun codecs mmc_snapins
Hardware: system_summary motherboard bios cpu memory sensors devices pci system_slots
          network_adapters video monitors sound storage_devices logical_disks ports usb
          printers virtual_machine cameras
Network:  network_information shares network_connections
```

Section conventions used by every section task:

- Key/value sections return `{"groups": [{"title": str, "rows": {label: value}}]}` and render with `kv_groups`.
- Tabular sections return `{"rows": [dict, ...]}` (or several named lists) and render with `list_table`.
- Pure builders (`build(...)`) take the raw query dicts and return the data shape, so decode logic is tested with inline dicts; `collect` only issues queries and calls `build`.
- Labels must not collide with redaction tokens unless masking is wanted (see Task 4's token list).

---

### Task 1: Foundation modules

**Files:**
- Create: `pc_report/format.py`
- Create: `pc_report/section.py`
- Create: `pc_report/ps.py`
- Create: `pc_report/decode.py`
- Create: `pc_report/registry.py`
- Create: `pc_report/sections/__init__.py`
- Modify: `pc_report/utils.py` (becomes re-exports)
- Test: `tests/pc_report/__init__.py`, `tests/pc_report/test_format.py`, `tests/pc_report/test_section_helpers.py`, `tests/pc_report/test_ps.py`, `tests/pc_report/test_decode.py`, `tests/pc_report/test_registry.py`

**Interfaces:**
- Produces: everything listed in the File Map for these modules. Later tasks import `from ..section import Section, SectionContext, RenderContext, REQUIRES_ADMIN, first_dict, rows_of, as_list, kv_groups, kv_table, list_table, sub_heading, NO_DATA`, `from ..ps import cim, reg_props, ps_quote, dx_list`, `from ..format import ...`, `from .. import decode`.

- [ ] **Step 1: Create the branch**

```bash
git checkout -b pc-report-siw
```

- [ ] **Step 2: Write the failing tests**

`tests/pc_report/__init__.py`: empty file.

`tests/pc_report/test_format.py`:

```python
import datetime
import unittest

from pc_report import format as fmt


class DatetimeParsingTests(unittest.TestCase):
    def test_ms_json_date(self):
        dt = fmt.parse_datetime("/Date(1700000000000)/")
        self.assertEqual(dt, datetime.datetime.fromtimestamp(1700000000))

    def test_cim_datetime(self):
        self.assertEqual(fmt.parse_datetime("20260922103917.000000+120"),
                         datetime.datetime(2026, 9, 22, 10, 39, 17))

    def test_iso_with_offset_becomes_naive_local(self):
        dt = fmt.parse_datetime("2026-09-22T10:39:17+00:00")
        self.assertIsNone(dt.tzinfo)

    def test_yyyymmdd(self):
        self.assertEqual(fmt.parse_datetime("20260522"), datetime.datetime(2026, 5, 22))

    def test_datetime_wrapper_dict(self):
        self.assertEqual(fmt.parse_datetime({"DateTime": "20260522000000.000000+000"}),
                         datetime.datetime(2026, 5, 22))

    def test_garbage_is_none(self):
        for value in (None, "", "yesterday", True, [], {}):
            self.assertIsNone(fmt.parse_datetime(value))

    def test_fmt_datetime_returns_input_when_unparseable(self):
        self.assertEqual(fmt.fmt_datetime("n/a"), "n/a")
        self.assertEqual(fmt.fmt_datetime(None), "")
        self.assertEqual(fmt.fmt_datetime("20260522103000.000000+000"), "2026-05-22 10:30")


class OtherFormattersTests(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(fmt.percent(25, 100), "25.0 %")
        self.assertEqual(fmt.percent(1, 0), "")
        self.assertEqual(fmt.percent("x", 10), "")

    def test_duration(self):
        self.assertEqual(fmt.duration(3723), "1 h 02 m 03 s")
        self.assertEqual(fmt.duration(65), "1 m 05 s")
        self.assertEqual(fmt.duration(7), "7 s")
        self.assertEqual(fmt.duration("bad"), "")

    def test_mhz(self):
        self.assertEqual(fmt.mhz(3200), "3200 MHz")
        self.assertEqual(fmt.mhz(12000), "12.00 GHz")
        self.assertEqual(fmt.mhz(None), "")

    def test_yes_no(self):
        self.assertEqual(fmt.yes_no(True), "Yes")
        self.assertEqual(fmt.yes_no(0), "No")
        self.assertEqual(fmt.yes_no("True"), "Yes")
        self.assertEqual(fmt.yes_no(None), "")
        self.assertEqual(fmt.yes_no("Maybe"), "Maybe")

    def test_kb_human(self):
        self.assertEqual(fmt.kb_human(1024), "1.0 MB")

    def test_uptime_human_is_empty_for_future_or_missing(self):
        self.assertEqual(fmt.uptime_human(None), "")
        future = (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(fmt.uptime_human(future), "")

    def test_legacy_names_still_exist(self):
        from pc_report.utils import bytes_human, bitrate_to_mbps, run_ps_json
        self.assertEqual(bytes_human(2048), "2.0 KB")
        self.assertEqual(bitrate_to_mbps(1_000_000), "1.0 Mbps")
        self.assertTrue(callable(run_ps_json))
```

`tests/pc_report/test_section_helpers.py`:

```python
import unittest

from pc_report import section as S


def _section(key="k", **kw):
    return S.Section(key=key, title=key.title(), group="Software",
                     collect=lambda ctx: {}, render=lambda d, c: "", **kw)


class ResultShapeTests(unittest.TestCase):
    def test_wrap_and_unwrap(self):
        wrapped = S.wrap({"a": 1}, ["n1"])
        self.assertEqual(wrapped, {"data": {"a": 1}, "notes": ["n1"]})
        self.assertEqual(S.section_data(wrapped), {"a": 1})
        self.assertEqual(S.section_notes(wrapped), ["n1"])

    def test_partial_is_recognised_and_has_no_data(self):
        partial = {"status": "partial", "error": "boom"}
        self.assertTrue(S.is_partial(partial))
        self.assertIsNone(S.section_data(partial))
        self.assertIsNone(S.section_data(None))

    def test_legacy_unwrapped_result_passes_through(self):
        self.assertEqual(S.section_data([1, 2]), [1, 2])

    def test_shaping_helpers(self):
        self.assertEqual(S.as_list(None), [])
        self.assertEqual(S.as_list({"a": 1}), [{"a": 1}])
        self.assertEqual(S.rows_of([{"a": 1}, "junk", None]), [{"a": 1}])
        self.assertEqual(S.first_dict(["x", {"b": 2}]), {"b": 2})
        self.assertEqual(S.first_dict(None), {})


class SectionContextTests(unittest.TestCase):
    def _ctx(self, is_admin=False, runner=None, text_runner=None, loaders=None):
        run = S.RunContext(options={"x": 1}, is_admin=is_admin, results={"dep": S.wrap({"v": 7}, [])},
                           shared=S.SharedSources(loaders or {}),
                           runner=runner or (lambda script, timeout: ({"ok": True}, None)),
                           text_runner=text_runner or (lambda args, timeout: ("out", None)))
        return S.SectionContext(run, _section(timeout=42))

    def test_query_uses_section_timeout_and_records_errors(self):
        seen = {}

        def runner(script, timeout):
            seen["timeout"] = timeout
            return None, "timed out"

        ctx = self._ctx(runner=runner)
        self.assertIsNone(ctx.query("thing", "Get-Thing"))
        self.assertEqual(seen["timeout"], 42)
        self.assertEqual(ctx.notes, ["thing: timed out"])

    def test_query_timeout_override(self):
        seen = {}
        ctx = self._ctx(runner=lambda s, t: (seen.setdefault("t", t), None))
        ctx.query("x", "y", timeout=90)
        self.assertEqual(seen["t"], 90)

    def test_admin_query_without_admin_never_runs(self):
        ctx = self._ctx(runner=lambda s, t: self.fail("must not run"))
        self.assertEqual(ctx.admin_query("bitlocker", "Get-BitLockerVolume"), S.REQUIRES_ADMIN)
        self.assertEqual(ctx.notes, ["bitlocker: requires administrator"])

    def test_admin_query_with_admin_runs(self):
        ctx = self._ctx(is_admin=True)
        self.assertEqual(ctx.admin_query("x", "y"), {"ok": True})

    def test_text_returns_empty_string_on_error(self):
        ctx = self._ctx(text_runner=lambda a, t: ("", "no such command"))
        self.assertEqual(ctx.text("netsh", ["netsh"]), "")
        self.assertIn("netsh: no such command", ctx.notes)

    def test_shared_is_memoised_and_errors_noted(self):
        calls = []

        def loader():
            calls.append(1)
            return {"dx": 1}, None

        ctx = self._ctx(loaders={"dxdiag": loader})
        self.assertEqual(ctx.shared("dxdiag"), {"dx": 1})
        self.assertEqual(ctx.shared("dxdiag"), {"dx": 1})
        self.assertEqual(len(calls), 1)
        self.assertIsNone(ctx.shared("missing"))
        self.assertTrue(any("missing" in n for n in ctx.notes))

    def test_shared_loader_exception_is_captured(self):
        def loader():
            raise RuntimeError("dxdiag exploded")
        ctx = self._ctx(loaders={"dxdiag": loader})
        self.assertIsNone(ctx.shared("dxdiag"))
        self.assertIn("dxdiag: dxdiag exploded", ctx.notes)

    def test_result_reads_other_sections_data(self):
        ctx = self._ctx()
        self.assertEqual(ctx.result("dep"), {"v": 7})
        self.assertIsNone(ctx.result("absent"))
        self.assertEqual(ctx.options, {"x": 1})


class HtmlHelperTests(unittest.TestCase):
    def test_kv_table_escapes_and_subheads(self):
        html = S.kv_table([("Group", None), ("Name", "<b>"), ("Flag", True), ("List", ["a", "b"])])
        self.assertIn('<tr class="sub"><th colspan="2">Group</th></tr>', html)
        self.assertIn("<th>Name</th><td>&lt;b&gt;</td>", html)
        self.assertIn("<td>Yes</td>", html)
        self.assertIn("<td>a, b</td>", html)

    def test_kv_table_empty(self):
        self.assertEqual(S.kv_table([]), S.NO_DATA)

    def test_kv_groups_skips_empty_groups_and_keeps_none_values_blank(self):
        html = S.kv_groups([{"title": "Empty", "rows": {}},
                            {"title": "Real", "rows": {"A": None, "B": 2}}])
        self.assertNotIn("Empty", html)
        self.assertIn("<th>A</th><td></td>", html)
        self.assertIn("<th>B</th><td>2</td>", html)

    def test_requires_admin_renders_warning(self):
        html = S.kv_table([("TPM", S.REQUIRES_ADMIN)])
        self.assertIn('<span class="warn">Requires administrator</span>', html)

    def test_list_table(self):
        html = S.list_table([("a", "Col A"), ("b", "Col B")], [{"a": 1}, "junk", {"b": "x"}])
        self.assertIn("<th>Col A</th><th>Col B</th>", html)
        self.assertIn("<td>1</td><td></td>", html)
        self.assertIn("<td></td><td>x</td>", html)
        self.assertEqual(S.list_table([("a", "A")], []), S.NO_DATA)

    def test_long_cell_is_folded(self):
        html = S.list_table([("c", "C")], [{"c": "x" * 600}])
        self.assertIn("<details>", html)

    def test_notes_block(self):
        self.assertEqual(S.notes_block([]), "")
        self.assertIn("a &amp; b", S.notes_block(["a & b"]))
        self.assertIn("<h3>T</h3>", S.sub_heading("T"))
```

`tests/pc_report/test_ps.py`:

```python
import unittest
from unittest.mock import patch

from pc_report import ps


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class RunPsJsonTests(unittest.TestCase):
    def test_wraps_script_in_a_scriptblock_and_utf8(self):
        captured = {}

        def run(cmd, **kw):
            captured["cmd"] = cmd
            return _Completed(stdout="{}")

        with patch.object(ps.subprocess, "run", run):
            ps.run_ps_json("Get-Thing")
        joined = " ".join(captured["cmd"])
        self.assertIn("& { Get-Thing }", joined)
        self.assertIn("ConvertTo-Json", joined)
        self.assertIn("OutputEncoding", joined)
        self.assertIn("ProgressPreference", joined)

    def test_timeout_message_names_the_seconds(self):
        import subprocess as sp
        with patch.object(ps.subprocess, "run", side_effect=sp.TimeoutExpired("powershell", 30)):
            data, error = ps.run_ps_json("x", timeout=30)
        self.assertIsNone(data)
        self.assertEqual(error, "timed out after 30 s")

    def test_nonzero_exit_without_stderr_still_reports(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(returncode=1)):
            _data, error = ps.run_ps_json("x")
        self.assertEqual(error, "exit code 1")


class RunTextTests(unittest.TestCase):
    def test_returns_stdout(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(stdout="hello")):
            self.assertEqual(ps.run_text(["cmd"]), ("hello", None))

    def test_failure_with_no_output_is_an_error(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(returncode=2, stderr="bad")):
            self.assertEqual(ps.run_text(["cmd"]), ("", "bad"))

    def test_missing_binary(self):
        with patch.object(ps.subprocess, "run", side_effect=FileNotFoundError("nope")):
            out, error = ps.run_text(["nope"])
        self.assertEqual(out, "")
        self.assertIn("nope", error)


class ScriptBuilderTests(unittest.TestCase):
    def test_cim(self):
        script = ps.cim("Win32_BIOS", ["Name", "Version"], namespace=r"root\wmi", where="Level=3")
        self.assertIn("Get-CimInstance -ClassName Win32_BIOS", script)
        self.assertIn("-Namespace 'root\\wmi'", script)
        self.assertIn("-Filter 'Level=3'", script)
        self.assertTrue(script.endswith("| Select-Object Name,Version"))

    def test_ps_quote_doubles_single_quotes(self):
        self.assertEqual(ps.ps_quote("it's"), "'it''s'")

    def test_reg_props(self):
        script = ps.reg_props(r"HKLM:\SOFTWARE\Test")
        self.assertIn("Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Test'", script)
        self.assertIn("PSPath", script)


class DxdiagTests(unittest.TestCase):
    def test_etree_to_dict_collapses_repeats_into_lists(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring("<DxDiag><A><B>1</B><B>2</B><C>x</C></A></DxDiag>")
        self.assertEqual(ps._etree_to_dict(root), {"A": {"B": ["1", "2"], "C": "x"}})

    def test_dx_list_handles_single_and_multiple(self):
        dx = {"DisplayDevices": {"DisplayDevice": {"CardName": "GPU"}}}
        self.assertEqual(ps.dx_list(dx, "DisplayDevices", "DisplayDevice"), [{"CardName": "GPU"}])
        dx = {"DisplayDevices": {"DisplayDevice": [{"CardName": "A"}, {"CardName": "B"}]}}
        self.assertEqual(len(ps.dx_list(dx, "DisplayDevices", "DisplayDevice")), 2)
        self.assertEqual(ps.dx_list(None, "X", "Y"), [])
        self.assertEqual(ps.dx_list({"X": "text"}, "X", "Y"), [])

    def test_shared_loaders_are_registered(self):
        self.assertEqual(set(ps.SHARED_LOADERS), {"dxdiag", "pnp_entities"})
```

`tests/pc_report/test_decode.py`:

```python
import unittest

from pc_report import decode as D


class DecodeTests(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(D.to_int("3"), 3)
        self.assertEqual(D.to_int(4.0), 4)
        self.assertIsNone(D.to_int("x"))
        self.assertEqual(D.to_int(None, 0), 0)

    def test_lookup_falls_back_to_other_with_code(self):
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, 3), "Desktop")
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, 999), "Other (999)")
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, None), "")
        self.assertEqual(D.lookup(D.CHASSIS_TYPES, [3, 10]), "Desktop, Notebook")

    def test_memory_and_form_factor(self):
        self.assertEqual(D.lookup(D.MEMORY_TYPES, 34), "DDR5")
        self.assertEqual(D.lookup(D.MEMORY_TYPES, 26), "DDR4")
        self.assertEqual(D.lookup(D.FORM_FACTORS, 8), "DIMM")
        self.assertEqual(D.lookup(D.FORM_FACTORS, 12), "SODIMM")

    def test_pnp_error_codes(self):
        self.assertEqual(D.lookup(D.PNP_ERROR_CODES, 0), "Working properly")
        self.assertEqual(D.lookup(D.PNP_ERROR_CODES, 28), "Drivers not installed")
        self.assertEqual(D.lookup(D.PNP_ERROR_CODES, 22), "Disabled")

    def test_bios_characteristics(self):
        text = D.bios_characteristics([7, 9, 32, 40])
        self.assertIn("Supports PCI", text)
        self.assertIn("Supports Plug and Play", text)
        self.assertIn("Supports ACPI", text)
        self.assertIn("Reserved (40)", text)

    def test_license_status_and_sku(self):
        self.assertEqual(D.lookup(D.LICENSE_STATUS, 1), "Licensed")
        self.assertEqual(D.os_sku(125), "Enterprise LTSC")
        self.assertEqual(D.os_sku(48), "Professional")

    def test_dotnet_release(self):
        self.assertEqual(D.dotnet_release(533320), "4.8.1")
        self.assertEqual(D.dotnet_release(528372), "4.8")
        self.assertEqual(D.dotnet_release(None), "")

    def test_au_options(self):
        self.assertEqual(D.au_options(1, None), "Disabled by policy")
        self.assertEqual(D.au_options(None, 4), "Automatically download and schedule installation")
        self.assertEqual(D.au_options(None, None), "Default (managed by Windows)")

    def test_security_center_state(self):
        # 0x061100 = enabled, up to date (Defender's usual value)
        self.assertEqual(D.security_center_state(397568), ("Enabled", "Up to date"))
        # 0x000000 = disabled
        self.assertEqual(D.security_center_state(0), ("Disabled", "Up to date"))
        self.assertEqual(D.security_center_state(0x1010), ("Enabled", "Out of date"))

    def test_accessibility_flags(self):
        decoded = D.accessibility_flags(0x1E)
        self.assertEqual(decoded["Enabled"], "No")
        self.assertEqual(decoded["Available"], "Yes")
        self.assertEqual(decoded["Hotkey activation enabled"], "Yes")

    def test_os_language(self):
        self.assertEqual(D.os_language(1033), "English (United States)")
        self.assertEqual(D.os_language("1043"), "Dutch (Netherlands)")
        self.assertEqual(D.os_language(9999), "LCID 9999")

    def test_pci_vendor(self):
        self.assertEqual(D.pci_vendor("8086"), "Intel Corporation")
        self.assertEqual(D.pci_vendor("10DE"), "NVIDIA Corporation")
        self.assertEqual(D.pci_vendor("FFFF"), "Vendor FFFF")
```

`tests/pc_report/test_registry.py`:

```python
import unittest

from pc_report import registry
from pc_report.section import GROUPS, Section


class RegistryInvariantTests(unittest.TestCase):
    def test_every_section_is_in_order_and_unique(self):
        keys = [s.key for s in registry.SECTIONS]
        self.assertEqual(len(keys), len(set(keys)))
        for key in keys:
            self.assertIn(key, registry.ORDER)
        self.assertEqual(keys, sorted(keys, key=registry.ORDER.index))

    def test_groups_are_known_and_callables_present(self):
        for section in registry.SECTIONS:
            self.assertIn(section.group, GROUPS, section.key)
            self.assertTrue(callable(section.collect), section.key)
            self.assertTrue(callable(section.render), section.key)
            self.assertGreaterEqual(section.timeout, 12, section.key)

    def test_after_names_existing_keys_without_cycles(self):
        keys = {s.key for s in registry.SECTIONS}
        for section in registry.SECTIONS:
            for dep in section.after:
                self.assertIn(dep, keys, f"{section.key} depends on unknown {dep}")
        # Kahn's algorithm: every section must be reachable.
        remaining = {s.key: set(s.after) for s in registry.SECTIONS}
        while remaining:
            ready = [k for k, deps in remaining.items() if not deps]
            self.assertTrue(ready, f"dependency cycle among {sorted(remaining)}")
            for k in ready:
                del remaining[k]
            for deps in remaining.values():
                deps.difference_update(ready)

    def test_render_survives_empty_and_partial(self):
        from pc_report.section import RenderContext
        ctx = RenderContext(redact=True, meta={})
        for section in registry.SECTIONS:
            for payload in ({}, None, []):
                out = section.render(payload, ctx)
                self.assertIsInstance(out, str, section.key)

    def test_order_covers_the_spec_and_alias_targets_exist_in_order(self):
        self.assertEqual(len(registry.ORDER), 40)
        self.assertEqual(registry.ORDER[0], "noldus_summary")
        for alias, targets in registry.ALIASES.items():
            for target in targets:
                self.assertIn(target, registry.ORDER, alias)


class SelectionTests(unittest.TestCase):
    def _sections(self):
        mk = lambda key, on=True: Section(key=key, title=key, group="Hardware",  # noqa: E731
                                          collect=lambda c: {}, render=lambda d, c: "", default_on=on)
        return [mk("cpu"), mk("memory"), mk("shares"), mk("processes", on=False)]

    def test_default_on_respected(self):
        keys = [s.key for s in registry.select({}, self._sections())]
        self.assertEqual(keys, ["cpu", "memory", "shares"])

    def test_explicit_switches(self):
        keys = [s.key for s in registry.select({"cpu": False, "processes": True}, self._sections())]
        self.assertEqual(keys, ["memory", "shares", "processes"])

    def test_group_alias_switches_split_sections(self):
        keys = [s.key for s in registry.select({"hardware": False}, self._sections())]
        self.assertEqual(keys, ["shares"])
        keys = [s.key for s in registry.select({"network": False}, self._sections())]
        self.assertEqual(keys, ["cpu", "memory"])

    def test_explicit_key_beats_alias(self):
        keys = [s.key for s in registry.select({"hardware": False, "cpu": True}, self._sections())]
        self.assertEqual(keys, ["cpu", "shares"])

    def test_grouped_keeps_group_order(self):
        grouped = registry.grouped(self._sections())
        self.assertEqual(list(grouped), list(GROUPS))
        self.assertEqual([s.key for s in grouped["Hardware"]], ["cpu", "memory", "shares", "processes"])
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/pc_report -q`
Expected: collection errors, `ModuleNotFoundError: No module named 'pc_report.format'` (and section, ps, decode, registry).

- [ ] **Step 4: Write `pc_report/format.py`**

```python
"""Value formatters shared by the PC report sections and page shell."""
from __future__ import annotations

import datetime
import re

_MSJSON = re.compile(r"/Date\((-?\d+)\)/")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def bytes_human(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return n
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return f"{f:.1f} {units[i]}"


def kb_human(kilobytes):
    try:
        return bytes_human(int(float(kilobytes)) * 1024)
    except (TypeError, ValueError):
        return kilobytes


def bitrate_to_mbps(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "Unknown"
    if n <= 0 or n >= 9_000_000_000_000_000_000:
        return "Unknown"
    return f"{n / 1_000_000:.1f} Mbps"


def parse_datetime(value) -> datetime.datetime | None:
    """Naive local datetime from the shapes PowerShell JSON produces, else None.

    Handles ``{"DateTime": ...}`` wrappers, ``/Date(ms)/``, CIM
    ``yyyymmddHHMMSS.ffffff+zzz``, ``yyyymmdd``, ISO-8601, and epoch
    seconds or milliseconds.
    """
    if isinstance(value, dict):
        value = value.get("DateTime") or value.get("value")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            seconds = value / 1000.0 if value > 10_000_000_000 else float(value)
            return datetime.datetime.fromtimestamp(seconds)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    m = _MSJSON.search(s)
    if m:
        try:
            return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000.0)
        except (OverflowError, OSError, ValueError):
            return None
    if len(s) >= 14 and s[:14].isdigit():
        try:
            return datetime.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]),
                                     int(s[8:10]), int(s[10:12]), int(s[12:14]))
        except ValueError:
            return None
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    if _ISO_DATE.match(s):
        try:
            dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    return None


def fmt_datetime(value, fmt: str = "%Y-%m-%d %H:%M"):
    """Formatted datetime, or the input unchanged when it cannot be parsed."""
    dt = parse_datetime(value)
    if dt is None:
        return "" if value is None else value
    return dt.strftime(fmt)


def fmt_date(value):
    return fmt_datetime(value, "%Y-%m-%d")


def uptime_human(since) -> str:
    dt = parse_datetime(since)
    if dt is None:
        return ""
    delta = datetime.datetime.now() - dt
    if delta.total_seconds() < 0:
        return ""
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts)


def percent(part, whole, digits: int = 1) -> str:
    try:
        part = float(part)
        whole = float(whole)
    except (TypeError, ValueError):
        return ""
    if whole <= 0:
        return ""
    return f"{100.0 * part / whole:.{digits}f} %"


def duration(seconds) -> str:
    """'1 h 02 m 03 s' style, for elapsed and CPU times."""
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    hours, rem = divmod(max(0, total), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} h {minutes:02d} m {secs:02d} s"
    if minutes:
        return f"{minutes} m {secs:02d} s"
    return f"{secs} s"


def mhz(value) -> str:
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return ""
    return f"{v} MHz" if v < 10_000 else f"{v / 1000:.2f} GHz"


def yes_no(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "1", "on", "enabled"):
            return "Yes"
        if low in ("false", "no", "0", "off", "disabled"):
            return "No"
        return value
    return "Yes" if value else "No"
```

- [ ] **Step 5: Write `pc_report/section.py`**

```python
"""Building blocks shared by every PC report section.

A section module exposes one ``SECTION`` object (see ``Section``). Its
``collect`` receives a ``SectionContext`` and returns JSON-able data; the
orchestrator wraps that as ``{"data": ..., "notes": [...]}``. Its ``render``
receives the unwrapped data and a ``RenderContext`` and returns an HTML
fragment built from the table helpers below.
"""
from __future__ import annotations

import ctypes
import html as _html
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

REQUIRES_ADMIN = "__requires_admin__"
GROUPS: tuple[str, ...] = ("NVC", "Software", "Hardware", "Network")
NO_DATA = "<em>No data</em>"
CELL_LIMIT = 512


def is_user_admin() -> bool:
    """True when the process runs elevated. False on any failure or off Windows."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


class SharedSources:
    """Memoises expensive sources (dxdiag, the PnP dump) across sections in one run.

    ``loaders`` maps a name to a zero-argument callable returning
    ``(value, error)``. The first caller pays; later callers get the cached
    pair. A loader that raises is recorded as ``(None, str(exc))``.
    """

    def __init__(self, loaders: dict[str, Callable[[], tuple[Any, str | None]]]):
        self._loaders = dict(loaders)
        self._cache: dict[str, tuple[Any, str | None]] = {}
        self._lock = threading.Lock()
        self.calls: dict[str, int] = {}

    def get(self, name: str) -> tuple[Any, str | None]:
        with self._lock:
            if name not in self._cache:
                loader = self._loaders.get(name)
                if loader is None:
                    self._cache[name] = (None, f"unknown shared source {name!r}")
                else:
                    self.calls[name] = self.calls.get(name, 0) + 1
                    try:
                        self._cache[name] = loader()
                    except Exception as exc:  # a shared source must never sink its consumers
                        self._cache[name] = (None, str(exc))
            return self._cache[name]


@dataclass
class RunContext:
    """State shared by every section during one ``run_all``."""
    options: dict
    is_admin: bool
    results: dict
    shared: SharedSources
    runner: Callable[[str, int], tuple[Any, str | None]]
    text_runner: Callable[[list[str], int], tuple[str, str | None]]


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    group: str
    collect: Callable[["SectionContext"], Any]
    render: Callable[[Any, "RenderContext"], str]
    timeout: int = 30
    default_on: bool = True
    after: tuple[str, ...] = ()


class SectionContext:
    """What one section's ``collect`` receives.

    Every query is named so fixtures can be recorded and replayed by name,
    and so a failing query produces a readable note.
    """

    def __init__(self, run: RunContext, section: Section):
        self.run = run
        self.section = section
        self.notes: list[str] = []

    @property
    def is_admin(self) -> bool:
        return self.run.is_admin

    @property
    def options(self) -> dict:
        return self.run.options

    def note(self, text: str) -> None:
        self.notes.append(text)

    def query(self, name: str, script: str, timeout: int | None = None):
        data, error = self.run.runner(script, timeout or self.section.timeout)
        if error:
            self.note(f"{name}: {error}")
        return data

    def text(self, name: str, args: list[str], timeout: int | None = None) -> str:
        out, error = self.run.text_runner(list(args), timeout or self.section.timeout)
        if error:
            self.note(f"{name}: {error}")
        return out or ""

    def admin_query(self, name: str, script: str, timeout: int | None = None):
        if not self.is_admin:
            self.note(f"{name}: requires administrator")
            return REQUIRES_ADMIN
        return self.query(name, script, timeout)

    def shared(self, name: str):
        value, error = self.run.shared.get(name)
        if error:
            self.note(f"{name}: {error}")
        return value

    def result(self, key: str):
        return section_data(self.run.results.get(key))


@dataclass
class RenderContext:
    redact: bool = True
    meta: dict = field(default_factory=dict)


# --- result shape ----------------------------------------------------------

def wrap(data, notes) -> dict:
    return {"data": data, "notes": list(notes)}


def is_partial(result) -> bool:
    return isinstance(result, dict) and result.get("status") == "partial"


def section_data(result):
    if result is None or is_partial(result):
        return None
    if isinstance(result, dict) and set(result) == {"data", "notes"}:
        return result["data"]
    return result


def section_notes(result) -> list[str]:
    if isinstance(result, dict) and isinstance(result.get("notes"), list):
        return [str(n) for n in result["notes"]]
    return []


# --- data shaping ----------------------------------------------------------

def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def rows_of(value) -> list[dict]:
    return [row for row in as_list(value) if isinstance(row, dict)]


def first_dict(value) -> dict:
    for item in as_list(value):
        if isinstance(item, dict):
            return item
    return {}


# --- HTML ------------------------------------------------------------------

def esc(value) -> str:
    return _html.escape("" if value is None else str(value))


def render_value(value) -> str:
    if value is None:
        return ""
    if value == REQUIRES_ADMIN:
        return '<span class="warn">Requires administrator</span>'
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return esc(", ".join("" if v is None else str(v) for v in value))
    if isinstance(value, dict):
        return esc("; ".join(f"{k}: {v}" for k, v in value.items()))
    text = str(value)
    if len(text) > CELL_LIMIT:
        return (esc(text[:CELL_LIMIT]) + "…<details><summary>Show more</summary><pre>"
                + esc(text) + "</pre></details>")
    return esc(text)


def kv_table(rows) -> str:
    """rows: iterable of (label, value). (label, None) renders as a sub-heading row."""
    rows = list(rows)
    if not rows:
        return NO_DATA
    out = ['<table class="kv">']
    for label, value in rows:
        if value is None:
            out.append(f'<tr class="sub"><th colspan="2">{esc(label)}</th></tr>')
        else:
            out.append(f"<tr><th>{esc(label)}</th><td>{render_value(value)}</td></tr>")
    out.append("</table>")
    return "".join(out)


def kv_groups(groups) -> str:
    """groups: list of {"title": str, "rows": dict | list of pairs}. Empty groups are skipped.

    A ``None`` value inside ``rows`` renders as a blank cell, not a sub-heading.
    """
    rows = []
    for group in as_list(groups):
        if not isinstance(group, dict):
            continue
        grows = group.get("rows") or {}
        pairs = list(grows.items()) if isinstance(grows, dict) else [tuple(p) for p in grows]
        pairs = [(k, "" if v is None else v) for k, v in pairs]
        if not pairs:
            continue
        if group.get("title"):
            rows.append((group["title"], None))
        rows.extend(pairs)
    return kv_table(rows)


def list_table(columns, rows) -> str:
    """columns: list of (key, label); rows: list of dicts. Missing keys render blank."""
    rows = rows_of(rows)
    if not rows:
        return NO_DATA
    head = "".join(f"<th>{esc(label)}</th>" for _key, label in columns)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{render_value(row.get(key))}</td>"
                                     for key, _label in columns) + "</tr>")
    return (f'<table class="list"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def sub_heading(text) -> str:
    return f"<h3>{esc(text)}</h3>"


def notes_block(notes) -> str:
    notes = [n for n in as_list(notes) if n]
    if not notes:
        return ""
    return '<p class="notes"><em>' + "<br>".join(esc(n) for n in notes) + "</em></p>"
```

- [ ] **Step 6: Write `pc_report/ps.py`**

```python
"""PowerShell and command-line plumbing for the PC report.

Everything the sections need to reach Windows goes through here, so tests can
replace two functions (``run_ps_json`` and ``run_text``) and never spawn a
process.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

CREATE_NO_WINDOW = 0x08000000

_PREAMBLE = (
    "$ErrorActionPreference='Continue'; $WarningPreference='SilentlyContinue'; "
    "$ProgressPreference='SilentlyContinue'; "
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
)


def _run_kwargs(timeout):
    kwargs = dict(capture_output=True, text=True, timeout=timeout,
                  encoding="utf-8", errors="replace")
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        kwargs["shell"] = False
    return kwargs


def run_ps_json(script: str, timeout: int = 15):
    """Run a PowerShell snippet and parse its ConvertTo-Json output.

    Returns ``(data, error)`` and never raises. The snippet is wrapped in a
    scriptblock so multi-statement scripts pipe all their output.
    """
    eff_timeout = max(timeout, 12)
    cmd = [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
        _PREAMBLE + "& { " + script + " } | ConvertTo-Json -Depth 6 -Compress -WarningAction SilentlyContinue",
    ]
    try:
        cp = subprocess.run(cmd, **_run_kwargs(eff_timeout))
    except subprocess.TimeoutExpired:
        return None, f"timed out after {eff_timeout} s"
    except Exception as e:
        return None, str(e)
    if cp.returncode != 0:
        return None, (cp.stderr or f"exit code {cp.returncode}").strip()[:500]
    if not cp.stdout or not cp.stdout.strip():
        return None, None
    try:
        return json.loads(cp.stdout), None
    except Exception as e:
        return None, f"JSON parse error: {e}"


def run_text(args: list[str], timeout: int = 15) -> tuple[str, str | None]:
    """Run a command line (netsh, powercfg, ...) and return ``(stdout, error)``."""
    try:
        cp = subprocess.run(list(args), **_run_kwargs(max(timeout, 5)))
    except subprocess.TimeoutExpired:
        return "", f"timed out after {timeout} s"
    except Exception as e:
        return "", str(e)
    if cp.returncode != 0 and not cp.stdout:
        return "", (cp.stderr or f"exit code {cp.returncode}").strip()[:500]
    return cp.stdout or "", None


def ps_quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def cim(class_name: str, props=None, namespace: str | None = None, where: str | None = None) -> str:
    parts = ["Get-CimInstance", "-ClassName", class_name, "-ErrorAction", "SilentlyContinue"]
    if namespace:
        parts += ["-Namespace", ps_quote(namespace)]
    if where:
        parts += ["-Filter", ps_quote(where)]
    script = " ".join(parts)
    if props:
        script += " | Select-Object " + ",".join(props)
    return script


def reg_props(path: str) -> str:
    """Script returning ``[{Name, Value}]`` for every value under a registry key."""
    return (
        f"$p = Get-ItemProperty -Path {ps_quote(path)} -ErrorAction SilentlyContinue; "
        "if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notmatch "
        "'^PS(Path|ParentPath|ChildName|Drive|Provider)$' } | ForEach-Object { "
        "[pscustomobject]@{ Name = [string]$_.Name; Value = [string]$_.Value } } }"
    )


# --- shared sources ----------------------------------------------------------

def _etree_to_dict(node):
    children = list(node)
    if not children:
        return (node.text or "").strip()
    out: dict = {}
    for child in children:
        value = _etree_to_dict(child)
        if child.tag in out:
            if not isinstance(out[child.tag], list):
                out[child.tag] = [out[child.tag]]
            out[child.tag].append(value)
        else:
            out[child.tag] = value
    return out


def dxdiag_xml(timeout: int = 90):
    """Run ``dxdiag /whql:off /x`` and return ``(dict, error)``. Slow but rich."""
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "dxdiag.exe")
    fd, path = tempfile.mkstemp(suffix=".xml", prefix="nvc_dxdiag_")
    os.close(fd)
    try:
        os.remove(path)
        cp = subprocess.run([exe, "/whql:off", "/x", path], **_run_kwargs(timeout))
        if not os.path.exists(path):
            return None, (cp.stderr or "dxdiag produced no output").strip()[:200]
        return _etree_to_dict(ET.parse(path).getroot()), None
    except subprocess.TimeoutExpired:
        return None, f"dxdiag timed out after {timeout} s"
    except Exception as e:
        return None, f"dxdiag failed: {e}"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def dx_list(dx, container: str, item: str) -> list[dict]:
    """Items under e.g. ``('DisplayDevices', 'DisplayDevice')`` as a list of dicts."""
    if not isinstance(dx, dict):
        return []
    block = dx.get(container)
    if not isinstance(block, dict):
        return []
    value = block.get(item)
    if value is None:
        return []
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, dict)]


PNP_PROPS = ("Name", "Manufacturer", "PNPClass", "ClassGuid", "DeviceID", "PNPDeviceID",
             "Status", "ConfigManagerErrorCode", "Service", "Present", "Description")


def pnp_entities(timeout: int = 60):
    return run_ps_json(cim("Win32_PnPEntity", PNP_PROPS) + " | Sort-Object PNPClass, Name", timeout)


SHARED_LOADERS = {"dxdiag": dxdiag_xml, "pnp_entities": pnp_entities}
```

- [ ] **Step 7: Write `pc_report/decode.py`**

```python
"""WMI enumeration tables and small decoders used by the sections."""
from __future__ import annotations


def to_int(value, default=None):
    try:
        if isinstance(value, bool):
            return int(value)
        return int(float(value))
    except (TypeError, ValueError):
        return default


def lookup(table: dict, code, other: str = "Other") -> str:
    """Decode one code or a list of codes; unknown codes become 'Other (n)'."""
    if code is None or code == "":
        return ""
    if isinstance(code, list):
        return ", ".join(lookup(table, c, other) for c in code)
    n = to_int(code)
    if n is None:
        return str(code)
    return table.get(n, f"{other} ({n})")


def flags(table: dict, value) -> list[str]:
    """Names of the bits set in ``value``."""
    n = to_int(value)
    if n is None:
        return []
    return [name for bit, name in table.items() if n & bit]


# --- operating system ---------------------------------------------------------

PRODUCT_TYPES = {1: "Workstation", 2: "Domain Controller", 3: "Server"}

_OS_SKU = {
    1: "Ultimate", 2: "Home Basic", 3: "Home Premium", 4: "Enterprise", 6: "Business",
    7: "Server Standard", 8: "Server Datacenter", 27: "Enterprise N", 48: "Professional",
    49: "Professional N", 98: "Home N", 100: "Home Single Language", 101: "Home",
    121: "Education", 122: "Education N", 125: "Enterprise LTSC", 126: "Enterprise N LTSC",
    161: "Pro for Workstations", 162: "Pro for Workstations N", 175: "Enterprise for Virtual Desktops",
    188: "IoT Enterprise", 191: "IoT Enterprise LTSC",
}


def os_sku(code) -> str:
    return lookup(_OS_SKU, code, "SKU")


LICENSE_STATUS = {0: "Unlicensed", 1: "Licensed", 2: "Initial grace period",
                  3: "Additional grace period", 4: "Non-genuine grace period",
                  5: "Notification", 6: "Extended grace period"}

UAC_PROMPT = {0: "Elevate without prompting", 1: "Prompt for credentials on the secure desktop",
              2: "Prompt for consent on the secure desktop", 3: "Prompt for credentials",
              4: "Prompt for consent", 5: "Prompt for consent for non-Windows binaries"}

DEP_POLICY = {0: "Always off", 1: "Always on", 2: "Opt in (Windows programs only)", 3: "Opt out"}

_LCID = {
    1033: "English (United States)", 2057: "English (United Kingdom)", 3081: "English (Australia)",
    4105: "English (Canada)", 1043: "Dutch (Netherlands)", 2067: "Dutch (Belgium)",
    2052: "Chinese (Simplified)", 1028: "Chinese (Traditional)", 1031: "German (Germany)",
    1036: "French (France)", 1034: "Spanish (Spain)", 1040: "Italian (Italy)", 1041: "Japanese",
    1042: "Korean", 1046: "Portuguese (Brazil)", 2070: "Portuguese (Portugal)", 1053: "Swedish",
    1030: "Danish", 1044: "Norwegian", 1035: "Finnish", 1045: "Polish", 1049: "Russian",
    1029: "Czech", 1038: "Hungarian", 1055: "Turkish", 1032: "Greek", 1037: "Hebrew",
    1025: "Arabic (Saudi Arabia)", 1054: "Thai", 1066: "Vietnamese",
}


def os_language(lcid) -> str:
    n = to_int(lcid)
    if n is None:
        return "" if lcid in (None, "") else str(lcid)
    return _LCID.get(n, f"LCID {n}")


_DOTNET = [(533320, "4.8.1"), (528040, "4.8"), (461808, "4.7.2"), (461308, "4.7.1"),
           (460798, "4.7"), (394802, "4.6.2"), (394254, "4.6.1"), (393295, "4.6"),
           (379893, "4.5.2"), (378675, "4.5.1"), (378389, "4.5")]


def dotnet_release(release) -> str:
    n = to_int(release)
    if n is None:
        return ""
    for floor, version in _DOTNET:
        if n >= floor:
            return version
    return f"release {n}"


_AU = {1: "Never check for updates", 2: "Notify before download",
       3: "Automatically download, notify before install",
       4: "Automatically download and schedule installation",
       5: "Local administrator chooses", 7: "Notify for install and restart"}


def au_options(no_auto_update, au_option) -> str:
    if to_int(no_auto_update) == 1:
        return "Disabled by policy"
    n = to_int(au_option)
    if n is None:
        return "Default (managed by Windows)"
    return _AU.get(n, f"Option {n}")


# --- security -----------------------------------------------------------------

def security_center_state(product_state) -> tuple[str, str]:
    """Decode root\\SecurityCenter2 productState into (enabled, signature) words."""
    n = to_int(product_state, 0)
    enabled = "Enabled" if (n >> 12) & 0x1 else "Disabled"
    signature = "Out of date" if (n >> 4) & 0x1 else "Up to date"
    return enabled, signature


DEVICE_GUARD_ONOFF = {0: "Off", 1: "On", 2: "Not applicable"}
DEVICE_GUARD_SERVICES = {0: "None/Unknown", 1: "Credential Guard", 2: "Hypervisor Code Integrity (HVCI)",
                         3: "Secure Boot", 4: "DMA Protection", 5: "Secure Launch",
                         6: "SMM Firmware Measurement", 7: "Kernel-mode Hardware-enforced Stack Protection"}
DEVICE_GUARD_AVAILABLE = {1: "Secure Boot", 2: "DMA Protection", 3: "UEFI Memory Attributes Table",
                          4: "Secure Memory Overwrite", 5: "Kernel DMA Protection",
                          6: "Virtualization-based Security", 7: "HVCI", 8: "Credential Guard",
                          9: "Secure Launch", 10: "SMM Firmware Measurement"}

# --- accessibility ------------------------------------------------------------

_ACC_FLAGS = {0x01: "Enabled", 0x02: "Available", 0x04: "Hotkey activation enabled",
              0x08: "Confirm hotkey activation", 0x10: "Hotkey activation warning sound",
              0x20: "Visual indicator"}


def accessibility_flags(value) -> dict:
    n = to_int(value, 0)
    return {name: ("Yes" if n & bit else "No") for bit, name in _ACC_FLAGS.items()}


# --- system ------------------------------------------------------------------

CHASSIS_TYPES = {
    1: "Other", 2: "Unknown", 3: "Desktop", 4: "Low Profile Desktop", 5: "Pizza Box",
    6: "Mini Tower", 7: "Tower", 8: "Portable", 9: "Laptop", 10: "Notebook", 11: "Hand Held",
    12: "Docking Station", 13: "All in One", 14: "Sub Notebook", 15: "Space-Saving",
    16: "Lunch Box", 17: "Main System Chassis", 18: "Expansion Chassis", 19: "SubChassis",
    20: "Bus Expansion Chassis", 21: "Peripheral Chassis", 22: "Storage Chassis",
    23: "Rack Mount Chassis", 24: "Sealed-Case PC", 30: "Tablet", 31: "Convertible",
    32: "Detachable", 35: "Mini PC", 36: "Stick PC",
}

PC_SYSTEM_TYPES = {0: "Unspecified", 1: "Desktop", 2: "Mobile", 3: "Workstation",
                   4: "Enterprise Server", 5: "SOHO Server", 6: "Appliance PC",
                   7: "Performance Server", 8: "Maximum"}

DOMAIN_ROLES = {0: "Standalone Workstation", 1: "Member Workstation", 2: "Standalone Server",
                3: "Member Server", 4: "Backup Domain Controller", 5: "Primary Domain Controller"}

POWER_PLATFORM_ROLES = {0: "Unspecified", 1: "Desktop", 2: "Mobile", 3: "Workstation",
                        4: "Enterprise Server", 5: "SOHO Server", 6: "Appliance PC",
                        7: "Performance Server", 8: "Slate"}

# --- memory ------------------------------------------------------------------

MEMORY_TYPES = {
    0: "Unknown", 1: "Other", 2: "DRAM", 3: "Synchronous DRAM", 4: "Cache DRAM", 5: "EDO",
    6: "EDRAM", 7: "VRAM", 8: "SRAM", 9: "RAM", 10: "ROM", 11: "Flash", 12: "EEPROM",
    13: "FEPROM", 14: "EPROM", 15: "CDRAM", 16: "3DRAM", 17: "SDRAM", 18: "SGRAM",
    19: "RDRAM", 20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM", 24: "DDR3", 25: "FBD2",
    26: "DDR4", 27: "LPDDR", 28: "LPDDR2", 29: "LPDDR3", 30: "LPDDR4", 31: "Logical non-volatile",
    32: "HBM", 33: "HBM2", 34: "DDR5", 35: "LPDDR5", 36: "HBM3",
}

FORM_FACTORS = {0: "Unknown", 1: "Other", 2: "SIP", 3: "DIP", 4: "ZIP", 5: "SOJ", 6: "Proprietary",
                7: "SIMM", 8: "DIMM", 9: "TSOP", 10: "PGA", 11: "RIMM", 12: "SODIMM",
                13: "SRIMM", 14: "SMD", 15: "SSMP", 16: "QFP", 17: "TQFP", 18: "SOIC",
                19: "LCC", 20: "PLCC", 21: "BGA", 22: "FPBGA", 23: "LGA", 24: "FB-DIMM"}

TYPE_DETAIL = {1: "Reserved", 2: "Other", 4: "Unknown", 8: "Fast-paged", 16: "Static column",
               32: "Pseudo-static", 64: "RAMBUS", 128: "Synchronous", 256: "CMOS", 512: "EDO",
               1024: "Window DRAM", 2048: "Cache DRAM", 4096: "Non-volatile", 8192: "Registered (Buffered)",
               16384: "Unbuffered (Unregistered)", 32768: "LRDIMM"}

ERROR_CORRECTION = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "None", 4: "Parity",
                    5: "Single-bit ECC", 6: "Multi-bit ECC", 7: "CRC"}

# --- cpu ---------------------------------------------------------------------

CPU_ARCHITECTURE = {0: "x86", 1: "MIPS", 2: "Alpha", 3: "PowerPC", 5: "ARM", 6: "ia64",
                    9: "x64", 12: "ARM64"}

CACHE_LEVEL = {3: "L1", 4: "L2", 5: "L3"}

CACHE_ASSOCIATIVITY = {1: "Other", 2: "Unknown", 3: "Direct Mapped", 4: "2-way", 5: "4-way",
                       6: "Fully Associative", 7: "8-way", 8: "16-way", 9: "12-way", 10: "24-way",
                       11: "32-way", 12: "48-way", 13: "64-way", 14: "20-way"}

CACHE_TYPE = {1: "Other", 2: "Unknown", 3: "Instruction", 4: "Data", 5: "Unified"}

CPU_STATUS = {0: "Unknown", 1: "Enabled", 2: "Disabled by user", 3: "Disabled by BIOS",
              4: "Idle", 7: "Other"}

# --- bios --------------------------------------------------------------------

_BIOS_CHARACTERISTICS = {
    0: "Reserved", 1: "Reserved", 2: "Unknown", 3: "BIOS characteristics not supported",
    4: "ISA is supported", 5: "MCA is supported", 6: "EISA is supported", 7: "Supports PCI",
    8: "Supports PC Card (PCMCIA)", 9: "Supports Plug and Play", 10: "Supports APM",
    11: "Upgradeable (Flash) BIOS", 12: "Allows BIOS shadowing", 13: "Supports VL-VESA",
    14: "ESCD support is available", 15: "Supports booting from CD-ROM", 16: "Supports selectable boot",
    17: "BIOS ROM is socketed", 18: "Supports booting from PC Card (PCMCIA)",
    19: "Supports Enhanced Disk Drive specification", 20: "Supports INT 13 NEC 9800 1.2M floppy",
    21: "Supports INT 13 Toshiba 1.2M floppy", 22: "Supports INT 13 5.25-inch/360K floppy",
    23: "Supports INT 13 5.25-inch/1.2M floppy", 24: "Supports INT 13 3.5-inch/720K floppy",
    25: "Supports INT 13 3.5-inch/2.88M floppy", 26: "Supports INT 05 print-screen",
    27: "Supports INT 09 and 8042 keyboard services", 28: "Supports INT 14 serial services",
    29: "Supports INT 17 printer services", 30: "Supports INT 10 CGA/Mono video services",
    31: "NEC PC-98", 32: "Supports ACPI", 33: "Supports legacy USB", 34: "Supports AGP",
    35: "Supports booting from I2O device", 36: "Supports booting from LS-120",
    37: "Supports booting from ATAPI ZIP drive", 38: "Supports booting from IEEE 1394 device",
    39: "Smart Battery supported",
}


def bios_characteristics(codes) -> str:
    names = []
    for code in codes or []:
        n = to_int(code)
        if n is None:
            continue
        # SMBIOS reserves bits 40-47 for the vendor; report the number rather than a guessed name.
        if n >= 40:
            names.append(f"Reserved ({n})")
        else:
            names.append(_BIOS_CHARACTERISTICS.get(n, f"Reserved ({n})"))
    return ", ".join(names)


# --- devices -----------------------------------------------------------------

PNP_ERROR_CODES = {
    0: "Working properly", 1: "Not configured correctly", 2: "Cannot load the driver",
    3: "Driver may be corrupted or the system is low on resources", 4: "Driver or registry may be corrupted",
    5: "Needs a resource Windows cannot manage", 6: "Boot configuration conflicts with other devices",
    7: "Cannot filter", 8: "Driver loader is missing", 9: "Firmware is reporting resources incorrectly",
    10: "Cannot start", 11: "Failed", 12: "Not enough free resources", 13: "Cannot verify resources",
    14: "Cannot work until the computer restarts", 15: "Re-enumeration problem",
    16: "Cannot identify all resources", 17: "Asking for an unknown resource type",
    18: "Drivers must be reinstalled", 19: "Registry may be corrupted", 20: "VxD loader failure",
    21: "System failure; try changing the driver", 22: "Disabled", 23: "System failure; try changing the driver",
    24: "Not present, not working properly, or drivers missing", 25: "Windows is still setting up",
    26: "Windows is still setting up", 27: "No valid log configuration", 28: "Drivers not installed",
    29: "Disabled by firmware", 30: "Using an IRQ another device is using", 31: "Cannot load the required drivers",
    32: "Driver start type is disabled", 33: "Cannot determine which resources are required",
    34: "Requires manual configuration", 35: "Firmware lacks resources for this device",
    36: "IRQ translation failed", 37: "Driver returned failure from DriverEntry",
    38: "A previous driver instance is still in memory", 39: "Driver is corrupted or missing",
    40: "Registry service key information is invalid", 41: "Driver loaded but device not found",
    42: "Duplicate device detected", 43: "Driver reported a device failure", 44: "Stopped by an application or service",
    45: "Not connected", 46: "Not available while Windows shuts down", 47: "Prepared for safe removal",
    48: "Blocked from starting because of known problems", 49: "System hive too large",
    50: "Failed to apply one or more properties", 51: "Waiting on another device",
    52: "Driver signature cannot be verified", 53: "Reserved by the debugger", 54: "Failed and is undergoing a reset",
}

SLOT_USAGE = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "Available", 4: "In use"}

SLOT_MAX_DATA_WIDTH = {0: "8 bit", 1: "16 bit", 2: "32 bit", 3: "64 bit", 4: "128 bit",
                       5: "x1", 6: "x2", 7: "x4", 8: "x8", 9: "x12", 10: "x16", 11: "x32"}

DRIVE_TYPES = {0: "Unknown", 1: "No root directory", 2: "Removable", 3: "Local disk",
               4: "Network drive", 5: "CD-ROM", 6: "RAM disk"}

VIDEO_ARCHITECTURE = {1: "Other", 2: "Unknown", 3: "CGA", 4: "EGA", 5: "VGA", 6: "SVGA", 7: "MDA",
                      8: "HGC", 9: "MCGA", 10: "8514A", 11: "XGA", 12: "Linear Frame Buffer",
                      160: "PC-98"}

AVAILABILITY = {1: "Other", 2: "Unknown", 3: "Running / Full power", 4: "Warning", 5: "In test",
                6: "Not applicable", 7: "Power off", 8: "Off line", 9: "Off duty", 10: "Degraded",
                11: "Not installed", 12: "Install error", 13: "Power save - unknown",
                14: "Power save - low power", 15: "Power save - standby", 16: "Power cycle",
                17: "Power save - warning", 18: "Paused", 19: "Not ready", 20: "Not configured",
                21: "Quiesced"}

PRINTER_STATUS = {1: "Other", 2: "Unknown", 3: "Idle", 4: "Printing", 5: "Warming up",
                  6: "Stopped printing", 7: "Offline"}

NET_CONNECTION_STATUS = {0: "Disconnected", 1: "Connecting", 2: "Connected", 3: "Disconnecting",
                         4: "Hardware not present", 5: "Hardware disabled", 6: "Hardware malfunction",
                         7: "Media disconnected", 8: "Authenticating", 9: "Authentication succeeded",
                         10: "Authentication failed", 11: "Invalid address", 12: "Credentials required"}

PORT_CONNECTOR_TYPES = {
    0: "Unknown", 1: "Other", 2: "Male", 3: "Female", 4: "Shielded", 5: "Unshielded", 6: "SCSI (A) High-Density",
    7: "SCSI (A) Low-Density", 8: "SCSI (P) High-Density", 9: "SCSI SCA-I", 10: "SCSI SCA-II",
    11: "Fibre Channel (DB-9)", 12: "Fibre Channel Optical", 13: "Fibre Channel SCA-II", 14: "Fibre Channel SSA",
    15: "Fibre Channel Copper", 16: "Fibre Channel Optical", 17: "Fibre Channel Style-2", 18: "Fibre Channel SCA-II",
    19: "Fibre Channel Copper", 20: "Fibre Channel Optical", 21: "PCI", 22: "ISA", 23: "EISA",
    24: "VESA", 25: "MCA", 26: "PCMCIA", 27: "Centronics", 28: "Mini-Centronics", 29: "DB-9", 30: "DB-15",
    31: "DB-25", 32: "DB-37", 33: "DB-50", 34: "ACR", 35: "CardBus", 36: "IEEE-1394", 37: "PS/2",
    38: "Infrared", 39: "HP-HIL", 40: "Access Bus (USB)", 41: "SSA SCSI", 42: "Circular DIN-8 Male",
    43: "Circular DIN-8 Female", 44: "On Board IDE", 45: "On Board Floppy", 46: "9 Pin Dual Inline",
    47: "25 Pin Dual Inline", 48: "50 Pin Dual Inline", 49: "68 Pin Dual Inline", 50: "On Board Sound Input from CD-ROM",
    51: "Mini-Centronics Type-14", 52: "Mini-Centronics Type-26", 53: "Mini-Jack (headphones)", 54: "BNC",
    55: "1394", 56: "PC-98", 57: "PC-98Hireso", 58: "PC-H98", 59: "PC-98Note", 60: "PC-98Full",
    61: "SAS/SATA Plug Receptacle", 62: "USB Type-C", 63: "USB Type-A", 64: "USB Type-B", 65: "USB Type-C Receptacle",
    255: "Other", 160: "RJ-45", 161: "RJ-11", 162: "DVI", 163: "HDMI", 164: "DisplayPort",
}

PORT_TYPES = {0: "None", 1: "Parallel Port XT/AT Compatible", 2: "Parallel Port PS/2", 3: "Parallel Port ECP",
              4: "Parallel Port EPP", 5: "Parallel Port ECP/EPP", 6: "Serial Port XT/AT Compatible",
              7: "Serial Port 16450 Compatible", 8: "Serial Port 16550 Compatible", 9: "Serial Port 16550A Compatible",
              10: "SCSI Port", 11: "MIDI Port", 12: "Joy Stick Port", 13: "Keyboard Port", 14: "Mouse Port",
              15: "SSA SCSI", 16: "USB", 17: "FireWire (IEEE P1394)", 18: "PCMCIA Type I", 19: "PCMCIA Type II",
              20: "PCMCIA Type III", 21: "Cardbus", 22: "Access Bus Port", 23: "SCSI II", 24: "SCSI Wide",
              25: "PC-98", 26: "PC-98-Hireso", 27: "PC-H98", 28: "Video Port", 29: "Audio Port", 30: "Modem Port",
              31: "Network Port", 32: "SATA", 33: "SAS", 34: "MFDP (Multi-Function Display Port)",
              35: "Thunderbolt", 160: "8251 Compatible", 161: "8251 FIFO Compatible", 255: "Other"}

# --- windows update ----------------------------------------------------------

WU_OPERATION = {1: "Installation", 2: "Uninstallation", 3: "Other"}
WU_RESULT = {0: "Not started", 1: "In progress", 2: "Succeeded", 3: "Succeeded with errors",
             4: "Failed", 5: "Aborted"}

# --- pci vendors -------------------------------------------------------------

_PCI_VENDORS = {
    "8086": "Intel Corporation", "10DE": "NVIDIA Corporation", "1002": "Advanced Micro Devices (ATI)",
    "1022": "Advanced Micro Devices", "10EC": "Realtek Semiconductor", "14E4": "Broadcom",
    "11AB": "Marvell Technology", "1B4B": "Marvell Technology", "17CB": "Qualcomm", "168C": "Qualcomm Atheros",
    "1969": "Qualcomm Atheros", "10B5": "PLX Technology", "1106": "VIA Technologies", "1039": "Silicon Integrated Systems",
    "104C": "Texas Instruments", "1180": "Ricoh", "1217": "O2 Micro", "1033": "NEC", "1912": "Renesas",
    "1B21": "ASMedia Technology", "1B73": "Fresco Logic", "1AF4": "Red Hat (virtio)", "15AD": "VMware",
    "80EE": "Oracle (VirtualBox)", "1414": "Microsoft", "5333": "S3 Graphics", "102B": "Matrox",
    "1AF1": "Euresys", "1C6C": "Silicom", "15B3": "Mellanox", "144D": "Samsung Electronics",
    "1987": "Phison Electronics", "1E0F": "Kioxia", "1C5C": "SK hynix", "15B7": "Sandisk / Western Digital",
    "1179": "Toshiba", "1CC1": "ADATA", "126F": "Silicon Motion", "1E49": "Yangtze Memory (YMTC)",
    "1D6A": "Aquantia", "1FC9": "Tehuti Networks", "1077": "QLogic", "1000": "Broadcom / LSI",
    "9005": "Adaptec", "1B85": "OCZ", "1344": "Micron Technology", "1E4B": "Maxio Technology",
    "1D79": "Transcend", "8087": "Intel Corporation", "1013": "Cirrus Logic", "1102": "Creative Labs",
    "13F6": "C-Media", "1412": "VIA (ICE)", "1B96": "Western Digital", "1E95": "Solid State Storage Technology",
}


def pci_vendor(vendor_id) -> str:
    vid = str(vendor_id or "").upper().replace("0X", "")
    return _PCI_VENDORS.get(vid, f"Vendor {vid}" if vid else "")
```

- [ ] **Step 8: Write `pc_report/registry.py` and `pc_report/sections/__init__.py`**

`pc_report/sections/__init__.py`:

```python
"""One module per report section. Each exposes a ``SECTION`` object; see pc_report.section."""
```

`pc_report/registry.py`:

```python
"""The ordered list of report sections and the option keys that switch them.

``ORDER`` is the page order and the only place it is defined. A section
module that is not yet written is simply absent from ``SECTIONS``.
"""
from __future__ import annotations

import importlib
import pkgutil

from . import sections as _pkg
from .section import GROUPS, Section

ORDER: tuple[str, ...] = (
    "noldus_summary",
    "operating_system", "installed_updates", "licenses", "system_directories", "system_files",
    "installed_programs", "security", "accessibility", "environment", "regional_settings",
    "processes", "services", "drivers", "autorun", "codecs", "mmc_snapins",
    "system_summary", "motherboard", "bios", "cpu", "memory", "sensors", "devices", "pci",
    "system_slots", "network_adapters", "video", "monitors", "sound", "storage_devices",
    "logical_disks", "ports", "usb", "printers", "virtual_machine", "cameras",
    "network_information", "shares", "network_connections",
)

# Option keys the dialog (and older callers) pass that map onto several or renamed sections.
ALIASES: dict[str, tuple[str, ...]] = {
    "hardware": ("system_summary", "motherboard", "bios", "cpu", "memory", "video", "sound",
                 "storage_devices", "logical_disks"),
    "network": ("network_adapters", "shares"),
    "noldus_nvc_report": ("noldus_summary",),
    "network_info": ("network_information",),
    "autoruns": ("autorun",),
    "snapins": ("mmc_snapins",),
    "slots": ("system_slots",),
}


def _discover() -> list[Section]:
    found = []
    for module_info in pkgutil.iter_modules(_pkg.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{_pkg.__name__}.{module_info.name}")
        section = getattr(module, "SECTION", None)
        if isinstance(section, Section):
            found.append(section)
    unknown = [s.key for s in found if s.key not in ORDER]
    if unknown:
        raise RuntimeError(f"sections not in registry.ORDER: {unknown}")
    return sorted(found, key=lambda s: ORDER.index(s.key))


SECTIONS: tuple[Section, ...] = tuple(_discover())


def by_key(key: str, sections=None) -> Section | None:
    for section in (sections if sections is not None else SECTIONS):
        if section.key == key:
            return section
    return None


def grouped(sections=None) -> dict[str, list[Section]]:
    out: dict[str, list[Section]] = {group: [] for group in GROUPS}
    for section in (sections if sections is not None else SECTIONS):
        out.setdefault(section.group, []).append(section)
    return out


def is_enabled(section: Section, options: dict) -> bool:
    if section.key in options:
        return bool(options[section.key])
    for alias, targets in ALIASES.items():
        if section.key in targets and alias in options:
            return bool(options[alias])
    return section.default_on


def select(options: dict, sections=None) -> list[Section]:
    options = options or {}
    return [s for s in (sections if sections is not None else SECTIONS) if is_enabled(s, options)]
```

- [ ] **Step 9: Replace `pc_report/utils.py` with re-exports**

```python
"""Compatibility shims. New code imports from pc_report.ps and pc_report.format."""
from .format import bitrate_to_mbps, bytes_human  # noqa: F401
from .ps import run_ps_json  # noqa: F401
```

- [ ] **Step 10: Run the new tests and the old suite**

Run: `python -m pytest tests/pc_report -q`
Expected: all pass.

Run: `python -m pytest tests/test_pc_report_orchestration.py -q`
Expected: pass. `TimeoutLocationTests.test_a_slow_collector_is_bounded_by_the_subprocess_timeout` reads `pcutils.run_ps_json.__defaults__[0]`; the re-export keeps it working. `PowerShellJsonTests` patch `pcutils.subprocess` — `pc_report.utils` no longer has a `subprocess` attribute, so those eight tests fail with `AttributeError`. Change their patch target: in `tests/test_pc_report_orchestration.py` add `from pc_report import ps as pcps` and replace every `patch.object(pcutils.subprocess, "run", ...)` with `patch.object(pcps.subprocess, "run", ...)`. Also change `test_the_script_is_piped_through_convertto_json` to assert `"Get-Process" in joined` and `"ConvertTo-Json" in joined` only (drop nothing else; the `-NonInteractive`/`-NoProfile` assertions still hold). Re-run; expected pass.

- [ ] **Step 11: Lint and commit**

```bash
python -m ruff check pc_report tests/pc_report
git add pc_report tests/pc_report tests/test_pc_report_orchestration.py
git commit -m "refactor(pc_report): add section, format, ps, decode and registry foundations"
```

### Task 2: Fixture contexts and the capture script

**Files:**
- Create: `tests/pc_report/support.py`
- Create: `scripts/dev/capture_pc_report_fixtures.py`
- Create: `tests/fixtures/pc_report/.gitkeep`
- Test: `tests/pc_report/test_support.py`

**Interfaces:**
- Consumes: `SectionContext`, `RunContext`, `SharedSources`, `REQUIRES_ADMIN`, `RenderContext`, `is_partial` from Task 1.
- Produces: `FixtureSectionContext(section, is_admin=False, results=None, root=FIXTURES)`, `RecordingSectionContext(run, section, root, redact, scrub)`, `render_ctx(redact=True, meta=None)`, `assert_renders_empty(testcase, section)`, `collect_and_render(section, is_admin=False, results=None) -> (data, html, ctx)`, `FIXTURES: Path`, `safe_name(name)`. The capture CLI: `python scripts/dev/capture_pc_report_fixtures.py [--section KEY ...] [--out DIR]`.

- [ ] **Step 1: Write the failing tests**

`tests/pc_report/test_support.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from pc_report.section import REQUIRES_ADMIN, RunContext, Section, SharedSources
from tests.pc_report import support


def _section(key="demo", collect=None):
    return Section(key=key, title="Demo", group="Software",
                   collect=collect or (lambda ctx: {}), render=lambda d, c: "")


class FixtureContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "demo").mkdir()
        (self.root / "demo" / "os.json").write_text('{"Caption": "Windows"}', encoding="utf-8")
        (self.root / "demo" / "netsh_wlan.txt").write_text("SSID : lab", encoding="utf-8")
        (self.root / "_shared").mkdir()
        (self.root / "_shared" / "dxdiag.json").write_text('{"DxDiag": 1}', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_json_and_text_by_query_name(self):
        ctx = support.FixtureSectionContext(_section(), root=self.root)
        self.assertEqual(ctx.query("os", "Get-CimInstance ..."), {"Caption": "Windows"})
        self.assertEqual(ctx.text("netsh wlan", ["netsh", "wlan"]), "SSID : lab")
        self.assertEqual(ctx.shared("dxdiag"), {"DxDiag": 1})
        self.assertEqual(ctx.requested, ["os", "netsh wlan", "dxdiag"])

    def test_missing_fixture_is_none_with_a_note(self):
        ctx = support.FixtureSectionContext(_section(), root=self.root)
        self.assertIsNone(ctx.query("absent", "x"))
        self.assertEqual(ctx.text("absent txt", ["x"]), "")
        self.assertTrue(any(n.startswith("absent: no fixture") for n in ctx.notes))

    def test_admin_query_respects_flag(self):
        ctx = support.FixtureSectionContext(_section(), root=self.root)
        self.assertEqual(ctx.admin_query("os", "x"), REQUIRES_ADMIN)
        ctx = support.FixtureSectionContext(_section(), is_admin=True, root=self.root)
        self.assertEqual(ctx.admin_query("os", "x"), {"Caption": "Windows"})

    def test_results_are_visible_to_dependent_sections(self):
        ctx = support.FixtureSectionContext(_section(), results={"cpu": {"data": {"n": 1}, "notes": []}},
                                            root=self.root)
        self.assertEqual(ctx.result("cpu"), {"n": 1})

    def test_query_names_are_made_filesystem_safe(self):
        self.assertEqual(support.safe_name("Win32 Bios/version"), "Win32_Bios_version")


class RecordingContextTests(unittest.TestCase):
    def test_records_redacted_and_scrubbed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = RunContext(options={}, is_admin=False, results={},
                             shared=SharedSources({"dxdiag": lambda: ({"Machine": "LAB-PC-01"}, None)}),
                             runner=lambda s, t: ({"SerialNumber": "ABC123456", "Host": "LAB-PC-01"}, None),
                             text_runner=lambda a, t: ("host LAB-PC-01", None))
            redact = lambda v: {**v, "SerialNumber": "masked"} if isinstance(v, dict) else v  # noqa: E731
            scrub = lambda text: text.replace("LAB-PC-01", "PC-NAME")  # noqa: E731
            ctx = support.RecordingSectionContext(run, _section(), root, redact, scrub)

            ctx.query("os", "x")
            ctx.text("netsh", ["netsh"])
            ctx.shared("dxdiag")
            self.assertEqual(ctx.admin_query("bitlocker", "x"), REQUIRES_ADMIN)

            saved = json.loads((root / "demo" / "os.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, {"SerialNumber": "masked", "Host": "PC-NAME"})
            self.assertEqual((root / "demo" / "netsh.txt").read_text(encoding="utf-8"), "host PC-NAME")
            self.assertEqual(json.loads((root / "_shared" / "dxdiag.json").read_text(encoding="utf-8")),
                             {"Machine": "PC-NAME"})
            self.assertFalse((root / "demo" / "bitlocker.json").exists())


class HelperTests(unittest.TestCase):
    def test_assert_renders_empty_passes_for_a_tolerant_section(self):
        support.assert_renders_empty(self, _section())

    def test_collect_and_render_uses_fixtures_and_redacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo").mkdir()
            (root / "demo" / "q.json").write_text('{"SerialNumber": "ABCDEFGH"}', encoding="utf-8")
            import dataclasses
            section = dataclasses.replace(_section(collect=lambda ctx: ctx.query("q", "x")),
                                          render=lambda d, c: str(d))
            data, html, ctx = support.collect_and_render(section, root=root)
        self.assertEqual(data, {"SerialNumber": "ABCDEFGH"})
        self.assertNotIn("ABCDEFGH", html)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/pc_report/test_support.py -q`
Expected: `ModuleNotFoundError: No module named 'tests.pc_report.support'`.

- [ ] **Step 3: Write `tests/pc_report/support.py`**

```python
"""Fixture-backed contexts so section tests never spawn PowerShell or dxdiag."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pc_report.privacy import redact_payload
from pc_report.section import (REQUIRES_ADMIN, RenderContext, RunContext, SectionContext,
                               SharedSources, is_partial)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pc_report"
SHARED_DIR = "_shared"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _refuse(*_args, **_kwargs):
    raise AssertionError("a section test tried to run a real command; add a fixture instead")


class FixtureSectionContext(SectionContext):
    """Serves recorded results by query name from ``<root>/<section>/<name>.json|.txt``."""

    def __init__(self, section, is_admin=False, results=None, root: Path = FIXTURES):
        run = RunContext(options={}, is_admin=is_admin, results=results or {},
                         shared=SharedSources({}), runner=_refuse, text_runner=_refuse)
        super().__init__(run, section)
        self.dir = Path(root) / section.key
        self.shared_dir = Path(root) / SHARED_DIR
        self.requested: list[str] = []

    def _load(self, directory: Path, name: str, suffix: str):
        self.requested.append(name)
        path = directory / f"{safe_name(name)}{suffix}"
        if not path.exists():
            self.note(f"{name}: no fixture {path.name}")
            return None
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if suffix == ".json" else text

    def query(self, name, script, timeout=None):
        return self._load(self.dir, name, ".json")

    def text(self, name, args, timeout=None):
        return self._load(self.dir, name, ".txt") or ""

    def admin_query(self, name, script, timeout=None):
        if not self.is_admin:
            self.note(f"{name}: requires administrator")
            return REQUIRES_ADMIN
        return self.query(name, script, timeout)

    def shared(self, name):
        return self._load(self.shared_dir, name, ".json")


class RecordingSectionContext(SectionContext):
    """Runs real queries and writes each result to the fixture folder, redacted and scrubbed.

    Admin-only queries are recorded only when the capture itself runs elevated.
    """

    def __init__(self, run, section, root: Path, redact, scrub):
        super().__init__(run, section)
        self.dir = Path(root) / section.key
        self.shared_dir = Path(root) / SHARED_DIR
        self.redact = redact
        self.scrub = scrub

    def _save(self, directory: Path, name: str, value, suffix: str):
        directory.mkdir(parents=True, exist_ok=True)
        if suffix == ".json":
            text = json.dumps(self.redact(value), indent=1, default=str)
        else:
            text = value or ""
        (directory / f"{safe_name(name)}{suffix}").write_text(self.scrub(text), encoding="utf-8")

    def query(self, name, script, timeout=None):
        data = super().query(name, script, timeout)
        self._save(self.dir, name, data, ".json")
        return data

    def text(self, name, args, timeout=None):
        out = super().text(name, args, timeout)
        self._save(self.dir, name, out, ".txt")
        return out

    def shared(self, name):
        value = super().shared(name)
        self._save(self.shared_dir, name, value, ".json")
        return value


def render_ctx(redact=True, meta=None) -> RenderContext:
    return RenderContext(redact=redact, meta=meta or {})


def assert_renders_empty(testcase, section):
    """Every render must tolerate nothing, an empty dict, an empty list and a partial placeholder."""
    ctx = render_ctx()
    for payload in ({}, None, [], {"status": "partial", "error": "x"}):
        out = section.render(None if is_partial(payload) else payload, ctx)
        testcase.assertIsInstance(out, str, f"{section.key} render returned non-str for {payload!r}")


def collect_and_render(section, is_admin=False, results=None, root: Path = FIXTURES):
    """Collect from fixtures, redact, render; return ``(data, html, ctx)``."""
    ctx = FixtureSectionContext(section, is_admin=is_admin, results=results, root=root)
    data = section.collect(ctx)
    html = section.render(redact_payload(data, {"redact": True}), render_ctx())
    return data, html, ctx
```

- [ ] **Step 4: Write `scripts/dev/capture_pc_report_fixtures.py`**

```python
"""Record redacted PC report fixtures from this machine.

Usage:
    python scripts/dev/capture_pc_report_fixtures.py                  # every section
    python scripts/dev/capture_pc_report_fixtures.py --section cpu memory
    python scripts/dev/capture_pc_report_fixtures.py --out D:\\tmp\\fixtures

Each named query a section issues is written to
tests/fixtures/pc_report/<section>/<query>.json after redact_payload and a
scrub that replaces this machine's name, user name and domain. Review the
files before committing them anyway. Run once elevated to record the
admin-only queries too.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pc_report import ps, registry  # noqa: E402
from pc_report.privacy import redact_payload  # noqa: E402
from pc_report.section import RunContext, SharedSources, is_user_admin, wrap  # noqa: E402
from tests.pc_report.support import FIXTURES, RecordingSectionContext  # noqa: E402


def make_scrub():
    replacements = []
    for value, token in (
        (os.environ.get("COMPUTERNAME"), "PC-NAME"),
        (getpass.getuser(), "user"),
        (os.environ.get("USERDNSDOMAIN"), "example.local"),
        (os.environ.get("USERDOMAIN"), "WORKGROUP"),
    ):
        if value and len(value) >= 3 and value.upper() != "WORKGROUP":
            replacements.append((re.compile(re.escape(value), re.IGNORECASE), token))

    def scrub(text: str) -> str:
        for pattern, token in replacements:
            text = pattern.sub(token, text)
        return text

    return scrub


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--section", nargs="*", default=[], help="section keys; default is every section")
    parser.add_argument("--out", default=str(FIXTURES), help="fixture root")
    args = parser.parse_args(argv)

    if args.section:
        sections = []
        for key in args.section:
            section = registry.by_key(key)
            if section is None:
                parser.error(f"unknown section {key!r}; known: {', '.join(s.key for s in registry.SECTIONS)}")
            sections.append(section)
    else:
        sections = list(registry.SECTIONS)
    # Sections that read others' results go last so their inputs exist.
    sections.sort(key=lambda s: (bool(s.after), registry.ORDER.index(s.key)))

    run = RunContext(options={}, is_admin=is_user_admin(), results={},
                     shared=SharedSources(ps.SHARED_LOADERS),
                     runner=ps.run_ps_json, text_runner=ps.run_text)
    scrub = make_scrub()
    redact = lambda value: redact_payload(value, {"redact": True})  # noqa: E731
    print(f"elevated: {run.is_admin}; writing to {args.out}")
    for section in sections:
        ctx = RecordingSectionContext(run, section, Path(args.out), redact, scrub)
        started = time.monotonic()
        try:
            data = section.collect(ctx)
        except Exception as exc:  # keep capturing the rest
            print(f"{section.key}: FAILED {exc}")
            continue
        run.results[section.key] = wrap(data, ctx.notes)
        print(f"{section.key}: {time.monotonic() - started:.1f} s, {len(ctx.notes)} note(s)")
        for note in ctx.notes:
            print(f"   - {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Create `tests/fixtures/pc_report/.gitkeep` (empty).

- [ ] **Step 5: Run tests, lint, commit**

Run: `python -m pytest tests/pc_report -q`
Expected: pass.

```bash
python -m ruff check tests/pc_report scripts/dev/capture_pc_report_fixtures.py
git add tests/pc_report/support.py tests/pc_report/test_support.py scripts/dev/capture_pc_report_fixtures.py tests/fixtures/pc_report/.gitkeep
git commit -m "test(pc_report): fixture-backed section contexts and a capture script"
```

---

### Task 3: Orchestrator over the registry

**Files:**
- Modify: `pc_report/orchestrator.py` (rewrite)
- Modify: `tests/test_pc_report_orchestration.py` (rewrite `RunAllTests`; keep the other classes)

**Interfaces:**
- Consumes: `registry.select`, `registry.SECTIONS`, `RunContext`, `SectionContext`, `SharedSources`, `wrap`, `is_user_admin`, `ps.SHARED_LOADERS`, `ps.run_ps_json`, `ps.run_text`.
- Produces: `run_all(options, progress_cb=None, sections=None, runner=None, text_runner=None, shared_loaders=None, is_admin=None) -> (meta, results, errors)`. `meta` keys: `generated_at`, `machine`, `nvc_version`, `elevated`, `elapsed_by_section`, `total_seconds`. Each `results[key]` is `{"data", "notes"}` or the partial placeholder. `progress_cb(title, completed, total)`.

- [ ] **Step 1: Rewrite `RunAllTests` in `tests/test_pc_report_orchestration.py`**

Replace the whole `RunAllTests` class (keep the module docstring updated to say "sections" instead of "collectors", and keep `TimeoutLocationTests`, `ByteFormattingTests`, `BitrateTests`, `PowerShellJsonTests`):

```python
from pc_report import registry
from pc_report.section import Section


def _fake(key, group="Software", collect=None, after=(), default_on=True):
    return Section(key=key, title=key.replace("_", " ").title(), group=group,
                   collect=collect or (lambda ctx: {"ok": key}), render=lambda d, c: "",
                   after=after, default_on=default_on)


class RunAllTests(unittest.TestCase):
    def _sections(self, **overrides):
        base = {
            "operating_system": _fake("operating_system"),
            "cpu": _fake("cpu", "Hardware"),
            "memory": _fake("memory", "Hardware"),
            "shares": _fake("shares", "Network"),
            "processes": _fake("processes"),
        }
        base.update(overrides)
        return list(base.values())

    def _run(self, options=None, progress_cb=None, sections=None, runner=None, **kw):
        return orchestrator.run_all(
            options or {}, progress_cb=progress_cb,
            sections=self._sections() if sections is None else sections,
            runner=runner or (lambda script, timeout: (None, None)),
            text_runner=lambda args, timeout: ("", None),
            shared_loaders=kw.pop("shared_loaders", {}), is_admin=kw.pop("is_admin", False))

    def test_every_section_runs_by_default_and_is_wrapped(self):
        meta, results, errors = self._run()
        self.assertEqual(errors, {})
        self.assertEqual(set(results), {"operating_system", "cpu", "memory", "shares", "processes"})
        self.assertEqual(results["cpu"], {"data": {"ok": "cpu"}, "notes": []})

    def test_a_section_can_be_switched_off(self):
        _meta, results, _errors = self._run({"processes": False, "shares": False})
        self.assertEqual(set(results), {"operating_system", "cpu", "memory"})

    def test_group_alias_switches_off_the_split_sections(self):
        _meta, results, _errors = self._run({"hardware": False})
        self.assertEqual(set(results), {"operating_system", "shares", "processes"})

    def test_switching_everything_off_produces_no_results(self):
        options = dict.fromkeys(("operating_system", "cpu", "memory", "shares", "processes"), False)
        meta, results, errors = self._run(options)
        self.assertEqual(results, {})
        self.assertEqual(errors, {})
        self.assertIn("generated_at", meta)

    def test_metadata(self):
        meta, _results, _errors = self._run()
        import datetime
        datetime.datetime.fromisoformat(meta["generated_at"])
        self.assertIn("machine", meta)
        self.assertEqual(meta["elevated"], False)
        self.assertEqual(set(meta["elapsed_by_section"]), {"operating_system", "cpu", "memory", "shares", "processes"})
        self.assertIsInstance(meta["total_seconds"], float)
        self.assertTrue(meta["nvc_version"])

    # -- failure isolation ----------------------------------------------
    def test_one_failing_section_does_not_lose_the_others(self):
        def exploding(ctx):
            raise RuntimeError("WMI is unavailable")
        _meta, results, errors = self._run(sections=self._sections(cpu=_fake("cpu", collect=exploding)))
        self.assertIn("WMI is unavailable", errors["cpu"])
        self.assertEqual(results["cpu"], {"status": "partial", "error": "WMI is unavailable"})
        self.assertEqual(len(results), 5)

    def test_several_failures_are_all_recorded(self):
        def exploding(ctx):
            raise OSError("nope")
        _meta, _results, errors = self._run(sections=self._sections(
            cpu=_fake("cpu", collect=exploding), memory=_fake("memory", collect=exploding)))
        self.assertEqual(set(errors), {"cpu", "memory"})

    def test_query_errors_become_notes_not_failures(self):
        def collect(ctx):
            return {"value": ctx.query("thing", "Get-Thing")}
        _meta, results, errors = self._run(sections=[_fake("cpu", collect=collect)],
                                           runner=lambda s, t: (None, "access denied"))
        self.assertEqual(errors, {})
        self.assertEqual(results["cpu"], {"data": {"value": None}, "notes": ["thing: access denied"]})

    # -- progress -------------------------------------------------------
    def test_progress_is_reported_once_per_section_with_titles(self):
        seen = []
        self._run(progress_cb=lambda name, done, total: seen.append((name, done, total)))
        self.assertEqual(len(seen), 5)
        self.assertEqual([d for _n, d, _t in seen], [1, 2, 3, 4, 5])
        self.assertTrue(all(t == 5 for _n, _d, t in seen))
        self.assertIn("Operating System", [n for n, _d, _t in seen])

    def test_progress_is_reported_for_failed_sections_too(self):
        def exploding(ctx):
            raise RuntimeError("x")
        seen = []
        self._run(progress_cb=lambda *a: seen.append(a),
                  sections=self._sections(cpu=_fake("cpu", collect=exploding)))
        self.assertEqual(len(seen), 5)

    def test_a_raising_progress_callback_does_not_break_the_report(self):
        def hostile(*_args):
            raise RuntimeError("the dialog closed")
        _meta, results, errors = self._run(progress_cb=hostile)
        self.assertEqual(len(results), 5)
        self.assertEqual(errors, {})

    # -- options reach the sections ---------------------------------------
    def test_sections_read_limits_from_ctx_options(self):
        captured = {}
        def collect(ctx):
            captured["limit"] = ctx.options.get("services_limit", 1000)
            return {}
        self._run({"services_limit": 7}, sections=[_fake("services", collect=collect)])
        self.assertEqual(captured["limit"], 7)
        self._run({}, sections=[_fake("services", collect=collect)])
        self.assertEqual(captured["limit"], 1000)

    # -- dependencies ------------------------------------------------------
    def test_after_sections_see_their_dependencies_results(self):
        def summary(ctx):
            return {"cpu_seen": ctx.result("cpu")}
        sections = [_fake("noldus_summary", "NVC", collect=summary, after=("cpu",)), _fake("cpu", "Hardware")]
        _meta, results, _errors = self._run(sections=sections)
        self.assertEqual(results["noldus_summary"]["data"], {"cpu_seen": {"ok": "cpu"}})

    def test_a_dependency_that_is_switched_off_counts_as_satisfied(self):
        def summary(ctx):
            return {"cpu_seen": ctx.result("cpu")}
        sections = [_fake("noldus_summary", "NVC", collect=summary, after=("cpu",)), _fake("cpu", "Hardware")]
        _meta, results, _errors = self._run({"cpu": False}, sections=sections)
        self.assertEqual(results["noldus_summary"]["data"], {"cpu_seen": None})

    def test_a_dependency_cycle_is_reported_not_hung(self):
        sections = [_fake("a", after=("b",)), _fake("b", after=("a",))]
        _meta, results, errors = self._run(sections=sections)
        self.assertEqual(set(errors), {"a", "b"})
        self.assertIn("never completed", results["a"]["error"])

    # -- shared sources ----------------------------------------------------
    def test_shared_sources_are_loaded_once_for_the_whole_run(self):
        calls = []
        def loader():
            calls.append(1)
            return {"dx": True}, None
        def uses_dx(ctx):
            return {"dx": ctx.shared("dxdiag")}
        sections = [_fake(k, "Hardware", collect=uses_dx) for k in ("video", "monitors", "sound", "cameras")]
        _meta, results, _errors = self._run(sections=sections, shared_loaders={"dxdiag": loader})
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(results[k]["data"] == {"dx": {"dx": True}} for k in ("video", "monitors", "sound", "cameras")))

    def test_shared_source_failure_degrades_to_notes(self):
        def loader():
            return None, "dxdiag timed out"
        def uses_dx(ctx):
            return {"dx": ctx.shared("dxdiag")}
        _meta, results, errors = self._run(sections=[_fake("video", "Hardware", collect=uses_dx)],
                                           shared_loaders={"dxdiag": loader})
        self.assertEqual(errors, {})
        self.assertEqual(results["video"]["notes"], ["dxdiag: dxdiag timed out"])

    # -- the real registry ----------------------------------------------------
    def test_every_registered_section_tolerates_an_offline_machine(self):
        """Every query answering (None, 'offline') must still yield a wrapped result, never a raise."""
        _meta, results, errors = orchestrator.run_all(
            {}, sections=registry.SECTIONS, runner=lambda s, t: (None, "offline"),
            text_runner=lambda a, t: ("", "offline"),
            shared_loaders={"dxdiag": lambda: (None, "offline"), "pnp_entities": lambda: (None, "offline")},
            is_admin=False)
        self.assertEqual(errors, {}, errors)
        self.assertEqual(set(results), {s.key for s in registry.SECTIONS})
```

Remove the old `_patch_collectors`/`_run`, `test_the_section_limits_are_passed_through`, and `test_the_limits_have_defaults` (replaced above). Keep `TimeoutLocationTests` but change its first test to:

```python
    def test_run_all_does_not_claim_a_timeout_it_cannot_enforce(self):
        import inspect
        source = inspect.getsource(orchestrator.run_all)
        self.assertNotIn("fut.result(timeout=", source)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pc_report_orchestration.py -q`
Expected: `TypeError: run_all() got an unexpected keyword argument 'sections'`.

- [ ] **Step 3: Rewrite `pc_report/orchestrator.py`**

```python
"""Runs every enabled section and assembles ``(meta, results, errors)``.

Sections without dependencies run first on a thread pool; a section that
names ``after`` keys is submitted once those have finished. A section that
raises becomes ``{"status": "partial", "error": ...}`` so the report still
renders. The only real time bound is the subprocess timeout inside each
query; see pc_report.ps.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime
import os
import time

from utils.logger import logger
from utils.version import APP_VERSION

from . import ps, registry
from .section import RunContext, SectionContext, SharedSources, is_user_admin, wrap

MAX_WORKERS = 6


def _collect_one(run: RunContext, section):
    started = time.monotonic()
    ctx = SectionContext(run, section)
    data = section.collect(ctx)
    return wrap(data, ctx.notes), time.monotonic() - started


def run_all(options: dict, progress_cb=None, sections=None, runner=None, text_runner=None,
            shared_loaders=None, is_admin=None):
    options = options or {}
    selected = registry.select(options, sections if sections is not None else registry.SECTIONS)
    selected_keys = {s.key for s in selected}
    run = RunContext(
        options=options,
        is_admin=is_user_admin() if is_admin is None else bool(is_admin),
        results={},
        shared=SharedSources(shared_loaders if shared_loaders is not None else ps.SHARED_LOADERS),
        runner=runner or ps.run_ps_json,
        text_runner=text_runner or ps.run_text,
    )
    results = run.results
    errors: dict[str, str] = {}
    elapsed: dict[str, float] = {}
    total = len(selected)
    completed = 0
    started_at = time.monotonic()

    def report(section):
        nonlocal completed
        completed += 1
        if progress_cb:
            try:
                progress_cb(section.title, completed, total)
            except Exception:
                logger.debug("run_all: progress callback failed", exc_info=True)

    def deps_done(section):
        return all(dep in results or dep not in selected_keys for dep in section.after)

    pending = list(selected)
    running: dict[cf.Future, object] = {}
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        while pending or running:
            for section in [s for s in pending if deps_done(s)]:
                pending.remove(section)
                running[ex.submit(_collect_one, run, section)] = section
            if not running:
                # Nothing can start: a dependency will never complete (cycle).
                for section in pending:
                    message = f"dependencies never completed: {', '.join(section.after)}"
                    results[section.key] = {"status": "partial", "error": message}
                    errors[section.key] = message
                    report(section)
                break
            done, _ = cf.wait(running, return_when=cf.FIRST_COMPLETED)
            for fut in done:
                section = running.pop(fut)
                try:
                    result, seconds = fut.result()
                except Exception as exc:
                    logger.warning("PC report section %s failed: %s", section.key, exc)
                    result, seconds = {"status": "partial", "error": str(exc)}, 0.0
                    errors[section.key] = str(exc)
                results[section.key] = result
                elapsed[section.key] = round(seconds, 2)
                report(section)

    meta = {
        "generated_at": datetime.datetime.now().isoformat(),
        "machine": os.environ.get("COMPUTERNAME", ""),
        "nvc_version": APP_VERSION,
        "elevated": run.is_admin,
        "elapsed_by_section": elapsed,
        "total_seconds": round(time.monotonic() - started_at, 2),
    }
    return meta, dict(results), errors
```

- [ ] **Step 4: Run, lint, commit**

Run: `python -m pytest tests/test_pc_report_orchestration.py tests/pc_report -q`
Expected: pass (the registry is still empty, so `test_every_registered_section_tolerates_an_offline_machine` passes trivially).

```bash
python -m ruff check pc_report tests
git add pc_report/orchestrator.py tests/test_pc_report_orchestration.py
git commit -m "refactor(pc_report): run sections from the registry with phases and shared sources"
```

---

### Task 4: Redaction for the new field families

**Files:**
- Modify: `pc_report/privacy.py` (rewrite)
- Modify: `tests/test_pc_report_privacy.py` (extend `PcReportPrivacyTests`; the `render_html` tests in that file are replaced in Task 5)

**Interfaces:**
- Produces: `redact_payload(data, options)`, `mask_string(value, keep=4)`, `mask_mac(mac)`, `mask_ip(value)`, `redact_user_paths(path)`, `SENSITIVE_TOKENS`, `IP_TOKENS`, `MAC_TOKENS`, `SENSITIVE_ENV_NAMES`, `norm_key(key)`.

- [ ] **Step 1: Add failing tests to `tests/test_pc_report_privacy.py`**

Add to `PcReportPrivacyTests`:

```python
    def test_new_identifying_fields_are_masked_by_human_label(self):
        payload = {"summary": {"UUID": "4C4C4544-0000-1234-8000-ABCDEF123456", "Asset Tag": "A123456",
                               "Computer Name": "WDGS-BH0020", "Registered Owner": "Pat Example",
                               "User Name": "pat", "Logon Server": r"\\DC01", "SSID": "LabWiFi",
                               "Volume Serial Number": "1A2B-3C4D", "Hardware ID": "ABCDEFGHIJ"}}
        r = redact_payload(payload, {"redact": True})["summary"]
        for key, original in payload["summary"].items():
            self.assertNotEqual(r[key], original, key)

    def test_decoded_text_fields_are_not_masked(self):
        payload = {"x": {"Domain Role": "Member Workstation", "License Status": "Licensed",
                         "Key Type": "Volume:GVLK", "Machine Type": "Desktop", "Owning Process": "svchost"}}
        self.assertEqual(redact_payload(payload, {"redact": True}), payload)

    def test_ip_addresses_keep_two_octets_and_loopback_is_untouched(self):
        payload = {"n": {"IPv4 Address": "192.168.10.55, 10.0.0.7", "IPv6 Address": "fe80::1c2d:3e4f:5a6b:7c8d",
                         "Default Gateway": "192.168.10.1", "Local Address": "0.0.0.0",
                         "Remote Address": "127.0.0.1", "DNS Servers": ["8.8.8.8", "1.1.1.1"]}}
        r = redact_payload(payload, {"redact": True})["n"]
        self.assertEqual(r["IPv4 Address"], "192.168.*.*, 10.0.*.*")
        self.assertEqual(r["IPv6 Address"], "fe80::*")
        self.assertEqual(r["Default Gateway"], "192.168.*.*")
        self.assertEqual(r["Local Address"], "0.0.0.0")
        self.assertEqual(r["Remote Address"], "127.0.0.1")
        self.assertEqual(r["DNS Servers"], ["8.8.*.*", "1.1.*.*"])

    def test_name_value_rows_mask_sensitive_names_only(self):
        rows = [{"Name": "USERNAME", "Value": "pat"}, {"Name": "Path", "Value": r"C:\Users\pat\bin"},
                {"Name": "LOGONSERVER", "Value": r"\\DC01"}]
        r = redact_payload(rows, {"redact": True})
        self.assertNotEqual(r[0]["Value"], "pat")
        self.assertEqual(r[1]["Value"], r"C:\Users\<redacted>\bin")
        self.assertNotEqual(r[2]["Value"], r"\\DC01")

    def test_requires_admin_sentinel_and_numbers_survive(self):
        from pc_report.section import REQUIRES_ADMIN
        payload = {"d": {"Serial Number": REQUIRES_ADMIN, "Size": 1024, "Serial Count": 3, "Ok": True}}
        r = redact_payload(payload, {"redact": True})["d"]
        self.assertEqual(r["Serial Number"], REQUIRES_ADMIN)
        self.assertEqual(r["Size"], 1024)
        self.assertEqual(r["Serial Count"], 3)
        self.assertIs(r["Ok"], True)

    def test_lists_under_sensitive_keys_are_masked_elementwise(self):
        r = redact_payload({"Members": ["DOMAIN\\alice", "DOMAIN\\bob"]}, {"redact": True})
        self.assertEqual(r, {"Members": ["DOMAIN\\alice", "DOMAIN\\bob"]})  # 'members' is not a token
        r = redact_payload({"Local Administrators": ["DOMAIN\\alice"]}, {"redact": True})
        self.assertNotEqual(r["Local Administrators"], ["DOMAIN\\alice"])

    def test_redact_off_returns_a_deep_copy(self):
        payload = {"a": {"Serial Number": "X1234567"}}
        r = redact_payload(payload, {"redact": False})
        self.assertEqual(r, payload)
        self.assertIsNot(r["a"], payload["a"])
```

(`Local Administrators` is masked because the Security section names that key with the token `localadministrators` — see the token list below.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pc_report_privacy.py -q -k "masked or ip or name_value or sentinel or lists or deep_copy"`
Expected: several failures (`KeyError`/`AssertionError`).

- [ ] **Step 3: Rewrite `pc_report/privacy.py`**

```python
"""Redaction applied to the collected payload before either renderer.

Keys are matched after lowering and stripping non-alphanumerics, so the
human labels sections use ("Serial Number") and raw WMI names
("SerialNumber") hit the same tokens. Section authors must not label a
decoded text field with a token word unless they want it masked.
"""
from __future__ import annotations

import re
from copy import deepcopy

from .section import REQUIRES_ADMIN

_NON_ALNUM = re.compile(r"[^a-z0-9]")

SENSITIVE_TOKENS = (
    "serial", "productkey", "partialproductkey", "productid", "oa3x", "licensekey",
    "password", "passwd", "pwd", "token", "secret", "credential", "apikey",
    "uuid", "assettag", "registeredowner", "owner", "username", "startname", "logonserver",
    "ssid", "computername", "csname", "hostname", "hardwareid", "machineguid", "domainname",
    "localadministrators", "accessaccount", "accountname",
)
IP_TOKENS = ("ipv4", "ipv6", "ipaddress", "gateway", "dnsserver", "dhcpserver",
             "remoteaddress", "localaddress", "serveraddress", "winsserver", "nexthop")
MAC_TOKENS = ("macaddress", "physicaladdress")
SENSITIVE_ENV_NAMES = {"USERNAME", "USERDOMAIN", "USERDNSDOMAIN", "LOGONSERVER", "COMPUTERNAME",
                       "USERDOMAIN_ROAMINGPROFILE", "CLIENTNAME"}

_IPV4 = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}\b")
_IPV6 = re.compile(r"\b([0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{0,4}:)+[0-9a-fA-F]{1,4}\b|\b([0-9a-fA-F]{1,4})::[0-9a-fA-F:]+")


def norm_key(key) -> str:
    return _NON_ALNUM.sub("", str(key).lower())


def mask_string(value, keep: int = 4):
    if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [mask_string(v, keep) for v in value]
    if isinstance(value, dict):
        return {k: mask_string(v, keep) for k, v in value.items()}
    s = str(value)
    if len(s) <= keep:
        return "*" * len(s)
    return s[:2] + "*" * max(1, len(s) - keep - 2) + s[-keep:]


def mask_mac(mac):
    if not mac or mac == REQUIRES_ADMIN:
        return mac
    if isinstance(mac, list):
        return [mask_mac(m) for m in mac]
    mc = str(mac).replace("-", ":")
    parts = mc.split(":")
    if len(parts) >= 6:
        return f"{parts[0]}:{parts[1]}:**:**:{parts[-2]}:{parts[-1]}"
    return mask_string(mac)


def _mask_v4(match):
    whole = match.group(0)
    if whole == "0.0.0.0" or whole.startswith("127.") or whole.startswith("255."):
        return whole
    return f"{match.group(1)}.{match.group(2)}.*.*"


def _mask_v6(match):
    whole = match.group(0)
    if whole in ("::", "::1"):
        return whole
    head = match.group(1) or match.group(2) or ""
    return f"{head}::*"


def mask_ip(value):
    if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [mask_ip(v) for v in value]
    if isinstance(value, dict):
        return {k: mask_ip(v) for k, v in value.items()}
    s = _IPV4.sub(_mask_v4, str(value))
    return _IPV6.sub(_mask_v6, s)


def redact_user_paths(path):
    if not path:
        return path
    return re.sub(r"(C:\\Users\\)[^\\/]+", r"\1<redacted>", str(path), flags=re.IGNORECASE)


def _name_is_sensitive(name: str) -> bool:
    return name.upper() in SENSITIVE_ENV_NAMES or any(t in norm_key(name) for t in SENSITIVE_TOKENS)


def redact_payload(data, options=None):
    """Return a redacted deep copy suitable for HTML or JSON export."""
    options = options or {}
    if not options.get("redact", True):
        return deepcopy(data)

    def redact_value(key, value):
        if isinstance(value, dict):
            out = {k: redact_value(k, v) for k, v in value.items()}
            # Name/Value rows (environment variables, registry dumps): the name says what is sensitive.
            if isinstance(out.get("Name"), str) and "Value" in out and _name_is_sensitive(out["Name"]):
                out["Value"] = mask_string(out["Value"])
            return out
        if isinstance(value, list):
            return [redact_value(key, item) for item in value]
        if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
            return value
        key_l = norm_key(key)
        if any(t in key_l for t in MAC_TOKENS):
            return mask_mac(value)
        if any(t in key_l for t in IP_TOKENS):
            return mask_ip(value)
        if any(t in key_l for t in SENSITIVE_TOKENS):
            return mask_string(value)
        return redact_user_paths(value) if isinstance(value, str) else value

    return redact_value("", data)
```

Note `test_lists_under_sensitive_keys_are_masked_elementwise`: a list under a sensitive key reaches `redact_value(key, list)` which recurses per item with the same key, so each string is masked. Fine.

- [ ] **Step 4: Run, lint, commit**

Run: `python -m pytest tests/test_pc_report_privacy.py -q -k "PcReportPrivacyTests and not html"`
Expected: pass (the `test_html_renderer_*` tests still target the old renderer and are replaced next task).

```bash
python -m ruff check pc_report/privacy.py
git add pc_report/privacy.py tests/test_pc_report_privacy.py
git commit -m "feat(pc_report): redact identifying fields, IP addresses and sensitive Name/Value rows"
```

---

### Task 5: The HTML page shell and Report Health

**Files:**
- Modify: `pc_report/render_html.py` (rewrite)
- Create: `tests/pc_report/test_render_html.py`
- Modify: `tests/test_pc_report_privacy.py` (delete the five `test_html_renderer_*` tests and the `render_html` import; keep the two redaction/JSON tests)

**Interfaces:**
- Consumes: `registry.SECTIONS`, `GROUPS`, `RenderContext`, `is_partial`, `section_data`, `section_notes`, `notes_block`, `kv_table`, `esc`, `NO_DATA`, `mask_string`, `redact_payload`, `format.duration`.
- Produces: `render(meta, data, options) -> str` (signature unchanged). Anchors: `#top`, `#g-<Group>`, `#s-report_health`, `#s-<key>`.

- [ ] **Step 1: Write the failing tests**

`tests/pc_report/test_render_html.py`:

```python
import re
import unittest
from html.parser import HTMLParser
from unittest.mock import patch

from pc_report import registry, render_html
from pc_report.section import NO_DATA, Section, kv_table, wrap


def _default_render(d, c):
    return kv_table([("Field", d.get("v", ""))]) if d else NO_DATA


def _fake(key, group, render=None, title=None):
    return Section(key=key, title=title or key.replace("_", " ").title(), group=group,
                   collect=lambda ctx: {}, render=render or _default_render)


FAKES = (
    _fake("noldus_summary", "NVC", title="Noldus Summary"),
    _fake("operating_system", "Software"),
    _fake("cpu", "Hardware", render=lambda d, c: kv_table([("Serial Number", (d or {}).get("Serial Number", ""))])),
    _fake("shares", "Network"),
)
META = {"generated_at": "2026-09-24T10:00:00", "machine": "WDGS-BH0020", "nvc_version": "2.3.0",
        "elevated": False, "elapsed_by_section": {"cpu": 3.2, "shares": 0.4, "operating_system": 1.1},
        "total_seconds": 4.7}


class _Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.errors = set(), set(), []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href", "").startswith("#"):
            self.hrefs.add(a["href"][1:])
        if tag not in ("br", "img", "meta", "link", "hr"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected </{tag}>; open: {self.stack[-3:]}")


def _render(data, options=None, meta=None):
    with patch.object(registry, "SECTIONS", FAKES):
        return render_html.render(meta or META, data, options or {"redact": True})


def _data(**kw):
    return {k: wrap(v, []) for k, v in kw.items()}


class PageShellTests(unittest.TestCase):
    def test_contents_are_grouped_in_order_and_anchors_resolve(self):
        html = _render(_data(noldus_summary={}, operating_system={}, cpu={}, shares={}))
        self.assertLess(html.index('id="g-NVC"'), html.index('id="g-Software"'))
        self.assertLess(html.index('id="g-Software"'), html.index('id="g-Hardware"'))
        self.assertLess(html.index('id="g-Hardware"'), html.index('id="g-Network"'))
        checker = _Checker()
        checker.feed(html)
        self.assertEqual(checker.errors, [])
        self.assertTrue(checker.hrefs)
        self.assertTrue(checker.hrefs <= checker.ids, checker.hrefs - checker.ids)

    def test_report_health_comes_first_and_summarises_the_run(self):
        html = _render(_data(operating_system={}, cpu={}, shares={}))
        self.assertLess(html.index('id="s-report_health"'), html.index('id="s-operating_system"'))
        self.assertIn("<th>Elevated (administrator)</th><td>No</td>", html)
        self.assertIn("Cpu (3.2 s)", html)
        self.assertIn("<th>Total collection time</th><td>4 s</td>", html)
        self.assertIn("Run NVC as administrator", html)

    def test_absent_sections_are_neither_listed_nor_rendered(self):
        html = _render(_data(cpu={}))
        self.assertNotIn('id="s-shares"', html)
        self.assertNotIn('href="#s-shares"', html)
        self.assertNotIn('id="g-Network"', html)

    def test_partial_section_shows_its_error_and_is_counted(self):
        html = _render({"cpu": {"status": "partial", "error": "WMI down"}})
        self.assertIn('class="bad">This section failed: WMI down', html)
        self.assertIn("<th>Partial sections</th><td>Cpu</td>", html)

    def test_notes_are_printed_under_the_section(self):
        html = _render({"cpu": wrap({}, ["cache: timed out after 30 s"])})
        self.assertIn('<p class="notes"><em>cache: timed out after 30 s</em></p>', html)
        self.assertIn("<th>Sections with notes</th><td>1: Cpu</td>", html)

    def test_empty_sections_are_counted(self):
        html = _render(_data(operating_system=None))
        self.assertIn("<th>Empty sections</th><td>1: Operating System</td>", html)

    def test_a_render_that_raises_does_not_sink_the_page(self):
        def boom(d, c):
            raise ValueError("bad data")
        with patch.object(registry, "SECTIONS", (_fake("cpu", "Hardware", render=boom),)):
            html = render_html.render(META, _data(cpu={}), {"redact": True})
        self.assertIn("Could not render this section.", html)

    def test_redaction_masks_payload_and_header_machine_name(self):
        html = _render(_data(cpu={"Serial Number": "ABCDEFGH12"}))
        self.assertNotIn("ABCDEFGH12", html)
        self.assertNotIn("WDGS-BH0020", html)
        self.assertIn("<th>Redaction</th><td>Enabled</td>", html)
        html = _render(_data(cpu={"Serial Number": "ABCDEFGH12"}), {"redact": False})
        self.assertIn("ABCDEFGH12", html)
        self.assertIn("WDGS-BH0020", html)

    def test_header_carries_version_and_time(self):
        html = _render(_data(cpu={}))
        self.assertIn("NVC 2.3.0", html)
        self.assertIn("2026-09-24T10:00:00", html)
        self.assertIn("<title>NVC PC Report", html)
```

Delete from `tests/test_pc_report_privacy.py`: the `render_html` import line, `test_html_renderer_handles_nvc_report_section`, `test_html_renderer_shows_report_health_nvc_counts_and_uptime`, `test_html_renderer_shows_environment_variables_and_parity_sections`, `test_html_renderer_combines_tcp_and_udp_network_connections`, `test_html_renderer_adds_imaging_devices_section`, and the now-unused `import re`.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/pc_report/test_render_html.py -q`
Expected: failures (old renderer has no `g-` anchors).

- [ ] **Step 3: Rewrite `pc_report/render_html.py`**

```python
"""The PC report page: header, grouped contents, Report Health and every section in registry order."""
from __future__ import annotations

import base64
import os

from utils.logger import logger
from utils.resources import resource_path

from . import registry
from .format import duration
from .privacy import mask_string, redact_payload
from .section import (GROUPS, NO_DATA, RenderContext, esc, is_partial, kv_table, notes_block,
                      section_data, section_notes)

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:20px;color:#222;background:#fff}
h1{border-bottom:2px solid #43a296;padding-bottom:6px;margin-top:0;font-size:26px}
h2{font-size:18pt;margin:28px 0 4px;border-bottom:1px solid #d6eae5}
h3{font-size:12pt;margin:14px 0 4px;color:#2f6f66}
.logo{height:64px;vertical-align:middle;margin-right:12px}
.meta{color:#555;margin:0 0 12px}
.group{background:#eaf5f3;border:1px solid #b9dcd5;text-align:center;font-size:20px;font-weight:bold;padding:6px;margin-top:36px}
.toc{display:flex;gap:24px;border:1px solid #b9dcd5;padding:10px;margin:12px 0 20px}
.toc-col{flex:1}.toc h3{margin:0 0 6px}.toc ul{margin:0;padding-left:18px}.toc li{margin:2px 0}
table{border-collapse:collapse;width:100%;margin:6px 0 10px}
table.kv th{text-align:left;background:#f3f7f6;padding:5px 8px;border:1px solid #e0e0e0;width:33%;font-weight:normal}
table.kv td{padding:5px 8px;border:1px solid #e0e0e0}
table.kv tr.sub th{background:#cfe8e3;font-weight:bold;color:#1f4f48}
table.list th{background:#cfe8e3;text-align:left;border:1px solid #d6eae5;padding:5px 8px;position:sticky;top:0}
table.list td{border:1px solid #f0f0f0;padding:4px 8px;word-break:break-word;vertical-align:top}
tr:nth-child(even) td{background:#fafafa}
tr:hover td{background:#e8f4f1}
a{color:#2f7d72;text-decoration:none}a:hover{text-decoration:underline}
.top{float:right;font-size:11px;color:#3a8f82;font-weight:normal}
.warn{color:#9a6200}.bad{color:#b00020;font-weight:bold}.ok{color:#1b7f3b}
.notes{color:#666;font-size:12px;margin:4px 0 0}
pre{max-height:240px;overflow:auto;white-space:pre-wrap;margin:4px 0}
details summary{cursor:pointer;color:#2f7d72}
"""


def _logo_tag() -> str:
    try:
        logo_path = resource_path("graphics/PCREPORT.png")
        if logo_path and os.path.exists(logo_path):
            with open(logo_path, "rb") as handle:
                b64 = base64.b64encode(handle.read()).decode("ascii")
            return f"<img src='data:image/png;base64,{b64}' alt='PC Report' class='logo'/>"
    except OSError:
        logger.debug("render_html: logo unavailable", exc_info=True)
    return ""


def _h2(title: str, anchor: str) -> str:
    return f'<h2 id="{anchor}">{esc(title)}<a href="#top" class="top">Top ▲</a></h2>'


def _banner(group: str) -> str:
    return f'<div class="group" id="g-{esc(group)}">{esc(group)}</div>'


def _section_body(section, result, ctx: RenderContext) -> str:
    if is_partial(result):
        return f'<p class="bad">This section failed: {esc(result.get("error"))}</p>'
    try:
        body = section.render(section_data(result), ctx)
    except Exception:
        logger.exception("PC report: rendering %s failed", section.key)
        body = '<p class="bad">Could not render this section.</p>'
    return (body or NO_DATA) + notes_block(section_notes(result))


def _report_health(meta: dict, data: dict, rendered, redact: bool) -> str:
    titles = {s.key: s.title for s, _a, _b in rendered}
    partial = [s.title for s, _a, _b in rendered if is_partial(data.get(s.key))]
    noted = [s.title for s, _a, _b in rendered if section_notes(data.get(s.key))]
    empty = [s.title for s, _a, body in rendered if NO_DATA in body]
    elapsed = meta.get("elapsed_by_section") or {}
    slowest = sorted(elapsed.items(), key=lambda kv: kv[1], reverse=True)[:3]

    def counted(items):
        return f"{len(items)}" + (f": {', '.join(items)}" if items else "")

    rows = [
        ("Redaction", "Enabled" if redact else "Disabled"),
        ("Elevated (administrator)", "Yes" if meta.get("elevated") else "No"),
        ("Sections collected", str(len(rendered))),
        ("Partial sections", ", ".join(partial) if partial else "None"),
        ("Sections with notes", counted(noted)),
        ("Empty sections", counted(empty)),
        ("Total collection time", duration(meta.get("total_seconds")) or "Unknown"),
        ("Slowest sections", ", ".join(f"{titles.get(k, k)} ({v:.1f} s)" for k, v in slowest) or "Unknown"),
    ]
    html = kv_table(rows)
    if partial:
        html += f'<p class="bad">{len(partial)} section(s) failed to collect; see their entries below.</p>'
    if not meta.get("elevated"):
        html += ('<p class="warn">Run NVC as administrator to fill in the fields marked '
                 '"Requires administrator".</p>')
    return html


def _contents(rendered) -> str:
    groups: dict[str, list[tuple[str, str]]] = {g: [] for g in GROUPS}
    for section, anchor, _body in rendered:
        groups.setdefault(section.group, []).append((section.title, anchor))
    groups["NVC"].insert(0, ("Report Health", "s-report_health"))
    columns = []
    for group in GROUPS:
        items = groups.get(group) or []
        if not items:
            continue
        links = "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for t, a in items)
        columns.append(f'<div class="toc-col"><h3><a href="#g-{esc(group)}">{esc(group)}</a></h3><ul>{links}</ul></div>')
    return '<div class="toc">' + "".join(columns) + "</div>"


def render(meta, data, options):
    meta = meta or {}
    options = options or {}
    redact = options.get("redact", True)
    data = redact_payload(data or {}, options) if redact else (data or {})
    ctx = RenderContext(redact=redact, meta=meta)

    present = [s for s in registry.SECTIONS if s.key in data]
    rendered = [(s, f"s-{s.key}", _section_body(s, data[s.key], ctx)) for s in present]

    parts = [_banner("NVC"), _h2("Report Health", "s-report_health"), _report_health(meta, data, rendered, redact)]
    current_group = "NVC"
    for section, anchor, body in rendered:
        if section.group != current_group:
            current_group = section.group
            parts.append(_banner(current_group))
        parts.append(_h2(section.title, anchor))
        parts.append(body)

    machine = meta.get("machine", "")
    if redact and machine:
        machine = mask_string(machine)
    version = meta.get("nvc_version", "")
    header = (f"<h1>{_logo_tag()}NVC PC Report</h1>"
              f"<p class='meta'>Machine: {esc(machine)} &middot; Generated: {esc(meta.get('generated_at', ''))}"
              f" &middot; NVC {esc(version)} &middot; Elevated: {'Yes' if meta.get('elevated') else 'No'}</p>")

    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        f"<title>NVC PC Report - {esc(machine)}</title><style>{CSS}</style></head>\n"
        f"<body><a id=\"top\"></a>{header}{_contents(rendered)}{''.join(parts)}</body></html>\n"
    )
```

- [ ] **Step 4: Run, lint, commit**

Run: `python -m pytest tests/pc_report tests/test_pc_report_privacy.py tests/test_pc_report_orchestration.py tests/test_pc_report_widget.py -q`
Expected: pass.

```bash
python -m ruff check pc_report tests
git add pc_report/render_html.py tests/pc_report/test_render_html.py tests/test_pc_report_privacy.py
git commit -m "feat(pc_report): SIW-style page shell with grouped contents and Report Health"
```

### How every section task works

Each section task below follows the same steps; they are spelled out once here and referenced as "the standard steps":

1. Write the section's test module (given in the task) and run it: `python -m pytest tests/pc_report/test_<section>.py -q` — expected to fail with `ImportError`.
2. Write the section module (given in the task).
3. Record fixtures on this machine: `python scripts/dev/capture_pc_report_fixtures.py --section <key> [<key2> ...]`. Open every file written under `tests/fixtures/pc_report/<key>/` and confirm nothing identifying survived redaction and scrubbing (hostnames, user names, serials, keys, IPs beyond two octets). Edit by hand if something did.
4. Run the section tests again: expected pass. Then `python -m pytest tests/pc_report tests/test_pc_report_orchestration.py -q` — the registry invariant test and the offline-tolerance test now include the new section.
5. `python -m ruff check pc_report tests/pc_report`, then commit with the message given.

Section test modules import `from tests.pc_report import support` and use `support.collect_and_render(mod.SECTION)`, which asserts nothing by itself; the test asserts on labels in the HTML and on `ctx.notes` containing no `"no fixture"` entries (a query that is only recorded when elevated is allowed to be missing when the test passes `is_admin=False`, because `admin_query` never reaches the fixture).

---

### Task 6: Operating System

**Files:**
- Create: `pc_report/sections/operating_system.py`
- Test: `tests/pc_report/test_operating_system.py`
- Fixtures: `tests/fixtures/pc_report/operating_system/{os,version_registry,policies,licensing}.json`

**Interfaces:**
- Produces: `SECTION` (key `operating_system`, group Software), `build(os_, ver, pol, lic) -> {"groups": [...]}`. Other sections read `ctx.result("operating_system")["groups"]`; the Noldus Summary reads `find(data, "Name")`-style via `section.kv_lookup` defined here and re-exported later — so also define in this module: `def value_of(data, label)` returning the first matching row value across groups.

- [ ] **Step 1: Test module `tests/pc_report/test_operating_system.py`**

```python
import unittest

from pc_report.sections import operating_system as mod
from tests.pc_report import support

OS = {"Caption": "Microsoft Windows 11 Enterprise LTSC", "Version": "10.0.26100", "BuildNumber": "26100",
      "OSArchitecture": "64-bit", "InstallDate": "/Date(1750000000000)/", "LastBootUpTime": "/Date(1758500000000)/",
      "WindowsDirectory": "C:\\Windows", "SystemDirectory": "C:\\Windows\\system32", "BootDevice": "\\Device\\HarddiskVolume2",
      "SystemDevice": "\\Device\\HarddiskVolume4", "SystemStartOptions": "NOEXECUTE=OPTIN", "OSLanguage": 1033,
      "MUILanguages": ["en-US", "nl-NL"], "CSName": "PC-NAME", "Description": "Lab PC", "OperatingSystemSKU": 125,
      "ProductType": 1, "DataExecutionPrevention_Available": True, "DataExecutionPrevention_SupportPolicy": 2,
      "EncryptionLevel": 256, "RegisteredUser": "user", "Organization": "Lab"}
VER = {"ProductName": "Windows 10 Enterprise LTSC 2024", "EditionID": "EnterpriseS", "DisplayVersion": "24H2",
       "CurrentBuild": "26100", "UBR": 9445, "BuildLab": "26100.ge_release.240331-1435",
       "BuildLabEx": "26100.1.amd64fre.ge_release.240331-1435", "BuildBranch": "ge_release",
       "InstallationType": "Client", "RegisteredOwner": "user", "RegisteredOrganization": "Lab"}
POL = {"EnableLUA": 0, "ConsentPromptBehaviorAdmin": 5, "SecureBoot": 1, "LongPathsEnabled": 1, "HiberbootEnabled": 0,
       "HibernateEnabled": 1, "NoAutoUpdate": None, "AUOptions": 4, "InsiderBranch": None, "DisableSR": 1,
       "RebootPendingCBS": False, "RebootRequiredWU": True, "PendingFileRename": False, "FirmwareType": "UEFI",
       "SafeMode": None, "KernelVersion": "10.0.26100.9444", "DotNetRelease": 533320}
LIC = {"Name": "Windows(R), Enterprise edition", "Description": "Windows(R) Operating System, VOLUME_KMSCLIENT channel",
       "LicenseStatus": 1, "GracePeriodRemaining": 259041, "PartialProductKey": "ABCDE", "ProductKeyChannel": "Volume:GVLK"}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.rows = mod.flatten(mod.build(OS, VER, POL, LIC))

    def test_windows_group(self):
        self.assertEqual(self.rows["Name"], "Microsoft Windows 11 Enterprise LTSC")
        self.assertEqual(self.rows["Version"], "24H2 (OS Build 26100.9445)")
        self.assertEqual(self.rows["SKU"], "Enterprise LTSC")
        self.assertEqual(self.rows["Kernel Version"], "10.0.26100.9444")
        self.assertEqual(self.rows["Product Type"], "Workstation")
        self.assertEqual(self.rows["Language"], "English (United States)")
        self.assertEqual(self.rows["Computer Name"], "PC-NAME")

    def test_activation_group(self):
        self.assertEqual(self.rows["Activation Status"], "Licensed")
        self.assertEqual(self.rows["License Channel"], "Volume:GVLK")
        self.assertEqual(self.rows["Remaining Grace Period"], "179 days, 21 hours, 21 minutes")

    def test_boot_and_policy_groups(self):
        self.assertEqual(self.rows["Boot Device"], "\\Device\\HarddiskVolume2")
        self.assertEqual(self.rows["Pending Reboot"], "Yes")
        self.assertEqual(self.rows["UAC Enabled"], "No")
        self.assertEqual(self.rows["UAC Prompt (Administrators)"], "Prompt for consent for non-Windows binaries")
        self.assertEqual(self.rows["Secure Boot"], "Yes")
        self.assertEqual(self.rows["DEP Policy"], "Opt in (Windows programs only)")
        self.assertEqual(self.rows["Automatic Updates"], "Automatically download and schedule installation")
        self.assertEqual(self.rows["System Restore"], "Disabled")
        self.assertEqual(self.rows[".NET Framework 4.x"], "4.8.1")
        self.assertEqual(self.rows["Fast Startup"], "No")
        self.assertEqual(self.rows["Safe Mode"], "No")

    def test_missing_inputs_do_not_raise(self):
        rows = mod.flatten(mod.build({}, {}, {}, {}))
        self.assertEqual(rows["Activation Status"], "Unknown")
        self.assertEqual(rows["Version"], "")

    def test_value_of(self):
        data = mod.build(OS, VER, POL, LIC)
        self.assertEqual(mod.value_of(data, "Name"), "Microsoft Windows 11 Enterprise LTSC")
        self.assertEqual(mod.value_of(None, "Name"), "")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Name", "Version", "Kernel Version", "Build Lab Ex", "Activation Status",
                      "Boot Time", "Up Time", "UAC Enabled", "Secure Boot", "Pending Reboot"):
            self.assertIn(f"<th>{label}</th>", html, label)
        self.assertNotIn("PC-NAME", html, "computer name must be masked")

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Section module `pc_report/sections/operating_system.py`**

```python
"""Operating System: edition, build, activation, boot and policy state."""
from __future__ import annotations

from .. import decode
from ..format import fmt_datetime, uptime_human, yes_no
from ..ps import cim, ps_quote
from ..section import Section, as_list, first_dict, kv_groups

OS_PROPS = ("Caption", "Version", "BuildNumber", "OSArchitecture", "InstallDate", "LastBootUpTime",
            "WindowsDirectory", "SystemDirectory", "BootDevice", "SystemDevice", "SystemStartOptions",
            "RegisteredUser", "Organization", "OSLanguage", "MUILanguages", "Description", "CSName",
            "OperatingSystemSKU", "ProductType", "DataExecutionPrevention_Available",
            "DataExecutionPrevention_SupportPolicy", "EncryptionLevel", "PortableOperatingSystem")

VERSION_KEY = r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
VERSION_PROPS = ("ProductName,EditionID,DisplayVersion,ReleaseId,CurrentBuild,UBR,BuildLab,BuildLabEx,"
                 "BuildBranch,InstallationType,RegisteredOwner,RegisteredOrganization")

POLICY_SCRIPT = r"""
$o = [ordered]@{}
$sys = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction SilentlyContinue
$o.EnableLUA = $sys.EnableLUA
$o.ConsentPromptBehaviorAdmin = $sys.ConsentPromptBehaviorAdmin
$o.SecureBoot = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SecureBoot\State' -ErrorAction SilentlyContinue).UEFISecureBootEnabled
$o.LongPathsEnabled = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction SilentlyContinue).LongPathsEnabled
$pw = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -ErrorAction SilentlyContinue
$o.HiberbootEnabled = $pw.HiberbootEnabled
$o.HibernateEnabled = $pw.HibernateEnabled
$au = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
$o.NoAutoUpdate = $au.NoAutoUpdate
$o.AUOptions = $au.AUOptions
if ($null -eq $o.AUOptions) { $o.AUOptions = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update' -ErrorAction SilentlyContinue).AUOptions }
$o.InsiderBranch = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsSelfHost\Applicability' -ErrorAction SilentlyContinue).BranchName
$o.DisableSR = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -ErrorAction SilentlyContinue).DisableSR
$o.RebootPendingCBS = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$o.RebootRequiredWU = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
$o.PendingFileRename = [bool](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -ErrorAction SilentlyContinue).PendingFileRenameOperations
$o.FirmwareType = [string]$env:firmware_type
$o.SafeMode = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SafeBoot\Option' -ErrorAction SilentlyContinue).OptionValue
$o.KernelVersion = (Get-Item "$env:SystemRoot\System32\ntoskrnl.exe" -ErrorAction SilentlyContinue).VersionInfo.ProductVersion
$o.DotNetRelease = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue).Release
[pscustomobject]$o
"""

LICENSE_SCRIPT = (
    "Get-CimInstance SoftwareLicensingProduct -ErrorAction SilentlyContinue "
    "-Filter \"ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL\" "
    "| Select-Object Name,Description,LicenseStatus,LicenseStatusReason,GracePeriodRemaining,"
    "PartialProductKey,ProductKeyChannel,LicenseFamily"
)


def _minutes_human(minutes) -> str:
    n = decode.to_int(minutes)
    if n is None:
        return ""
    days, rem = divmod(n, 1440)
    hours, mins = divmod(rem, 60)
    return f"{days} days, {hours} hours, {mins} minutes"


def build(os_: dict, ver: dict, pol: dict, lic: dict) -> dict:
    os_, ver, pol, lic = os_ or {}, ver or {}, pol or {}, lic or {}
    build_no = str(os_.get("BuildNumber") or ver.get("CurrentBuild") or "")
    ubr = ver.get("UBR")
    full_build = f"{build_no}.{ubr}" if build_no and ubr is not None else build_no
    display = ver.get("DisplayVersion") or ver.get("ReleaseId") or ""
    version = f"{display} (OS Build {full_build})".strip() if (display or full_build) else ""

    windows = {
        "Name": os_.get("Caption", ""),
        "Product Name": ver.get("ProductName", ""),
        "Edition": ver.get("EditionID", ""),
        "SKU": decode.os_sku(os_.get("OperatingSystemSKU")),
        "Version": version,
        "Kernel Version": pol.get("KernelVersion") or os_.get("Version", ""),
        "Build Lab": ver.get("BuildLab", ""),
        "Build Lab Ex": ver.get("BuildLabEx", ""),
        "Build Branch": ver.get("BuildBranch", ""),
        "Installation Type": ver.get("InstallationType", ""),
        "Product Type": decode.lookup(decode.PRODUCT_TYPES, os_.get("ProductType")),
        "Architecture": os_.get("OSArchitecture", ""),
        "Language": decode.os_language(os_.get("OSLanguage")),
        "MUI Languages": as_list(os_.get("MUILanguages")),
        "Computer Name": os_.get("CSName", ""),
        "Computer Description": os_.get("Description", ""),
        "Registered Owner": ver.get("RegisteredOwner") or os_.get("RegisteredUser", ""),
        "Registered Organization": ver.get("RegisteredOrganization") or os_.get("Organization", ""),
    }
    activation = {
        "Activation Status": decode.lookup(decode.LICENSE_STATUS, lic.get("LicenseStatus")) if lic else "Unknown",
        "License": lic.get("Name", ""),
        "License Description": lic.get("Description", ""),
        "License Channel": lic.get("ProductKeyChannel", ""),
        "Partial Product Key": lic.get("PartialProductKey", ""),
        "Remaining Grace Period": _minutes_human(lic.get("GracePeriodRemaining")),
    }
    pending = bool(pol.get("RebootPendingCBS") or pol.get("RebootRequiredWU") or pol.get("PendingFileRename"))
    boot = {
        "Install Date": fmt_datetime(os_.get("InstallDate")),
        "Boot Time": fmt_datetime(os_.get("LastBootUpTime")),
        "Up Time": uptime_human(os_.get("LastBootUpTime")),
        "OS Root": os_.get("WindowsDirectory", ""),
        "System Directory": os_.get("SystemDirectory", ""),
        "Boot Device": os_.get("BootDevice", ""),
        "System Device": os_.get("SystemDevice", ""),
        "System Start Options": os_.get("SystemStartOptions", ""),
        "Firmware Type": pol.get("FirmwareType", ""),
        "Safe Mode": pol.get("SafeMode") or "No",
        "Fast Startup": yes_no(pol.get("HiberbootEnabled")),
        "Hibernation": yes_no(pol.get("HibernateEnabled")),
        "Portable Operating System": yes_no(os_.get("PortableOperatingSystem")),
        "Pending Reboot": yes_no(pending),
    }
    security = {
        "UAC Enabled": yes_no(pol.get("EnableLUA")),
        "UAC Prompt (Administrators)": decode.lookup(decode.UAC_PROMPT, pol.get("ConsentPromptBehaviorAdmin")),
        "Secure Boot": yes_no(pol.get("SecureBoot")),
        "Hardware DEP Available": yes_no(os_.get("DataExecutionPrevention_Available")),
        "DEP Policy": decode.lookup(decode.DEP_POLICY, os_.get("DataExecutionPrevention_SupportPolicy")),
        "Encryption Level": f"{os_.get('EncryptionLevel')} bits" if os_.get("EncryptionLevel") else "",
        "Long Paths Enabled": yes_no(pol.get("LongPathsEnabled")),
        "Automatic Updates": decode.au_options(pol.get("NoAutoUpdate"), pol.get("AUOptions")),
        "Windows Insider Program": pol.get("InsiderBranch") or "Not enrolled",
        "System Restore": "Disabled" if decode.to_int(pol.get("DisableSR")) == 1 else "Enabled",
        ".NET Framework 4.x": decode.dotnet_release(pol.get("DotNetRelease")),
    }
    return {"groups": [
        {"title": "Windows", "rows": windows},
        {"title": "Activation", "rows": activation},
        {"title": "Boot", "rows": boot},
        {"title": "Security and Policies", "rows": security},
    ]}


def flatten(data) -> dict:
    """All rows of a kv-groups payload in one dict (later groups win on duplicate labels)."""
    out = {}
    for group in as_list((data or {}).get("groups") if isinstance(data, dict) else None):
        if isinstance(group, dict) and isinstance(group.get("rows"), dict):
            out.update(group["rows"])
    return out


def value_of(data, label: str):
    return flatten(data).get(label, "")


def collect(ctx):
    os_ = first_dict(ctx.query("os", cim("Win32_OperatingSystem", OS_PROPS)))
    ver = first_dict(ctx.query("version_registry",
                               f"Get-ItemProperty {ps_quote(VERSION_KEY)} | Select-Object {VERSION_PROPS}"))
    pol = first_dict(ctx.query("policies", POLICY_SCRIPT))
    lic = first_dict(ctx.query("licensing", LICENSE_SCRIPT, timeout=45))
    return build(os_, ver, pol, lic)


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="operating_system", title="Operating System", group="Software",
                  collect=collect, render=render, timeout=45)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Operating System section at SIW depth`

---

### Task 7: Installed Updates and Licenses

**Files:**
- Create: `pc_report/sections/installed_updates.py`, `pc_report/sections/licenses.py`
- Test: `tests/pc_report/test_installed_updates.py`, `tests/pc_report/test_licenses.py`
- Fixtures: `installed_updates/{hotfixes,history}.json`, `licenses/licensing.json`

- [ ] **Step 1: Tests**

`tests/pc_report/test_installed_updates.py`:

```python
import unittest

from pc_report.sections import installed_updates as mod
from tests.pc_report import support

HOTFIX = [{"HotFixID": "KB5062660", "Description": "Update", "InstalledOn": "/Date(1750000000000)/", "InstalledBy": "NT AUTHORITY\\SYSTEM"}]
HISTORY = [
    {"Date": "/Date(1758000000000)/", "Title": "2026-09 Cumulative Update (KB5124007)", "KB": "KB5124007", "Operation": 1, "Result": 2, "Client": "MoUpdateOrchestrator"},
    {"Date": "/Date(1755000000000)/", "Title": "Defender Antivirus platform", "KB": "", "Operation": 1, "Result": 4, "Client": "UpdateOrchestrator"},
]


class BuildTests(unittest.TestCase):
    def test_hotfix_rows(self):
        data = mod.build(HOTFIX, HISTORY)
        self.assertEqual(data["hotfixes"][0]["KB"], "KB5062660")
        self.assertRegex(data["hotfixes"][0]["Installed On"], r"^\d{4}-\d{2}-\d{2}$")

    def test_history_is_newest_first_and_decoded(self):
        data = mod.build(HOTFIX, HISTORY)
        self.assertEqual(data["history"][0]["KB"], "KB5124007")
        self.assertEqual(data["history"][0]["Operation"], "Installation")
        self.assertEqual(data["history"][0]["Result"], "Succeeded")
        self.assertEqual(data["history"][1]["Result"], "Failed")
        self.assertRegex(data["history"][0]["Month"], r"^\d{4}-\d{2}$")

    def test_render_groups_history_by_month(self):
        html = mod.render(mod.build(HOTFIX, HISTORY), support.render_ctx())
        self.assertIn("<h3>Installed hotfixes</h3>", html)
        self.assertEqual(html.count("<h3>Windows Update history"), 1)
        self.assertGreaterEqual(html.count('class="sub"'), 2)
        self.assertIn("✖ Failed", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>KB</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_licenses.py`:

```python
import unittest

from pc_report.sections import licenses as mod
from tests.pc_report import support

RAW = {"ProductId": "00329-00000-00003-AA123", "OA3xOriginalProductKey": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
       "OA3xOriginalProductKeyDescription": "Win 10 Pro OEM", "KeyManagementServiceMachine": "kms.example.local",
       "Products": [{"Name": "Windows(R), Enterprise edition", "Description": "VOLUME_KMSCLIENT channel",
                     "LicenseStatus": 1, "PartialProductKey": "ABCDE", "ProductKeyChannel": "Volume:GVLK",
                     "LicenseFamily": "Enterprise", "GracePeriodRemaining": 100}]}


class BuildTests(unittest.TestCase):
    def test_summary_and_products(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Windows Product ID"], "00329-00000-00003-AA123")
        self.assertEqual(rows["OEM Original Product Key"], "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY")
        self.assertEqual(rows["KMS Host Name"], "kms.example.local")
        self.assertEqual(data["products"][0]["Status"], "Licensed")
        self.assertEqual(data["products"][0]["Partial Product Key"], "ABCDE")

    def test_render_masks_keys(self):
        _data, html, _ctx = support.collect_and_render(mod.SECTION)
        self.assertNotIn("Partial Product Key</th><td>ABCDE<", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Windows Product ID</th>", html)
        self.assertIn("<th>Product</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/installed_updates.py`:

```python
"""Installed Updates: hotfixes plus the Windows Update history, newest first, grouped by month."""
from __future__ import annotations

import datetime

from .. import decode
from ..format import fmt_date, fmt_datetime, parse_datetime
from ..section import Section, list_table, rows_of, sub_heading

HOTFIX_SCRIPT = "Get-HotFix -ErrorAction SilentlyContinue | Select-Object HotFixID,Description,InstalledOn,InstalledBy"

HISTORY_SCRIPT = r"""
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$count = $searcher.GetTotalHistoryCount()
if ($count -gt 0) {
  $searcher.QueryHistory(0, [Math]::Min($count, 500)) | Where-Object { $_.Title } | ForEach-Object {
    $kb = ''
    if ($_.Title -match 'KB\d+') { $kb = $matches[0] }
    [pscustomobject]@{ Date = $_.Date; Title = [string]$_.Title; KB = $kb; Operation = [int]$_.Operation
                       Result = [int]$_.ResultCode; Client = [string]$_.ClientApplicationID }
  }
}
"""

HOTFIX_COLUMNS = [("KB", "KB"), ("Description", "Description"), ("Installed On", "Installed On"),
                  ("Installed By (account name)", "Installed By")]
HISTORY_COLUMNS = [("Date", "Date"), ("Title", "Title"), ("KB", "KB"), ("Operation", "Operation"),
                   ("Result", "Result"), ("Client", "Client")]


def build(hotfixes, history) -> dict:
    hot = [{
        "KB": h.get("HotFixID", ""), "Description": h.get("Description", ""),
        "Installed On": fmt_date(h.get("InstalledOn")),
        "Installed By (account name)": h.get("InstalledBy", ""),
    } for h in rows_of(hotfixes)]
    hot.sort(key=lambda r: r["Installed On"], reverse=True)

    def when(row):
        return parse_datetime(row.get("Date")) or datetime.datetime.min

    hist = []
    for r in sorted(rows_of(history), key=when, reverse=True):
        dt = parse_datetime(r.get("Date"))
        hist.append({
            "Date": fmt_datetime(r.get("Date")), "Month": dt.strftime("%Y-%m") if dt else "Unknown",
            "Title": r.get("Title", ""), "KB": r.get("KB", ""),
            "Operation": decode.lookup(decode.WU_OPERATION, r.get("Operation")),
            "Result": decode.lookup(decode.WU_RESULT, r.get("Result")),
            "Client": r.get("Client", ""),
        })
    return {"hotfixes": hot, "history": hist}


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [sub_heading("Installed hotfixes"), list_table(HOTFIX_COLUMNS, data.get("hotfixes")),
           sub_heading("Windows Update history")]
    history = rows_of(data.get("history"))
    if not history:
        out.append(list_table(HISTORY_COLUMNS, []))
        return "".join(out)
    by_month: dict[str, list] = {}
    for row in history:
        by_month.setdefault(row.get("Month", "Unknown"), []).append(row)
    for month, rows in by_month.items():
        shown = []
        for row in rows:
            row = dict(row)
            if row.get("Result") in ("Failed", "Aborted"):
                row["Result"] = f"✖ {row['Result']}"
            shown.append(row)
        out.append(f'<table class="kv"><tr class="sub"><th colspan="2">{month} ({len(rows)})</th></tr></table>'
                   + list_table(HISTORY_COLUMNS, shown))
    return "".join(out)


def collect(ctx):
    hotfixes = ctx.query("hotfixes", HOTFIX_SCRIPT)
    history = ctx.query("history", HISTORY_SCRIPT, timeout=90)
    return build(hotfixes, history)


SECTION = Section(key="installed_updates", title="Installed Updates", group="Software",
                  collect=collect, render=render, timeout=90)
```

(Highlight classes are reserved for the summary and Report Health; a marker glyph keeps the section plain.)

`pc_report/sections/licenses.py`:

```python
"""Licenses: Windows product ID, OEM key and every licensed product. All keys are masked by redaction."""
from __future__ import annotations

from .. import decode
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
$o = [ordered]@{}
$o.ProductId = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue).ProductId
$svc = Get-CimInstance SoftwareLicensingService -ErrorAction SilentlyContinue
$o.OA3xOriginalProductKey = [string]$svc.OA3xOriginalProductKey
$o.OA3xOriginalProductKeyDescription = [string]$svc.OA3xOriginalProductKeyDescription
$o.KeyManagementServiceMachine = [string]$svc.KeyManagementServiceMachine
$o.Products = @(Get-CimInstance SoftwareLicensingProduct -ErrorAction SilentlyContinue -Filter "PartialProductKey IS NOT NULL" |
  Select-Object Name,Description,LicenseStatus,PartialProductKey,ProductKeyChannel,LicenseFamily,GracePeriodRemaining)
[pscustomobject]$o
"""

COLUMNS = [("Product", "Product"), ("Description", "Description"), ("Status", "Status"),
           ("Channel", "Channel"), ("Partial Product Key", "Partial Product Key"), ("Family", "Family")]


def build(raw: dict) -> dict:
    raw = raw or {}
    summary = {
        "Windows Product ID": raw.get("ProductId", ""),
        "OEM Original Product Key": raw.get("OA3xOriginalProductKey", ""),
        "OEM Key Description": raw.get("OA3xOriginalProductKeyDescription", ""),
        "KMS Host Name": raw.get("KeyManagementServiceMachine", ""),
    }
    products = [{
        "Product": p.get("Name", ""), "Description": p.get("Description", ""),
        "Status": decode.lookup(decode.LICENSE_STATUS, p.get("LicenseStatus")),
        "Channel": p.get("ProductKeyChannel", ""), "Partial Product Key": p.get("PartialProductKey", ""),
        "Family": p.get("LicenseFamily", ""),
    } for p in rows_of(raw.get("Products"))]
    return {"groups": [{"title": "Windows", "rows": summary}], "products": products}


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Licensed products") + list_table(COLUMNS, data.get("products"))


def collect(ctx):
    return build(first_dict(ctx.query("licensing", SCRIPT, timeout=45)))


SECTION = Section(key="licenses", title="Licenses", group="Software", collect=collect, render=render, timeout=45)
```

- [ ] **Step 3: Standard steps 3–5**

`python scripts/dev/capture_pc_report_fixtures.py --section installed_updates licenses`

Commit message: `feat(pc_report): Installed Updates with Windows Update history; Licenses per product`

---

### Task 8: System Directories, System Files, Environment

**Files:**
- Create: `pc_report/sections/system_directories.py`, `pc_report/sections/system_files.py`, `pc_report/sections/environment.py`
- Test: `tests/pc_report/test_system_directories.py`, `tests/pc_report/test_system_files.py`, `tests/pc_report/test_environment.py`
- Fixtures: `system_directories/folders.json`, `system_files/files.json`, `environment/variables.json`

- [ ] **Step 1: Tests**

`tests/pc_report/test_system_directories.py`:

```python
import unittest

from pc_report.sections import system_directories as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_names_are_humanised_and_env_dirs_come_first(self):
        data = mod.build([{"Name": "ApplicationData", "Path": "C:\\Users\\user\\AppData\\Roaming"},
                          {"Name": "CommonProgramFiles", "Path": "C:\\Program Files\\Common Files"}],
                         {"SystemRoot": "C:\\Windows"})
        self.assertEqual(data["rows"][0], {"Name": "System Root", "Path": "C:\\Windows", "Source": "Environment"})
        names = [r["Name"] for r in data["rows"]]
        self.assertIn("Application Data", names)
        self.assertIn("Common Program Files", names)

    def test_humanise(self):
        self.assertEqual(mod.humanise("MyDocuments"), "My Documents")
        self.assertEqual(mod.humanise("CDBurning"), "CD Burning")
        self.assertEqual(mod.humanise("ProgramFilesX86"), "Program Files X86")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<td>Desktop Directory</td>", html)
        self.assertNotIn("C:\\Users\\user\\", html)  # scrubbed to user, then redacted

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_system_files.py`:

```python
import unittest

from pc_report.sections import system_files as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_rows_are_formatted(self):
        data = mod.build([{"Name": "hosts", "Path": "C:\\Windows\\System32\\drivers\\etc\\hosts", "Size": 824,
                           "Modified": "/Date(1700000000000)/", "Entries": 2},
                          {"Name": "win.ini", "Path": "C:\\Windows\\win.ini", "Size": "", "Modified": "", "Entries": "missing"}])
        self.assertEqual(data["rows"][0]["Size"], "824.0 B")
        self.assertEqual(data["rows"][0]["Hosts Entries"], 2)
        self.assertEqual(data["rows"][1]["Status"], "Missing")
        self.assertEqual(data["rows"][0]["Status"], "Present")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for name in ("hosts", "services", "win.ini", "system.ini"):
            self.assertIn(f"<td>{name}</td>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_environment.py`:

```python
import unittest

from pc_report.sections import environment as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_variables_are_grouped_by_scope(self):
        data = mod.build([{"Scope": "Machine", "Name": "Path", "Value": "C:\\Windows"},
                          {"Scope": "User", "Name": "TEMP", "Value": "C:\\Users\\user\\Temp"},
                          {"Scope": "Process", "Name": "USERNAME", "Value": "user"}])
        self.assertEqual([r["Name"] for r in data["Machine"]], ["Path"])
        self.assertEqual([r["Name"] for r in data["User"]], ["TEMP"])
        self.assertEqual(data["Process"][0]["Name"], "USERNAME")

    def test_render_has_three_headings_and_masks_username(self):
        data = mod.build([{"Scope": "Process", "Name": "USERNAME", "Value": "patrick"}])
        from pc_report.privacy import redact_payload
        html = mod.render(redact_payload(data, {"redact": True}), support.render_ctx())
        self.assertIn("<h3>Process</h3>", html)
        self.assertNotIn("patrick", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<td>Path</td>", html)
        self.assertIn("<h3>Machine</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/system_directories.py`:

```python
"""System Directories: every Environment.SpecialFolder plus the core environment folders."""
from __future__ import annotations

import os
import re

from ..section import Section, list_table, rows_of

SCRIPT = r"""
[Enum]::GetNames([System.Environment+SpecialFolder]) | Sort-Object -Unique | ForEach-Object {
  $p = [Environment]::GetFolderPath($_)
  if ($p) { [pscustomobject]@{ Name = [string]$_; Path = [string]$p } }
}
"""

ENV_DIRS = ("SystemRoot", "SystemDrive", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432",
            "ProgramData", "CommonProgramFiles", "CommonProgramFiles(x86)", "PUBLIC", "TEMP", "TMP", "windir")

COLUMNS = [("Name", "Name"), ("Path", "Path"), ("Source", "Source")]

_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=X86)")


def humanise(name: str) -> str:
    return _CAMEL.sub(" ", str(name))


def build(folders, env: dict) -> dict:
    rows = [{"Name": humanise(k), "Path": env[k], "Source": "Environment"} for k in ENV_DIRS if env.get(k)]
    rows += [{"Name": humanise(r.get("Name", "")), "Path": r.get("Path", ""), "Source": "Shell folder"}
             for r in rows_of(folders)]
    return {"rows": rows}


def collect(ctx):
    return build(ctx.query("folders", SCRIPT), dict(os.environ))


def render(data, ctx):
    return list_table(COLUMNS, (data or {}).get("rows") if isinstance(data, dict) else None)


SECTION = Section(key="system_directories", title="System Directories", group="Software",
                  collect=collect, render=render)
```

`pc_report/sections/system_files.py`:

```python
"""System Files: the classic configuration files, with size, modified time and hosts entry count."""
from __future__ import annotations

from ..format import bytes_human, fmt_datetime
from ..section import Section, list_table, rows_of

SCRIPT = r"""
$root = $env:SystemRoot
$paths = @("$root\System32\drivers\etc\hosts", "$root\System32\drivers\etc\lmhosts.sam",
           "$root\System32\drivers\etc\networks", "$root\System32\drivers\etc\protocol",
           "$root\System32\drivers\etc\services", "$root\system.ini", "$root\win.ini")
foreach ($p in $paths) {
  $f = Get-Item $p -ErrorAction SilentlyContinue
  if ($f) {
    $entries = ''
    if ($f.Name -eq 'hosts') { $entries = @(Get-Content $p -ErrorAction SilentlyContinue | Where-Object { $_ -match '^\s*[^#\s]' }).Count }
    [pscustomobject]@{ Name = $f.Name; Path = $f.FullName; Size = $f.Length; Modified = $f.LastWriteTime; Entries = $entries }
  } else {
    [pscustomobject]@{ Name = (Split-Path $p -Leaf); Path = $p; Size = ''; Modified = ''; Entries = 'missing' }
  }
}
"""

COLUMNS = [("Name", "Name"), ("Path", "Path"), ("Status", "Status"), ("Size", "Size"),
           ("Modified", "Modified"), ("Hosts Entries", "Hosts entries")]


def build(files) -> dict:
    rows = []
    for f in rows_of(files):
        missing = f.get("Entries") == "missing"
        rows.append({
            "Name": f.get("Name", ""), "Path": f.get("Path", ""),
            "Status": "Missing" if missing else "Present",
            "Size": "" if missing or f.get("Size") in ("", None) else bytes_human(f.get("Size")),
            "Modified": "" if missing else fmt_datetime(f.get("Modified")),
            "Hosts Entries": "" if missing or f.get("Entries") in ("", None) else f.get("Entries"),
        })
    return {"rows": rows}


def collect(ctx):
    return build(ctx.query("files", SCRIPT))


def render(data, ctx):
    return list_table(COLUMNS, (data or {}).get("rows") if isinstance(data, dict) else None)


SECTION = Section(key="system_files", title="System Files", group="Software", collect=collect, render=render)
```

`pc_report/sections/environment.py`:

```python
"""Environment: variables in Machine, User and Process scope. Redaction masks USERNAME-style values."""
from __future__ import annotations

from ..section import Section, list_table, rows_of, sub_heading

SCRIPT = r"""
foreach ($scope in 'Machine','User','Process') {
  $vars = [Environment]::GetEnvironmentVariables($scope)
  foreach ($k in ($vars.Keys | Sort-Object)) {
    [pscustomobject]@{ Scope = $scope; Name = [string]$k; Value = [string]$vars[$k] }
  }
}
"""

SCOPES = ("Machine", "User", "Process")
COLUMNS = [("Name", "Name"), ("Value", "Value")]


def build(variables) -> dict:
    out = {scope: [] for scope in SCOPES}
    for row in rows_of(variables):
        scope = row.get("Scope") if row.get("Scope") in SCOPES else "Process"
        out[scope].append({"Name": row.get("Name", ""), "Value": row.get("Value", "")})
    return out


def collect(ctx):
    return build(ctx.query("variables", SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return "".join(sub_heading(scope) + list_table(COLUMNS, data.get(scope)) for scope in SCOPES)


SECTION = Section(key="environment", title="Environment", group="Software", collect=collect, render=render)
```

- [ ] **Step 3: Standard steps 3–5**

`python scripts/dev/capture_pc_report_fixtures.py --section system_directories system_files environment`

Commit message: `feat(pc_report): System Directories, System Files and scoped Environment sections`

---

### Task 9: Installed Programs

**Files:**
- Create: `pc_report/sections/installed_programs.py`
- Test: `tests/pc_report/test_installed_programs.py`
- Fixtures: `installed_programs/{registry,packages,appx}.json`

**Interfaces:**
- Produces: `data = {"rows": [...], "groups": [summary]}`; each row has keys `Name, Version, Publisher, Install Date, Size, Architecture, Scope, Hidden, Install Location, Install Source, Source, Uninstall`. The Noldus Summary (Task 29) reads `ctx.result("installed_programs")["rows"]`.

- [ ] **Step 1: Test `tests/pc_report/test_installed_programs.py`**

```python
import unittest

from pc_report.sections import installed_programs as mod
from tests.pc_report import support

REG = [{"Name": "EthoVision XT 19", "Version": "19.0.1912", "Publisher": "Noldus", "InstallDate": "20260522",
        "InstallLocation": "C:\\Program Files\\Noldus\\EthoVision XT", "InstallSource": "D:\\", "EstimatedSize": 2048000,
        "Uninstall": "MsiExec.exe /X{GUID}", "Architecture": "x64", "Scope": "Machine", "SystemComponent": None},
       {"Name": "Noldus - IPP - X64 Package - 8", "Version": "8.0", "Publisher": "Noldus", "InstallDate": "",
        "InstallLocation": "", "InstallSource": "", "EstimatedSize": None, "Uninstall": "", "Architecture": "x64",
        "Scope": "Machine", "SystemComponent": 1}]
PKG = [{"Name": "EthoVision XT 19", "Version": "19.0.1912", "Publisher": "Noldus", "ProviderName": "msi"}]
APPX = [{"Name": "Microsoft.WindowsCalculator", "Version": "11.0", "Publisher": "Microsoft Corporation",
         "InstallDate": "2026-01-02", "InstallLocation": "C:\\Program Files\\WindowsApps\\Calc", "Architecture": "X64"}]


class BuildTests(unittest.TestCase):
    def test_rows_are_normalised_and_deduplicated(self):
        data = mod.build(REG, PKG, APPX)
        names = [r["Name"] for r in data["rows"]]
        self.assertEqual(names.count("EthoVision XT 19"), 1)
        etho = next(r for r in data["rows"] if r["Name"] == "EthoVision XT 19")
        self.assertEqual(etho["Install Date"], "2026-05-22")
        self.assertEqual(etho["Size"], "2.0 GB")
        self.assertEqual(etho["Hidden"], "No")
        ipp = next(r for r in data["rows"] if r["Name"].startswith("Noldus - IPP"))
        self.assertEqual(ipp["Hidden"], "Yes")
        calc = next(r for r in data["rows"] if r["Name"].startswith("Microsoft.Windows"))
        self.assertEqual(calc["Source"], "Microsoft Store")

    def test_rows_are_sorted_case_insensitively(self):
        data = mod.build([{"Name": "beta"}, {"Name": "Alpha"}], [], [])
        self.assertEqual([r["Name"] for r in data["rows"]], ["Alpha", "beta"])

    def test_summary_counts(self):
        rows = dict(mod.build(REG, PKG, APPX)["groups"][0]["rows"])
        self.assertEqual(rows["Programs"], 3)
        self.assertEqual(rows["Hidden (system components)"], 1)
        self.assertEqual(rows["Microsoft Store apps"], 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Publisher</th>", html)
        self.assertIn("<th>Programs</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/installed_programs.py`**

```python
"""Installed Programs: Uninstall registry keys (both hives, user scope), package providers and Store apps."""
from __future__ import annotations

from ..format import fmt_date, kb_human, yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

REGISTRY_SCRIPT = r"""
$hives = @(
  @{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall'; Arch = 'x64'; Scope = 'Machine' },
  @{ Path = 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'; Arch = 'x86'; Scope = 'Machine' },
  @{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'; Arch = ''; Scope = 'User' }
)
foreach ($h in $hives) {
  if (Test-Path $h.Path) {
    Get-ChildItem $h.Path -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      if ($x.DisplayName) {
        [pscustomobject]@{ Name = [string]$x.DisplayName; Version = [string]$x.DisplayVersion; Publisher = [string]$x.Publisher
                           InstallDate = [string]$x.InstallDate; InstallLocation = [string]$x.InstallLocation
                           InstallSource = [string]$x.InstallSource; EstimatedSize = $x.EstimatedSize
                           Uninstall = [string]$x.UninstallString; Architecture = $h.Arch; Scope = $h.Scope
                           SystemComponent = $x.SystemComponent }
      }
    }
  }
}
"""

PACKAGES_SCRIPT = (
    "Get-Package -ErrorAction SilentlyContinue | ForEach-Object { "
    "[pscustomobject]@{ Name = [string]$_.Name; Version = [string]$_.Version; "
    "Publisher = [string]($_.Meta.Attributes['Publisher']); ProviderName = [string]$_.ProviderName } }"
)

APPX_SCRIPT = (
    "Get-AppxPackage -ErrorAction SilentlyContinue | ForEach-Object { "
    "$pub = [string]$_.Publisher; if ($pub -match 'CN=([^,]+)') { $pub = $matches[1] } "
    "$inst = ''; try { if ($_.InstallLocation) { $fi = Get-Item $_.InstallLocation -ErrorAction SilentlyContinue; "
    "if ($fi) { $inst = $fi.CreationTime.ToString('yyyy-MM-dd') } } } catch {} "
    "[pscustomobject]@{ Name = [string]$_.Name; Version = [string]$_.Version; Publisher = $pub; InstallDate = $inst; "
    "InstallLocation = [string]$_.InstallLocation; Architecture = [string]$_.Architecture } }"
)

COLUMNS = [("Name", "Name"), ("Version", "Version"), ("Publisher", "Publisher"), ("Install Date", "Install Date"),
           ("Size", "Size"), ("Architecture", "Architecture"), ("Scope", "Scope"), ("Hidden", "Hidden"),
           ("Install Location", "Install Location"), ("Install Source", "Install Source"), ("Source", "Source"),
           ("Uninstall", "Uninstall")]


def _row(name, version="", publisher="", install_date="", size="", arch="", scope="Machine", hidden=False,
         location="", install_source="", source="", uninstall=""):
    return {"Name": str(name), "Version": str(version or ""), "Publisher": str(publisher or ""),
            "Install Date": fmt_date(install_date) if install_date else "", "Size": size, "Architecture": str(arch or ""),
            "Scope": scope, "Hidden": yes_no(bool(hidden)), "Install Location": str(location or ""),
            "Install Source": str(install_source or ""), "Source": source, "Uninstall": str(uninstall or "")}


def build(registry_rows, package_rows, appx_rows) -> dict:
    rows = []
    for it in rows_of(registry_rows):
        if not it.get("Name"):
            continue
        size = kb_human(it["EstimatedSize"]) if it.get("EstimatedSize") not in (None, "", 0) else ""
        rows.append(_row(it["Name"], it.get("Version"), it.get("Publisher"), it.get("InstallDate"), size,
                         it.get("Architecture"), it.get("Scope") or "Machine", bool(it.get("SystemComponent")),
                         it.get("InstallLocation"), it.get("InstallSource"), "Registry", it.get("Uninstall")))
    for it in rows_of(package_rows):
        if it.get("Name"):
            rows.append(_row(it["Name"], it.get("Version"), it.get("Publisher"),
                             source=f"Package ({it.get('ProviderName') or 'provider'})"))
    for it in rows_of(appx_rows):
        if it.get("Name"):
            rows.append(_row(it["Name"], it.get("Version"), it.get("Publisher"), it.get("InstallDate"),
                             arch=it.get("Architecture"), location=it.get("InstallLocation"), source="Microsoft Store"))
    seen, deduped = set(), []
    for row in rows:
        key = (row["Name"].lower(), row["Version"], row["Publisher"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    deduped.sort(key=lambda r: r["Name"].lower())
    summary = {
        "Programs": len(deduped),
        "Hidden (system components)": sum(1 for r in deduped if r["Hidden"] == "Yes"),
        "Microsoft Store apps": sum(1 for r in deduped if r["Source"] == "Microsoft Store"),
        "User-scope installs": sum(1 for r in deduped if r["Scope"] == "User"),
    }
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": deduped}


def collect(ctx):
    reg = ctx.query("registry", REGISTRY_SCRIPT, timeout=60)
    pkg = ctx.query("packages", PACKAGES_SCRIPT, timeout=90)
    appx = ctx.query("appx", APPX_SCRIPT, timeout=60)
    return build(reg, pkg, appx)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Programs") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="installed_programs", title="Installed Programs", group="Software",
                  collect=collect, render=render, timeout=90)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Installed Programs with location, size, architecture, scope and hidden flag`

### Task 10: Security

**Files:**
- Create: `pc_report/sections/security.py`
- Test: `tests/pc_report/test_security.py`
- Fixtures: `security/{security_center,defender,firewall,device_guard,local_admins,net_accounts.txt}` (+ `tpm.json`, `bitlocker.json` when captured elevated)

- [ ] **Step 1: Test `tests/pc_report/test_security.py`**

```python
import unittest

from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import security as mod
from tests.pc_report import support

SC = [{"Kind": "AntiVirusProduct", "Name": "Windows Defender", "State": 397568, "Path": "C:\\x.exe", "Timestamp": "Mon"},
      {"Kind": "FirewallProduct", "Name": "Vendor FW", "State": 266256, "Path": "", "Timestamp": ""}]
DEF = {"AMProductVersion": "4.18.1", "AMEngineVersion": "1.1.2", "AntivirusSignatureVersion": "1.4",
       "AntivirusSignatureLastUpdated": "/Date(1758000000000)/", "RealTimeProtectionEnabled": True,
       "IsTamperProtected": True, "NISEnabled": True, "QuickScanEndTime": None, "FullScanEndTime": None,
       "QuickScanAge": 2, "FullScanAge": 4294967295}
FW = [{"Name": "Domain", "Enabled": 1, "DefaultInboundAction": 4, "DefaultOutboundAction": 2, "NotifyOnListen": 0,
       "LogFileName": "%systemroot%\\pfirewall.log", "LogMaxSizeKilobytes": 4096}]
DG = {"VirtualizationBasedSecurityStatus": 2, "SecurityServicesConfigured": [1, 2], "SecurityServicesRunning": [2],
      "AvailableSecurityProperties": [1, 2, 3, 5, 7], "RequiredSecurityProperties": [0],
      "CodeIntegrityPolicyEnforcementStatus": 2, "UsermodeCodeIntegrityPolicyEnforcementStatus": 0}
ADMINS = [{"Name": "PC-NAME\\Administrator", "ObjectClass": "User", "PrincipalSource": 1}]
NET = "Force user logoff how long after time expires?:       Never\nMinimum password length:                              8\nLockout threshold:                                    Never\nThe command completed successfully.\n"


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(SC, DEF, FW, DG, {"TpmPresent": True, "TpmReady": True, "ManufacturerIdTxt": "IFX "},
                              [{"MountPoint": "C:", "ProtectionStatus": 1, "EncryptionMethod": 7, "EncryptionPercentage": 100,
                                "VolumeStatus": 1, "KeyProtector": "Tpm, RecoveryPassword"}], ADMINS, NET)

    def test_security_center_rows(self):
        av = self.data["security_center"][0]
        self.assertEqual(av["Kind"], "Antivirus")
        self.assertEqual(av["State"], "Enabled")
        self.assertEqual(av["Signatures"], "Up to date")

    def test_defender_and_firewall(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Real-time Protection"], "Yes")
        self.assertEqual(rows["Last Full Scan"], "Never")
        fw = self.data["firewall"][0]
        self.assertEqual(fw["Enabled"], "Yes")
        self.assertEqual(fw["Inbound"], "Block")
        self.assertEqual(fw["Outbound"], "Allow")

    def test_device_guard_decoded(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Virtualization-based Security"], "Running")
        self.assertEqual(rows["Security Services Running"], "Hypervisor Code Integrity (HVCI)")
        self.assertEqual(rows["Kernel-mode Code Integrity"], "Enforced")

    def test_tpm_bitlocker_and_accounts(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["TPM Present"], "Yes")
        self.assertEqual(rows["TPM Manufacturer"], "IFX")
        self.assertEqual(rows["Minimum password length"], "8")
        bl = self.data["bitlocker"][0]
        self.assertEqual(bl["Protection"], "On")
        self.assertEqual(bl["Method"], "XTS-AES 256")

    def test_requires_admin_placeholders(self):
        data = mod.build([], {}, [], {}, REQUIRES_ADMIN, REQUIRES_ADMIN, [], "")
        self.assertEqual(mod.flatten(data)["TPM"], REQUIRES_ADMIN)
        self.assertEqual(data["bitlocker"], REQUIRES_ADMIN)
        html = mod.render(data, support.render_ctx())
        self.assertEqual(html.count("Requires administrator"), 2)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Antivirus", "Real-time Protection", "Inbound", "Virtualization-based Security",
                      "Local Administrators", "Requires administrator"):
            self.assertIn(label, html, label)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/security.py`**

```python
"""Security: Security Center products, Defender, firewall, VBS, TPM, BitLocker, admins and account policy."""
from __future__ import annotations

from .. import decode
from ..format import fmt_datetime, yes_no
from ..ps import cim
from ..section import REQUIRES_ADMIN, Section, first_dict, kv_groups, kv_table, list_table, rows_of, sub_heading

SC_SCRIPT = r"""
foreach ($cls in 'AntiVirusProduct','AntiSpywareProduct','FirewallProduct') {
  Get-CimInstance -Namespace root/SecurityCenter2 -ClassName $cls -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ Kind = $cls; Name = [string]$_.displayName; State = $_.productState
                       Path = [string]$_.pathToSignedProductExe; Timestamp = [string]$_.timestamp }
  }
}
"""
DEFENDER_SCRIPT = ("Get-MpComputerStatus -ErrorAction SilentlyContinue | Select-Object AMProductVersion,AMEngineVersion,"
                   "AMServiceEnabled,AntivirusEnabled,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,"
                   "AntispywareEnabled,RealTimeProtectionEnabled,IsTamperProtected,NISEnabled,BehaviorMonitorEnabled,"
                   "IoavProtectionEnabled,QuickScanEndTime,FullScanEndTime,QuickScanAge,FullScanAge")
FIREWALL_SCRIPT = ("Get-NetFirewallProfile -ErrorAction SilentlyContinue | Select-Object Name,Enabled,DefaultInboundAction,"
                   "DefaultOutboundAction,NotifyOnListen,LogFileName,LogMaxSizeKilobytes")
DEVICE_GUARD_SCRIPT = cim("Win32_DeviceGuard", ("VirtualizationBasedSecurityStatus", "SecurityServicesConfigured",
                                                "SecurityServicesRunning", "AvailableSecurityProperties",
                                                "RequiredSecurityProperties", "CodeIntegrityPolicyEnforcementStatus",
                                                "UsermodeCodeIntegrityPolicyEnforcementStatus"),
                          namespace=r"root\Microsoft\Windows\DeviceGuard")
TPM_SCRIPT = ("Get-Tpm -ErrorAction SilentlyContinue | Select-Object TpmPresent,TpmReady,TpmEnabled,TpmActivated,"
              "ManufacturerIdTxt,ManufacturerVersion,ManagedAuthLevel,LockedOut")
BITLOCKER_SCRIPT = ("Get-BitLockerVolume -ErrorAction SilentlyContinue | Select-Object MountPoint,VolumeType,ProtectionStatus,"
                    "LockStatus,EncryptionMethod,EncryptionPercentage,VolumeStatus,"
                    "@{n='KeyProtector';e={($_.KeyProtector | ForEach-Object { [string]$_.KeyProtectorType }) -join ', '}}")
ADMINS_SCRIPT = "Get-LocalGroupMember -Group Administrators -ErrorAction SilentlyContinue | Select-Object Name,ObjectClass,PrincipalSource"

KINDS = {"AntiVirusProduct": "Antivirus", "AntiSpywareProduct": "Anti-spyware", "FirewallProduct": "Firewall"}
FW_ACTION = {0: "Not configured", 2: "Allow", 4: "Block"}
VBS_STATUS = {0: "Not enabled", 1: "Enabled, not running", 2: "Running"}
CI_STATUS = {0: "Off", 1: "Audit", 2: "Enforced"}
ENCRYPTION_METHOD = {0: "None", 1: "AES 128 with diffuser", 2: "AES 256 with diffuser", 3: "AES 128", 4: "AES 256",
                     5: "Hardware", 6: "XTS-AES 128", 7: "XTS-AES 256"}
PROTECTION = {0: "Off", 1: "On", 2: "Unknown"}

SC_COLUMNS = [("Kind", "Kind"), ("Name", "Product"), ("State", "State"), ("Signatures", "Signatures"),
              ("Path", "Path"), ("Timestamp", "Timestamp")]
FW_COLUMNS = [("Profile", "Profile"), ("Enabled", "Enabled"), ("Inbound", "Default inbound"),
              ("Outbound", "Default outbound"), ("Notify", "Notify on listen"), ("Log", "Log file"), ("Log Size", "Log size")]
BL_COLUMNS = [("Volume", "Volume"), ("Type", "Type"), ("Protection", "Protection"), ("Lock", "Lock"),
              ("Method", "Method"), ("Encrypted", "Encrypted"), ("Key Protectors", "Key protectors")]
ADMIN_COLUMNS = [("Local Administrators", "Member"), ("Class", "Class"), ("Source", "Source")]


def _fw_action(value):
    return decode.lookup(FW_ACTION, value) if decode.to_int(value) is not None else str(value or "")


def _scan_age(age):
    n = decode.to_int(age)
    if n is None:
        return ""
    return "Never" if n >= 4294967295 else f"{n} day{'s' if n != 1 else ''} ago"


def _kv_or_admin(label, value, rows_fn):
    if value == REQUIRES_ADMIN:
        return {label: REQUIRES_ADMIN}
    return rows_fn(first_dict(value) if not isinstance(value, dict) else value)


def _tpm_rows(t):
    return {"TPM Present": yes_no(t.get("TpmPresent")), "TPM Ready": yes_no(t.get("TpmReady")),
            "TPM Enabled": yes_no(t.get("TpmEnabled")), "TPM Activated": yes_no(t.get("TpmActivated")),
            "TPM Manufacturer": str(t.get("ManufacturerIdTxt") or "").strip(),
            "TPM Manufacturer Version": t.get("ManufacturerVersion", ""),
            "TPM Locked Out": yes_no(t.get("LockedOut"))} if t else {"TPM": "Not detected"}


def _net_accounts(text) -> dict:
    rows = {}
    for line in (text or "").splitlines():
        if ":" not in line or line.lower().startswith("the command"):
            continue
        key, _, value = line.partition(":")
        rows[key.strip().rstrip("?")] = value.strip()
    return rows


def build(sc, defender, firewall, dg, tpm, bitlocker, admins, accounts_text) -> dict:
    defender, dg = defender or {}, dg or {}
    security_center = []
    for p in rows_of(sc):
        enabled, signature = decode.security_center_state(p.get("State"))
        security_center.append({"Kind": KINDS.get(p.get("Kind"), p.get("Kind", "")), "Name": p.get("Name", ""),
                                "State": enabled, "Signatures": signature if p.get("Kind") != "FirewallProduct" else "",
                                "Path": p.get("Path", ""), "Timestamp": p.get("Timestamp", "")})
    defender_rows = {
        "Platform Version": defender.get("AMProductVersion", ""), "Engine Version": defender.get("AMEngineVersion", ""),
        "Signature Version": defender.get("AntivirusSignatureVersion", ""),
        "Signatures Updated": fmt_datetime(defender.get("AntivirusSignatureLastUpdated")),
        "Antivirus Enabled": yes_no(defender.get("AntivirusEnabled")),
        "Real-time Protection": yes_no(defender.get("RealTimeProtectionEnabled")),
        "Behavior Monitoring": yes_no(defender.get("BehaviorMonitorEnabled")),
        "Network Inspection": yes_no(defender.get("NISEnabled")),
        "Tamper Protection": yes_no(defender.get("IsTamperProtected")),
        "Last Quick Scan": _scan_age(defender.get("QuickScanAge")) or fmt_datetime(defender.get("QuickScanEndTime")),
        "Last Full Scan": _scan_age(defender.get("FullScanAge")) or fmt_datetime(defender.get("FullScanEndTime")),
    } if defender else {"Microsoft Defender": "Not available (another product may be registered)"}
    fw_rows = [{"Profile": f.get("Name", ""), "Enabled": yes_no(f.get("Enabled")),
                "Inbound": _fw_action(f.get("DefaultInboundAction")), "Outbound": _fw_action(f.get("DefaultOutboundAction")),
                "Notify": yes_no(f.get("NotifyOnListen")), "Log": f.get("LogFileName", ""),
                "Log Size": f"{f.get('LogMaxSizeKilobytes')} KB" if f.get("LogMaxSizeKilobytes") else ""}
               for f in rows_of(firewall)]
    vbs = {
        "Virtualization-based Security": decode.lookup(VBS_STATUS, dg.get("VirtualizationBasedSecurityStatus")),
        "Security Services Configured": decode.lookup(decode.DEVICE_GUARD_SERVICES, dg.get("SecurityServicesConfigured")),
        "Security Services Running": decode.lookup(decode.DEVICE_GUARD_SERVICES, dg.get("SecurityServicesRunning")),
        "Available Security Properties": decode.lookup(decode.DEVICE_GUARD_AVAILABLE, dg.get("AvailableSecurityProperties")),
        "Kernel-mode Code Integrity": decode.lookup(CI_STATUS, dg.get("CodeIntegrityPolicyEnforcementStatus")),
        "User-mode Code Integrity": decode.lookup(CI_STATUS, dg.get("UsermodeCodeIntegrityPolicyEnforcementStatus")),
    } if dg else {"Virtualization-based Security": "Not reported"}
    tpm_rows = _kv_or_admin("TPM", tpm, _tpm_rows)
    if bitlocker == REQUIRES_ADMIN:
        bl_rows = REQUIRES_ADMIN
    else:
        bl_rows = [{"Volume": v.get("MountPoint", ""), "Type": str(v.get("VolumeType") or ""),
                    "Protection": decode.lookup(PROTECTION, v.get("ProtectionStatus")),
                    "Lock": str(v.get("LockStatus") or ""), "Method": decode.lookup(ENCRYPTION_METHOD, v.get("EncryptionMethod")),
                    "Encrypted": f"{v.get('EncryptionPercentage')} %" if v.get("EncryptionPercentage") is not None else "",
                    "Key Protectors": v.get("KeyProtector", "")} for v in rows_of(bitlocker)]
    admin_rows = [{"Local Administrators": a.get("Name", ""), "Class": a.get("ObjectClass", ""),
                   "Source": {1: "Local", 2: "Active Directory", 3: "Azure AD", 4: "Microsoft account"}.get(
                       decode.to_int(a.get("PrincipalSource")), str(a.get("PrincipalSource") or ""))}
                  for a in rows_of(admins)]
    return {
        "groups": [{"title": "Microsoft Defender", "rows": defender_rows},
                   {"title": "Virtualization-based Security", "rows": vbs},
                   {"title": "TPM", "rows": tpm_rows},
                   {"title": "Account Policy", "rows": _net_accounts(accounts_text)}],
        "security_center": security_center, "firewall": fw_rows, "bitlocker": bl_rows, "admins": admin_rows,
    }


def flatten(data) -> dict:
    out = {}
    for group in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(group.get("rows") or {})
    return out


def collect(ctx):
    return build(ctx.query("security_center", SC_SCRIPT),
                 first_dict(ctx.query("defender", DEFENDER_SCRIPT, timeout=30)),
                 ctx.query("firewall", FIREWALL_SCRIPT),
                 first_dict(ctx.query("device_guard", DEVICE_GUARD_SCRIPT)),
                 ctx.admin_query("tpm", TPM_SCRIPT),
                 ctx.admin_query("bitlocker", BITLOCKER_SCRIPT, timeout=30),
                 ctx.query("local_admins", ADMINS_SCRIPT),
                 ctx.text("net_accounts", ["net", "accounts"]))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [sub_heading("Security Center"), list_table(SC_COLUMNS, data.get("security_center")),
           kv_groups(data.get("groups")),
           sub_heading("Firewall profiles"), list_table(FW_COLUMNS, data.get("firewall")),
           sub_heading("BitLocker")]
    bl = data.get("bitlocker")
    out.append(kv_table([("BitLocker", REQUIRES_ADMIN)]) if bl == REQUIRES_ADMIN else list_table(BL_COLUMNS, bl))
    out += [sub_heading("Local Administrators"), list_table(ADMIN_COLUMNS, data.get("admins"))]
    return "".join(out)


SECTION = Section(key="security", title="Security", group="Software", collect=collect, render=render, timeout=30)
```

Note `_kv_or_admin` passes a dict straight through; when `tpm` is a list (JSON array) it takes the first dict. `{"TPM": "Not detected"}` covers an empty result.

- [ ] **Step 3: Standard steps 3–5**

Run the capture twice if you can: once normally, once from an elevated prompt (`--section security`) so `tpm.json` and `bitlocker.json` exist. The fixture test passes `is_admin=False` so it always sees "Requires administrator" for those two.

Commit message: `feat(pc_report): Security section with Defender, firewall, VBS, TPM/BitLocker (admin) and account policy`

---

### Task 11: Accessibility and Regional Settings

**Files:**
- Create: `pc_report/sections/accessibility.py`, `pc_report/sections/regional_settings.py`
- Test: `tests/pc_report/test_accessibility.py`, `tests/pc_report/test_regional_settings.py`
- Fixtures: `accessibility/settings.json`, `regional_settings/regional.json`

- [ ] **Step 1: Tests**

`tests/pc_report/test_accessibility.py`:

```python
import unittest

from pc_report.sections import accessibility as mod
from tests.pc_report import support

RAW = {"StickyKeys": 510, "ToggleKeys": 62, "FilterKeys": 126, "MouseKeys": 62, "SoundSentry": 2, "HighContrast": 126,
       "Keyboard Response": 126, "TimeOut": 2, "ShowSounds": 0, "Keyboard Preference": 0, "Blind Access": 0,
       "CursorBlinkRate": 530, "CaretWidth": 1, "MouseScheme": "Windows Default", "TextScaleFactor": 100,
       "HighContrastScheme": "High Contrast Black"}


class BuildTests(unittest.TestCase):
    def test_feature_groups_decode_flags(self):
        data = mod.build(RAW)
        titles = [g["title"] for g in data["groups"]]
        self.assertEqual(titles[0], "Settings")
        self.assertIn("Sticky Keys", titles)
        sticky = next(g for g in data["groups"] if g["title"] == "Sticky Keys")["rows"]
        self.assertEqual(sticky["Enabled"], "No")
        self.assertEqual(sticky["Available"], "Yes")
        self.assertEqual(sticky["Hotkey activation enabled"], "Yes")

    def test_settings_rows(self):
        rows = mod.build(RAW)["groups"][0]["rows"]
        self.assertEqual(rows["Cursor Blink Rate"], "530 ms")
        self.assertEqual(rows["Text Scale"], "100 %")
        self.assertEqual(rows["High Contrast Scheme"], "High Contrast Black")
        self.assertEqual(rows["Show Sounds"], "No")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn(">Sticky Keys<", html)
        self.assertIn("<th>Cursor Blink Rate</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_regional_settings.py`:

```python
import unittest

from pc_report.sections import regional_settings as mod
from tests.pc_report import support

RAW = {"Culture": "en-US", "CultureDisplay": "English (United States)", "UICulture": "en-US", "UICultureDisplay": "English (United States)",
       "SystemLocale": "en-US", "SystemLocaleDisplay": "English (United States)", "HomeLocation": "Netherlands", "GeoId": 176,
       "TimeZoneId": "W. Europe Standard Time", "TimeZoneDisplay": "(UTC+01:00) Amsterdam", "BaseUtcOffset": "01:00:00",
       "SupportsDst": True, "IsDst": True, "ShortDate": "yyyy-MM-dd", "LongDate": "dddd, MMMM d, yyyy", "ShortTime": "HH:mm",
       "TimeFormat": "HH:mm:ss", "Decimal": ".", "Thousand": ",", "ListSeparator": ",", "Currency": "€", "Measure": 0,
       "FirstDayOfWeek": 0, "CalendarType": 1, "NativeDigits": "0123456789", "NegativeSign": "-",
       "DateSample": "2026-09-24", "LongDateSample": "Thursday, September 24, 2026", "TimeSample": "10:11:12",
       "NumberSample": "1,234,567.89", "CurrencySample": "€1,234.50",
       "Languages": [{"Tag": "en-US", "Name": "English (United States)", "Autonym": "English (United States)", "InputMethods": "0409:00000409"}]}


class BuildTests(unittest.TestCase):
    def test_groups(self):
        data = mod.build(RAW)
        rows = {}
        for g in data["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["User Locale"], "English (United States) [en-US]")
        self.assertEqual(rows["Time Zone"], "(UTC+01:00) Amsterdam")
        self.assertEqual(rows["Daylight Saving Time"], "Supported, currently active")
        self.assertEqual(rows["Measurement System"], "Metric")
        self.assertEqual(rows["First Day of Week"], "Monday")
        self.assertEqual(rows["Calendar"], "Gregorian (localized)")
        self.assertEqual(data["languages"][0]["Keyboard Layouts"], "0409:00000409")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Time Zone</th>", html)
        self.assertIn("<th>Keyboard Layouts</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/accessibility.py`:

```python
"""Accessibility: Ease of Access feature flags and the cursor/text settings that affect observation UIs."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..section import Section, first_dict, kv_groups

FEATURES = ("StickyKeys", "ToggleKeys", "FilterKeys", "MouseKeys", "SoundSentry", "HighContrast",
            "Keyboard Response", "TimeOut")
SWITCHES = ("ShowSounds", "Keyboard Preference", "Blind Access")

SCRIPT = r"""
$root = 'HKCU:\Control Panel\Accessibility'
$o = [ordered]@{}
foreach ($k in 'StickyKeys','ToggleKeys','FilterKeys','MouseKeys','SoundSentry','HighContrast','Keyboard Response','TimeOut') {
  $o[$k] = (Get-ItemProperty "$root\$k" -ErrorAction SilentlyContinue).Flags
}
foreach ($k in 'ShowSounds','Keyboard Preference','Blind Access') {
  $o[$k] = (Get-ItemProperty "$root\$k" -ErrorAction SilentlyContinue).On
}
$desk = Get-ItemProperty 'HKCU:\Control Panel\Desktop' -ErrorAction SilentlyContinue
$o.CursorBlinkRate = $desk.CursorBlinkRate
$o.CaretWidth = $desk.CaretWidth
$o.MouseScheme = (Get-ItemProperty 'HKCU:\Control Panel\Cursors' -ErrorAction SilentlyContinue).'(default)'
$o.TextScaleFactor = (Get-ItemProperty 'HKCU:\Software\Microsoft\Accessibility' -ErrorAction SilentlyContinue).TextScaleFactor
$o.HighContrastScheme = (Get-ItemProperty "$root\HighContrast" -ErrorAction SilentlyContinue).'High Contrast Scheme'
[pscustomobject]$o
"""


def _title(name: str) -> str:
    return {"StickyKeys": "Sticky Keys", "ToggleKeys": "Toggle Keys", "FilterKeys": "Filter Keys",
            "MouseKeys": "Mouse Keys", "SoundSentry": "Sound Sentry", "HighContrast": "High Contrast",
            "TimeOut": "Accessibility Time-out", "ShowSounds": "Show Sounds"}.get(name, name)


def build(raw: dict) -> dict:
    raw = raw or {}
    settings = {
        "Cursor Blink Rate": f"{raw['CursorBlinkRate']} ms" if raw.get("CursorBlinkRate") not in (None, "") else "",
        "Caret Width": f"{raw['CaretWidth']} px" if raw.get("CaretWidth") not in (None, "") else "",
        "Mouse Pointer Scheme": raw.get("MouseScheme") or "Windows Default",
        "Text Scale": f"{raw['TextScaleFactor']} %" if raw.get("TextScaleFactor") not in (None, "") else "100 %",
        "High Contrast Scheme": raw.get("HighContrastScheme", ""),
    }
    for name in SWITCHES:
        value = raw.get(name)
        settings[_title(name)] = yes_no(decode.to_int(value)) if value not in (None, "") else ""
    groups = [{"title": "Settings", "rows": settings}]
    for name in FEATURES:
        if raw.get(name) in (None, ""):
            continue
        groups.append({"title": _title(name), "rows": decode.accessibility_flags(raw.get(name))})
    return {"groups": groups}


def collect(ctx):
    return build(first_dict(ctx.query("settings", SCRIPT)))


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="accessibility", title="Accessibility", group="Software", collect=collect, render=render)
```

`pc_report/sections/regional_settings.py`:

```python
"""Regional Settings: locales, time zone, formats with live samples, and installed input languages."""
from __future__ import annotations

from .. import decode
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
$c = Get-Culture; $ui = Get-UICulture; $sys = Get-WinSystemLocale -ErrorAction SilentlyContinue
$loc = Get-WinHomeLocation -ErrorAction SilentlyContinue; $tz = Get-TimeZone
$intl = Get-ItemProperty 'HKCU:\Control Panel\International' -ErrorAction SilentlyContinue
$langs = @(Get-WinUserLanguageList -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ Tag = $_.LanguageTag; Name = $_.EnglishName; Autonym = $_.Autonym; InputMethods = ($_.InputMethodTips -join ', ') } })
$now = Get-Date
[pscustomobject]@{
  Culture = $c.Name; CultureDisplay = $c.DisplayName; UICulture = $ui.Name; UICultureDisplay = $ui.DisplayName
  SystemLocale = [string]$sys.Name; SystemLocaleDisplay = [string]$sys.DisplayName
  HomeLocation = [string]$loc.HomeLocation; GeoId = $loc.GeoId
  TimeZoneId = $tz.Id; TimeZoneDisplay = $tz.DisplayName; BaseUtcOffset = [string]$tz.BaseUtcOffset
  SupportsDst = $tz.SupportsDaylightSavingTime; IsDst = [System.TimeZoneInfo]::Local.IsDaylightSavingTime($now)
  ShortDate = $intl.sShortDate; LongDate = $intl.sLongDate; ShortTime = $intl.sShortTime; TimeFormat = $intl.sTimeFormat
  Decimal = $intl.sDecimal; Thousand = $intl.sThousand; ListSeparator = $intl.sList; Currency = $intl.sCurrency
  Measure = $intl.iMeasure; FirstDayOfWeek = $intl.iFirstDayOfWeek; CalendarType = $intl.iCalendarType
  NativeDigits = $intl.sNativeDigits; NegativeSign = $intl.sNegativeSign
  DateSample = $now.ToString('d'); LongDateSample = $now.ToString('D'); TimeSample = $now.ToString('T')
  NumberSample = (1234567.89).ToString('N2'); CurrencySample = (1234.5).ToString('C')
  Languages = $langs
}
"""

MEASURE = {0: "Metric", 1: "U.S."}
DAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
CALENDARS = {1: "Gregorian (localized)", 2: "Gregorian (English)", 3: "Japanese Emperor Era", 4: "Taiwan",
             5: "Korean Tangun Era", 6: "Hijri", 7: "Thai", 8: "Hebrew", 9: "Gregorian Middle East French",
             10: "Gregorian Arabic", 11: "Gregorian Transliterated English", 12: "Gregorian Transliterated French",
             23: "Um Al Qura"}
LANG_COLUMNS = [("Tag", "Tag"), ("Name", "Language"), ("Autonym", "Native name"), ("Keyboard Layouts", "Keyboard Layouts")]


def _pair(display, code):
    return f"{display} [{code}]" if display and code else (display or code or "")


def build(raw: dict) -> dict:
    raw = raw or {}
    dst = ""
    if raw.get("SupportsDst") is not None:
        dst = "Supported" if raw.get("SupportsDst") else "Not supported"
        if raw.get("SupportsDst"):
            dst += ", currently active" if raw.get("IsDst") else ", not active"
    locales = {
        "User Locale": _pair(raw.get("CultureDisplay"), raw.get("Culture")),
        "Display Language": _pair(raw.get("UICultureDisplay"), raw.get("UICulture")),
        "System Locale": _pair(raw.get("SystemLocaleDisplay"), raw.get("SystemLocale")),
        "Home Location": f"{raw.get('HomeLocation', '')} (GeoID {raw.get('GeoId')})" if raw.get("GeoId") else raw.get("HomeLocation", ""),
    }
    time = {
        "Time Zone": raw.get("TimeZoneDisplay", ""), "Time Zone ID": raw.get("TimeZoneId", ""),
        "UTC Offset": raw.get("BaseUtcOffset", ""), "Daylight Saving Time": dst,
    }
    formats = {
        "Short Date": raw.get("ShortDate", ""), "Short Date Sample": raw.get("DateSample", ""),
        "Long Date": raw.get("LongDate", ""), "Long Date Sample": raw.get("LongDateSample", ""),
        "Short Time": raw.get("ShortTime", ""), "Time Format": raw.get("TimeFormat", ""), "Time Sample": raw.get("TimeSample", ""),
        "Decimal Symbol": raw.get("Decimal", ""), "Digit Grouping Symbol": raw.get("Thousand", ""),
        "List Separator": raw.get("ListSeparator", ""), "Negative Sign": raw.get("NegativeSign", ""),
        "Native Digits": raw.get("NativeDigits", ""), "Number Sample": raw.get("NumberSample", ""),
        "Currency Symbol": raw.get("Currency", ""), "Currency Sample": raw.get("CurrencySample", ""),
        "Measurement System": decode.lookup(MEASURE, raw.get("Measure")),
        "First Day of Week": decode.lookup(DAYS, raw.get("FirstDayOfWeek")),
        "Calendar": decode.lookup(CALENDARS, raw.get("CalendarType")),
    }
    languages = [{"Tag": lang.get("Tag", ""), "Name": lang.get("Name", ""), "Autonym": lang.get("Autonym", ""),
                  "Keyboard Layouts": lang.get("InputMethods", "")} for lang in rows_of(raw.get("Languages"))]
    return {"groups": [{"title": "Locales", "rows": locales}, {"title": "Time", "rows": time},
                       {"title": "Formats", "rows": formats}], "languages": languages}


def collect(ctx):
    return build(first_dict(ctx.query("regional", SCRIPT)))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Input languages") + list_table(LANG_COLUMNS, data.get("languages"))


SECTION = Section(key="regional_settings", title="Regional Settings", group="Software", collect=collect, render=render)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Accessibility flags and Regional Settings with format samples`

---

### Task 12: Processes and Services

**Files:**
- Create: `pc_report/sections/processes.py`, `pc_report/sections/services.py`
- Test: `tests/pc_report/test_processes.py`, `tests/pc_report/test_services.py`
- Fixtures: `processes/processes.json`, `services/services.json`

- [ ] **Step 1: Tests**

`tests/pc_report/test_processes.py`:

```python
import unittest

from pc_report.sections import processes as mod
from tests.pc_report import support

RAW = [{"Id": 4, "Name": "System", "Description": "", "Company": "", "Version": "", "Path": "", "CommandLine": "",
        "ParentId": 0, "Session": 0, "StartTime": None, "CPU": 1234.5, "WorkingSet": 1048576, "PrivateBytes": 204800,
        "Threads": 200, "Handles": 5000, "Priority": "Normal", "Responding": True, "Owner": ""},
       {"Id": 1000, "Name": "EthoVision", "Description": "EthoVision XT", "Company": "Noldus", "Version": "19.0",
        "Path": "C:\\Program Files\\Noldus\\EV.exe", "CommandLine": "\"C:\\Program Files\\Noldus\\EV.exe\" /x",
        "ParentId": 900, "Session": 1, "StartTime": "/Date(1758000000000)/", "CPU": 10.0, "WorkingSet": 2147483648,
        "PrivateBytes": 1073741824, "Threads": 40, "Handles": 900, "Priority": "High", "Responding": True,
        "Owner": "LAB\\user"}]


class BuildTests(unittest.TestCase):
    def test_rows_and_summary(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Processes"], 2)
        self.assertEqual(rows["Threads"], 240)
        self.assertEqual(rows["Handles"], 5900)
        self.assertEqual(rows["Working Set (total)"], "2.0 GB")
        ev = next(r for r in data["rows"] if r["Name"] == "EthoVision")
        self.assertEqual(ev["Working Set"], "2.0 GB")
        self.assertEqual(ev["CPU Time"], "10 s")
        self.assertEqual(ev["Parent PID"], 900)

    def test_top_lists(self):
        data = mod.build(RAW)
        self.assertEqual(data["top_cpu"][0]["Name"], "System")
        self.assertEqual(data["top_memory"][0]["Name"], "EthoVision")

    def test_owner_is_masked_in_render(self):
        _data, html, _ctx = support.collect_and_render(mod.SECTION)
        self.assertNotIn("\\user<", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Top 10 by CPU time</h3>", html)
        self.assertIn("<th>Command Line</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_services.py`:

```python
import unittest

from pc_report.sections import services as mod
from tests.pc_report import support

RAW = [{"Name": "FrameServer", "DisplayName": "Windows Camera Frame Server", "State": "Stopped", "StartMode": "Manual",
        "StartName": "LocalSystem", "PathName": "C:\\Windows\\system32\\svchost.exe -k Camera",
        "ProcessId": 0, "Description": "Enables multiple clients to access video frames", "ServiceType": "Share Process",
        "DelayedAutoStart": False, "ExitCode": 1077},
       {"Name": "hasplms", "DisplayName": "Sentinel LDK License Manager", "State": "Running", "StartMode": "Auto",
        "StartName": "LocalSystem", "PathName": "C:\\Windows\\system32\\hasplms.exe -run", "ProcessId": 4321,
        "Description": "", "ServiceType": "Own Process", "DelayedAutoStart": True, "ExitCode": 0}]


class BuildTests(unittest.TestCase):
    def test_rows_and_summary(self):
        data = mod.build(RAW)
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Services"], 2)
        self.assertEqual(rows["Running"], 1)
        self.assertEqual(rows["Automatic (Delayed)"], 1)
        hasp = next(r for r in data["rows"] if r["Name"] == "hasplms")
        self.assertEqual(hasp["Start Mode"], "Automatic (Delayed)")
        self.assertEqual(hasp["PID"], 4321)
        fs = next(r for r in data["rows"] if r["Name"] == "FrameServer")
        self.assertEqual(fs["PID"], "")
        self.assertEqual(fs["Exit Code"], 1077)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Start Mode</th>", html)
        self.assertIn("<th>Services</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/processes.py`:

```python
"""Processes: every process with owner, command line, memory and CPU, plus top-10 lists."""
from __future__ import annotations

from ..format import bytes_human, duration, fmt_datetime, yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
$cim = @{}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object { $cim[[int]$_.ProcessId] = $_ }
foreach ($p in (Get-Process -ErrorAction SilentlyContinue)) {
  $c = $cim[[int]$p.Id]
  $owner = ''
  if ($c) { try { $o = Invoke-CimMethod -InputObject $c -MethodName GetOwner -ErrorAction SilentlyContinue; if ($o.User) { $owner = "$($o.Domain)\$($o.User)" } } catch {} }
  $start = $null; try { $start = $p.StartTime } catch {}
  $cpu = $null; try { $cpu = $p.CPU } catch {}
  [pscustomobject]@{ Id = $p.Id; Name = $p.ProcessName; Description = [string]$p.Description; Company = [string]$p.Company
    Version = [string]$p.FileVersion; Path = [string]$p.Path; CommandLine = [string]$c.CommandLine; ParentId = $c.ParentProcessId
    Session = $p.SessionId; StartTime = $start; CPU = $cpu; WorkingSet = $p.WorkingSet64; PrivateBytes = $p.PrivateMemorySize64
    Threads = $p.Threads.Count; Handles = $p.HandleCount; Priority = [string]$p.PriorityClass; Responding = $p.Responding; Owner = $owner }
}
"""

COLUMNS = [("PID", "PID"), ("Name", "Name"), ("Description", "Description"), ("Company", "Company"), ("Version", "Version"),
           ("Owner", "Owner"), ("Session", "Session"), ("Parent PID", "Parent PID"), ("Started", "Started"),
           ("CPU Time", "CPU Time"), ("Working Set", "Working Set"), ("Private Bytes", "Private Bytes"),
           ("Threads", "Threads"), ("Handles", "Handles"), ("Priority", "Priority"), ("Responding", "Responding"),
           ("Path", "Path"), ("Command Line", "Command Line")]
TOP_COLUMNS = [("PID", "PID"), ("Name", "Name"), ("CPU Time", "CPU Time"), ("Working Set", "Working Set"), ("Owner", "Owner")]


def _num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build(raw) -> dict:
    rows = []
    for p in rows_of(raw):
        rows.append({
            "PID": p.get("Id"), "Name": p.get("Name", ""), "Description": p.get("Description", ""),
            "Company": p.get("Company", ""), "Version": p.get("Version", ""), "Owner": p.get("Owner", ""),
            "Session": p.get("Session"), "Parent PID": p.get("ParentId"), "Started": fmt_datetime(p.get("StartTime")),
            "CPU Time": duration(p.get("CPU")) if p.get("CPU") is not None else "",
            "Working Set": bytes_human(p.get("WorkingSet")) if p.get("WorkingSet") is not None else "",
            "Private Bytes": bytes_human(p.get("PrivateBytes")) if p.get("PrivateBytes") is not None else "",
            "Threads": p.get("Threads"), "Handles": p.get("Handles"), "Priority": p.get("Priority", ""),
            "Responding": yes_no(p.get("Responding")), "Path": p.get("Path", ""), "Command Line": p.get("CommandLine", ""),
            "_cpu": _num(p.get("CPU")), "_ws": _num(p.get("WorkingSet")),
        })
    rows.sort(key=lambda r: str(r["Name"]).lower())
    top_cpu = sorted(rows, key=lambda r: r["_cpu"], reverse=True)[:10]
    top_mem = sorted(rows, key=lambda r: r["_ws"], reverse=True)[:10]
    summary = {
        "Processes": len(rows),
        "Threads": sum(int(_num(r["Threads"])) for r in rows),
        "Handles": sum(int(_num(r["Handles"])) for r in rows),
        "Working Set (total)": bytes_human(int(sum(r["_ws"] for r in rows))),
        "Not Responding": sum(1 for r in rows if r["Responding"] == "No"),
    }

    def clean(r):
        return {k: v for k, v in r.items() if not k.startswith("_")}

    return {"groups": [{"title": "Summary", "rows": summary}],
            "top_cpu": [clean(r) for r in top_cpu], "top_memory": [clean(r) for r in top_mem],
            "rows": [clean(r) for r in rows]}


def collect(ctx):
    return build(ctx.query("processes", SCRIPT, timeout=90))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("Top 10 by CPU time") + list_table(TOP_COLUMNS, data.get("top_cpu"))
            + sub_heading("Top 10 by working set") + list_table(TOP_COLUMNS, data.get("top_memory"))
            + sub_heading("All processes") + list_table(COLUMNS, data.get("rows")))


SECTION = Section(key="processes", title="Processes", group="Software", collect=collect, render=render, timeout=90)
```

`pc_report/sections/services.py`:

```python
"""Services: every Win32 service with state, start mode, account and binary path."""
from __future__ import annotations

from ..format import yes_no
from ..ps import cim
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

PROPS = ("Name", "DisplayName", "State", "StartMode", "StartName", "PathName", "ProcessId", "Description",
         "ServiceType", "DelayedAutoStart", "ExitCode")
SCRIPT = cim("Win32_Service", PROPS) + " | Sort-Object DisplayName"

COLUMNS = [("Display Name", "Display Name"), ("Name", "Name"), ("State", "State"), ("Start Mode", "Start Mode"),
           ("Start Name", "Log On As"), ("PID", "PID"), ("Type", "Type"), ("Exit Code", "Exit Code"),
           ("Path", "Path"), ("Description", "Description")]


def _start_mode(s):
    mode = str(s.get("StartMode") or "")
    if mode == "Auto":
        return "Automatic (Delayed)" if yes_no(s.get("DelayedAutoStart")) == "Yes" else "Automatic"
    return mode


def build(raw) -> dict:
    rows = [{
        "Display Name": s.get("DisplayName", ""), "Name": s.get("Name", ""), "State": s.get("State", ""),
        "Start Mode": _start_mode(s), "Start Name": s.get("StartName", ""),
        "PID": s.get("ProcessId") if s.get("ProcessId") else "", "Type": s.get("ServiceType", ""),
        "Exit Code": s.get("ExitCode"), "Path": s.get("PathName", ""), "Description": s.get("Description", ""),
    } for s in rows_of(raw)]
    rows.sort(key=lambda r: str(r["Display Name"]).lower())
    summary = {
        "Services": len(rows),
        "Running": sum(1 for r in rows if r["State"] == "Running"),
        "Stopped": sum(1 for r in rows if r["State"] == "Stopped"),
        "Automatic": sum(1 for r in rows if r["Start Mode"] == "Automatic"),
        "Automatic (Delayed)": sum(1 for r in rows if r["Start Mode"] == "Automatic (Delayed)"),
        "Manual": sum(1 for r in rows if r["Start Mode"] == "Manual"),
        "Disabled": sum(1 for r in rows if r["Start Mode"] == "Disabled"),
    }
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.query("services", SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Services") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="services", title="Services", group="Software", collect=collect, render=render, timeout=60)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Processes with owner/command line/top-10; Services with summary`

---

### Task 13: Drivers and Autorun

**Files:**
- Create: `pc_report/sections/drivers.py`, `pc_report/sections/autorun.py`
- Test: `tests/pc_report/test_drivers.py`, `tests/pc_report/test_autorun.py`
- Fixtures: `drivers/{signed_drivers,system_drivers}.json`, `autorun/{run_entries,scheduled_tasks}.json`

**Interfaces:**
- `drivers` data: `{"groups": [summary], "by_class": {class: [rows]}, "system": [rows]}`; each PnP row has `Device, Class, Version, Date, Provider, Manufacturer, INF, Signed, Signer, Device ID`. The Noldus Summary reads `by_class` values.

- [ ] **Step 1: Tests**

`tests/pc_report/test_drivers.py`:

```python
import unittest

from pc_report.sections import drivers as mod
from tests.pc_report import support

SIGNED = [{"DeviceName": "Basler pylon GigE", "DeviceClass": "NET", "DriverVersion": "7.1.0.1", "DriverDate": "20240101000000.000000-000",
           "DriverProviderName": "Basler AG", "Manufacturer": "Basler", "InfName": "oem42.inf", "IsSigned": True,
           "Signer": "Microsoft Windows Hardware Compatibility Publisher", "DeviceID": "PCI\\VEN_8086&DEV_1533\\1234"},
          {"DeviceName": "Generic Monitor", "DeviceClass": "MONITOR", "DriverVersion": "10.0.1", "DriverDate": None,
           "DriverProviderName": "Microsoft", "Manufacturer": "(Standard monitor types)", "InfName": "monitor.inf",
           "IsSigned": True, "Signer": "Microsoft Windows", "DeviceID": "DISPLAY\\ABC"}]
SYSTEM = [{"Name": "hasplms", "DisplayName": "Sentinel", "State": "Running", "StartMode": "Auto",
           "PathName": "C:\\Windows\\system32\\drivers\\hardlock.sys", "ServiceType": "Kernel Driver", "Started": True}]


class BuildTests(unittest.TestCase):
    def test_grouped_by_class_and_summary(self):
        data = mod.build(SIGNED, SYSTEM)
        self.assertEqual(sorted(data["by_class"]), ["Monitor", "NET"])
        net = data["by_class"]["NET"][0]
        self.assertEqual(net["Date"], "2024-01-01")
        self.assertEqual(net["Signed"], "Yes")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["PnP Drivers"], 2)
        self.assertEqual(rows["Unsigned Drivers"], 0)
        self.assertEqual(rows["System Drivers"], 1)
        self.assertEqual(data["system"][0]["Started"], "Yes")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>INF</th>", html)
        self.assertIn("<h3>System drivers</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_autorun.py`:

```python
import unittest

from pc_report.sections import autorun as mod
from tests.pc_report import support

RUN = [{"Name": "SecurityHealth", "Command": "%windir%\\system32\\SecurityHealthSystray.exe", "Location": "HKLM:\\...\\Run",
        "Enabled": True, "Kind": "Registry"},
       {"Name": "OneDrive", "Command": "C:\\Users\\user\\AppData\\OneDrive.exe /background", "Location": "HKCU:\\...\\Run",
        "Enabled": False, "Kind": "Registry"}]
TASKS = [{"Name": "NoldusUpdate", "Path": "\\Noldus\\", "State": "Ready", "Author": "Noldus", "Action": "C:\\x.exe /u",
          "Triggers": "Daily", "LastRun": "/Date(1758000000000)/", "NextRun": "/Date(1758100000000)/", "LastResult": 0,
          "Run As (account name)": "SYSTEM"}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(RUN, TASKS)
        one = next(r for r in data["entries"] if r["Name"] == "OneDrive")
        self.assertEqual(one["Enabled"], "No")
        self.assertEqual(data["tasks"][0]["Last Result"], "0x0")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Startup Entries"], 2)
        self.assertEqual(rows["Disabled Entries"], 1)
        self.assertEqual(rows["Scheduled Tasks (non-Microsoft)"], 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Startup entries</h3>", html)
        self.assertIn("<h3>Scheduled tasks</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/drivers.py`:

```python
"""Drivers: signed PnP drivers grouped by device class, plus kernel/file-system drivers."""
from __future__ import annotations

from ..format import fmt_date, yes_no
from ..ps import cim
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

SIGNED_PROPS = ("DeviceName", "DeviceClass", "DriverVersion", "DriverDate", "DriverProviderName", "Manufacturer",
                "InfName", "IsSigned", "Signer", "DeviceID")
SIGNED_SCRIPT = cim("Win32_PnPSignedDriver", SIGNED_PROPS) + " | Where-Object { $_.DeviceName } | Sort-Object DeviceClass, DeviceName"
SYSTEM_SCRIPT = cim("Win32_SystemDriver", ("Name", "DisplayName", "State", "StartMode", "PathName", "ServiceType", "Started")) + " | Sort-Object DisplayName"

PNP_COLUMNS = [("Device", "Device"), ("Version", "Version"), ("Date", "Date"), ("Provider", "Provider"),
               ("Manufacturer", "Manufacturer"), ("INF", "INF"), ("Signed", "Signed"), ("Signer", "Signer"),
               ("Device ID", "Device ID")]
SYS_COLUMNS = [("Display Name", "Display Name"), ("Name", "Name"), ("State", "State"), ("Start Mode", "Start Mode"),
               ("Started", "Started"), ("Type", "Type"), ("Path", "Path")]


def _class_title(name) -> str:
    """NET/USB/HID stay as-is; longer all-caps classes (MONITOR, DISPLAY) become Monitor, Display."""
    text = str(name or "Unknown")
    if text.isupper() and len(text) <= 4:
        return text
    return text.capitalize() if text.isupper() else text


def build(signed, system) -> dict:
    by_class: dict[str, list] = {}
    unsigned = 0
    for d in rows_of(signed):
        row = {"Device": d.get("DeviceName", ""), "Class": _class_title(d.get("DeviceClass")),
               "Version": d.get("DriverVersion", ""), "Date": fmt_date(d.get("DriverDate")) if d.get("DriverDate") else "",
               "Provider": d.get("DriverProviderName", ""), "Manufacturer": d.get("Manufacturer", ""),
               "INF": d.get("InfName", ""), "Signed": yes_no(d.get("IsSigned")), "Signer": d.get("Signer", ""),
               "Device ID": d.get("DeviceID", "")}
        if row["Signed"] == "No":
            unsigned += 1
        by_class.setdefault(row["Class"], []).append(row)
    by_class = dict(sorted(by_class.items()))
    system_rows = [{"Display Name": s.get("DisplayName", ""), "Name": s.get("Name", ""), "State": s.get("State", ""),
                    "Start Mode": s.get("StartMode", ""), "Started": yes_no(s.get("Started")),
                    "Type": s.get("ServiceType", ""), "Path": s.get("PathName", "")} for s in rows_of(system)]
    summary = {"PnP Drivers": sum(len(v) for v in by_class.values()), "Device Classes": len(by_class),
               "Unsigned Drivers": unsigned, "System Drivers": len(system_rows),
               "System Drivers Running": sum(1 for r in system_rows if r["State"] == "Running")}
    return {"groups": [{"title": "Summary", "rows": summary}], "by_class": by_class, "system": system_rows}


def collect(ctx):
    return build(ctx.query("signed_drivers", SIGNED_SCRIPT, timeout=90), ctx.query("system_drivers", SYSTEM_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    by_class = data.get("by_class") or {}
    if not by_class:
        out.append(sub_heading("PnP drivers") + list_table(PNP_COLUMNS, []))
    for cls, rows in by_class.items():
        out.append(sub_heading(f"{cls} ({len(rows)})") + list_table(PNP_COLUMNS, rows))
    out.append(sub_heading("System drivers") + list_table(SYS_COLUMNS, data.get("system")))
    return "".join(out)


SECTION = Section(key="drivers", title="Drivers", group="Software", collect=collect, render=render, timeout=90)
```

`pc_report/sections/autorun.py`:

```python
"""Autorun: Run/RunOnce keys, startup folders (with the StartupApproved enabled flag) and non-Microsoft scheduled tasks."""
from __future__ import annotations

from ..format import fmt_datetime, yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

RUN_SCRIPT = r"""
$keys = @('HKLM:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
          'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run',
          'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce')
$approved = @{}
foreach ($ap in 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32',
                'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder') {
  $p = Get-ItemProperty $ap -ErrorAction SilentlyContinue
  if ($p) { $p.PSObject.Properties | Where-Object { $_.Value -is [byte[]] -and $_.Value.Length -gt 0 } | ForEach-Object { $approved[$_.Name] = ($_.Value[0] -ne 3) } }
}
foreach ($k in $keys) {
  $p = Get-ItemProperty $k -ErrorAction SilentlyContinue
  if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS(Path|ParentPath|ChildName|Drive|Provider)$' } | ForEach-Object {
    $en = if ($approved.ContainsKey($_.Name)) { $approved[$_.Name] } else { $true }
    [pscustomobject]@{ Name = [string]$_.Name; Command = [string]$_.Value; Location = $k; Enabled = $en; Kind = 'Registry' } } }
}
foreach ($sf in 'Startup','CommonStartup') {
  $dir = [Environment]::GetFolderPath($sf)
  if ($dir -and (Test-Path $dir)) { Get-ChildItem $dir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'desktop.ini' } | ForEach-Object {
    $en = if ($approved.ContainsKey($_.Name)) { $approved[$_.Name] } else { $true }
    [pscustomobject]@{ Name = $_.Name; Command = $_.FullName; Location = $dir; Enabled = $en; Kind = 'Startup folder' } } }
}
"""

TASKS_SCRIPT = r"""
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskPath -notlike '\Microsoft\*' } | ForEach-Object {
  $info = $null; try { $info = $_ | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue } catch {}
  $act = ($_.Actions | ForEach-Object { if ($_.Execute) { "$($_.Execute) $($_.Arguments)".Trim() } }) -join '; '
  $trig = ($_.Triggers | ForEach-Object { $_.CimClass.CimClassName -replace '^MSFT_Task','' -replace 'Trigger$','' }) -join ', '
  [pscustomobject]@{ Name = $_.TaskName; Path = $_.TaskPath; State = [string]$_.State; Author = [string]$_.Author; Action = $act
    Triggers = $trig; LastRun = $info.LastRunTime; NextRun = $info.NextRunTime; LastResult = $info.LastTaskResult
    'Run As (account name)' = [string]$_.Principal.UserId }
}
"""

ENTRY_COLUMNS = [("Name", "Name"), ("Command", "Command"), ("Location", "Location"), ("Enabled", "Enabled"), ("Kind", "Kind")]
TASK_COLUMNS = [("Name", "Task"), ("Path", "Folder"), ("State", "State"), ("Author", "Author"), ("Action", "Action"),
                ("Triggers", "Triggers"), ("Last Run", "Last Run"), ("Next Run", "Next Run"), ("Last Result", "Last Result"),
                ("Run As (account name)", "Run As")]


def _hex(value):
    try:
        return f"0x{int(value) & 0xFFFFFFFF:X}"
    except (TypeError, ValueError):
        return "" if value is None else str(value)


def build(entries, tasks) -> dict:
    ent = [{"Name": e.get("Name", ""), "Command": e.get("Command", ""), "Location": e.get("Location", ""),
            "Enabled": yes_no(e.get("Enabled")), "Kind": e.get("Kind", "")} for e in rows_of(entries)]
    tsk = [{"Name": t.get("Name", ""), "Path": t.get("Path", ""), "State": t.get("State", ""), "Author": t.get("Author", ""),
            "Action": t.get("Action", ""), "Triggers": t.get("Triggers", ""), "Last Run": fmt_datetime(t.get("LastRun")),
            "Next Run": fmt_datetime(t.get("NextRun")), "Last Result": _hex(t.get("LastResult")),
            "Run As (account name)": t.get("Run As (account name)", "")} for t in rows_of(tasks)]
    summary = {"Startup Entries": len(ent), "Disabled Entries": sum(1 for e in ent if e["Enabled"] == "No"),
               "Scheduled Tasks (non-Microsoft)": len(tsk),
               "Tasks Ready or Running": sum(1 for t in tsk if t["State"] in ("Ready", "Running"))}
    return {"groups": [{"title": "Summary", "rows": summary}], "entries": ent, "tasks": tsk}


def collect(ctx):
    return build(ctx.query("run_entries", RUN_SCRIPT), ctx.query("scheduled_tasks", TASKS_SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Startup entries") + list_table(ENTRY_COLUMNS, data.get("entries"))
            + sub_heading("Scheduled tasks") + list_table(TASK_COLUMNS, data.get("tasks")))


SECTION = Section(key="autorun", title="Autorun", group="Software", collect=collect, render=render, timeout=60)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Drivers grouped by class with system drivers; Autorun with StartupApproved and tasks`

---

### Task 14: Codecs and MMC Snap-ins

**Files:**
- Create: `pc_report/sections/codecs.py`, `pc_report/sections/mmc_snapins.py`
- Test: `tests/pc_report/test_codecs.py`, `tests/pc_report/test_mmc_snapins.py`
- Fixtures: `codecs/{directshow,drivers32,media_foundation}.json`, `mmc_snapins/snapins.json`

**Interfaces:**
- `codecs` data: `{"groups": [summary], "categories": {category: [rows]}}`; rows have `Name, File, Version, Company, CLSID, Merit, Architecture, Source`. The Noldus Summary reads all category rows.

- [ ] **Step 1: Tests**

`tests/pc_report/test_codecs.py`:

```python
import unittest

from pc_report.sections import codecs as mod
from tests.pc_report import support

DS = [{"Category": "DirectShow Filters", "Name": "Noldus Resizer Filter", "CLSID": "{AAAA}", "File": "C:\\Program Files\\Common Files\\Noldus\\Resizer.ax",
       "Version": "1.2.3.4", "Company": "Noldus", "Merit": 2097152, "Architecture": "x64"},
      {"Category": "Video Compressors", "Name": "Cinepak", "CLSID": "{BBBB}", "File": "", "Version": "", "Company": "", "Merit": None, "Architecture": "x86"}]
D32 = [{"Name": "vidc.cvid", "File": "iccvid.dll", "Version": "10.0.1", "Company": "Microsoft", "Architecture": "x64"},
       {"Name": "msacm.l3acm", "File": "l3codeca.acm", "Version": "1.9", "Company": "Fraunhofer", "Architecture": "x86"}]
MF = [{"Category": "Media Foundation Transforms", "Name": "H264 Encoder MFT", "CLSID": "{CCCC}", "File": "mfh264enc.dll",
       "Version": "10.0", "Company": "Microsoft", "Architecture": "x64"}]


class BuildTests(unittest.TestCase):
    def test_categories_and_merit(self):
        data = mod.build(DS, D32, MF)
        self.assertIn("DirectShow Filters", data["categories"])
        self.assertIn("Video Compressors", data["categories"])
        self.assertIn("Video for Windows (VCM)", data["categories"])
        self.assertIn("Audio Compression Manager (ACM)", data["categories"])
        self.assertIn("Media Foundation Transforms", data["categories"])
        resizer = data["categories"]["DirectShow Filters"][0]
        self.assertEqual(resizer["Merit"], "0x200000 (Normal)")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["DirectShow Filters"], 1)
        self.assertEqual(rows["Total Entries"], 5)

    def test_merit_names(self):
        self.assertEqual(mod.merit(0x800000), "0x800000 (Preferred)")
        self.assertEqual(mod.merit(0x200001), "0x200001 (Normal+1)")
        self.assertEqual(mod.merit(None), "")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>CLSID</th>", html)
        self.assertIn("Video Compressors", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_mmc_snapins.py`:

```python
import unittest

from pc_report.sections import mmc_snapins as mod
from tests.pc_report import support

RAW = [{"CLSID": "{1234}", "Name": "Device Manager", "NameString": "Device Manager", "About": "{5678}", "Module": "C:\\Windows\\system32\\devmgr.dll",
        "Version": "10.0.1", "Company": "Microsoft Corporation", "Architecture": "x64"}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(RAW)
        self.assertEqual(data["rows"][0]["Name"], "Device Manager")
        self.assertEqual(data["rows"][0]["Module"], "C:\\Windows\\system32\\devmgr.dll")
        self.assertEqual(dict(data["groups"][0]["rows"])["Snap-ins"], 1)

    def test_indirect_name_falls_back(self):
        data = mod.build([{"CLSID": "{1}", "Name": "@devmgr.dll,-4", "NameString": "", "Module": "", "Version": "", "Company": "", "Architecture": "x64"}])
        self.assertEqual(data["rows"][0]["Name"], "@devmgr.dll,-4")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Module</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/codecs.py`:

```python
"""Codecs: DirectShow filter categories, VCM/ACM drivers and Media Foundation transforms, 64- and 32-bit."""
from __future__ import annotations

from ..section import Section, kv_groups, list_table, rows_of, sub_heading

# DirectShow category CLSIDs -> human names (the ones SIW and GraphStudio show).
DS_CATEGORIES = {
    "{083863F1-70DE-11D0-BD40-00A0C911CE86}": "DirectShow Filters",
    "{33D9A760-90C8-11D0-BD43-00A0C911CE86}": "Video Compressors",
    "{33D9A761-90C8-11D0-BD43-00A0C911CE86}": "Audio Compressors",
    "{33D9A762-90C8-11D0-BD43-00A0C911CE86}": "Audio Capture Sources",
    "{860BB310-5D01-11D0-BD3B-00A0C911CE86}": "Video Capture Sources",
    "{E0F158E1-CB04-11D0-BD4E-00A0C911CE86}": "Audio Renderers",
    "{CC7BFB41-F175-11D1-A392-00E0291F3959}": "WDM Streaming Capture Devices",
    "{CC7BFB46-F175-11D1-A392-00E0291F3959}": "WDM Streaming Rendering Devices",
    "{4EFE2452-168A-11D1-BC76-00C04FB9453B}": "Midi Renderers",
    "{7B8B58A4-26A8-11D1-A4C3-00A0C9BD4A21}": "External Renderers",
    "{DA4E3DA0-D07D-11D0-BD50-00A0C911CE86}": "Device Control Filters",
    "{2721AE20-7E70-11D0-A5D6-28DB04C10000}": "Video Compressors (Legacy)",
}

DIRECTSHOW_SCRIPT = r"""
$cats = @{
  '{083863F1-70DE-11D0-BD40-00A0C911CE86}' = 'DirectShow Filters'; '{33D9A760-90C8-11D0-BD43-00A0C911CE86}' = 'Video Compressors'
  '{33D9A761-90C8-11D0-BD43-00A0C911CE86}' = 'Audio Compressors'; '{33D9A762-90C8-11D0-BD43-00A0C911CE86}' = 'Audio Capture Sources'
  '{860BB310-5D01-11D0-BD3B-00A0C911CE86}' = 'Video Capture Sources'; '{E0F158E1-CB04-11D0-BD4E-00A0C911CE86}' = 'Audio Renderers'
  '{CC7BFB41-F175-11D1-A392-00E0291F3959}' = 'WDM Streaming Capture Devices'; '{CC7BFB46-F175-11D1-A392-00E0291F3959}' = 'WDM Streaming Rendering Devices'
  '{4EFE2452-168A-11D1-BC76-00C04FB9453B}' = 'Midi Renderers'; '{7B8B58A4-26A8-11D1-A4C3-00A0C9BD4A21}' = 'External Renderers'
  '{DA4E3DA0-D07D-11D0-BD50-00A0C911CE86}' = 'Device Control Filters'
}
$fileCache = @{}
function Get-FileMeta($path) {
  if (-not $path) { return @('', '') }
  $p = [Environment]::ExpandEnvironmentVariables($path.Trim('"'))
  if ($fileCache.ContainsKey($p)) { return $fileCache[$p] }
  $meta = @('', '')
  try { $vi = (Get-Item $p -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $meta = @([string]$vi.FileVersion, [string]$vi.CompanyName) } } catch {}
  $fileCache[$p] = $meta
  return $meta
}
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' }, @{ Root = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  foreach ($cat in $cats.Keys) {
    $inst = Join-Path (Join-Path $arch.Root $cat) 'Instance'
    if (-not (Test-Path $inst)) { continue }
    Get-ChildItem $inst -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      $clsid = [string]$x.CLSID
      $merit = $null
      if ($x.FilterData -is [byte[]] -and $x.FilterData.Length -ge 8) { $merit = [BitConverter]::ToUInt32($x.FilterData, 4) }
      $server = ''
      if ($clsid) { $server = [string](Get-ItemProperty (Join-Path (Join-Path $arch.Root $clsid) 'InprocServer32') -ErrorAction SilentlyContinue).'(default)' }
      $meta = Get-FileMeta $server
      [pscustomobject]@{ Category = $cats[$cat]; Name = [string]$x.FriendlyName; CLSID = $clsid; File = $server
                         Version = $meta[0]; Company = $meta[1]; Merit = $merit; Architecture = $arch.Name }
    }
  }
}
"""

DRIVERS32_SCRIPT = r"""
foreach ($arch in @(@{ Key = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Drivers32'; Name = 'x64'; Sys = "$env:SystemRoot\System32" },
                    @{ Key = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Drivers32'; Name = 'x86'; Sys = "$env:SystemRoot\SysWOW64" })) {
  $p = Get-ItemProperty $arch.Key -ErrorAction SilentlyContinue
  if (-not $p) { continue }
  $p.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS(Path|ParentPath|ChildName|Drive|Provider)$' -and $_.Name -match '^(vidc|msacm|icm|midi|wave|mixer|aux|msvideo)' } | ForEach-Object {
    $file = [string]$_.Value
    $full = if ([IO.Path]::IsPathRooted($file)) { $file } else { Join-Path $arch.Sys $file }
    $ver = ''; $co = ''
    try { $vi = (Get-Item $full -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $ver = [string]$vi.FileVersion; $co = [string]$vi.CompanyName } } catch {}
    [pscustomobject]@{ Name = [string]$_.Name; File = $file; Version = $ver; Company = $co; Architecture = $arch.Name }
  }
}
"""

MF_SCRIPT = r"""
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Classes\MediaFoundation\Transforms'; Clsid = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' },
                    @{ Root = 'HKLM:\SOFTWARE\Classes\WOW6432Node\MediaFoundation\Transforms'; Clsid = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  if (-not (Test-Path $arch.Root)) { continue }
  Get-ChildItem $arch.Root -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\{' } | ForEach-Object {
    $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
    $server = [string](Get-ItemProperty (Join-Path (Join-Path $arch.Clsid $_.PSChildName) 'InprocServer32') -ErrorAction SilentlyContinue).'(default)'
    $ver = ''; $co = ''
    try { $vi = (Get-Item ([Environment]::ExpandEnvironmentVariables($server)) -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $ver = [string]$vi.FileVersion; $co = [string]$vi.CompanyName } } catch {}
    [pscustomobject]@{ Category = 'Media Foundation Transforms'; Name = [string]$x.'(default)'; CLSID = $_.PSChildName; File = $server
                       Version = $ver; Company = $co; Architecture = $arch.Name }
  }
}
"""

_MERIT_BASE = [(0x800000, "Preferred"), (0x600000, "Normal"), (0x400000, "Unlikely"), (0x200000, "Normal"),
               (0x100000, "Software compressor"), (0x080000, "HW compressor"), (0x000001, "Do not use")]

COLUMNS = [("Name", "Name"), ("File", "File"), ("Version", "Version"), ("Company", "Company"), ("CLSID", "CLSID"),
           ("Merit", "Merit"), ("Architecture", "Architecture")]


def merit(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    for base, name in _MERIT_BASE:
        if n == base:
            return f"0x{n:X} ({name})"
        if base < n < base + 0x10000:
            return f"0x{n:X} ({name}+{n - base})"
    return f"0x{n:X}"


def build(directshow, drivers32, media_foundation) -> dict:
    categories: dict[str, list] = {}

    def add(category, row):
        categories.setdefault(category, []).append(row)

    for f in rows_of(directshow):
        add(f.get("Category") or "DirectShow Filters",
            {"Name": f.get("Name", ""), "File": f.get("File", ""), "Version": f.get("Version", ""), "Company": f.get("Company", ""),
             "CLSID": f.get("CLSID", ""), "Merit": merit(f.get("Merit")), "Architecture": f.get("Architecture", ""), "Source": "DirectShow"})
    for d in rows_of(drivers32):
        name = str(d.get("Name") or "")
        cat = "Audio Compression Manager (ACM)" if name.lower().startswith("msacm") else "Video for Windows (VCM)"
        add(cat, {"Name": name, "File": d.get("File", ""), "Version": d.get("Version", ""), "Company": d.get("Company", ""),
                  "CLSID": "", "Merit": "", "Architecture": d.get("Architecture", ""), "Source": "Drivers32"})
    for m in rows_of(media_foundation):
        add("Media Foundation Transforms",
            {"Name": m.get("Name", ""), "File": m.get("File", ""), "Version": m.get("Version", ""), "Company": m.get("Company", ""),
             "CLSID": m.get("CLSID", ""), "Merit": "", "Architecture": m.get("Architecture", ""), "Source": "Media Foundation"})
    order = list(DS_CATEGORIES.values()) + ["Video for Windows (VCM)", "Audio Compression Manager (ACM)", "Media Foundation Transforms"]
    ordered = {c: sorted(categories[c], key=lambda r: str(r["Name"]).lower()) for c in order if c in categories}
    for c in categories:
        if c not in ordered:
            ordered[c] = categories[c]
    summary = {c: len(rows) for c, rows in ordered.items()}
    summary["Total Entries"] = sum(summary.values())
    return {"groups": [{"title": "Summary", "rows": summary}], "categories": ordered}


def collect(ctx):
    return build(ctx.query("directshow", DIRECTSHOW_SCRIPT, timeout=90),
                 ctx.query("drivers32", DRIVERS32_SCRIPT),
                 ctx.query("media_foundation", MF_SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    cats = data.get("categories") or {}
    if not cats:
        out.append(list_table(COLUMNS, []))
    for cat, rows in cats.items():
        out.append(sub_heading(f"{cat} ({len(rows)})") + list_table(COLUMNS, rows))
    return "".join(out)


SECTION = Section(key="codecs", title="Codecs", group="Software", collect=collect, render=render, timeout=90)
```

`pc_report/sections/mmc_snapins.py`:

```python
"""MMC Snap-ins: registered console snap-ins with their module, version and company."""
from __future__ import annotations

from ..section import Section, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Microsoft\MMC\SnapIns'; Clsid = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' },
                    @{ Root = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\MMC\SnapIns'; Clsid = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  if (-not (Test-Path $arch.Root)) { continue }
  Get-ChildItem $arch.Root -ErrorAction SilentlyContinue | ForEach-Object {
    $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
    $clsid = $_.PSChildName
    $module = ''
    try { $module = [string](Get-ItemProperty (Join-Path (Join-Path $arch.Clsid $clsid) 'InprocServer32') -ErrorAction SilentlyContinue).'(default)' } catch {}
    if (-not $module -and $x.FxVersion) { $module = 'Managed (' + [string]$x.FxVersion + ')' }
    $ver = ''; $co = ''
    if ($module -and -not $module.StartsWith('Managed')) {
      try { $vi = (Get-Item ([Environment]::ExpandEnvironmentVariables($module)) -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $ver = [string]$vi.FileVersion; $co = [string]$vi.CompanyName } } catch {}
    }
    [pscustomobject]@{ CLSID = $clsid; Name = [string]$x.NameString; NameString = [string]$x.NameString; About = [string]$x.About
                       Module = $module; Version = $ver; Company = $co; Architecture = $arch.Name }
  }
}
"""

COLUMNS = [("Name", "Name"), ("Module", "Module"), ("Version", "Version"), ("Company", "Company"),
           ("CLSID", "CLSID"), ("Architecture", "Architecture")]


def build(raw) -> dict:
    rows = [{"Name": s.get("NameString") or s.get("Name") or s.get("CLSID", ""), "Module": s.get("Module", ""),
             "Version": s.get("Version", ""), "Company": s.get("Company", ""), "CLSID": s.get("CLSID", ""),
             "Architecture": s.get("Architecture", "")} for s in rows_of(raw)]
    rows.sort(key=lambda r: str(r["Name"]).lower())
    return {"groups": [{"title": "Summary", "rows": {"Snap-ins": len(rows)}}], "rows": rows}


def collect(ctx):
    return build(ctx.query("snapins", SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Snap-ins") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="mmc_snapins", title="MMC Snap-ins", group="Software", collect=collect, render=render, timeout=60)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Codecs across DirectShow categories, VCM/ACM and MFT; MMC Snap-ins with modules`

### Task 15: Motherboard and BIOS

**Files:**
- Create: `pc_report/sections/motherboard.py`, `pc_report/sections/bios.py`
- Test: `tests/pc_report/test_motherboard.py`, `tests/pc_report/test_bios.py`
- Fixtures: `motherboard/{baseboard,sockets,memory_array,slots,onboard,connectors}.json`, `bios/{bios,acpi,boot}.json`

**Interfaces:** `motherboard.build(...)` returns `{"groups": [...], "onboard": [...], "connectors": [...]}`; `bios.build(...)` returns `{"groups": [...]}`. Both are read by System Summary via `operating_system.value_of`-style lookups (`flatten` is provided by each module).

- [ ] **Step 1: Tests**

`tests/pc_report/test_motherboard.py`:

```python
import unittest

from pc_report.sections import motherboard as mod
from tests.pc_report import support

BB = {"Manufacturer": "Dell Inc.", "Product": "0ABC12", "Version": "A00", "SerialNumber": "/ABC123/", "Tag": "Base Board"}
SOCK = [{"SocketDesignation": "CPU 1", "UpgradeMethod": 1}]
ARR = [{"MaxCapacity": 134217728, "MaxCapacityEx": 134217728, "MemoryDevices": 4, "MemoryErrorCorrection": 3, "Use": 3, "Location": 3}]
SLOTS = [{"SlotDesignation": "PCIEX16_1", "CurrentUsage": 4, "MaxDataWidth": 10},
         {"SlotDesignation": "PCIEX1_1", "CurrentUsage": 3, "MaxDataWidth": 5}]
ONBOARD = [{"Description": "Realtek Audio", "DeviceType": 7, "Enabled": True}]
CONN = [{"ExternalReferenceDesignator": "USB1", "InternalReferenceDesignator": "", "ConnectorType": [16], "PortType": 16}]


class BuildTests(unittest.TestCase):
    def test_groups(self):
        rows = mod.flatten(mod.build(BB, SOCK, ARR, SLOTS, ONBOARD, CONN))
        self.assertEqual(rows["Manufacturer"], "Dell Inc.")
        self.assertEqual(rows["Model"], "0ABC12")
        self.assertEqual(rows["CPU Socket"], "CPU 1")
        self.assertEqual(rows["Maximum Memory"], "128.0 GB")
        self.assertEqual(rows["Memory Slots"], 4)
        self.assertEqual(rows["Error Correction"], "None")
        self.assertEqual(rows["Slots In Use"], "1 of 2")

    def test_tables(self):
        data = mod.build(BB, SOCK, ARR, SLOTS, ONBOARD, CONN)
        self.assertEqual(data["onboard"][0]["Type"], "Sound")
        self.assertEqual(data["connectors"][0]["Port Type"], "USB")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Manufacturer</th>", html)
        self.assertIn("<h3>External connectors</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_bios.py`:

```python
import unittest

from pc_report.sections import bios as mod
from tests.pc_report import support

BIOS = {"Manufacturer": "Dell Inc.", "Name": "1.2.3", "Version": "DELL   - 1072009", "SMBIOSBIOSVersion": "1.2.3",
        "SMBIOSMajorVersion": 3, "SMBIOSMinorVersion": 4, "ReleaseDate": "20250110000000.000000+000",
        "BiosCharacteristics": [4, 7, 9, 11, 12, 15, 16, 19, 26, 27, 28, 29, 32, 33, 40], "EmbeddedControllerMajorVersion": 1,
        "EmbeddedControllerMinorVersion": 9, "SystemBiosMajorVersion": 1, "SystemBiosMinorVersion": 2,
        "SerialNumber": "ABC123", "PrimaryBIOS": True, "Status": "OK", "CurrentLanguage": "en|US|iso8859-1"}
ACPI = [{"Table": "DSDT"}, {"Table": "FACP"}, {"Table": "SSDT"}]
BOOT = {"FirmwareType": "UEFI", "SecureBoot": 1}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        rows = mod.flatten(mod.build(BIOS, ACPI, BOOT))
        self.assertEqual(rows["Vendor"], "Dell Inc.")
        self.assertEqual(rows["SMBIOS Version"], "3.4")
        self.assertEqual(rows["Release Date"], "2025-01-10")
        self.assertEqual(rows["Embedded Controller Version"], "1.9")
        self.assertEqual(rows["Firmware Type"], "UEFI")
        self.assertEqual(rows["Secure Boot"], "Yes")
        self.assertEqual(rows["ACPI Tables"], "DSDT, FACP, SSDT")
        self.assertIn("Supports PCI", rows["Characteristics"])
        self.assertIn("Reserved (40)", rows["Characteristics"])


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>SMBIOS Version</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/motherboard.py`:

```python
"""Motherboard: baseboard identity, CPU socket, memory array, slot usage, onboard devices and connectors."""
from __future__ import annotations

from .. import decode
from ..format import kb_human, yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

BASEBOARD = cim("Win32_BaseBoard", ("Manufacturer", "Product", "Version", "SerialNumber", "Tag"))
SOCKETS = cim("Win32_Processor", ("SocketDesignation", "UpgradeMethod"))
MEMORY_ARRAY = cim("Win32_PhysicalMemoryArray", ("MaxCapacity", "MaxCapacityEx", "MemoryDevices", "MemoryErrorCorrection", "Use", "Location"))
SLOTS = cim("Win32_SystemSlot", ("SlotDesignation", "CurrentUsage", "MaxDataWidth"))
ONBOARD = cim("Win32_OnBoardDevice", ("Description", "DeviceType", "Enabled"))
CONNECTORS = cim("Win32_PortConnector", ("ExternalReferenceDesignator", "InternalReferenceDesignator", "ConnectorType", "PortType"))

ONBOARD_TYPES = {1: "Other", 2: "Unknown", 3: "Video", 4: "SCSI Controller", 5: "Ethernet", 6: "Token Ring",
                 7: "Sound", 8: "PATA Controller", 9: "SATA Controller", 10: "SAS Controller"}
MEMORY_USE = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "System memory", 4: "Video memory", 5: "Flash memory",
              6: "Non-volatile RAM", 7: "Cache memory"}
MEMORY_LOCATION = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "System board or motherboard", 4: "ISA add-on card",
                   5: "EISA add-on card", 6: "PCI add-on card", 7: "MCA add-on card", 8: "PCMCIA add-on card",
                   9: "Proprietary add-on card", 10: "NuBus"}
UPGRADE = {1: "Other", 2: "Unknown", 3: "Daughter Board", 4: "ZIF Socket", 5: "Replacement/Piggy Back", 6: "None",
           7: "LIF Socket", 8: "Slot 1", 9: "Slot 2", 10: "370 Pin Socket", 11: "Slot A", 12: "Slot M",
           13: "Socket 423", 14: "Socket A (Socket 462)", 15: "Socket 478", 16: "Socket 754", 17: "Socket 940",
           18: "Socket 939", 19: "Socket mPGA604", 20: "Socket LGA771", 21: "Socket LGA775", 22: "Socket S1",
           23: "Socket AM2", 24: "Socket F (1207)", 25: "Socket LGA1366", 26: "Socket G34", 27: "Socket AM3",
           28: "Socket C32", 29: "Socket LGA1156", 30: "Socket LGA1567", 31: "Socket PGA988A", 32: "Socket BGA1288",
           33: "rPGA988B", 34: "BGA1023", 35: "BGA1224", 36: "LGA1155", 37: "LGA1356", 38: "LGA2011", 39: "Socket FS1",
           40: "Socket FS2", 41: "Socket FM1", 42: "Socket FM2", 43: "Socket LGA2011-3", 44: "Socket LGA1356-3",
           45: "Socket LGA1150", 46: "Socket BGA1168", 47: "Socket BGA1234", 48: "Socket BGA1364", 49: "Socket AM4",
           50: "Socket LGA1151", 51: "Socket BGA1356", 52: "Socket BGA1440", 53: "Socket BGA1515", 54: "Socket LGA3647-1",
           55: "Socket SP3", 56: "Socket SP3r2", 57: "Socket LGA2066", 58: "Socket BGA1392", 59: "Socket BGA1510",
           60: "Socket BGA1528", 61: "Socket LGA4189", 62: "Socket LGA1200", 63: "Socket LGA4677", 64: "Socket LGA1700",
           65: "Socket BGA1744", 66: "Socket BGA1781", 67: "Socket BGA1211", 68: "Socket BGA2422", 69: "Socket LGA1211",
           70: "Socket LGA2422", 71: "Socket LGA5773", 72: "Socket BGA5773", 73: "Socket AM5", 74: "Socket SP5",
           75: "Socket SP6", 76: "Socket BGA883", 77: "Socket BGA1190", 78: "Socket BGA4129", 79: "Socket LGA4710",
           80: "Socket LGA7529", 81: "Socket BGA1964", 82: "Socket BGA1792", 83: "Socket BGA2049", 84: "Socket BGA2551",
           85: "Socket LGA1851", 86: "Socket BGA2114", 87: "Socket BGA2833"}

ONBOARD_COLUMNS = [("Description", "Description"), ("Type", "Type"), ("Enabled", "Enabled")]
CONNECTOR_COLUMNS = [("External", "External designator"), ("Internal", "Internal designator"),
                     ("Connector", "Connector"), ("Port Type", "Port Type")]


def build(baseboard, sockets, arrays, slots, onboard, connectors) -> dict:
    bb = baseboard or {}
    board = {"Manufacturer": bb.get("Manufacturer", ""), "Model": bb.get("Product", ""), "Version": bb.get("Version", ""),
             "Serial Number": bb.get("SerialNumber", ""), "Tag": bb.get("Tag", "")}
    sockets_rows = {}
    for i, s in enumerate(rows_of(sockets), 1):
        suffix = "" if i == 1 else f" {i}"
        sockets_rows[f"CPU Socket{suffix}"] = s.get("SocketDesignation", "")
        sockets_rows[f"Socket Type{suffix}"] = decode.lookup(UPGRADE, s.get("UpgradeMethod"))
    array_rows = {}
    for i, a in enumerate(rows_of(arrays), 1):
        suffix = "" if i == 1 else f" {i}"
        cap = a.get("MaxCapacityEx") or a.get("MaxCapacity")
        array_rows[f"Maximum Memory{suffix}"] = kb_human(cap) if cap else ""
        array_rows[f"Memory Slots{suffix}"] = a.get("MemoryDevices", "")
        array_rows[f"Error Correction{suffix}"] = decode.lookup(decode.ERROR_CORRECTION, a.get("MemoryErrorCorrection"))
        array_rows[f"Use{suffix}"] = decode.lookup(MEMORY_USE, a.get("Use"))
        array_rows[f"Location{suffix}"] = decode.lookup(MEMORY_LOCATION, a.get("Location"))
    slot_rows_raw = rows_of(slots)
    in_use = sum(1 for s in slot_rows_raw if decode.to_int(s.get("CurrentUsage")) == 4)
    widths: dict[str, int] = {}
    for s in slot_rows_raw:
        w = decode.lookup(decode.SLOT_MAX_DATA_WIDTH, s.get("MaxDataWidth")) or "Unknown"
        widths[w] = widths.get(w, 0) + 1
    slot_rows = {"Slots In Use": f"{in_use} of {len(slot_rows_raw)}" if slot_rows_raw else "",
                 "Slots By Width": ", ".join(f"{k}: {v}" for k, v in widths.items())}
    onboard_rows = [{"Description": o.get("Description", ""), "Type": decode.lookup(ONBOARD_TYPES, o.get("DeviceType")),
                     "Enabled": yes_no(o.get("Enabled"))} for o in rows_of(onboard)]
    conn_rows = [{"External": c.get("ExternalReferenceDesignator", ""), "Internal": c.get("InternalReferenceDesignator", ""),
                  "Connector": decode.lookup(decode.PORT_CONNECTOR_TYPES, c.get("ConnectorType")),
                  "Port Type": decode.lookup(decode.PORT_TYPES, c.get("PortType"))} for c in rows_of(connectors)]
    return {"groups": [{"title": "Board", "rows": board}, {"title": "Processor Socket", "rows": sockets_rows},
                       {"title": "Memory Array", "rows": array_rows}, {"title": "Expansion Slots", "rows": slot_rows}],
            "onboard": onboard_rows, "connectors": conn_rows}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(first_dict(ctx.query("baseboard", BASEBOARD)), ctx.query("sockets", SOCKETS),
                 ctx.query("memory_array", MEMORY_ARRAY), ctx.query("slots", SLOTS),
                 ctx.query("onboard", ONBOARD), ctx.query("connectors", CONNECTORS))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Onboard devices") + list_table(ONBOARD_COLUMNS, data.get("onboard"))
            + sub_heading("External connectors") + list_table(CONNECTOR_COLUMNS, data.get("connectors")))


SECTION = Section(key="motherboard", title="Motherboard", group="Hardware", collect=collect, render=render)
```

`pc_report/sections/bios.py`:

```python
"""BIOS: vendor, versions, release date, decoded characteristics, firmware type and ACPI tables."""
from __future__ import annotations

from .. import decode
from ..format import fmt_date, yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, rows_of

BIOS_PROPS = ("Manufacturer", "Name", "Version", "SMBIOSBIOSVersion", "SMBIOSMajorVersion", "SMBIOSMinorVersion",
              "ReleaseDate", "BiosCharacteristics", "EmbeddedControllerMajorVersion", "EmbeddedControllerMinorVersion",
              "SystemBiosMajorVersion", "SystemBiosMinorVersion", "SerialNumber", "PrimaryBIOS", "Status",
              "CurrentLanguage", "InstallableLanguages")
BIOS_SCRIPT = cim("Win32_BIOS", BIOS_PROPS)
ACPI_SCRIPT = ("Get-ChildItem 'HKLM:\\HARDWARE\\ACPI' -ErrorAction SilentlyContinue | ForEach-Object { "
               "[pscustomobject]@{ Table = $_.PSChildName } }")
BOOT_SCRIPT = ("[pscustomobject]@{ FirmwareType = [string]$env:firmware_type; SecureBoot = (Get-ItemProperty "
               "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecureBoot\\State' -ErrorAction SilentlyContinue).UEFISecureBootEnabled }")


def _ver(major, minor):
    if major in (None, "") or minor in (None, ""):
        return ""
    return f"{major}.{minor}"


def build(bios, acpi, boot) -> dict:
    bios, boot = bios or {}, boot or {}
    rows = {
        "Vendor": bios.get("Manufacturer", ""), "Name": bios.get("Name", ""), "Version": bios.get("Version", ""),
        "SMBIOS BIOS Version": bios.get("SMBIOSBIOSVersion", ""),
        "SMBIOS Version": _ver(bios.get("SMBIOSMajorVersion"), bios.get("SMBIOSMinorVersion")),
        "System BIOS Version": _ver(bios.get("SystemBiosMajorVersion"), bios.get("SystemBiosMinorVersion")),
        "Embedded Controller Version": _ver(bios.get("EmbeddedControllerMajorVersion"), bios.get("EmbeddedControllerMinorVersion")),
        "Release Date": fmt_date(bios.get("ReleaseDate")) if bios.get("ReleaseDate") else "",
        "Primary BIOS": yes_no(bios.get("PrimaryBIOS")), "Status": bios.get("Status", ""),
        "Current Language": bios.get("CurrentLanguage", ""), "Installable Languages": bios.get("InstallableLanguages", ""),
        "Serial Number": bios.get("SerialNumber", ""),
        "Firmware Type": boot.get("FirmwareType", ""), "Secure Boot": yes_no(boot.get("SecureBoot")),
        "Characteristics": decode.bios_characteristics(bios.get("BiosCharacteristics")),
        "ACPI Tables": ", ".join(str(t.get("Table")) for t in rows_of(acpi) if t.get("Table")),
    }
    return {"groups": [{"title": "BIOS", "rows": rows}]}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(first_dict(ctx.query("bios", BIOS_SCRIPT)), ctx.query("acpi", ACPI_SCRIPT),
                 first_dict(ctx.query("boot", BOOT_SCRIPT)))


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="bios", title="BIOS", group="Hardware", collect=collect, render=render)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Motherboard with sockets/array/slots/connectors; BIOS with decoded characteristics`

---

### Task 16: CPU

**Files:**
- Create: `pc_report/sections/cpu.py`
- Test: `tests/pc_report/test_cpu.py`
- Fixtures: `cpu/{processors,caches,registry,performance}.json`

**Interfaces:** `build(procs, caches, reg, perf, features) -> {"groups": [...], "caches": [...], "per_core": [...]}`; `flatten(data)`; `probe_features() -> dict[str, bool]` via `ctypes.windll.kernel32.IsProcessorFeaturePresent` (empty dict off Windows).

- [ ] **Step 1: Test `tests/pc_report/test_cpu.py`**

```python
import unittest

from pc_report.sections import cpu as mod
from tests.pc_report import support

PROC = [{"Name": "Intel(R) Core(TM) i7-12700 CPU @ 2.10GHz", "Manufacturer": "GenuineIntel", "Description": "Intel64 Family 6 Model 151 Stepping 2",
         "ProcessorId": "BFEBFBFF000906A2", "SocketDesignation": "U3E1", "Architecture": 9, "AddressWidth": 64, "DataWidth": 64,
         "NumberOfCores": 12, "NumberOfEnabledCore": 12, "NumberOfLogicalProcessors": 20, "ThreadCount": 20,
         "MaxClockSpeed": 2100, "CurrentClockSpeed": 2100, "ExtClock": 100, "L2CacheSize": 12288, "L3CacheSize": 25600,
         "VirtualizationFirmwareEnabled": True, "VMMonitorModeExtensions": True, "SecondLevelAddressTranslationExtensions": True,
         "LoadPercentage": 7, "Status": "OK", "CpuStatus": 1, "CurrentVoltage": 8, "Family": 198, "Level": 6, "Revision": 38914,
         "Stepping": "", "Characteristics": 252, "PartNumber": "", "Caption": "Intel64 Family 6 Model 151 Stepping 2"}]
CACHES = [{"Purpose": "L1 Cache", "Level": 3, "InstalledSize": 1024, "MaxCacheSize": 1024, "Associativity": 7, "CacheType": 5, "CacheSpeed": None, "Status": "OK"},
          {"Purpose": "L2 Cache", "Level": 4, "InstalledSize": 12288, "MaxCacheSize": 12288, "Associativity": 8, "CacheType": 5, "CacheSpeed": None, "Status": "OK"}]
REG = {"ProcessorNameString": "12th Gen Intel(R) Core(TM) i7-12700", "Identifier": "Intel64 Family 6 Model 151 Stepping 2",
       "VendorIdentifier": "GenuineIntel", "Update Revision": [0, 0, 0, 0, 44, 0, 0, 0], "Previous Update Revision": [0, 0, 0, 0, 43, 0, 0, 0],
       "~MHz": 2112, "FeatureSet": 3219913727, "Platform ID": 0}
PERF = [{"Path": "\\\\pc\\processor information(_total)\\% processor utility", "InstanceName": "_total", "CookedValue": 12.5},
        {"Path": "\\\\pc\\processor information(0,0)\\% processor performance", "InstanceName": "0,0", "CookedValue": 145.2},
        {"Path": "\\\\pc\\processor information(0,1)\\% processor performance", "InstanceName": "0,1", "CookedValue": 98.0}]
FEATURES = {"SSE2": True, "AVX2": True, "AVX-512F": False}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(PROC, CACHES, REG, PERF, FEATURES)
        self.rows = mod.flatten(self.data)

    def test_identity(self):
        self.assertEqual(self.rows["Name"], "12th Gen Intel(R) Core(TM) i7-12700")
        self.assertEqual(self.rows["Vendor"], "GenuineIntel")
        self.assertEqual(self.rows["Architecture"], "x64")
        self.assertEqual(self.rows["Family / Model / Stepping"], "6 / 151 / 2")
        self.assertEqual(self.rows["Cores / Threads"], "12 / 20")
        self.assertEqual(self.rows["Max Clock"], "2100 MHz")
        self.assertEqual(self.rows["Microcode Revision"], "0x2C")
        self.assertEqual(self.rows["Voltage"], "0.8 V")

    def test_virtualization_and_load(self):
        self.assertEqual(self.rows["Virtualization Enabled in Firmware"], "Yes")
        self.assertEqual(self.rows["Second Level Address Translation"], "Yes")
        self.assertEqual(self.rows["Load"], "7 %")
        self.assertEqual(self.rows["Processor Utility (sample)"], "12.5 %")
        self.assertEqual(self.data["per_core"][0], {"Core": "0,0", "Performance": "145.2 %"})

    def test_caches_and_features(self):
        self.assertEqual(self.data["caches"][0]["Level"], "L1")
        self.assertEqual(self.data["caches"][0]["Associativity"], "8-way")
        self.assertEqual(self.data["caches"][1]["Size"], "12.0 MB")
        self.assertEqual(self.rows["Instruction Sets"], "SSE2, AVX2")
        self.assertEqual(self.rows["Not Available"], "AVX-512F")

    def test_microcode_from_hex_string(self):
        self.assertEqual(mod.microcode("0x000000B4"), "0xB4")
        self.assertEqual(mod.microcode(None), "")

    def test_probe_features_returns_dict(self):
        self.assertIsInstance(mod.probe_features(), dict)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Name", "Cores / Threads", "Max Clock", "Instruction Sets"):
            self.assertIn(f"<th>{label}</th>", html)
        self.assertIn("<h3>Cache</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/cpu.py`**

```python
"""CPU: identity, topology, clocks, caches, virtualization, microcode, live load and instruction sets."""
from __future__ import annotations

import ctypes
import os
import re

from .. import decode
from ..format import kb_human, mhz, yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

PROC_PROPS = ("Name", "Manufacturer", "Description", "Caption", "ProcessorId", "SocketDesignation", "Architecture",
              "AddressWidth", "DataWidth", "NumberOfCores", "NumberOfEnabledCore", "NumberOfLogicalProcessors",
              "ThreadCount", "MaxClockSpeed", "CurrentClockSpeed", "ExtClock", "L2CacheSize", "L3CacheSize",
              "VirtualizationFirmwareEnabled", "VMMonitorModeExtensions", "SecondLevelAddressTranslationExtensions",
              "LoadPercentage", "Status", "CpuStatus", "CurrentVoltage", "Family", "Level", "Revision", "Stepping",
              "Characteristics", "PartNumber")
PROC_SCRIPT = cim("Win32_Processor", PROC_PROPS)
CACHE_SCRIPT = cim("Win32_CacheMemory", ("Purpose", "Level", "InstalledSize", "MaxCacheSize", "Associativity",
                                         "CacheType", "CacheSpeed", "Status"))
REG_SCRIPT = ("Get-ItemProperty 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0' -ErrorAction SilentlyContinue "
              "| Select-Object ProcessorNameString,Identifier,VendorIdentifier,'Update Revision','Previous Update Revision',"
              "'~MHz',FeatureSet,'Platform ID'")
PERF_SCRIPT = r"""
$paths = @('\Processor Information(_Total)\% Processor Utility', '\Processor Information(*)\% Processor Performance')
foreach ($p in $paths) {
  try { (Get-Counter -Counter $p -SampleInterval 1 -MaxSamples 1 -ErrorAction Stop).CounterSamples | ForEach-Object {
    [pscustomobject]@{ Path = $_.Path; InstanceName = $_.InstanceName; CookedValue = [double]$_.CookedValue } } } catch {}
}
"""

# IsProcessorFeaturePresent ids (winnt.h).
FEATURE_IDS = {"MMX": 3, "3DNow": 7, "SSE": 6, "SSE2": 10, "SSE3": 13, "SSSE3": 36, "SSE4.1": 37, "SSE4.2": 38,
               "AVX": 39, "AVX2": 40, "AVX-512F": 41, "CMPXCHG16B": 14, "XSAVE": 17, "NX": 12, "PAE": 9,
               "RDTSC": 8, "SLAT": 20, "Virtualization firmware": 21, "RDWRFSGSBASE": 22, "FASTFAIL": 23,
               "RDRAND": 28, "RDTSCP": 32, "RDPID": 33, "ERMS": 42}

CACHE_COLUMNS = [("Level", "Level"), ("Purpose", "Purpose"), ("Size", "Size"), ("Type", "Type"),
                 ("Associativity", "Associativity"), ("Speed", "Speed"), ("Status", "Status")]
CORE_COLUMNS = [("Core", "Core"), ("Performance", "Performance")]
_FMS = re.compile(r"Family (\d+) Model (\d+) Stepping (\d+)")


def probe_features() -> dict[str, bool]:
    if os.name != "nt":
        return {}
    try:
        fn = ctypes.windll.kernel32.IsProcessorFeaturePresent
    except (AttributeError, OSError):
        return {}
    out = {}
    for name, fid in FEATURE_IDS.items():
        try:
            out[name] = bool(fn(fid))
        except Exception:
            out[name] = False
    return out


def microcode(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, list) and len(value) >= 8:
        try:
            n = int.from_bytes(bytes(int(b) & 0xFF for b in value[4:8]), "little")
            return f"0x{n:X}"
        except (TypeError, ValueError):
            return ""
    try:
        n = int(str(value), 16) if str(value).lower().startswith("0x") else int(value)
        return f"0x{n:X}"
    except (TypeError, ValueError):
        return str(value)


def build(procs, caches, reg, perf, features) -> dict:
    p = first_dict(procs)
    reg, features = reg or {}, features or {}
    desc = p.get("Description") or reg.get("Identifier") or ""
    fms = _FMS.search(str(desc))
    identity = {
        "Name": reg.get("ProcessorNameString") or p.get("Name", ""),
        "WMI Name": p.get("Name", "") if reg.get("ProcessorNameString") else "",
        "Vendor": p.get("Manufacturer") or reg.get("VendorIdentifier", ""),
        "Description": desc, "Processor ID": p.get("ProcessorId", ""), "Socket": p.get("SocketDesignation", ""),
        "Architecture": decode.lookup(decode.CPU_ARCHITECTURE, p.get("Architecture")),
        "Family / Model / Stepping": " / ".join(fms.groups()) if fms else "",
        "Address Width": f"{p.get('AddressWidth')} bit" if p.get("AddressWidth") else "",
        "Data Width": f"{p.get('DataWidth')} bit" if p.get("DataWidth") else "",
        "Part Number": (p.get("PartNumber") or "").strip(),
        "Status": p.get("Status", ""), "CPU Status": decode.lookup(decode.CPU_STATUS, p.get("CpuStatus")),
    }
    n_sockets = len(rows_of(procs))
    topology = {
        "Sockets": n_sockets,
        "Cores / Threads": f"{p.get('NumberOfCores', '')} / {p.get('NumberOfLogicalProcessors', '')}",
        "Enabled Cores": p.get("NumberOfEnabledCore", ""),
        "Max Clock": mhz(p.get("MaxClockSpeed")), "Current Clock": mhz(p.get("CurrentClockSpeed")),
        "External Clock": mhz(p.get("ExtClock")), "Registry Clock": mhz(reg.get("~MHz")),
        "Voltage": f"{decode.to_int(p.get('CurrentVoltage')) / 10:.1f} V" if decode.to_int(p.get("CurrentVoltage")) else "",
        "L2 Cache (WMI)": kb_human(p.get("L2CacheSize")) if p.get("L2CacheSize") else "",
        "L3 Cache (WMI)": kb_human(p.get("L3CacheSize")) if p.get("L3CacheSize") else "",
    }
    virt = {
        "Virtualization Enabled in Firmware": yes_no(p.get("VirtualizationFirmwareEnabled")),
        "VM Monitor Mode Extensions": yes_no(p.get("VMMonitorModeExtensions")),
        "Second Level Address Translation": yes_no(p.get("SecondLevelAddressTranslationExtensions")),
        "Microcode Revision": microcode(reg.get("Update Revision")),
        "Previous Microcode Revision": microcode(reg.get("Previous Update Revision")),
    }
    total = next((s for s in rows_of(perf) if "utility" in str(s.get("Path", "")).lower()), None)
    load = {"Load": f"{p.get('LoadPercentage')} %" if p.get("LoadPercentage") is not None else "",
            "Processor Utility (sample)": f"{float(total['CookedValue']):.1f} %" if total else ""}
    per_core = [{"Core": s.get("InstanceName", ""), "Performance": f"{float(s.get('CookedValue') or 0):.1f} %"}
                for s in rows_of(perf) if "performance" in str(s.get("Path", "")).lower() and s.get("InstanceName") != "_total"]
    have = [n for n, ok in features.items() if ok]
    missing = [n for n, ok in features.items() if not ok]
    instr = {"Instruction Sets": ", ".join(have), "Not Available": ", ".join(missing)}
    cache_rows = [{"Level": decode.lookup(decode.CACHE_LEVEL, c.get("Level")), "Purpose": c.get("Purpose", ""),
                   "Size": kb_human(c.get("InstalledSize")) if c.get("InstalledSize") else "",
                   "Type": decode.lookup(decode.CACHE_TYPE, c.get("CacheType")),
                   "Associativity": decode.lookup(decode.CACHE_ASSOCIATIVITY, c.get("Associativity")),
                   "Speed": f"{c.get('CacheSpeed')} ns" if c.get("CacheSpeed") else "", "Status": c.get("Status", "")}
                  for c in rows_of(caches)]
    return {"groups": [{"title": "Processor", "rows": identity}, {"title": "Topology and Clocks", "rows": topology},
                       {"title": "Virtualization and Microcode", "rows": virt}, {"title": "Load", "rows": load},
                       {"title": "Instruction Sets", "rows": instr}],
            "caches": cache_rows, "per_core": per_core}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(ctx.query("processors", PROC_SCRIPT), ctx.query("caches", CACHE_SCRIPT),
                 first_dict(ctx.query("registry", REG_SCRIPT)), ctx.query("performance", PERF_SCRIPT, timeout=30),
                 probe_features())


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Cache") + list_table(CACHE_COLUMNS, data.get("caches"))
            + sub_heading("Per-core performance (1 s sample)") + list_table(CORE_COLUMNS, data.get("per_core")))


SECTION = Section(key="cpu", title="CPU", group="Hardware", collect=collect, render=render, timeout=30)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): CPU section with caches, microcode, feature probe and per-core sample`

---

### Task 17: Memory

**Files:**
- Create: `pc_report/sections/memory.py`
- Test: `tests/pc_report/test_memory.py`
- Fixtures: `memory/{array,modules,os,perf}.json`

- [ ] **Step 1: Test `tests/pc_report/test_memory.py`**

```python
import unittest

from pc_report.sections import memory as mod
from tests.pc_report import support

ARR = [{"MaxCapacity": 134217728, "MaxCapacityEx": 134217728, "MemoryDevices": 4, "MemoryErrorCorrection": 3}]
MODS = [{"DeviceLocator": "DIMM 1", "BankLabel": "BANK 0", "Capacity": 17179869184, "Speed": 3200, "ConfiguredClockSpeed": 3200,
         "ConfiguredVoltage": 1200, "MinVoltage": 1200, "MaxVoltage": 1200, "DataWidth": 64, "TotalWidth": 64, "FormFactor": 8,
         "MemoryType": 0, "SMBIOSMemoryType": 26, "TypeDetail": 128, "Manufacturer": "Kingston", "PartNumber": "KF3200C16D4/16GX ",
         "SerialNumber": "1234ABCD", "Tag": "Physical Memory 0"},
        {"DeviceLocator": "DIMM 3", "BankLabel": "BANK 2", "Capacity": 17179869184, "Speed": 3200, "ConfiguredClockSpeed": 2933,
         "ConfiguredVoltage": 1200, "MinVoltage": 1200, "MaxVoltage": 1200, "DataWidth": 64, "TotalWidth": 72, "FormFactor": 8,
         "MemoryType": 0, "SMBIOSMemoryType": 26, "TypeDetail": 8320, "Manufacturer": "Kingston", "PartNumber": "KF3200C16D4/16GX",
         "SerialNumber": "5678EF01", "Tag": "Physical Memory 2"}]
OS = {"TotalVisibleMemorySize": 33357824, "FreePhysicalMemory": 20000000, "TotalVirtualMemorySize": 38000000,
      "FreeVirtualMemory": 24000000, "SizeStoredInPagingFiles": 4718592, "FreeSpaceInPagingFiles": 4600000}
PERF = {"CommittedBytes": 15000000000, "CommitLimit": 38912000000, "AvailableBytes": 20480000000, "CacheBytes": 900000000,
        "PoolPagedBytes": 500000000, "PoolNonpagedBytes": 400000000}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(ARR, MODS, OS, PERF)
        self.rows = mod.flatten(self.data)

    def test_summary(self):
        self.assertEqual(self.rows["Installed Memory"], "32.0 GB")
        self.assertEqual(self.rows["Slots Used"], "2 of 4")
        self.assertEqual(self.rows["Memory Type"], "DDR4")
        self.assertEqual(self.rows["Total Physical"], "31.8 GB")
        self.assertEqual(self.rows["Memory Load"], "40.0 %")
        self.assertEqual(self.rows["Committed"], "14.0 GB of 36.2 GB")

    def test_modules(self):
        m = self.data["modules"][1]
        self.assertEqual(m["Capacity"], "16.0 GB")
        self.assertEqual(m["Speed"], "3200 MT/s")
        self.assertEqual(m["Configured Speed"], "2933 MT/s")
        self.assertEqual(m["Voltage"], "1.2 V")
        self.assertEqual(m["ECC"], "Yes")
        self.assertEqual(m["Form Factor"], "DIMM")
        self.assertEqual(m["Type Detail"], "Synchronous, Registered (Buffered)")
        self.assertEqual(m["Part Number"], "KF3200C16D4/16GX")

    def test_notes_mention_spd(self):
        self.assertIn("SPD", self.rows["Timings"])


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Installed Memory</th>", html)
        self.assertIn("<th>Part Number</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/memory.py`**

```python
"""Memory: array, every module with SMBIOS detail, and live OS/commit figures."""
from __future__ import annotations

from .. import decode
from ..format import bytes_human, kb_human, percent
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

ARRAY_SCRIPT = cim("Win32_PhysicalMemoryArray", ("MaxCapacity", "MaxCapacityEx", "MemoryDevices", "MemoryErrorCorrection"))
MODULE_PROPS = ("DeviceLocator", "BankLabel", "Capacity", "Speed", "ConfiguredClockSpeed", "ConfiguredVoltage", "MinVoltage",
                "MaxVoltage", "DataWidth", "TotalWidth", "FormFactor", "MemoryType", "SMBIOSMemoryType", "TypeDetail",
                "Manufacturer", "PartNumber", "SerialNumber", "Tag")
MODULE_SCRIPT = cim("Win32_PhysicalMemory", MODULE_PROPS)
OS_SCRIPT = cim("Win32_OperatingSystem", ("TotalVisibleMemorySize", "FreePhysicalMemory", "TotalVirtualMemorySize",
                                          "FreeVirtualMemory", "SizeStoredInPagingFiles", "FreeSpaceInPagingFiles"))
PERF_SCRIPT = cim("Win32_PerfFormattedData_PerfOS_Memory", ("CommittedBytes", "CommitLimit", "AvailableBytes", "CacheBytes",
                                                            "PoolPagedBytes", "PoolNonpagedBytes"))

COLUMNS = [("Slot", "Slot"), ("Bank", "Bank"), ("Capacity", "Capacity"), ("Type", "Type"), ("Speed", "Speed"),
           ("Configured Speed", "Configured Speed"), ("Voltage", "Voltage"), ("Data Width", "Data Width"),
           ("Total Width", "Total Width"), ("ECC", "ECC"), ("Form Factor", "Form Factor"), ("Type Detail", "Type Detail"),
           ("Manufacturer", "Manufacturer"), ("Part Number", "Part Number"), ("Serial Number", "Serial Number")]


def _volt(mv):
    n = decode.to_int(mv)
    return f"{n / 1000:.1f} V" if n else ""


def _mts(v):
    n = decode.to_int(v)
    return f"{n} MT/s" if n else ""


def build(arrays, modules, os_, perf) -> dict:
    arr = first_dict(arrays)
    os_, perf = os_ or {}, perf or {}
    mods = []
    total = 0
    types = set()
    for m in rows_of(modules):
        cap = decode.to_int(m.get("Capacity")) or 0
        total += cap
        mtype = decode.lookup(decode.MEMORY_TYPES, m.get("SMBIOSMemoryType") or m.get("MemoryType"))
        if mtype and mtype not in ("Unknown", "Other"):
            types.add(mtype)
        dw, tw = decode.to_int(m.get("DataWidth")), decode.to_int(m.get("TotalWidth"))
        mods.append({
            "Slot": m.get("DeviceLocator", ""), "Bank": m.get("BankLabel", ""), "Capacity": bytes_human(cap) if cap else "",
            "Type": mtype, "Speed": _mts(m.get("Speed")), "Configured Speed": _mts(m.get("ConfiguredClockSpeed")),
            "Voltage": _volt(m.get("ConfiguredVoltage")) or _volt(m.get("MaxVoltage")),
            "Data Width": f"{dw} bit" if dw else "", "Total Width": f"{tw} bit" if tw else "",
            "ECC": "Yes" if dw and tw and tw > dw else ("No" if dw and tw else ""),
            "Form Factor": decode.lookup(decode.FORM_FACTORS, m.get("FormFactor")),
            "Type Detail": ", ".join(decode.flags(decode.TYPE_DETAIL, m.get("TypeDetail"))),
            "Manufacturer": str(m.get("Manufacturer") or "").strip(), "Part Number": str(m.get("PartNumber") or "").strip(),
            "Serial Number": str(m.get("SerialNumber") or "").strip(),
        })
    slots = decode.to_int(arr.get("MemoryDevices"))
    total_kb = decode.to_int(os_.get("TotalVisibleMemorySize"))
    free_kb = decode.to_int(os_.get("FreePhysicalMemory"))
    used_kb = (total_kb - free_kb) if total_kb and free_kb is not None else None
    summary = {
        "Installed Memory": bytes_human(total) if total else "",
        "Maximum Capacity": kb_human(arr.get("MaxCapacityEx") or arr.get("MaxCapacity")) if arr else "",
        "Slots Used": f"{len(mods)} of {slots}" if slots else str(len(mods) or ""),
        "Memory Type": ", ".join(sorted(types)),
        "Error Correction": decode.lookup(decode.ERROR_CORRECTION, arr.get("MemoryErrorCorrection")),
        "Timings": "CAS/RAS timings and XMP profiles are read from SPD and need a vendor tool; not reported here.",
    }
    live = {
        "Total Physical": kb_human(total_kb) if total_kb else "",
        "Free Physical": kb_human(free_kb) if free_kb is not None else "",
        "Used Physical": kb_human(used_kb) if used_kb is not None else "",
        "Memory Load": percent(used_kb, total_kb) if used_kb is not None else "",
        "Total Virtual": kb_human(os_.get("TotalVirtualMemorySize")) if os_.get("TotalVirtualMemorySize") else "",
        "Free Virtual": kb_human(os_.get("FreeVirtualMemory")) if os_.get("FreeVirtualMemory") else "",
        "Paging Files": kb_human(os_.get("SizeStoredInPagingFiles")) if os_.get("SizeStoredInPagingFiles") else "",
        "Paging Files Free": kb_human(os_.get("FreeSpaceInPagingFiles")) if os_.get("FreeSpaceInPagingFiles") else "",
        "Committed": (f"{bytes_human(perf['CommittedBytes'])} of {bytes_human(perf['CommitLimit'])}"
                      if perf.get("CommittedBytes") and perf.get("CommitLimit") else ""),
        "Available": bytes_human(perf["AvailableBytes"]) if perf.get("AvailableBytes") else "",
        "System Cache": bytes_human(perf["CacheBytes"]) if perf.get("CacheBytes") else "",
        "Paged Pool": bytes_human(perf["PoolPagedBytes"]) if perf.get("PoolPagedBytes") else "",
        "Non-paged Pool": bytes_human(perf["PoolNonpagedBytes"]) if perf.get("PoolNonpagedBytes") else "",
    }
    return {"groups": [{"title": "Summary", "rows": summary}, {"title": "Operating System View", "rows": live}],
            "modules": mods}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(ctx.query("array", ARRAY_SCRIPT), ctx.query("modules", MODULE_SCRIPT),
                 first_dict(ctx.query("os", OS_SCRIPT)), first_dict(ctx.query("perf", PERF_SCRIPT)))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Modules") + list_table(COLUMNS, data.get("modules"))


SECTION = Section(key="memory", title="Memory", group="Hardware", collect=collect, render=render)
```

Expected values in the test: `33357824 KB` → 31.8 GB; used = 13357824 KB → 40.0 %; `15000000000 B` → 14.0 GB; `38912000000 B` → 36.2 GB; TypeDetail 8320 = 128 + 8192 → "Synchronous, Registered (Buffered)".

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Memory with per-module SMBIOS detail and live commit figures`

---

### Task 18: Sensors

**Files:**
- Create: `pc_report/sections/sensors.py`
- Test: `tests/pc_report/test_sensors.py`
- Fixtures: `sensors/{thermal,fans,probes,battery,counters}.json`

- [ ] **Step 1: Test `tests/pc_report/test_sensors.py`**

```python
import unittest

from pc_report.sections import sensors as mod
from tests.pc_report import support

THERMAL = [{"InstanceName": "ACPI\\ThermalZone\\TZ00_0", "CurrentTemperature": 3132, "CriticalTripPoint": 3782, "PassiveTripPoint": 0, "ActiveTripPoint": [0]}]
FANS = [{"Name": "Cooling Device", "DesiredSpeed": None, "Status": "OK", "ActiveCooling": True}]
PROBES = {"Temperature": [], "Voltage": [{"Name": "VCORE", "CurrentReading": 1200, "Status": "OK"}]}
BATTERY = [{"Name": "DELL 1234", "BatteryStatus": 2, "EstimatedChargeRemaining": 87, "EstimatedRunTime": 71582788, "DesignVoltage": 11400, "Chemistry": 6}]
COUNTERS = [{"Path": "\\\\pc\\processor information(_total)\\% processor utility", "InstanceName": "_total", "CookedValue": 9.7},
            {"Path": "\\\\pc\\memory\\% committed bytes in use", "InstanceName": "", "CookedValue": 38.2},
            {"Path": "\\\\pc\\memory\\available mbytes", "InstanceName": "", "CookedValue": 19532},
            {"Path": "\\\\pc\\physicaldisk(0 c:)\\% disk time", "InstanceName": "0 c:", "CookedValue": 3.1},
            {"Path": "\\\\pc\\physicaldisk(_total)\\% disk time", "InstanceName": "_total", "CookedValue": 3.1},
            {"Path": "\\\\pc\\gpu engine(pid_1234_luid_0x0_0x1_phys_0_engtype_3d)\\utilization percentage", "InstanceName": "pid_1234_luid_0x0_0x1_phys_0_engtype_3d", "CookedValue": 4.0},
            {"Path": "\\\\pc\\gpu engine(pid_99_luid_0x0_0x1_phys_0_engtype_3d)\\utilization percentage", "InstanceName": "pid_99_luid_0x0_0x1_phys_0_engtype_3d", "CookedValue": 1.5},
            {"Path": "\\\\pc\\gpu adapter memory(luid_0x0_0x1_phys_0)\\dedicated usage", "InstanceName": "luid_0x0_0x1_phys_0", "CookedValue": 1073741824},
            {"Path": "\\\\pc\\network interface(intel ethernet)\\bytes total/sec", "InstanceName": "intel ethernet", "CookedValue": 125000}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(THERMAL, FANS, PROBES, BATTERY, COUNTERS)

    def test_thermal_zone_in_celsius(self):
        tz = self.data["thermal"][0]
        self.assertEqual(tz["Zone"], "TZ00_0")
        self.assertEqual(tz["Temperature"], "40.05 °C")
        self.assertEqual(tz["Critical"], "105.05 °C")

    def test_battery(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Battery Status"], "Unknown / AC power")
        self.assertEqual(rows["Charge"], "87 %")
        self.assertEqual(rows["Estimated Runtime"], "")  # 71582788 means "on AC"
        self.assertEqual(rows["Chemistry"], "Lithium-ion")

    def test_counters(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["CPU Utility"], "9.7 %")
        self.assertEqual(rows["Memory Committed"], "38.2 %")
        self.assertEqual(rows["Memory Available"], "19532 MB")
        self.assertEqual(rows["GPU 3D Utilization (all processes)"], "5.5 %")
        self.assertEqual(self.data["disks"][0], {"Disk": "0 c:", "Active": "3.1 %"})
        self.assertEqual(self.data["gpus"][0]["Dedicated Memory In Use"], "1.0 GB")
        self.assertEqual(self.data["nics"][0]["Throughput"], "1.0 Mbps")

    def test_voltage_probe(self):
        self.assertEqual(self.data["probes"][0], {"Kind": "Voltage", "Name": "VCORE", "Reading": "1.200 V", "Status": "OK"})


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>CPU Utility</th>", html)
        self.assertIn("vendor tool", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/sensors.py`**

```python
"""Sensors: ACPI thermal zones, fans, probes, battery and a one-second performance-counter sample."""
from __future__ import annotations

from .. import decode
from ..format import bitrate_to_mbps, bytes_human, yes_no
from ..ps import cim
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

THERMAL_SCRIPT = cim("MSAcpi_ThermalZoneTemperature", ("InstanceName", "CurrentTemperature", "CriticalTripPoint",
                                                        "PassiveTripPoint", "ActiveTripPoint"), namespace="root/wmi")
FANS_SCRIPT = cim("Win32_Fan", ("Name", "DesiredSpeed", "Status", "ActiveCooling"))
PROBES_SCRIPT = ("[pscustomobject]@{ Temperature = @(" + cim("Win32_TemperatureProbe", ("Name", "CurrentReading", "Status"))
                 + "); Voltage = @(" + cim("Win32_VoltageProbe", ("Name", "CurrentReading", "Status")) + ") }")
BATTERY_SCRIPT = cim("Win32_Battery", ("Name", "BatteryStatus", "EstimatedChargeRemaining", "EstimatedRunTime",
                                       "DesignVoltage", "Chemistry"))
COUNTERS_SCRIPT = r"""
$paths = @('\Processor Information(_Total)\% Processor Utility', '\Memory\% Committed Bytes In Use', '\Memory\Available MBytes',
           '\PhysicalDisk(*)\% Disk Time', '\GPU Engine(*engtype_3D)\Utilization Percentage',
           '\GPU Adapter Memory(*)\Dedicated Usage', '\Network Interface(*)\Bytes Total/sec')
foreach ($p in $paths) {
  try { (Get-Counter -Counter $p -SampleInterval 1 -MaxSamples 1 -ErrorAction Stop).CounterSamples | ForEach-Object {
    [pscustomobject]@{ Path = $_.Path; InstanceName = $_.InstanceName; CookedValue = [double]$_.CookedValue } } } catch {}
}
"""

BATTERY_STATUS = {1: "Discharging", 2: "Unknown / AC power", 3: "Fully charged", 4: "Low", 5: "Critical", 6: "Charging",
                  7: "Charging and high", 8: "Charging and low", 9: "Charging and critical", 10: "Undefined",
                  11: "Partially charged"}
CHEMISTRY = {1: "Other", 2: "Unknown", 3: "Lead acid", 4: "Nickel cadmium", 5: "Nickel metal hydride", 6: "Lithium-ion",
             7: "Zinc air", 8: "Lithium polymer"}

THERMAL_COLUMNS = [("Zone", "Zone"), ("Temperature", "Temperature"), ("Passive Trip", "Passive trip"), ("Critical", "Critical")]
FAN_COLUMNS = [("Name", "Name"), ("Speed", "Desired speed"), ("Active Cooling", "Active cooling"), ("Status", "Status")]
PROBE_COLUMNS = [("Kind", "Kind"), ("Name", "Name"), ("Reading", "Reading"), ("Status", "Status")]
DISK_COLUMNS = [("Disk", "Disk"), ("Active", "Active time")]
GPU_COLUMNS = [("Adapter", "Adapter (LUID)"), ("Dedicated Memory In Use", "Dedicated Memory In Use")]
NIC_COLUMNS = [("Interface", "Interface"), ("Throughput", "Throughput")]


def _celsius(tenths_kelvin):
    """ACPI reports tenths of Kelvin; do the subtraction in hundredths to avoid float rounding surprises."""
    n = decode.to_int(tenths_kelvin)
    if not n:
        return ""
    return f"{(n * 10 - 27315) / 100:.2f} °C"


def _lc(sample) -> str:
    return str(sample.get("Path", "")).lower()


def build(thermal, fans, probes, battery, counters) -> dict:
    thermal_rows = [{"Zone": str(t.get("InstanceName", "")).rsplit("\\", 1)[-1], "Temperature": _celsius(t.get("CurrentTemperature")),
                     "Passive Trip": _celsius(t.get("PassiveTripPoint")), "Critical": _celsius(t.get("CriticalTripPoint"))}
                    for t in rows_of(thermal)]
    fan_rows = [{"Name": f.get("Name", ""), "Speed": f"{f.get('DesiredSpeed')} RPM" if f.get("DesiredSpeed") else "",
                 "Active Cooling": yes_no(f.get("ActiveCooling")), "Status": f.get("Status", "")} for f in rows_of(fans)]
    probes = probes if isinstance(probes, dict) else {}
    probe_rows = []
    for p in rows_of(probes.get("Temperature")):
        probe_rows.append({"Kind": "Temperature", "Name": p.get("Name", ""), "Reading": _celsius(p.get("CurrentReading")), "Status": p.get("Status", "")})
    for p in rows_of(probes.get("Voltage")):
        mv = decode.to_int(p.get("CurrentReading"))
        probe_rows.append({"Kind": "Voltage", "Name": p.get("Name", ""), "Reading": f"{mv / 1000:.3f} V" if mv else "", "Status": p.get("Status", "")})
    battery_rows = {}
    for i, b in enumerate(rows_of(battery), 1):
        suffix = "" if i == 1 else f" {i}"
        runtime = decode.to_int(b.get("EstimatedRunTime"))
        battery_rows.update({
            f"Battery{suffix}": b.get("Name", ""), f"Battery Status{suffix}": decode.lookup(BATTERY_STATUS, b.get("BatteryStatus")),
            f"Charge{suffix}": f"{b.get('EstimatedChargeRemaining')} %" if b.get("EstimatedChargeRemaining") is not None else "",
            f"Estimated Runtime{suffix}": f"{runtime} min" if runtime and runtime < 71582788 else "",
            f"Design Voltage{suffix}": f"{decode.to_int(b.get('DesignVoltage')) / 1000:.1f} V" if decode.to_int(b.get("DesignVoltage")) else "",
            f"Chemistry{suffix}": decode.lookup(CHEMISTRY, b.get("Chemistry")),
        })
    if not battery_rows:
        battery_rows = {"Battery": "None (desktop or no battery reported)"}

    samples = rows_of(counters)

    def one(fragment):
        for s in samples:
            if fragment in _lc(s):
                return s.get("CookedValue")
        return None
    gpu3d = sum(float(s.get("CookedValue") or 0) for s in samples if "gpu engine" in _lc(s) and "engtype_3d" in _lc(s))
    live = {
        "CPU Utility": f"{float(one('% processor utility')):.1f} %" if one("% processor utility") is not None else "",
        "Memory Committed": f"{float(one('% committed bytes in use')):.1f} %" if one("% committed bytes in use") is not None else "",
        "Memory Available": f"{int(float(one('available mbytes')))} MB" if one("available mbytes") is not None else "",
        "GPU 3D Utilization (all processes)": f"{gpu3d:.1f} %" if any("gpu engine" in _lc(s) for s in samples) else "",
        "Temperatures": "CPU/GPU core temperatures need a vendor tool (HWiNFO, vendor utilities); only ACPI zones are shown.",
    }
    disks = [{"Disk": s.get("InstanceName", ""), "Active": f"{float(s.get('CookedValue') or 0):.1f} %"}
             for s in samples if "physicaldisk" in _lc(s) and s.get("InstanceName") != "_total"]
    gpus = [{"Adapter": s.get("InstanceName", ""), "Dedicated Memory In Use": bytes_human(int(float(s.get("CookedValue") or 0)))}
            for s in samples if "gpu adapter memory" in _lc(s)]
    nics = [{"Interface": s.get("InstanceName", ""), "Throughput": bitrate_to_mbps(int(float(s.get("CookedValue") or 0) * 8))}
            for s in samples if "network interface" in _lc(s)]
    return {"groups": [{"title": "Live Sample (1 s)", "rows": live}, {"title": "Battery", "rows": battery_rows}],
            "thermal": thermal_rows, "fans": fan_rows, "probes": probe_rows, "disks": disks, "gpus": gpus, "nics": nics}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(ctx.query("thermal", THERMAL_SCRIPT), ctx.query("fans", FANS_SCRIPT),
                 ctx.query("probes", PROBES_SCRIPT), ctx.query("battery", BATTERY_SCRIPT),
                 ctx.query("counters", COUNTERS_SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("ACPI thermal zones") + list_table(THERMAL_COLUMNS, data.get("thermal"))
            + sub_heading("Fans") + list_table(FAN_COLUMNS, data.get("fans"))
            + sub_heading("Probes") + list_table(PROBE_COLUMNS, data.get("probes"))
            + sub_heading("Disk activity") + list_table(DISK_COLUMNS, data.get("disks"))
            + sub_heading("GPU memory") + list_table(GPU_COLUMNS, data.get("gpus"))
            + sub_heading("Network throughput") + list_table(NIC_COLUMNS, data.get("nics")))


SECTION = Section(key="sensors", title="Sensors", group="Hardware", collect=collect, render=render, timeout=60)
```

`PROBES_SCRIPT` returns one object whose `Temperature`/`Voltage` are arrays; `first_dict` is not used because `ctx.query` already returns the single object (ConvertTo-Json of one object is a dict). `build` guards with `isinstance(probes, dict)`.

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Sensors with thermal zones, battery and live counter sample`

---

### Task 19: Devices, PCI, System Slots

**Files:**
- Create: `pc_report/sections/devices.py`, `pc_report/sections/pci.py`, `pc_report/sections/system_slots.py`
- Test: `tests/pc_report/test_devices.py`, `tests/pc_report/test_pci.py`, `tests/pc_report/test_system_slots.py`
- Fixtures: `_shared/pnp_entities.json` (captured once, reused), `pci/pnp_properties.json`, `system_slots/slots.json`

**Interfaces:** `devices.build(pnp) -> {"groups": [summary], "problems": [...], "by_class": {cls: [rows]}}`. The Cameras section (Task 25) and Noldus Summary read `by_class`.

- [ ] **Step 1: Tests**

`tests/pc_report/test_devices.py`:

```python
import unittest

from pc_report.sections import devices as mod
from tests.pc_report import support

PNP = [{"Name": "Basler ace acA1920", "Manufacturer": "Basler", "PNPClass": "Camera", "ClassGuid": "{ca3e7ab9}", "DeviceID": "USB\\VID_2676&PID_BA02\\123",
        "PNPDeviceID": "USB\\VID_2676&PID_BA02\\123", "Status": "OK", "ConfigManagerErrorCode": 0, "Service": "usbvideo", "Present": True, "Description": "Basler camera"},
       {"Name": "Unknown device", "Manufacturer": "", "PNPClass": None, "ClassGuid": None, "DeviceID": "ACPI\\PNP0A0A\\0",
        "PNPDeviceID": "ACPI\\PNP0A0A\\0", "Status": "Error", "ConfigManagerErrorCode": 28, "Service": None, "Present": True, "Description": "Unknown device"},
       {"Name": "Old printer", "Manufacturer": "HP", "PNPClass": "Printer", "ClassGuid": "{x}", "DeviceID": "SWD\\PRINTENUM\\1",
        "PNPDeviceID": "SWD\\PRINTENUM\\1", "Status": "Unknown", "ConfigManagerErrorCode": 0, "Service": None, "Present": False, "Description": "Printer"}]


class BuildTests(unittest.TestCase):
    def test_problems_first_and_grouping(self):
        data = mod.build(PNP)
        self.assertEqual(data["problems"][0]["Problem"], "28: Drivers not installed")
        self.assertIn("Camera", data["by_class"])
        self.assertIn("(No class)", data["by_class"])
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Devices"], 3)
        self.assertEqual(rows["Present"], 2)
        self.assertEqual(rows["Problem Devices"], 1)
        self.assertEqual(rows["Not Present (phantom)"], 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Problem devices</h3>", html)
        self.assertIn("<th>Service</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_pci.py`:

```python
import unittest

from pc_report.sections import pci as mod
from tests.pc_report import support

PNP = [{"Name": "Intel(R) Ethernet Connection I219-LM", "Manufacturer": "Intel", "PNPClass": "Net", "DeviceID": "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\3&11583659&0&FE",
        "PNPDeviceID": "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\3&11583659&0&FE", "Status": "OK", "ConfigManagerErrorCode": 0, "Service": "e1dexpress", "Present": True},
       {"Name": "USB Root Hub", "PNPClass": "USB", "DeviceID": "USB\\ROOT_HUB30\\4", "PNPDeviceID": "USB\\ROOT_HUB30\\4", "Status": "OK", "ConfigManagerErrorCode": 0, "Present": True}]
PROPS = [{"InstanceId": "PCI\\VEN_8086&DEV_15BB&SUBSYS_08B21028&REV_10\\3&11583659&0&FE", "Location": "PCI bus 0, device 31, function 6",
          "DriverVersion": "12.19.2.45", "DriverDate": "/Date(1700000000000)/", "Bus": 0, "Address": 2031622}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(PNP, PROPS)
        self.assertEqual(len(data["rows"]), 1)
        r = data["rows"][0]
        self.assertEqual(r["Vendor"], "Intel Corporation")
        self.assertEqual(r["Vendor ID"], "8086")
        self.assertEqual(r["Device ID"], "15BB")
        self.assertEqual(r["Subsystem"], "08B21028")
        self.assertEqual(r["Revision"], "10")
        self.assertEqual(r["Bus / Device / Function"], "0 / 31 / 6")
        self.assertEqual(r["Driver Version"], "12.19.2.45")

    def test_parse_ids(self):
        self.assertEqual(mod.parse_ids("PCI\\VEN_10DE&DEV_2204&SUBSYS_38971462&REV_A1\\4&x"), ("10DE", "2204", "38971462", "A1"))
        self.assertEqual(mod.parse_ids("PCI\\VEN_10DE&DEV_2204\\x"), ("10DE", "2204", "", ""))


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Vendor ID</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_system_slots.py`:

```python
import unittest

from pc_report.sections import system_slots as mod
from tests.pc_report import support

RAW = [{"SlotDesignation": "PCIEX16_1", "CurrentUsage": 4, "MaxDataWidth": 10, "ConnectorType": [43], "Status": "OK",
        "SupportsHotPlug": False, "BusNumber": 1, "DeviceNumber": 0, "FunctionNumber": 0, "Shared": False, "Number": 1}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        r = mod.build(RAW)["rows"][0]
        self.assertEqual(r["Designation"], "PCIEX16_1")
        self.assertEqual(r["Usage"], "In use")
        self.assertEqual(r["Data Width"], "x16")
        self.assertEqual(r["Bus / Device / Function"], "1 / 0 / 0")
        self.assertEqual(r["Hot Plug"], "No")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Designation</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/devices.py`:

```python
"""Devices: problem devices first, then every PnP device grouped by class (shared PnP dump)."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

COLUMNS = [("Name", "Name"), ("Manufacturer", "Manufacturer"), ("Status", "Status"), ("Present", "Present"),
           ("Service", "Service"), ("Device Instance", "Device Instance")]
PROBLEM_COLUMNS = [("Name", "Name"), ("Class", "Class"), ("Problem", "Problem"), ("Manufacturer", "Manufacturer"),
                   ("Device Instance", "Device Instance")]


def build(pnp) -> dict:
    by_class: dict[str, list] = {}
    problems = []
    present = 0
    for d in rows_of(pnp):
        code = decode.to_int(d.get("ConfigManagerErrorCode")) or 0
        is_present = bool(d.get("Present"))
        present += is_present
        cls = d.get("PNPClass") or "(No class)"
        row = {"Name": d.get("Name") or d.get("Description") or "", "Class": cls, "Manufacturer": d.get("Manufacturer") or "",
               "Status": d.get("Status") or "", "Present": yes_no(is_present), "Service": d.get("Service") or "",
               "Device Instance": d.get("PNPDeviceID") or d.get("DeviceID") or ""}
        by_class.setdefault(cls, []).append(row)
        if code and is_present:
            problems.append({**row, "Problem": f"{code}: {decode.lookup(decode.PNP_ERROR_CODES, code)}"})
    by_class = dict(sorted(by_class.items(), key=lambda kv: kv[0].lower()))
    total = sum(len(v) for v in by_class.values())
    summary = {"Devices": total, "Present": present, "Not Present (phantom)": total - present,
               "Problem Devices": len(problems), "Classes": len(by_class)}
    return {"groups": [{"title": "Summary", "rows": summary}], "problems": problems, "by_class": by_class}


def collect(ctx):
    return build(ctx.shared("pnp_entities"))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups")), sub_heading("Problem devices"), list_table(PROBLEM_COLUMNS, data.get("problems"))]
    by_class = data.get("by_class") or {}
    if not by_class:
        out.append(list_table(COLUMNS, []))
    for cls, rows in by_class.items():
        out.append(sub_heading(f"{cls} ({len(rows)})") + list_table(COLUMNS, rows))
    return "".join(out)


SECTION = Section(key="devices", title="Devices", group="Hardware", collect=collect, render=render, timeout=60)
```

`pc_report/sections/pci.py`:

```python
"""PCI: every PCI device with vendor/device/subsystem IDs, location and driver version."""
from __future__ import annotations

import re

from .. import decode
from ..format import fmt_date
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

PROPS_SCRIPT = r"""
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'PCI\*' } | ForEach-Object {
  $props = Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_LocationInfo','DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverDate','DEVPKEY_Device_BusNumber','DEVPKEY_Device_Address' -ErrorAction SilentlyContinue
  $h = @{}; foreach ($p in $props) { $h[$p.KeyName] = $p.Data }
  [pscustomobject]@{ InstanceId = $_.InstanceId; Location = [string]$h['DEVPKEY_Device_LocationInfo']; DriverVersion = [string]$h['DEVPKEY_Device_DriverVersion']
                     DriverDate = $h['DEVPKEY_Device_DriverDate']; Bus = $h['DEVPKEY_Device_BusNumber']; Address = $h['DEVPKEY_Device_Address'] }
}
"""

COLUMNS = [("Name", "Name"), ("Vendor", "Vendor"), ("Vendor ID", "Vendor ID"), ("Device ID", "Device ID"),
           ("Subsystem", "Subsystem"), ("Revision", "Revision"), ("Class", "Class"),
           ("Bus / Device / Function", "Bus / Device / Function"), ("Location", "Location"),
           ("Driver Version", "Driver Version"), ("Driver Date", "Driver Date"), ("Status", "Status"), ("Instance", "Instance")]
_IDS = re.compile(r"VEN_([0-9A-Fa-f]{4})&DEV_([0-9A-Fa-f]{4})(?:&SUBSYS_([0-9A-Fa-f]{8}))?(?:&REV_([0-9A-Fa-f]{2}))?")


def parse_ids(instance_id: str):
    m = _IDS.search(str(instance_id or ""))
    if not m:
        return "", "", "", ""
    ven, dev, sub, rev = m.groups()
    return ven.upper(), dev.upper(), (sub or "").upper(), (rev or "").upper()


def _bdf(props: dict) -> str:
    bus, addr = decode.to_int(props.get("Bus")), decode.to_int(props.get("Address"))
    if bus is None or addr is None:
        return ""
    return f"{bus} / {(addr >> 16) & 0xFFFF} / {addr & 0xFFFF}"


def build(pnp, props) -> dict:
    by_id = {str(p.get("InstanceId") or "").upper(): p for p in rows_of(props)}
    rows = []
    for d in rows_of(pnp):
        inst = str(d.get("PNPDeviceID") or d.get("DeviceID") or "")
        if not inst.upper().startswith("PCI\\"):
            continue
        ven, dev, sub, rev = parse_ids(inst)
        p = by_id.get(inst.upper(), {})
        rows.append({"Name": d.get("Name") or "", "Vendor": decode.pci_vendor(ven), "Vendor ID": ven, "Device ID": dev,
                     "Subsystem": sub, "Revision": rev, "Class": d.get("PNPClass") or "", "Bus / Device / Function": _bdf(p),
                     "Location": p.get("Location", ""), "Driver Version": p.get("DriverVersion", ""),
                     "Driver Date": fmt_date(p.get("DriverDate")) if p.get("DriverDate") else "",
                     "Status": d.get("Status") or "", "Instance": inst})
    rows.sort(key=lambda r: (r["Bus / Device / Function"] == "", r["Bus / Device / Function"], r["Name"].lower()))
    vendors: dict[str, int] = {}
    for r in rows:
        vendors[r["Vendor"]] = vendors.get(r["Vendor"], 0) + 1
    summary = {"PCI Devices": len(rows), "Vendors": ", ".join(f"{k} ({v})" for k, v in sorted(vendors.items()))}
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.shared("pnp_entities"), ctx.query("pnp_properties", PROPS_SCRIPT, timeout=90))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Devices") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="pci", title="PCI", group="Hardware", collect=collect, render=render, timeout=90)
```

`Address` 2031622 = `0x1F0006` → device 31, function 6.

`pc_report/sections/system_slots.py`:

```python
"""System Slots: expansion slots with usage, width, connector, hot-plug and PCI address."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..ps import cim
from ..section import Section, list_table, rows_of

SCRIPT = cim("Win32_SystemSlot", ("SlotDesignation", "CurrentUsage", "MaxDataWidth", "ConnectorType", "Status",
                                  "SupportsHotPlug", "BusNumber", "DeviceNumber", "FunctionNumber", "Shared", "Number"))

COLUMNS = [("Designation", "Designation"), ("Usage", "Usage"), ("Data Width", "Data Width"), ("Connector", "Connector"),
           ("Bus / Device / Function", "Bus / Device / Function"), ("Hot Plug", "Hot Plug"), ("Shared", "Shared"),
           ("Status", "Status")]


def build(raw) -> dict:
    rows = []
    for s in rows_of(raw):
        parts = [s.get("BusNumber"), s.get("DeviceNumber"), s.get("FunctionNumber")]
        bdf = " / ".join(str(p) for p in parts) if all(p is not None for p in parts) else ""
        rows.append({"Designation": s.get("SlotDesignation", ""), "Usage": decode.lookup(decode.SLOT_USAGE, s.get("CurrentUsage")),
                     "Data Width": decode.lookup(decode.SLOT_MAX_DATA_WIDTH, s.get("MaxDataWidth")),
                     "Connector": decode.lookup(decode.PORT_CONNECTOR_TYPES, s.get("ConnectorType")),
                     "Bus / Device / Function": bdf, "Hot Plug": yes_no(s.get("SupportsHotPlug")),
                     "Shared": yes_no(s.get("Shared")), "Status": s.get("Status", "")})
    return {"rows": rows}


def collect(ctx):
    return build(ctx.query("slots", SCRIPT))


def render(data, ctx):
    return list_table(COLUMNS, (data or {}).get("rows") if isinstance(data, dict) else None)


SECTION = Section(key="system_slots", title="System Slots", group="Hardware", collect=collect, render=render)
```

- [ ] **Step 3: Standard steps 3–5**

The shared PnP dump is written to `tests/fixtures/pc_report/_shared/pnp_entities.json` the first time any capture touches it. It is large (a few hundred KB); that is acceptable, but review it for hostnames in device names (Bluetooth devices can carry phone names) and edit them out.

Commit message: `feat(pc_report): Devices by class with problem list; PCI with IDs and location; System Slots`

### Task 20: Network Adapters

**Files:**
- Create: `pc_report/sections/network_adapters.py`
- Test: `tests/pc_report/test_network_adapters.py`
- Fixtures: `network_adapters/{adapters,advanced,ip_interfaces,wmi}.json`

**Interfaces:** `build(adapters, advanced, ipif, wmi) -> {"groups": [summary], "adapters": [{"name", "groups", "advanced"}], "gige": [rows]}`. `gige` (per physical adapter: name, link speed, jumbo packet, receive buffers, transmit buffers, interrupt moderation) is consumed by the Noldus Summary.

- [ ] **Step 1: Test `tests/pc_report/test_network_adapters.py`**

```python
import unittest

from pc_report.sections import network_adapters as mod
from tests.pc_report import support

ADAPTERS = [{"Name": "Ethernet", "InterfaceDescription": "Intel(R) Ethernet Connection I219-LM", "ifIndex": 12, "Status": "Up",
             "MacAddress": "AA-BB-CC-DD-EE-FF", "LinkSpeed": "1 Gbps", "MediaType": "802.3", "PhysicalMediaType": "802.3",
             "MtuSize": 1500, "DriverVersion": "12.19.2.45", "DriverDate": "2023-10-05", "DriverProvider": "Intel",
             "DriverFileName": "e1d68x64.sys", "DriverDescription": "Intel(R) Ethernet Connection I219-LM", "PnPDeviceID": "PCI\\VEN_8086&DEV_15BB\\3",
             "InterfaceGuid": "{guid}", "Virtual": False, "Hidden": False, "FullDuplex": True, "PromiscuousMode": False,
             "ReceiveLinkSpeed": 1000000000, "TransmitLinkSpeed": 1000000000, "ConnectorPresent": True, "NdisVersion": "6.85"}]
ADVANCED = [{"Name": "Ethernet", "DisplayName": "Jumbo Packet", "DisplayValue": "9014 Bytes", "RegistryKeyword": "*JumboPacket", "RegistryValue": ["9014"]},
            {"Name": "Ethernet", "DisplayName": "Receive Buffers", "DisplayValue": "2048", "RegistryKeyword": "*ReceiveBuffers", "RegistryValue": ["2048"]},
            {"Name": "Ethernet", "DisplayName": "Interrupt Moderation", "DisplayValue": "Enabled", "RegistryKeyword": "*InterruptModeration", "RegistryValue": ["1"]}]
IPIF = [{"ifIndex": 12, "AddressFamily": 2, "NlMtu": 1500, "InterfaceMetric": 25, "Dhcp": 1, "ConnectionState": 1},
        {"ifIndex": 12, "AddressFamily": 23, "NlMtu": 1500, "InterfaceMetric": 25, "Dhcp": 1, "ConnectionState": 1}]
WMI = [{"Name": "Intel(R) Ethernet Connection I219-LM", "NetConnectionID": "Ethernet", "NetConnectionStatus": 2, "PhysicalAdapter": True,
        "AdapterType": "Ethernet 802.3", "Speed": 1000000000, "MACAddress": "AA:BB:CC:DD:EE:FF", "Manufacturer": "Intel",
        "PNPDeviceID": "PCI\\VEN_8086&DEV_15BB\\3", "Index": 3, "InterfaceIndex": 12, "TimeOfLastReset": "/Date(1758000000000)/"}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(ADAPTERS, ADVANCED, IPIF, WMI)

    def test_adapter_groups(self):
        a = self.data["adapters"][0]
        rows = {}
        for g in a["groups"]:
            rows.update(g["rows"])
        self.assertEqual(a["name"], "Ethernet")
        self.assertEqual(rows["Description"], "Intel(R) Ethernet Connection I219-LM")
        self.assertEqual(rows["Link Speed"], "1 Gbps")
        self.assertEqual(rows["Connection Status"], "Connected")
        self.assertEqual(rows["IPv4 Metric"], 25)
        self.assertEqual(rows["IPv4 DHCP"], "Enabled")
        self.assertEqual(rows["Physical"], "Yes")
        self.assertEqual(rows["Adapter Type"], "Ethernet 802.3")

    def test_advanced_and_gige(self):
        self.assertEqual(self.data["adapters"][0]["advanced"][0]["Property"], "Jumbo Packet")
        g = self.data["gige"][0]
        self.assertEqual(g["Jumbo Packet"], "9014 Bytes")
        self.assertEqual(g["Receive Buffers"], "2048")
        self.assertEqual(g["Interrupt Moderation"], "Enabled")
        self.assertEqual(g["Transmit Buffers"], "")

    def test_summary(self):
        rows = dict(self.data["groups"][0]["rows"])
        self.assertEqual(rows["Adapters"], 1)
        self.assertEqual(rows["Physical Adapters"], 1)
        self.assertEqual(rows["Connected"], 1)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Link Speed</th>", html)
        self.assertIn("<th>MAC Address</th>", html)
        self.assertNotIn("AA-BB-CC-DD-EE-FF", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/network_adapters.py`**

```python
"""Network Adapters: NDIS view, WMI view, IP interface settings and every advanced property per adapter."""
from __future__ import annotations

from .. import decode
from ..format import fmt_date, fmt_datetime, yes_no
from ..ps import cim
from ..section import Section, as_list, kv_groups, list_table, rows_of, sub_heading

ADAPTERS_SCRIPT = ("Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object Name,InterfaceDescription,ifIndex,Status,"
                   "MacAddress,LinkSpeed,MediaType,PhysicalMediaType,MtuSize,DriverVersion,DriverDate,DriverProvider,"
                   "DriverFileName,DriverDescription,PnPDeviceID,InterfaceGuid,Virtual,Hidden,FullDuplex,PromiscuousMode,"
                   "ReceiveLinkSpeed,TransmitLinkSpeed,ConnectorPresent,NdisVersion")
ADVANCED_SCRIPT = ("Get-NetAdapterAdvancedProperty -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,"
                   "DisplayValue,RegistryKeyword,RegistryValue")
IPIF_SCRIPT = ("Get-NetIPInterface -ErrorAction SilentlyContinue | Select-Object ifIndex,AddressFamily,NlMtu,"
               "InterfaceMetric,Dhcp,ConnectionState")
WMI_SCRIPT = cim("Win32_NetworkAdapter", ("Name", "NetConnectionID", "NetConnectionStatus", "PhysicalAdapter", "AdapterType",
                                          "Speed", "MACAddress", "Manufacturer", "PNPDeviceID", "Index", "InterfaceIndex",
                                          "TimeOfLastReset"))

GIGE_KEYWORDS = {"*JumboPacket": "Jumbo Packet", "*ReceiveBuffers": "Receive Buffers", "*TransmitBuffers": "Transmit Buffers",
                 "*InterruptModeration": "Interrupt Moderation", "*FlowControl": "Flow Control", "*EEE": "Energy-Efficient Ethernet",
                 "*SpeedDuplex": "Speed and Duplex", "*RSS": "Receive Side Scaling"}
ADV_COLUMNS = [("Property", "Property"), ("Value", "Value"), ("Keyword", "Registry keyword"), ("Raw", "Registry value")]
GIGE_COLUMNS = [("Adapter", "Adapter"), ("Link Speed", "Link Speed")] + [(v, v) for v in GIGE_KEYWORDS.values()]
DHCP = {0: "", 1: "Enabled", 2: "Disabled"}
CONNECTION = {0: "", 1: "Connected", 2: "Disconnected"}


def build(adapters, advanced, ipif, wmi) -> dict:
    adv_by_name: dict[str, list] = {}
    for a in rows_of(advanced):
        adv_by_name.setdefault(str(a.get("Name") or ""), []).append(a)
    ip_by_index: dict[int, dict] = {}
    for i in rows_of(ipif):
        fam = "IPv6" if decode.to_int(i.get("AddressFamily")) == 23 else "IPv4"
        ip_by_index.setdefault(decode.to_int(i.get("ifIndex")), {})[fam] = i
    wmi_by_index = {decode.to_int(w.get("InterfaceIndex")): w for w in rows_of(wmi)}

    out, gige = [], []
    physical = connected = 0
    for a in rows_of(adapters):
        name = str(a.get("Name") or a.get("InterfaceDescription") or "")
        idx = decode.to_int(a.get("ifIndex"))
        w = wmi_by_index.get(idx, {})
        ips = ip_by_index.get(idx, {})
        is_physical = bool(w.get("PhysicalAdapter")) or (not a.get("Virtual") and bool(a.get("ConnectorPresent")))
        physical += is_physical
        if str(a.get("Status")) == "Up":
            connected += 1
        identity = {"Description": a.get("InterfaceDescription", ""), "Manufacturer": w.get("Manufacturer", ""),
                    "Adapter Type": w.get("AdapterType", ""), "Physical": yes_no(is_physical), "Virtual": yes_no(a.get("Virtual")),
                    "Hidden": yes_no(a.get("Hidden")), "Interface Index": idx, "Interface GUID": a.get("InterfaceGuid", ""),
                    "PnP Device ID": a.get("PnPDeviceID", ""), "MAC Address": a.get("MacAddress") or w.get("MACAddress", "")}
        link = {"Status": a.get("Status", ""),
                "Connection Status": decode.lookup(decode.NET_CONNECTION_STATUS, w.get("NetConnectionStatus")),
                "Link Speed": a.get("LinkSpeed", ""), "Full Duplex": yes_no(a.get("FullDuplex")),
                "Media Type": a.get("MediaType", ""), "Physical Media": a.get("PhysicalMediaType", ""),
                "MTU": a.get("MtuSize", ""), "Promiscuous Mode": yes_no(a.get("PromiscuousMode")),
                "Connector Present": yes_no(a.get("ConnectorPresent")), "NDIS Version": a.get("NdisVersion", ""),
                "Last Reset": fmt_datetime(w.get("TimeOfLastReset")) if w.get("TimeOfLastReset") else ""}
        for fam in ("IPv4", "IPv6"):
            i = ips.get(fam, {})
            link[f"{fam} Metric"] = i.get("InterfaceMetric", "")
            link[f"{fam} DHCP"] = decode.lookup(DHCP, i.get("Dhcp")) if i else ""
            link[f"{fam} MTU"] = i.get("NlMtu", "")
            link[f"{fam} State"] = decode.lookup(CONNECTION, i.get("ConnectionState")) if i else ""
        driver = {"Driver Description": a.get("DriverDescription", ""), "Driver Version": a.get("DriverVersion", ""),
                  "Driver Date": fmt_date(a.get("DriverDate")) if a.get("DriverDate") else "",
                  "Driver Provider": a.get("DriverProvider", ""), "Driver File": a.get("DriverFileName", "")}
        adv_rows = [{"Property": p.get("DisplayName", ""), "Value": p.get("DisplayValue", ""), "Keyword": p.get("RegistryKeyword", ""),
                     "Raw": ", ".join(str(v) for v in as_list(p.get("RegistryValue")))} for p in adv_by_name.get(name, [])]
        out.append({"name": name, "groups": [{"title": "Adapter", "rows": identity}, {"title": "Link", "rows": link},
                                             {"title": "Driver", "rows": driver}], "advanced": adv_rows})
        if is_physical:
            by_kw = {p.get("RegistryKeyword"): p.get("DisplayValue", "") for p in adv_by_name.get(name, [])}
            row = {"Adapter": name, "Link Speed": a.get("LinkSpeed", "")}
            for kw, label in GIGE_KEYWORDS.items():
                row[label] = by_kw.get(kw, "")
            gige.append(row)
    summary = {"Adapters": len(out), "Physical Adapters": physical, "Connected": connected}
    return {"groups": [{"title": "Summary", "rows": summary}], "adapters": out, "gige": gige}


def collect(ctx):
    return build(ctx.query("adapters", ADAPTERS_SCRIPT), ctx.query("advanced", ADVANCED_SCRIPT, timeout=60),
                 ctx.query("ip_interfaces", IPIF_SCRIPT), ctx.query("wmi", WMI_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups")), sub_heading("Physical adapters: GigE-relevant settings"),
           list_table(GIGE_COLUMNS, data.get("gige"))]
    adapters = rows_of(data.get("adapters"))
    if not adapters:
        out.append(sub_heading("Adapters") + list_table([("Name", "Name")], []))
    for a in adapters:
        out.append(sub_heading(a.get("name", "")) + kv_groups(a.get("groups"))
                   + list_table(ADV_COLUMNS, a.get("advanced")))
    return "".join(out)


SECTION = Section(key="network_adapters", title="Network Adapters", group="Hardware", collect=collect, render=render, timeout=60)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Network Adapters with IP interface, driver and advanced properties`

---

### Task 21: Video, Monitors, Sound

**Files:**
- Create: `pc_report/sections/video.py`, `pc_report/sections/monitors.py`, `pc_report/sections/sound.py`
- Test: `tests/pc_report/test_video.py`, `tests/pc_report/test_monitors.py`, `tests/pc_report/test_sound.py`
- Fixtures: `_shared/dxdiag.json`, `video/{controllers,registry}.json`, `monitors/{wmi_monitors,params,screens}.json`, `sound/{devices,endpoints,drivers}.json`

**Interfaces:** `video.build(controllers, reg, dx) -> {"groups": [summary], "adapters": [{"name", "groups"}]}`; `video.names(data) -> list[str]` for System Summary and Noldus Summary. The dxdiag dict shape is `_etree_to_dict` output: `dx["DisplayDevices"]["DisplayDevice"]` is a dict or list of dicts with string values; `dx["SystemInformation"]["DirectXVersion"]`.

- [ ] **Step 1: Tests**

`tests/pc_report/test_video.py`:

```python
import unittest

from pc_report.sections import video as mod
from tests.pc_report import support

CTRL = [{"Name": "NVIDIA GeForce RTX 3060", "Status": "OK", "AdapterRAM": 4293918720, "AdapterDACType": "Integrated RAMDAC",
         "VideoProcessor": "NVIDIA GeForce RTX 3060", "VideoArchitecture": 5, "PNPDeviceID": "PCI\\VEN_10DE&DEV_2503&SUBSYS_00000001&REV_A1\\4",
         "CurrentHorizontalResolution": 2560, "CurrentVerticalResolution": 1440, "CurrentRefreshRate": 60, "CurrentBitsPerPixel": 32,
         "CurrentNumberOfColors": 4294967296, "DriverVersion": "32.0.15.6094", "DriverDate": "20240801000000.000000-000",
         "InfFilename": "oem12.inf", "InfSection": "Section123", "VideoModeDescription": "2560 x 1440 x 4294967296 colors",
         "Availability": 3, "MaxRefreshRate": 165, "MinRefreshRate": 24, "ConfigManagerErrorCode": 0, "AdapterCompatibility": "NVIDIA"}]
REG = [{"Key": "0000", "DriverDesc": "NVIDIA GeForce RTX 3060", "MatchingDeviceId": "PCI\\VEN_10DE&DEV_2503&SUBSYS_00000001",
        "qwMemorySize": 12884901888, "DriverVersion": "32.0.15.6094", "DriverDate": "8-1-2024", "ProviderName": "NVIDIA"}]
DX = {"SystemInformation": {"DirectXVersion": "DirectX 12"},
      "DisplayDevices": {"DisplayDevice": {"CardName": "NVIDIA GeForce RTX 3060", "Manufacturer": "NVIDIA", "ChipType": "NVIDIA GeForce RTX 3060",
                                           "DACType": "Integrated RAMDAC", "DeviceType": "Full Device (POST)", "DisplayMemory": "20387 MB",
                                           "DedicatedMemory": "12100 MB", "SharedMemory": "8287 MB", "CurrentMode": "2560 x 1440 (32 bit) (60Hz)",
                                           "HDR": "Not Supported", "DriverName": "nvldumdx.dll", "DriverFileVersion": "32.00.0015.6094",
                                           "DriverVersion": "32.0.15.6094", "DDIVersion": "12", "FeatureLevels": "12_1,12_0,11_1,11_0",
                                           "DriverModel": "WDDM 3.1", "DriverDate": "8/1/2024 02:00:00", "VendorID": "0x10DE", "DeviceID": "0x2503",
                                           "SubSysID": "0x00000001", "RevisionID": "0x00A1", "MonitorName": "Generic PnP Monitor",
                                           "MonitorModel": "DELL U2722D", "OutputType": "Displayport External", "NativeMode": "2560 x 1440(p) (59.951Hz)"}}}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(CTRL, REG, DX)
        self.rows = {}
        for g in self.data["adapters"][0]["groups"]:
            self.rows.update(g["rows"])

    def test_memory_is_corrected_from_registry(self):
        self.assertEqual(self.rows["Adapter RAM"], "12.0 GB")
        self.assertEqual(self.rows["Adapter RAM (WMI, 32-bit capped)"], "4.0 GB")
        self.assertEqual(self.rows["Dedicated Memory (DirectX)"], "12100 MB")
        self.assertEqual(self.rows["Shared Memory (DirectX)"], "8287 MB")

    def test_mode_and_driver(self):
        self.assertEqual(self.rows["Current Mode"], "2560 x 1440, 32 bit, 60 Hz")
        self.assertEqual(self.rows["Refresh Rate Range"], "24 - 165 Hz")
        self.assertEqual(self.rows["Driver Model"], "WDDM 3.1")
        self.assertEqual(self.rows["Feature Levels"], "12_1,12_0,11_1,11_0")
        self.assertEqual(self.rows["Driver Date"], "2024-08-01")
        self.assertEqual(self.rows["PCI IDs"], "VEN 10DE / DEV 2503 / SUBSYS 00000001 / REV A1")
        self.assertEqual(self.rows["Architecture"], "VGA")

    def test_summary_and_names(self):
        self.assertEqual(dict(self.data["groups"][0]["rows"])["DirectX Version"], "DirectX 12")
        self.assertEqual(mod.names(self.data), ["NVIDIA GeForce RTX 3060"])


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Adapter RAM</th>", html)
        self.assertIn("<th>DirectX Version</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_monitors.py`:

```python
import unittest

from pc_report.sections import monitors as mod
from tests.pc_report import support

WMI = [{"InstanceName": "DISPLAY\\DELA1C4\\5&1&0&UID4353_0", "Manufacturer": "DEL", "Model": "DELL U2722D", "Serial": "ABC123",
        "ProductCode": "A1C4", "Year": 2022, "Week": 12, "Active": True}]
PARAMS = [{"InstanceName": "DISPLAY\\DELA1C4\\5&1&0&UID4353_0", "MaxHorizontalImageSize": 60, "MaxVerticalImageSize": 34, "Active": True}]
SCREENS = [{"DeviceName": "\\\\.\\DISPLAY1", "Primary": True, "Width": 2560, "Height": 1440, "X": 0, "Y": 0, "BitsPerPixel": 32}]
DX = {"DisplayDevices": {"DisplayDevice": {"CardName": "GPU", "MonitorName": "Generic PnP Monitor", "MonitorModel": "DELL U2722D",
                                           "MonitorId": "DELA1C4", "NativeMode": "2560 x 1440(p) (59.951Hz)", "OutputType": "Displayport External",
                                           "CurrentMode": "2560 x 1440 (32 bit) (60Hz)"}}}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(WMI, PARAMS, SCREENS, DX)
        m = data["monitors"][0]
        self.assertEqual(m["Manufacturer"], "Dell")
        self.assertEqual(m["Model"], "DELL U2722D")
        self.assertEqual(m["Manufactured"], "2022, week 12")
        self.assertEqual(m["Diagonal"], '27.1" (60 x 34 cm)')
        self.assertEqual(m["Native Mode"], "2560 x 1440(p) (59.951Hz)")
        self.assertEqual(m["Output"], "Displayport External")
        self.assertEqual(data["screens"][0]["Resolution"], "2560 x 1440")
        self.assertEqual(data["screens"][0]["Primary"], "Yes")

    def test_pnp_vendor(self):
        self.assertEqual(mod.pnp_vendor("SAM"), "Samsung")
        self.assertEqual(mod.pnp_vendor("XYZ"), "XYZ")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Diagonal</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_sound.py`:

```python
import unittest

from pc_report.sections import sound as mod
from tests.pc_report import support

DEV = [{"Name": "Realtek(R) Audio", "Manufacturer": "Realtek", "Status": "OK", "StatusInfo": 3, "PNPDeviceID": "HDAUDIO\\FUNC_01&VEN_10EC\\1", "ConfigManagerErrorCode": 0}]
ENDPOINTS = [{"FriendlyName": "Speakers (Realtek(R) Audio)", "Status": "OK", "InstanceId": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{aaaa}", "Present": True},
             {"FriendlyName": "Microphone (USB Camera)", "Status": "OK", "InstanceId": "SWD\\MMDEVAPI\\{0.0.1.00000000}.{bbbb}", "Present": True}]
DRIVERS = [{"DeviceName": "Realtek(R) Audio", "DriverVersion": "6.0.9.1", "DriverDate": "20230301000000.000000-000", "DriverProviderName": "Realtek"}]
DX = {"SoundDevices": {"SoundDevice": {"Description": "Speakers (Realtek(R) Audio)", "DefaultSoundPlayback": "True", "DefaultVoicePlayback": "True",
                                       "HardwareID": "HDAUDIO\\FUNC_01&VEN_10EC", "DriverName": "RTKVHD64.sys", "DriverVersion": "6.0.9.1", "DriverProvider": "Realtek"}},
      "SoundCaptureDevices": {"SoundCaptureDevice": {"Description": "Microphone (USB Camera)", "DefaultSoundRecording": "True", "DriverName": "usbaudio.sys", "DriverVersion": "10.0.1"}}}


class BuildTests(unittest.TestCase):
    def test_devices_endpoints_defaults(self):
        data = mod.build(DEV, ENDPOINTS, DRIVERS, DX)
        d = data["devices"][0]
        self.assertEqual(d["Driver Version"], "6.0.9.1")
        self.assertEqual(d["Driver Date"], "2023-03-01")
        self.assertEqual(data["endpoints"][0]["Direction"], "Playback")
        self.assertEqual(data["endpoints"][1]["Direction"], "Capture")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Default Playback"], "Speakers (Realtek(R) Audio)")
        self.assertEqual(rows["Default Capture"], "Microphone (USB Camera)")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Direction</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/video.py`:

```python
"""Video: every adapter with corrected memory (registry qwMemorySize), mode, driver and DirectX detail."""
from __future__ import annotations

import re

from .. import decode
from ..format import bytes_human, fmt_date
from ..ps import cim, dx_list
from ..section import Section, kv_groups, rows_of, sub_heading

CTRL_PROPS = ("Name", "Status", "AdapterRAM", "AdapterDACType", "VideoProcessor", "VideoArchitecture", "PNPDeviceID",
              "CurrentHorizontalResolution", "CurrentVerticalResolution", "CurrentRefreshRate", "CurrentBitsPerPixel",
              "CurrentNumberOfColors", "DriverVersion", "DriverDate", "InfFilename", "InfSection", "VideoModeDescription",
              "Availability", "MaxRefreshRate", "MinRefreshRate", "ConfigManagerErrorCode", "AdapterCompatibility")
CTRL_SCRIPT = cim("Win32_VideoController", CTRL_PROPS)
REG_SCRIPT = r"""
$root = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
Get-ChildItem $root -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\d{4}$' } | ForEach-Object {
  $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
  if ($x.DriverDesc) {
    [pscustomobject]@{ Key = $_.PSChildName; DriverDesc = [string]$x.DriverDesc; MatchingDeviceId = [string]$x.MatchingDeviceId
                       qwMemorySize = $x.'HardwareInformation.qwMemorySize'; DriverVersion = [string]$x.DriverVersion
                       DriverDate = [string]$x.DriverDate; ProviderName = [string]$x.ProviderName }
  }
}
"""
_IDS = re.compile(r"VEN_([0-9A-Fa-f]{4})&DEV_([0-9A-Fa-f]{4})(?:&SUBSYS_([0-9A-Fa-f]{8}))?(?:&REV_([0-9A-Fa-f]{2}))?")


def _pci_ids(pnp_id: str) -> str:
    m = _IDS.search(str(pnp_id or ""))
    if not m:
        return ""
    ven, dev, sub, rev = m.groups()
    parts = [f"VEN {ven.upper()}", f"DEV {dev.upper()}"]
    if sub:
        parts.append(f"SUBSYS {sub.upper()}")
    if rev:
        parts.append(f"REV {rev.upper()}")
    return " / ".join(parts)


def _match_reg(ctrl: dict, regs: list[dict]) -> dict:
    pnp = str(ctrl.get("PNPDeviceID") or "").upper()
    for r in regs:
        mid = str(r.get("MatchingDeviceId") or "").upper()
        if mid and pnp.startswith(mid):
            return r
    for r in regs:
        if str(r.get("DriverDesc") or "").lower() == str(ctrl.get("Name") or "").lower():
            return r
    return {}


def _match_dx(ctrl: dict, dxs: list[dict]) -> dict:
    name = str(ctrl.get("Name") or "").lower()
    for d in dxs:
        if str(d.get("CardName") or "").lower() == name:
            return d
    return {}


def build(controllers, reg, dx) -> dict:
    regs = rows_of(reg)
    dxs = dx_list(dx, "DisplayDevices", "DisplayDevice")
    adapters = []
    for c in rows_of(controllers):
        r = _match_reg(c, regs)
        d = _match_dx(c, dxs)
        wmi_ram = decode.to_int(c.get("AdapterRAM"))
        reg_ram = decode.to_int(r.get("qwMemorySize"))
        h, v = c.get("CurrentHorizontalResolution"), c.get("CurrentVerticalResolution")
        mode = ""
        if h and v:
            mode = f"{h} x {v}"
            if c.get("CurrentBitsPerPixel"):
                mode += f", {c['CurrentBitsPerPixel']} bit"
            if c.get("CurrentRefreshRate"):
                mode += f", {c['CurrentRefreshRate']} Hz"
        lo, hi = c.get("MinRefreshRate"), c.get("MaxRefreshRate")
        adapter = {
            "Name": c.get("Name", ""), "Status": c.get("Status", ""),
            "Availability": decode.lookup(decode.AVAILABILITY, c.get("Availability")),
            "Problem": decode.lookup(decode.PNP_ERROR_CODES, c.get("ConfigManagerErrorCode")) if decode.to_int(c.get("ConfigManagerErrorCode")) else "",
            "Chip Type": d.get("ChipType") or c.get("VideoProcessor", ""), "Video Processor": c.get("VideoProcessor", ""),
            "DAC Type": c.get("AdapterDACType") or d.get("DACType", ""), "Manufacturer": d.get("Manufacturer") or c.get("AdapterCompatibility", ""),
            "Device Type": d.get("DeviceType", ""), "Architecture": decode.lookup(decode.VIDEO_ARCHITECTURE, c.get("VideoArchitecture")),
            "PCI IDs": _pci_ids(c.get("PNPDeviceID")), "PnP Device ID": c.get("PNPDeviceID", ""),
        }
        memory = {
            "Adapter RAM": bytes_human(reg_ram) if reg_ram else (bytes_human(wmi_ram) if wmi_ram else ""),
            "Adapter RAM (WMI, 32-bit capped)": bytes_human(wmi_ram) if wmi_ram else "",
            "Display Memory (DirectX)": d.get("DisplayMemory", ""), "Dedicated Memory (DirectX)": d.get("DedicatedMemory", ""),
            "Shared Memory (DirectX)": d.get("SharedMemory", ""),
        }
        display = {
            "Current Mode": mode, "Video Mode": c.get("VideoModeDescription", ""),
            "Refresh Rate Range": f"{lo} - {hi} Hz" if lo and hi else "", "HDR": d.get("HDR", ""),
            "Attached Monitor": d.get("MonitorModel") or d.get("MonitorName", ""), "Output Type": d.get("OutputType", ""),
            "Native Mode": d.get("NativeMode", ""),
        }
        driver = {
            "Driver Version": c.get("DriverVersion") or r.get("DriverVersion", ""),
            "Driver Date": fmt_date(c.get("DriverDate")) if c.get("DriverDate") else r.get("DriverDate", ""),
            "Driver Provider": r.get("ProviderName", ""), "Driver Model": d.get("DriverModel", ""),
            "Driver File": d.get("DriverName", ""), "Driver File Version": d.get("DriverFileVersion", ""),
            "DDI Version": d.get("DDIVersion", ""), "Feature Levels": d.get("FeatureLevels", ""),
            "INF": f"{c.get('InfFilename', '')} [{c.get('InfSection', '')}]" if c.get("InfFilename") else "",
        }
        adapters.append({"name": c.get("Name", ""), "groups": [
            {"title": "Adapter", "rows": adapter}, {"title": "Memory", "rows": memory},
            {"title": "Display", "rows": display}, {"title": "Driver", "rows": driver}]})
    sysinfo = dx.get("SystemInformation", {}) if isinstance(dx, dict) else {}
    summary = {"Adapters": len(adapters), "DirectX Version": sysinfo.get("DirectXVersion", "") if isinstance(sysinfo, dict) else "",
               "Memory Note": "Adapter RAM comes from the driver registry key; WMI caps at 4 GB." if any(
                   decode.to_int(r.get("qwMemorySize")) for r in regs) else ""}
    return {"groups": [{"title": "Summary", "rows": summary}], "adapters": adapters}


def names(data) -> list[str]:
    return [a.get("name", "") for a in rows_of((data or {}).get("adapters")) if a.get("name")] if isinstance(data, dict) else []


def collect(ctx):
    return build(ctx.query("controllers", CTRL_SCRIPT), ctx.query("registry", REG_SCRIPT), ctx.shared("dxdiag"))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    for a in rows_of(data.get("adapters")):
        out.append(sub_heading(a.get("name", "")) + kv_groups(a.get("groups")))
    return "".join(out)


SECTION = Section(key="video", title="Video", group="Hardware", collect=collect, render=render, timeout=120)
```

`pc_report/sections/monitors.py`:

```python
"""Monitors: EDID identity from WMI, physical size, native/current mode from dxdiag, desktop layout from Screen.AllScreens."""
from __future__ import annotations

import math

from ..format import yes_no
from ..ps import cim, dx_list
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

WMI_SCRIPT = r"""
Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID -ErrorAction SilentlyContinue | ForEach-Object {
  function txt($a) { if ($a) { -join ($a | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) } else { '' } }
  [pscustomobject]@{ InstanceName = $_.InstanceName; Manufacturer = (txt $_.ManufacturerName); Model = (txt $_.UserFriendlyName)
                     Serial = (txt $_.SerialNumberID); ProductCode = (txt $_.ProductCodeID); Year = $_.YearOfManufacture
                     Week = $_.WeekOfManufacture; Active = $_.Active }
}
"""
PARAMS_SCRIPT = cim("WmiMonitorBasicDisplayParams", ("InstanceName", "MaxHorizontalImageSize", "MaxVerticalImageSize", "Active"),
                    namespace="root/wmi")
SCREENS_SCRIPT = ("Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { "
                  "[pscustomobject]@{ DeviceName = $_.DeviceName; Primary = $_.Primary; Width = $_.Bounds.Width; Height = $_.Bounds.Height; "
                  "X = $_.Bounds.X; Y = $_.Bounds.Y; BitsPerPixel = $_.BitsPerPixel } }")

PNP_VENDORS = {"DEL": "Dell", "SAM": "Samsung", "LGD": "LG Display", "GSM": "LG", "AUO": "AU Optronics", "BOE": "BOE",
               "ACR": "Acer", "AOC": "AOC", "BNQ": "BenQ", "HWP": "HP", "HPN": "HP", "LEN": "Lenovo", "PHL": "Philips",
               "VSC": "ViewSonic", "IVM": "Iiyama", "SNY": "Sony", "NEC": "NEC", "MSI": "MSI", "ASU": "ASUS", "AUS": "ASUS",
               "EIZ": "Eizo", "ENC": "Eizo", "CMN": "Chi Mei", "SHP": "Sharp", "APP": "Apple", "MEI": "Panasonic"}

MON_COLUMNS = [("Manufacturer", "Manufacturer"), ("Model", "Model"), ("Product Code", "Product Code"), ("Serial Number", "Serial Number"),
               ("Manufactured", "Manufactured"), ("Diagonal", "Diagonal"), ("Native Mode", "Native Mode"), ("Current Mode", "Current Mode"),
               ("Output", "Output"), ("Attached To", "Attached To"), ("Active", "Active")]
SCREEN_COLUMNS = [("Device", "Device"), ("Resolution", "Resolution"), ("Position", "Position"), ("Bits Per Pixel", "Bits Per Pixel"), ("Primary", "Primary")]


def pnp_vendor(code: str) -> str:
    return PNP_VENDORS.get(str(code or "").upper(), str(code or ""))


def _diagonal(h_cm, v_cm) -> str:
    try:
        h, v = float(h_cm), float(v_cm)
    except (TypeError, ValueError):
        return ""
    if h <= 0 or v <= 0:
        return ""
    return f'{math.hypot(h, v) / 2.54:.1f}" ({int(h)} x {int(v)} cm)'


def build(wmi, params, screens, dx) -> dict:
    params_by = {str(p.get("InstanceName") or ""): p for p in rows_of(params)}
    dxs = dx_list(dx, "DisplayDevices", "DisplayDevice")
    monitors = []
    for m in rows_of(wmi):
        inst = str(m.get("InstanceName") or "")
        p = params_by.get(inst, {})
        pnp_id = inst.split("\\")[1] if "\\" in inst else ""
        d = next((x for x in dxs if str(x.get("MonitorId") or "").upper() == pnp_id.upper()), {})
        monitors.append({
            "Manufacturer": pnp_vendor(m.get("Manufacturer")), "Model": m.get("Model") or d.get("MonitorModel", ""),
            "Product Code": m.get("ProductCode", ""), "Serial Number": m.get("Serial", ""),
            "Manufactured": f"{m.get('Year')}, week {m.get('Week')}" if m.get("Year") else "",
            "Diagonal": _diagonal(p.get("MaxHorizontalImageSize"), p.get("MaxVerticalImageSize")),
            "Native Mode": d.get("NativeMode", ""), "Current Mode": d.get("CurrentMode", ""), "Output": d.get("OutputType", ""),
            "Attached To": d.get("CardName", ""), "Active": yes_no(m.get("Active")),
        })
    screen_rows = [{"Device": s.get("DeviceName", ""), "Resolution": f"{s.get('Width')} x {s.get('Height')}",
                    "Position": f"{s.get('X')}, {s.get('Y')}", "Bits Per Pixel": s.get("BitsPerPixel", ""),
                    "Primary": yes_no(s.get("Primary"))} for s in rows_of(screens)]
    summary = {"Monitors": len(monitors), "Active Monitors": sum(1 for m in monitors if m["Active"] == "Yes"),
               "Desktop Screens": len(screen_rows)}
    return {"groups": [{"title": "Summary", "rows": summary}], "monitors": monitors, "screens": screen_rows}


def collect(ctx):
    return build(ctx.query("wmi_monitors", WMI_SCRIPT), ctx.query("params", PARAMS_SCRIPT),
                 ctx.query("screens", SCREENS_SCRIPT, timeout=30), ctx.shared("dxdiag"))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Monitors") + list_table(MON_COLUMNS, data.get("monitors"))
            + sub_heading("Desktop layout") + list_table(SCREEN_COLUMNS, data.get("screens")))


SECTION = Section(key="monitors", title="Monitors", group="Hardware", collect=collect, render=render, timeout=120)
```

`pc_report/sections/sound.py`:

```python
"""Sound: devices with driver detail, render/capture endpoints, and DirectX default devices."""
from __future__ import annotations

from ..format import fmt_date, yes_no
from ..ps import cim, dx_list
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

DEV_SCRIPT = cim("Win32_SoundDevice", ("Name", "Manufacturer", "Status", "StatusInfo", "PNPDeviceID", "ConfigManagerErrorCode"))
ENDPOINTS_SCRIPT = "Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | Select-Object FriendlyName,Status,InstanceId,Present"
DRIVERS_SCRIPT = cim("Win32_PnPSignedDriver", ("DeviceName", "DriverVersion", "DriverDate", "DriverProviderName"),
                     where="DeviceClass='MEDIA'")

DEV_COLUMNS = [("Name", "Name"), ("Manufacturer", "Manufacturer"), ("Status", "Status"), ("Driver Version", "Driver Version"),
               ("Driver Date", "Driver Date"), ("Driver Provider", "Driver Provider"), ("PnP Device ID", "PnP Device ID")]
EP_COLUMNS = [("Name", "Name"), ("Direction", "Direction"), ("Status", "Status"), ("Present", "Present"), ("Instance", "Instance")]


def _direction(instance_id: str) -> str:
    inst = str(instance_id or "")
    if "{0.0.0." in inst:
        return "Playback"
    if "{0.0.1." in inst:
        return "Capture"
    return ""


def build(devices, endpoints, drivers, dx) -> dict:
    drv_by_name = {str(d.get("DeviceName") or "").lower(): d for d in rows_of(drivers)}
    dev_rows = []
    for d in rows_of(devices):
        drv = drv_by_name.get(str(d.get("Name") or "").lower(), {})
        dev_rows.append({"Name": d.get("Name", ""), "Manufacturer": d.get("Manufacturer", ""), "Status": d.get("Status", ""),
                         "Driver Version": drv.get("DriverVersion", ""),
                         "Driver Date": fmt_date(drv.get("DriverDate")) if drv.get("DriverDate") else "",
                         "Driver Provider": drv.get("DriverProviderName", ""), "PnP Device ID": d.get("PNPDeviceID", "")})
    ep_rows = [{"Name": e.get("FriendlyName", ""), "Direction": _direction(e.get("InstanceId")), "Status": e.get("Status", ""),
                "Present": yes_no(e.get("Present")), "Instance": e.get("InstanceId", "")} for e in rows_of(endpoints)]
    ep_rows.sort(key=lambda r: (r["Direction"] != "Playback", str(r["Name"]).lower()))
    playback = next((d.get("Description", "") for d in dx_list(dx, "SoundDevices", "SoundDevice")
                     if str(d.get("DefaultSoundPlayback")).lower() == "true"), "")
    capture = next((d.get("Description", "") for d in dx_list(dx, "SoundCaptureDevices", "SoundCaptureDevice")
                    if str(d.get("DefaultSoundRecording")).lower() == "true"), "")
    summary = {"Sound Devices": len(dev_rows), "Playback Endpoints": sum(1 for r in ep_rows if r["Direction"] == "Playback"),
               "Capture Endpoints": sum(1 for r in ep_rows if r["Direction"] == "Capture"),
               "Default Playback": playback, "Default Capture": capture}
    return {"groups": [{"title": "Summary", "rows": summary}], "devices": dev_rows, "endpoints": ep_rows}


def collect(ctx):
    return build(ctx.query("devices", DEV_SCRIPT), ctx.query("endpoints", ENDPOINTS_SCRIPT),
                 ctx.query("drivers", DRIVERS_SCRIPT, timeout=60), ctx.shared("dxdiag"))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Devices") + list_table(DEV_COLUMNS, data.get("devices"))
            + sub_heading("Endpoints") + list_table(EP_COLUMNS, data.get("endpoints")))


SECTION = Section(key="sound", title="Sound", group="Hardware", collect=collect, render=render, timeout=120)
```

- [ ] **Step 3: Standard steps 3–5**

The first capture of any of these three writes `_shared/dxdiag.json` (dxdiag takes 30–90 s). The `SystemInformation` block of dxdiag contains `MachineName`, `UserDNSDomain` and `MachineId`; the capture script's scrub replaces the host name, but delete `MachineId` and `UserDNSDomain` by hand before committing.

Commit message: `feat(pc_report): Video with corrected memory and DirectX detail; Monitors from EDID; Sound endpoints`

---

### Task 22: Storage Devices and Logical Disks

**Files:**
- Create: `pc_report/sections/storage_devices.py`, `pc_report/sections/logical_disks.py`
- Test: `tests/pc_report/test_storage_devices.py`, `tests/pc_report/test_logical_disks.py`
- Fixtures: `storage_devices/{physical,disks,partitions,smart,optical}.json` (+ `reliability.json` when elevated), `logical_disks/{logical,volumes,partitions}.json` (+ `bitlocker.json` when elevated)

**Interfaces:** `logical_disks.build(...) -> {"groups": [summary], "rows": [...]}` with per-row `Drive, Label, Type, File System, Total, Used, Free, Free %, ...`. System Summary reads `rows`.

- [ ] **Step 1: Tests**

`tests/pc_report/test_storage_devices.py`:

```python
import unittest

from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import storage_devices as mod
from tests.pc_report import support

PHYS = [{"DeviceId": "0", "FriendlyName": "Samsung SSD 980 PRO 1TB", "Model": "Samsung SSD 980 PRO 1TB", "Manufacturer": "", "SerialNumber": "S5GX",
         "MediaType": "SSD", "BusType": "NVMe", "Size": 1000204886016, "HealthStatus": "Healthy", "OperationalStatus": "OK",
         "FirmwareVersion": "5B2QGXA7", "SpindleSpeed": 0, "PhysicalSectorSize": 512, "LogicalSectorSize": 512, "Usage": "Auto-Select", "UniqueId": "eui.1"}]
DISKS = [{"Number": 0, "FriendlyName": "Samsung SSD 980 PRO 1TB", "SerialNumber": "S5GX", "PartitionStyle": "GPT", "IsBoot": True, "IsSystem": True,
          "IsReadOnly": False, "IsOffline": False, "NumberOfPartitions": 4, "Size": 1000204886016, "AllocatedSize": 1000204886016,
          "Location": "PCI Slot 4 : Bus 3 : Device 0 : Function 0 : Adapter 0 : Port 0", "Guid": "{g}", "OperationalStatus": "Online"}]
PARTS = [{"DiskNumber": 0, "PartitionNumber": 3, "DriveLetter": "C", "Size": 998000000000, "Type": "Basic", "GptType": "{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}",
          "IsActive": False, "IsBoot": True, "IsSystem": False, "IsHidden": False, "Offset": 123},
         {"DiskNumber": 0, "PartitionNumber": 1, "DriveLetter": None, "Size": 104857600, "Type": "System", "GptType": "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}",
          "IsActive": False, "IsBoot": False, "IsSystem": True, "IsHidden": False, "Offset": 1}]
SMART = [{"InstanceName": "SCSI\\Disk&Ven_NVMe&Prod_Samsung_SSD_980\\5&1_0", "PredictFailure": False, "Reason": 0}]
REL = [{"DeviceId": "0", "Temperature": 41, "TemperatureMax": 62, "PowerOnHours": 5121, "Wear": 2, "ReadErrorsTotal": 0, "WriteErrorsTotal": 0,
        "ReadErrorsUncorrected": 0, "WriteErrorsUncorrected": 0, "StartStopCycleCount": 300}]
OPT = [{"Name": "HL-DT-ST DVDRAM", "Drive": "E:", "MediaType": "DVD Writer", "Manufacturer": "(Standard CD-ROM drives)", "Status": "OK", "MediaLoaded": False}]


class BuildTests(unittest.TestCase):
    def test_disk_rows(self):
        data = mod.build(PHYS, DISKS, PARTS, SMART, REL, OPT)
        d = data["disks"][0]
        rows = {}
        for g in d["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["Size"], "931.5 GB")
        self.assertEqual(rows["Media Type"], "SSD")
        self.assertEqual(rows["Bus Type"], "NVMe")
        self.assertEqual(rows["Partition Style"], "GPT")
        self.assertEqual(rows["Boot / System Disk"], "Yes / Yes")
        self.assertEqual(rows["Sector Size (logical / physical)"], "512 / 512")
        self.assertEqual(rows["SMART Predict Failure"], "No")
        self.assertEqual(rows["Temperature"], "41 °C (max 62 °C)")
        self.assertEqual(rows["Power-on Hours"], "5121 h (213 days)")
        self.assertEqual(rows["Wear"], "2 %")
        parts = d["partitions"]
        self.assertEqual(parts[0]["Partition"], 1)
        self.assertEqual(parts[0]["GPT Type"], "EFI System")
        self.assertEqual(parts[1]["Drive"], "C:")
        self.assertEqual(parts[1]["GPT Type"], "Basic Data")

    def test_requires_admin_reliability(self):
        data = mod.build(PHYS, DISKS, PARTS, SMART, REQUIRES_ADMIN, OPT)
        rows = {}
        for g in data["disks"][0]["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["Reliability Counters"], REQUIRES_ADMIN)

    def test_optical(self):
        data = mod.build([], [], [], [], [], OPT)
        self.assertEqual(data["optical"][0]["Drive"], "E:")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Bus Type</th>", html)
        self.assertIn("<h3>Optical drives</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_logical_disks.py`:

```python
import unittest

from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import logical_disks as mod
from tests.pc_report import support

LD = [{"DeviceID": "C:", "VolumeName": "Windows", "DriveType": 3, "FileSystem": "NTFS", "Size": 998000000000, "FreeSpace": 49000000000,
       "VolumeSerialNumber": "1A2B3C4D", "Compressed": False, "ProviderName": None, "Description": "Local Fixed Disk", "MediaType": 12},
      {"DeviceID": "Z:", "VolumeName": "share", "DriveType": 4, "FileSystem": "NTFS", "Size": 2000000000000, "FreeSpace": 1000000000000,
       "VolumeSerialNumber": "0000", "Compressed": False, "ProviderName": "\\\\server\\share", "Description": "Network Connection", "MediaType": 0}]
VOL = [{"DriveLetter": "C", "FileSystemLabel": "Windows", "FileSystem": "NTFS", "HealthStatus": "Healthy", "OperationalStatus": "OK",
        "AllocationUnitSize": 4096, "Size": 998000000000, "SizeRemaining": 49000000000, "DriveType": "Fixed"}]
PARTS = [{"DriveLetter": "C", "DiskNumber": 0, "PartitionNumber": 3, "BusType": "NVMe", "DiskModel": "Samsung SSD 980 PRO 1TB"}]
BL = [{"MountPoint": "C:", "ProtectionStatus": 1, "VolumeStatus": 1, "EncryptionPercentage": 100}]


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(LD, VOL, PARTS, BL)
        c = data["rows"][0]
        self.assertEqual(c["Drive"], "C:")
        self.assertEqual(c["Type"], "Local disk")
        self.assertEqual(c["Total"], "929.5 GB")
        self.assertEqual(c["Free %"], "⚠ 4.9 %")
        self.assertEqual(c["Allocation Unit"], "4096 B")
        self.assertEqual(c["Bus Type"], "NVMe")
        self.assertEqual(c["Disk"], "0 (Samsung SSD 980 PRO 1TB)")
        self.assertEqual(c["BitLocker"], "On")
        z = data["rows"][1]
        self.assertEqual(z["Type"], "Network drive")
        self.assertEqual(z["Network Path (host name)"], "\\\\server\\share")
        self.assertEqual(z["Free %"], "50.0 %")

    def test_requires_admin_bitlocker(self):
        data = mod.build(LD, VOL, PARTS, REQUIRES_ADMIN)
        self.assertEqual(data["rows"][0]["BitLocker"], REQUIRES_ADMIN)

    def test_summary(self):
        rows = dict(mod.build(LD, VOL, PARTS, BL)["groups"][0]["rows"])
        self.assertEqual(rows["Volumes"], 2)
        self.assertEqual(rows["Low Space (<10 %)"], "C:")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Free %</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/storage_devices.py`:

```python
"""Storage Devices: physical disks with partitions, SMART status, reliability counters (admin) and optical drives."""
from __future__ import annotations

from .. import decode
from ..format import bytes_human, yes_no
from ..ps import cim
from ..section import REQUIRES_ADMIN, Section, kv_groups, list_table, rows_of, sub_heading

PHYS_SCRIPT = ("Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object DeviceId,FriendlyName,Model,Manufacturer,SerialNumber,"
               "MediaType,BusType,Size,HealthStatus,OperationalStatus,FirmwareVersion,SpindleSpeed,PhysicalSectorSize,"
               "LogicalSectorSize,Usage,UniqueId")
DISKS_SCRIPT = ("Get-Disk -ErrorAction SilentlyContinue | Select-Object Number,FriendlyName,SerialNumber,PartitionStyle,IsBoot,IsSystem,"
                "IsReadOnly,IsOffline,NumberOfPartitions,Size,AllocatedSize,Location,Guid,OperationalStatus")
PARTS_SCRIPT = ("Get-Partition -ErrorAction SilentlyContinue | Select-Object DiskNumber,PartitionNumber,DriveLetter,Size,Type,GptType,"
                "IsActive,IsBoot,IsSystem,IsHidden,Offset")
SMART_SCRIPT = cim("MSStorageDriver_FailurePredictStatus", ("InstanceName", "PredictFailure", "Reason"), namespace="root/wmi")
RELIABILITY_SCRIPT = ("Get-PhysicalDisk -ErrorAction SilentlyContinue | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | "
                      "Select-Object DeviceId,Temperature,TemperatureMax,PowerOnHours,Wear,ReadErrorsTotal,WriteErrorsTotal,"
                      "ReadErrorsUncorrected,WriteErrorsUncorrected,StartStopCycleCount")
OPTICAL_SCRIPT = cim("Win32_CDROMDrive", ("Name", "Drive", "MediaType", "Manufacturer", "Status", "MediaLoaded"))

GPT_TYPES = {"{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}": "EFI System", "{e3c9e316-0b5c-4db8-817d-f92df00215ae}": "Microsoft Reserved",
             "{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}": "Basic Data", "{de94bba4-06d1-4d40-a16a-bfd50179d6ac}": "Windows Recovery",
             "{5808c8aa-7e8f-42e0-85d2-e1e90434cfb3}": "LDM Metadata", "{af9b60a0-1431-4f62-bc68-3311714a69ad}": "LDM Data",
             "{0fc63daf-8483-4772-8e79-3d69d8477de4}": "Linux Filesystem", "{0657fd6d-a4ab-43c4-84e5-0933c84b4f4f}": "Linux Swap"}
PART_COLUMNS = [("Partition", "Partition"), ("Drive", "Drive"), ("Size", "Size"), ("Type", "Type"), ("GPT Type", "GPT Type"),
                ("Boot", "Boot"), ("System", "System"), ("Active", "Active"), ("Hidden", "Hidden"), ("Offset", "Offset")]
OPT_COLUMNS = [("Name", "Name"), ("Drive", "Drive"), ("Media Type", "Media Type"), ("Manufacturer", "Manufacturer"),
               ("Status", "Status"), ("Media Loaded", "Media Loaded")]


def _hours(h):
    n = decode.to_int(h)
    return f"{n} h ({n // 24} days)" if n is not None else ""


def build(physical, disks, partitions, smart, reliability, optical) -> dict:
    disks_by_no = {decode.to_int(d.get("Number")): d for d in rows_of(disks)}
    parts_by_no: dict[int, list] = {}
    for p in rows_of(partitions):
        parts_by_no.setdefault(decode.to_int(p.get("DiskNumber")), []).append(p)
    smart_rows = rows_of(smart)
    rel_by_id = {} if reliability == REQUIRES_ADMIN else {str(r.get("DeviceId")): r for r in rows_of(reliability)}

    out = []
    for ph in rows_of(physical):
        no = decode.to_int(ph.get("DeviceId"))
        d = disks_by_no.get(no, {})
        model_token = str(ph.get("Model") or ph.get("FriendlyName") or "").split(" ")[0].lower()
        sm = next((s for s in smart_rows if model_token and model_token in str(s.get("InstanceName", "")).lower()), None)
        identity = {"Model": ph.get("Model") or ph.get("FriendlyName", ""), "Friendly Name": ph.get("FriendlyName", ""),
                    "Manufacturer": ph.get("Manufacturer", ""), "Serial Number": ph.get("SerialNumber") or d.get("SerialNumber", ""),
                    "Firmware": ph.get("FirmwareVersion", ""), "Unique ID": ph.get("UniqueId", ""), "Location": d.get("Location", "")}
        geometry = {"Size": bytes_human(ph.get("Size")) if ph.get("Size") else "", "Media Type": ph.get("MediaType", ""),
                    "Bus Type": ph.get("BusType", ""),
                    "Spindle Speed": f"{ph.get('SpindleSpeed')} RPM" if decode.to_int(ph.get("SpindleSpeed")) else ("N/A (solid state)" if ph.get("MediaType") == "SSD" else ""),
                    "Sector Size (logical / physical)": f"{ph.get('LogicalSectorSize', '')} / {ph.get('PhysicalSectorSize', '')}",
                    "Partition Style": d.get("PartitionStyle", ""), "Partitions": d.get("NumberOfPartitions", ""),
                    "Boot / System Disk": f"{yes_no(d.get('IsBoot'))} / {yes_no(d.get('IsSystem'))}" if d else "",
                    "Read Only": yes_no(d.get("IsReadOnly")), "Offline": yes_no(d.get("IsOffline")), "Usage": ph.get("Usage", "")}
        health = {"Health": ph.get("HealthStatus", ""), "Operational Status": str(ph.get("OperationalStatus") or ""),
                  "SMART Predict Failure": yes_no(sm.get("PredictFailure")) if sm else "Not reported"}
        if reliability == REQUIRES_ADMIN:
            health["Reliability Counters"] = REQUIRES_ADMIN
        else:
            r = rel_by_id.get(str(ph.get("DeviceId")), {})
            t, tmax = decode.to_int(r.get("Temperature")), decode.to_int(r.get("TemperatureMax"))
            health.update({
                "Temperature": (f"{t} °C" + (f" (max {tmax} °C)" if tmax else "")) if t else "",
                "Power-on Hours": _hours(r.get("PowerOnHours")),
                "Wear": f"{r.get('Wear')} %" if r.get("Wear") is not None else "",
                "Start/Stop Cycles": r.get("StartStopCycleCount", ""),
                "Read Errors (total / uncorrected)": f"{r.get('ReadErrorsTotal', '')} / {r.get('ReadErrorsUncorrected', '')}" if r else "",
                "Write Errors (total / uncorrected)": f"{r.get('WriteErrorsTotal', '')} / {r.get('WriteErrorsUncorrected', '')}" if r else "",
            })
        parts = sorted(parts_by_no.get(no, []), key=lambda p: decode.to_int(p.get("PartitionNumber")) or 0)
        part_rows = [{"Partition": p.get("PartitionNumber"), "Drive": f"{p['DriveLetter']}:" if p.get("DriveLetter") else "",
                      "Size": bytes_human(p.get("Size")) if p.get("Size") else "", "Type": p.get("Type", ""),
                      "GPT Type": GPT_TYPES.get(str(p.get("GptType") or "").lower(), p.get("GptType") or ""),
                      "Boot": yes_no(p.get("IsBoot")), "System": yes_no(p.get("IsSystem")), "Active": yes_no(p.get("IsActive")),
                      "Hidden": yes_no(p.get("IsHidden")), "Offset": p.get("Offset", "")} for p in parts]
        out.append({"name": identity["Model"], "groups": [{"title": "Identity", "rows": identity}, {"title": "Geometry", "rows": geometry},
                                                          {"title": "Health", "rows": health}], "partitions": part_rows})
    optical_rows = [{"Name": o.get("Name", ""), "Drive": o.get("Drive", ""), "Media Type": o.get("MediaType", ""),
                     "Manufacturer": o.get("Manufacturer", ""), "Status": o.get("Status", ""), "Media Loaded": yes_no(o.get("MediaLoaded"))}
                    for o in rows_of(optical)]
    summary = {"Physical Disks": len(out),
               "Total Capacity": bytes_human(sum(decode.to_int(p.get("Size")) or 0 for p in rows_of(physical))) if rows_of(physical) else "",
               "Unhealthy": ", ".join(d["name"] for d in out if any(g["rows"].get("Health") not in ("Healthy", "", None) for g in d["groups"])) or "None",
               "Optical Drives": len(optical_rows)}
    return {"groups": [{"title": "Summary", "rows": summary}], "disks": out, "optical": optical_rows}


def collect(ctx):
    return build(ctx.query("physical", PHYS_SCRIPT, timeout=45), ctx.query("disks", DISKS_SCRIPT, timeout=45),
                 ctx.query("partitions", PARTS_SCRIPT, timeout=45), ctx.query("smart", SMART_SCRIPT),
                 ctx.admin_query("reliability", RELIABILITY_SCRIPT, timeout=45), ctx.query("optical", OPTICAL_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    for d in rows_of(data.get("disks")):
        out.append(sub_heading(d.get("name", "")) + kv_groups(d.get("groups")) + list_table(PART_COLUMNS, d.get("partitions")))
    out.append(sub_heading("Optical drives") + list_table(OPT_COLUMNS, data.get("optical")))
    return "".join(out)


SECTION = Section(key="storage_devices", title="Storage Devices", group="Hardware", collect=collect, render=render, timeout=45)
```

`pc_report/sections/logical_disks.py`:

```python
"""Logical Disks: every volume with usage, health, allocation unit, backing disk and BitLocker state (admin)."""
from __future__ import annotations

from .. import decode
from ..format import bytes_human, percent
from ..ps import cim
from ..section import REQUIRES_ADMIN, Section, kv_groups, list_table, rows_of, sub_heading

LD_SCRIPT = cim("Win32_LogicalDisk", ("DeviceID", "VolumeName", "DriveType", "FileSystem", "Size", "FreeSpace", "VolumeSerialNumber",
                                      "Compressed", "ProviderName", "Description", "MediaType"))
VOL_SCRIPT = ("Get-Volume -ErrorAction SilentlyContinue | Where-Object DriveLetter | Select-Object DriveLetter,FileSystemLabel,FileSystem,"
              "HealthStatus,OperationalStatus,AllocationUnitSize,Size,SizeRemaining,DriveType")
PARTS_SCRIPT = ("Get-Partition -ErrorAction SilentlyContinue | Where-Object DriveLetter | ForEach-Object { "
                "$d = Get-Disk -Number $_.DiskNumber -ErrorAction SilentlyContinue; "
                "[pscustomobject]@{ DriveLetter = [string]$_.DriveLetter; DiskNumber = $_.DiskNumber; PartitionNumber = $_.PartitionNumber; "
                "BusType = [string]$d.BusType; DiskModel = [string]$d.FriendlyName } }")
BITLOCKER_SCRIPT = ("Get-BitLockerVolume -ErrorAction SilentlyContinue | Select-Object MountPoint,ProtectionStatus,VolumeStatus,"
                    "EncryptionPercentage")

PROTECTION = {0: "Off", 1: "On", 2: "Unknown"}
COLUMNS = [("Drive", "Drive"), ("Label", "Label"), ("Type", "Type"), ("File System", "File System"), ("Total", "Total"),
           ("Used", "Used"), ("Free", "Free"), ("Free %", "Free %"), ("Health", "Health"), ("Allocation Unit", "Allocation Unit"),
           ("Compressed", "Compressed"), ("Disk", "Disk"), ("Bus Type", "Bus Type"), ("BitLocker", "BitLocker"),
           ("Volume Serial Number", "Volume Serial Number"), ("Network Path (host name)", "Network Path")]


def build(logical, volumes, partitions, bitlocker) -> dict:
    vol_by = {str(v.get("DriveLetter") or "").upper(): v for v in rows_of(volumes)}
    part_by = {str(p.get("DriveLetter") or "").upper(): p for p in rows_of(partitions)}
    bl_by = {} if bitlocker == REQUIRES_ADMIN else {str(b.get("MountPoint") or "").upper().rstrip(":"): b for b in rows_of(bitlocker)}
    rows, low = [], []
    for ld in rows_of(logical):
        letter = str(ld.get("DeviceID") or "").rstrip(":").upper()
        v, p = vol_by.get(letter, {}), part_by.get(letter, {})
        size, free = decode.to_int(ld.get("Size")), decode.to_int(ld.get("FreeSpace"))
        used = size - free if size is not None and free is not None else None
        pct = percent(free, size) if size else ""
        if size and free is not None and free / size < 0.10:
            pct = f"⚠ {pct}"
            low.append(f"{letter}:")
        if bitlocker == REQUIRES_ADMIN:
            bl = REQUIRES_ADMIN
        else:
            b = bl_by.get(letter)
            bl = decode.lookup(PROTECTION, b.get("ProtectionStatus")) if b else ""
        rows.append({
            "Drive": f"{letter}:", "Label": ld.get("VolumeName") or v.get("FileSystemLabel", ""),
            "Type": decode.lookup(decode.DRIVE_TYPES, ld.get("DriveType")), "File System": ld.get("FileSystem") or v.get("FileSystem", ""),
            "Total": bytes_human(size) if size else "", "Used": bytes_human(used) if used is not None else "",
            "Free": bytes_human(free) if free is not None else "", "Free %": pct,
            "Health": v.get("HealthStatus", ""), "Allocation Unit": f"{v.get('AllocationUnitSize')} B" if v.get("AllocationUnitSize") else "",
            "Compressed": "Yes" if ld.get("Compressed") else ("No" if ld.get("Compressed") is not None else ""),
            "Disk": f"{p.get('DiskNumber')} ({p.get('DiskModel')})" if p else "", "Bus Type": p.get("BusType", ""),
            "BitLocker": bl, "Volume Serial Number": ld.get("VolumeSerialNumber", ""),
            "Network Path (host name)": ld.get("ProviderName") or "",
        })
    summary = {"Volumes": len(rows), "Fixed": sum(1 for r in rows if r["Type"] == "Local disk"),
               "Network": sum(1 for r in rows if r["Type"] == "Network drive"),
               "Removable": sum(1 for r in rows if r["Type"] == "Removable"),
               "Low Space (<10 %)": ", ".join(low) or "None"}
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.query("logical", LD_SCRIPT), ctx.query("volumes", VOL_SCRIPT, timeout=45),
                 ctx.query("partitions", PARTS_SCRIPT, timeout=45), ctx.admin_query("bitlocker", BITLOCKER_SCRIPT, timeout=30))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Volumes") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="logical_disks", title="Logical Disks", group="Hardware", collect=collect, render=render, timeout=45)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Storage Devices with partitions/SMART/reliability; Logical Disks with usage and BitLocker`

---

### Task 23: Ports and USB

**Files:**
- Create: `pc_report/sections/ports.py`, `pc_report/sections/usb.py`
- Test: `tests/pc_report/test_ports.py`, `tests/pc_report/test_usb.py`
- Fixtures: `ports/{connectors,serial,serialcomm,parallel}.json`, `usb/{controllers,hubs,devices,selective_suspend.txt}`

**Interfaces:** `usb.build(...) -> {"groups": [summary], "controllers": [...], "hubs": [...], "devices": [...]}`; `usb.hasp_devices(data) -> list[str]` (device names with VID 0529 or name containing HASP/Sentinel) for the Noldus Summary.

- [ ] **Step 1: Tests**

`tests/pc_report/test_ports.py`:

```python
import unittest

from pc_report.sections import ports as mod
from tests.pc_report import support

CONN = [{"ExternalReferenceDesignator": "USB 1", "ConnectorType": [16], "PortType": 16}]
SERIAL = [{"Name": "Communications Port (COM1)", "DeviceID": "COM1", "Description": "Communications Port", "MaxBaudRate": 115200,
           "ProviderType": "RS232 Serial Port", "Status": "OK", "PNPDeviceID": "ACPI\\PNP0501\\0"}]
SERIALCOMM = [{"Name": "\\Device\\Serial0", "Value": "COM1"}, {"Name": "\\Device\\USBSER000", "Value": "COM5"}]
PARALLEL = []


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(CONN, SERIAL, SERIALCOMM, PARALLEL)
        self.assertEqual(data["connectors"][0]["Port Type"], "USB")
        self.assertEqual(data["serial"][0]["Max Baud Rate"], "115200 baud")
        com5 = next(r for r in data["serialcomm"] if r["Port"] == "COM5")
        self.assertEqual(com5["Device"], "\\Device\\USBSER000")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["COM Ports Registered"], "COM1, COM5")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Serial ports (registry SERIALCOMM)</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_usb.py`:

```python
import unittest

from pc_report.sections import usb as mod
from tests.pc_report import support

CTRL = [{"Name": "Intel(R) USB 3.20 eXtensible Host Controller", "Manufacturer": "Intel", "Status": "OK", "PNPDeviceID": "PCI\\VEN_8086&DEV_7AE0\\3", "ProtocolSupported": 16}]
HUBS = [{"Name": "USB Root Hub (USB 3.0)", "DeviceID": "USB\\ROOT_HUB30\\4", "Status": "OK", "PNPDeviceID": "USB\\ROOT_HUB30\\4", "Description": "USB Root Hub (USB 3.0)"}]
DEV = [{"InstanceId": "USB\\VID_0529&PID_0001\\5&1", "FriendlyName": "SafeNet Inc. Sentinel HASP Key", "Class": "USB", "Manufacturer": "SafeNet Inc.",
        "Status": "OK", "Present": True, "Service": "hardlock", "Parent": "USB\\ROOT_HUB30\\4"},
       {"InstanceId": "USB\\VID_2676&PID_BA02\\123", "FriendlyName": "Basler ace acA1920", "Class": "Camera", "Manufacturer": "Basler",
        "Status": "OK", "Present": True, "Service": "usbvideo", "Parent": "USB\\ROOT_HUB30\\4"}]
SUSPEND = """Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
  Subgroup GUID: 2a737441-1930-4402-8d77-b2bebba308a3  (USB settings)
    Power Setting GUID: 48e6b7a6-50f5-4782-a5d4-53bb50f7e3f1  (USB selective suspend setting)
      Possible Setting Index: 000
      Possible Setting Friendly Name: Disabled
      Possible Setting Index: 001
      Possible Setting Friendly Name: Enabled
    Current AC Power Setting Index: 0x00000000
    Current DC Power Setting Index: 0x00000001
"""


class BuildTests(unittest.TestCase):
    def test_devices_and_suspend(self):
        data = mod.build(CTRL, HUBS, DEV, SUSPEND)
        hasp = next(r for r in data["devices"] if r["Name"].startswith("SafeNet"))
        self.assertEqual(hasp["VID / PID"], "0529 / 0001")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Selective Suspend (AC)"], "Disabled")
        self.assertEqual(rows["Selective Suspend (DC)"], "Enabled")
        self.assertEqual(rows["USB Devices Present"], 2)
        self.assertEqual(mod.hasp_devices(data), ["SafeNet Inc. Sentinel HASP Key"])

    def test_controller_version(self):
        data = mod.build(CTRL, HUBS, DEV, "")
        self.assertEqual(data["controllers"][0]["USB Version"], "USB")
        self.assertEqual(dict(data["groups"][0]["rows"])["Selective Suspend (AC)"], "")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>VID / PID</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/ports.py`:

```python
"""Ports: external connectors, serial ports (WMI and SERIALCOMM registry), parallel ports."""
from __future__ import annotations

from .. import decode
from ..ps import cim, reg_props
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

CONNECTORS_SCRIPT = cim("Win32_PortConnector", ("ExternalReferenceDesignator", "ConnectorType", "PortType"))
SERIAL_SCRIPT = cim("Win32_SerialPort", ("Name", "DeviceID", "Description", "MaxBaudRate", "ProviderType", "Status", "PNPDeviceID"))
SERIALCOMM_SCRIPT = reg_props(r"HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM")
PARALLEL_SCRIPT = cim("Win32_ParallelPort", ("Name", "DeviceID", "Status", "PNPDeviceID"))

CONN_COLUMNS = [("Designator", "Designator"), ("Connector", "Connector"), ("Port Type", "Port Type")]
SERIAL_COLUMNS = [("Name", "Name"), ("Device", "Device"), ("Description", "Description"), ("Max Baud Rate", "Max Baud Rate"),
                  ("Provider", "Provider"), ("Status", "Status"), ("PnP Device ID", "PnP Device ID")]
SERIALCOMM_COLUMNS = [("Port", "Port"), ("Device", "Device object")]
PARALLEL_COLUMNS = [("Name", "Name"), ("Device", "Device"), ("Status", "Status"), ("PnP Device ID", "PnP Device ID")]


def build(connectors, serial, serialcomm, parallel) -> dict:
    conn = [{"Designator": c.get("ExternalReferenceDesignator", ""),
             "Connector": decode.lookup(decode.PORT_CONNECTOR_TYPES, c.get("ConnectorType")),
             "Port Type": decode.lookup(decode.PORT_TYPES, c.get("PortType"))} for c in rows_of(connectors)]
    ser = [{"Name": s.get("Name", ""), "Device": s.get("DeviceID", ""), "Description": s.get("Description", ""),
            "Max Baud Rate": f"{s.get('MaxBaudRate')} baud" if s.get("MaxBaudRate") else "", "Provider": s.get("ProviderType", ""),
            "Status": s.get("Status", ""), "PnP Device ID": s.get("PNPDeviceID", "")} for s in rows_of(serial)]
    comm = sorted([{"Port": r.get("Value", ""), "Device": r.get("Name", "")} for r in rows_of(serialcomm)],
                  key=lambda r: (len(str(r["Port"])), str(r["Port"])))
    par = [{"Name": p.get("Name", ""), "Device": p.get("DeviceID", ""), "Status": p.get("Status", ""), "PnP Device ID": p.get("PNPDeviceID", "")}
           for p in rows_of(parallel)]
    summary = {"External Connectors": len(conn), "Serial Ports (WMI)": len(ser),
               "COM Ports Registered": ", ".join(str(r["Port"]) for r in comm) or "None", "Parallel Ports": len(par)}
    return {"groups": [{"title": "Summary", "rows": summary}], "connectors": conn, "serial": ser, "serialcomm": comm, "parallel": par}


def collect(ctx):
    return build(ctx.query("connectors", CONNECTORS_SCRIPT), ctx.query("serial", SERIAL_SCRIPT),
                 ctx.query("serialcomm", SERIALCOMM_SCRIPT), ctx.query("parallel", PARALLEL_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("External connectors") + list_table(CONN_COLUMNS, data.get("connectors"))
            + sub_heading("Serial ports (WMI)") + list_table(SERIAL_COLUMNS, data.get("serial"))
            + sub_heading("Serial ports (registry SERIALCOMM)") + list_table(SERIALCOMM_COLUMNS, data.get("serialcomm"))
            + sub_heading("Parallel ports") + list_table(PARALLEL_COLUMNS, data.get("parallel")))


SECTION = Section(key="ports", title="Ports", group="Hardware", collect=collect, render=render)
```

`pc_report/sections/usb.py`:

```python
"""USB: controllers, hubs, every USB device with VID/PID and parent, and the selective-suspend power setting."""
from __future__ import annotations

import re

from .. import decode
from ..format import yes_no
from ..ps import cim
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

CTRL_SCRIPT = cim("Win32_USBController", ("Name", "Manufacturer", "Status", "PNPDeviceID", "ProtocolSupported"))
HUBS_SCRIPT = cim("Win32_USBHub", ("Name", "DeviceID", "Status", "PNPDeviceID", "Description"))
DEVICES_SCRIPT = r"""
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB\*' } | ForEach-Object {
  $parent = ''
  try { $parent = [string](Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_Parent' -ErrorAction SilentlyContinue).Data } catch {}
  [pscustomobject]@{ InstanceId = $_.InstanceId; FriendlyName = [string]$_.FriendlyName; Class = [string]$_.Class; Manufacturer = [string]$_.Manufacturer
                     Status = [string]$_.Status; Present = $_.Present; Service = [string]$_.Service; Parent = $parent }
}
"""
SUSPEND_ARGS = ["powercfg", "/q", "SCHEME_CURRENT", "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb50f7e3f1"]

PROTOCOL = {16: "USB", 17: "USB 1.1", 18: "USB 2.0", 19: "USB 3.0"}  # Win32_USBController.ProtocolSupported
HASP_VIDS = {"0529", "0471"}
_VIDPID = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")
_AC = re.compile(r"Current AC Power Setting Index:\s*0x([0-9A-Fa-f]+)")
_DC = re.compile(r"Current DC Power Setting Index:\s*0x([0-9A-Fa-f]+)")

CTRL_COLUMNS = [("Name", "Name"), ("Manufacturer", "Manufacturer"), ("USB Version", "USB Version"), ("Status", "Status"), ("PnP Device ID", "PnP Device ID")]
HUB_COLUMNS = [("Name", "Name"), ("Status", "Status"), ("Device ID", "Device ID")]
DEV_COLUMNS = [("Name", "Name"), ("VID / PID", "VID / PID"), ("Class", "Class"), ("Manufacturer", "Manufacturer"), ("Service", "Service"),
               ("Status", "Status"), ("Present", "Present"), ("Parent", "Parent"), ("Instance", "Instance")]


def _suspend(text: str, rx) -> str:
    m = rx.search(text or "")
    if not m:
        return ""
    return "Enabled" if int(m.group(1), 16) else "Disabled"


def build(controllers, hubs, devices, suspend_text) -> dict:
    ctrl = [{"Name": c.get("Name", ""), "Manufacturer": c.get("Manufacturer", ""),
             "USB Version": decode.lookup(PROTOCOL, c.get("ProtocolSupported")), "Status": c.get("Status", ""),
             "PnP Device ID": c.get("PNPDeviceID", "")} for c in rows_of(controllers)]
    hub_rows = [{"Name": h.get("Name") or h.get("Description", ""), "Status": h.get("Status", ""), "Device ID": h.get("DeviceID", "")}
                for h in rows_of(hubs)]
    dev_rows = []
    for d in rows_of(devices):
        m = _VIDPID.search(str(d.get("InstanceId") or ""))
        dev_rows.append({"Name": d.get("FriendlyName") or "", "VID / PID": f"{m.group(1).upper()} / {m.group(2).upper()}" if m else "",
                         "Class": d.get("Class", ""), "Manufacturer": d.get("Manufacturer", ""), "Service": d.get("Service", ""),
                         "Status": d.get("Status", ""), "Present": yes_no(d.get("Present")), "Parent": d.get("Parent", ""),
                         "Instance": d.get("InstanceId", "")})
    dev_rows.sort(key=lambda r: (r["Present"] != "Yes", str(r["Name"]).lower()))
    summary = {"Controllers": len(ctrl), "Hubs": len(hub_rows), "USB Devices Present": sum(1 for r in dev_rows if r["Present"] == "Yes"),
               "USB Devices Not Present": sum(1 for r in dev_rows if r["Present"] != "Yes"),
               "Selective Suspend (AC)": _suspend(suspend_text, _AC), "Selective Suspend (DC)": _suspend(suspend_text, _DC)}
    return {"groups": [{"title": "Summary", "rows": summary}], "controllers": ctrl, "hubs": hub_rows, "devices": dev_rows}


def hasp_devices(data) -> list[str]:
    out = []
    for r in rows_of((data or {}).get("devices") if isinstance(data, dict) else None):
        vid = str(r.get("VID / PID") or "")[:4]
        name = str(r.get("Name") or "")
        if vid in HASP_VIDS or re.search(r"hasp|sentinel|hardlock", name, re.I):
            out.append(name)
    return out


def collect(ctx):
    return build(ctx.query("controllers", CTRL_SCRIPT), ctx.query("hubs", HUBS_SCRIPT),
                 ctx.query("devices", DEVICES_SCRIPT, timeout=90), ctx.text("selective_suspend", SUSPEND_ARGS))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Controllers") + list_table(CTRL_COLUMNS, data.get("controllers"))
            + sub_heading("Hubs") + list_table(HUB_COLUMNS, data.get("hubs"))
            + sub_heading("Devices") + list_table(DEV_COLUMNS, data.get("devices")))


SECTION = Section(key="usb", title="USB", group="Hardware", collect=collect, render=render, timeout=90)
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Ports with SERIALCOMM; USB devices with VID/PID, parents and selective suspend`

---

### Task 24: Printers and Virtual Machine

**Files:**
- Create: `pc_report/sections/printers.py`, `pc_report/sections/virtual_machine.py`
- Test: `tests/pc_report/test_printers.py`, `tests/pc_report/test_virtual_machine.py`
- Fixtures: `printers/{printers,spooler}.json`, `virtual_machine/{system,services}.json` (+ `_shared/pnp_entities.json`)

- [ ] **Step 1: Tests**

`tests/pc_report/test_printers.py`:

```python
import unittest

from pc_report.sections import printers as mod
from tests.pc_report import support

PR = [{"Name": "Microsoft Print to PDF", "DriverName": "Microsoft Print To PDF", "PortName": "PORTPROMPT:", "Default": True, "Shared": False,
       "ShareName": "", "Network": False, "Local": True, "PrinterStatus": 3, "Location": "", "WorkOffline": False, "Comment": "",
       "PrintProcessor": "winprint", "Priority": 1}]
SP = {"State": "Running", "StartMode": "Auto"}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(PR, SP)
        self.assertEqual(data["rows"][0]["Status"], "Idle")
        self.assertEqual(data["rows"][0]["Default"], "Yes")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Print Spooler"], "Running (Auto)")
        self.assertEqual(rows["Default Printer"], "Microsoft Print to PDF")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Print Spooler</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_virtual_machine.py`:

```python
import unittest

from pc_report.sections import virtual_machine as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_physical_host_with_hyper_v(self):
        rows = mod.flatten(mod.build({"Manufacturer": "Dell Inc.", "Model": "Precision 3660", "HypervisorPresent": True},
                                     {"Manufacturer": "Dell Inc.", "Version": "DELL - 1", "BaseBoardManufacturer": "Dell Inc.", "BaseBoardProduct": "0ABC"},
                                     [{"Name": "vmms", "State": "Running", "StartMode": "Auto"}, {"Name": "vmcompute", "State": "Stopped", "StartMode": "Manual"}],
                                     [{"Name": "Intel Ethernet", "PNPClass": "Net"}]))
        self.assertEqual(rows["Running Inside a VM"], "No")
        self.assertEqual(rows["Hypervisor Present"], "Yes")
        self.assertEqual(rows["Interpretation"], "Physical machine with a hypervisor active (Hyper-V role, VBS or WSL 2)")
        self.assertEqual(rows["Hyper-V Management (vmms)"], "Running (Auto)")

    def test_vmware_guest(self):
        rows = mod.flatten(mod.build({"Manufacturer": "VMware, Inc.", "Model": "VMware20,1", "HypervisorPresent": True}, {}, [],
                                     [{"Name": "VMware SVGA 3D", "PNPClass": "Display"}, {"Name": "VMware VMCI Bus Device", "PNPClass": "System"}]))
        self.assertEqual(rows["Running Inside a VM"], "Yes")
        self.assertEqual(rows["Detected Hypervisor"], "VMware")
        self.assertIn("VMware SVGA 3D", rows["Guest Device Markers"])

    def test_detect(self):
        self.assertEqual(mod.detect_vendor("innotek GmbH", "VirtualBox", ""), "VirtualBox")
        self.assertEqual(mod.detect_vendor("Microsoft Corporation", "Virtual Machine", ""), "Hyper-V")
        self.assertEqual(mod.detect_vendor("QEMU", "Standard PC (Q35)", ""), "QEMU/KVM")
        self.assertEqual(mod.detect_vendor("Dell Inc.", "OptiPlex", ""), "")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Running Inside a VM</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/printers.py`:

```python
"""Printers: every queue with driver, port, sharing, status and offline state; spooler service state."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

PRINTERS_SCRIPT = cim("Win32_Printer", ("Name", "DriverName", "PortName", "Default", "Shared", "ShareName", "Network", "Local",
                                        "PrinterStatus", "Location", "WorkOffline", "Comment", "PrintProcessor", "Priority"))
SPOOLER_SCRIPT = cim("Win32_Service", ("State", "StartMode"), where="Name='Spooler'")

COLUMNS = [("Name", "Name"), ("Driver", "Driver"), ("Port", "Port"), ("Status", "Status"), ("Default", "Default"),
           ("Shared", "Shared"), ("Share Name", "Share Name"), ("Network", "Network"), ("Offline", "Offline"),
           ("Location", "Location"), ("Comment", "Comment"), ("Print Processor", "Print Processor"), ("Priority", "Priority")]


def build(printers, spooler) -> dict:
    rows = [{"Name": p.get("Name", ""), "Driver": p.get("DriverName", ""), "Port": p.get("PortName", ""),
             "Status": decode.lookup(decode.PRINTER_STATUS, p.get("PrinterStatus")), "Default": yes_no(p.get("Default")),
             "Shared": yes_no(p.get("Shared")), "Share Name": p.get("ShareName") or "", "Network": yes_no(p.get("Network")),
             "Offline": yes_no(p.get("WorkOffline")), "Location": p.get("Location") or "", "Comment": p.get("Comment") or "",
             "Print Processor": p.get("PrintProcessor", ""), "Priority": p.get("Priority", "")} for p in rows_of(printers)]
    rows.sort(key=lambda r: (r["Default"] != "Yes", str(r["Name"]).lower()))
    spooler = spooler or {}
    summary = {"Printers": len(rows), "Default Printer": next((r["Name"] for r in rows if r["Default"] == "Yes"), "None"),
               "Network Printers": sum(1 for r in rows if r["Network"] == "Yes"),
               "Offline": ", ".join(r["Name"] for r in rows if r["Offline"] == "Yes") or "None",
               "Print Spooler": f"{spooler.get('State')} ({spooler.get('StartMode')})" if spooler.get("State") else "Not found"}
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.query("printers", PRINTERS_SCRIPT, timeout=45), first_dict(ctx.query("spooler", SPOOLER_SCRIPT)))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Printers") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="printers", title="Printers", group="Hardware", collect=collect, render=render, timeout=45)
```

`pc_report/sections/virtual_machine.py`:

```python
"""Virtual Machine: guest detection from firmware/model markers and devices; host-side hypervisor services."""
from __future__ import annotations

import re

from ..format import yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, rows_of

SYSTEM_SCRIPT = cim("Win32_ComputerSystem", ("Manufacturer", "Model", "HypervisorPresent"))
FIRMWARE_SCRIPT = ("$b = Get-CimInstance Win32_BIOS -ErrorAction SilentlyContinue; $bb = Get-CimInstance Win32_BaseBoard -ErrorAction SilentlyContinue; "
                   "[pscustomobject]@{ Manufacturer = [string]$b.Manufacturer; Version = [string]$b.Version; "
                   "BaseBoardManufacturer = [string]$bb.Manufacturer; BaseBoardProduct = [string]$bb.Product }")
SERVICES_SCRIPT = cim("Win32_Service", ("Name", "State", "StartMode"),
                      where="Name='vmms' OR Name='vmcompute' OR Name='HvHost' OR Name='LxssManager' OR Name='CmService' "
                            "OR Name='VMTools' OR Name='VBoxService' OR Name='vmicheartbeat' OR Name='WSLService'")

SERVICE_LABELS = {"vmms": "Hyper-V Management (vmms)", "vmcompute": "Hyper-V Host Compute (vmcompute)", "HvHost": "HV Host Service",
                  "LxssManager": "WSL (LxssManager)", "WSLService": "WSL (WSLService)", "CmService": "Windows Sandbox (CmService)",
                  "VMTools": "VMware Tools (guest)", "VBoxService": "VirtualBox Guest Additions (guest)",
                  "vmicheartbeat": "Hyper-V Heartbeat (guest)"}
GUEST_MARKERS = re.compile(r"vmware|virtualbox|vbox|hyper-v|virtual machine|red hat virtio|virtio|qemu|parallels|xen|bochs|kvm", re.I)


def detect_vendor(manufacturer, model, bios) -> str:
    text = f"{manufacturer} {model} {bios}".lower()
    if "vmware" in text:
        return "VMware"
    if "virtualbox" in text or "innotek" in text or "vbox" in text:
        return "VirtualBox"
    if "microsoft corporation" in text and "virtual machine" in text:
        return "Hyper-V"
    if "qemu" in text or "kvm" in text or "bochs" in text:
        return "QEMU/KVM"
    if "parallels" in text:
        return "Parallels"
    if "xen" in text:
        return "Xen"
    return ""


def build(system, firmware, services, pnp) -> dict:
    system, firmware = system or {}, firmware or {}
    vendor = detect_vendor(system.get("Manufacturer", ""), system.get("Model", ""),
                           f"{firmware.get('Manufacturer', '')} {firmware.get('Version', '')} {firmware.get('BaseBoardProduct', '')}")
    markers = sorted({str(d.get("Name")) for d in rows_of(pnp) if d.get("Name") and GUEST_MARKERS.search(str(d.get("Name")))})
    guest_services = [s for s in rows_of(services) if s.get("Name") in ("VMTools", "VBoxService", "vmicheartbeat") and s.get("State") == "Running"]
    inside = bool(vendor) or bool(guest_services) or (len(markers) >= 2)
    hypervisor = bool(system.get("HypervisorPresent"))
    if inside:
        interpretation = f"Virtual machine ({vendor or 'vendor not identified'})"
    elif hypervisor:
        interpretation = "Physical machine with a hypervisor active (Hyper-V role, VBS or WSL 2)"
    else:
        interpretation = "Physical machine, no hypervisor"
    rows = {"Running Inside a VM": yes_no(inside), "Detected Hypervisor": vendor or ("Not identified" if inside else "None"),
            "Hypervisor Present": yes_no(hypervisor), "Interpretation": interpretation,
            "System Manufacturer": system.get("Manufacturer", ""), "System Model": system.get("Model", ""),
            "BIOS Vendor": firmware.get("Manufacturer", ""), "BIOS Version": firmware.get("Version", ""),
            "Guest Device Markers": ", ".join(markers) or "None"}
    svc = {}
    by_name = {s.get("Name"): s for s in rows_of(services)}
    for name, label in SERVICE_LABELS.items():
        s = by_name.get(name)
        svc[label] = f"{s.get('State')} ({s.get('StartMode')})" if s else "Not installed"
    return {"groups": [{"title": "Detection", "rows": rows}, {"title": "Virtualization Services", "rows": svc}]}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(first_dict(ctx.query("system", SYSTEM_SCRIPT)), first_dict(ctx.query("firmware", FIRMWARE_SCRIPT)),
                 ctx.query("services", SERVICES_SCRIPT), ctx.shared("pnp_entities"))


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="virtual_machine", title="Virtual Machine", group="Hardware", collect=collect, render=render, timeout=60)
```

In the test's VMware case, `firmware` is `{}` and `pnp` has two VMware markers, so `inside` is true through the vendor string alone; the marker count is a fallback for guests with generic firmware strings.

- [ ] **Step 3: Standard steps 3–5**

Fixture note: `virtual_machine/firmware.json` is also written (three queries: `system`, `firmware`, `services`).

Commit message: `feat(pc_report): Printers with spooler state; Virtual Machine detection with services and device markers`

### Task 25: Cameras

**Files:**
- Create: `pc_report/sections/cameras.py`
- Test: `tests/pc_report/test_cameras.py`
- Fixtures: `cameras/{directshow_capture,frame_server,consent}.json` (+ `_shared/{pnp_entities,dxdiag}.json`)

**Interfaces:** `after=("installed_programs",)` so Basler/GigE transport layers can be read from `ctx.result("installed_programs")["rows"]`. Data: `{"groups": [Frame Server, Consent, GenICam, Transport Layers], "pnp": [...], "video_sources": [...], "audio_sources": [...], "dxdiag": [...], "consent_apps": [...]}`. `camera_names(data)` returns PnP camera names for the Noldus Summary; `frame_server_enabled(data) -> bool | None`; `denied(data) -> list[str]` (capabilities denied globally).

- [ ] **Step 1: Test `tests/pc_report/test_cameras.py`**

```python
import unittest

from pc_report.sections import cameras as mod
from tests.pc_report import support

PNP = [{"Name": "Basler ace acA1920-40uc", "Manufacturer": "Basler", "PNPClass": "Camera", "Status": "OK", "ConfigManagerErrorCode": 0,
        "Service": "usbvideo", "Present": True, "PNPDeviceID": "USB\\VID_2676&PID_BA02\\123", "DeviceID": "USB\\VID_2676&PID_BA02\\123"},
       {"Name": "Intel Ethernet", "PNPClass": "Net", "Status": "OK", "ConfigManagerErrorCode": 0, "Present": True, "PNPDeviceID": "PCI\\1"},
       {"Name": "Integrated Webcam", "Manufacturer": "Microsoft", "PNPClass": "Image", "Status": "Error", "ConfigManagerErrorCode": 22,
        "Service": "usbvideo", "Present": True, "PNPDeviceID": "USB\\VID_0C45&PID_6A10\\1", "DeviceID": "USB\\VID_0C45&PID_6A10\\1"}]
DS = [{"Category": "Video Capture Sources", "Name": "Basler ace acA1920-40uc", "CLSID": "{860BB310-5D01-11d0-BD3B-00A0C911CE86}",
       "DevicePath": "\\\\?\\usb#vid_2676&pid_ba02#123#{65e8773d}", "Architecture": "x64"},
      {"Category": "Audio Capture Sources", "Name": "Microphone (USB Camera)", "CLSID": "{33D9A762}", "DevicePath": "", "Architecture": "x64"}]
DX = {"VideoCaptureDevices": {"VideoCaptureDevice": {"FriendlyName": "Basler ace acA1920-40uc", "Category": "Camera", "Manufacturer": "Basler",
                                                     "HardwareID": "USB\\VID_2676&PID_BA02&REV_0100", "DriverDesc": "USB Video Device",
                                                     "DriverProvider": "Microsoft", "DriverVersion": "10.0.26100.1", "DriverDateEnglish": "6/21/2006",
                                                     "Service": "usbvideo", "Class": "Camera", "ProblemCode": "No Problem", "Location": "Port_#0001.Hub_#0002"}}}
FS = {"EnableFrameServerMode": 0, "EnableFrameServerModeWow": None, "FrameServerStatus": "Stopped", "FrameServerStartType": "Manual"}
CONSENT = [{"Capability": "webcam", "Hive": "HKCU", "App": "(global)", "Value": "Allow", "LastUsedStart": None, "LastUsedStop": None},
           {"Capability": "webcam", "Hive": "HKCU", "App": "C:#Program Files#Noldus#EthoVision.exe", "Value": "Allow",
            "LastUsedStart": 133700000000000000, "LastUsedStop": 0},
           {"Capability": "microphone", "Hive": "HKLM", "App": "(global)", "Value": "Deny", "LastUsedStart": None, "LastUsedStop": None}]
ENV = {"GENICAM_GENTL64_PATH": "C:\\Program Files\\Basler\\pylon 7\\Runtime\\x64\\;C:\\Program Files\\Common Files\\Noldus\\GenTL\\"}
PROGRAMS = [{"Name": "pylon 7.4 Camera Software Suite", "Version": "7.4.0", "Publisher": "Basler AG"},
            {"Name": "Basler GigE Vision Transport Layer", "Version": "7.4.0", "Publisher": "Basler AG"},
            {"Name": "7-Zip", "Version": "23.01", "Publisher": "Igor Pavlov"}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(PNP, DS, DX, FS, CONSENT, ENV, PROGRAMS)
        self.rows = mod.flatten(self.data)

    def test_pnp_cameras_only(self):
        names = [r["Name"] for r in self.data["pnp"]]
        self.assertEqual(names, ["Basler ace acA1920-40uc", "Integrated Webcam"])
        self.assertEqual(self.data["pnp"][1]["Problem"], "22: Disabled")
        self.assertEqual(mod.camera_names(self.data), names)

    def test_frame_server_and_consent(self):
        self.assertEqual(self.rows["Frame Server Mode"], "Disabled (exclusive camera access for legacy applications)")
        self.assertEqual(self.rows["Frame Server Service"], "Stopped (Manual)")
        self.assertEqual(self.rows["Camera Access (user)"], "Allow")
        self.assertEqual(self.rows["Microphone Access (machine policy)"], "Deny")
        self.assertEqual(mod.denied(self.data), ["Microphone (machine policy)"])
        app = self.data["consent_apps"][0]
        self.assertEqual(app["Application"], "C:\\Program Files\\Noldus\\EthoVision.exe")
        self.assertEqual(app["In Use Now"], "Yes")
        self.assertRegex(app["Last Used Start"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_genicam_and_transport_layers(self):
        self.assertEqual(self.rows["GENICAM_GENTL64_PATH"], ["C:\\Program Files\\Basler\\pylon 7\\Runtime\\x64\\", "C:\\Program Files\\Common Files\\Noldus\\GenTL\\"])
        self.assertEqual(self.rows["Basler / GigE Transport Layers"], ["Basler GigE Vision Transport Layer 7.4.0", "pylon 7.4 Camera Software Suite 7.4.0"])

    def test_sources_and_dxdiag(self):
        self.assertEqual(self.data["video_sources"][0]["Device Path"], "\\\\?\\usb#vid_2676&pid_ba02#123#{65e8773d}")
        self.assertEqual(self.data["audio_sources"][0]["Name"], "Microphone (USB Camera)")
        self.assertEqual(self.data["dxdiag"][0]["Driver"], "USB Video Device 10.0.26100.1 (Microsoft)")

    def test_filetime(self):
        self.assertEqual(mod.filetime(0), "")
        self.assertRegex(mod.filetime(133700000000000000), r"^\d{4}-")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        programs = {"installed_programs": {"data": {"rows": PROGRAMS}, "notes": []}}
        _data, html, ctx = support.collect_and_render(mod.SECTION, results=programs)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Frame Server Mode</th>", html)
        self.assertIn("<h3>DirectShow video capture sources</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/cameras.py`**

```python
"""Cameras: PnP cameras, DirectShow capture sources, dxdiag detail, Frame Server, consent store, GenICam and transport layers."""
from __future__ import annotations

import datetime
import os
import re

from .. import decode
from ..format import yes_no
from ..ps import dx_list
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

DS_SCRIPT = r"""
$cats = @{ '{860BB310-5D01-11D0-BD3B-00A0C911CE86}' = 'Video Capture Sources'; '{33D9A762-90C8-11D0-BD43-00A0C911CE86}' = 'Audio Capture Sources' }
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' }, @{ Root = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  foreach ($cat in $cats.Keys) {
    $inst = Join-Path (Join-Path $arch.Root $cat) 'Instance'
    if (-not (Test-Path $inst)) { continue }
    Get-ChildItem $inst -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      [pscustomobject]@{ Category = $cats[$cat]; Name = [string]$x.FriendlyName; CLSID = [string]$x.CLSID; DevicePath = [string]$x.DevicePath; Architecture = $arch.Name }
    }
  }
}
"""
FRAME_SERVER_SCRIPT = r"""
$svc = Get-Service FrameServer -ErrorAction SilentlyContinue
[pscustomobject]@{
  EnableFrameServerMode = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows Media Foundation\Platform' -ErrorAction SilentlyContinue).EnableFrameServerMode
  EnableFrameServerModeWow = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Media Foundation\Platform' -ErrorAction SilentlyContinue).EnableFrameServerMode
  FrameServerStatus = [string]$svc.Status; FrameServerStartType = [string]$svc.StartType
}
"""
CONSENT_SCRIPT = r"""
foreach ($cap in 'webcam','microphone') {
  foreach ($hive in 'HKCU','HKLM') {
    $root = "$($hive):\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\$cap"
    if (-not (Test-Path $root)) { continue }
    $g = Get-ItemProperty $root -ErrorAction SilentlyContinue
    [pscustomobject]@{ Capability = $cap; Hive = $hive; App = '(global)'; Value = [string]$g.Value; LastUsedStart = $null; LastUsedStop = $null }
    Get-ChildItem $root -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      if ($null -ne $x.Value -or $x.LastUsedTimeStart) {
        [pscustomobject]@{ Capability = $cap; Hive = $hive; App = $_.PSChildName; Value = [string]$x.Value; LastUsedStart = $x.LastUsedTimeStart; LastUsedStop = $x.LastUsedTimeStop }
      }
    }
  }
}
"""

CAMERA_CLASSES = {"Camera", "Image"}
CAMERA_NAME = re.compile(r"camera|webcam|basler|pylon|gige|daheng|flir|ids |imaging|capture", re.I)
TRANSPORT = re.compile(r"basler|pylon|gige|gentl|transport layer|coaxpress|camera link|euresys|daheng|galaxy", re.I)

PNP_COLUMNS = [("Name", "Name"), ("Class", "Class"), ("Manufacturer", "Manufacturer"), ("Status", "Status"), ("Problem", "Problem"),
               ("Service", "Service"), ("Present", "Present"), ("Device Instance", "Device Instance")]
DS_COLUMNS = [("Name", "Name"), ("CLSID", "CLSID"), ("Device Path", "Device Path"), ("Architecture", "Architecture")]
DX_COLUMNS = [("Name", "Name"), ("Category", "Category"), ("Manufacturer", "Manufacturer"), ("Hardware ID", "Hardware ID"),
              ("Driver", "Driver"), ("Driver Date", "Driver Date"), ("Service", "Service"), ("Problem", "Problem"), ("Location", "Location")]
CONSENT_COLUMNS = [("Capability", "Capability"), ("Scope", "Scope"), ("Application", "Application"), ("Access", "Access"),
                   ("Last Used Start", "Last Used Start"), ("Last Used Stop", "Last Used Stop"), ("In Use Now", "In Use Now")]


def filetime(value) -> str:
    n = decode.to_int(value)
    if not n:
        return ""
    try:
        dt = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=n / 10)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (OverflowError, ValueError, OSError):
        return ""


def _scope(hive) -> str:
    return "machine policy" if str(hive).upper() == "HKLM" else "user"


def _app_name(raw: str) -> str:
    return str(raw or "").replace("#", "\\")


def build(pnp, ds, dx, frame_server, consent, env, programs) -> dict:
    fs, env = frame_server or {}, env or {}
    pnp_rows = []
    for d in rows_of(pnp):
        name = str(d.get("Name") or "")
        cls = str(d.get("PNPClass") or "")
        if cls not in CAMERA_CLASSES and not (d.get("Service") == "usbvideo") and not (cls == "Media" and CAMERA_NAME.search(name)):
            continue
        code = decode.to_int(d.get("ConfigManagerErrorCode")) or 0
        pnp_rows.append({"Name": name, "Class": cls, "Manufacturer": d.get("Manufacturer") or "", "Status": d.get("Status") or "",
                         "Problem": f"{code}: {decode.lookup(decode.PNP_ERROR_CODES, code)}" if code else "",
                         "Service": d.get("Service") or "", "Present": yes_no(bool(d.get("Present"))),
                         "Device Instance": d.get("PNPDeviceID") or d.get("DeviceID") or ""})
    video = [{"Name": s.get("Name", ""), "CLSID": s.get("CLSID", ""), "Device Path": s.get("DevicePath", ""), "Architecture": s.get("Architecture", "")}
             for s in rows_of(ds) if s.get("Category") == "Video Capture Sources"]
    audio = [{"Name": s.get("Name", ""), "CLSID": s.get("CLSID", ""), "Device Path": s.get("DevicePath", ""), "Architecture": s.get("Architecture", "")}
             for s in rows_of(ds) if s.get("Category") == "Audio Capture Sources"]
    dxrows = [{"Name": v.get("FriendlyName", ""), "Category": v.get("Category", ""), "Manufacturer": v.get("Manufacturer", ""),
               "Hardware ID": v.get("HardwareID", ""),
               "Driver": " ".join(x for x in (v.get("DriverDesc", ""), v.get("DriverVersion", ""), f"({v.get('DriverProvider')})" if v.get("DriverProvider") else "") if x),
               "Driver Date": v.get("DriverDateEnglish", ""), "Service": v.get("Service", ""), "Problem": v.get("ProblemCode", ""),
               "Location": v.get("Location", "")} for v in dx_list(dx, "VideoCaptureDevices", "VideoCaptureDevice")]

    mode = fs.get("EnableFrameServerMode")
    if mode is None:
        mode = fs.get("EnableFrameServerModeWow")
    frame = {
        "Frame Server Mode": ("Not configured (Windows default: shared access through Frame Server)" if mode is None else
                              "Enabled (shared camera access through Frame Server)" if decode.to_int(mode) else
                              "Disabled (exclusive camera access for legacy applications)"),
        "Frame Server Service": f"{fs.get('FrameServerStatus')} ({fs.get('FrameServerStartType')})" if fs.get("FrameServerStatus") else "Not found",
    }
    consent_rows = {}
    apps = []
    for c in rows_of(consent):
        cap = "Camera" if c.get("Capability") == "webcam" else "Microphone"
        scope = _scope(c.get("Hive"))
        if c.get("App") == "(global)":
            consent_rows[f"{cap} Access ({scope})"] = c.get("Value") or "Not set"
            continue
        start, stop = decode.to_int(c.get("LastUsedStart")) or 0, decode.to_int(c.get("LastUsedStop")) or 0
        apps.append({"Capability": cap, "Scope": scope, "Application": _app_name(c.get("App")), "Access": c.get("Value") or "",
                     "Last Used Start": filetime(start), "Last Used Stop": filetime(stop),
                     "In Use Now": yes_no(bool(start and (stop == 0 or stop < start)))})
    apps.sort(key=lambda r: (r["In Use Now"] != "Yes", r["Capability"], r["Application"].lower()))
    genicam = {k: [p for p in str(v).split(";") if p] for k, v in sorted(env.items()) if k.upper().startswith("GENICAM_GENTL")}
    if not genicam:
        genicam = {"GenICam GenTL Producers": "No GENICAM_GENTL*_PATH variables set"}
    layers = sorted(f"{p.get('Name')} {p.get('Version') or ''}".strip() for p in rows_of(programs)
                    if TRANSPORT.search(f"{p.get('Name', '')} {p.get('Publisher', '')}"))
    transport = {"Basler / GigE Transport Layers": layers or "None found in installed programs"}
    return {"groups": [{"title": "Windows Camera Frame Server", "rows": frame}, {"title": "Camera and Microphone Consent", "rows": consent_rows},
                       {"title": "GenICam", "rows": genicam}, {"title": "Transport Layers", "rows": transport}],
            "pnp": pnp_rows, "video_sources": video, "audio_sources": audio, "dxdiag": dxrows, "consent_apps": apps}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def camera_names(data) -> list[str]:
    return [r.get("Name", "") for r in rows_of((data or {}).get("pnp") if isinstance(data, dict) else None)]


def frame_server_enabled(data):
    text = str(flatten(data).get("Frame Server Mode", ""))
    if text.startswith("Enabled") or text.startswith("Not configured"):
        return True
    if text.startswith("Disabled"):
        return False
    return None


def denied(data) -> list[str]:
    out = []
    for label, value in flatten(data).items():
        if label.endswith(")") and " Access (" in label and str(value).lower() == "deny":
            cap, scope = label.split(" Access (")
            out.append(f"{cap} ({scope}")
    return out


def collect(ctx):
    programs = (ctx.result("installed_programs") or {}).get("rows") if isinstance(ctx.result("installed_programs"), dict) else []
    return build(ctx.shared("pnp_entities"), ctx.query("directshow_capture", DS_SCRIPT), ctx.shared("dxdiag"),
                 first_dict(ctx.query("frame_server", FRAME_SERVER_SCRIPT)), ctx.query("consent", CONSENT_SCRIPT),
                 dict(os.environ), programs)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (sub_heading("Cameras (Plug and Play)") + list_table(PNP_COLUMNS, data.get("pnp"))
            + kv_groups(data.get("groups"))
            + sub_heading("Application consent") + list_table(CONSENT_COLUMNS, data.get("consent_apps"))
            + sub_heading("DirectShow video capture sources") + list_table(DS_COLUMNS, data.get("video_sources"))
            + sub_heading("DirectShow audio capture sources") + list_table(DS_COLUMNS, data.get("audio_sources"))
            + sub_heading("DirectX capture device detail") + list_table(DX_COLUMNS, data.get("dxdiag")))


SECTION = Section(key="cameras", title="Cameras", group="Hardware", collect=collect, render=render, timeout=120,
                  after=("installed_programs",))
```

The `"Hardware ID"` column label is a redaction token on purpose: hardware IDs of USB cameras carry serials in some vendors' formats.

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Cameras section with Frame Server, consent store, DirectShow sources and GenICam`

---

### Task 26: Network Information

**Files:**
- Create: `pc_report/sections/network_information.py`
- Test: `tests/pc_report/test_network_information.py`
- Fixtures: `network_information/{computer,ip_configuration,wmi_configuration,routes,proxy,winhttp_proxy.txt,wlan.txt}`

- [ ] **Step 1: Test `tests/pc_report/test_network_information.py`**

```python
import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import network_information as mod
from tests.pc_report import support

CS = {"Name": "PC-NAME", "Domain": "lab.example.org", "PartOfDomain": True, "DomainRole": 1, "Workgroup": None, "DNSHostName": "pc-name", "Description": ""}
IPC = [{"InterfaceAlias": "Ethernet", "InterfaceIndex": 12, "InterfaceDescription": "Intel I219", "Status": "Up", "MacAddress": "AA-BB-CC-DD-EE-FF",
        "LinkSpeed": "1 Gbps", "IPv4Address": ["192.168.10.55/24"], "IPv6Address": ["fe80::1c2d:3e4f:5a6b:7c8d/64"], "IPv4DefaultGateway": ["192.168.10.1"],
        "IPv6DefaultGateway": [], "DNSServer": ["192.168.10.2", "8.8.8.8"], "NetProfileName": "lab.example.org", "NetProfileCategory": "DomainAuthenticated",
        "IPv4Connectivity": "Internet", "IPv6Connectivity": "NoTraffic"}]
WMI = [{"InterfaceIndex": 12, "Description": "Intel I219", "DHCPEnabled": True, "DHCPServer": "192.168.10.2", "DHCPLeaseObtained": "/Date(1758000000000)/",
        "DHCPLeaseExpires": "/Date(1758086400000)/", "DNSDomain": "lab.example.org", "DNSDomainSuffixSearchOrder": ["lab.example.org"],
        "WINSPrimaryServer": None, "WINSSecondaryServer": None, "TcpipNetbiosOptions": 0, "IPConnectionMetric": 25, "MTU": None, "IPEnabled": True}]
ROUTES = [{"InterfaceAlias": "Ethernet", "DestinationPrefix": "0.0.0.0/0", "NextHop": "192.168.10.1", "RouteMetric": 0, "InterfaceMetric": 25, "AddressFamily": 2}]
PROXY = {"ProxyEnable": 0, "ProxyServer": None, "ProxyOverride": None, "AutoConfigURL": None}
WINHTTP = "\nCurrent WinHTTP proxy settings:\n\n    Direct access (no proxy server).\n\n"
WLAN = "\nThere is 1 interface on the system:\n\n    Name                   : Wi-Fi\n    Description            : Intel(R) Wi-Fi 6\n    State                  : connected\n    SSID                   : LabNet\n    Radio type             : 802.11ax\n    Channel                : 44\n    Receive rate (Mbps)    : 1200\n    Transmit rate (Mbps)   : 1200\n    Signal                 : 91%\n"


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(CS, IPC, WMI, ROUTES, PROXY, WINHTTP, WLAN)

    def test_identity(self):
        rows = dict(self.data["groups"][0]["rows"])
        self.assertEqual(rows["Computer Name"], "PC-NAME")
        self.assertEqual(rows["Domain Name"], "lab.example.org")
        self.assertEqual(rows["Role"], "Member Workstation")

    def test_interface(self):
        iface = self.data["interfaces"][0]
        rows = {}
        for g in iface["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["IPv4 Address"], ["192.168.10.55/24"])
        self.assertEqual(rows["Default Gateway"], ["192.168.10.1"])
        self.assertEqual(rows["DHCP Enabled"], "Yes")
        self.assertEqual(rows["DHCP Server"], "192.168.10.2")
        self.assertEqual(rows["NetBIOS over TCP/IP"], "Default (from DHCP)")
        self.assertEqual(rows["Network Profile"], "lab.example.org (DomainAuthenticated)")

    def test_proxy_routes_wifi(self):
        rows = dict(self.data["groups"][1]["rows"])
        self.assertEqual(rows["User Proxy"], "Disabled")
        self.assertEqual(rows["WinHTTP Proxy"], "Direct access (no proxy server)")
        self.assertEqual(self.data["routes"][0]["Next Hop"], "192.168.10.1")
        wifi = dict(self.data["groups"][2]["rows"])
        self.assertEqual(wifi["SSID"], "LabNet")
        self.assertEqual(wifi["Signal"], "91%")
        self.assertEqual(wifi["Radio Type"], "802.11ax")

    def test_redaction_masks_addresses(self):
        red = redact_payload(self.data, {"redact": True})
        rows = {}
        for g in red["interfaces"][0]["groups"]:
            rows.update(g["rows"])
        self.assertEqual(rows["IPv4 Address"], ["192.168.*.*/24"])
        self.assertEqual(rows["DHCP Server"], "192.168.*.*")
        self.assertEqual(rows["Default Gateway"], ["192.168.*.*"])
        self.assertNotEqual(dict(red["groups"][0]["rows"])["Computer Name"], "PC-NAME")
        self.assertNotEqual(dict(red["groups"][2]["rows"])["SSID"], "LabNet")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>IPv4 Address</th>", html)
        self.assertIn("<th>WinHTTP Proxy</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/network_information.py`**

```python
"""Network Information: identity, per-interface IP configuration, DHCP/DNS, routes, proxies and Wi-Fi."""
from __future__ import annotations

import re

from .. import decode
from ..format import fmt_datetime, yes_no
from ..ps import cim
from ..section import Section, as_list, first_dict, kv_groups, list_table, rows_of, sub_heading

CS_SCRIPT = cim("Win32_ComputerSystem", ("Name", "Domain", "PartOfDomain", "DomainRole", "Workgroup", "DNSHostName", "Description"))
IPC_SCRIPT = r"""
Get-NetIPConfiguration -Detailed -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ InterfaceAlias = $_.InterfaceAlias; InterfaceIndex = $_.InterfaceIndex; InterfaceDescription = $_.InterfaceDescription
    Status = [string]$_.NetAdapter.Status; MacAddress = [string]$_.NetAdapter.MacAddress; LinkSpeed = [string]$_.NetAdapter.LinkSpeed
    IPv4Address = @($_.IPv4Address | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" })
    IPv6Address = @($_.IPv6Address | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" })
    IPv4DefaultGateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
    IPv6DefaultGateway = @($_.IPv6DefaultGateway | ForEach-Object { $_.NextHop })
    DNSServer = @($_.DNSServer | ForEach-Object { $_.ServerAddresses } | ForEach-Object { $_ })
    NetProfileName = [string]$_.NetProfile.Name; NetProfileCategory = [string]$_.NetProfile.NetworkCategory
    IPv4Connectivity = [string]$_.NetProfile.IPv4Connectivity; IPv6Connectivity = [string]$_.NetProfile.IPv6Connectivity }
}
"""
WMI_SCRIPT = cim("Win32_NetworkAdapterConfiguration", ("InterfaceIndex", "Description", "DHCPEnabled", "DHCPServer", "DHCPLeaseObtained",
                                                       "DHCPLeaseExpires", "DNSDomain", "DNSDomainSuffixSearchOrder", "WINSPrimaryServer",
                                                       "WINSSecondaryServer", "TcpipNetbiosOptions", "IPConnectionMetric", "MTU", "IPEnabled"),
                 where="IPEnabled=TRUE")
ROUTES_SCRIPT = ("Get-NetRoute -DestinationPrefix '0.0.0.0/0','::/0' -ErrorAction SilentlyContinue | Select-Object InterfaceAlias,"
                 "DestinationPrefix,NextHop,RouteMetric,InterfaceMetric,AddressFamily")
PROXY_SCRIPT = ("Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -ErrorAction SilentlyContinue "
                "| Select-Object ProxyEnable,ProxyServer,ProxyOverride,AutoConfigURL")
WINHTTP_ARGS = ["netsh", "winhttp", "show", "proxy"]
WLAN_ARGS = ["netsh", "wlan", "show", "interfaces"]

NETBIOS = {0: "Default (from DHCP)", 1: "Enabled", 2: "Disabled"}
ROUTE_COLUMNS = [("Interface", "Interface"), ("Destination", "Destination"), ("Next Hop", "Next Hop"), ("Route Metric", "Route Metric"),
                 ("Interface Metric", "Interface Metric"), ("Family", "Family")]
WLAN_KEYS = {"Name": "Interface", "Description": "Adapter", "State": "State", "SSID": "SSID", "BSSID": "BSSID", "Radio type": "Radio Type",
             "Authentication": "Authentication", "Cipher": "Cipher", "Channel": "Channel", "Band": "Band",
             "Receive rate (Mbps)": "Receive Rate (Mbps)", "Transmit rate (Mbps)": "Transmit Rate (Mbps)", "Signal": "Signal"}


def parse_kv_text(text: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key and key not in out:
            out[key] = value
    return out


def winhttp_summary(text: str) -> str:
    t = text or ""
    if "Direct access" in t:
        return "Direct access (no proxy server)"
    m = re.search(r"Proxy Server\(s\)\s*:\s*(.+)", t)
    if m:
        bypass = re.search(r"Bypass List\s*:\s*(.+)", t)
        return f"{m.group(1).strip()}" + (f" (bypass: {bypass.group(1).strip()})" if bypass else "")
    return t.strip().splitlines()[-1].strip() if t.strip() else ""


def build(cs, ipc, wmi, routes, proxy, winhttp_text, wlan_text) -> dict:
    cs, proxy = cs or {}, proxy or {}
    identity = {"Computer Name": cs.get("Name", ""), "DNS Host Name": cs.get("DNSHostName", ""), "Description": cs.get("Description") or "",
                "Domain Name": cs.get("Domain", "") if cs.get("PartOfDomain") else "", "Workgroup": cs.get("Workgroup") or ("" if cs.get("PartOfDomain") else cs.get("Domain", "")),
                "Part of Domain": yes_no(cs.get("PartOfDomain")), "Role": decode.lookup(decode.DOMAIN_ROLES, cs.get("DomainRole"))}
    wmi_by = {decode.to_int(w.get("InterfaceIndex")): w for w in rows_of(wmi)}
    interfaces = []
    for i in rows_of(ipc):
        w = wmi_by.get(decode.to_int(i.get("InterfaceIndex")), {})
        link = {"Description": i.get("InterfaceDescription", ""), "Interface Index": i.get("InterfaceIndex", ""), "Status": i.get("Status", ""),
                "MAC Address": i.get("MacAddress", ""), "Link Speed": i.get("LinkSpeed", ""),
                "Network Profile": f"{i.get('NetProfileName', '')} ({i.get('NetProfileCategory', '')})" if i.get("NetProfileName") else "",
                "IPv4 Connectivity": i.get("IPv4Connectivity", ""), "IPv6 Connectivity": i.get("IPv6Connectivity", "")}
        addressing = {"IPv4 Address": as_list(i.get("IPv4Address")), "IPv6 Address": as_list(i.get("IPv6Address")),
                      "Default Gateway": as_list(i.get("IPv4DefaultGateway")) + as_list(i.get("IPv6DefaultGateway")),
                      "DNS Servers": as_list(i.get("DNSServer")), "DNS Suffix": w.get("DNSDomain") or "",
                      "DNS Suffix Search Order": as_list(w.get("DNSDomainSuffixSearchOrder")),
                      "Interface Metric": w.get("IPConnectionMetric", "")}
        dhcp = {"DHCP Enabled": yes_no(w.get("DHCPEnabled")) if w else "", "DHCP Server": w.get("DHCPServer") or "",
                "Lease Obtained": fmt_datetime(w.get("DHCPLeaseObtained")) if w.get("DHCPLeaseObtained") else "",
                "Lease Expires": fmt_datetime(w.get("DHCPLeaseExpires")) if w.get("DHCPLeaseExpires") else "",
                "WINS Servers": [s for s in (w.get("WINSPrimaryServer"), w.get("WINSSecondaryServer")) if s],
                "NetBIOS over TCP/IP": decode.lookup(NETBIOS, w.get("TcpipNetbiosOptions")) if w else ""}
        interfaces.append({"name": i.get("InterfaceAlias", ""), "groups": [{"title": "Link", "rows": link}, {"title": "Addressing", "rows": addressing},
                                                                          {"title": "DHCP and Name Resolution", "rows": dhcp}]})
    proxies = {"User Proxy": ("Enabled: " + str(proxy.get("ProxyServer") or "")) if decode.to_int(proxy.get("ProxyEnable")) else "Disabled",
               "Proxy Bypass": proxy.get("ProxyOverride") or "", "Auto-config URL": proxy.get("AutoConfigURL") or "",
               "WinHTTP Proxy": winhttp_summary(winhttp_text)}
    route_rows = [{"Interface": r.get("InterfaceAlias", ""), "Destination": r.get("DestinationPrefix", ""), "Next Hop": r.get("NextHop", ""),
                   "Route Metric": r.get("RouteMetric", ""), "Interface Metric": r.get("InterfaceMetric", ""),
                   "Family": "IPv6" if decode.to_int(r.get("AddressFamily")) == 23 else "IPv4"} for r in rows_of(routes)]
    wl = parse_kv_text(wlan_text)
    wifi = {label: wl[key] for key, label in WLAN_KEYS.items() if key in wl}
    if not wifi:
        wifi = {"Wi-Fi": "No wireless interface" if "no wireless interface" in (wlan_text or "").lower() or not wlan_text else (wlan_text or "").strip().splitlines()[0]}
    return {"groups": [{"title": "Identity", "rows": identity}, {"title": "Proxy", "rows": proxies}, {"title": "Wi-Fi", "rows": wifi}],
            "interfaces": interfaces, "routes": route_rows}


def collect(ctx):
    return build(first_dict(ctx.query("computer", CS_SCRIPT)), ctx.query("ip_configuration", IPC_SCRIPT, timeout=45),
                 ctx.query("wmi_configuration", WMI_SCRIPT), ctx.query("routes", ROUTES_SCRIPT),
                 first_dict(ctx.query("proxy", PROXY_SCRIPT)), ctx.text("winhttp_proxy", WINHTTP_ARGS), ctx.text("wlan", WLAN_ARGS))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    interfaces = rows_of(data.get("interfaces"))
    if not interfaces:
        out.append(sub_heading("Interfaces") + list_table([("Name", "Name")], []))
    for i in interfaces:
        out.append(sub_heading(i.get("name", "")) + kv_groups(i.get("groups")))
    out.append(sub_heading("Default routes") + list_table(ROUTE_COLUMNS, data.get("routes")))
    return "".join(out)


SECTION = Section(key="network_information", title="Network Information", group="Network", collect=collect, render=render, timeout=45)
```

Redaction check for this section's labels: `Computer Name`, `DNS Host Name` (hostname), `Domain Name`, `MAC Address`, `IPv4 Address`, `IPv6 Address`, `Default Gateway`, `DNS Servers`, `DHCP Server`, `WINS Servers`, `Next Hop`, `SSID`, `BSSID` (contains "ssid") are all masked. `Network Profile` and `DNS Suffix` are not — they can carry the domain; add `dnssuffix` and `networkprofile` to `SENSITIVE_TOKENS` in `pc_report/privacy.py` in this task (one-line change) and add a line to `tests/test_pc_report_privacy.py`:

```python
    def test_dns_suffix_and_network_profile_are_masked(self):
        out = redact_payload({"DNS Suffix": "lab.example.org", "Network Profile": "lab.example.org (Domain)"}, {"redact": True})
        self.assertNotIn("example", out["DNS Suffix"])
        self.assertNotIn("example", out["Network Profile"])
```

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Network Information with per-interface IP/DHCP/DNS, routes, proxies and Wi-Fi`

---

### Task 27: Shares and Network Connections

**Files:**
- Create: `pc_report/sections/shares.py`, `pc_report/sections/network_connections.py`
- Test: `tests/pc_report/test_shares.py`, `tests/pc_report/test_network_connections.py`
- Fixtures: `shares/{shares,access,client}.json` (+ `server.json` elevated), `network_connections/{mapped,smb_mappings,vpn,tcp,udp,processes}.json`

- [ ] **Step 1: Tests**

`tests/pc_report/test_shares.py`:

```python
import unittest

from pc_report.section import REQUIRES_ADMIN
from pc_report.sections import shares as mod
from tests.pc_report import support

SH = [{"Name": "Data", "Path": "D:\\Data", "Description": "Lab data", "ShareType": 0, "ShareState": 1, "CurrentUsers": 2, "CachingMode": 0,
       "EncryptData": False, "FolderEnumerationMode": 0, "Special": False},
      {"Name": "ADMIN$", "Path": "C:\\Windows", "Description": "Remote Admin", "ShareType": 0, "ShareState": 1, "CurrentUsers": 0, "CachingMode": 0,
       "EncryptData": False, "FolderEnumerationMode": 0, "Special": True}]
ACC = [{"Name": "Data", "AccountName": "LAB\\Researchers", "AccessControlType": 0, "AccessRight": 1}]
CLIENT = {"EnableInsecureGuestLogons": False, "RequireSecuritySignature": False, "EnableSecuritySignature": True, "EnableMultiChannel": True, "SMB1": None}
SERVER = {"EnableSMB1Protocol": False, "EnableSMB2Protocol": True, "RequireSecuritySignature": False, "EnableSecuritySignature": False,
          "AutoShareServer": True, "AutoShareWorkstation": True}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(SH, ACC, CLIENT, SERVER)
        d = data["rows"][0]
        self.assertEqual(d["Type"], "Disk")
        self.assertEqual(d["State"], "Online")
        self.assertEqual(d["Special"], "No")
        self.assertEqual(data["access"][0]["Right"], "Change")
        self.assertEqual(data["access"][0]["Control"], "Allow")
        rows = mod.flatten(data)
        self.assertEqual(rows["Insecure Guest Logons"], "No")
        self.assertEqual(rows["SMB1 Protocol (server)"], "No")
        self.assertEqual(dict(data["groups"][0]["rows"])["Shares"], 2)

    def test_server_requires_admin(self):
        rows = mod.flatten(mod.build(SH, ACC, CLIENT, REQUIRES_ADMIN))
        self.assertEqual(rows["Server Configuration"], REQUIRES_ADMIN)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Share permissions</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

`tests/pc_report/test_network_connections.py`:

```python
import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import network_connections as mod
from tests.pc_report import support

MAPPED = [{"Name": "Z:", "ProviderName": "\\\\server\\share", "FileSystem": "NTFS", "Size": 2000000000000, "FreeSpace": 1000000000000, "VolumeName": "share"}]
SMB = [{"LocalPath": "Z:", "RemotePath": "\\\\server\\share", "Status": "OK"}]
VPN = [{"Name": "Office", "ServerAddress": "vpn.example.org", "ConnectionStatus": "Disconnected", "TunnelType": "Automatic", "AuthenticationMethod": ["Eap"], "SplitTunneling": False}]
TCP = [{"LocalAddress": "0.0.0.0", "LocalPort": 135, "RemoteAddress": "0.0.0.0", "RemotePort": 0, "State": "Listen", "OwningProcess": 1000},
       {"LocalAddress": "192.168.10.55", "LocalPort": 51000, "RemoteAddress": "52.1.2.3", "RemotePort": 443, "State": "Established", "OwningProcess": 2000}]
UDP = [{"LocalAddress": "0.0.0.0", "LocalPort": 5353, "OwningProcess": 3000}]
PROCS = [{"Id": 1000, "ProcessName": "svchost"}, {"Id": 2000, "ProcessName": "msedge"}, {"Id": 3000, "ProcessName": "svchost"}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(MAPPED, SMB, VPN, TCP, UDP, PROCS)

    def test_tables(self):
        self.assertEqual(self.data["mapped"][0]["Remote Path (host name)"], "\\\\server\\share")
        self.assertEqual(self.data["mapped"][0]["Free"], "931.3 GB")
        self.assertEqual(self.data["vpn"][0]["Server (host name)"], "vpn.example.org")
        self.assertEqual(self.data["listening"][0]["Process"], "svchost (1000)")
        self.assertEqual(self.data["established"][0]["Remote Address"], "52.1.2.3")
        self.assertEqual(self.data["udp"][0]["Local Port"], 5353)
        rows = dict(self.data["groups"][0]["rows"])
        self.assertEqual(rows["Listening TCP Ports"], 1)
        self.assertEqual(rows["Established TCP Connections"], 1)

    def test_redaction(self):
        red = redact_payload(self.data, {"redact": True})
        self.assertEqual(red["established"][0]["Remote Address"], "52.1.*.*")
        self.assertEqual(red["listening"][0]["Local Address"], "0.0.0.0")
        self.assertNotIn("server", red["mapped"][0]["Remote Path (host name)"])
        self.assertNotIn("example", red["vpn"][0]["Server (host name)"])


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<h3>Listening TCP ports</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Modules**

`pc_report/sections/shares.py`:

```python
"""Shares: SMB shares with permissions, client configuration, server configuration (admin)."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..section import REQUIRES_ADMIN, Section, first_dict, kv_groups, list_table, rows_of, sub_heading

SHARES_SCRIPT = ("Get-SmbShare -ErrorAction SilentlyContinue | Select-Object Name,Path,Description,ShareType,ShareState,CurrentUsers,"
                 "CachingMode,EncryptData,FolderEnumerationMode,Special")
ACCESS_SCRIPT = ("Get-SmbShare -ErrorAction SilentlyContinue | Get-SmbShareAccess -ErrorAction SilentlyContinue | Select-Object Name,"
                 "AccountName,AccessControlType,AccessRight")
CLIENT_SCRIPT = ("$c = Get-SmbClientConfiguration -ErrorAction SilentlyContinue; "
                 "[pscustomobject]@{ EnableInsecureGuestLogons = $c.EnableInsecureGuestLogons; RequireSecuritySignature = $c.RequireSecuritySignature; "
                 "EnableSecuritySignature = $c.EnableSecuritySignature; EnableMultiChannel = $c.EnableMultiChannel; "
                 "SMB1 = (Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Parameters' -ErrorAction SilentlyContinue).SMB1 }")
SERVER_SCRIPT = ("Get-SmbServerConfiguration -ErrorAction SilentlyContinue | Select-Object EnableSMB1Protocol,EnableSMB2Protocol,"
                 "RequireSecuritySignature,EnableSecuritySignature,AutoShareServer,AutoShareWorkstation")

SHARE_TYPE = {0: "Disk", 1: "Print queue", 2: "Device", 3: "IPC", 2147483648: "Disk (admin)", 2147483649: "Print queue (admin)",
              2147483650: "Device (admin)", 2147483651: "IPC (admin)"}
SHARE_STATE = {0: "Pending", 1: "Online", 2: "Offline"}
CACHING = {0: "Manual", 1: "Documents", 2: "Programs", 3: "None", 4: "BranchCache", 5: "Unknown"}
CONTROL = {0: "Allow", 1: "Deny"}
RIGHT = {0: "Full", 1: "Change", 2: "Read", 3: "Custom"}
COLUMNS = [("Name", "Name"), ("Path", "Path"), ("Description", "Description"), ("Type", "Type"), ("State", "State"),
           ("Current Users", "Current Users"), ("Caching", "Caching"), ("Encrypted", "Encrypted"), ("Special", "Special")]
ACCESS_COLUMNS = [("Share", "Share"), ("Account Name", "Account"), ("Control", "Control"), ("Right", "Right")]


def build(shares, access, client, server) -> dict:
    client = client or {}
    rows = [{"Name": s.get("Name", ""), "Path": s.get("Path") or "", "Description": s.get("Description") or "",
             "Type": decode.lookup(SHARE_TYPE, s.get("ShareType")), "State": decode.lookup(SHARE_STATE, s.get("ShareState")),
             "Current Users": s.get("CurrentUsers", ""), "Caching": decode.lookup(CACHING, s.get("CachingMode")),
             "Encrypted": yes_no(s.get("EncryptData")), "Special": yes_no(s.get("Special"))} for s in rows_of(shares)]
    acc = [{"Share": a.get("Name", ""), "Account Name": a.get("AccountName", ""), "Control": decode.lookup(CONTROL, a.get("AccessControlType")),
            "Right": decode.lookup(RIGHT, a.get("AccessRight"))} for a in rows_of(access)]
    client_rows = {"Insecure Guest Logons": yes_no(client.get("EnableInsecureGuestLogons")),
                   "Signing Required (client)": yes_no(client.get("RequireSecuritySignature")),
                   "Signing Enabled (client)": yes_no(client.get("EnableSecuritySignature")),
                   "Multichannel": yes_no(client.get("EnableMultiChannel")),
                   "SMB1 Registry Override": "" if client.get("SMB1") is None else yes_no(client.get("SMB1"))} if client else {"Client Configuration": "Not available"}
    if server == REQUIRES_ADMIN:
        server_rows = {"Server Configuration": REQUIRES_ADMIN}
    else:
        sv = first_dict(server) if not isinstance(server, dict) else server
        server_rows = {"SMB1 Protocol (server)": yes_no(sv.get("EnableSMB1Protocol")), "SMB2/3 Protocol (server)": yes_no(sv.get("EnableSMB2Protocol")),
                       "Signing Required (server)": yes_no(sv.get("RequireSecuritySignature")),
                       "Administrative Shares (server)": yes_no(sv.get("AutoShareServer")),
                       "Administrative Shares (workstation)": yes_no(sv.get("AutoShareWorkstation"))} if sv else {"Server Configuration": "Not available"}
    summary = {"Shares": len(rows), "User Shares": sum(1 for r in rows if r["Special"] == "No"),
               "Administrative Shares": sum(1 for r in rows if r["Special"] == "Yes"),
               "Connected Users": sum(decode.to_int(r["Current Users"]) or 0 for r in rows)}
    return {"groups": [{"title": "Summary", "rows": summary}, {"title": "SMB Client", "rows": client_rows},
                       {"title": "SMB Server", "rows": server_rows}], "rows": rows, "access": acc}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(ctx.query("shares", SHARES_SCRIPT, timeout=30), ctx.query("access", ACCESS_SCRIPT, timeout=30),
                 first_dict(ctx.query("client", CLIENT_SCRIPT)), ctx.admin_query("server", SERVER_SCRIPT, timeout=30))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Shares") + list_table(COLUMNS, data.get("rows"))
            + sub_heading("Share permissions") + list_table(ACCESS_COLUMNS, data.get("access")))


SECTION = Section(key="shares", title="Shares", group="Network", collect=collect, render=render, timeout=30)
```

`pc_report/sections/network_connections.py`:

```python
"""Network Connections: mapped drives, SMB mappings, VPN profiles, TCP listeners/connections and UDP endpoints."""
from __future__ import annotations

from .. import decode
from ..format import bytes_human, yes_no
from ..ps import cim
from ..section import Section, as_list, kv_groups, list_table, rows_of, sub_heading

MAPPED_SCRIPT = cim("Win32_MappedLogicalDisk", ("Name", "ProviderName", "FileSystem", "Size", "FreeSpace", "VolumeName"))
SMB_SCRIPT = "Get-SmbMapping -ErrorAction SilentlyContinue | Select-Object LocalPath,RemotePath,Status"
VPN_SCRIPT = ("Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object Name,ServerAddress,ConnectionStatus,TunnelType,"
              "AuthenticationMethod,SplitTunneling")
TCP_SCRIPT = ("Get-NetTCPConnection -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,"
              "State,OwningProcess")
UDP_SCRIPT = "Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess"
PROCS_SCRIPT = "Get-Process -ErrorAction SilentlyContinue | Select-Object Id,ProcessName"

MAPPED_COLUMNS = [("Drive", "Drive"), ("Remote Path (host name)", "Remote Path"), ("Label", "Label"), ("File System", "File System"),
                  ("Total", "Total"), ("Free", "Free"), ("Status", "Status")]
VPN_COLUMNS = [("Name", "Name"), ("Server (host name)", "Server"), ("Status", "Status"), ("Tunnel", "Tunnel"), ("Authentication", "Authentication"),
               ("Split Tunneling", "Split Tunneling")]
TCP_COLUMNS = [("Local Address", "Local Address"), ("Local Port", "Local Port"), ("Remote Address", "Remote Address"), ("Remote Port", "Remote Port"),
               ("State", "State"), ("Process", "Process")]
UDP_COLUMNS = [("Local Address", "Local Address"), ("Local Port", "Local Port"), ("Process", "Process")]
TCP_STATE = {1: "Closed", 2: "Listen", 3: "SynSent", 4: "SynReceived", 5: "Established", 6: "FinWait1", 7: "FinWait2", 8: "CloseWait",
             9: "Closing", 10: "LastAck", 11: "TimeWait", 12: "DeleteTCB", 100: "Bound"}


def _state(value) -> str:
    return decode.lookup(TCP_STATE, value) if decode.to_int(value) is not None else str(value or "")


def build(mapped, smb, vpn, tcp, udp, procs) -> dict:
    names = {decode.to_int(p.get("Id")): p.get("ProcessName", "") for p in rows_of(procs)}
    smb_by = {str(m.get("LocalPath") or "").upper(): m for m in rows_of(smb)}

    def proc(pid):
        n = decode.to_int(pid)
        return f"{names.get(n, 'unknown')} ({n})" if n is not None else ""

    mapped_rows = []
    seen = set()
    for m in rows_of(mapped):
        drive = str(m.get("Name") or "").upper()
        seen.add(drive)
        s = smb_by.get(drive, {})
        mapped_rows.append({"Drive": drive, "Remote Path (host name)": m.get("ProviderName") or s.get("RemotePath", ""),
                            "Label": m.get("VolumeName") or "", "File System": m.get("FileSystem") or "",
                            "Total": bytes_human(m.get("Size")) if m.get("Size") else "", "Free": bytes_human(m.get("FreeSpace")) if m.get("FreeSpace") else "",
                            "Status": s.get("Status", "")})
    for drive, s in smb_by.items():
        if drive not in seen:
            mapped_rows.append({"Drive": drive, "Remote Path (host name)": s.get("RemotePath", ""), "Label": "", "File System": "",
                                "Total": "", "Free": "", "Status": s.get("Status", "")})
    vpn_rows = [{"Name": v.get("Name", ""), "Server (host name)": v.get("ServerAddress", ""), "Status": v.get("ConnectionStatus", ""),
                 "Tunnel": v.get("TunnelType", ""), "Authentication": ", ".join(str(a) for a in as_list(v.get("AuthenticationMethod"))),
                 "Split Tunneling": yes_no(v.get("SplitTunneling"))} for v in rows_of(vpn)]
    tcp_rows = [{"Local Address": t.get("LocalAddress", ""), "Local Port": t.get("LocalPort"), "Remote Address": t.get("RemoteAddress", ""),
                 "Remote Port": t.get("RemotePort"), "State": _state(t.get("State")), "Process": proc(t.get("OwningProcess"))} for t in rows_of(tcp)]
    listening = sorted([r for r in tcp_rows if r["State"] == "Listen"], key=lambda r: (decode.to_int(r["Local Port"]) or 0, str(r["Local Address"])))
    established = sorted([r for r in tcp_rows if r["State"] == "Established"], key=lambda r: (str(r["Process"]), decode.to_int(r["Remote Port"]) or 0))
    other = [r for r in tcp_rows if r["State"] not in ("Listen", "Established")]
    udp_rows = sorted([{"Local Address": u.get("LocalAddress", ""), "Local Port": u.get("LocalPort"), "Process": proc(u.get("OwningProcess"))}
                       for u in rows_of(udp)], key=lambda r: (decode.to_int(r["Local Port"]) or 0, str(r["Local Address"])))
    summary = {"Mapped Drives": len(mapped_rows), "VPN Profiles": len(vpn_rows), "Listening TCP Ports": len(listening),
               "Established TCP Connections": len(established), "Other TCP States": len(other), "UDP Endpoints": len(udp_rows)}
    return {"groups": [{"title": "Summary", "rows": summary}], "mapped": mapped_rows, "vpn": vpn_rows,
            "listening": listening, "established": established, "other": other, "udp": udp_rows}


def collect(ctx):
    return build(ctx.query("mapped", MAPPED_SCRIPT), ctx.query("smb_mappings", SMB_SCRIPT), ctx.query("vpn", VPN_SCRIPT),
                 ctx.query("tcp", TCP_SCRIPT, timeout=30), ctx.query("udp", UDP_SCRIPT, timeout=30), ctx.query("processes", PROCS_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("Mapped drives") + list_table(MAPPED_COLUMNS, data.get("mapped"))
            + sub_heading("VPN profiles") + list_table(VPN_COLUMNS, data.get("vpn"))
            + sub_heading("Listening TCP ports") + list_table(TCP_COLUMNS, data.get("listening"))
            + sub_heading("Established TCP connections") + list_table(TCP_COLUMNS, data.get("established"))
            + sub_heading("Other TCP states") + list_table(TCP_COLUMNS, data.get("other"))
            + sub_heading("UDP endpoints") + list_table(UDP_COLUMNS, data.get("udp")))


SECTION = Section(key="network_connections", title="Network Connections", group="Network", collect=collect, render=render, timeout=30)
```

The VPN server key is `"Server (host name)"` rather than `"Server Address"` on purpose: `serveraddress` is an IP token (two-octet masking, host names untouched) whereas `hostname` masks the string.

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): Shares with permissions and SMB configuration; Network Connections with TCP/UDP tables`

### Task 28: System Summary

**Files:**
- Create: `pc_report/sections/system_summary.py`
- Test: `tests/pc_report/test_system_summary.py`
- Fixtures: `system_summary/{computer,product,enclosure,pagefile_usage,pagefile_setting,winsat,power_scheme.txt}`

**Interfaces:** `after=("operating_system", "cpu", "memory", "video", "logical_disks", "motherboard", "bios")`; reads those results through each module's `flatten`/`names`/`rows`. `build(cs, csp, enclosure, pf_usage, pf_setting, winsat, power_text, results) -> {"groups": [...], "drives": [...]}` where `results` is a dict of `key -> section data` (already unwrapped).

- [ ] **Step 1: Test `tests/pc_report/test_system_summary.py`**

```python
import unittest

from pc_report.sections import system_summary as mod
from tests.pc_report import support

CS = {"Manufacturer": "Dell Inc.", "Model": "Precision 3660", "SystemFamily": "Precision", "SystemSKUNumber": "0ABC", "Name": "PC-NAME", "Domain": "lab.example.org",
      "PartOfDomain": True, "DomainRole": 1, "Workgroup": None, "PCSystemType": 1, "TotalPhysicalMemory": 34158411776, "UserName": "LAB\\user",
      "NumberOfProcessors": 1, "NumberOfLogicalProcessors": 20, "HypervisorPresent": True, "BootupState": "Normal boot", "PowerSupplyState": 3,
      "ThermalState": 3, "Description": ""}
CSP = {"Name": "Precision 3660", "Vendor": "Dell Inc.", "Version": "1.0", "IdentifyingNumber": "ABC1234", "UUID": "4C4C4544-0000-1010-8020-B1C04F123456", "SKUNumber": "0ABC"}
ENC = [{"ChassisTypes": [3], "SerialNumber": "ABC1234", "SMBIOSAssetTag": "", "Manufacturer": "Dell Inc.", "LockPresent": False}]
PFU = [{"Name": "C:\\pagefile.sys", "AllocatedBaseSize": 4864, "CurrentUsage": 120, "PeakUsage": 300}]
PFS = []
WINSAT = {"CPUScore": 9.1, "D3DScore": 9.9, "DiskScore": 9.2, "GraphicsScore": 9.0, "MemoryScore": 9.1, "WinSPRLevel": 9.0, "WinSATAssessmentState": 1}
POWER = "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)\n"
RESULTS = {
    "operating_system": {"groups": [{"title": "Windows", "rows": {"Name": "Microsoft Windows 11 Enterprise", "Version": "24H2 (OS Build 26100.9445)", "Kernel Version": "10.0.26100.9444"}},
                                    {"title": "Boot", "rows": {"Boot Time": "2026-09-22 08:00", "Up Time": "2 days, 1 hour, 5 minutes", "Firmware Type": "UEFI"}},
                                    {"title": "Security and Policies", "rows": {"Secure Boot": "Yes"}}]},
    "cpu": {"groups": [{"title": "Processor", "rows": {"Name": "12th Gen Intel(R) Core(TM) i7-12700"}}, {"title": "Topology and Clocks", "rows": {"Cores / Threads": "12 / 20", "Max Clock": "2100 MHz"}},
                       {"title": "Load", "rows": {"Load": "7 %"}}]},
    "memory": {"groups": [{"title": "Summary", "rows": {"Installed Memory": "32.0 GB", "Memory Type": "DDR4"}},
                          {"title": "Operating System View", "rows": {"Total Physical": "31.8 GB", "Free Physical": "19.1 GB", "Memory Load": "40.0 %", "Committed": "14.0 GB of 36.2 GB", "Total Virtual": "36.2 GB", "Free Virtual": "22.9 GB"}}]},
    "video": {"adapters": [{"name": "NVIDIA GeForce RTX 3060", "groups": []}]},
    "logical_disks": {"rows": [{"Drive": "C:", "Label": "Windows", "Total": "929.5 GB", "Free": "45.6 GB", "Free %": "⚠ 4.9 %", "Type": "Local disk"}]},
    "motherboard": {"groups": [{"title": "Board", "rows": {"Manufacturer": "Dell Inc.", "Model": "0ABC12"}}]},
    "bios": {"groups": [{"title": "BIOS", "rows": {"Vendor": "Dell Inc.", "Version": "DELL - 1", "SMBIOS BIOS Version": "1.2.3", "Release Date": "2025-01-10"}}]},
}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(CS, CSP, ENC, PFU, PFS, WINSAT, POWER, RESULTS)
        self.rows = mod.flatten(self.data)

    def test_identity(self):
        self.assertEqual(self.rows["Manufacturer"], "Dell Inc.")
        self.assertEqual(self.rows["Model"], "Precision 3660")
        self.assertEqual(self.rows["Chassis Type"], "Desktop")
        self.assertEqual(self.rows["PC System Type"], "Desktop")
        self.assertEqual(self.rows["UUID"], "4C4C4544-0000-1010-8020-B1C04F123456")
        self.assertEqual(self.rows["Role"], "Member Workstation")
        self.assertEqual(self.rows["User Name"], "LAB\\user")

    def test_cross_section_rows(self):
        self.assertEqual(self.rows["Operating System"], "Microsoft Windows 11 Enterprise, 24H2 (OS Build 26100.9445)")
        self.assertEqual(self.rows["Processor"], "12th Gen Intel(R) Core(TM) i7-12700 (12 / 20 cores / threads, 2100 MHz)")
        self.assertEqual(self.rows["Physical Memory"], "31.8 GB total, 19.1 GB free (40.0 % load)")
        self.assertEqual(self.rows["Video Adapters"], "NVIDIA GeForce RTX 3060")
        self.assertEqual(self.rows["Motherboard"], "Dell Inc. 0ABC12")
        self.assertEqual(self.rows["BIOS"], "Dell Inc. 1.2.3 (2025-01-10)")
        self.assertEqual(self.rows["Up Time"], "2 days, 1 hour, 5 minutes")

    def test_pagefile_power_winsat(self):
        self.assertEqual(self.rows["Page File"], "C:\\pagefile.sys: 4.8 GB allocated, 120.0 MB in use, 300.0 MB peak")
        self.assertEqual(self.rows["Page File Management"], "Automatic (system managed)")
        self.assertEqual(self.rows["Active Power Plan"], "Balanced")
        self.assertEqual(self.rows["Windows Experience Index (base)"], "9.0")
        self.assertEqual(self.data["drives"][0]["Drive"], "C:")

    def test_missing_results(self):
        rows = mod.flatten(mod.build({}, {}, [], [], [], {}, "", {}))
        self.assertEqual(rows["Operating System"], "")
        self.assertEqual(rows["Active Power Plan"], "")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        results = {k: {"data": v, "notes": []} for k, v in RESULTS.items()}
        _data, html, ctx = support.collect_and_render(mod.SECTION, results=results)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        for label in ("Manufacturer", "Operating System", "Processor", "Physical Memory", "Active Power Plan"):
            self.assertIn(f"<th>{label}</th>", html, label)
        self.assertIn("<h3>Drives</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 2: Module `pc_report/sections/system_summary.py`**

```python
"""System Summary: the one-page overview, combining identity queries with the detailed sections' results."""
from __future__ import annotations

import re

from .. import decode
from ..format import bytes_human, yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

CS_SCRIPT = cim("Win32_ComputerSystem", ("Manufacturer", "Model", "SystemFamily", "SystemSKUNumber", "Name", "Domain", "PartOfDomain",
                                         "DomainRole", "Workgroup", "PCSystemType", "TotalPhysicalMemory", "UserName", "NumberOfProcessors",
                                         "NumberOfLogicalProcessors", "HypervisorPresent", "BootupState", "PowerSupplyState", "ThermalState",
                                         "Description"))
CSP_SCRIPT = cim("Win32_ComputerSystemProduct", ("Name", "Vendor", "Version", "IdentifyingNumber", "UUID", "SKUNumber"))
ENCLOSURE_SCRIPT = cim("Win32_SystemEnclosure", ("ChassisTypes", "SerialNumber", "SMBIOSAssetTag", "Manufacturer", "LockPresent"))
PF_USAGE_SCRIPT = cim("Win32_PageFileUsage", ("Name", "AllocatedBaseSize", "CurrentUsage", "PeakUsage"))
PF_SETTING_SCRIPT = cim("Win32_PageFileSetting", ("Name", "InitialSize", "MaximumSize"))
WINSAT_SCRIPT = cim("Win32_WinSAT", ("CPUScore", "D3DScore", "DiskScore", "GraphicsScore", "MemoryScore", "WinSPRLevel", "WinSATAssessmentState"))
POWER_ARGS = ["powercfg", "/getactivescheme"]

STATE = {1: "Other", 2: "Unknown", 3: "Safe", 4: "Warning", 5: "Critical", 6: "Non-recoverable"}
DRIVE_COLUMNS = [("Drive", "Drive"), ("Label", "Label"), ("Type", "Type"), ("Total", "Total"), ("Free", "Free"), ("Free %", "Free %")]
_PLAN = re.compile(r"\(([^)]+)\)\s*$", re.M)


def _flat(data) -> dict:
    out = {}
    if isinstance(data, dict):
        for g in rows_of(data.get("groups")):
            out.update(g.get("rows") or {})
    return out


def _mb(value):
    n = decode.to_int(value)
    return bytes_human(n * 1024 * 1024) if n is not None else ""


def build(cs, csp, enclosure, pf_usage, pf_setting, winsat, power_text, results) -> dict:
    cs, csp, winsat, results = cs or {}, csp or {}, winsat or {}, results or {}
    enc = first_dict(enclosure)
    os_, cpu, mem = _flat(results.get("operating_system")), _flat(results.get("cpu")), _flat(results.get("memory"))
    board, bios = _flat(results.get("motherboard")), _flat(results.get("bios"))
    video_names = [a.get("name", "") for a in rows_of((results.get("video") or {}).get("adapters") if isinstance(results.get("video"), dict) else None)]
    drives = [{k: r.get(k, "") for k, _l in DRIVE_COLUMNS} for r in rows_of((results.get("logical_disks") or {}).get("rows") if isinstance(results.get("logical_disks"), dict) else None)]

    identity = {
        "Manufacturer": cs.get("Manufacturer") or csp.get("Vendor", ""), "Model": cs.get("Model") or csp.get("Name", ""),
        "System Family": cs.get("SystemFamily", ""), "Product Version": csp.get("Version", ""), "SKU": cs.get("SystemSKUNumber") or csp.get("SKUNumber", ""),
        "Serial Number": csp.get("IdentifyingNumber") or enc.get("SerialNumber", ""), "UUID": csp.get("UUID", ""),
        "Asset Tag": enc.get("SMBIOSAssetTag", ""), "Chassis Type": decode.lookup(decode.CHASSIS_TYPES, enc.get("ChassisTypes")),
        "PC System Type": decode.lookup(decode.PC_SYSTEM_TYPES, cs.get("PCSystemType")), "Chassis Lock": yes_no(enc.get("LockPresent")),
        "Computer Name": cs.get("Name", ""), "Computer Description": cs.get("Description") or "",
        "Domain Name": cs.get("Domain", "") if cs.get("PartOfDomain") else "", "Workgroup": "" if cs.get("PartOfDomain") else cs.get("Domain") or cs.get("Workgroup") or "",
        "Role": decode.lookup(decode.DOMAIN_ROLES, cs.get("DomainRole")), "User Name": cs.get("UserName", ""),
        "Boot State": cs.get("BootupState", ""), "Power Supply State": decode.lookup(STATE, cs.get("PowerSupplyState")),
        "Thermal State": decode.lookup(STATE, cs.get("ThermalState")), "Hypervisor Present": yes_no(cs.get("HypervisorPresent")),
    }
    os_line = ", ".join(x for x in (os_.get("Name", ""), os_.get("Version", "")) if x)
    cpu_line = cpu.get("Name", "")
    if cpu_line and (cpu.get("Cores / Threads") or cpu.get("Max Clock")):
        cpu_line += f" ({cpu.get('Cores / Threads', '')} cores / threads, {cpu.get('Max Clock', '')})"
    mem_line = ""
    if mem.get("Total Physical"):
        mem_line = f"{mem['Total Physical']} total, {mem.get('Free Physical', '')} free ({mem.get('Memory Load', '')} load)"
    overview = {
        "Operating System": os_line, "Kernel Version": os_.get("Kernel Version", ""), "Firmware Type": os_.get("Firmware Type", ""),
        "Secure Boot": os_.get("Secure Boot", ""), "Boot Time": os_.get("Boot Time", ""), "Up Time": os_.get("Up Time", ""),
        "Processor": cpu_line, "Processor Load": cpu.get("Load", ""), "Processors / Logical": f"{cs.get('NumberOfProcessors', '')} / {cs.get('NumberOfLogicalProcessors', '')}" if cs else "",
        "Installed Memory": mem.get("Installed Memory", "") or (bytes_human(cs["TotalPhysicalMemory"]) if cs.get("TotalPhysicalMemory") else ""),
        "Memory Type": mem.get("Memory Type", ""), "Physical Memory": mem_line,
        "Virtual Memory": f"{mem.get('Total Virtual', '')} total, {mem.get('Free Virtual', '')} free" if mem.get("Total Virtual") else "",
        "Committed": mem.get("Committed", ""), "Video Adapters": ", ".join(v for v in video_names if v),
        "Motherboard": " ".join(x for x in (board.get("Manufacturer", ""), board.get("Model", "")) if x),
        "BIOS": " ".join(x for x in (bios.get("Vendor", ""), bios.get("SMBIOS BIOS Version") or bios.get("Version", ""),
                                     f"({bios['Release Date']})" if bios.get("Release Date") else "") if x),
    }
    pf = ["{}: {} allocated, {} in use, {} peak".format(p.get("Name", ""), _mb(p.get("AllocatedBaseSize")), _mb(p.get("CurrentUsage")), _mb(p.get("PeakUsage")))
          for p in rows_of(pf_usage)]
    settings = rows_of(pf_setting)
    plan = _PLAN.search(power_text or "")
    system = {
        "Page File": "; ".join(pf) if pf else ("None" if pf_usage is not None else ""),
        "Page File Management": ("Automatic (system managed)" if not settings else
                                 "; ".join(f"{s.get('Name')}: {s.get('InitialSize')} - {s.get('MaximumSize')} MB" + (" (system managed)" if not s.get("MaximumSize") else "") for s in settings)),
        "Active Power Plan": plan.group(1).strip() if plan else "",
        "Windows Experience Index (base)": f"{winsat.get('WinSPRLevel')}" if winsat.get("WinSPRLevel") else "",
        "WinSAT Scores (CPU / Memory / Disk / Graphics / 3D)": " / ".join(str(winsat.get(k, "")) for k in ("CPUScore", "MemoryScore", "DiskScore", "GraphicsScore", "D3DScore")) if winsat.get("CPUScore") else "",
    }
    return {"groups": [{"title": "Computer", "rows": identity}, {"title": "Overview", "rows": overview}, {"title": "System", "rows": system}],
            "drives": drives}


def flatten(data) -> dict:
    return _flat(data)


def collect(ctx):
    results = {k: ctx.result(k) for k in SECTION.after}
    return build(first_dict(ctx.query("computer", CS_SCRIPT)), first_dict(ctx.query("product", CSP_SCRIPT)),
                 ctx.query("enclosure", ENCLOSURE_SCRIPT), ctx.query("pagefile_usage", PF_USAGE_SCRIPT),
                 ctx.query("pagefile_setting", PF_SETTING_SCRIPT), first_dict(ctx.query("winsat", WINSAT_SCRIPT)),
                 ctx.text("power_scheme", POWER_ARGS), results)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Drives") + list_table(DRIVE_COLUMNS, data.get("drives"))


SECTION = Section(key="system_summary", title="System Summary", group="Hardware", collect=collect, render=render,
                  after=("operating_system", "cpu", "memory", "video", "logical_disks", "motherboard", "bios"))
```

Expected in the test: `4864 MB` → `4.8 GB`; `120 MB` → `120.0 MB`; `300 MB` → `300.0 MB`. `Page File` when `pf_usage` is `[]` yields "None"; when `None` (query failed) yields "".

- [ ] **Step 3: Standard steps 3–5**

Commit message: `feat(pc_report): System Summary combining identity queries with section results`

---

### Task 29: Noldus Summary, `noldus_terms.py`, delete the old collectors

**Files:**
- Create: `pc_report/noldus_terms.py` (moved from `pc_report/collectors.py`)
- Create: `pc_report/sections/noldus_summary.py`
- Move: `tests/test_nvc_collector_helpers.py` → `tests/pc_report/test_noldus_terms.py`
- Create: `tests/pc_report/test_noldus_summary.py`
- Delete: `pc_report/collectors.py`, `pc_report/utils.py`
- Modify: `pc_report/__init__.py` docstring

**Interfaces:** `after=` every section it reads: `operating_system installed_programs drivers codecs environment cameras usb services network_adapters security memory cpu video logical_disks devices system_summary`. Data: `{"attention": [{"Severity", "Item", "Detail"}], "groups": [Specifications, Collection], "software": [...], "drivers": [...], "codecs": [...], "environment": [...], "cameras": [...], "dongles": [...], "gige": [...], "runtimes": [...]}`.

- [ ] **Step 1: Move the helpers**

Create `pc_report/noldus_terms.py` with the following, moved verbatim from `collectors.py` (function bodies unchanged; only `_nvc_filter_roots` is renamed to `nvc_filter_roots`; none of the moved functions use `re`, `datetime`, `logger` or `run_ps_json`, so `os` is the only import):

```python
"""Noldus/NVC vocabulary and file scanners used by the Noldus Summary."""
from __future__ import annotations

import os

NVC_RELATED_TERMS = (
    'noldus', 'ethovision', 'etho vision', 'observer', 'mediarecorder', 'media recorder', 'catwalk',
    'daniovision', 'danioscope', 'ultravox', 'facereader', 'viso', 'basler', 'pylon', 'genicam',
    'gige vision', 'coaxpress', 'camera link', 'euresys', 'leadtools', 'samplegrabber', 'resizer filter',
    'rtsp source', 'tee filter', 'timestamp corrector', 'video mixer', 'hardwareinterface',
    'sentinel hasp', 'sentinel ldk', 'safenet', 'thales', 'hardlock',
)

RUNTIME_TERMS = ('visual c++', 'vc++ redistributable', '.net framework', '.net runtime', '.net desktop runtime',
                 'windows desktop runtime', 'directx', 'intel ipp', 'noldus - ipp', 'leadtools')
```

followed by `_as_list`, `_row_text`, `filter_nvc_related_items`, `normalize_nvc_program_row`, `normalize_logical_disk_rows`, `scan_codec_files`, `scan_nvc_filter_files`, and `nvc_filter_roots` copied from `collectors.py` lines 43–230 (keep their bodies; `nvc_filter_roots` drops the leading underscore). Keep `_uptime_from_last_boot` out — `format.uptime_human` replaced it.

Move `tests/test_nvc_collector_helpers.py` to `tests/pc_report/test_noldus_terms.py` and change its import to `from pc_report.noldus_terms import (...)`. Run: `python -m pytest tests/pc_report/test_noldus_terms.py -q` — passes.

Delete `pc_report/collectors.py` and `pc_report/utils.py`. Run `python -m pytest -q` — everything still passes (nothing imports them after Task 3). Update the `pc_report/__init__.py` docstring:

```python
"""PC Report engine.

- registry / sections: one module per report section (collect + render)
- orchestrator.run_all: phased parallel execution with shared sources
- privacy.redact_payload: masking
- render_html / render_json: output
"""
```

Commit: `refactor(pc_report): move Noldus vocabulary to noldus_terms; delete legacy collectors`

- [ ] **Step 2: Test `tests/pc_report/test_noldus_summary.py`**

```python
import unittest

from pc_report.sections import noldus_summary as mod
from tests.pc_report import support

RESULTS = {
    "operating_system": {"groups": [{"title": "Windows", "rows": {"Name": "Windows 11", "Version": "24H2"}},
                                    {"title": "Boot", "rows": {"Pending Reboot": "Yes", "Boot Time": "2026-09-22 08:00", "Up Time": "2 days"}},
                                    {"title": "Security and Policies", "rows": {"UAC Enabled": "No", ".NET Framework 4.x": "4.8.1"}}]},
    "installed_programs": {"rows": [{"Name": "EthoVision XT 19", "Version": "19.0", "Publisher": "Noldus", "Install Date": "2026-05-22", "Install Location": "C:\\EV"},
                                    {"Name": "Microsoft Visual C++ 2015-2022 Redistributable (x64)", "Version": "14.40", "Publisher": "Microsoft", "Install Date": "", "Install Location": ""},
                                    {"Name": "7-Zip", "Version": "23", "Publisher": "Igor Pavlov", "Install Date": "", "Install Location": ""}]},
    "drivers": {"by_class": {"NET": [{"Device": "Basler pylon GigE Filter", "Version": "7.1", "Date": "2024-01-01", "Provider": "Basler AG", "INF": "oem42.inf", "Signed": "Yes"}],
                             "USB": [{"Device": "Sentinel HASP Key", "Version": "8.5", "Date": "2023-01-01", "Provider": "SafeNet", "INF": "oem9.inf", "Signed": "Yes"}]}},
    "codecs": {"categories": {"DirectShow Filters": [{"Name": "Noldus Resizer Filter", "File": "C:\\x\\Resizer.ax", "Version": "1.0", "Company": "Noldus", "Architecture": "x64"}]}},
    "environment": {"Machine": [{"Name": "GENICAM_GENTL64_PATH", "Value": "C:\\Program Files\\Basler\\"}, {"Name": "Path", "Value": "C:\\Windows"}], "User": [], "Process": []},
    "cameras": {"pnp": [{"Name": "Basler ace acA1920", "Class": "Camera", "Status": "OK", "Problem": ""}],
                "groups": [{"title": "Windows Camera Frame Server", "rows": {"Frame Server Mode": "Enabled (shared camera access through Frame Server)"}},
                           {"title": "Camera and Microphone Consent", "rows": {"Camera Access (user)": "Deny"}}]},
    "usb": {"devices": [{"Name": "SafeNet Inc. Sentinel HASP Key", "VID / PID": "0529 / 0001", "Status": "OK", "Present": "Yes"}],
            "groups": [{"title": "Summary", "rows": {"Selective Suspend (AC)": "Enabled", "Selective Suspend (DC)": "Enabled"}}]},
    "services": {"rows": [{"Name": "hasplms", "Display Name": "Sentinel LDK License Manager", "State": "Stopped", "Start Mode": "Automatic"}]},
    "network_adapters": {"gige": [{"Adapter": "Ethernet", "Link Speed": "1 Gbps", "Jumbo Packet": "Disabled", "Receive Buffers": "256"}]},
    "security": {"groups": []},
    "memory": {"groups": [{"title": "Summary", "rows": {"Installed Memory": "32.0 GB"}}]},
    "cpu": {"groups": [{"title": "Processor", "rows": {"Name": "i7-12700"}}]},
    "video": {"adapters": [{"name": "RTX 3060"}]},
    "logical_disks": {"groups": [{"title": "Summary", "rows": {"Low Space (<10 %)": "C:"}}], "rows": []},
    "devices": {"groups": [{"title": "Summary", "rows": {"Problem Devices": 1}}], "problems": [{"Name": "Unknown device", "Problem": "28: Drivers not installed"}]},
    "system_summary": {"groups": [{"title": "Computer", "rows": {"Manufacturer": "Dell Inc.", "Model": "Precision 3660"}}]},
}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(RESULTS, is_admin=False, elapsed={"processes": 12.3, "cpu": 2.0})

    def test_attention_items(self):
        items = {a["Item"]: a for a in self.data["attention"]}
        self.assertEqual(items["Pending reboot"]["Severity"], "Warning")
        self.assertEqual(items["UAC disabled"]["Severity"], "Warning")
        self.assertEqual(items["Low disk space"]["Detail"], "C:")
        self.assertEqual(items["Problem devices"]["Detail"], "Unknown device (28: Drivers not installed)")
        self.assertIn("Enabled", items["USB selective suspend"]["Detail"])
        self.assertEqual(items["Camera Frame Server"]["Severity"], "Info")
        self.assertEqual(items["Camera or microphone access denied"]["Detail"], "Camera (user)")
        self.assertEqual(items["Sentinel LDK License Manager not running"]["Severity"], "Warning")
        self.assertEqual(items["Jumbo frames disabled on a physical adapter"]["Detail"], "Ethernet: Disabled (GigE Vision cameras benefit from 9014)")
        self.assertEqual(items["Report ran without administrator rights"]["Severity"], "Info")

    def test_specifications_and_inventories(self):
        rows = mod.flatten(self.data)
        self.assertEqual(rows["Manufacturer"], "Dell Inc.")
        self.assertEqual(rows["Operating System"], "Windows 11 24H2")
        self.assertEqual(rows["Processor"], "i7-12700")
        self.assertEqual(rows["Memory"], "32.0 GB")
        self.assertEqual(rows["Video"], "RTX 3060")
        self.assertEqual(rows["Cameras"], "Basler ace acA1920")
        self.assertEqual(rows["HASP / Sentinel Dongles"], "SafeNet Inc. Sentinel HASP Key")
        self.assertEqual(rows["Slowest Sections"], "processes (12.3 s), cpu (2.0 s)")
        self.assertEqual([s["Name"] for s in self.data["software"]], ["EthoVision XT 19"])
        self.assertEqual([r["Name"] for r in self.data["runtimes"]], ["Microsoft Visual C++ 2015-2022 Redistributable (x64)"])
        self.assertEqual(self.data["drivers"][0]["Device"], "Basler pylon GigE Filter")
        self.assertEqual(self.data["codecs"][0]["Name"], "Noldus Resizer Filter")
        self.assertEqual(self.data["environment"][0]["Name"], "GENICAM_GENTL64_PATH")
        self.assertEqual(self.data["gige"][0]["Jumbo Packet"], "Disabled")

    def test_all_clear_when_nothing_is_wrong(self):
        data = mod.build({}, is_admin=True, elapsed={})
        self.assertEqual(data["attention"], [])
        html = mod.render(data, support.render_ctx())
        self.assertIn("No items need attention", html)

    def test_render_uses_severity_classes(self):
        html = mod.render(self.data, support.render_ctx())
        self.assertIn('class="warn"', html)
        self.assertIn("<h3>Needs attention</h3>", html)
        self.assertIn("<h3>Noldus software</h3>", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_results(self):
        results = {k: {"data": v, "notes": []} for k, v in RESULTS.items()}
        _data, html, ctx = support.collect_and_render(mod.SECTION, results=results)
        self.assertEqual(ctx.notes, [])
        self.assertIn("<h3>Needs attention</h3>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
```

- [ ] **Step 3: Module `pc_report/sections/noldus_summary.py`**

```python
"""Noldus Summary: what a Noldus support engineer needs first — attention items, specs and Noldus inventories."""
from __future__ import annotations

import re

from ..noldus_terms import RUNTIME_TERMS, filter_nvc_related_items, nvc_filter_roots, scan_nvc_filter_files
from ..section import Section, esc, kv_groups, list_table, rows_of, sub_heading

ATTENTION_COLUMNS = [("Severity", "Severity"), ("Item", "Item"), ("Detail", "Detail")]
SOFTWARE_COLUMNS = [("Name", "Name"), ("Version", "Version"), ("Publisher", "Publisher"), ("Install Date", "Install Date"), ("Install Location", "Install Location")]
DRIVER_COLUMNS = [("Device", "Device"), ("Class", "Class"), ("Version", "Version"), ("Date", "Date"), ("Provider", "Provider"), ("INF", "INF"), ("Signed", "Signed")]
CODEC_COLUMNS = [("Name", "Name"), ("Category", "Category"), ("File", "File"), ("Version", "Version"), ("Company", "Company"), ("Architecture", "Architecture")]
ENV_COLUMNS = [("Scope", "Scope"), ("Name", "Name"), ("Value", "Value")]
CAMERA_COLUMNS = [("Name", "Name"), ("Class", "Class"), ("Status", "Status"), ("Problem", "Problem")]
DONGLE_COLUMNS = [("Name", "Name"), ("VID / PID", "VID / PID"), ("Status", "Status"), ("Present", "Present")]
GIGE_COLUMNS = [("Adapter", "Adapter"), ("Link Speed", "Link Speed"), ("Jumbo Packet", "Jumbo Packet"), ("Receive Buffers", "Receive Buffers"),
                ("Transmit Buffers", "Transmit Buffers"), ("Interrupt Moderation", "Interrupt Moderation")]
RUNTIME_COLUMNS = [("Name", "Name"), ("Version", "Version"), ("Publisher", "Publisher")]
SEVERITY_CLASS = {"Warning": "warn", "Error": "bad", "Info": ""}
_HASP = re.compile(r"hasp|sentinel|hardlock", re.I)


def _flat(data) -> dict:
    out = {}
    if isinstance(data, dict):
        for g in rows_of(data.get("groups")):
            out.update(g.get("rows") or {})
    return out


def _rows(data, key) -> list[dict]:
    return rows_of(data.get(key)) if isinstance(data, dict) else []


def _attention(r: dict, is_admin: bool) -> list[dict]:
    items = []

    def add(severity, item, detail=""):
        items.append({"Severity": severity, "Item": item, "Detail": detail})

    os_ = _flat(r.get("operating_system"))
    if os_.get("Pending Reboot") == "Yes":
        add("Warning", "Pending reboot", "Windows has a reboot pending (CBS, Windows Update or file rename)")
    if os_.get("UAC Enabled") == "No":
        add("Warning", "UAC disabled", "EnableLUA is 0")
    low = _flat(r.get("logical_disks")).get("Low Space (<10 %)")
    if low and low != "None":
        add("Warning", "Low disk space", str(low))
    problems = _rows(r.get("devices"), "problems")
    if problems:
        add("Warning", "Problem devices", "; ".join(f"{p.get('Name')} ({p.get('Problem')})" for p in problems))
    usb = _flat(r.get("usb"))
    if usb.get("Selective Suspend (AC)") == "Enabled":
        add("Warning", "USB selective suspend", f"Enabled on AC power (DC: {usb.get('Selective Suspend (DC)', '')}); USB cameras may drop frames")
    cams = _flat(r.get("cameras"))
    fs = str(cams.get("Frame Server Mode", ""))
    if fs.startswith("Enabled") or fs.startswith("Not configured"):
        add("Info", "Camera Frame Server", "Shared camera access is on; legacy DirectShow applications may need EnableFrameServerMode = 0")
    denied = [label.replace(" Access (", " (") for label, value in cams.items() if " Access (" in label and str(value).lower() == "deny"]
    if denied:
        add("Warning", "Camera or microphone access denied", ", ".join(denied))
    for s in _rows(r.get("services"), "rows"):
        if s.get("Name") == "hasplms" and s.get("State") != "Running":
            add("Warning", "Sentinel LDK License Manager not running", f"hasplms is {s.get('State')} ({s.get('Start Mode')})")
    for g in _rows(r.get("network_adapters"), "gige"):
        if str(g.get("Jumbo Packet", "")).lower() in ("disabled", "1514", "1514 bytes", "off"):
            add("Info", "Jumbo frames disabled on a physical adapter", f"{g.get('Adapter')}: {g.get('Jumbo Packet')} (GigE Vision cameras benefit from 9014)")
    if not is_admin:
        add("Info", "Report ran without administrator rights", "TPM, BitLocker, disk reliability counters and SMB server settings were skipped")
    return items


def build(results: dict, is_admin: bool, elapsed: dict) -> dict:
    r = results or {}
    os_, cpu, mem, sysm = _flat(r.get("operating_system")), _flat(r.get("cpu")), _flat(r.get("memory")), _flat(r.get("system_summary"))
    video = [a.get("name", "") for a in _rows(r.get("video"), "adapters")]
    cameras = [{"Name": c.get("Name", ""), "Class": c.get("Class", ""), "Status": c.get("Status", ""), "Problem": c.get("Problem", "")}
               for c in _rows(r.get("cameras"), "pnp")]
    dongles = [{"Name": d.get("Name", ""), "VID / PID": d.get("VID / PID", ""), "Status": d.get("Status", ""), "Present": d.get("Present", "")}
               for d in _rows(r.get("usb"), "devices") if str(d.get("VID / PID", "")).startswith("0529") or _HASP.search(str(d.get("Name", "")))]
    programs = _rows(r.get("installed_programs"), "rows")
    software = [{k: p.get(k, "") for k, _l in SOFTWARE_COLUMNS} for p in filter_nvc_related_items(programs)]
    runtimes = [{k: p.get(k, "") for k, _l in RUNTIME_COLUMNS} for p in programs if any(t in str(p.get("Name", "")).lower() for t in RUNTIME_TERMS)]
    drivers = []
    by_class = r.get("drivers", {}).get("by_class", {}) if isinstance(r.get("drivers"), dict) else {}
    for cls, rows in (by_class or {}).items():
        for d in filter_nvc_related_items(rows):
            drivers.append({"Device": d.get("Device", ""), "Class": cls, "Version": d.get("Version", ""), "Date": d.get("Date", ""),
                            "Provider": d.get("Provider", ""), "INF": d.get("INF", ""), "Signed": d.get("Signed", "")})
    codecs = []
    categories = r.get("codecs", {}).get("categories", {}) if isinstance(r.get("codecs"), dict) else {}
    for cat, rows in (categories or {}).items():
        for c in filter_nvc_related_items(rows):
            codecs.append({"Name": c.get("Name", ""), "Category": cat, "File": c.get("File", ""), "Version": c.get("Version", ""),
                           "Company": c.get("Company", ""), "Architecture": c.get("Architecture", "")})
    for f in scan_nvc_filter_files(nvc_filter_roots()):
        codecs.append({"Name": f.get("Name", ""), "Category": "File scan", "File": f.get("File", ""), "Version": "", "Company": "", "Architecture": ""})
    env = []
    env_data = r.get("environment") if isinstance(r.get("environment"), dict) else {}
    for scope in ("Machine", "User", "Process"):
        for v in filter_nvc_related_items(rows_of(env_data.get(scope))):
            env.append({"Scope": scope, "Name": v.get("Name", ""), "Value": v.get("Value", "")})
    gige = _rows(r.get("network_adapters"), "gige")
    specs = {"Manufacturer": sysm.get("Manufacturer", ""), "Model": sysm.get("Model", ""),
             "Operating System": " ".join(x for x in (os_.get("Name", ""), os_.get("Version", "")) if x),
             "Processor": cpu.get("Name", ""), "Memory": mem.get("Installed Memory", ""), "Video": ", ".join(v for v in video if v),
             "Cameras": ", ".join(c["Name"] for c in cameras) or "None detected",
             "HASP / Sentinel Dongles": ", ".join(d["Name"] for d in dongles) or "None detected",
             ".NET Framework 4.x": os_.get(".NET Framework 4.x", ""), "Boot Time": os_.get("Boot Time", ""), "Up Time": os_.get("Up Time", "")}
    slow = sorted((elapsed or {}).items(), key=lambda kv: kv[1], reverse=True)[:5]
    collection = {"Elevated": "Yes" if is_admin else "No", "Sections Timed": len(elapsed or {}),
                  "Slowest Sections": ", ".join(f"{k} ({v:.1f} s)" for k, v in slow)}
    return {"attention": _attention(r, is_admin),
            "groups": [{"title": "System Specifications", "rows": specs}, {"title": "Collection", "rows": collection}],
            "software": software, "runtimes": runtimes, "drivers": drivers, "codecs": codecs, "environment": env,
            "cameras": cameras, "dongles": dongles, "gige": gige}


def flatten(data) -> dict:
    return _flat(data)


def collect(ctx):
    results = {k: ctx.result(k) for k in SECTION.after}
    elapsed = getattr(ctx.run, "elapsed", None) or {}
    return build(results, ctx.is_admin, elapsed)


def _attention_table(items) -> str:
    if not items:
        return '<p class="ok">No items need attention.</p>'
    body = "".join(
        f'<tr><td class="{SEVERITY_CLASS.get(i.get("Severity"), "")}">{esc(i.get("Severity"))}</td>'
        f'<td>{esc(i.get("Item"))}</td><td>{esc(i.get("Detail"))}</td></tr>' for i in items)
    head = "".join(f"<th>{esc(label)}</th>" for _k, label in ATTENTION_COLUMNS)
    return f'<table class="list"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (sub_heading("Needs attention") + _attention_table(rows_of(data.get("attention")))
            + kv_groups(data.get("groups"))
            + sub_heading("Noldus software") + list_table(SOFTWARE_COLUMNS, data.get("software"))
            + sub_heading("Runtimes and redistributables") + list_table(RUNTIME_COLUMNS, data.get("runtimes"))
            + sub_heading("Noldus and camera drivers") + list_table(DRIVER_COLUMNS, data.get("drivers"))
            + sub_heading("Noldus filters and codecs") + list_table(CODEC_COLUMNS, data.get("codecs"))
            + sub_heading("Noldus environment variables") + list_table(ENV_COLUMNS, data.get("environment"))
            + sub_heading("Cameras") + list_table(CAMERA_COLUMNS, data.get("cameras"))
            + sub_heading("HASP / Sentinel dongles") + list_table(DONGLE_COLUMNS, data.get("dongles"))
            + sub_heading("GigE-relevant adapter settings") + list_table(GIGE_COLUMNS, data.get("gige")))


SECTION = Section(key="noldus_summary", title="Noldus Summary", group="NVC", collect=collect, render=render, timeout=30,
                  after=("operating_system", "installed_programs", "drivers", "codecs", "environment", "cameras", "usb",
                         "services", "network_adapters", "security", "memory", "cpu", "video", "logical_disks", "devices",
                         "system_summary"))
```

Two support changes this module needs:

1. `RunContext` gains an `elapsed: dict` field (default empty) that the orchestrator fills as each section finishes, so the summary can report the slowest sections. In `pc_report/section.py` add `elapsed: dict = field(default_factory=dict)` to `RunContext`; in `pc_report/orchestrator.py` write `run.elapsed[section.key] = seconds` where `meta["elapsed_by_section"]` is filled today (same value). Add one assertion to `tests/test_pc_report_orchestration.py`'s existing timing test: `self.assertEqual(set(meta["elapsed_by_section"]), {"a", "b"})` already exists in spirit — extend `test_meta_has_elapsed_by_section` (or the equivalent test written in Task 3) with a fake section whose `collect` reads `ctx.run.elapsed` and asserts the earlier phase's key is present.
2. `.ok` CSS class: add `.ok{color:#1f7a4d;font-weight:600}` next to `.warn`/`.bad` in `render_html.py`'s CSS.

`filter_nvc_related_items` matches the test's `hasplms` row too — it is only applied to programs, drivers, codecs and environment rows, so that is fine.

- [ ] **Step 4: Run and commit**

```
python -m pytest tests/pc_report -q
python -m pytest -q
python -m ruff check pc_report tests scripts/dev/capture_pc_report_fixtures.py
```

Commit: `feat(pc_report): Noldus Summary with attention items, specs and inventories`

---

### Task 30: Wrap-up — dialog, docs, live smoke test, comparison against SIW, merge

**Files:**
- Modify: `ui/pc_report_dialog.py` (options dict, progress text)
- Create: `tests/pc_report/test_live_report.py`
- Modify: `docs/CHANGELOG.md`, `docs/BACKLOG.md`
- Modify: `tests/test_pc_report_widget.py` if it asserts on progress text

- [ ] **Step 1: Dialog options and progress**

In `ui/pc_report_dialog.py` replace the `run_all({...}, progress_cb=...)` call in `_PCReportWorker._generate` with:

```python
        meta, data, errors = run_all({
            'installed_updates': self.options.get('updates', True),
            'installed_programs': self.options.get('programs', True),
            'security': self.options.get('security', True),
        }, progress_cb=lambda title, completed, total: self.progress.emit(f"{title} ({completed}/{total})"))
```

(Unlisted sections are enabled by default; `registry.is_enabled` treats missing keys as on. The old `hardware`/`network`/`network_info`/`autoruns` keys still work through `ALIASES` for any saved presets.)

Run `python -m pytest tests/test_pc_report_widget.py -q`; if a test asserts the old `"Running PC report…"` narration or option keys, update the assertion to the new text.

- [ ] **Step 2: Live smoke test (opt-in)**

Create `tests/pc_report/test_live_report.py`:

```python
"""Runs the real report on this machine. Opt in with NVC_PC_REPORT_LIVE=1; skipped otherwise."""
import os
import unittest

from pc_report import orchestrator, registry, render_html
from pc_report.section import NO_DATA


@unittest.skipUnless(os.environ.get("NVC_PC_REPORT_LIVE") == "1", "set NVC_PC_REPORT_LIVE=1 to run the live report")
class LiveReportTests(unittest.TestCase):
    def test_every_section_collects_and_renders(self):
        meta, data, errors = orchestrator.run_all({})
        self.assertEqual(set(data), {s.key for s in registry.SECTIONS})
        self.assertEqual(errors, {}, errors)
        html = render_html.render(meta, data, {"redact": True})
        empty = [s.title for s in registry.SECTIONS if NO_DATA in html.split(f'id="s-{s.key}"', 1)[-1].split("<h2", 1)[0]]
        # Sections that can legitimately be empty on a desktop without the hardware:
        allowed_empty = {"Printers", "Shares", "Sensors", "Ports", "Virtual Machine"}
        self.assertLessEqual(set(empty) - allowed_empty, set(), f"unexpectedly empty: {empty}")
        out = os.path.join(os.environ.get("TEMP", "."), "nvc_live_pc_report.html")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"\nlive report written to {out} in {meta['total_seconds']:.1f} s")
```

Run it once: `set NVC_PC_REPORT_LIVE=1 && python -m pytest tests/pc_report/test_live_report.py -q -s` (PowerShell: `$env:NVC_PC_REPORT_LIVE='1'; python -m pytest tests/pc_report/test_live_report.py -q -s`). Open the written HTML in a browser.

- [ ] **Step 3: Section-by-section comparison against SIW**

With the live report and `the SIW reference report on the Desktop` open side by side, walk every SIW section and note any field SIW shows that the NVC report does not. For each gap decide: (a) add it to the section (small builder change plus a test line), or (b) record it in `docs/BACKLOG.md` under "PC report follow-ups" with the source it would need. Expected known gaps to record, not fix: per-core temperatures, SPD timings, vendor-specific fan speeds, SIW's own benchmark scores.

Also check in the live HTML, with redaction on:
- No machine name, user name, serial, key, MAC or full IP appears anywhere (`Ctrl+F` for the machine name, your user name, and the first octets of the LAN).
- Every "Requires administrator" cell is in the expected places (TPM, BitLocker, reliability counters, SMB server).
- The Contents block lists 40 sections plus Report Health and every link lands on its section.

Run once more elevated (right-click PowerShell → Run as administrator) and confirm those cells fill in.

- [ ] **Step 4: Docs**

`docs/CHANGELOG.md` — add under the unreleased/next version heading:

```
### PC Report
- Rebuilt on a section registry: 40 sections in NVC / Software / Hardware / Network groups, matching SIW's layout, each with a grouped Contents entry and Top link.
- Depth parity with SIW: operating system (activation, boot, policies), update history, licences, security (Defender, firewall, VBS, TPM, BitLocker), processes with owners, services, drivers by class, autorun with StartupApproved state, codecs across DirectShow/VCM/ACM/MFT, motherboard, BIOS characteristics, CPU caches and features, memory modules, sensors, devices, PCI, slots, adapters with advanced properties, video with corrected memory, monitors, sound endpoints, storage with partitions and reliability counters, logical disks, ports, USB, printers, VM detection, cameras (Frame Server, consent store, GenICam), network information, shares, connections.
- New Noldus Summary first: attention items (pending reboot, UAC, low disk, problem devices, USB selective suspend, Frame Server, camera consent, hasplms, jumbo frames), specs, Noldus software/drivers/filters/environment, cameras, dongles, GigE settings.
- Redaction extended: normalised label matching, IPs masked to two octets, MACs, hardware IDs, account names, SSIDs, DNS suffixes; Name/Value rows.
- Admin-only fields show "Requires administrator" instead of failing; no UAC prompt.
- Report Health block: partial/empty sections, elapsed time per section.
```

`docs/BACKLOG.md` — add a "PC report follow-ups" list with the gaps from Step 3 and the out-of-scope items from the spec (UAC-elevated collection, Quick/Full profiles, PDF export, report comparison, dialog redesign).

- [ ] **Step 5: Final checks and merge**

```
python -m ruff check .
python -m pytest -q
git status   # only intended files; no fixture with identifying data
```

Read every file under `tests/fixtures/pc_report/` one last time for host names, user names, serials, keys and addresses. Then:

```
git add -A
git commit -m "feat(pc_report): SIW-depth PC report with section registry, Noldus summary, fixtures and live smoke test"
git checkout main
git merge --no-ff pc-report-siw -m "Merge pc-report-siw: SIW-depth PC report"
python -m pytest -q
```

If the repository's main branch has another name, use that. Do not delete the branch until the merged suite passes.

---

## Self-review notes

- Spec coverage: every section in the spec's four catalogue tables has a task (6–28), the Noldus Summary is Task 29, Report Health is rendered by Task 5's page shell, redaction additions are Task 4 plus the two tokens added in Task 26, fixtures/tests strategy is Task 2, migration steps map to Tasks 1–5 and 29–30.
- Every section module follows the same shape (`SCRIPT` constants, pure `build`, `collect`, `render`, `SECTION`), returns plain data, and never raises on empty input; `assert_renders_empty` is in every test module.
- Labels chosen to hit redaction tokens where masking is wanted: `Serial Number`, `Computer Name`, `Domain Name`, `User Name`, `Registered Owner`, `Partial Product Key`, `Windows Product ID`, `OEM Original Product Key`, `KMS Host Name`, `MAC Address`, `IPv4/IPv6 Address`, `Default Gateway`, `DNS Servers`, `DHCP Server`, `WINS Servers`, `Next Hop`, `Local/Remote Address`, `SSID`, `Hardware ID`, `Local Administrators`, `Account Name`, `Installed By (account name)`, `Run As (account name)`, `Remote Path (host name)`, `Server (host name)`, `Network Path (host name)`, `DNS Host Name`, `Owner`, `Start Name` (`startname`), `UUID`, `Asset Tag`; and chosen to avoid tokens where masking is not wanted: `Role`, `Owning Process` → `Process`, `Key Type`, `License Status`, `Machine Type`.
- Test expectations were checked against the foundation helpers: `bytes_human` gives one decimal, `mhz` prints MHz below 10 000, `duration` prints `N s`, `parse_datetime` accepts `/Date(ms)/`, CIM and `yyyymmdd`, `lookup` returns `Other (n)` for unknown codes.

