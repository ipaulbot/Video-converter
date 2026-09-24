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


def _bytes(value) -> str:
    n = decode.to_int(value)
    return bytes_human(n) if n is not None else ""


def _kb(value) -> str:
    n = decode.to_int(value)
    return kb_human(n) if n is not None else ""


def _volt(mv):
    n = decode.to_int(mv)
    return f"{n / 1000:.1f} V" if n else ""


def _mts(v):
    n = decode.to_int(v)
    return f"{n} MT/s" if n else ""


def build(arrays, modules, os_, perf) -> dict:
    arr = first_dict(arrays)
    os_, perf = first_dict(os_), first_dict(perf)
    mods = []
    total = 0
    types = set()
    for m in rows_of(modules):
        cap = decode.to_int(m.get("Capacity"))
        if cap is not None:
            total += cap
        smbios_type = decode.to_int(m.get("SMBIOSMemoryType"))
        type_code = smbios_type if smbios_type else m.get("MemoryType")
        mtype = decode.lookup(decode.MEMORY_TYPES, type_code)
        if mtype and mtype not in ("Unknown", "Other"):
            types.add(mtype)
        dw, tw = decode.to_int(m.get("DataWidth")), decode.to_int(m.get("TotalWidth"))
        mods.append({
            "Slot": m.get("DeviceLocator", ""), "Bank": m.get("BankLabel", ""), "Capacity": _bytes(cap),
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
    max_capacity = decode.to_int(arr.get("MaxCapacityEx"))
    if max_capacity is None:
        max_capacity = decode.to_int(arr.get("MaxCapacity"))
    total_kb = decode.to_int(os_.get("TotalVisibleMemorySize"))
    free_kb = decode.to_int(os_.get("FreePhysicalMemory"))
    used_kb = (total_kb - free_kb) if total_kb is not None and free_kb is not None else None
    summary = {
        "Installed Memory": bytes_human(total) if total else "",
        "Maximum Capacity": _kb(max_capacity),
        "Slots Used": f"{len(mods)} of {slots}" if slots else str(len(mods) or ""),
        "Memory Type": ", ".join(sorted(types)),
        "Error Correction": decode.lookup(decode.ERROR_CORRECTION, arr.get("MemoryErrorCorrection")),
        "Timings": "CAS/RAS timings and XMP profiles are read from SPD and need a vendor tool; not reported here.",
    }
    committed = decode.to_int(perf.get("CommittedBytes"))
    commit_limit = decode.to_int(perf.get("CommitLimit"))
    live = {
        "Total Physical": _kb(total_kb),
        "Free Physical": _kb(free_kb),
        "Used Physical": _kb(used_kb),
        "Memory Load": percent(used_kb, total_kb) if used_kb is not None else "",
        "Total Virtual": _kb(os_.get("TotalVirtualMemorySize")),
        "Free Virtual": _kb(os_.get("FreeVirtualMemory")),
        "Paging Files": _kb(os_.get("SizeStoredInPagingFiles")),
        "Paging Files Free": _kb(os_.get("FreeSpaceInPagingFiles")),
        "Committed": (f"{bytes_human(committed)} of {bytes_human(commit_limit)}"
                      if committed is not None and commit_limit is not None else ""),
        "Available": _bytes(perf.get("AvailableBytes")),
        "System Cache": _bytes(perf.get("CacheBytes")),
        "Paged Pool": _bytes(perf.get("PoolPagedBytes")),
        "Non-paged Pool": _bytes(perf.get("PoolNonpagedBytes")),
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
