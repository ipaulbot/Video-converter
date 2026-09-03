import os
import sys
from typing import Optional

def get_data_dir(subfolder: Optional[str] = None) -> str:
    """Return the root directory for all persistent NVC data files.

    Windows: %APPDATA%\\NVC (e.g. C:\\Users\\<user>\\AppData\\Roaming\\NVC)
    macOS:   ~/Library/Application Support/NVC
    Linux:   ~/.local/share/NVC

    If *subfolder* is provided (e.g. "logs", "game"), it is created beneath
    the root directory and that path is returned.
    """
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
