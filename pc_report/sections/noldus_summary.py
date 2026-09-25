"""Noldus Summary: attention items, specifications, and Noldus inventories."""
from __future__ import annotations

import re

from ..noldus_terms import RUNTIME_TERMS, filter_nvc_related_items
from ..section import Section, esc, flatten_groups, kv_groups, list_table, rows_of, sub_heading
from . import cameras, cpu, memory, operating_system, security, sensors, system_summary, usb, video, virtual_machine

ATTENTION_COLUMNS = [("Severity", "Severity"), ("Item", "Item"), ("Detail", "Detail")]
SOFTWARE_COLUMNS = [("Name", "Name"), ("Version", "Version"), ("Publisher", "Publisher"),
                    ("Install Date", "Install Date"), ("Install Location", "Install Location")]
DRIVER_COLUMNS = [("Device", "Device"), ("Class", "Class"), ("Version", "Version"), ("Date", "Date"),
                  ("Provider", "Provider"), ("INF", "INF"), ("Signed", "Signed")]
CODEC_COLUMNS = [("Name", "Name"), ("Category", "Category"), ("File", "File"), ("Version", "Version"),
                 ("Company", "Company"), ("Architecture", "Architecture")]
ENV_COLUMNS = [("Scope", "Scope"), ("Name", "Name"), ("Value", "Value")]
CAMERA_COLUMNS = [("Name", "Name"), ("Class", "Class"), ("Status", "Status"), ("Problem", "Problem")]
DONGLE_COLUMNS = [("Name", "Name"), ("VID / PID", "VID / PID"), ("Status", "Status"), ("Present", "Present")]
GIGE_COLUMNS = [("Adapter", "Adapter"), ("Link Speed", "Link Speed"), ("Jumbo Packet", "Jumbo Packet"),
                ("Receive Buffers", "Receive Buffers"), ("Transmit Buffers", "Transmit Buffers"),
                ("Interrupt Moderation", "Interrupt Moderation")]
RUNTIME_COLUMNS = [("Name", "Name"), ("Version", "Version"), ("Publisher", "Publisher")]
SEVERITY_CLASS = {"Error": "bad", "Warning": "warn", "Info": "", "OK": "ok"}

_HASP = re.compile(r"hasp|sentinel|hardlock", re.I)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}


def _rows(data, key) -> list[dict]:
    return rows_of(data.get(key)) if isinstance(data, dict) else []


def _first(values: dict, *labels):
    for label in labels:
        value = values.get(label)
        if value not in (None, ""):
            return value
    return ""


def _is_disabled(value) -> bool:
    return str(value or "").strip().casefold() in {"0", "disabled", "false", "no", "off"}


def _number(value):
    match = _NUMBER.search(str(value or "").replace(",", ""))
    return float(match.group()) if match else None


def _bytes(value):
    text = str(value or "").strip().upper()
    number = _number(text)
    if number is None:
        return None
    unit = next((unit for unit in _SIZE_UNITS if re.search(rf"\b{unit}\b", text)), None)
    return number * _SIZE_UNITS[unit] if unit else None


def _low_disks(data) -> list[str]:
    low = []
    for row in _rows(data, "rows"):
        drive_type = str(_first(row, "Type", "Drive Type", "DriveType")).casefold()
        if "local" not in drive_type and "fixed" not in drive_type:
            continue
        drive = _first(row, "Drive", "Device", "Device ID", "DeviceID")
        free, free_pct = _first(row, "Free", "Free Space"), _first(row, "Free %", "Percent Free")
        pct = _number(free_pct)
        free_bytes = _bytes(free)
        triggers = []
        if pct is not None and pct < 10:
            triggers.append("Free % below 10%")
        if free_bytes is not None and free_bytes < 10 * 1024 ** 3:
            triggers.append("Free space below 10 GB")
        if triggers:
            detail = ", ".join(str(value) for value in (free, free_pct) if value not in (None, ""))
            disk = f"{drive} ({detail})" if detail else str(drive)
            low.append(f"{disk}; triggered: {', '.join(triggers)}")
    return low


