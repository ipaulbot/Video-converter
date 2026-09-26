import atexit
import re
import subprocess
import sys
import threading
from typing import NamedTuple
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

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
        "id": "screen",
        "label": "Screen capture",
        "hint": (
            "Leave empty (or 'desktop') for the whole screen, 'monitor=1' for GPU capture of one "
            "display, 'region=X,Y,WxH' for part of the desktop, or a window title to capture one "
            "window. Video Settings lists the displays, open windows and a region picker."
        ),
    },
    {
        "id": "file",
        "label": "File / Test Source",
        "hint": "Local file path for testing the recorder pipeline.",
    },
]

SCREEN_SOURCE_PREFIX = "screen="
SCREEN_DEFAULT_TARGET = "desktop"      # gdigrab's name for the whole screen
SCREEN_MONITOR_PREFIX = "monitor="     # one display via Desktop Duplication (ddagrab), 1-based

# DirectShow video filters that are not cameras and must not be offered as one.
# Medialooks' filter pops a licence dialog inside the ffmpeg process as soon as it
# is instantiated, which blocks the recording; the built-in screen source
# (gdigrab / ddagrab) replaces it.
HIDDEN_DIRECTSHOW_VIDEO_DEVICES = ("medialooks",)


def is_hidden_directshow_video_device(name):
    text = (name or "").strip().lower()
    if text.startswith("video="):
        text = text[len("video="):]
    return bool(text) and any(marker in text for marker in HIDDEN_DIRECTSHOW_VIDEO_DEVICES)


_MONITOR_PATTERN = re.compile(r"^monitor\s*[= ]\s*(\d+)$", re.IGNORECASE)
SCREEN_REGION_PREFIX = "region="      # region=X,Y,WxH in virtual-desktop pixels (gdigrab crop)
_REGION_PATTERN = re.compile(
    r"^region\s*=\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(\d+)\s*x\s*(\d+)$", re.IGNORECASE
)


def build_region_source_value(x, y, width, height):
    return f"{SCREEN_REGION_PREFIX}{int(x)},{int(y)},{int(width)}x{int(height)}"


def _parse_region(text):
    match = _REGION_PATTERN.match((text or "").strip())
    if not match:
        return None
    x, y, width, height = (int(match.group(i)) for i in range(1, 5))
    if width <= 0 or height <= 0:
        return None
    return (x, y, width, height)


def build_screen_source_text(value):
    """`screen=desktop` / `screen=title=<window>` / `screen=region=X,Y,WxH` (gdigrab)
    or `screen=monitor=N` (ddagrab)."""
    text = (value or "").strip()
    if text.lower().startswith(SCREEN_SOURCE_PREFIX):
        text = text[len(SCREEN_SOURCE_PREFIX):].strip()
    if not text or text.lower() == SCREEN_DEFAULT_TARGET:
        return f"{SCREEN_SOURCE_PREFIX}{SCREEN_DEFAULT_TARGET}"
    monitor = _MONITOR_PATTERN.match(text)
    if monitor:
        return f"{SCREEN_SOURCE_PREFIX}{SCREEN_MONITOR_PREFIX}{int(monitor.group(1))}"
    region = _parse_region(text)
    if region:
        return f"{SCREEN_SOURCE_PREFIX}{build_region_source_value(*region)}"
    if text.lower().startswith("title="):
        return f"{SCREEN_SOURCE_PREFIX}{text}"
    return f"{SCREEN_SOURCE_PREFIX}title={text}"


def screen_region(source_text):
    """(x, y, width, height) of a `screen=region=…` source, else None."""
    text = (source_text or "").strip()
    if not text.lower().startswith(SCREEN_SOURCE_PREFIX):
        return None
    return _parse_region(text[len(SCREEN_SOURCE_PREFIX):])


# Windows whose title is not something a user would pick to record.
_SHELL_WINDOW_TITLES = {"program manager", "windows input experience", "settings", "microsoft text input application"}
_WINDOW_TITLE_LIMIT = 40


