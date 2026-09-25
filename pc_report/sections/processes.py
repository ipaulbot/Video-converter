"""Processes: every process with owner, command line, memory and CPU, plus top-10 lists."""
from __future__ import annotations

from ..format import bytes_human, duration, fmt_datetime, yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
$cim = @{}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object { $cim[[int]$_.ProcessId] = $_ }
foreach ($p in (Get-Process -ErrorAction SilentlyContinue)) {
  $c = $cim[[int]$p.Id]
  $owner = ''
  if ($c) { try { $o = Invoke-CimMethod -InputObject $c -MethodName GetOwner -ErrorAction SilentlyContinue; if ($o.User) { $owner = "$($o.Domain)\$($o.User)" } } catch {} }
  $start = $null; try { $start = $p.StartTime } catch {}
  $cpu = $null; try { $cpu = $p.CPU } catch {}
  [pscustomobject]@{ Id = $p.Id; Name = $p.ProcessName; Description = [string]$p.Description; Company = [string]$p.Company
    Version = [string]$p.FileVersion; Path = [string]$p.Path; CommandLine = [string]$c.CommandLine; ParentId = $c.ParentProcessId
    Session = $p.SessionId; StartTime = $start; CPU = $cpu; WorkingSet = $p.WorkingSet64; PrivateBytes = $p.PrivateMemorySize64
    Threads = $p.Threads.Count; Handles = $p.HandleCount; Priority = [string]$p.PriorityClass; Responding = $p.Responding; Owner = $owner }
}
"""

COLUMNS = [("PID", "PID"), ("Name", "Name"), ("Description", "Description"), ("Company", "Company"), ("Version", "Version"),
           ("Owner", "Owner"), ("Session", "Session"), ("Parent PID", "Parent PID"), ("Started", "Started"),
           ("CPU Time", "CPU Time"), ("Working Set", "Working Set"), ("Private Bytes", "Private Bytes"),
           ("Threads", "Threads"), ("Handles", "Handles"), ("Priority", "Priority"), ("Responding", "Responding"),
           ("Path", "Path"), ("Command Line", "Command Line")]
TOP_COLUMNS = [("PID", "PID"), ("Name", "Name"), ("CPU Time", "CPU Time"), ("Working Set", "Working Set"), ("Owner", "Owner")]
ROW_CAP = 1000


def _num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build(raw) -> dict:
    rows = []
    for p in rows_of(raw):
        rows.append({
            "PID": p.get("Id"), "Name": p.get("Name", ""), "Description": p.get("Description", ""),
            "Company": p.get("Company", ""), "Version": p.get("Version", ""), "Owner": p.get("Owner", ""),
            "Session": p.get("Session"), "Parent PID": p.get("ParentId"), "Started": fmt_datetime(p.get("StartTime")),
            "CPU Time": duration(p.get("CPU")) if p.get("CPU") is not None else "",
            "Working Set": bytes_human(p.get("WorkingSet")) if p.get("WorkingSet") is not None else "",
            "Private Bytes": bytes_human(p.get("PrivateBytes")) if p.get("PrivateBytes") is not None else "",
            "Threads": p.get("Threads"), "Handles": p.get("Handles"), "Priority": p.get("Priority", ""),
            "Responding": yes_no(p.get("Responding")), "Path": p.get("Path", ""), "Command Line": p.get("CommandLine", ""),
            "_cpu": _num(p.get("CPU")), "_ws": _num(p.get("WorkingSet")),
        })
    rows.sort(key=lambda r: str(r["Name"]).lower())
    top_cpu = sorted(rows, key=lambda r: r["_cpu"], reverse=True)[:10]
    top_mem = sorted(rows, key=lambda r: r["_ws"], reverse=True)[:10]
    total = len(rows)
    shown = rows[:ROW_CAP]
    summary = {
        "Processes": total,
        "Shown": len(shown),
        "Total": total,
        "Threads": sum(int(_num(r["Threads"])) for r in rows),
        "Handles": sum(int(_num(r["Handles"])) for r in rows),
        "Working Set (total)": bytes_human(int(sum(r["_ws"] for r in rows))),
        "Not Responding": sum(1 for r in rows if r["Responding"] == "No"),
    }

    def clean(r):
        return {k: v for k, v in r.items() if not k.startswith("_")}

    return {"groups": [{"title": "Summary", "rows": summary}],
            "top_cpu": [clean(r) for r in top_cpu], "top_memory": [clean(r) for r in top_mem],
            "rows": [clean(r) for r in shown]}


def collect(ctx):
    data = build(ctx.query("processes", SCRIPT, timeout=90))
    summary = data["groups"][0]["rows"]
    if summary["Shown"] < summary["Total"]:
        ctx.note(f"processes: showing {summary['Shown']} of {summary['Total']} rows")
    return data


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups"))
            + sub_heading("Top 10 by CPU time") + list_table(TOP_COLUMNS, data.get("top_cpu"))
            + sub_heading("Top 10 by working set") + list_table(TOP_COLUMNS, data.get("top_memory"))
            + sub_heading("All processes") + list_table(COLUMNS, data.get("rows")))


SECTION = Section(key="processes", title="Processes", group="Software", collect=collect, render=render, timeout=90)