def _attention(results: dict, is_admin: bool) -> list[dict]:
    items = []

    def add(severity, item, detail=""):
        items.append({"Severity": severity, "Item": item, "Detail": detail})

    os_rows = operating_system.flatten(results.get("operating_system"))
    security_rows = security.flatten(results.get("security"))
    if str(_first(os_rows, "Pending Reboot", "Reboot Pending")).casefold() in {"yes", "true", "pending"}:
        add("Warning", "Pending reboot", "Windows has a reboot pending")
    uac = _first(security_rows, "UAC Enabled", "User Account Control (UAC)", "EnableLUA")
    if uac == "":
        uac = _first(os_rows, "UAC Enabled", "User Account Control (UAC)", "EnableLUA")
    if _is_disabled(uac):
        add("Warning", "UAC disabled", f"Reported as {uac}")

    low = _low_disks(results.get("logical_disks"))
    if low:
        add("Warning", "Low disk space", "; ".join(low))

    problems = _rows(results.get("devices"), "problems")
    if problems:
        first_names = []
        for problem in problems[:3]:
            name = _first(problem, "Name", "Device")
            detail = _first(problem, "Problem", "ConfigManagerErrorCode")
            first_names.append(f"{name} ({detail})" if detail else str(name))
        suffix = f"; +{len(problems) - 3} more" if len(problems) > 3 else ""
        add("Warning", "Problem devices",
            f"{len(problems)} device{'s' if len(problems) != 1 else ''}: {'; '.join(first_names)}{suffix}")

    usb_rows = {}
    for group in rows_of((results.get("usb") or {}).get("groups") if isinstance(results.get("usb"), dict) else None):
        usb_rows.update(group.get("rows") or {})
    ac = _first(usb_rows, "Selective Suspend (AC)", "USB Selective Suspend (AC)")
    dc = _first(usb_rows, "Selective Suspend (DC)", "USB Selective Suspend (DC)")
    if str(ac).casefold() == "enabled" or str(dc).casefold() == "enabled":
        add("Warning", "USB selective suspend", f"AC: {ac or 'Unknown'}; DC: {dc or 'Unknown'}; USB cameras may drop frames")

    camera_data = results.get("cameras")
    if cameras.frame_server_enabled(camera_data):
        add("Info", "Camera Frame Server shared mode",
            "Shared camera access is enabled; legacy DirectShow applications may require exclusive mode")
    denied = cameras.denied(camera_data)
    if denied:
        add("Warning", "Camera or microphone access denied", ", ".join(denied))

    for service_row in _rows(results.get("services"), "rows"):
        if str(service_row.get("Name", "")).casefold() == "hasplms" and str(service_row.get("State", "")).casefold() != "running":
            start_mode = _first(service_row, "Start Mode", "StartMode")
            add("Warning", "Sentinel LDK License Manager not running",
                f"hasplms is {service_row.get('State') or 'not running'} ({start_mode})")

    for adapter in _rows(results.get("network_adapters"), "gige"):
        jumbo = _first(adapter, "Jumbo Packet", "Jumbo Frames", "Jumbo Frame")
        if str(jumbo or "").strip().casefold() in {"disabled", "1514", "1514 bytes", "off"}:
            add("Info", "Jumbo frames disabled on GigE adapters",
                f"{adapter.get('Adapter', '')}: {jumbo} (GigE Vision cameras benefit from 9014)")

    if not is_admin:
        add("Info", "Report ran without administrator rights",
            "TPM, BitLocker, disk reliability counters and SMB server settings may be unavailable")

    memory_rows = memory.flatten(results.get("memory"))
    live_source = _first(memory_rows, "Live Source", "Live Data Source")
    sensor_rows = sensors.flatten(results.get("sensors"))
    sensor_counter_labels = ("CPU Utility", "Memory Committed", "Memory Available")
    sensors_present_without_counters = bool(sensor_rows) and not any(sensor_rows.get(label) for label in sensor_counter_labels)
    if (live_source and str(live_source).casefold() != "performance counters") or sensors_present_without_counters:
        detail = f"Memory live source: {live_source}" if live_source and str(live_source).casefold() != "performance counters" else (
            "Sensor performance-counter values are unavailable"
        )
        add("Info", "Performance counters unavailable", detail)

    vm_rows = virtual_machine.flatten(results.get("virtual_machine"))
    if str(_first(vm_rows, "Running Inside a VM", "Running inside a VM")).casefold() in {"yes", "true"}:
        add("Info", "Running inside a virtual machine",
            str(_first(vm_rows, "Interpretation", "Detected Hypervisor", "Hypervisor") or "Virtual machine detected"))
    return items


