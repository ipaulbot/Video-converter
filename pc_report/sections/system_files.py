"""System Files: the classic configuration files, with size, modified time and hosts entry count."""
from __future__ import annotations

from ..format import bytes_human, fmt_datetime
from ..section import Section, list_table, rows_of

SCRIPT = r"""
$root = $env:SystemRoot
$paths = @("$root\System32\drivers\etc\hosts", "$root\System32\drivers\etc\lmhosts.sam",
           "$root\System32\drivers\etc\networks", "$root\System32\drivers\etc\protocol",
           "$root\System32\drivers\etc\services", "$root\system.ini", "$root\win.ini")
foreach ($p in $paths) {
  $f = Get-Item $p -ErrorAction SilentlyContinue
  if ($f) {
    $entries = ''
    if ($f.Name -eq 'hosts') { $entries = @(Get-Content $p -ErrorAction SilentlyContinue | Where-Object { $_ -match '^\s*[^#\s]' }).Count }
    [pscustomobject]@{ Name = $f.Name; Path = $f.FullName; Size = $f.Length; Modified = $f.LastWriteTime; Entries = $entries }
  } else {
    [pscustomobject]@{ Name = (Split-Path $p -Leaf); Path = $p; Size = ''; Modified = ''; Entries = 'missing' }
  }
}
"""

COLUMNS = [("Name", "Name"), ("Path", "Path"), ("Status", "Status"), ("Size", "Size"),
           ("Modified", "Modified"), ("Hosts Entries", "Hosts entries")]


def build(files) -> dict:
    rows = []
    for f in rows_of(files):
        missing = f.get("Entries") == "missing"
        rows.append({
            "Name": f.get("Name", ""), "Path": f.get("Path", ""),
            "Status": "Missing" if missing else "Present",
            "Size": "" if missing or f.get("Size") in ("", None) else bytes_human(f.get("Size")),
            "Modified": "" if missing else fmt_datetime(f.get("Modified")),
            "Hosts Entries": "" if missing or f.get("Entries") in ("", None) else f.get("Entries"),
        })
    return {"rows": rows}


def collect(ctx):
    return build(ctx.query("files", SCRIPT))


def render(data, ctx):
    return list_table(COLUMNS, (data or {}).get("rows") if isinstance(data, dict) else None)


SECTION = Section(key="system_files", title="System Files", group="Software", collect=collect, render=render)
