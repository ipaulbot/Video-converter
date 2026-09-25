"""Devices: problem devices first, then every PnP device grouped by class (shared PnP dump)."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

COLUMNS = [("Name", "Name"), ("Manufacturer", "Manufacturer"), ("Status", "Status"), ("Present", "Present"),
           ("Service", "Service"), ("Device Instance", "Device Instance")]
PROBLEM_COLUMNS = [("Name", "Name"), ("Class", "Class"), ("Problem", "Problem"), ("Manufacturer", "Manufacturer"),
                   ("Device Instance", "Device Instance")]


def build(pnp) -> dict:
    by_class: dict[str, list] = {}
    problems = []
    present = 0
    disabled = 0
    unknown = 0
    for d in rows_of(pnp):
        code = decode.to_int(d.get("ConfigManagerErrorCode")) or 0
        is_present = bool(d.get("Present"))
        present += is_present
        status = d.get("Status") or ""
        disabled += code == 22 or str(status).casefold() == "disabled"
        unknown += str(status).casefold() == "unknown"
        cls = d.get("PNPClass") or "(No class)"
        instance_id = d.get("PNPDeviceID") or d.get("DeviceID") or ""
        error_text = decode.lookup(decode.PNP_ERROR_CODES, code)
        row = {"Name": d.get("Name") or d.get("Description") or "", "Class": cls, "Manufacturer": d.get("Manufacturer") or "",
               "Status": status, "Present": yes_no(is_present), "Service": d.get("Service") or "",
               "Device Instance": instance_id, "InstanceId": instance_id, "ConfigManagerErrorCode": error_text}
        by_class.setdefault(cls, []).append(row)
        if code and is_present:
            problems.append({**row, "Problem": f"{code}: {error_text}"})
    for rows in by_class.values():
        rows.sort(key=lambda row: (str(row["Name"]).casefold(), str(row["InstanceId"]).casefold()))
    by_class = dict(sorted(by_class.items(), key=lambda kv: kv[0].lower()))
    problems.sort(key=lambda row: (str(row["Class"]).casefold(), str(row["Name"]).casefold(),
                                   str(row["InstanceId"]).casefold()))
    total = sum(len(v) for v in by_class.values())
    summary = {"Devices": total, "Present": present, "Not Present (phantom)": total - present,
               "Problem Devices": len(problems), "Disabled": disabled, "Unknown": unknown, "Classes": len(by_class)}
    return {"groups": [{"title": "Summary", "rows": summary}], "problems": problems, "by_class": by_class}


def collect(ctx):
    pnp = ctx.shared("pnp_entities")
    if pnp is None:
        ctx.note("pnp_entities: unavailable")
    return build(pnp)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups")), sub_heading("Problem devices"), list_table(PROBLEM_COLUMNS, data.get("problems"))]
    by_class = data.get("by_class") or {}
    if not by_class:
        out.append(list_table(COLUMNS, []))
    for cls, rows in by_class.items():
        out.append(sub_heading(f"{cls} ({len(rows)})") + list_table(COLUMNS, rows))
    return "".join(out)


SECTION = Section(key="devices", title="Devices", group="Hardware", collect=collect, render=render, timeout=60)
