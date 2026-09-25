"""Sensors: ACPI thermal zones, fans, probes, battery and a one-second performance-counter sample."""
from __future__ import annotations

import re

from .. import decode
from ..format import bitrate_to_mbps, bytes_human, yes_no
from ..ps import cim
from ..section import Section, flatten_groups, kv_groups, list_table, rows_of, sub_heading

THERMAL_SCRIPT = cim("MSAcpi_ThermalZoneTemperature", ("InstanceName", "CurrentTemperature", "CriticalTripPoint",
                                                        "PassiveTripPoint", "ActiveTripPoint"), namespace="root/wmi")
FANS_SCRIPT = cim("Win32_Fan", ("Name", "DesiredSpeed", "Status", "ActiveCooling"))
PROBES_SCRIPT = ("[pscustomobject]@{ Temperature = @(" + cim("Win32_TemperatureProbe", ("Name", "CurrentReading", "Status"))
                 + "); Voltage = @(" + cim("Win32_VoltageProbe", ("Name", "CurrentReading", "Status")) + ") }")
BATTERY_SCRIPT = cim("Win32_Battery", ("Name", "BatteryStatus", "EstimatedChargeRemaining", "EstimatedRunTime",
                                       "DesignVoltage", "Chemistry"))
COUNTERS_SCRIPT = r"""
$paths = @('\Processor Information(_Total)\% Processor Utility', '\Memory\% Committed Bytes In Use', '\Memory\Available MBytes',
           '\PhysicalDisk(*)\% Disk Time', '\GPU Engine(*)\Utilization Percentage',
           '\GPU Adapter Memory(*)\Dedicated Usage', '\Network Interface(*)\Bytes Total/sec')
foreach ($p in $paths) {
  try { (Get-Counter -Counter $p -SampleInterval 1 -MaxSamples 1 -ErrorAction Stop).CounterSamples | ForEach-Object {
    [pscustomobject]@{ Path = $_.Path; InstanceName = $_.InstanceName; CookedValue = [double]$_.CookedValue } } } catch {}
}
"""

THERMAL_COLUMNS = [("Zone", "Zone"), ("Temperature", "Temperature"), ("Passive Trip", "Passive trip"), ("Critical", "Critical")]
FAN_COLUMNS = [("Name", "Name"), ("Speed", "Desired speed"), ("Active Cooling", "Active cooling"), ("Status", "Status")]
PROBE_COLUMNS = [("Kind", "Kind"), ("Name", "Name"), ("Reading", "Reading"), ("Status", "Status")]
DISK_COLUMNS = [("Disk", "Disk"), ("Active", "Active time")]
GPU_COLUMNS = [("Adapter", "Adapter (LUID)"), ("Dedicated Memory In Use", "Dedicated Memory In Use")]
NIC_COLUMNS = [("Interface", "Interface"), ("Throughput", "Throughput")]


