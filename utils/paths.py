import os
import sys


def get_data_dir(subfolder: str | None = None) -> str:
    """Return the root directory for all persistent NVC data files.

    Windows: %APPDATA%\\NVC (e.g. C:\\Users\\<user>\\AppData\\Roaming\\NVC)
    macOS:   ~/Library/Application Support/NVC
    Linux:   ~/.local/share/NVC

    If *subfolder* is provided (e.g. "logs", "game"), it is created beneath
    the root directory and that path is returned.
    """
    # An explicit override wins. The test suite points this at a temporary
    # directory so running tests cannot read or rewrite the real user's
    # settings -- which it previously did, silently changing which tabs were
    # visible.
    override = os.environ.get("NVC_DATA_DIR")
    if override:
        base = override
        os.makedirs(base, exist_ok=True)
        if subfolder:
            full = os.path.join(base, subfolder)
            os.makedirs(full, exist_ok=True)
            return full
        return base

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            # Fallback to typical Roaming path if APPDATA not set
            appdata = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        base = os.path.join(appdata, "NVC")
    elif sys.platform == "darwin":  # macOS
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "NVC")
    else:  # Linux and others
        base = os.path.join(os.path.expanduser("~/.local/share"), "NVC")

    os.makedirs(base, exist_ok=True)
    if subfolder:
        full = os.path.join(base, subfolder)
        os.makedirs(full, exist_ok=True)
        return full
    return base


def log_dir(settings: dict | None = None) -> str:
    """Return the folder used for per-file conversion logs.

    Honour Settings -> Folders -> Log Folder when it is set and can be
    created; otherwise use the application data logs folder. The root
    application log is unaffected because it opens before settings are read.
    """
    wanted = settings.get("log_folder") if isinstance(settings, dict) else None
    if isinstance(wanted, str) and wanted.strip():
        try:
            os.makedirs(wanted, exist_ok=True)
            return wanted
        except OSError:
            pass
    return get_data_dir("logs")
