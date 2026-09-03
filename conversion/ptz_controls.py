from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    build_opener,
)


def _axis_http_base(camera_source):
    parsed = urlparse((camera_source or "").strip())
    if not parsed.hostname:
        return ""
    auth = ""
    if parsed.username:
        auth = quote(parsed.username, safe="")
        if parsed.password:
            auth += f":{quote(parsed.password, safe='')}"
        auth += "@"
    return f"http://{auth}{parsed.hostname}"


def axis_vapix_ptz_url(camera_source, action, move="", preset_name=""):
    base = _axis_http_base(camera_source)
    if not base:
        return ""
    params = []
    if action == "move":
        params.append(("move", move))
    elif action == "stop":
        params.append(("move", "stop"))
    elif action == "home":
        params.append(("move", "home"))
    elif action == "zoom_in":
        params.append(("zoom", "tele"))
    elif action == "zoom_out":
        params.append(("zoom", "wide"))
    elif action == "goto_preset":
        params.append(("gotoserverpresetname", preset_name))
    elif action == "set_preset":
        params.append(("setserverpresetname", preset_name))
    elif action == "list_presets":
        params.append(("query", "presetposall"))
    else:
        return ""
    return f"{base}/axis-cgi/com/ptz.cgi?{urlencode(params)}"


def axis_vapix_continuous_url(camera_source, pan=None, tilt=None, zoom=None):
    """Build an Axis VAPIX continuous-movement URL.

    Use ``pan`` and ``tilt`` together for joystick-style movement. Pass ``0`` for both to
    halt panning/tilting. Use ``zoom`` independently; pass ``0`` to stop zoom motion.
    """
    base = _axis_http_base(camera_source)
    if not base:
        return ""
    params = []
    if pan is not None or tilt is not None:
        pan_value = int(pan or 0)
        tilt_value = int(tilt or 0)
        params.append(("continuouspantiltmove", f"{pan_value},{tilt_value}"))
    if zoom is not None:
        params.append(("continuouszoommove", str(int(zoom))))
    if not params:
        return ""
    return f"{base}/axis-cgi/com/ptz.cgi?{urlencode(params)}"


def _split_credentials(url):
    parsed = urlparse(url or "")
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    sanitized = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return sanitized, username, password


def send_axis_vapix_request(url, timeout=3):
    if not url:
        return ""
    sanitized_url, username, password = _split_credentials(url)
    if username:
        manager = HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, sanitized_url, username, password)
        opener = build_opener(HTTPDigestAuthHandler(manager), HTTPBasicAuthHandler(manager))
    else:
        opener = build_opener()
    with opener.open(sanitized_url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_axis_ptz_presets(response_text):
    presets = []
    for line in (response_text or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().lower().startswith("serverpresetname") and value.strip():
            presets.append(value.strip())
    if presets:
        return presets
    for key, value in parse_qsl(response_text or "", keep_blank_values=False):
        if key.lower().startswith("serverpresetname") and value:
            presets.append(value)
    return presets
