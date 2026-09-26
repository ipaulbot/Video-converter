"""Which hardware H.264 encoder, if any, works on this machine.

The bundled ffmpeg is a "full" build and lists h264_nvenc, h264_qsv and
h264_amf whatever GPU is present; the only way to know which one initialises
is to try. Each candidate encodes two frames of a synthetic source into a null
sink (nothing written), which takes 0.2-1 s, so callers run the probe off the
GUI thread and the result is cached per ffmpeg path.
"""

import subprocess
import threading

from utils.subprocess_helpers import get_subprocess_startupinfo

# Preference order: NVIDIA first (most common on lab PCs with a discrete GPU),
# then Intel Quick Sync (any recent Intel CPU), then AMD.
HARDWARE_H264_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf")

_cache = {}
_cache_lock = threading.Lock()

# What ffmpeg prints when a hardware encoder is listed but cannot start here.
_ENCODER_FAILURE_MARKERS = (
    "error while opening encoder",
    "cannot load",                 # nvcuda.dll / nvEncodeAPI64.dll missing
    "no capable devices",
    "error initializing",          # QSV: an internal MFX session
    "failed to initialise",
    "failed to initialize",
    "failed to create",
    "openencodesessionex failed",
)


def looks_like_encoder_failure(error_text):
    text = (error_text or "").lower()
    return any(marker in text for marker in _ENCODER_FAILURE_MARKERS)


def clear_hardware_encoder_cache():
    with _cache_lock:
        _cache.clear()


def _probe_command(ffmpeg_path, encoder):
    return [
        ffmpeg_path, "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "lavfi", "-i", "nullsrc=s=256x256:r=5",
        "-frames:v", "2", "-pix_fmt", "yuv420p", "-c:v", encoder,
        "-f", "null", "-",
    ]


def probe_hardware_h264_encoder(ffmpeg_path, timeout_seconds=8, candidates=HARDWARE_H264_ENCODERS, run=None):
    """The first encoder in `candidates` that encodes here, or "" for none."""
    if not ffmpeg_path:
        return ""
    with _cache_lock:
        if ffmpeg_path in _cache:
            return _cache[ffmpeg_path]
    if run is None:
        startupinfo, creationflags = get_subprocess_startupinfo()

        def run(command, **kwargs):
            return subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
                **kwargs,
            )

    found = ""
    for encoder in candidates:
        try:
            result = run(_probe_command(ffmpeg_path, encoder), timeout=timeout_seconds)
        except (OSError, subprocess.SubprocessError):
            continue
        if getattr(result, "returncode", 1) == 0:
            found = encoder
            break
    with _cache_lock:
        _cache[ffmpeg_path] = found
    return found
