import os
import subprocess

# Timeouts for the FFmpeg/FFprobe calls made throughout the app. Every
# subprocess needs one: without it a wedged binary blocks its caller forever,
# and most of these run on the Qt main thread, so the window stops repainting
# with no error and no way out.
#
# Values are deliberately generous -- they exist to break a hang, not to cap
# legitimate work.

# Metadata queries (`-show_format`, `-show_streams`, duration). Should return
# in well under a second; the allowance is for cold network shares.
FFPROBE_TIMEOUT = 60

# Rendering a single frame or thumbnail, and keyframe scans that decode a
# bounded interval.
FFMPEG_RENDER_TIMEOUT = 120

# Whole-file stream copy (preprocess/remux). I/O bound and proportional to file
# size, so this is a last-resort ceiling rather than a real expectation.
FFMPEG_REMUX_TIMEOUT = 1800


def get_subprocess_startupinfo():
    """Return startup options that hide subprocess console windows on Windows."""
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo, subprocess.CREATE_NO_WINDOW
    return None, 0
