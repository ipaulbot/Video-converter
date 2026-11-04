import os
import shutil
import sys

from utils.paths import get_data_dir

_STABLE_FROZEN_BINARIES = frozenset({"ffmpeg.exe", "ffprobe.exe"})


def _stage_frozen_binary(bundled_path: str, filename: str) -> str:
    """Copy a bundled helper binary to a stable per-user path when frozen.

    PyInstaller one-file builds unpack binaries into a fresh Temp\\_MEIxxxxxx
    directory on every launch. Because Windows Defender Firewall keys rules on
    the full executable path, running ffmpeg.exe from _MEIxxxxxx causes a new
    firewall prompt every time NVC starts and touches a network/DirectShow
    socket. Staging the binary under %APPDATA%\\NVC\\bin keeps its path fixed
    across launches while preserving the single-file distribution.
    """
    try:
        bin_dir = get_data_dir("bin")
        stable_path = os.path.join(bin_dir, filename)
        src_stat = os.stat(bundled_path)
        if os.path.isfile(stable_path):
            dst_stat = os.stat(stable_path)
            if dst_stat.st_size == src_stat.st_size and int(dst_stat.st_mtime) == int(src_stat.st_mtime):
                return stable_path
        tmp_path = f"{stable_path}.{os.getpid()}.tmp"
        shutil.copy2(bundled_path, tmp_path)
        os.replace(tmp_path, stable_path)
        return stable_path
    except OSError:
        # If the existing stable copy is locked by a running process or the
        # data dir is not writable, use the existing stable file if present,
        # otherwise fall back to the unpacked bundle path.
        try:
            if os.path.isfile(stable_path):
                return stable_path
        except Exception:
            pass
        return bundled_path


def resource_path(relative_path):
    """
    Get the absolute path to a resource, works for development and PyInstaller.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    bundled = os.path.join(base_path, relative_path)
    norm_name = os.path.basename(relative_path).lower()
    if (
        getattr(sys, 'frozen', False)
        and hasattr(sys, '_MEIPASS')
        and norm_name in _STABLE_FROZEN_BINARIES
        and os.path.isfile(bundled)
    ):
        return _stage_frozen_binary(bundled, os.path.basename(relative_path))
    return bundled
