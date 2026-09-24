"""Codecs: DirectShow filter categories, VCM/ACM drivers and Media Foundation transforms, 64- and 32-bit."""
from __future__ import annotations

from ..section import Section, kv_groups, list_table, rows_of, sub_heading

# DirectShow category CLSIDs -> human names (the ones SIW and GraphStudio show).
DS_CATEGORIES = {
    "{083863F1-70DE-11D0-BD40-00A0C911CE86}": "DirectShow Filters",
    "{33D9A760-90C8-11D0-BD43-00A0C911CE86}": "Video Compressors (Legacy)",
    "{33D9A761-90C8-11D0-BD43-00A0C911CE86}": "Audio Compressors",
    "{33D9A762-90C8-11D0-BD43-00A0C911CE86}": "Audio Capture Sources",
    "{860BB310-5D01-11D0-BD3B-00A0C911CE86}": "Video Capture Sources",
    "{E0F158E1-CB04-11D0-BD4E-00A0C911CE86}": "Audio Renderers",
    "{CC7BFB41-F175-11D1-A392-00E0291F3959}": "WDM Streaming Capture Devices",
    "{CC7BFB46-F175-11D1-A392-00E0291F3959}": "WDM Streaming Rendering Devices",
    "{4EFE2452-168A-11D1-BC76-00C04FB9453B}": "Midi Renderers",
    "{7B8B58A4-26A8-11D1-A4C3-00A0C9BD4A21}": "External Renderers",
    "{DA4E3DA0-D07D-11D0-BD50-00A0C911CE86}": "Device Control Filters",
}

DIRECTSHOW_SCRIPT = r"""
$cats = @{
  '{083863F1-70DE-11D0-BD40-00A0C911CE86}' = 'DirectShow Filters'; '{33D9A760-90C8-11D0-BD43-00A0C911CE86}' = 'Video Compressors (Legacy)'
  '{33D9A761-90C8-11D0-BD43-00A0C911CE86}' = 'Audio Compressors'; '{33D9A762-90C8-11D0-BD43-00A0C911CE86}' = 'Audio Capture Sources'
  '{860BB310-5D01-11D0-BD3B-00A0C911CE86}' = 'Video Capture Sources'; '{E0F158E1-CB04-11D0-BD4E-00A0C911CE86}' = 'Audio Renderers'
  '{CC7BFB41-F175-11D1-A392-00E0291F3959}' = 'WDM Streaming Capture Devices'; '{CC7BFB46-F175-11D1-A392-00E0291F3959}' = 'WDM Streaming Rendering Devices'
  '{4EFE2452-168A-11D1-BC76-00C04FB9453B}' = 'Midi Renderers'; '{7B8B58A4-26A8-11D1-A4C3-00A0C9BD4A21}' = 'External Renderers'
  '{DA4E3DA0-D07D-11D0-BD50-00A0C911CE86}' = 'Device Control Filters'
}
$fileCache = @{}
function Get-FileMeta($path) {
  if (-not $path) { return @('', '') }
  $p = [Environment]::ExpandEnvironmentVariables($path.Trim('"'))
  if ($fileCache.ContainsKey($p)) { return $fileCache[$p] }
  $meta = @('', '')
  try { $vi = (Get-Item $p -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $meta = @([string]$vi.FileVersion, [string]$vi.CompanyName) } } catch {}
  $fileCache[$p] = $meta
  return $meta
}
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' }, @{ Root = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  foreach ($cat in $cats.Keys) {
    $inst = Join-Path (Join-Path $arch.Root $cat) 'Instance'
    if (-not (Test-Path $inst)) { continue }
    Get-ChildItem $inst -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      $clsid = [string]$x.CLSID
      $merit = $null
      if ($x.FilterData -is [byte[]] -and $x.FilterData.Length -ge 8) { $merit = [BitConverter]::ToUInt32($x.FilterData, 4) }
      $server = ''
      if ($clsid) { $server = [string](Get-ItemProperty (Join-Path (Join-Path $arch.Root $clsid) 'InprocServer32') -ErrorAction SilentlyContinue).'(default)' }
      $meta = Get-FileMeta $server
      [pscustomobject]@{ Category = $cats[$cat]; Name = [string]$x.FriendlyName; CLSID = $clsid; File = $server
                         Version = $meta[0]; Company = $meta[1]; Merit = $merit; Architecture = $arch.Name }
    }
  }
}
"""

