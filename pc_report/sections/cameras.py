"""Cameras: PnP cameras, DirectShow capture sources, dxdiag detail, Frame Server, consent store, GenICam and transport layers."""
from __future__ import annotations

import datetime
import re

from .. import decode
from ..format import fmt_datetime, yes_no
from ..ps import dx_list
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

DS_SCRIPT = r"""
$cats = @{ '{860BB310-5D01-11D0-BD3B-00A0C911CE86}' = 'Video Capture Sources'; '{33D9A762-90C8-11D0-BD43-00A0C911CE86}' = 'Audio Capture Sources' }
foreach ($arch in @(@{ Root = 'HKLM:\SOFTWARE\Classes\CLSID'; Name = 'x64' }, @{ Root = 'HKLM:\SOFTWARE\Classes\WOW6432Node\CLSID'; Name = 'x86' })) {
  foreach ($cat in $cats.Keys) {
    $inst = Join-Path (Join-Path $arch.Root $cat) 'Instance'
    if (-not (Test-Path $inst)) { continue }
    Get-ChildItem $inst -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      [pscustomobject]@{ Category = $cats[$cat]; Name = [string]$x.FriendlyName; CLSID = [string]$x.CLSID; DevicePath = [string]$x.DevicePath; Architecture = $arch.Name }
    }
  }
}
"""
FRAME_SERVER_SCRIPT = r"""
$svc = Get-Service FrameServer -ErrorAction SilentlyContinue
[pscustomobject]@{
  EnableFrameServerMode = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows Media Foundation\Platform' -ErrorAction SilentlyContinue).EnableFrameServerMode
  EnableFrameServerModeWow = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Media Foundation\Platform' -ErrorAction SilentlyContinue).EnableFrameServerMode
  FrameServerStatus = [string]$svc.Status; FrameServerStartType = [string]$svc.StartType
}
"""
CONSENT_SCRIPT = r"""
foreach ($cap in 'webcam','microphone') {
  foreach ($hive in 'HKCU','HKLM') {
    $root = "$($hive):\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\$cap"
    if (-not (Test-Path $root)) { continue }
    $g = Get-ItemProperty $root -ErrorAction SilentlyContinue
    [pscustomobject]@{ Capability = $cap; Hive = $hive; App = '(global)'; Value = [string]$g.Value; LastUsedStart = $null; LastUsedStop = $null }
    Get-ChildItem $root -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
      $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
      if ($null -ne $x.Value -or $x.LastUsedTimeStart) {
        [pscustomobject]@{ Capability = $cap; Hive = $hive; App = $_.PSChildName; Value = [string]$x.Value; LastUsedStart = $x.LastUsedTimeStart; LastUsedStop = $x.LastUsedTimeStop }
      }
    }
  }
}
"""

CAMERA_NAME = re.compile(r"\b(camera|webcam|cam)\b", re.I)
TRANSPORT_PATTERNS = [
    (re.compile(r"\b(?:pylon|Basler)\b", re.I), "Basler"),
    (re.compile(r"\b(?:MATRIX VISION|mvIMPACT)\b", re.I), "MATRIX VISION"),
    (re.compile(r"\b(?:FLIR|Spinnaker)\b", re.I), "FLIR"),
    (re.compile(r"\b(?:IDS(?:\s+peak)?|uEye)\b", re.I), "IDS"),
    (re.compile(r"\b(?:Allied Vision|Vimba)\b", re.I), "Allied Vision"),
    (re.compile(r"\bGenICam\b", re.I), "GenICam"),
    (re.compile(r"\bGenTL\b", re.I), "GenTL"),
    (re.compile(r"\bGigE\b", re.I), "GigE"),
    (re.compile(r"\b(?:Teledyne|DALSA|Sapera)\b", re.I), "Teledyne DALSA"),
    (re.compile(r"\b(?:Lucid|Arena SDK)\b", re.I), "Lucid"),
    (re.compile(r"\b(?:The Imaging Source|IC Imaging)\b", re.I), "The Imaging Source"),
    (re.compile(r"\bEuresys\b", re.I), "Euresys"),
    (re.compile(r"\b(?:Daheng|Galaxy)\b", re.I), "Daheng Imaging"),
    (re.compile(r"\b(?:transport layer|CoaXPress|Camera Link)\b", re.I), "Camera transport"),
]
GENICAM_ENV_SCRIPT = "Get-ChildItem Env: -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'GENICAM_*' } | Select-Object Name,Value"