def build(results: dict, is_admin: bool, elapsed: dict) -> dict:
    results = results or {}
    summary_rows = system_summary.flatten(results.get("system_summary"))
    os_rows = operating_system.flatten(results.get("operating_system"))
    cpu_rows = cpu.flatten(results.get("cpu"))
    memory_rows = memory.flatten(results.get("memory"))
    video_names = video.names(results.get("video"))
    camera_names = cameras.camera_names(results.get("cameras"))
    dongle_names = usb.hasp_devices(results.get("usb"))
    gige = _rows(results.get("network_adapters"), "gige")
    disk_rows = _rows(results.get("system_summary"), "drives") or _rows(results.get("logical_disks"), "rows")
    system_drive = next((row for row in disk_rows if str(_first(row, "Drive", "Device", "Device ID")).upper() == "C:"), {})
    system_free = _first(system_drive, "Free", "Free Space")
    system_pct = _first(system_drive, "Free %", "Percent Free")

    os_fallback = " ".join(str(value) for value in (
        _first(os_rows, "Name", "Product Name", "Caption"),
        _first(os_rows, "Version", "Display Version"),
    ) if value)
    specs = {
        "Manufacturer": _first(summary_rows, "Manufacturer", "System Manufacturer"),
        "Model": _first(summary_rows, "Model", "System Model"),
        "Operating System": _first(summary_rows, "Operating System") or os_fallback,
        "Processor": _first(summary_rows, "Processor") or _first(cpu_rows, "Name", "Processor Name"),
        "Memory": _first(summary_rows, "Installed Memory", "Memory") or _first(memory_rows, "Installed Memory"),
        "Video": _first(summary_rows, "Video Adapters", "Video", "GPU") or ", ".join(video_names),
        "System Drive Free": f"{system_free} ({system_pct})" if system_free and system_pct else system_free or system_pct,
        # Kept as rows so redaction still sees one camera name per value; the renderer joins them.
        "Cameras": camera_names or "None detected",
        "HASP / Sentinel Dongles": ", ".join(dongle_names) or "None detected",
        "GigE Adapters": ", ".join(str(row.get("Adapter") or "") for row in gige if row.get("Adapter")) or "None detected",
    }

    programs = _rows(results.get("installed_programs"), "rows")
    software = [{key: row.get(key, "") for key, _label in SOFTWARE_COLUMNS}
                for row in filter_nvc_related_items(programs)]
    runtimes = [{key: row.get(key, "") for key, _label in RUNTIME_COLUMNS}
                for row in programs
                if any(term in str(row.get("Name", "")).casefold() for term in RUNTIME_TERMS)]

    drivers = []
    by_class = results.get("drivers", {}).get("by_class", {}) if isinstance(results.get("drivers"), dict) else {}
    for class_name, class_rows in (by_class or {}).items():
        for row in filter_nvc_related_items(class_rows):
            drivers.append({"Device": row.get("Device", ""), "Class": class_name, "Version": row.get("Version", ""),
                            "Date": row.get("Date", ""), "Provider": row.get("Provider", ""),
                            "INF": row.get("INF", ""), "Signed": row.get("Signed", "")})

    codecs = []
    categories = results.get("codecs", {}).get("categories", {}) if isinstance(results.get("codecs"), dict) else {}
    for category, category_rows in (categories or {}).items():
        for row in filter_nvc_related_items(category_rows):
            codecs.append({"Name": row.get("Name", ""), "Category": category, "File": row.get("File", ""),
                           "Version": row.get("Version", ""), "Company": row.get("Company", ""),
                           "Architecture": row.get("Architecture", "")})

    environment_rows = []
    environment = results.get("environment") if isinstance(results.get("environment"), dict) else {}
    for scope in ("Machine", "User", "Process"):
        for row in filter_nvc_related_items(rows_of(environment.get(scope))):
            environment_rows.append({"Scope": scope, "Name": row.get("Name", ""), "Value": row.get("Value", "")})

    camera_rows = [{"Name": row.get("Name", ""), "Class": row.get("Class", ""), "Status": row.get("Status", ""),
                    "Problem": row.get("Problem", "")} for row in _rows(results.get("cameras"), "pnp")]
    dongle_rows = [
        {"Name": row.get("Name", ""), "VID / PID": row.get("VID / PID", ""), "Status": row.get("Status", ""),
         "Present": row.get("Present", "")}
        for row in _rows(results.get("usb"), "devices")
        if str(row.get("VID / PID", "")).startswith("0529") or _HASP.search(str(row.get("Name", "")))
    ]

    elapsed = elapsed or {}
    slowest = sorted(elapsed.items(), key=lambda item: item[1], reverse=True)[:3]
    collection = {
        "Elapsed Total": f"{sum(elapsed.values()):.1f} s",
        "Slowest Sections": ", ".join(f"{key} ({seconds:.1f} s)" for key, seconds in slowest),
        "Elevated": "Yes" if is_admin else "No",
        "Sections Timed": len(elapsed),
    }
    return {
        "attention": _attention(results, is_admin),
        "groups": [{"title": "System Specifications", "rows": specs}, {"title": "Collection", "rows": collection}],
        "software": software,
        "runtimes": runtimes,
        "drivers": drivers,
        "codecs": codecs,
        "environment": environment_rows,
        "cameras": camera_rows,
        "dongles": dongle_rows,
        "gige": gige,
    }


