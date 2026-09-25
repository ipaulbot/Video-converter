"""Qt-free helpers for the Media Player tab.

Everything here is plain Python so it can be unit-tested without a display:
timecode/frame arithmetic, ffprobe parsing, the unsupported-file message, the
fixed "convert and play" preset, and the playlist model.
"""
import json
import math
import subprocess

from utils.logger import logger
from utils.resources import resource_path
from utils.subprocess_helpers import FFPROBE_TIMEOUT, get_subprocess_startupinfo

DEFAULT_FPS = 25.0

MEDIA_PLAYER_DEFAULTS = {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False}
PLAYER_CONVERT_CUSTOM_ARGS = "-crf 20 -preset veryfast -movflags +faststart"


def format_timecode_ms(milliseconds):
    """Format a millisecond position as H:MM:SS.mmm (hours always shown)."""
    try:
        total_ms = int(max(0, milliseconds))
    except (TypeError, ValueError):
        total_ms = 0
    total_seconds, millis = divmod(total_ms, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def parse_frame_rate(text):
    """Turn ffprobe's r_frame_rate ("30000/1001", "25") into a float; 0.0 when unusable."""
    if text is None:
        return 0.0
    value = str(text).strip()
    if not value:
        return 0.0
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator = float(denominator)
            if denominator == 0:
                return 0.0
            fps = float(numerator) / denominator
        else:
            fps = float(value)
    except (TypeError, ValueError):
        return 0.0
    return fps if fps > 0 else 0.0


def frame_step_ms(fps):
    if not fps or fps <= 0:
        fps = DEFAULT_FPS
    return max(1, int(round(1000.0 / fps)))


def frame_index(position_ms, fps):
    if not fps or fps <= 0 or not position_ms or position_ms <= 0:
        return 0
    return int(math.floor(position_ms * fps / 1000.0))


def total_frames(duration_ms, fps, nb_frames=0):
    try:
        if int(nb_frames) > 0:
            return int(nb_frames)
    except (TypeError, ValueError):
        pass
    return frame_index(duration_ms, fps)


def format_readout(position_ms, duration_ms, fps, nb_frames=0):
    text = f"{format_timecode_ms(position_ms)} / {format_timecode_ms(duration_ms)}"
    if fps and fps > 0:
        text += f" · frame {frame_index(position_ms, fps)} / {total_frames(duration_ms, fps, nb_frames)}"
    return text


def _empty_probe():
    return {"ok": False, "fps": 0.0, "nb_frames": 0, "duration_ms": 0,
            "container": "", "vcodec": "", "acodec": ""}


def probe_media_info(path, runner=subprocess.run):
    """Ask ffprobe for the frame rate, frame count, duration and codecs of `path`.

    `runner` is injectable so tests never spawn a process. Any failure returns a dict
    with ok=False and zero/empty fields; callers treat that as "unknown".
    """
    command = [
        resource_path("ffprobe.exe"), "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,r_frame_rate,avg_frame_rate,nb_frames:format=format_name,duration",
        "-of", "json", path,
    ]
    startupinfo, creationflags = get_subprocess_startupinfo()
    try:
        result = runner(command, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT,
                        startupinfo=startupinfo, creationflags=creationflags)
        if result.returncode != 0:
            return _empty_probe()
        payload = json.loads(result.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        logger.debug("probe_media_info failed for %s", path, exc_info=True)
        return _empty_probe()
    info = _empty_probe()
    info["ok"] = True
    video = next((s for s in payload.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in payload.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video:
        info["vcodec"] = str(video.get("codec_name") or "")
        info["fps"] = parse_frame_rate(video.get("r_frame_rate")) or parse_frame_rate(video.get("avg_frame_rate"))
        try:
            info["nb_frames"] = max(0, int(video.get("nb_frames") or 0))
        except (TypeError, ValueError):
            info["nb_frames"] = 0
    if audio:
        info["acodec"] = str(audio.get("codec_name") or "")
    fmt = payload.get("format", {}) or {}
    info["container"] = str(fmt.get("format_name") or "").split(",")[0].strip()
    try:
        info["duration_ms"] = max(0, int(round(float(fmt.get("duration") or 0) * 1000)))
    except (TypeError, ValueError):
        info["duration_ms"] = 0
    return info


def unsupported_message(info):
    """Tile text shown when the Windows backend cannot decode a file."""
    if not info or not info.get("ok"):
        return "Windows cannot play this file."
    vcodec = info.get("vcodec") or "unknown"
    container = info.get("container") or "unknown"
    acodec = info.get("acodec") or ""
    codecs = f"{vcodec}/{acodec}" if acodec else vcodec
    return f"Windows cannot play {codecs} in {container}."


def player_convert_settings(base_settings):
    """Converter settings for "Convert to MP4 (H.264) and play": fixed, predictable preset."""
    settings = dict(base_settings or {})
    settings.update({
        "output_format": "mp4",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "160k",
        "video_bitrate": "Auto",
        "video_size": "Auto",
        "framerate": "Auto",
        "keyframe_interval": 0,
        "volume_percentage": 100,
        "copy_only": False,
        "use_gpu": False,
        "text_overlay": "None",
        "delete_after_conversion": False,
        "use_backup": False,
        "custom_console_command": PLAYER_CONVERT_CUSTOM_ARGS,
    })
    return settings