PNP_COLUMNS = [("Name", "Name"), ("Class", "Class"), ("Manufacturer", "Manufacturer"), ("Status", "Status"), ("Problem", "Problem"),
               ("Service", "Service"), ("Present", "Present"), ("Device Instance", "Device Instance")]
DS_COLUMNS = [("Name", "Name"), ("CLSID", "CLSID"), ("Device Path", "Device Path"), ("Architecture", "Architecture")]
DX_COLUMNS = [("Name", "Name"), ("Category", "Category"), ("Manufacturer", "Manufacturer"), ("Hardware ID", "Hardware ID"),
              ("Driver", "Driver"), ("Driver Date", "Driver Date"), ("Service", "Service"), ("Problem", "Problem"), ("Location", "Location")]
CONSENT_COLUMNS = [("App", "App"), ("Camera", "Camera"), ("Microphone", "Microphone"), ("Last Used", "Last Used")]
_AUDIO_SERVICES = frozenset({"usbaudio", "usbaudio2", "hdaudbus", "intelaudio", "audioendpoint"})


def is_camera(row) -> bool:
    cls = str(row.get("PNPClass") or row.get("Class") or "")
    if cls.casefold() == "camera":
        return True
    if str(row.get("Service") or "").casefold() == "usbvideo":
        return True
    service = str(row.get("Service") or "").casefold()
    if service in _AUDIO_SERVICES:
        return False
    if cls.casefold() == "audioendpoint":
        return False
    if "audio" in str(row.get("Description") or "").casefold():
        return False
    return cls.casefold() in {"image", "media"} and bool(CAMERA_NAME.search(str(row.get("Name") or "")))


