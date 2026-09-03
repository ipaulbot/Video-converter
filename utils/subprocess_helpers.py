import os
import subprocess


def get_subprocess_startupinfo():
    """Return startup options that hide subprocess console windows on Windows."""
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo, subprocess.CREATE_NO_WINDOW
    return None, 0
