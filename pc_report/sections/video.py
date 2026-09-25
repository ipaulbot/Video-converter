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
            "Adapter RAM Source": "Driver registry (64-bit)" if reg_ram else ("WMI (32-bit capped)" if wmi_ram else ""),
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
    adapters.sort(key=lambda item: str(item.get("name") or "").casefold())
    sysinfo = dx.get("SystemInformation", {}) if isinstance(dx, dict) else {}
    summary = {"Adapters": len(adapters), "DirectX Version": sysinfo.get("DirectXVersion", "") if isinstance(sysinfo, dict) else "",
               "Memory Note": "Adapter RAM comes from the driver registry key; WMI caps at 4 GB." if any(
                   decode.to_int(r.get("qwMemorySize")) for r in regs) else ""}
    return {"groups": [{"title": "Summary", "rows": summary}], "adapters": adapters}


def names(data) -> list[str]:
    return [a.get("name", "") for a in rows_of((data or {}).get("adapters")) if a.get("name")] if isinstance(data, dict) else []


def collect(ctx):
    dx = ctx.shared("dxdiag")
    if dx is None:
        ctx.note("dxdiag: unavailable")
    return build(ctx.query("controllers", CTRL_SCRIPT), ctx.query("registry", REG_SCRIPT), dx)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    for a in rows_of(data.get("adapters")):
        out.append(sub_heading(a.get("name", "")) + kv_groups(a.get("groups")))
    return "".join(out)


SECTION = Section(key="video", title="Video", group="Hardware", collect=collect, render=render, timeout=120)
