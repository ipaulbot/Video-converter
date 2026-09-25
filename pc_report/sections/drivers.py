"""Drivers: signed PnP drivers grouped by device class, plus kernel/file-system drivers."""
from __future__ import annotations

from ..format import fmt_date, yes_no
from ..ps import cim
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

SIGNED_PROPS = ("DeviceName", "DeviceClass", "DriverVersion", "DriverDate", "DriverProviderName", "Manufacturer",
                "InfName", "IsSigned", "Signer", "DeviceID")
SIGNED_SCRIPT = cim("Win32_PnPSignedDriver", SIGNED_PROPS) + " | Where-Object { $_.DeviceName } | Sort-Object DeviceClass, DeviceName"
SYSTEM_SCRIPT = cim("Win32_SystemDriver", ("Name", "DisplayName", "State", "StartMode", "PathName", "ServiceType", "Started")) + " | Sort-Object DisplayName"

PNP_COLUMNS = [("Device", "Device"), ("Version", "Version"), ("Date", "Date"), ("Provider", "Provider"),
               ("Manufacturer", "Manufacturer"), ("INF", "INF"), ("Signed", "Signed"), ("Signer", "Signer"),
               ("Device ID", "Device ID")]
SYS_COLUMNS = [("Display Name", "Display Name"), ("Name", "Name"), ("State", "State"), ("Start Mode", "Start Mode"),
               ("Started", "Started"), ("Type", "Type"), ("Path", "Path")]
ROW_CAP = 1500


def _class_title(name) -> str:
    """NET/USB/HID stay as-is; longer all-caps classes (MONITOR, DISPLAY) become Monitor, Display."""
    text = str(name or "Unknown")
    if text.isupper() and len(text) <= 4:
        return text
    return text.capitalize() if text.isupper() else text


def build(signed, system) -> dict:
    pnp_rows = []
    unsigned = 0
    for d in rows_of(signed):
        row = {"Device": d.get("DeviceName", ""), "Class": _class_title(d.get("DeviceClass")),
               "Version": d.get("DriverVersion", ""), "Date": fmt_date(d.get("DriverDate")) if d.get("DriverDate") else "",
               "Provider": d.get("DriverProviderName", ""), "Manufacturer": d.get("Manufacturer", ""),
               "INF": d.get("InfName", ""), "Signed": yes_no(d.get("IsSigned")), "Signer": d.get("Signer", ""),
               "Device ID": d.get("DeviceID", "")}
        if row["Signed"] == "No":
            unsigned += 1
        pnp_rows.append(row)
    pnp_rows.sort(key=lambda row: (str(row["Class"]).casefold(), str(row["Device"]).casefold(),
                                   str(row["Device ID"]).casefold()))
    system_rows = [{"Display Name": s.get("DisplayName", ""), "Name": s.get("Name", ""), "State": s.get("State", ""),
                    "Start Mode": s.get("StartMode", ""), "Started": yes_no(s.get("Started")),
                    "Type": s.get("ServiceType", ""), "Path": s.get("PathName", "")} for s in rows_of(system)]
    system_rows.sort(key=lambda row: (str(row["Display Name"]).casefold(), str(row["Name"]).casefold()))
    total = len(pnp_rows) + len(system_rows)
    shown_pnp = pnp_rows[:ROW_CAP]
    shown_system = system_rows[:max(0, ROW_CAP - len(shown_pnp))]
    by_class: dict[str, list] = {}
    for row in shown_pnp:
        by_class.setdefault(row["Class"], []).append(row)
    summary = {"PnP Drivers": len(pnp_rows), "Device Classes": len({row["Class"] for row in pnp_rows}),
               "Unsigned Drivers": unsigned, "System Drivers": len(system_rows),
               "System Drivers Running": sum(1 for r in system_rows if r["State"] == "Running"),
               "Shown": len(shown_pnp) + len(shown_system), "Total": total}
    return {"groups": [{"title": "Summary", "rows": summary}], "by_class": by_class, "system": shown_system}


def collect(ctx):
    data = build(ctx.query("signed_drivers", SIGNED_SCRIPT, timeout=90), ctx.query("system_drivers", SYSTEM_SCRIPT))
    summary = data["groups"][0]["rows"]
    if summary["Shown"] < summary["Total"]:
        ctx.note(f"drivers: showing {summary['Shown']} of {summary['Total']} rows")
    return data


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    by_class = data.get("by_class") or {}
    if not by_class:
        out.append(sub_heading("PnP drivers") + list_table(PNP_COLUMNS, []))
    for cls, rows in by_class.items():
        out.append(sub_heading(f"{cls} ({len(rows)})") + list_table(PNP_COLUMNS, rows))
    out.append(sub_heading("System drivers") + list_table(SYS_COLUMNS, data.get("system")))
    return "".join(out)


SECTION = Section(key="drivers", title="Drivers", group="Software", collect=collect, render=render, timeout=90)
