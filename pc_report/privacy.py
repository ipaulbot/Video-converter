"""Redaction applied to the collected payload before either renderer.

Keys are matched after lowering and stripping non-alphanumerics, so the
human labels sections use ("Serial Number") and raw WMI names
("SerialNumber") hit the same tokens. Section authors must not label a
decoded text field with a token word unless they want it masked.
"""
from __future__ import annotations

import os
import re
from copy import deepcopy

from .section import REQUIRES_ADMIN

_NON_ALNUM = re.compile(r"[^a-z0-9]")

SENSITIVE_TOKENS = (
    "serial", "productkey", "partialproductkey", "productid", "oa3x", "licensekey",
    "password", "passwd", "pwd", "token", "secret", "credential", "apikey",
    "uuid", "assettag", "registeredowner", "registereduser", "registeredorganization", "organization",
    "owner", "username", "startname", "logonserver",
    "ssid", "computername", "csname", "hostname", "hardwareid", "processorid", "machineguid", "domainname",
    "machineid", "localadministrators", "accessaccount", "accountname", "interfaceguid",
)
IP_TOKENS = ("ipv4", "ipv6", "ipaddress", "gateway", "dnsserver", "dhcpserver",
             "remoteaddress", "localaddress", "serveraddress", "winsserver", "nexthop")
MAC_TOKENS = ("macaddress", "permanentaddress", "physicaladdress")
SENSITIVE_ENV_NAMES = {"USERNAME", "USERDOMAIN", "USERDNSDOMAIN", "LOGONSERVER", "COMPUTERNAME",
                       "USERDOMAIN_ROAMINGPROFILE", "CLIENTNAME", "IGCCSVC_DB",
                       "__CURSOR_SANDBOX_ENV_RESTORE", "CURSOR_CONVERSATION_ID",
                       "CHROME_CRASHPAD_PIPE_NAME", "VSCODE_IPC_HOOK"}
WELL_KNOWN_ACCOUNTS = frozenset({
    "localsystem",
    r"nt authority\system",
    r"nt authority\localservice",
    r"nt authority\networkservice",
    r"nt authority\local service",
    r"nt authority\network service",
})

_IPV4 = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}\b")
_IPV6 = re.compile(r"\b([0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{0,4}:)+[0-9a-fA-F]{1,4}\b|\b([0-9a-fA-F]{1,4})::[0-9a-fA-F:]+")
_GUID_FULL = re.compile(
    r"\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?"
)
_ACCOUNT_SID = re.compile(r"\b(S-1-(?:5-21|12-1)-)(?:\d+-){3}\d+\b", re.IGNORECASE)
_COMMAND_SECRET_ARG = re.compile(
    r"((?:--|-(?!-)|/)([A-Za-z0-9_.-]+)(?:=|:(\s*)|\s+))"
    r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|\S+)",
    re.IGNORECASE,
)
_CREDENTIAL_OPTION_SUBSTRINGS = (
    "token", "password", "passwd", "pwd", "secret", "credential",
    "apikey", "api-key", "api_key", "accesskey", "access-key", "access_key",
    "bearer", "sas",
)
_CLI_NON_CREDENTIAL_SUBSTRINGS = (
    "session", "conversation", "uuid", "pipe", "channel", "windowconfig",
)


def _is_credential_option(name: str) -> bool:
    """True when a lower-cased CLI option name (no -/--/ prefix) carries a secret value."""
    lower = name.lower()
    if any(fragment in lower for fragment in _CREDENTIAL_OPTION_SUBSTRINGS):
        return True
    if lower == "key" or lower.endswith("key"):
        return True
    if lower == "auth":
        return True
    if lower.startswith(("auth-", "auth_")):
        return True
    if lower.endswith(("-auth", "_auth")):
        return True
    return False


def _command_option_is_sensitive(name: str) -> bool:
    lower = name.lower()
    if _is_credential_option(lower):
        return True
    compact = _NON_ALNUM.sub("", lower)
    return any(fragment in compact for fragment in _CLI_NON_CREDENTIAL_SUBSTRINGS)


def _mask_command_secret_arg(match: re.Match[str]) -> str:
    if not _command_option_is_sensitive(match.group(2)):
        return match.group(0)
    prefix = match.group(1)
    gap = match.group(3) or ""
    if gap and prefix[-1].isspace():
        gap = ""
    return prefix + gap + "***"
