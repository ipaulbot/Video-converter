from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse
import subprocess
import re

from utils.subprocess_helpers import get_subprocess_startupinfo


CAMERA_SOURCE_TYPES = [
    {
        "id": "rtsp_ip",
        "label": "RTSP/IP Camera",
        "hint": "IP address or RTSP host; optional username, password, and port.",
    },
    {
        "id": "directshow",
        "label": "USB / DirectShow Camera",
        "hint": "Windows device name, for example Logitech Camera.",
    },
    {
        "id": "basler_genicam",
        "label": "Basler / GenICam Camera",
        "hint": "Basler, pylon, or GenICam source string.",
    },
    {
        "id": "stream_url",
        "label": "Stream URL",
        "hint": "RTSP, HTTP, HTTPS, MJPEG, or other FFmpeg-readable URL.",
    },
    {
        "id": "file",
        "label": "File / Test Source",
        "hint": "Local file path for testing the recorder pipeline.",
    },
]


def build_source_text(source_type, value, port="", username="", password=""):
    text = (value or "").strip()
    source_type = (source_type or "").strip()
    if source_type == "directshow":
        if text.lower().startswith(("video=", "audio=")):
            return text
        return f"video={text}" if text else ""
    if source_type == "rtsp_ip":
        if text.lower().startswith("rtsp://"):
            return text
        auth = ""
        if username:
            auth = quote(username, safe="")
            if password:
                auth += f":{quote(password, safe='')}"
            auth += "@"
        port_part = f":{port.strip()}" if str(port or "").strip() else ""
        return f"rtsp://{auth}{text}{port_part}/stream" if text else ""
    return text


def build_rtsp_url(host, port="", username="", password="", path="stream"):
    host_text = (host or "").strip()
    if not host_text:
        return ""
    if host_text.lower().startswith("rtsp://"):
        return host_text
    parsed = urlparse(host_text)
    if parsed.scheme in ("http", "https"):
        host_text = parsed.netloc
        if not (path or "").strip() and parsed.path and parsed.path != "/":
            path = parsed.path
    auth = ""
    if username:
        auth = quote(username, safe="")
        if password:
            auth += f":{quote(password, safe='')}"
        auth += "@"
    port_part = f":{str(port).strip()}" if str(port or "").strip() else ""
    path_text = (path or "stream").strip().lstrip("/")
    return f"rtsp://{auth}{host_text}{port_part}/{path_text}"


def parse_rtsp_url_settings(url):
    text = (url or "").strip()
    if not text:
        return {"host": "", "port": "554", "username": "", "password": "", "path": "axis-media/media.amp"}
    parsed = urlparse(text if "://" in text else f"rtsp://{text}")
    return {
        "host": parsed.hostname or "",
        "port": str(parsed.port or 554),
        "username": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "path": (parsed.path or "/axis-media/media.amp").lstrip("/"),
    }


def axis_mjpeg_preview_url(rtsp_url, resolution="480x270", fps=15):
    parsed = urlparse((rtsp_url or "").strip())
    if parsed.scheme.lower() != "rtsp" or not parsed.hostname:
        return ""
    if "axis-media" not in (parsed.path or "").lower():
        return ""
    auth = ""
    if parsed.username:
        auth = quote(unquote(parsed.username), safe="")
        if parsed.password:
            auth += f":{quote(unquote(parsed.password), safe='')}"
        auth += "@"
    params = urlencode({
        "resolution": resolution,
        "fps": str(fps),
    })
    return f"http://{auth}{parsed.hostname}/axis-cgi/mjpg/video.cgi?{params}"


def _normalize_resolution_value(resolution):
    text = str(resolution or "").strip()
    if not text or text.lower() == "auto":
        return ""
    return text.lower().replace(" ", "")