def flatten(data) -> dict:
    return flatten_groups(data)


def collect(ctx):
    results = {key: ctx.result(key) for key in SECTION.after}
    return build(results, ctx.is_admin, ctx.run.elapsed)


def _attention_table(items) -> str:
    if not items:
        return '<p class="ok">No items need attention.</p>'
    body = "".join(
        f'<tr><td class="{SEVERITY_CLASS.get(item.get("Severity"), "")}">{esc(item.get("Severity"))}</td>'
        f'<td>{esc(item.get("Item"))}</td><td>{esc(item.get("Detail"))}</td></tr>'
        for item in items
    )
    head = "".join(f"<th>{esc(label)}</th>" for _key, label in ATTENTION_COLUMNS)
    return f'<table class="list"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (
        sub_heading("Needs attention") + _attention_table(rows_of(data.get("attention")))
        + kv_groups(data.get("groups"))
        + sub_heading("Noldus software") + list_table(SOFTWARE_COLUMNS, data.get("software"))
        + sub_heading("Runtimes and redistributables") + list_table(RUNTIME_COLUMNS, data.get("runtimes"))
        + sub_heading("Noldus and camera drivers") + list_table(DRIVER_COLUMNS, data.get("drivers"))
        + sub_heading("Noldus filters and codecs") + list_table(CODEC_COLUMNS, data.get("codecs"))
        + sub_heading("Noldus environment variables") + list_table(ENV_COLUMNS, data.get("environment"))
        + sub_heading("Cameras") + list_table(CAMERA_COLUMNS, data.get("cameras"))
        + sub_heading("HASP / Sentinel dongles") + list_table(DONGLE_COLUMNS, data.get("dongles"))
        + sub_heading("GigE-relevant adapter settings") + list_table(GIGE_COLUMNS, data.get("gige"))
    )


SECTION = Section(
    key="noldus_summary",
    title="Noldus Summary",
    group="NVC",
    collect=collect,
    render=render,
    timeout=30,
    after=(
        "operating_system", "installed_programs", "drivers", "codecs", "environment", "cameras", "usb",
        "services", "network_adapters", "security", "memory", "cpu", "video", "logical_disks", "devices",
        "system_summary", "sensors", "virtual_machine",
    ),
)