def _enumerate_windows_win32():
    """Yield (handle, title, visible) for every top-level window."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    windows = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
        # Minimised windows stay listed: the user picks one here and restores it
        # before recording. Hidden helper windows do not.
        visible = bool(user32.IsWindowVisible(hwnd))
        if visible:
            # Cloaked windows (suspended UWP apps, other virtual desktops) report
            # visible but have no pixels to grab.
            cloaked = wintypes.DWORD(0)
            try:
                ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            except OSError:
                cloaked = wintypes.DWORD(0)
            visible = cloaked.value == 0
        windows.append((int(hwnd), title, visible))
        return True

    user32.EnumWindows(proc(callback), 0)
    return windows


def list_capture_windows(enumerate_windows=None):
    """Titles of the windows gdigrab can capture right now, sorted, without duplicates."""
    if enumerate_windows is None:
        if sys.platform != "win32":
            return []
        enumerate_windows = _enumerate_windows_win32
    try:
        entries = list(enumerate_windows())
    except (OSError, AttributeError):
        return []
    titles = []
    for _handle, title, visible in entries:
        title = (title or "").strip()
        if not visible or not title or title.lower() in _SHELL_WINDOW_TITLES or title in titles:
            continue
        titles.append(title)
    return sorted(titles, key=str.lower)[:_WINDOW_TITLE_LIMIT]


def screen_monitor_index(source_text):
    """1-based monitor number of a `screen=monitor=N` source, else None."""
    text = (source_text or "").strip()
    if not text.lower().startswith(SCREEN_SOURCE_PREFIX):
        return None
    monitor = _MONITOR_PATTERN.match(text[len(SCREEN_SOURCE_PREFIX):].strip())
    if not monitor:
        return None
    index = int(monitor.group(1))
    return index if index >= 1 else None


def build_source_text(source_type, value, port="", username="", password=""):
    text = (value or "").strip()
    source_type = (source_type or "").strip()
    if source_type == "directshow":
        if text.lower().startswith(("video=", "audio=")):
            return text
        return f"video={text}" if text else ""
    if source_type == "screen":
        return build_screen_source_text(text)
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


def stream_host_problem(address):
    """Explain why `address` cannot reach a camera, or "" when it looks usable.

    Only one class of mistake is caught: a host made of digits and dots that
    is not a valid IPv4 literal (a four-digit octet, three octets, an octet
    over 255). ffmpeg does not reject those -- it hands them to DNS, which
    fails with "Failed to resolve hostname", and the preview reconnects for
    ever. Host names and full URLs are left alone: the network decides.
    """
    text = (address or "").strip()
    if not text:
        return ""
    if "://" in text:
        try:
            host = urlparse(text).hostname or ""
        except ValueError:
            return ""
    else:
        host = text.split("/", 1)[0]
        if host.count(":") == 1:
            host = host.split(":", 1)[0]
    if not host or not re.fullmatch(r"[0-9.]+", host):
        return ""
    octets = host.split(".")
    if len(octets) == 4 and all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
        return ""
    return f"'{host}' is not a valid IP address (four numbers 0-255 separated by dots)."


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
            if is_hidden_directshow_video_device(device_name):
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


class DeviceScan(NamedTuple):
    """Result of one `ffmpeg -list_devices` run.

    `ok` is False when ffmpeg was missing, crashed or timed out; callers should
    then keep whatever lists they already had rather than treat the machine as
    having no cameras.
    """

    video: list
    audio: list
    ok: bool


_ACTIVE_PROBES: list = []
_PROBES_LOCK = threading.Lock()


def _register_probe(probe):
    with _PROBES_LOCK:
        _ACTIVE_PROBES.append(probe)


def _unregister_probe(probe):
    with _PROBES_LOCK:
        if probe in _ACTIVE_PROBES:
            _ACTIVE_PROBES.remove(probe)


def active_device_probes():
    with _PROBES_LOCK:
        return list(_ACTIVE_PROBES)


def terminate_device_probes():
    """Kill every device listing still running.

    Called from the recorder's shutdown() and at interpreter exit. A listing
    that outlives its parent stays queued on DirectShow enumeration and makes
    every later listing on the machine time out, so leaving one behind is not
    harmless.
    """
    for probe in active_device_probes():
        try:
            if probe.poll() is None:
                probe.kill()
        except OSError:
            pass
        _unregister_probe(probe)


atexit.register(terminate_device_probes)


def discover_directshow_devices(ffmpeg_path, timeout_seconds=12):
    """List DirectShow cameras and microphones with a single ffmpeg run.

    Blocking (several seconds with many devices) -- call it off the GUI thread.
    """
    if not ffmpeg_path:
        return DeviceScan([], [], False)
    startupinfo, creationflags = get_subprocess_startupinfo()
    try:
        probe = subprocess.Popen(
            [ffmpeg_path, "-hide_banner", "-nostdin", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return DeviceScan([], [], False)
    _register_probe(probe)
    try:
        stdout, stderr = probe.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        probe.kill()
        try:
            probe.communicate(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
        return DeviceScan([], [], False)
    except (OSError, subprocess.SubprocessError):
        return DeviceScan([], [], False)
    finally:
        _unregister_probe(probe)
    output = (stdout or "") + "\n" + (stderr or "")
    return DeviceScan(
        parse_directshow_video_devices(output),
        parse_directshow_audio_devices(output),
        True,
    )


def discover_directshow_audio_devices(ffmpeg_path, timeout_seconds=12):
    return discover_directshow_devices(ffmpeg_path, timeout_seconds).audio


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
    return discover_directshow_devices(ffmpeg_path, timeout_seconds).video

