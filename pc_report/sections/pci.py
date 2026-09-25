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
           ("Driver Version", "Driver Version"), ("Driver Date", "Driver Date"), ("Status", "Status"),
           # The key must stay InstanceId so redaction recognises the PnP instance path.
           ("InstanceId", "Instance")]
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
                     "Status": d.get("Status") or "", "InstanceId": inst})
    rows.sort(key=lambda r: (r["Bus / Device / Function"] == "", r["Bus / Device / Function"], r["Name"].lower()))
    vendors: dict[str, int] = {}
    for r in rows:
        vendors[r["Vendor"]] = vendors.get(r["Vendor"], 0) + 1
    summary = {"PCI Devices": len(rows), "Vendors": ", ".join(f"{k} ({v})" for k, v in sorted(vendors.items()))}
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    pnp = ctx.shared("pnp_entities")
    if pnp is None:
        ctx.note("pnp_entities: unavailable")
    return build(pnp, ctx.query("pnp_properties", PROPS_SCRIPT, timeout=90))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Devices") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="pci", title="PCI", group="Hardware", collect=collect, render=render, timeout=90)