DRIVERS32_SCRIPT = r"""
foreach ($arch in @(@{ Key = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Drivers32'; Name = 'x64'; Sys = "$env:SystemRoot\System32" },
                    @{ Key = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Drivers32'; Name = 'x86'; Sys = "$env:SystemRoot\SysWOW64" })) {
  $p = Get-ItemProperty $arch.Key -ErrorAction SilentlyContinue
  if (-not $p) { continue }
  $p.PSObject.Properties | Where-Object { $_.Name -match '^(vidc\.|msacm\.)' } | ForEach-Object {
    $file = [string]$_.Value
    $full = if ([IO.Path]::IsPathRooted($file)) { $file } else { Join-Path $arch.Sys $file }
    $ver = ''; $co = ''
    try { $vi = (Get-Item $full -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $ver = [string]$vi.FileVersion; $co = [string]$vi.CompanyName } } catch {}
    [pscustomobject]@{ Name = [string]$_.Name; File = $file; Version = $ver; Company = $co; Architecture = $arch.Name }
  }
}
"""

MF_SCRIPT = r"""
$categoryNames = @{
  'D6C02D4B-6833-45B4-971A-05A4B04BAB91' = 'Video Decoder'
  'F79EAC7D-E545-4387-BDEE-D647D7BDE42A' = 'Video Encoder'
  '9EA73FB4-EF7A-4559-8D5D-719D8F0426C7' = 'Audio Decoder'
  '91C64BD0-F91E-4D8C-9276-DB248279D975' = 'Audio Encoder'
  '12E17C21-532C-4A6E-8A1C-40825A736397' = 'Video Effect'
  '302EA3FC-AA5F-47F9-9F7A-C2188BB16302' = 'Video Processor'
  'A8700A7A-939B-44C5-99D7-76226B23B3F1' = 'Demultiplexer'
  '059C561E-05AE-4B61-B69D-55B61EE54A7B' = 'Multiplexer'
  '90175D57-B7EA-4901-AEB3-933A8747756F' = 'Other'
}
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Classes\MediaFoundation\Transforms'; RegistryPath = 'SOFTWARE\Classes\MediaFoundation\Transforms'; Clsid = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' },
                    @{ Root = 'HKLM:\SOFTWARE\Classes\WOW6432Node\MediaFoundation\Transforms'; RegistryPath = 'SOFTWARE\Classes\WOW6432Node\MediaFoundation\Transforms'; Clsid = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  if (-not (Test-Path $arch.Root)) { continue }
  $categoriesByTransform = @{}
  $baseKey = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
  try {
    $categoryRoot = $baseKey.OpenSubKey("$($arch.RegistryPath)\Categories")
    if ($categoryRoot) {
      try {
        foreach ($categoryGuid in $categoryRoot.GetSubKeyNames()) {
          $categoryKey = $categoryRoot.OpenSubKey($categoryGuid)
          if (-not $categoryKey) { continue }
          try {
            $normalizedCategory = $categoryGuid.Trim('{}').ToUpperInvariant()
            $categoryName = if ($categoryNames.ContainsKey($normalizedCategory)) { $categoryNames[$normalizedCategory] } else { $categoryGuid }
            foreach ($transformClsid in $categoryKey.GetSubKeyNames()) {
              $normalizedClsid = $transformClsid.Trim('{}').ToUpperInvariant()
              if (-not $categoriesByTransform.ContainsKey($normalizedClsid)) { $categoriesByTransform[$normalizedClsid] = @() }
              $categoriesByTransform[$normalizedClsid] += $categoryName
            }
          } finally { $categoryKey.Close() }
        }
      } finally { $categoryRoot.Close() }
    }
  } finally { $baseKey.Close() }
  Get-ChildItem $arch.Root -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\{?[0-9A-Fa-f-]{36}\}?$' } | ForEach-Object {
    $transform = $_
    $x = Get-ItemProperty $transform.PsPath -ErrorAction SilentlyContinue
    $clsid = [string]$transform.PSChildName
    $clsidKey = if ($clsid.StartsWith('{')) { $clsid } else { "{$clsid}" }
    $server = [string](Get-ItemProperty (Join-Path (Join-Path $arch.Clsid $clsidKey) 'InprocServer32') -ErrorAction SilentlyContinue).'(default)'
    $name = [string]$x.'(default)'
    if (-not $name) { $name = '(default)' }
    $normalizedClsid = $clsid.Trim('{}').ToUpperInvariant()
    $categories = if ($categoriesByTransform.ContainsKey($normalizedClsid)) { $categoriesByTransform[$normalizedClsid] } else { @() }
    $ver = ''; $co = ''
    try { $vi = (Get-Item ([Environment]::ExpandEnvironmentVariables($server.Trim('"'))) -ErrorAction SilentlyContinue).VersionInfo; if ($vi) { $ver = [string]$vi.FileVersion; $co = [string]$vi.CompanyName } } catch {}
    [pscustomobject]@{ Category = ($categories -join ', '); Name = $name; CLSID = $clsid; File = $server
                       Version = $ver; Company = $co; Architecture = $arch.Name }
  }
}
"""

