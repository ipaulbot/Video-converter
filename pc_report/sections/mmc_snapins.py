"""MMC Snap-ins: registered console snap-ins with their module, version and company."""
from __future__ import annotations

from ..section import Section, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Microsoft\MMC\SnapIns'; Clsid = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' },
                    @{ Root = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\MMC\SnapIns'; Clsid = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  if (-not (Test-Path $arch.Root)) { continue }
  Get-ChildItem $arch.Root -ErrorAction SilentlyContinue | ForEach-Object {
    $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
    $clsid = $_.PSChildName
    $module = ''
    try { $module = [string](Get-ItemProperty (Join-Path (Join-Path $arch.Clsid $clsid) 'InprocServer32') -ErrorAction SilentlyContinue).'(default)' } catch {}
    if (-not $module -and $x.FxVersion) { $module = 'Managed (' + [string]$x.FxVersion + ')' }
    $ver = ''; $co = ''
    if ($module -and -not $module.StartsWith('Managed')) {
      try { $vi = (Get-Item ([Environment]::ExpandEnvironmentVariables($module)) -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $ver = [string]$vi.FileVersion; $co = [string]$vi.CompanyName } } catch {}
    }
    [pscustomobject]@{ CLSID = $clsid; Name = [string]$x.NameString; NameString = [string]$x.NameString; About = [string]$x.About
                       Module = $module; Version = $ver; Company = $co; Architecture = $arch.Name }
  }
}
"""

COLUMNS = [("Name", "Name"), ("Module", "Module"), ("Version", "Version"), ("Company", "Company"),
           ("CLSID", "CLSID"), ("Architecture", "Architecture")]


def build(raw) -> dict:
    rows = [{"Name": s.get("NameString") or s.get("Name") or s.get("CLSID", ""), "Module": s.get("Module", ""),
             "Version": s.get("Version", ""), "Company": s.get("Company", ""), "CLSID": s.get("CLSID", ""),
             "Architecture": s.get("Architecture", "")} for s in rows_of(raw)]
    rows.sort(key=lambda r: str(r["Name"]).lower())
    return {"groups": [{"title": "Summary", "rows": {"Snap-ins": len(rows)}}], "rows": rows}


def collect(ctx):
    return build(ctx.query("snapins", SCRIPT, timeout=60))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Snap-ins") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="mmc_snapins", title="MMC Snap-ins", group="Software", collect=collect, render=render, timeout=60)
