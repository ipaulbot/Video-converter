import json
import os

RECORDER_SETTINGS_VERSION = 1


def default_recorder_settings():
    return {
        "version": RECORDER_SETTINGS_VERSION,
        "output": {
            "folder": os.path.join(os.path.expanduser("~"), "Videos"),
            "base_name": "Video",
            "encoding": "copy",
            "mode": "Separate videos",
        },
        "timer": {
            "duration": "",
            "time_format": "HH:mm:ss",
            "decimals": "0",
            "use_maximum_time": False,
            "maximum_time": "01:00:00",
        },
        "preview": {
            "fps": 20,
            "width": 480,
        },
        "channels": [],
    }


def normalize_recorder_settings(settings):
    normalized = default_recorder_settings()
    settings = settings or {}
    for key, value in settings.items():
        if key not in ("output", "timer", "preview", "channels"):
            normalized[key] = value
    normalized["version"] = int(settings.get("version") or RECORDER_SETTINGS_VERSION)
    normalized["output"].update(settings.get("output") or {})
    normalized["timer"].update(settings.get("timer") or {})
    normalized["preview"].update(settings.get("preview") or {})
    normalized["channels"] = list(settings.get("channels") or [])
    return normalized


def load_recorder_settings(path):
    if not os.path.exists(path):
        return default_recorder_settings()
    with open(path, "r", encoding="utf-8") as handle:
        return normalize_recorder_settings(json.load(handle))


def save_recorder_settings(path, settings):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(normalize_recorder_settings(settings), handle, indent=4)


def safe_preset_name(name):
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else " " for ch in str(name or "").strip())
    safe = "_".join(part for part in safe.split() if part)
    return safe or "Preset"


def preset_file_path(preset_dir, name):
    return os.path.join(preset_dir, f"{safe_preset_name(name)}.json")


def list_recorder_presets(preset_dir):
    if not os.path.isdir(preset_dir):
        return []
    presets = []
    for filename in os.listdir(preset_dir):
        if filename.lower().endswith(".json"):
            presets.append(os.path.splitext(filename)[0])
    return sorted(presets)
