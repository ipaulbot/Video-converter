"""CPU: identity, topology, clocks, caches, virtualization, microcode, live load and instruction sets."""
from __future__ import annotations

import ctypes
import os
import re

from .. import decode
from ..format import kb_human, mhz, yes_no
from ..ps import cim
from ..section import Section, first_dict, flatten_groups, kv_groups, list_table, rows_of, sub_heading

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
    if isinstance(value, list):
        if len(value) != 8:
            return ""
        try:
            n = int.from_bytes(bytes(int(b) & 0xFF for b in value[4:8]), "little")
            return f"0x{n:X}"
        except (TypeError, ValueError):
            return ""
    try:
        n = int(str(value), 16) if str(value).lower().startswith("0x") else int(value)
        return f"0x{n:X}"
    except (TypeError, ValueError):
        return ""


def _pct(value) -> str:
    try:
        return f"{float(value):.1f} %" if value is not None else ""
    except (TypeError, ValueError):
        return ""


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
            "Processor Utility (sample)": _pct(total.get("CookedValue")) if total else ""}
    per_core = [{"Core": s.get("InstanceName", ""), "Performance": _pct(s.get("CookedValue"))}
                for s in rows_of(perf)
                if "performance" in str(s.get("Path", "")).lower()
                and not (str(s.get("InstanceName", "")).casefold() == "_total"
                         or str(s.get("InstanceName", "")).casefold().endswith(",_total"))]
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
    return flatten_groups(data)


def collect(ctx):
    return build(ctx.query("processors", PROC_SCRIPT), ctx.query("caches", CACHE_SCRIPT),
                 first_dict(ctx.query("registry", REG_SCRIPT)), ctx.query("performance", PERF_SCRIPT, timeout=30),
                 probe_features())


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Cache") + list_table(CACHE_COLUMNS, data.get("caches"))
            + sub_heading("Per-core performance (1 s sample)") + list_table(CORE_COLUMNS, data.get("per_core")))


SECTION = Section(key="cpu", title="CPU", group="Hardware", collect=collect, render=render, timeout=30)
