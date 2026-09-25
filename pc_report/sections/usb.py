"""USB controllers, hubs, devices, topology details, and selective suspend."""
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
  $props = @{}
  try {
    Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue | ForEach-Object {
      $props[$_.KeyName] = $_.Data
    }
  } catch {}
  [pscustomobject]@{
    InstanceId = $_.InstanceId
    FriendlyName = [string]$_.FriendlyName
    Class = [string]$_.Class
    Manufacturer = [string]$_.Manufacturer
    Status = [string]$_.Status
    Present = $_.Present
    Service = [string]$_.Service
    ParentInstanceId = [string]$props['DEVPKEY_Device_Parent']
    Location = [string]$props['DEVPKEY_Device_LocationInfo']
    Address = $props['DEVPKEY_Device_Address']
    Speed = [string]$props['DEVPKEY_Device_UsbSpeed']
    Problem = $props['DEVPKEY_Device_ProblemCode']
  }
}
"""
SUSPEND_ARGS = ["powercfg", "/q", "SCHEME_CURRENT", "2a737441-1930-4402-8d77-b2bebba308a3",
                "48e6b7a6-50f5-4782-a5d4-53bb50f7e3f1"]

_VIDPID = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")
_AC = re.compile(r"Current AC Power Setting Index:\s*0x([0-9A-Fa-f]+)", re.IGNORECASE)
_DC = re.compile(r"Current DC Power Setting Index:\s*0x([0-9A-Fa-f]+)", re.IGNORECASE)

CTRL_COLUMNS = [("Name", "Name"), ("Manufacturer", "Manufacturer"), ("USB Version", "USB Version"),
                ("Status", "Status"), ("PNPDeviceID", "PnP Device ID")]
HUB_COLUMNS = [("Name", "Name"), ("Status", "Status"), ("DeviceID", "Device ID")]
DEV_COLUMNS = [("Name", "Name"), ("VID / PID", "VID / PID"), ("Class", "Class"),
               ("Manufacturer", "Manufacturer"), ("Speed", "Speed"), ("Service", "Service"),
               ("Status", "Status"), ("Problem", "Problem"), ("Present", "Present"),
               ("ParentInstanceId", "Parent"), ("Location", "Location"), ("InstanceId", "Instance")]


def _suspend(text: str, rx) -> str:
    if not text:
        return ""
    match = rx.search(text)
    if not match:
        return "Unknown"
    try:
        return "Enabled" if int(match.group(1), 16) else "Disabled"
    except (TypeError, ValueError):
        return "Unknown"


def _problem(value) -> str:
    code = decode.to_int(value)
    if code in (None, 0):
        return ""
    return f"{code}: {decode.lookup(decode.PNP_ERROR_CODES, code)}"


def _device_sort_key(row: dict) -> tuple:
    parent = str(row.get("ParentInstanceId") or "").casefold()
    location = str(row.get("Location") or "").casefold()
    address = decode.to_int(row.get("_Address"))
    return (parent, location, address is None, address or 0, str(row.get("Name") or "").casefold(),
            str(row.get("InstanceId") or "").casefold())


def build(controllers, hubs, devices, suspend_text) -> dict:
    ctrl = [{"Name": c.get("Name", ""), "Manufacturer": c.get("Manufacturer", ""),
             "USB Version": decode.lookup(decode.USB_PROTOCOLS, c.get("ProtocolSupported")),
             "Status": c.get("Status", ""), "PNPDeviceID": c.get("PNPDeviceID", "")}
            for c in rows_of(controllers)]
    ctrl.sort(key=lambda row: (str(row["Name"]).casefold(), str(row["PNPDeviceID"]).casefold()))
    hub_rows = [{"Name": h.get("Name") or h.get("Description", ""), "Status": h.get("Status", ""),
                 "DeviceID": h.get("DeviceID", ""), "PNPDeviceID": h.get("PNPDeviceID", "")}
                for h in rows_of(hubs)]
    hub_rows.sort(key=lambda row: (str(row["DeviceID"]).casefold(), str(row["Name"]).casefold()))

    dev_rows = []
    for device in rows_of(devices):
        instance_id = str(device.get("InstanceId") or "")
        match = _VIDPID.search(instance_id)
        parent = device.get("ParentInstanceId")
        if parent in (None, ""):
            parent = device.get("Parent", "")
        dev_rows.append({
            "Name": device.get("FriendlyName") or "",
            "VID / PID": f"{match.group(1).upper()} / {match.group(2).upper()}" if match else "",
            "Class": device.get("Class", ""),
            "Manufacturer": device.get("Manufacturer", ""),
            "Speed": device.get("Speed", ""),
            "Service": device.get("Service", ""),
            "Status": device.get("Status", ""),
            "Problem": _problem(device.get("Problem", device.get("ConfigManagerErrorCode"))),
            "Present": yes_no(device.get("Present")),
            "ParentInstanceId": parent,
            "Location": device.get("Location", ""),
            "InstanceId": instance_id,
            "_Address": device.get("Address"),
        })
    dev_rows.sort(key=_device_sort_key)
    for row in dev_rows:
        del row["_Address"]

    summary = {
        "Controllers": len(ctrl),
        "Hubs": len(hub_rows),
        "USB Devices Present": sum(1 for row in dev_rows if row["Present"] == "Yes"),
        "USB Devices Not Present": sum(1 for row in dev_rows if row["Present"] != "Yes"),
        "Selective Suspend (AC)": _suspend(suspend_text, _AC),
        "Selective Suspend (DC)": _suspend(suspend_text, _DC),
    }
    return {"groups": [{"title": "Summary", "rows": summary}], "controllers": ctrl,
            "hubs": hub_rows, "devices": dev_rows}


def hasp_devices(data) -> list[str]:
    out = []
    for row in rows_of((data or {}).get("devices") if isinstance(data, dict) else None):
        vid = str(row.get("VID / PID") or "")[:4]
        name = str(row.get("Name") or "")
        if vid == "0529" or re.search(r"hasp|sentinel", name, re.IGNORECASE):
            out.append(name)
    return out


def collect(ctx):
    suspend = ctx.text("selective_suspend", SUSPEND_ARGS)
    data = build(ctx.query("controllers", CTRL_SCRIPT), ctx.query("hubs", HUBS_SCRIPT),
                 ctx.query("devices", DEVICES_SCRIPT, timeout=90), suspend)
    summary = data["groups"][0]["rows"]
    if not suspend:
        summary["Selective Suspend (AC)"] = "Unknown"
        summary["Selective Suspend (DC)"] = "Unknown"
        ctx.note("USB selective suspend: powercfg output was unavailable")
    elif "Unknown" in (summary["Selective Suspend (AC)"], summary["Selective Suspend (DC)"]):
        ctx.note("USB selective suspend: powercfg output was not recognised (possibly localised)")
    return data


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("Controllers") + list_table(CTRL_COLUMNS, data.get("controllers"))
            + sub_heading("Hubs") + list_table(HUB_COLUMNS, data.get("hubs"))
            + sub_heading("Devices") + list_table(DEV_COLUMNS, data.get("devices")))


SECTION = Section(key="usb", title="USB", group="Hardware", collect=collect, render=render, timeout=90)
