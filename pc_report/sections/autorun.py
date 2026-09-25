"""Autorun: Run/RunOnce keys, startup folders (with the StartupApproved enabled flag) and non-Microsoft scheduled tasks."""
from __future__ import annotations

from ..format import fmt_datetime, yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

RUN_SCRIPT = r"""
$keys = @(
  [pscustomobject]@{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'; Hive = 'HKLM'; Kind = 'Run' },
  [pscustomobject]@{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce'; Hive = 'HKLM'; Kind = 'Run' },
  [pscustomobject]@{ Path = 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'; Hive = 'HKLM'; Kind = 'Run32' },
  [pscustomobject]@{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'; Hive = 'HKCU'; Kind = 'Run' },
  [pscustomobject]@{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce'; Hive = 'HKCU'; Kind = 'Run' }
)
$approvalPaths = @(
  [pscustomobject]@{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'; Hive = 'HKLM'; Kind = 'Run' },
  [pscustomobject]@{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32'; Hive = 'HKLM'; Kind = 'Run32' },
  [pscustomobject]@{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder'; Hive = 'HKLM'; Kind = 'StartupFolder' },
  [pscustomobject]@{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'; Hive = 'HKCU'; Kind = 'Run' },
  [pscustomobject]@{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32'; Hive = 'HKCU'; Kind = 'Run32' },
  [pscustomobject]@{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder'; Hive = 'HKCU'; Kind = 'StartupFolder' }
)
$approved = @{}
foreach ($ap in $approvalPaths) {
  $p = Get-ItemProperty $ap.Path -ErrorAction SilentlyContinue
  if ($p) { $p.PSObject.Properties | Where-Object { $_.Value -is [byte[]] -and $_.Value.Length -gt 0 } | ForEach-Object {
    $approved["$($ap.Hive)|$($ap.Kind)|$($_.Name)"] = ($_.Value[0] -ne 3) } }
}
foreach ($k in $keys) {
  $p = Get-ItemProperty $k.Path -ErrorAction SilentlyContinue
  if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS(Path|ParentPath|ChildName|Drive|Provider)$' } | ForEach-Object {
    $approvalKey = "$($k.Hive)|$($k.Kind)|$($_.Name)"
    $en = if ($approved.ContainsKey($approvalKey)) { $approved[$approvalKey] } else { $true }
    [pscustomobject]@{ Name = [string]$_.Name; Command = [string]$_.Value; Location = $k.Path; Enabled = $en; Kind = 'Registry' } } }
}
foreach ($sf in @([pscustomobject]@{ Folder = 'Startup'; Hive = 'HKCU' },
                  [pscustomobject]@{ Folder = 'CommonStartup'; Hive = 'HKLM' })) {
  $dir = [Environment]::GetFolderPath($sf.Folder)
  if ($dir -and (Test-Path $dir)) { Get-ChildItem $dir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'desktop.ini' } | ForEach-Object {
    $approvalKey = "$($sf.Hive)|StartupFolder|$($_.Name)"
    $en = if ($approved.ContainsKey($approvalKey)) { $approved[$approvalKey] } else { $true }
    [pscustomobject]@{ Name = $_.Name; Command = $_.FullName; Location = $dir; Enabled = $en; Kind = 'Startup folder' } } }
}
"""

TASKS_SCRIPT = r"""
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
  $_.TaskPath -notlike '\Microsoft\*' -and [string]$_.Author -notmatch 'Microsoft'
} | ForEach-Object {
  $info = $null; try { $info = $_ | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue } catch {}
  $act = ($_.Actions | ForEach-Object { if ($_.Execute) { "$($_.Execute) $($_.Arguments)".Trim() } }) -join '; '
  $trig = ($_.Triggers | ForEach-Object { $_.CimClass.CimClassName -replace '^MSFT_Task','' -replace 'Trigger$','' }) -join ', '
  [pscustomobject]@{ Name = $_.TaskName; Path = $_.TaskPath; State = [string]$_.State; Author = [string]$_.Author; Action = $act
    Triggers = $trig; LastRun = $info.LastRunTime; NextRun = $info.NextRunTime; LastResult = $info.LastTaskResult
    'Run As (account name)' = [string]$_.Principal.UserId }
}
"""

ENTRY_COLUMNS = [("Name", "Name"), ("Command", "Command"), ("Location", "Location"), ("Enabled", "Enabled"), ("Kind", "Kind")]
TASK_COLUMNS = [("Name", "Task"), ("Path", "Folder"), ("State", "State"), ("Author", "Author"), ("Action", "Action"),
                ("Triggers", "Triggers"), ("Last Run", "Last Run"), ("Next Run", "Next Run"), ("Last Result", "Last Result"),
                ("Run As (account name)", "Run As")]


def _hex(value):
    try:
        return f"0x{int(value) & 0xFFFFFFFF:X}"
    except (TypeError, ValueError):
        return "" if value is None else str(value)


def build(entries, tasks) -> dict:
    ent = [{"Name": e.get("Name", ""), "Command": e.get("Command", ""), "Location": e.get("Location", ""),
            "Enabled": yes_no(e.get("Enabled")), "Kind": e.get("Kind", "")} for e in rows_of(entries)]
    tsk = [{"Name": t.get("Name", ""), "Path": t.get("Path", ""), "State": t.get("State", ""), "Author": t.get("Author", ""),
            "Action": t.get("Action", ""), "Triggers": t.get("Triggers", ""), "Last Run": fmt_datetime(t.get("LastRun")),
            "Next Run": fmt_datetime(t.get("NextRun")), "Last Result": _hex(t.get("LastResult")),
            "Run As (account name)": t.get("Run As (account name)", "")} for t in rows_of(tasks)
           if not str(t.get("Path", "")).casefold().startswith("\\microsoft\\")
           and "microsoft" not in str(t.get("Author", "")).casefold()]
    summary = {"Startup Entries": len(ent), "Disabled Entries": sum(1 for e in ent if e["Enabled"] == "No"),
               "Scheduled Tasks (non-Microsoft)": len(tsk),
               "Tasks Ready or Running": sum(1 for t in tsk if t["State"] in ("Ready", "Running"))}
    return {"groups": [{"title": "Summary", "rows": summary}], "entries": ent, "tasks": tsk}


def collect(ctx):
    return build(ctx.query("run_entries", RUN_SCRIPT), ctx.query("scheduled_tasks", TASKS_SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (kv_groups(data.get("groups")) + sub_heading("Startup entries") + list_table(ENTRY_COLUMNS, data.get("entries"))
            + sub_heading("Scheduled tasks") + list_table(TASK_COLUMNS, data.get("tasks")))


SECTION = Section(key="autorun", title="Autorun", group="Software", collect=collect, render=render, timeout=60)
