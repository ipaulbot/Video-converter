import os
import subprocess
from utils.logger import logger
from utils.resources import resource_path
from utils.subprocess_helpers import get_subprocess_startupinfo

# Helper to hide console windows on Windows
def _get_subprocess_startupinfo():
    return get_subprocess_startupinfo()

def get_supported_encoders():
    try:
        ffmpeg_bin = resource_path('ffmpeg.exe')
        if not os.path.exists(ffmpeg_bin):
            logger.error("ffmpeg.exe not found. Skipping GPU encoder detection.")
            return {}
        startupinfo, creationflags = _get_subprocess_startupinfo()
        result = subprocess.run(
            [ffmpeg_bin, '-encoders'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        encoders = result.stdout.lower()
        supported = {}
        vendor_encoders = {
            'nvidia': {'h264': 'h264_nvenc', 'hevc': 'hevc_nvenc'},
            'intel': {'h264': 'h264_qsv', 'hevc': 'hevc_qsv'},
            'amd': {'h264': 'h264_amf', 'hevc': 'hevc_amf'},
        }
        for vendor, candidates in vendor_encoders.items():
            available = {kind: encoder for kind, encoder in candidates.items() if encoder in encoders}
            if available:
                supported[vendor] = available
        return supported
    except subprocess.CalledProcessError as e:
        logger.error(f"Error detecting supported encoders: {e.stderr}")
        return {}
    except Exception as e:
        logger.error(f"General error detecting GPU encoders: {e}")
        return {}

def get_best_gpu_encoder():
    """Auto-detect the best available GPU encoder."""
    supported = get_supported_encoders()
    if 'nvidia' in supported:
        return 'nvidia', supported['nvidia']
    if 'amd' in supported:
        return 'amd', supported['amd']
    if 'intel' in supported:
        return 'intel', supported['intel']
    return None, None

GPU_ENCODERS = get_supported_encoders()

