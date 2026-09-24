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

ONBOARD_TYPES = {1: "Other", 2: "Unknown", 3: "Video", 4: "SCSI Controller", 5: "Ethernet", 6: "Token Ring",
                 7: "Sound", 8: "PATA Controller", 9: "SATA Controller", 10: "SAS Controller"}
MEMORY_USE = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "System memory", 4: "Video memory", 5: "Flash memory",
              6: "Non-volatile RAM", 7: "Cache memory"}
MEMORY_LOCATION = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "System board or motherboard", 4: "ISA add-on card",
                   5: "EISA add-on card", 6: "PCI add-on card", 7: "MCA add-on card", 8: "PCMCIA add-on card",
                   9: "Proprietary add-on card", 10: "NuBus"}
UPGRADE = {1: "Other", 2: "Unknown", 3: "Daughter Board", 4: "ZIF Socket", 5: "Replacement/Piggy Back", 6: "None",
           7: "LIF Socket", 8: "Slot 1", 9: "Slot 2", 10: "370 Pin Socket", 11: "Slot A", 12: "Slot M",
           13: "Socket 423", 14: "Socket A (Socket 462)", 15: "Socket 478", 16: "Socket 754", 17: "Socket 940",
           18: "Socket 939", 19: "Socket mPGA604", 20: "Socket LGA771", 21: "Socket LGA775", 22: "Socket S1",
           23: "Socket AM2", 24: "Socket F (1207)", 25: "Socket LGA1366", 26: "Socket G34", 27: "Socket AM3",
           28: "Socket C32", 29: "Socket LGA1156", 30: "Socket LGA1567", 31: "Socket PGA988A", 32: "Socket BGA1288",
           33: "rPGA988B", 34: "BGA1023", 35: "BGA1224", 36: "LGA1155", 37: "LGA1356", 38: "LGA2011", 39: "Socket FS1",
           40: "Socket FS2", 41: "Socket FM1", 42: "Socket FM2", 43: "Socket LGA2011-3", 44: "Socket LGA1356-3",
           45: "Socket LGA1150", 46: "Socket BGA1168", 47: "Socket BGA1234", 48: "Socket BGA1364", 49: "Socket AM4",
           50: "Socket LGA1151", 51: "Socket BGA1356", 52: "Socket BGA1440", 53: "Socket BGA1515", 54: "Socket LGA3647-1",
           55: "Socket SP3", 56: "Socket SP3r2", 57: "Socket LGA2066", 58: "Socket BGA1392", 59: "Socket BGA1510",
           60: "Socket BGA1528", 61: "Socket LGA4189", 62: "Socket LGA1200", 63: "Socket LGA4677", 64: "Socket LGA1700",
           65: "Socket BGA1744", 66: "Socket BGA1781", 67: "Socket BGA1211", 68: "Socket BGA2422", 69: "Socket LGA1211",
           70: "Socket LGA2422", 71: "Socket LGA5773", 72: "Socket BGA5773", 73: "Socket AM5", 74: "Socket SP5",
           75: "Socket SP6", 76: "Socket BGA883", 77: "Socket BGA1190", 78: "Socket BGA4129", 79: "Socket LGA4710",
           80: "Socket LGA7529", 81: "Socket BGA1964", 82: "Socket BGA1792", 83: "Socket BGA2049", 84: "Socket BGA2551",
           85: "Socket LGA1851", 86: "Socket BGA2114", 87: "Socket BGA2833"}

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
        sockets_rows[f"Socket Type{suffix}"] = decode.lookup(UPGRADE, s.get("UpgradeMethod"))
    array_rows = {}
    for i, a in enumerate(rows_of(arrays), 1):
        suffix = "" if i == 1 else f" {i}"
        cap = a.get("MaxCapacityEx") or a.get("MaxCapacity")
        array_rows[f"Maximum Memory{suffix}"] = kb_human(cap) if cap else ""
        array_rows[f"Memory Slots{suffix}"] = a.get("MemoryDevices", "")
        array_rows[f"Error Correction{suffix}"] = decode.lookup(decode.ERROR_CORRECTION, a.get("MemoryErrorCorrection"))
        array_rows[f"Use{suffix}"] = decode.lookup(MEMORY_USE, a.get("Use"))
        array_rows[f"Location{suffix}"] = decode.lookup(MEMORY_LOCATION, a.get("Location"))
    slot_rows_raw = rows_of(slots)
    in_use = sum(1 for s in slot_rows_raw if decode.to_int(s.get("CurrentUsage")) == 4)
    widths: dict[str, int] = {}
    for s in slot_rows_raw:
        w = decode.lookup(decode.SLOT_MAX_DATA_WIDTH, s.get("MaxDataWidth")) or "Unknown"
        widths[w] = widths.get(w, 0) + 1
    slot_rows = {"Slots In Use": f"{in_use} of {len(slot_rows_raw)}" if slot_rows_raw else "",
                 "Slots By Width": ", ".join(f"{k}: {v}" for k, v in widths.items())}
    onboard_rows = [{"Description": o.get("Description", ""), "Type": decode.lookup(ONBOARD_TYPES, o.get("DeviceType")),
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
