"""System Summary: identity and a one-page overview of detailed section results."""
from __future__ import annotations

import re

from .. import decode
from ..format import bytes_human, yes_no
from ..ps import cim
from ..section import Section, first_dict, flatten_groups, kv_groups, list_table, rows_of, sub_heading
from . import bios, cpu, memory, motherboard, operating_system, video

CS_SCRIPT = cim(
    "Win32_ComputerSystem",
    (
        "Manufacturer",
        "Model",
        "SystemFamily",
        "SystemSKUNumber",
        "Name",
        "Domain",
        "PartOfDomain",
        "DomainRole",
        "Workgroup",
        "PCSystemType",
        "TotalPhysicalMemory",
        "UserName",
        "NumberOfProcessors",
        "NumberOfLogicalProcessors",
        "HypervisorPresent",
        "BootupState",
        "PowerSupplyState",
        "ThermalState",
        "Description",
    ),
)
CSP_SCRIPT = cim(
    "Win32_ComputerSystemProduct",
    ("Name", "Vendor", "Version", "IdentifyingNumber", "UUID", "SKUNumber"),
)
ENCLOSURE_SCRIPT = cim(
    "Win32_SystemEnclosure",
    (
        "ChassisTypes",
        "SerialNumber",
        "SMBIOSAssetTag",
        "Manufacturer",
        "LockPresent",
    ),
)
PF_USAGE_SCRIPT = cim(
    "Win32_PageFileUsage",
    ("Name", "AllocatedBaseSize", "CurrentUsage", "PeakUsage"),
)
PF_SETTING_SCRIPT = cim(
    "Win32_PageFileSetting", ("Name", "InitialSize", "MaximumSize")
)
WINSAT_SCRIPT = cim(
    "Win32_WinSAT",
    (
        "CPUScore",
        "D3DScore",
        "DiskScore",
        "GraphicsScore",
        "MemoryScore",
        "WinSPRLevel",
        "WinSATAssessmentState",
    ),
)
POWER_ARGS = ["powercfg", "/getactivescheme"]

DRIVE_COLUMNS = [
    ("Drive", "Drive"),
    ("Label", "Label"),
    ("Type", "Type"),
    ("Total", "Total"),
    ("Free", "Free"),
    ("Free %", "Free %"),
]
_POWER_GUID = re.compile(
    r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.IGNORECASE
)
_POWER_NAME = re.compile(r"\(([^()\r\n]+)\)")


def _pick(values: dict, *labels: str):
    """Return the first non-empty value under any current or legacy label."""
    for label in labels:
        value = values.get(label)
        if value not in (None, ""):
            return value
    return ""


def _mb(value) -> str:
    number = decode.to_int(value)
    return bytes_human(number * 1024 * 1024) if number is not None else ""


def _power_plan(text: str) -> str:
    match = _POWER_GUID.search(text or "")
    if not match:
        return ""
    name = _POWER_NAME.search((text or "")[match.end() :])
    return (name.group(1) if name else match.group(0)).strip()


def _winsat_value(winsat: dict) -> str:
    level = winsat.get("WinSPRLevel")
    state = winsat.get("WinSATAssessmentState")
    state_text = str(state or "").strip().casefold()
    not_assessed = (
        level in (None, "")
        or state in (3, 4)
        or "not run" in state_text
        or "no assessment" in state_text
    )
    return "Not assessed" if not_assessed else str(level)


def _pagefile_management(settings) -> str:
    if settings is None:
        return "Not available"
    rows = rows_of(settings)
    if not rows:
        return "Automatic (system managed)"
    values = []
    for setting in rows:
        name = setting.get("Name", "")
        initial = decode.to_int(setting.get("InitialSize"))
        maximum = decode.to_int(setting.get("MaximumSize"))
        if not initial and not maximum:
            detail = "system managed"
        else:
            detail = f"{initial if initial is not None else ''} - {maximum if maximum is not None else ''} MB"
        values.append(f"{name}: {detail}" if name else detail)
    return "; ".join(values)


