"""Services: every Win32 service with state, start mode, account and binary path."""
from __future__ import annotations

from ..format import yes_no
from ..ps import cim
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

PROPS = ("Name", "DisplayName", "State", "StartMode", "StartName", "PathName", "ProcessId", "Description",
         "ServiceType", "DelayedAutoStart", "ExitCode")
SCRIPT = cim("Win32_Service", PROPS) + " | Sort-Object DisplayName"

COLUMNS = [("Display Name", "Display Name"), ("Name", "Name"), ("State", "State"), ("Start Mode", "Start Mode"),
           ("Start Name", "Log On As"), ("PID", "PID"), ("Type", "Type"), ("Exit Code", "Exit Code"),
           ("Path", "Path"), ("Description", "Description")]


def _start_mode(s):
    mode = str(s.get("StartMode") or "")
    if mode == "Auto":
        return "Automatic (Delayed)" if yes_no(s.get("DelayedAutoStart")) == "Yes" else "Automatic"
    return mode


def build(raw) -> dict:
    rows = [{
        "Display Name": s.get("DisplayName", ""), "Name": s.get("Name", ""), "State": s.get("State", ""),
        "Start Mode": _start_mode(s), "Start Name": s.get("StartName", ""),
        "PID": s.get("ProcessId") if s.get("ProcessId") else "", "Type": s.get("ServiceType", ""),
        "Exit Code": s.get("ExitCode"), "Path": s.get("PathName", ""), "Description": s.get("Description", ""),
    } for s in rows_of(raw)]
    rows.sort(key=lambda r: str(r["Display Name"]).lower())
    summary = {
        "Services": len(rows),
        "Running": sum(1 for r in rows if r["State"] == "Running"),
        "Stopped": sum(1 for r in rows if r["State"] == "Stopped"),
        "Automatic": sum(1 for r in rows if r["Start Mode"] == "Automatic"),
        "Automatic (Delayed)": sum(1 for r in rows if r["Start Mode"] == "Automatic (Delayed)"),
        "Manual": sum(1 for r in rows if r["Start Mode"] == "Manual"),
        "Disabled": sum(1 for r in rows if r["Start Mode"] == "Disabled"),
    }
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.query("services", SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Services") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="services", title="Services", group="Software", collect=collect, render=render, timeout=60)
