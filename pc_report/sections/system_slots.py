"""System Slots: expansion slots with usage, width, connector, hot-plug and PCI address."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..ps import cim
from ..section import Section, list_table, rows_of

SCRIPT = cim("Win32_SystemSlot", ("SlotDesignation", "CurrentUsage", "MaxDataWidth", "ConnectorType", "Status",
                                  "SupportsHotPlug", "BusNumber", "DeviceNumber", "FunctionNumber", "Shared", "Number"))

COLUMNS = [("Designation", "Designation"), ("Usage", "Usage"), ("Data Width", "Data Width"), ("Connector", "Connector"),
           ("Bus / Device / Function", "Bus / Device / Function"), ("Hot Plug", "Hot Plug"), ("Shared", "Shared"),
           ("Status", "Status")]


def build(raw) -> dict:
    rows = []
    for s in rows_of(raw):
        parts = [decode.to_int(s.get("BusNumber")), decode.to_int(s.get("DeviceNumber")),
                 decode.to_int(s.get("FunctionNumber"))]
        bdf = " / ".join(str(p) for p in parts) if all(p is not None for p in parts) else ""
        rows.append({"Designation": s.get("SlotDesignation", ""), "Usage": decode.lookup(decode.SLOT_USAGE, s.get("CurrentUsage")),
                     "Data Width": decode.lookup(decode.SLOT_MAX_DATA_WIDTH, s.get("MaxDataWidth")),
                     "Connector": decode.lookup(decode.PORT_CONNECTOR_TYPES, s.get("ConnectorType")),
                     "Bus / Device / Function": bdf, "Hot Plug": yes_no(s.get("SupportsHotPlug")),
                     "Shared": yes_no(s.get("Shared")), "Status": s.get("Status", "")})
    rows.sort(key=lambda row: (str(row["Designation"]).casefold(), row["Bus / Device / Function"]))
    return {"rows": rows}


def collect(ctx):
    return build(ctx.query("slots", SCRIPT))


def render(data, ctx):
    return list_table(COLUMNS, (data or {}).get("rows") if isinstance(data, dict) else None)


SECTION = Section(key="system_slots", title="System Slots", group="Hardware", collect=collect, render=render)
