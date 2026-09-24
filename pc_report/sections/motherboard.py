"""Motherboard: baseboard identity, CPU socket, memory array, slot usage, onboard devices and connectors."""
from __future__ import annotations

from .. import decode
from ..format import kb_human, yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

BASEBOARD = cim("Win32_BaseBoard", ("Manufacturer", "Product", "Version", "SerialNumber", "Tag"))
SOCKETS = cim("Win32_Processor", ("SocketDesignation", "UpgradeMethod"))
MEMORY_ARRAY = cim("Win32_PhysicalMemoryArray", ("MaxCapacity", "MaxCapacityEx", "MemoryDevices", "MemoryErrorCorrection", "Use", "Location"))
SLOTS = cim("Win32_SystemSlot", ("SlotDesignation", "CurrentUsage", "MaxDataWidth"))
ONBOARD = cim("Win32_OnBoardDevice", ("Description", "DeviceType", "Enabled"))
CONNECTORS = cim("Win32_PortConnector", ("ExternalReferenceDesignator", "InternalReferenceDesignator", "ConnectorType", "PortType"))

ONBOARD_COLUMNS = [("Description", "Description"), ("Type", "Type"), ("Enabled", "Enabled")]
CONNECTOR_COLUMNS = [("External", "External designator"), ("Internal", "Internal designator"),
                     ("Connector", "Connector"), ("Port Type", "Port Type")]


def build(baseboard, sockets, arrays, slots, onboard, connectors) -> dict:
    bb = baseboard or {}
    board = {"Manufacturer": bb.get("Manufacturer", ""), "Model": bb.get("Product", ""), "Version": bb.get("Version", ""),
             "Serial Number": bb.get("SerialNumber", ""), "Tag": bb.get("Tag", "")}
    sockets_rows = {}
    for i, s in enumerate(rows_of(sockets), 1):
        suffix = "" if i == 1 else f" {i}"
        sockets_rows[f"CPU Socket{suffix}"] = s.get("SocketDesignation", "")
        sockets_rows[f"Socket Type{suffix}"] = decode.lookup(decode.CPU_UPGRADE_METHOD, s.get("UpgradeMethod"))
    array_rows = {}
    for i, a in enumerate(rows_of(arrays), 1):
        suffix = "" if i == 1 else f" {i}"
        cap = a.get("MaxCapacityEx") or a.get("MaxCapacity")
        array_rows[f"Maximum Memory{suffix}"] = kb_human(cap) if cap else ""
        array_rows[f"Memory Slots{suffix}"] = a.get("MemoryDevices", "")
        array_rows[f"Error Correction{suffix}"] = decode.lookup(decode.ERROR_CORRECTION, a.get("MemoryErrorCorrection"))
        array_rows[f"Use{suffix}"] = decode.lookup(decode.MEMORY_ARRAY_USE, a.get("Use"))
        array_rows[f"Location{suffix}"] = decode.lookup(decode.MEMORY_ARRAY_LOCATION, a.get("Location"))
    slot_rows_raw = rows_of(slots)
    in_use = sum(1 for s in slot_rows_raw if decode.to_int(s.get("CurrentUsage")) == 4)
    widths: dict[str, int] = {}
    for s in slot_rows_raw:
        w = decode.lookup(decode.SLOT_MAX_DATA_WIDTH, s.get("MaxDataWidth")) or "Unknown"
        widths[w] = widths.get(w, 0) + 1
    slot_rows = {"Slots In Use": f"{in_use} of {len(slot_rows_raw)}" if slot_rows_raw else "",
                 "Slots By Width": ", ".join(f"{k}: {v}" for k, v in widths.items())}
    onboard_rows = [{"Description": o.get("Description", ""), "Type": decode.lookup(decode.ONBOARD_DEVICE_TYPES, o.get("DeviceType")),
                     "Enabled": yes_no(o.get("Enabled"))} for o in rows_of(onboard)]
    conn_rows = [{"External": c.get("ExternalReferenceDesignator", ""), "Internal": c.get("InternalReferenceDesignator", ""),
                  "Connector": decode.lookup(decode.PORT_CONNECTOR_TYPES, c.get("ConnectorType")),
                  "Port Type": decode.lookup(decode.PORT_TYPES, c.get("PortType"))} for c in rows_of(connectors)]
    return {"groups": [{"title": "Board", "rows": board}, {"title": "Processor Socket", "rows": sockets_rows},
                       {"title": "Memory Array", "rows": array_rows}, {"title": "Expansion Slots", "rows": slot_rows}],
            "onboard": onboard_rows, "connectors": conn_rows}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def collect(ctx):
    return build(first_dict(ctx.query("baseboard", BASEBOARD)), ctx.query("sockets", SOCKETS),
                 ctx.query("memory_array", MEMORY_ARRAY), ctx.query("slots", SLOTS),
                 ctx.query("onboard", ONBOARD), ctx.query("connectors", CONNECTORS))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Onboard devices") + list_table(ONBOARD_COLUMNS, data.get("onboard"))
            + sub_heading("External connectors") + list_table(CONNECTOR_COLUMNS, data.get("connectors")))


SECTION = Section(key="motherboard", title="Motherboard", group="Hardware", collect=collect, render=render)