def filetime(value) -> str:
    n = decode.to_int(value)
    if not n:
        return ""
    try:
        dt = datetime.datetime(1601, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(microseconds=n / 10)
        return fmt_datetime(dt.astimezone().isoformat())
    except (OverflowError, ValueError, OSError):
        return ""


def _scope(hive) -> str:
    return "machine policy" if str(hive).upper() == "HKLM" else "user"


def _app_name(raw: str) -> str:
    return str(raw or "").replace("#", "\\")


def build(pnp, ds, dx, frame_server, consent, env, programs) -> dict:
    fs, env = frame_server or {}, env or {}
    pnp_rows = []
    for d in rows_of(pnp):
        name = str(d.get("Name") or "")
        cls = str(d.get("PNPClass") or "")
        if not is_camera(d):
            continue
        code = decode.to_int(d.get("ConfigManagerErrorCode")) or 0
        pnp_rows.append({"Name": name, "Class": cls, "Manufacturer": d.get("Manufacturer") or "", "Status": d.get("Status") or "",
                         "Problem": f"{code}: {decode.lookup(decode.PNP_ERROR_CODES, code)}" if code else "",
                         "Service": d.get("Service") or "", "Present": yes_no(bool(d.get("Present"))),
                         "Device Instance": d.get("PNPDeviceID") or d.get("DeviceID") or ""})
    video = [{"Name": s.get("Name", ""), "CLSID": s.get("CLSID", ""), "Device Path": s.get("DevicePath", ""), "Architecture": s.get("Architecture", "")}
             for s in rows_of(ds) if s.get("Category") == "Video Capture Sources"]
    audio = [{"Name": s.get("Name", ""), "CLSID": s.get("CLSID", ""), "Device Path": s.get("DevicePath", ""), "Architecture": s.get("Architecture", "")}
             for s in rows_of(ds) if s.get("Category") == "Audio Capture Sources"]
    dxrows = [{"Name": v.get("FriendlyName", ""), "Category": v.get("Category", ""), "Manufacturer": v.get("Manufacturer", ""),
               "Hardware ID": v.get("HardwareID", ""),
               "Driver": " ".join(x for x in (v.get("DriverDesc", ""), v.get("DriverVersion", ""), f"({v.get('DriverProvider')})" if v.get("DriverProvider") else "") if x),
               "Driver Date": v.get("DriverDateEnglish", ""), "Service": v.get("Service", ""), "Problem": v.get("ProblemCode", ""),
               "Location": v.get("Location", "")} for v in dx_list(dx, "VideoCaptureDevices", "VideoCaptureDevice")]

    mode = fs.get("EnableFrameServerMode")
    if mode is None:
        mode = fs.get("EnableFrameServerModeWow")
    frame = {
        "Frame Server Mode": ("Not configured (Windows default: shared access through Frame Server)" if mode is None else
                              "Enabled (shared camera access through Frame Server)" if decode.to_int(mode) else
                              "Disabled (exclusive camera access for legacy applications)"),
        "Frame Server Service": f"{fs.get('FrameServerStatus')} ({fs.get('FrameServerStartType')})" if fs.get("FrameServerStatus") else "Not found",
    }
    consent_rows = {}
    apps_by_name = {}
    for c in rows_of(consent):
        cap = "Camera" if c.get("Capability") == "webcam" else "Microphone"
        scope = _scope(c.get("Hive"))
        if c.get("App") == "(global)":
            consent_rows[f"{cap} Access ({scope})"] = c.get("Value") or "Not set"
            continue
        app_name = _app_name(c.get("App"))
        app = apps_by_name.setdefault(app_name, {"App": app_name, "Camera": "", "Microphone": "", "_last_used": 0})
        app[cap] = c.get("Value") or ""
        app["_last_used"] = max(app["_last_used"], decode.to_int(c.get("LastUsedStop")) or 0)
    apps = []
    for app in apps_by_name.values():
        last_used = app.pop("_last_used")
        app["Last Used"] = filetime(last_used)
        apps.append(app)
    apps.sort(key=lambda row: row["App"].casefold())
    genicam = {
        str(row.get("Name")): [path for path in str(row.get("Value") or "").split(";") if path]
        for row in rows_of(env)
        if str(row.get("Name") or "").upper().startswith("GENICAM_GENTL")
    }
    genicam = dict(sorted(genicam.items()))
    if not genicam:
        genicam = {"GenICam GenTL Producers": "No GENICAM_GENTL*_PATH variables set"}
    layers = set()
    for program in rows_of(programs):
        search_text = f"{program.get('Name', '')} {program.get('Publisher', '')}"
        for pattern, vendor in TRANSPORT_PATTERNS:
            if pattern.search(search_text):
                detail = f"{program.get('Name')} {program.get('Version') or ''}".strip()
                layers.add(f"{vendor}: {detail}")
                break
    transport = {"Detected Camera Transport Layers": sorted(layers) or "None found in installed programs"}
    return {"groups": [{"title": "Windows Camera Frame Server", "rows": frame}, {"title": "Camera and Microphone Consent", "rows": consent_rows},
                       {"title": "GenICam", "rows": genicam}, {"title": "Transport Layers", "rows": transport}],
            "pnp": pnp_rows, "video_sources": video, "audio_sources": audio, "dxdiag": dxrows, "consent_apps": apps}


def flatten(data) -> dict:
    out = {}
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(g.get("rows") or {})
    return out


def camera_names(data) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in rows_of((data or {}).get("pnp") if isinstance(data, dict) else None):
        if not is_camera(r):
            continue
        name = r.get("Name", "")
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def frame_server_enabled(data):
    text = str(flatten(data).get("Frame Server Mode", ""))
    if text.startswith("Enabled") or text.startswith("Not configured"):
        return True
    if text.startswith("Disabled"):
        return False
    return None


def denied(data) -> list[str]:
    out = []
    for label, value in flatten(data).items():
        if label.endswith(")") and " Access (" in label and str(value).lower() == "deny":
            cap, scope = label.split(" Access (")
            out.append(f"{cap} ({scope}")
    return out


def collect(ctx):
    programs = (ctx.result("installed_programs") or {}).get("rows") if isinstance(ctx.result("installed_programs"), dict) else []
    return build(ctx.shared("pnp_entities"), ctx.query("directshow_capture", DS_SCRIPT), ctx.shared("dxdiag"),
                 first_dict(ctx.query("frame_server", FRAME_SERVER_SCRIPT)), ctx.query("consent", CONSENT_SCRIPT),
                 ctx.query("genicam_env", GENICAM_ENV_SCRIPT), programs)


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (sub_heading("Cameras (Plug and Play)") + list_table(PNP_COLUMNS, data.get("pnp"))
            + kv_groups(data.get("groups"))
            + sub_heading("Application consent") + list_table(CONSENT_COLUMNS, data.get("consent_apps"))
            + sub_heading("DirectShow video capture sources") + list_table(DS_COLUMNS, data.get("video_sources"))
            + sub_heading("DirectShow audio capture sources") + list_table(DS_COLUMNS, data.get("audio_sources"))
            + sub_heading("DirectX capture device detail") + list_table(DX_COLUMNS, data.get("dxdiag")))


SECTION = Section(key="cameras", title="Cameras", group="Hardware", collect=collect, render=render, timeout=120,
                  after=("installed_programs",))
