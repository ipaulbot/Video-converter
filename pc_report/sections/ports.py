"""Ports: external connectors, serial ports (WMI and SERIALCOMM registry), parallel ports."""
from __future__ import annotations

import re

from .. import decode
from ..ps import cim, reg_props
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

CONNECTORS_SCRIPT = cim("Win32_PortConnector", ("ExternalReferenceDesignator", "ConnectorType", "PortType"))
SERIAL_SCRIPT = cim("Win32_SerialPort", ("Name", "DeviceID", "Description", "MaxBaudRate", "ProviderType", "Status", "PNPDeviceID"))
SERIALCOMM_SCRIPT = reg_props(r"HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM")
PARALLEL_SCRIPT = cim("Win32_ParallelPort", ("Name", "DeviceID", "Status", "PNPDeviceID"))

CONN_COLUMNS = [("Designator", "Designator"), ("Connector", "Connector"), ("Port Type", "Port Type")]
SERIAL_COLUMNS = [("Name", "Name"), ("Device", "Device"), ("Description", "Description"), ("Max Baud Rate", "Max Baud Rate"),
                  ("Provider", "Provider"), ("Status", "Status"), ("PnP Device ID", "PnP Device ID")]
SERIALCOMM_COLUMNS = [("Port", "Port"), ("Device", "Device object")]
PARALLEL_COLUMNS = [("Name", "Name"), ("Device", "Device"), ("Status", "Status"), ("PnP Device ID", "PnP Device ID")]

_COM_NUMBER = re.compile(r"^COM(\d+)$", re.IGNORECASE)


def _port_key(value) -> tuple:
    text = str(value or "")
    match = _COM_NUMBER.fullmatch(text)
    return (0, int(match.group(1))) if match else (1, text.casefold())


def _serialcomm_rows(value) -> list[dict]:
    if isinstance(value, dict) and not ({"Name", "Value"} & set(value)):
        return [{"Name": name, "Value": port} for name, port in value.items()]
    return rows_of(value)


def build(connectors, serial, serialcomm, parallel) -> dict:
    conn = [{"Designator": c.get("ExternalReferenceDesignator", ""),
             "Connector": decode.lookup(decode.PORT_CONNECTOR_TYPES, c.get("ConnectorType")),
             "Port Type": decode.lookup(decode.PORT_TYPES, c.get("PortType"))} for c in rows_of(connectors)]
    ser = []
    for item in rows_of(serial):
        baud = decode.to_int(item.get("MaxBaudRate"))
        ser.append({
            "Name": item.get("Name", ""),
            "Device": item.get("DeviceID", ""),
            "Description": item.get("Description", ""),
            "Max Baud Rate": f"{baud} baud" if baud is not None else "",
            "Provider": item.get("ProviderType", ""),
            "Status": item.get("Status", ""),
            "PnP Device ID": item.get("PNPDeviceID", ""),
        })
    ser.sort(key=lambda row: (_port_key(row["Device"]), str(row["Name"]).casefold()))
    comm = sorted(
        [{"Port": row.get("Value", ""), "Device": row.get("Name", "")}
         for row in _serialcomm_rows(serialcomm)],
        key=lambda row: _port_key(row["Port"]),
    )
    par = [{"Name": p.get("Name", ""), "Device": p.get("DeviceID", ""), "Status": p.get("Status", ""),
            "PnP Device ID": p.get("PNPDeviceID", "")} for p in rows_of(parallel)]
    summary = {"External Connectors": len(conn), "Serial Ports (WMI)": len(ser),
               "COM Ports Registered": ", ".join(str(r["Port"]) for r in comm) or "None",
               "Parallel Ports": len(par)}
    return {"groups": [{"title": "Summary", "rows": summary}], "connectors": conn, "serial": ser,
            "serialcomm": comm, "parallel": par}


def collect(ctx):
    return build(ctx.query("connectors", CONNECTORS_SCRIPT), ctx.query("serial", SERIAL_SCRIPT),
                 ctx.query("serialcomm", SERIALCOMM_SCRIPT), ctx.query("parallel", PARALLEL_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("External connectors") + list_table(CONN_COLUMNS, data.get("connectors"))
            + sub_heading("Serial ports (WMI)") + list_table(SERIAL_COLUMNS, data.get("serial"))
            + sub_heading("Serial ports (registry SERIALCOMM)") + list_table(SERIALCOMM_COLUMNS, data.get("serialcomm"))
            + sub_heading("Parallel ports") + list_table(PARALLEL_COLUMNS, data.get("parallel")))


SECTION = Section(key="ports", title="Ports", group="Hardware", collect=collect, render=render)
