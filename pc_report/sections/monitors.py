"""Monitors: EDID identity from WMI, physical size, native/current mode from dxdiag, desktop layout from Screen.AllScreens."""
from __future__ import annotations

import math

from .. import decode
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

MON_COLUMNS = [("Manufacturer", "Manufacturer"), ("Model", "Model"), ("Product Code", "Product Code"), ("Serial Number", "Serial Number"),
               ("Manufactured", "Manufactured"), ("Diagonal", "Diagonal"), ("Native Mode", "Native Mode"), ("Current Mode", "Current Mode"),
               ("Output", "Output"), ("Attached To", "Attached To"), ("Active", "Active")]
SCREEN_COLUMNS = [("Device", "Device"), ("Resolution", "Resolution"), ("Position", "Position"), ("Bits Per Pixel", "Bits Per Pixel"), ("Primary", "Primary")]


def pnp_vendor(code: str) -> str:
    return decode.PNP_MONITOR_VENDORS.get(str(code or "").upper(), str(code or ""))


def _edid_text(value) -> str:
    if not isinstance(value, (list, tuple)):
        return str(value or "")
    chars = []
    for code in value:
        try:
            number = int(code)
        except (TypeError, ValueError):
            continue
        if number == 0:
            break
        try:
            chars.append(chr(number))
        except (OverflowError, ValueError):
            continue
    return "".join(chars)


def _diagonal(h_cm, v_cm) -> str:
    try:
        h, v = float(h_cm), float(v_cm)
    except (TypeError, ValueError):
        return ""
    if h <= 0 or v <= 0:
        return ""
    inches = math.floor((math.hypot(h, v) / 2.54) * 10) / 10
    return f'{inches:.1f}" ({int(h)} x {int(v)} cm)'


def build(wmi, params, screens, dx) -> dict:
    params_by = {str(p.get("InstanceName") or ""): p for p in rows_of(params)}
    dxs = dx_list(dx, "DisplayDevices", "DisplayDevice")
    monitors = []
    for m in rows_of(wmi):
        inst = str(m.get("InstanceName") or "")
        p = params_by.get(inst, {})
        pnp_id = inst.split("\\")[1] if "\\" in inst else ""
        d = next((x for x in dxs if str(x.get("MonitorId") or "").upper() == pnp_id.upper()), {})
        manufacturer = _edid_text(m.get("Manufacturer") if "Manufacturer" in m else m.get("ManufacturerName"))
        model = _edid_text(m.get("Model") if "Model" in m else m.get("UserFriendlyName"))
        serial = _edid_text(m.get("Serial") if "Serial" in m else m.get("SerialNumberID"))
        product = _edid_text(m.get("ProductCode") if "ProductCode" in m else m.get("ProductCodeID"))
        monitors.append({
            "Manufacturer": pnp_vendor(manufacturer), "Model": model or d.get("MonitorModel", ""),
            "Product Code": product, "Serial Number": serial,
            "Manufactured": f"{m.get('Year')}, week {m.get('Week')}" if m.get("Year") else "",
            "Diagonal": _diagonal(p.get("MaxHorizontalImageSize"), p.get("MaxVerticalImageSize")),
            "Native Mode": d.get("NativeMode", ""), "Current Mode": d.get("CurrentMode", ""), "Output": d.get("OutputType", ""),
            "Attached To": d.get("CardName", ""), "Active": yes_no(m.get("Active")),
        })
    monitors.sort(key=lambda item: (
        str(item["Manufacturer"]).casefold(),
        str(item["Model"]).casefold(),
        str(item["Product Code"]).casefold(),
    ))
    screen_rows = [{"Device": s.get("DeviceName", ""), "Resolution": f"{s.get('Width')} x {s.get('Height')}",
                    "Position": f"{s.get('X')}, {s.get('Y')}", "Bits Per Pixel": s.get("BitsPerPixel", ""),
                    "Primary": yes_no(s.get("Primary"))} for s in rows_of(screens)]
    screen_rows.sort(key=lambda item: str(item["Device"]).casefold())
    summary = {"Monitors": len(monitors), "Active Monitors": sum(1 for m in monitors if m["Active"] == "Yes"),
               "Desktop Screens": len(screen_rows)}
    return {"groups": [{"title": "Summary", "rows": summary}], "monitors": monitors, "screens": screen_rows}


def collect(ctx):
    dx = ctx.shared("dxdiag")
    if dx is None:
        ctx.note("dxdiag: unavailable")
    return build(ctx.query("wmi_monitors", WMI_SCRIPT), ctx.query("params", PARAMS_SCRIPT),
                 ctx.query("screens", SCREENS_SCRIPT, timeout=30), dx)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Monitors") + list_table(MON_COLUMNS, data.get("monitors"))
            + sub_heading("Desktop layout") + list_table(SCREEN_COLUMNS, data.get("screens")))


SECTION = Section(key="monitors", title="Monitors", group="Hardware", collect=collect, render=render, timeout=120)