_PIPE_NAME = re.compile(r"(\\\\\.\\pipe\\)[^\s\"<>]+", re.IGNORECASE)
_PORTABLE_INSTANCE_PREFIXES = (
    "USB\\", "USBSTOR\\", "SCSI\\", "SWD\\WPDBUSENUM\\",
    "BTHENUM\\", "BTHLE\\", "DISPLAY\\",
)
_GENERIC_INSTANCE_SEGMENT = re.compile(r"^\d+&[0-9A-F]+&0&", re.IGNORECASE)
_BTH_MAC_OR_GUID = re.compile(
    r"\{[^{}]*\}|(?<![0-9A-Fa-f])[0-9A-Fa-f]{12}(?![0-9A-Fa-f])"
)
_PERSONAL_DEVICE_NAME = re.compile(r"(?:\b(?:iphone|galaxy)\b|\b[\w.-]+(?:'|\u2019)s\b)", re.IGNORECASE)
_CANONICAL_BLUETOOTH_NETWORK_NAME = re.compile(
    r"^Bluetooth Network Connection(?: \d+)?$",
    re.IGNORECASE,
)


def norm_key(key) -> str:
    return _NON_ALNUM.sub("", str(key).lower())


def mask_string(value, keep: int = 4):
    if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [mask_string(v, keep) for v in value]
    if isinstance(value, dict):
        return {k: mask_string(v, keep) for k, v in value.items()}
    s = str(value)
    if len(s) < 2 * (keep + 2):
        return "*" * len(s)
    return s[:2] + "*" * max(1, len(s) - keep - 2) + s[-keep:]


def redact_instance_id(value):
    """Mask a portable device ID's trailing serial/instance segment."""
    if not isinstance(value, str):
        return value
    upper = value.upper()
    if upper.startswith("BTH"):
        return _BTH_MAC_OR_GUID.sub(
            lambda match: (
                match.group(0)
                if match.group(0).startswith("{")
                else f"{match.group(0)[:6]}******"
            ),
            value,
        )
    value = _GUID_FULL.sub(lambda match: mask_string(match.group(0)), value)
    if not upper.startswith(_PORTABLE_INSTANCE_PREFIXES) or "\\" not in value:
        return value
    stem, segment = value.rsplit("\\", 1)
    if not segment or _GENERIC_INSTANCE_SEGMENT.match(segment):
        return value
    return f"{stem}\\{mask_string(segment)}"


def _is_well_known_account(value) -> bool:
    if not isinstance(value, str):
        return False
    account = re.sub(r"\\+", r"\\", value.replace("/", "\\")).casefold()
    return (
        account in WELL_KNOWN_ACCOUNTS
        or account.startswith("nt service\\")
        or account.startswith("nt authority\\")
    )


def mask_mac(mac):
    if not mac or mac == REQUIRES_ADMIN:
        return mac
    if isinstance(mac, list):
        return [mask_mac(m) for m in mac]
    mc = str(mac).replace("-", ":")
    parts = mc.split(":")
    if len(parts) == 6:
        return f"{parts[0]}:{parts[1]}:{parts[2]}:**:**:**"
    return mask_string(mac)


def _mask_v4(match):
    whole = match.group(0)
    if whole == "0.0.0.0" or whole.startswith("127.") or whole.startswith("255."):
        return whole
    return f"{match.group(1)}.{match.group(2)}.*.*"


def _mask_v6(match):
    whole = match.group(0)
    if whole in ("::", "::1"):
        return whole
    head = match.group(1) or match.group(2) or ""
    return f"{head}::*"


def mask_ip(value):
    if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [mask_ip(v) for v in value]
    if isinstance(value, dict):
        return {k: mask_ip(v) for k, v in value.items()}
    s = _IPV4.sub(_mask_v4, str(value))
    return _IPV6.sub(_mask_v6, s)


def redact_user_paths(path):
    if not path:
        return path
    return re.sub(
        r"((?:[A-Z]:)?[\\/]Users[\\/])[^\\/;\"']+",
        r"\1<redacted>",
        str(path),
        flags=re.IGNORECASE,
    )


def redact_command_line(command):
    if not command:
        return command
    value = redact_user_paths(command)
    value = _COMMAND_SECRET_ARG.sub(_mask_command_secret_arg, value)
    return _PIPE_NAME.sub(r"\1<redacted>", value)


