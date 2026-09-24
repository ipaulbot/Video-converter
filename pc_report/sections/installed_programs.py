"""Installed Programs: Uninstall registry keys (both hives, user scope), package providers and Store apps."""
from __future__ import annotations

from ..format import fmt_date, kb_human, yes_no
from ..section import Section, kv_groups, list_table, rows_of, sub_heading

REGISTRY_SCRIPT = r"""
$hives = @(
  @{ Path = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall'; Arch = 'x64'; Scope = 'Machine' },
  @{ Path = 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'; Arch = 'x86'; Scope = 'Machine' },
  @{ Path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'; Arch = ''; Scope = 'User' }
)
foreach ($h in $hives) {
  if (Test-Path $h.Path) {
    Get-ChildItem $h.Path -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      if ($x.DisplayName) {
        [pscustomobject]@{ Name = [string]$x.DisplayName; Version = [string]$x.DisplayVersion; Publisher = [string]$x.Publisher
                           InstallDate = [string]$x.InstallDate; InstallLocation = [string]$x.InstallLocation
                           InstallSource = [string]$x.InstallSource; EstimatedSize = $x.EstimatedSize
                           Uninstall = [string]$x.UninstallString; Architecture = $h.Arch; Scope = $h.Scope
                           SystemComponent = $x.SystemComponent }
      }
    }
  }
}
"""

PACKAGES_SCRIPT = (
    "Get-Package -ErrorAction SilentlyContinue | ForEach-Object { "
    "[pscustomobject]@{ Name = [string]$_.Name; Version = [string]$_.Version; "
    "Publisher = [string]($_.Meta.Attributes['Publisher']); ProviderName = [string]$_.ProviderName } }"
)

APPX_SCRIPT = (
    "Get-AppxPackage -ErrorAction SilentlyContinue | ForEach-Object { "
    "$pub = [string]$_.Publisher; if ($pub -match 'CN=([^,]+)') { $pub = $matches[1] } "
    "$inst = ''; try { if ($_.InstallLocation) { $fi = Get-Item $_.InstallLocation -ErrorAction SilentlyContinue; "
    "if ($fi) { $inst = $fi.CreationTime.ToString('yyyy-MM-dd') } } } catch {} "
    "[pscustomobject]@{ Name = [string]$_.Name; Version = [string]$_.Version; Publisher = $pub; InstallDate = $inst; "
    "InstallLocation = [string]$_.InstallLocation; Architecture = [string]$_.Architecture } }"
)

COLUMNS = [("Name", "Name"), ("Version", "Version"), ("Publisher", "Publisher"), ("Install Date", "Install Date"),
           ("Size", "Size"), ("Architecture", "Architecture"), ("Scope", "Scope"), ("Hidden", "Hidden"),
           ("Install Location", "Install Location"), ("Install Source", "Install Source"), ("Source", "Source"),
           ("Uninstall", "Uninstall")]


def _row(name, version="", publisher="", install_date="", size="", arch="", scope="Machine", hidden=False,
         location="", install_source="", source="", uninstall=""):
    return {"Name": str(name), "Version": str(version or ""), "Publisher": str(publisher or ""),
            "Install Date": fmt_date(install_date) if install_date else "", "Size": size, "Architecture": str(arch or ""),
            "Scope": scope, "Hidden": yes_no(bool(hidden)), "Install Location": str(location or ""),
            "Install Source": str(install_source or ""), "Source": source, "Uninstall": str(uninstall or "")}


def build(registry_rows, package_rows, appx_rows) -> dict:
    rows = []
    for it in rows_of(registry_rows):
        if not it.get("Name"):
            continue
        size = kb_human(it["EstimatedSize"]) if it.get("EstimatedSize") not in (None, "", 0) else ""
        rows.append(_row(it["Name"], it.get("Version"), it.get("Publisher"), it.get("InstallDate"), size,
                         it.get("Architecture"), it.get("Scope") or "Machine", bool(it.get("SystemComponent")),
                         it.get("InstallLocation"), it.get("InstallSource"), "Registry", it.get("Uninstall")))
    for it in rows_of(package_rows):
        if it.get("Name"):
            rows.append(_row(it["Name"], it.get("Version"), it.get("Publisher"),
                             source=f"Package ({it.get('ProviderName') or 'provider'})"))
    for it in rows_of(appx_rows):
        if it.get("Name"):
            rows.append(_row(it["Name"], it.get("Version"), it.get("Publisher"), it.get("InstallDate"),
                             arch=it.get("Architecture"), location=it.get("InstallLocation"), source="Microsoft Store"))
    seen, deduped = set(), []
    for row in rows:
        key = (row["Name"].lower(), row["Version"], row["Publisher"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    deduped.sort(key=lambda r: r["Name"].lower())
    summary = {
        "Programs": len(deduped),
        "Hidden (system components)": sum(1 for r in deduped if r["Hidden"] == "Yes"),
        "Microsoft Store apps": sum(1 for r in deduped if r["Source"] == "Microsoft Store"),
        "User-scope installs": sum(1 for r in deduped if r["Scope"] == "User"),
    }
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": deduped}


def collect(ctx):
    reg = ctx.query("registry", REGISTRY_SCRIPT, timeout=60)
    pkg = ctx.query("packages", PACKAGES_SCRIPT, timeout=90)
    appx = ctx.query("appx", APPX_SCRIPT, timeout=60)
    return build(reg, pkg, appx)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Programs") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="installed_programs", title="Installed Programs", group="Software",
                  collect=collect, render=render, timeout=90)
