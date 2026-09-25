"""GPU encoder detection.

Detection shells out to `ffmpeg -encoders`, which is slow enough that it must
not happen at import time and must not happen twice. `get_supported_encoders`
is therefore cached; call it freely.
"""
import os
import subprocess
from functools import lru_cache

from utils.logger import logger
from utils.resources import resource_path
from utils.subprocess_helpers import get_subprocess_startupinfo

# `ffmpeg -encoders` only enumerates build capabilities, so it returns fast on a
# healthy install. The timeout is here to stop a wedged binary hanging the
# caller indefinitely -- previously this ran at import and could hang startup
# before any window appeared.
_DETECT_TIMEOUT_SECONDS = 20

_VENDOR_ENCODERS = {
    'nvidia': {'h264': 'h264_nvenc', 'hevc': 'hevc_nvenc'},
    'intel': {'h264': 'h264_qsv', 'hevc': 'hevc_qsv'},
    'amd': {'h264': 'h264_amf', 'hevc': 'hevc_amf'},
}


@lru_cache(maxsize=1)
def get_supported_encoders():
    """Return {vendor: {kind: encoder_name}} for GPU encoders ffmpeg can use.

    Cached: the subprocess runs at most once per process. Returns {} on any
    failure, so callers can treat an empty mapping as "no GPU encoding".
    """
    try:
        ffmpeg_bin = resource_path('ffmpeg.exe')
        if not os.path.exists(ffmpeg_bin):
            logger.error("ffmpeg.exe not found. Skipping GPU encoder detection.")
            return {}
        startupinfo, creationflags = get_subprocess_startupinfo()
        result = subprocess.run(
            [ffmpeg_bin, '-encoders'],
            capture_output=True,
            text=True,
            check=True,
            timeout=_DETECT_TIMEOUT_SECONDS,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        encoders = result.stdout.lower()
        supported = {}
        for vendor, candidates in _VENDOR_ENCODERS.items():
            available = {kind: encoder for kind, encoder in candidates.items()
                         if encoder in encoders}
            if available:
                supported[vendor] = available
        return supported
    except subprocess.TimeoutExpired:
        logger.error("GPU encoder detection timed out after %ss; assuming no GPU encoders.",
                     _DETECT_TIMEOUT_SECONDS)
        return {}
    except subprocess.CalledProcessError as e:
        logger.error("Error detecting supported encoders: %s", e.stderr)
        return {}
    except Exception:
        logger.exception("General error detecting GPU encoders.")
        return {}


def get_best_gpu_encoder():
    """Auto-detect the best available GPU encoder, preferring NVIDIA then AMD."""
    supported = get_supported_encoders()
    for vendor in ('nvidia', 'amd', 'intel'):
        if vendor in supported:
            return vendor, supported[vendor]
    return None, None
