"""Qt-free helpers for the Media Player tab.

Everything here is plain Python so it can be unit-tested without a display:
timecode/frame arithmetic, ffprobe parsing, the unsupported-file message, the
fixed "convert and play" preset, and the playlist model.
"""
import math

DEFAULT_FPS = 25.0

MEDIA_PLAYER_DEFAULTS = {"last_folder": "", "panel_count": 2, "volume": 100, "muted": False}


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
