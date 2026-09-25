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
    dev_rows.sort(key=lambda row: str(row["Name"]).casefold())
    ep_rows = [{"Name": e.get("FriendlyName", ""), "Direction": _direction(e.get("InstanceId")), "Status": e.get("Status", ""),
                "Present": yes_no(e.get("Present")), "Instance": e.get("InstanceId", "")} for e in rows_of(endpoints)]
    ep_rows.sort(key=lambda r: (r["Direction"] != "Playback", str(r["Name"]).lower(), str(r["Instance"]).lower()))
    playback = next((d.get("Description", "") for d in dx_list(dx, "SoundDevices", "SoundDevice")
                     if str(d.get("DefaultSoundPlayback")).lower() == "true"), "")
    capture = next((d.get("Description", "") for d in dx_list(dx, "SoundCaptureDevices", "SoundCaptureDevice")
                    if str(d.get("DefaultSoundRecording")).lower() == "true"), "")
    summary = {"Sound Devices": len(dev_rows), "Playback Endpoints": sum(1 for r in ep_rows if r["Direction"] == "Playback"),
               "Capture Endpoints": sum(1 for r in ep_rows if r["Direction"] == "Capture"),
               "Default Playback": playback, "Default Capture": capture}
    return {"groups": [{"title": "Summary", "rows": summary}], "devices": dev_rows, "endpoints": ep_rows}


def collect(ctx):
    dx = ctx.shared("dxdiag")
    if dx is None:
        ctx.note("dxdiag: unavailable")
    return build(ctx.query("devices", DEV_SCRIPT), ctx.query("endpoints", ENDPOINTS_SCRIPT),
                 ctx.query("drivers", DRIVERS_SCRIPT, timeout=60), dx)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Devices") + list_table(DEV_COLUMNS, data.get("devices"))
            + sub_heading("Endpoints") + list_table(EP_COLUMNS, data.get("endpoints")))


SECTION = Section(key="sound", title="Sound", group="Hardware", collect=collect, render=render, timeout=120)
