"""Installed Updates: hotfixes plus the Windows Update history, newest first, grouped by month."""
from __future__ import annotations

import datetime

from .. import decode
from ..format import fmt_date, fmt_datetime, parse_datetime
from ..section import Section, list_table, rows_of, sub_heading

HOTFIX_SCRIPT = "Get-HotFix -ErrorAction SilentlyContinue | Select-Object HotFixID,Description,InstalledOn,InstalledBy"

HISTORY_SCRIPT = r"""
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$count = $searcher.GetTotalHistoryCount()
if ($count -gt 0) {
  $searcher.QueryHistory(0, [Math]::Min($count, 500)) | Where-Object { $_.Title } | ForEach-Object {
    $kb = ''
    if ($_.Title -match 'KB\d+') { $kb = $matches[0] }
    [pscustomobject]@{ Date = $_.Date; Title = [string]$_.Title; KB = $kb; Operation = [int]$_.Operation
                       Result = [int]$_.ResultCode; Client = [string]$_.ClientApplicationID }
  }
}
"""

HOTFIX_COLUMNS = [("KB", "KB"), ("Description", "Description"), ("Installed On", "Installed On"),
                  ("Installed By (account name)", "Installed By")]
HISTORY_COLUMNS = [("Date", "Date"), ("Title", "Title"), ("KB", "KB"), ("Operation", "Operation"),
                   ("Result", "Result"), ("Client", "Client")]


def build(hotfixes, history) -> dict:
    hot = [{
        "KB": h.get("HotFixID", ""), "Description": h.get("Description", ""),
        "Installed On": fmt_date(h.get("InstalledOn")),
        "Installed By (account name)": h.get("InstalledBy", ""),
    } for h in rows_of(hotfixes)]
    hot.sort(key=lambda r: (not r["Installed On"], r["Installed On"]), reverse=True)

    def when(row):
        return parse_datetime(row.get("Date")) or datetime.datetime.min

    hist = []
    for r in sorted(rows_of(history), key=when, reverse=True):
        dt = parse_datetime(r.get("Date"))
        hist.append({
            "Date": fmt_datetime(r.get("Date")), "Month": dt.strftime("%Y-%m") if dt else "Unknown",
            "Title": r.get("Title", ""), "KB": r.get("KB", ""),
            "Operation": decode.lookup(decode.WU_OPERATION, r.get("Operation")),
            "Result": decode.lookup(decode.WU_RESULT, r.get("Result")),
            "Client": r.get("Client", ""),
        })
    return {"hotfixes": hot, "history": hist}


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [sub_heading("Installed hotfixes"), list_table(HOTFIX_COLUMNS, data.get("hotfixes")),
           sub_heading("Windows Update history")]
    history = rows_of(data.get("history"))
    if not history:
        out.append(list_table(HISTORY_COLUMNS, []))
        return "".join(out)
    by_month: dict[str, list] = {}
    for row in history:
        by_month.setdefault(row.get("Month", "Unknown"), []).append(row)
    for month, rows in by_month.items():
        shown = []
        for row in rows:
            row = dict(row)
            if row.get("Result") in ("Failed", "Aborted"):
                row["Result"] = f"✖ {row['Result']}"
            shown.append(row)
        out.append(f'<table class="kv"><tr class="sub"><th colspan="2">{month} ({len(rows)})</th></tr></table>'
                   + list_table(HISTORY_COLUMNS, shown))
    return "".join(out)


def collect(ctx):
    hotfixes = ctx.query("hotfixes", HOTFIX_SCRIPT)
    history = ctx.query("history", HISTORY_SCRIPT, timeout=90)
    return build(hotfixes, history)


SECTION = Section(key="installed_updates", title="Installed Updates", group="Software",
                  collect=collect, render=render, timeout=90)