_MERITS = {
    0x800000: "Preferred",
    0x600000: "Normal",
    0x400000: "Unlikely",
    0x200000: "Do not use",
    0x100050: "Hardware compressor",
    0x100000: "Software compressor",
}

COLUMNS = [("Name", "Name"), ("Category", "Category"), ("File", "File"), ("Version", "Version"),
           ("Company", "Company"), ("CLSID", "CLSID"), ("Merit", "Merit"), ("Architecture", "Architecture")]


def merit(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    label = _MERITS.get(n)
    return f"0x{n:X} ({label})" if label else f"0x{n:X}"


def build(directshow, drivers32, media_foundation) -> dict:
    categories: dict[str, list] = {}

    def add(category, row):
        categories.setdefault(category, []).append(row)

    for f in rows_of(directshow):
        add(f.get("Category") or "DirectShow Filters",
            {"Name": f.get("Name", ""), "File": f.get("File", ""), "Version": f.get("Version", ""), "Company": f.get("Company", ""),
             "CLSID": f.get("CLSID", ""), "Merit": merit(f.get("Merit")), "Architecture": f.get("Architecture", ""), "Source": "DirectShow"})
    for d in rows_of(drivers32):
        name = str(d.get("Name") or "")
        prefix = name.lower()
        if not prefix.startswith(("vidc.", "msacm.")):
            continue
        cat = "Audio Compression Manager (ACM)" if prefix.startswith("msacm.") else "Video for Windows (VCM)"
        add(cat, {"Name": name, "File": d.get("File", ""), "Version": d.get("Version", ""), "Company": d.get("Company", ""),
                  "CLSID": "", "Merit": "", "Architecture": d.get("Architecture", ""), "Source": "Drivers32"})
    for m in rows_of(media_foundation):
        add("Media Foundation Transforms",
            {"Name": m.get("Name", ""), "Category": m.get("Category", ""), "File": m.get("File", ""),
             "Version": m.get("Version", ""), "Company": m.get("Company", ""),
             "CLSID": m.get("CLSID", ""), "Merit": "", "Architecture": m.get("Architecture", ""), "Source": "Media Foundation"})
    order = list(DS_CATEGORIES.values()) + ["Video for Windows (VCM)", "Audio Compression Manager (ACM)", "Media Foundation Transforms"]
    ordered = {c: sorted(categories[c], key=lambda r: str(r["Name"]).lower()) for c in order if c in categories}
    for c in categories:
        if c not in ordered:
            ordered[c] = categories[c]
    summary = {c: len(rows) for c, rows in ordered.items()}
    summary["Total Entries"] = sum(summary.values())
    return {"groups": [{"title": "Summary", "rows": summary}], "categories": ordered}


def collect(ctx):
    directshow = ctx.query("directshow", DIRECTSHOW_SCRIPT, timeout=90)
    drivers32 = ctx.query("drivers32", DRIVERS32_SCRIPT)
    media_foundation = ctx.query("media_foundation", MF_SCRIPT, timeout=60)
    if rows_of(directshow) and not rows_of(media_foundation):
        ctx.note("media foundation: no transforms enumerated")
    return build(directshow, drivers32, media_foundation)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    cats = data.get("categories") or {}
    if not cats:
        out.append(list_table(COLUMNS, []))
    for cat, rows in cats.items():
        out.append(sub_heading(f"{cat} ({len(rows)})") + list_table(COLUMNS, rows))
    return "".join(out)


SECTION = Section(key="codecs", title="Codecs", group="Software", collect=collect, render=render, timeout=90)