def _nonnegative(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _celsius(tenths_kelvin):
    """ACPI reports tenths of Kelvin; do the subtraction in hundredths to avoid float rounding surprises."""
    n = _nonnegative(tenths_kelvin)
    if n is None:
        return ""
    celsius = (n * 10 - 27315) / 100
    return f"{celsius:.2f} °C" if -40.0 <= celsius <= 150.0 else ""


def _lc(sample) -> str:
    return str(sample.get("Path", "")).lower()


def _percent(value) -> str:
    n = _nonnegative(value)
    return f"{n:.1f} %" if n is not None else ""


def gpu_by_engine(samples) -> dict[str, float]:
    display_names = {
        "3d": "3D",
        "videodecode": "Video Decode",
        "videoencode": "Video Encode",
        "videoprocessing": "Video Processing",
        "copy": "Copy",
        "compute": "Compute",
        "security": "Security",
    }
    totals = {}
    for sample in samples:
        if "gpu engine" not in _lc(sample):
            continue
        match = re.search(r"engtype_([a-z0-9_]+)$", str(sample.get("InstanceName", "")).lower())
        value = _nonnegative(sample.get("CookedValue"))
        if not match or value is None:
            continue
        raw_name = match.group(1)
        display = display_names.get(raw_name, raw_name.title())
        totals[display] = totals.get(display, 0.0) + value
    return {name: min(total, 100.0) for name, total in totals.items()}


def missing_counter_families(samples) -> list[str]:
    families = (
        ("% processor utility", "Processor Information"),
        ("% committed bytes in use", "Memory"),
        ("physicaldisk", "PhysicalDisk"),
        ("gpu engine", "GPU Engine"),
        ("gpu adapter memory", "GPU Adapter Memory"),
        ("network interface", "Network Interface"),
    )
    paths = {_lc(sample) for sample in samples}
    return [display for fragment, display in families if not any(fragment in path for path in paths)]


def build(thermal, fans, probes, battery, counters) -> dict:
    thermal_rows = [{"Zone": str(t.get("InstanceName", "")).rsplit("\\", 1)[-1],
                     "Temperature": _celsius(t.get("CurrentTemperature")),
                     "Passive Trip": _celsius(t.get("PassiveTripPoint")),
                     "Critical": _celsius(t.get("CriticalTripPoint"))}
                    for t in rows_of(thermal)]
    fan_rows = []
    for f in rows_of(fans):
        speed = _nonnegative(f.get("DesiredSpeed"))
        fan_rows.append({"Name": f.get("Name", ""), "Speed": f"{speed:g} RPM" if speed is not None else "",
                         "Active Cooling": yes_no(f.get("ActiveCooling")), "Status": f.get("Status", "")})
    probes = probes if isinstance(probes, dict) else {}
    probe_rows = []
    for p in rows_of(probes.get("Temperature")):
        probe_rows.append({"Kind": "Temperature", "Name": p.get("Name", ""),
                           "Reading": _celsius(p.get("CurrentReading")), "Status": p.get("Status", "")})
    for p in rows_of(probes.get("Voltage")):
        mv = _nonnegative(p.get("CurrentReading"))
        probe_rows.append({"Kind": "Voltage", "Name": p.get("Name", ""),
                           "Reading": f"{mv / 1000:.3f} V" if mv is not None else "",
                           "Status": p.get("Status", "")})
    battery_rows = {}
    for i, b in enumerate(rows_of(battery), 1):
        suffix = "" if i == 1 else f" {i}"
        runtime = _nonnegative(b.get("EstimatedRunTime"))
        charge = _nonnegative(b.get("EstimatedChargeRemaining"))
        voltage = _nonnegative(b.get("DesignVoltage"))
        battery_rows.update({
            f"Battery{suffix}": b.get("Name", ""),
            f"Battery Status{suffix}": decode.lookup(decode.BATTERY_STATUS, b.get("BatteryStatus")),
            f"Charge{suffix}": f"{charge:g} %" if charge is not None else "",
            f"Estimated Runtime{suffix}": f"{runtime:g} min" if runtime and runtime < 71582788 else "",
            f"Design Voltage{suffix}": f"{voltage / 1000:.1f} V" if voltage else "",
            f"Chemistry{suffix}": decode.lookup(decode.BATTERY_CHEMISTRY, b.get("Chemistry")),
        })
    if not battery_rows:
        battery_rows = {"Battery": "None (desktop or no battery reported)"}

    samples = rows_of(counters)

    def one(fragment):
        for sample in samples:
            if fragment in _lc(sample):
                return _nonnegative(sample.get("CookedValue"))
        return None

    cpu, committed, available = one("% processor utility"), one("% committed bytes in use"), one("available mbytes")
    live = {
        "CPU Utility": _percent(cpu),
        "Memory Committed": _percent(committed),
        "Memory Available": f"{int(available)} MB" if available is not None else "",
    }
    gpu_samples = [sample for sample in samples if "gpu engine" in _lc(sample)]
    engine_totals = gpu_by_engine(gpu_samples)
    if gpu_samples:
        engine_totals.setdefault("3D", 0.0)
    preferred = ("3D", "Video Decode", "Video Encode", "Video Processing", "Copy", "Compute")
    engine_order = {name: index for index, name in enumerate(preferred)}
    for engine, total in sorted(engine_totals.items(),
                                key=lambda item: (engine_order.get(item[0], len(preferred)), item[0])):
        if total > 0 or engine == "3D":
            live[f"GPU {engine} Utilization"] = _percent(total)
    live["Temperatures"] = (
        "CPU/GPU core temperatures need a vendor tool (HWiNFO, vendor utilities); only ACPI zones are shown."
    )
    disks = [{"Disk": s.get("InstanceName", ""), "Active": _percent(s.get("CookedValue"))}
             for s in samples if "physicaldisk" in _lc(s) and s.get("InstanceName") != "_total"]
    gpus = []
    for sample in samples:
        if "gpu adapter memory" not in _lc(sample):
            continue
        usage = _nonnegative(sample.get("CookedValue"))
        gpus.append({"Adapter": sample.get("InstanceName", ""),
                     "Dedicated Memory In Use": bytes_human(int(usage)) if usage is not None else ""})
    nics = []
    for sample in samples:
        if "network interface" not in _lc(sample):
            continue
        rate = _nonnegative(sample.get("CookedValue"))
        nics.append({"Interface": sample.get("InstanceName", ""),
                     "Throughput": bitrate_to_mbps(int(rate * 8)) if rate is not None else ""})
    return {"groups": [{"title": "Live Sample (1 s)", "rows": live}, {"title": "Battery", "rows": battery_rows}],
            "thermal": thermal_rows, "fans": fan_rows, "probes": probe_rows, "disks": disks, "gpus": gpus, "nics": nics}


def flatten(data) -> dict:
    return flatten_groups(data)


def collect(ctx):
    thermal = ctx.query("thermal", THERMAL_SCRIPT)
    fans = ctx.query("fans", FANS_SCRIPT)
    probes = ctx.query("probes", PROBES_SCRIPT)
    battery = ctx.query("battery", BATTERY_SCRIPT)
    counters = ctx.query("counters", COUNTERS_SCRIPT, timeout=60)
    if not thermal:
        ctx.note("ACPI thermal zones unavailable on this system.")
    if not counters:
        ctx.note("Performance counters unavailable on this system.")
    else:
        missing = missing_counter_families(rows_of(counters))
        if missing:
            ctx.note("Performance counter sets unavailable on this system: " + ", ".join(missing) + ".")
    return build(thermal, fans, probes, battery, counters)


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
