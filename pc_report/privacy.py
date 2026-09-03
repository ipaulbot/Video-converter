import re
from copy import deepcopy

def mask_string(value: str, keep: int = 4) -> str:
    if value is None:
        return value
    s = str(value)
    if len(s) <= keep:
        return '*' * len(s)
    return s[:2] + '*' * max(1, len(s) - keep - 2) + s[-keep:]

def mask_mac(mac: str) -> str:
    if not mac:
        return mac
    mc = str(mac).replace('-', ':')
    parts = mc.split(':')
    if len(parts) >= 6:
        return f"{parts[0]}:{parts[1]}:**:**:{parts[-2]}:{parts[-1]}"
    return mask_string(mac)

def redact_user_paths(path: str) -> str:
    if not path:
        return path
    # Replace C:\Users\Name with C:\Users\<redacted>
    return re.sub(r"(C:\\Users\\)[^\\/]+", r"\1<redacted>", str(path), flags=re.IGNORECASE)

def redact_payload(data, options=None):
    """Return a redacted deep copy suitable for HTML or JSON export."""
    options = options or {}
    if not options.get('redact', True):
        return deepcopy(data)

    sensitive_key_tokens = (
        'serial',
        'productkey',
        'product_key',
        'license',
        'key',
        'password',
        'passwd',
        'pwd',
        'token',
        'secret',
        'credential',
        'apikey',
        'api_key',
    )
    path_key_tokens = (
        'path',
        'command',
        'userprofile',
        'temp',
    )

    def redact_value(key, value):
        key_l = str(key).lower()
        if isinstance(value, dict):
            return {k: redact_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact_value(key, item) for item in value]
        if value is None:
            return value
        if 'mac' in key_l:
            return mask_mac(value)
        if any(token in key_l for token in sensitive_key_tokens):
            return mask_string(value)
        if any(token in key_l for token in path_key_tokens):
            return redact_user_paths(value)
        if isinstance(value, str):
            return redact_user_paths(value)
        return value

    return redact_value('', data)