def build(
    cs,
    csp,
    enclosure,
    pf_usage,
    pf_setting,
    winsat,
    power_text,
    results,
) -> dict:
    cs, csp, winsat, results = cs or {}, csp or {}, winsat or {}, results or {}
    enc = first_dict(enclosure)

    os_rows = operating_system.flatten(results.get("operating_system"))
    cpu_rows = cpu.flatten(results.get("cpu"))
    memory_rows = memory.flatten(results.get("memory"))
    board_rows = motherboard.flatten(results.get("motherboard"))
    bios_rows = bios.flatten(results.get("bios"))
    video_names = video.names(results.get("video"))

    disk_data = results.get("logical_disks")
    disk_rows = (
        rows_of(disk_data.get("rows")) if isinstance(disk_data, dict) else []
    )
    drives = [
        {
            "Drive": _pick(row, "Drive", "Device", "Device ID"),
            "Label": _pick(row, "Label", "Volume Label"),
            "Type": _pick(row, "Type", "Drive Type"),
            "Total": _pick(row, "Total", "Size"),
            "Free": _pick(row, "Free", "Free Space"),
            "Free %": _pick(row, "Free %", "Percent Free"),
        }
        for row in disk_rows
    ]

    identity = {
        "Manufacturer": cs.get("Manufacturer") or csp.get("Vendor", ""),
        "Model": cs.get("Model") or csp.get("Name", ""),
        "System Family": cs.get("SystemFamily", ""),
        "Product Version": csp.get("Version", ""),
        "SKU": cs.get("SystemSKUNumber") or csp.get("SKUNumber", ""),
        "Serial Number": csp.get("IdentifyingNumber")
        or enc.get("SerialNumber", ""),
        "UUID": csp.get("UUID", ""),
        "Asset Tag": enc.get("SMBIOSAssetTag", ""),
        "Chassis Type": decode.lookup(
            decode.CHASSIS_TYPES, enc.get("ChassisTypes")
        ),
        "PC System Type": decode.lookup(
            decode.PC_SYSTEM_TYPES, cs.get("PCSystemType")
        ),
        "Chassis Lock": yes_no(enc.get("LockPresent")),
        "Computer Name": cs.get("Name", ""),
        "Computer Description": cs.get("Description") or "",
        "Domain Name": cs.get("Domain", "") if cs.get("PartOfDomain") else "",
        "Workgroup": (
            ""
            if cs.get("PartOfDomain")
            else cs.get("Domain") or cs.get("Workgroup") or ""
        ),
        "Role": decode.lookup(decode.DOMAIN_ROLES, cs.get("DomainRole")),
        "User Name": cs.get("UserName", ""),
        "Boot State": cs.get("BootupState", ""),
        "Power Supply State": decode.lookup(
            decode.SYSTEM_STATE, cs.get("PowerSupplyState")
        ),
        "Thermal State": decode.lookup(
            decode.SYSTEM_STATE, cs.get("ThermalState")
        ),
        "Hypervisor Present": yes_no(cs.get("HypervisorPresent")),
    }

    os_line = ", ".join(
        str(value)
        for value in (
            _pick(os_rows, "Name", "Product Name", "Caption"),
            _pick(os_rows, "Version", "Display Version"),
        )
        if value
    )
    cpu_line = _pick(cpu_rows, "Name", "Processor Name", "WMI Name")
    topology = _pick(
        cpu_rows,
        "Cores / Threads",
        "Cores / Logical Processors",
        "Core / Thread Count",
    )
    clock = _pick(cpu_rows, "Max Clock", "Maximum Clock", "Max Clock Speed")
    cpu_details = []
    if topology:
        cpu_details.append(f"{topology} cores / threads")
    if clock:
        cpu_details.append(str(clock))
    if cpu_line and cpu_details:
        cpu_line = f"{cpu_line} ({', '.join(cpu_details)})"

    total_physical = _pick(
        memory_rows, "Total Physical", "Total Physical Memory"
    )
    free_physical = _pick(
        memory_rows, "Free Physical", "Available Physical"
    )
    memory_load = _pick(memory_rows, "Memory Load", "Load")
    memory_parts = []
    if total_physical:
        memory_parts.append(f"{total_physical} total")
    if free_physical:
        memory_parts.append(f"{free_physical} free")
    memory_line = ", ".join(memory_parts)
    if memory_line and memory_load:
        memory_line += f" ({memory_load} load)"

    motherboard_line = " ".join(
        str(value)
        for value in (
            _pick(board_rows, "Manufacturer", "Vendor"),
            _pick(board_rows, "Model", "Product"),
        )
        if value
    )
    bios_version = _pick(
        bios_rows,
        "SMBIOS BIOS Version",
        "System BIOS Version",
        "Version",
        "Name",
    )
    bios_line = " ".join(
        str(value)
        for value in (
            _pick(bios_rows, "Vendor", "Manufacturer"),
            bios_version,
            (
                f"({_pick(bios_rows, 'Release Date', 'Date')})"
                if _pick(bios_rows, "Release Date", "Date")
                else ""
            ),
        )
        if value
    )

    overview = {
        "Operating System": os_line,
        "Kernel Version": _pick(os_rows, "Kernel Version", "Kernel"),
        "Firmware Type": _pick(os_rows, "Firmware Type", "Firmware"),
        "Secure Boot": _pick(os_rows, "Secure Boot", "Secure Boot State"),
        "Boot Time": _pick(os_rows, "Boot Time", "Last Boot Time"),
        "Up Time": _pick(os_rows, "Up Time", "Uptime"),
        "Processor": cpu_line,
        "Processor Load": _pick(
            cpu_rows, "Load", "Processor Utility (sample)", "Processor Load"
        ),
        "Processors / Logical": (
            f"{cs.get('NumberOfProcessors', '')} / "
            f"{cs.get('NumberOfLogicalProcessors', '')}"
            if cs
            else ""
        ),
        "Installed Memory": _pick(
            memory_rows, "Installed Memory", "Installed Physical Memory"
        )
        or (
            bytes_human(cs["TotalPhysicalMemory"])
            if cs.get("TotalPhysicalMemory")
            else ""
        ),
        "Memory Type": _pick(memory_rows, "Memory Type", "Type"),
        "Physical Memory": memory_line,
        "Virtual Memory": (
            f"{_pick(memory_rows, 'Total Virtual', 'Total Virtual Memory')} "
            f"total, "
            f"{_pick(memory_rows, 'Free Virtual', 'Available Virtual')} free"
            if _pick(memory_rows, "Total Virtual", "Total Virtual Memory")
            else ""
        ),
        "Committed": _pick(memory_rows, "Committed", "Committed Memory"),
        "Video Adapters": ", ".join(video_names),
        "Motherboard": motherboard_line,
        "BIOS": bios_line,
    }

    pagefiles = [
        "{}: {} allocated, {} in use, {} peak".format(
            item.get("Name", ""),
            _mb(item.get("AllocatedBaseSize")),
            _mb(item.get("CurrentUsage")),
            _mb(item.get("PeakUsage")),
        )
        for item in rows_of(pf_usage)
    ]
    system = {
        "Page File": (
            "; ".join(pagefiles)
            if pagefiles
            else ("None" if pf_usage is not None else "")
        ),
        "Page File Management": _pagefile_management(pf_setting),
        "Active Power Plan": _power_plan(power_text),
        "Windows Experience Index (base)": _winsat_value(winsat),
        "WinSAT Scores (CPU / Memory / Disk / Graphics / 3D)": (
            " / ".join(
                str(winsat.get(key, ""))
                for key in (
                    "CPUScore",
                    "MemoryScore",
                    "DiskScore",
                    "GraphicsScore",
                    "D3DScore",
                )
            )
            if winsat.get("CPUScore") is not None
            else ""
        ),
    }
    return {
        "groups": [
            {"title": "Computer", "rows": identity},
            {"title": "Overview", "rows": overview},
            {"title": "System", "rows": system},
        ],
        "drives": drives,
    }


def flatten(data) -> dict:
    return flatten_groups(data)


def collect(ctx):
    results = {key: ctx.result(key) for key in SECTION.after}
    return build(
        first_dict(ctx.query("computer", CS_SCRIPT)),
        first_dict(ctx.query("product", CSP_SCRIPT)),
        ctx.query("enclosure", ENCLOSURE_SCRIPT),
        ctx.query("pagefile_usage", PF_USAGE_SCRIPT),
        ctx.query("pagefile_setting", PF_SETTING_SCRIPT),
        first_dict(ctx.query("winsat", WINSAT_SCRIPT)),
        ctx.text("power_scheme", POWER_ARGS),
        results,
    )


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (
        kv_groups(data.get("groups"))
        + sub_heading("Drives")
        + list_table(DRIVE_COLUMNS, data.get("drives"))
    )


SECTION = Section(
    key="system_summary",
    title="System Summary",
    group="Hardware",
    collect=collect,
    render=render,
    after=(
        "operating_system",
        "cpu",
        "memory",
        "video",
        "logical_disks",
        "motherboard",
        "bios",
    ),
)
