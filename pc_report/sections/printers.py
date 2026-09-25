"""Printers: every queue with driver, port, sharing, status and offline state; spooler service state."""
from __future__ import annotations

import re

from .. import decode
from ..format import yes_no
from ..ps import cim
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

PRINTERS_SCRIPT = cim("Win32_Printer", ("Name", "DriverName", "PortName", "Default", "Shared", "ShareName", "Network", "Local",
                                        "PrinterStatus", "DetectedErrorState", "ExtendedPrinterStatus", "Location",
                                        "WorkOffline", "Comment", "PrintProcessor", "Priority"))
SPOOLER_SCRIPT = cim("Win32_Service", ("State", "StartMode"), where="Name='Spooler'")

COLUMNS = [("Name", "Name"), ("Driver", "Driver"), ("Port", "Port"), ("Port Type", "Port Type"), ("Status", "Status"),
           ("Error State", "Error State"), ("Extended Status", "Extended Status"), ("Default", "Default"),
           ("Shared", "Shared"), ("Share Name", "Share Name"), ("Network", "Network"), ("Offline", "Offline"),
           ("Location", "Location"), ("Comment", "Comment"), ("Print Processor", "Print Processor"),
           ("Priority", "Priority")]


def port_kind(port_name) -> str:
    port = str(port_name or "")
    upper = port.upper()
    if upper.startswith("WSD-"):
        return "WSD"
    bare_ipv4 = re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", port)
    bare_hostname = "." in port and re.fullmatch(r"_?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", port)
    if upper.startswith("IP_") or bare_ipv4 or bare_hostname:
        return "TCP/IP"
    if port.startswith("\\\\"):
        return "Network share"
    if re.fullmatch(r"USB\d*", upper):
        return "USB"
    if re.fullmatch(r"(?:LPT|COM)\d+", upper):
        return "Local"
    if upper in {"NUL:", "PORTPROMPT:", "SHRFAX:", "FILE:"}:
        return "Virtual"
    if "MICROSOFT.OFFICE" in upper or "_S-1-5-21" in upper:
        return "App"
    return "Other"


def build(printers, spooler) -> dict:
    rows = [{"Name": p.get("Name", ""), "Driver": p.get("DriverName", ""), "Port": p.get("PortName", ""),
             "Port Type": port_kind(p.get("PortName")), "Status": decode.lookup(decode.PRINTER_STATUS, p.get("PrinterStatus")),
             "Error State": decode.lookup(decode.PRINTER_ERROR_STATE, p.get("DetectedErrorState")),
             "Extended Status": decode.lookup(decode.PRINTER_EXTENDED_STATUS, p.get("ExtendedPrinterStatus")),
             "Default": yes_no(p.get("Default")),
             "Shared": yes_no(p.get("Shared")), "Share Name": p.get("ShareName") or "", "Network": yes_no(p.get("Network")),
             "Offline": yes_no(p.get("WorkOffline")), "Location": p.get("Location") or "", "Comment": p.get("Comment") or "",
             "Print Processor": p.get("PrintProcessor", ""), "Priority": p.get("Priority", "")} for p in rows_of(printers)]
    rows.sort(key=lambda r: (r["Default"] != "Yes", str(r["Name"]).lower()))
    spooler = first_dict(spooler)
    summary = {"Printers": len(rows), "Default Printer": next((r["Name"] for r in rows if r["Default"] == "Yes"), "None"),
               "Network Printers": sum(1 for r in rows if r["Network"] == "Yes"),
               "Offline": ", ".join(r["Name"] for r in rows if r["Offline"] == "Yes") or "None",
               "Print Spooler": f"{spooler.get('State')} ({spooler.get('StartMode')})" if spooler.get("State") else "Not found"}
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.query("printers", PRINTERS_SCRIPT, timeout=45), ctx.query("spooler", SPOOLER_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Printers") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="printers", title="Printers", group="Hardware", collect=collect, render=render, timeout=45)
