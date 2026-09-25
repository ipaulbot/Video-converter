import json
import os

from utils.logger import logger
from utils.paths import get_data_dir


def _vc_public_root() -> str:
    """Return Public Documents Noldus/NVC root for Video Converter folders.

    On Windows this resolves to C:\\Users\\Public\\Documents\\Noldus\\NVC.
    On other OSes, falls back to the app data dir "VideoConverter".
    """
    if os.name == 'nt':
        public_base = os.environ.get('PUBLIC', r'C:\\Users\\Public')
        root = os.path.join(public_base, 'Documents', 'Noldus', 'NVC')
        os.makedirs(root, exist_ok=True)
        return root
    # Non-Windows fallback to data dir
    return get_data_dir('VideoConverter')

_VC_ROOT = _vc_public_root()

default_settings = {
    "auto_run": False,
    "copy_only": False,
    # Default folders under Public Documents\Noldus\NVC (Windows)
    "source_folder": os.path.join(_VC_ROOT, "Source"),
    "destination_folder": os.path.join(_VC_ROOT, "Destination"),
    "backup_folder": os.path.join(_VC_ROOT, "Backup"),
    "delete_after_conversion": False,
    "retention_time": 0,
    "use_backup": False,
    "output_format": "mp4",
    "video_codec": "libx264",
    "audio_codec": "aac",
    "video_size": "Auto",
    "video_bitrate": "Auto",
    "framerate": "Auto",
    "no_time_restrictions": True,
    "start_time": "00:00",
    "end_time": "23:59",
    # Start unlocked on first run (teal/idle mode)
    "locked": False,
    "show_drop_confirmation": False,
    "dont_show_drop_dialog": False,
    "log_folder": get_data_dir("logs"),
    "game_unlocked": False,
    # New in 2.0: GIF export and UX controls
    "gif_fps": 10,
    "gif_max_width": 640,
    "gif_loop": True,
    "gif_quick": False,
    "close_on_x": True,
    "startup_common": False,
    # Custom presets (initially None/empty)
    "custom_preset_1": None,
    "custom_preset_2": None,
    # Text overlay default
    "text_overlay": "None",
    "visible_tool_tabs": {
        "conversion_log": True,
        "converted_files": True,
        "video_inspection": True,
        "pc_report": False,
        "lossless_editor": False,
        "multi_source_recorder": True,
        "media_player": False,
    }
}

config_file = os.path.join(get_data_dir(), "config.json")

def coerce_retention_days(value) -> int:
    try:
        days = int(str(value).strip())
    except Exception:
        days = 0
    return max(0, min(30, days))

def normalize_settings(settings):
    normalized = default_settings.copy()
    normalized.update(settings or {})
    normalized["retention_time"] = coerce_retention_days(normalized.get("retention_time", 0))
    default_tabs = default_settings["visible_tool_tabs"]
    supplied_tabs = normalized.get("visible_tool_tabs")
    if not isinstance(supplied_tabs, dict):
        supplied_tabs = {}
    normalized["visible_tool_tabs"] = {
        key: bool(supplied_tabs.get(key, default_value))
        for key, default_value in default_tabs.items()
    }
    return normalized

def load_settings():
    if os.path.exists(config_file):
        try:
            with open(config_file, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load settings from {config_file}: {e}")
            settings = default_settings.copy()
    else:
        settings = default_settings.copy()
    # Ensure required keys exist (merge defaults)
    merged = normalize_settings(settings)
    # Create default VC folders if missing
    try:
        for key in ("source_folder", "destination_folder", "backup_folder"):
            path = merged.get(key)
            if path:
                os.makedirs(path, exist_ok=True)
    except OSError:
        # Not fatal here, but conversions will fail later with a less obvious
        # message, so name the folder that could not be created.
        logger.warning("Could not create one of the configured folders: %s",
                       {k: merged.get(k) for k in
                        ("source_folder", "destination_folder", "backup_folder")},
                       exc_info=True)
    return merged

def save_settings(settings):
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(normalize_settings(settings), f, indent=4)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
