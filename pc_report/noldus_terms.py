"""Noldus/NVC vocabulary and file scanners used by the Noldus Summary."""
from __future__ import annotations

import os

NVC_RELATED_TERMS = (
    "noldus",
    "ethovision",
    "etho vision",
    "observer",
    "mediarecorder",
    "media recorder",
    "catwalk",
    "daniovision",
    "danioscope",
    "ultravox",
    "facereader",
    "viso",
    "basler",
    "pylon",
    "genicam",
    "gige vision",
    "coaxpress",
    "camera link",
    "euresys",
    "leadtools",
    "samplegrabber",
    "resizer filter",
    "rtsp source",
    "tee filter",
    "timestamp corrector",
    "video mixer",
    "hardwareinterface",
    "sentinel hasp",
    "sentinel ldk",
    "safenet",
    "thales",
    "hardlock",
)

RUNTIME_TERMS = (
    "visual c++",
    "vc++ redistributable",
    ".net framework",
    ".net runtime",
    ".net desktop runtime",
    "windows desktop runtime",
    "directx",
    "intel ipp",
    "noldus - ipp",
    "leadtools",
)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _row_text(row):
    if isinstance(row, dict):
        return " ".join(str(v or "") for v in row.values()).lower()
    return str(row or "").lower()


def filter_nvc_related_items(items):
    matches = []
    for item in _as_list(items):
        text = _row_text(item)
        if any(term in text for term in NVC_RELATED_TERMS):
            if "hypervisor" in text and "noldus" not in text:
                continue
            matches.append(item)
            continue
        if "noldusipp" in text or "noldus ipp" in text:
            matches.append(item)
    return matches


def normalize_nvc_program_row(row):
    return {
        "Name": row.get("Name") or row.get("DisplayName") or "",
        "Version": row.get("Version") or row.get("DisplayVersion") or "",
        "Publisher": row.get("Publisher") or "",
        "InstallDate": row.get("InstallDate") or "",
        "InstallLocation": row.get("InstallLocation") or "",
    }


def normalize_logical_disk_rows(rows):
    normalized = []
    for row in _as_list(rows):
        if not isinstance(row, dict):
            continue
        device_id = row.get("DeviceID") or row.get("DriveLetter") or ""
        if device_id and len(str(device_id)) == 1:
            device_id = f"{device_id}:"
        if not device_id:
            continue
        normalized.append({
            "DeviceID": device_id,
            "DriveType": row.get("DriveType") or "",
            "FileSystem": row.get("FileSystem") or "",
            "Size": row.get("Size"),
            "FreeSpace": row.get("FreeSpace") if "FreeSpace" in row else row.get("SizeRemaining"),
            "VolumeName": row.get("VolumeName") or row.get("FileSystemLabel") or "",
        })
    return normalized


def scan_codec_files(root_paths, max_files=500):
    rows = []
    seen = set()
    extensions = (".ax", ".acm")
    for root in root_paths:
        if not root or not os.path.isdir(root):
            continue
        try:
            filenames = sorted(os.listdir(root))
        except Exception:
            continue
        for filename in filenames:
            if len(rows) >= max_files:
                return rows
            if not filename.lower().endswith(extensions):
                continue
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({"Name": os.path.splitext(filename)[0], "File": path, "Source": "filesystem"})
    return rows


def scan_nvc_filter_files(root_paths, max_files=500):
    rows = []
    seen = set()
    extensions = (".ax", ".dll")
    for root in root_paths:
        if not root or not os.path.isdir(root):
            continue
        for current_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith("$") and d.lower() not in {"windowsapps"}]
            for filename in files:
                if len(rows) >= max_files:
                    return rows
                path = os.path.join(current_root, filename)
                if not filename.lower().endswith(extensions):
                    continue
                row = {"Name": os.path.splitext(filename)[0], "File": path, "Source": "filesystem"}
                if not filter_nvc_related_items([row]):
                    continue
                key = path.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def nvc_filter_roots():
    roots = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Common Files", "Noldus"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Common Files", "Noldus"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Basler"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Basler"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Daheng Imaging"),
    ]
    for value in os.environ.values():
        if not isinstance(value, str):
            continue
        for part in value.split(";"):
            part = part.strip()
            if not part:
                continue
            lower_part = part.lower()
            if (
                filter_nvc_related_items([{"Value": part}])
                and os.path.isdir(part)
                and (
                    "program files" in lower_part
                    or "common files" in lower_part
                    or "basler" in lower_part
                    or "daheng" in lower_part
                )
            ):
                roots.append(part)
    deduped = []
    seen = set()
    for root in roots:
        normalized = os.path.abspath(root)
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        deduped.append(normalized)
    return deduped