def identity_tokens(env=None) -> list[tuple[str, str]]:
    env = os.environ if env is None else env
    computer_name = env.get("COMPUTERNAME") or ""
    values = [
        (computer_name, "PC-NAME"),
        (env.get("USERNAME") or "", "user"),
        (env.get("USERDNSDOMAIN") or "", "example.local"),
    ]
    user_domain = env.get("USERDOMAIN") or ""
    if user_domain and user_domain.upper() not in {computer_name.upper(), "WORKGROUP"}:
        values.append((user_domain, "WORKGROUP"))
    logon = (env.get("LOGONSERVER") or "").strip()
    if logon:
        logon_host = logon.lstrip("\\").split("\\", 1)[0]
        if logon_host and logon_host.upper() not in {computer_name.upper()}:
            values.append((logon_host, "LOGON-SRV"))
    return [(value, replacement) for value, replacement in values if value]


def _name_is_sensitive(name: str) -> bool:
    return name.upper() in SENSITIVE_ENV_NAMES or any(t in norm_key(name) for t in SENSITIVE_TOKENS)


def redact_payload(data, options=None, *, env=None):
    """Return a redacted deep copy suitable for HTML or JSON export."""
    options = options or {}
    if not options.get("redact", True):
        return deepcopy(data)

    replacements = {}
    for value, replacement in identity_tokens(env):
        replacements.setdefault(value.casefold(), replacement)
    scrubber = None
    if replacements:
        alternatives = "|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True))
        scrubber = re.compile(
            r"(?<![A-Za-z0-9_])(?:" + alternatives + r")(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )

    def scrub_identities(value):
        if isinstance(value, dict):
            return {key: scrub_identities(item) for key, item in value.items()}
        if isinstance(value, list):
            return [scrub_identities(item) for item in value]
        if isinstance(value, str):
            if scrubber is not None:
                value = scrubber.sub(lambda match: replacements[match.group(0).casefold()], value)
            return _ACCOUNT_SID.sub(r"\1<redacted>", value)
        return value

    def redact_value(key, value):
        if isinstance(value, dict):
            out = {k: redact_value(k, v) for k, v in value.items()}
            instance_id = next(
                (
                    item for item_key, item in value.items()
                    if norm_key(item_key) in {"instanceid", "deviceid", "pnpdeviceid"}
                    and isinstance(item, str)
                ),
                "",
            )
            if instance_id.upper().startswith("BTH"):
                description = out.get("Description")
                normalized_description = (
                    " ".join(description.split()).casefold()
                    if isinstance(description, str)
                    else None
                )
                for name_key in ("FriendlyName", "Name"):
                    name = out.get(name_key)
                    normalized_name = (
                        " ".join(name.split()).casefold()
                        if isinstance(name, str)
                        else None
                    )
                    if name_key in out and (
                        normalized_description is None
                        or normalized_name != normalized_description
                    ) and not (
                        normalized_name is not None
                        and _CANONICAL_BLUETOOTH_NETWORK_NAME.fullmatch(normalized_name)
                    ):
                        out[name_key] = mask_string(out[name_key])
            for name_key in ("FriendlyName", "Name"):
                if isinstance(out.get(name_key), str) and _PERSONAL_DEVICE_NAME.search(out[name_key]):
                    out[name_key] = mask_string(out[name_key])
            # Name/Value rows (environment variables, registry dumps): the name says what is sensitive.
            if isinstance(out.get("Name"), str) and "Value" in out and _name_is_sensitive(out["Name"]):
                out["Value"] = mask_string(out["Value"])
            return out
        if isinstance(value, list):
            return [redact_value(key, item) for item in value]
        if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
            return value
        key_l = norm_key(key)
        if key_l in {"instanceid", "deviceid", "pnpdeviceid"}:
            if isinstance(value, str) and _GUID_FULL.fullmatch(value):
                return mask_string(value)
            return redact_instance_id(value)
        if any(t in key_l for t in MAC_TOKENS):
            return mask_mac(value)
        if any(t in key_l for t in IP_TOKENS):
            return mask_ip(value)
        if any(t in key_l for t in SENSITIVE_TOKENS):
            if _is_well_known_account(value):
                return value
            return mask_string(value)
        if isinstance(value, str):
            return redact_command_line(value) if key_l == "commandline" else redact_user_paths(value)
        return value

    return redact_value("", scrub_identities(data))