def _normalize_fps_value(frame_rate):
    text = str(frame_rate or "").strip()
    if not text or text.lower() == "auto":
        return ""
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def apply_axis_rtsp_recording_options(rtsp_url, frame_rate="", resolution=""):
    parsed = urlparse((rtsp_url or "").strip())
    if parsed.scheme.lower() != "rtsp" or not parsed.hostname:
        return rtsp_url
    if "axis-media" not in (parsed.path or "").lower():
        return rtsp_url
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    resolution_value = _normalize_resolution_value(resolution)
    fps_value = _normalize_fps_value(frame_rate)
    if resolution_value:
        params["resolution"] = resolution_value
    if fps_value:
        params["fps"] = fps_value
    return urlunparse(parsed._replace(query=urlencode(params)))


def parse_directshow_video_devices(output):
    devices = []
    in_video_section = False
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if "DirectShow video devices" in line:
            in_video_section = True
            continue
        if "DirectShow audio devices" in line:
            in_video_section = False
            continue
        if not in_video_section or "Alternative name" in line:
            if '" (video)' not in line and '" (video,' not in line:
                continue
        first_quote = line.find('"')
        last_quote = line.rfind('"')
        if first_quote >= 0 and last_quote > first_quote:
            device_name = line[first_quote + 1:last_quote]
            is_non_video = re.search(r'"\s+\((?:none|audio)\)', line, flags=re.IGNORECASE)
            if is_non_video and "basler genicam source" not in device_name.lower():
                continue
            devices.append(device_name)
    return devices


def parse_directshow_audio_devices(output):
    devices = []
    in_audio_section = False
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if "DirectShow audio devices" in line:
            in_audio_section = True
            continue
        if "DirectShow video devices" in line:
            in_audio_section = False
            continue
        if "Alternative name" in line:
            continue
        is_tagged_audio = '" (audio)' in line or '" (audio,' in line
        if not in_audio_section and not is_tagged_audio:
            continue
        first_quote = line.find('"')
        last_quote = line.rfind('"')
        if first_quote >= 0 and last_quote > first_quote:
            device_name = line[first_quote + 1:last_quote]
            if device_name and device_name not in devices:
                devices.append(device_name)
    return devices


def discover_directshow_audio_devices(ffmpeg_path, timeout_seconds=12):
    if not ffmpeg_path:
        return []
    startupinfo, creationflags = get_subprocess_startupinfo()
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_directshow_audio_devices((result.stdout or "") + "\n" + (result.stderr or ""))


def _format_mode_resolution(value):
    match = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", value or "", re.IGNORECASE)
    if not match:
        return ""
    return f"{int(match.group(1))} x {int(match.group(2))}"


def _format_mode_fps(value):
    try:
        fps = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{fps:.2f}"


def parse_directshow_video_options(output):
    modes = []
    seen = set()

    def add_mode(resolution_value, fps_value):
        resolution = _format_mode_resolution(resolution_value)
        frame_rate = _format_mode_fps(fps_value)
        if not resolution or not frame_rate:
            return
        key = (resolution, frame_rate)
        if key in seen:
            return
        seen.add(key)
        modes.append({"resolution": resolution, "frame_rate": frame_rate})

    for line in (output or "").splitlines():
        resolutions = re.findall(r"(?:min\s+|max\s+)?s=(\d+x\d+)", line, flags=re.IGNORECASE)
        fps_values = re.findall(r"fps=([0-9]+(?:\.[0-9]+)?)", line, flags=re.IGNORECASE)
        if not resolutions or not fps_values:
            continue
        add_mode(resolutions[0], fps_values[0])
        if len(resolutions) >= 2 or len(fps_values) >= 2:
            add_mode(resolutions[-1], fps_values[-1])
    return modes


def discover_directshow_video_devices(ffmpeg_path, timeout_seconds=12):
    if not ffmpeg_path:
        return []
    startupinfo, creationflags = get_subprocess_startupinfo()
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_directshow_video_devices((result.stdout or "") + "\n" + (result.stderr or ""))

