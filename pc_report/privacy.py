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
    "uniqueid", "identifyingnumber", "keyprotectorid", "guid",
    "uuid", "assettag", "registeredowner", "registereduser", "registeredorganization", "organization",
    "owner", "username", "startname", "logonserver",
    "ssid", "computername", "csname", "hostname", "hardwareid", "processorid", "machineguid", "domainname",
    "machineid", "localadministrators", "accessaccount", "accountname", "interfaceguid",
    "dnssuffix", "dnsdomain", "networkprofile", "netprofilename",
)
# Credentials keep nothing; a serial keeps a four-character tail a support engineer can match.
_FULL_MASK_TOKENS = ("password", "passwd", "pwd", "token", "secret", "credential",
                     "apikey", "productkey", "licensekey", "recoverypassword")
# Account-policy rows from `net accounts` mention "password" but carry numbers, never secrets.
_PASSWORD_POLICY_KEY = re.compile(r"password(?:age|length|history|complexity|expir)|passwordsmustmeet")
# Only these keys may hold a well-known account name that survives masking.
_ACCOUNT_KEY_TOKENS = ("startname", "accountname", "accessaccount", "owner", "username",
                       "localadministrators", "member", "runas")
IP_TOKENS = ("ipv4", "ipv6", "ipaddress", "gateway", "dnsserver", "dhcpserver",
             "remoteaddress", "localaddress", "serveraddress", "winsserver", "nexthop")
MAC_TOKENS = ("macaddress", "permanentaddress", "physicaladdress")
HOST_TOKENS = (
    "proxyserver", "proxyoverride", "proxybypass", "bypasslist",
    "autoconfigurl", "userproxy", "winhttpproxy",
    "remotepath", "serveraddress",
)
SENSITIVE_ENV_NAMES = {"USERNAME", "USERDOMAIN", "USERDNSDOMAIN", "LOGONSERVER", "COMPUTERNAME",
                       "USERDOMAIN_ROAMINGPROFILE", "CLIENTNAME", "IGCCSVC_DB",
                       "__CURSOR_SANDBOX_ENV_RESTORE", "CURSOR_CONVERSATION_ID",
                       "CHROME_CRASHPAD_PIPE_NAME", "VSCODE_IPC_HOOK"}
WELL_KNOWN_ACCOUNTS = frozenset({
    "everyone",
    "authenticated users",
    r"builtin\administrators",
    "localsystem",
    r"nt authority\system",
    r"nt authority\localservice",
    r"nt authority\networkservice",
    r"nt authority\local service",
    r"nt authority\network service",
})

_IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}(?![\d.])")
_IPV6 = re.compile(r"\b([0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{0,4}:)+[0-9a-fA-F]{1,4}\b|\b([0-9a-fA-F]{1,4})::[0-9a-fA-F:]+")
_MAC = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})(?:[:-][0-9A-Fa-f]{2}){3}(?![0-9A-Fa-f])")
_WIRELESS_LINE = re.compile(r"(?im)^(\s*(?:BSSID|SSID|GUID|Profile)\s*:\s*).*$")
_PROXY_TEXT_LINE = re.compile(r"(?im)^(\s*(?:Proxy Server\(s\)|AutoConfigURL)\s*:\s*).*$")
_UNC_PATH = re.compile(r"^(\\\\)([^\\]+)(\\.*)?$")
_UNC_HOST_PREFIX = re.compile(r"(\\\\)([^\\\s]+)(\\)")
_GUID_FULL = re.compile(
    r"\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?"
)
_ACCOUNT_SID = re.compile(r"(?<![A-Za-z0-9])(S-1-(?:5-21|12-1)-)(?:\d+-){3}\d+\b", re.IGNORECASE)
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


def _mask_command_secrets(value: str) -> str:
    """Mask every credential option's value, scanning inside the values we keep.

    A harmless space-separated option would otherwise swallow the token after it, hiding a real
    secret: ``setup.exe /S --token:abc`` reads as option ``S`` with value ``--token:abc``.
    """
    out: list[str] = []
    position = 0
    while (match := _COMMAND_SECRET_ARG.search(value, position)) is not None:
        if _command_option_is_sensitive(match.group(2)):
            out.append(value[position:match.start()])
            out.append(_mask_command_secret_arg(match))
            position = match.end()
        else:
            out.append(value[position:match.start(4)])
            position = match.start(4)
    out.append(value[position:])
    return "".join(out)


_PIPE_NAME = re.compile(r"(\\\\\.\\pipe\\)[^\s\"<>]+", re.IGNORECASE)
_PORTABLE_INSTANCE_PREFIXES = (
    "USB\\", "USBSTOR\\", "SCSI\\", "SWD\\WPDBUSENUM\\",
    "BTHENUM\\", "BTHLE\\", "DISPLAY\\", "PCI\\",
)
_GENERIC_INSTANCE_SEGMENT = re.compile(r"^\d+&[0-9A-F]+&0&", re.IGNORECASE)
# DirectShow / symbolic-link form: \\?\usb#vid_x&pid_y#<instance>#{guid}
_DIRECTSHOW_INSTANCE = re.compile(r"(#)([^#\\/]+)(#\{)")
_BTH_MAC_OR_GUID = re.compile(
    r"\{[^{}]*\}|(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])|"
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{12}(?![0-9A-Fa-f])"
)
_PERSONAL_DEVICE_NAME = re.compile(r"(?:\b(?:iphone|galaxy)\b|\b[\w.-]+(?:'|\u2019)s\b)", re.IGNORECASE)
_PERSONAL_NAME_KEYS = {
    "description", "name", "friendlyname", "devicename",
    "instancename", "productname", "caption",
    # Summary fields that republish a device name the source row already masks.
    "defaultplayback", "defaultcapture", "cameras", "detail",
    # Volume labels: phones and removable media are routinely named after their owner.
    "label", "volumename", "filesystemlabel",
}
_POSSESSIVE_OWNER = re.compile(
    r"(^|[(,:;-]\s*)(?:[a-z0-9.-]+(?:\s+[a-z0-9.-]+){0,2})((?:'|\u2019)s\b)",
    re.IGNORECASE,
)
_PERSONAL_DEVICE_OWNER = re.compile(
    r"^(?:[a-z0-9.-]+(?:\s+[a-z0-9.-]+){0,2})\s+(?=(?:iphone|ipad|galaxy)\b)",
    re.IGNORECASE,
)
_CANONICAL_BLUETOOTH_NETWORK_NAME = re.compile(
    r"^Bluetooth Network Connection(?: \d+)?$",
    re.IGNORECASE,
)
_WELL_KNOWN_NETWORK_PROFILE = re.compile(
    r"^(?:unidentified network|identifying\.\.\.|network(?: \d+)?|"
    r"public network|private network)(?: \([^)]*\))?$",
    re.IGNORECASE,
)
_FREE_TEXT_KEYS = frozenset({"notes", "note", "error", "message", "comment"})
# Anything that can carry a whole command line, whatever the section labels it.
_COMMAND_KEYS = frozenset({"command", "commandline", "action", "uninstall", "uninstallstring",
                           "quietuninstallstring", "modifypath", "imagepath", "arguments"})
# Keys whose value is a device instance path, symbolic link or container identifier.
_DEVICE_ID_KEYS = frozenset({"instanceid", "parentinstanceid", "deviceid", "deviceinstance",
                             "pnpdeviceid", "instancename", "devicepath", "symboliclink",
                             "containerid", "parent", "locationpaths"})
_NETWORK_LOCATION_KEYS = frozenset({"portname", "sharename", "servername", "location",
                                    "printername", "defaultprinter", "offline"})
# Windows' "this device has no container" placeholder; it identifies nothing.
_NULL_CONTAINER_GUID = "{00000000-0000-0000-ffff-ffffffffffff}"
_EMAIL_ADDRESS = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_URL_AUTHORITY = re.compile(
    r"(?P<scheme>\b[A-Za-z][A-Za-z0-9+.-]*://)(?P<userinfo>[^/\s@\"']+@)?"
    r"(?P<host>\[[0-9A-Fa-f:.]+\]|[^/\s:?#\"']+)(?P<port>:\d+)?",
)
# A bare dotted token is only a host name when it is not part of a path or a file name and its
# last label is a real TLD: precision matters more than coverage here, because this runs over
# command lines, notes and environment values full of file names and dotted .NET identifiers.
_BARE_FQDN = re.compile(
    r"(?<![\w.\\/:@-])"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
    r"(?![\w-])"
)
_HOST_TLDS = frozenset({
    "com", "net", "org", "edu", "gov", "mil", "int", "io", "co", "uk", "nl", "de", "fr", "be",
    "cn", "jp", "local", "lan", "corp", "internal", "home", "intranet", "arpa", "example",
})
_FILE_EXTENSIONS = frozenset({"exe", "dll", "sys", "py", "json", "xml", "txt", "log", "ini"})
_LOCAL_DEVICE_HOSTS = frozenset({".", "?"})
# A UNC server quoted without a share, as Windows error text does: "connect to \\SERVER failed".
_UNC_HOST_ONLY = re.compile(r"(\\\\)([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)(?![\\\w.*-])")
_HOST_URL = re.compile(r"^(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<host>\[[^\]]+\]|[^/:]+)(?P<rest>.*)$", re.IGNORECASE)
_HOST_ASSIGNMENT = re.compile(r"^(?P<prefix>[a-z][a-z0-9+.-]*=)(?P<rest>.+)$", re.IGNORECASE)
_HOST_PORT = re.compile(r"^(?P<host>.+?)(?P<port>:\d+)?$")
_HOST_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")
_WELL_KNOWN_HOSTS = frozenset({"<local>", "direct", "*", "localhost", "127.0.0.1"})
_PROXY_PROSE = frozenset({
    "access", "bypass", "disabled", "enabled", "list", "no", "proxy", "server",
})


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
    if keep <= 0 or len(s) < 2 * (keep + 2):
        return "*" * len(s)
    return s[:2] + "*" * max(1, len(s) - keep - 2) + s[-keep:]


def _mask_embedded_mac_tokens(value: str) -> str:
    """Mask MAC-shaped runs inside a device ID, leaving whole GUIDs for the GUID rule."""
    return _BTH_MAC_OR_GUID.sub(
        lambda match: (
            match.group(0)
            if match.group(0).startswith("{")
            else mask_mac(match.group(0))
            if ":" in match.group(0) or "-" in match.group(0)
            else f"{match.group(0)[:6]}******"
        ),
        value,
    )


def redact_instance_id(value):
    """Mask a portable device ID's trailing serial/instance segment."""
    if not isinstance(value, str):
        return value
    value = _MAC.sub(lambda match: mask_mac(match.group(0)), value)
    upper = value.upper()
    if upper.startswith("BTH"):
        return _mask_embedded_mac_tokens(value)
    # Radios, modems and docks publish the adapter MAC inside IDs whose prefix says nothing
    # about Bluetooth, e.g. SWD\RADIO\BLUETOOTH_<mac>, so the MAC rule cannot be prefix-gated.
    value = _mask_embedded_mac_tokens(value)
    if value.startswith(("\\\\?\\", "\\\\.\\")):
        value = _DIRECTSHOW_INSTANCE.sub(
            lambda match: match.group(1) + mask_string(match.group(2)) + match.group(3), value
        )
    value = _GUID_FULL.sub(lambda match: mask_string(match.group(0)), value)
    if not upper.startswith(_PORTABLE_INSTANCE_PREFIXES) or "\\" not in value:
        return value
    stem, segment = value.rsplit("\\", 1)
    if not segment or _GENERIC_INSTANCE_SEGMENT.match(segment):
        return value
    return f"{stem}\\{mask_string(segment)}"


def _redact_personal_device_name(value: str) -> str:
    if value.startswith("***"):
        return value
    if _POSSESSIVE_OWNER.search(value):
        return _POSSESSIVE_OWNER.sub(r"\1***\2", value)
    if _PERSONAL_DEVICE_OWNER.search(value):
        return _PERSONAL_DEVICE_OWNER.sub("*** ", value)
    if _PERSONAL_DEVICE_NAME.search(value):
        return mask_string(value)
    return value


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
    """Keep the vendor OUI and hide the device half, whatever separators the source used."""
    if not mac or mac == REQUIRES_ADMIN:
        return mac
    if isinstance(mac, list):
        return [mask_mac(m) for m in mac]
    raw = re.sub(r"[^0-9A-Fa-f]", "", str(mac))
    if len(raw) == 12:
        return ":".join(raw[i:i + 2] for i in range(0, 6, 2)) + ":**:**:**"
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


def _mask_host_name(host: str) -> str:
    if host.casefold() in _WELL_KNOWN_HOSTS:
        return host
    masked_ip = mask_ip(host)
    if masked_ip != host:
        return masked_ip
    wildcard = host.startswith("*.")
    name = host[2:] if wildcard else host
    parts = name.split(".")
    masked = f"***.{parts[-1]}" if len(parts) > 1 else "***"
    return f"*.{masked}" if wildcard else masked


def _mask_host_token(token: str) -> str:
    leading_match = re.match(r'^[("\']*', token)
    trailing_match = re.search(r'[)"\']*$', token)
    leading = leading_match.group(0) if leading_match else ""
    trailing = trailing_match.group(0) if trailing_match else ""
    core = token[len(leading):len(token) - len(trailing) if trailing else None]
    if not core or core.casefold() in _WELL_KNOWN_HOSTS:
        return token

    url = _HOST_URL.match(core)
    if url:
        return (
            leading + url.group("scheme") + _mask_host_name(url.group("host"))
            + url.group("rest") + trailing
        )

    assignment = _HOST_ASSIGNMENT.match(core)
    prefix = assignment.group("prefix") if assignment else ""
    entry = assignment.group("rest") if assignment else core
    match = _HOST_PORT.match(entry)
    if not match:
        return token
    host, port = match.group("host"), match.group("port") or ""
    plain_host = host[2:] if host.startswith("*.") else host
    if (
        host.casefold() in _WELL_KNOWN_HOSTS
        or host.casefold().rstrip(":") in _PROXY_PROSE
        or not (_HOST_TOKEN.fullmatch(plain_host) or "." in plain_host)
    ):
        return token
    return leading + prefix + _mask_host_name(host) + port + trailing


def mask_hosts(value) -> str:
    """Mask proxy/PAC host names while preserving schemes, ports, and separators."""
    if not isinstance(value, str):
        return value
    return "".join(
        part if re.fullmatch(r"[;,\s]+", part) else _mask_host_token(part)
        for part in re.split(r"([;,\s]+)", value)
    )


def _host_is_already_masked(host: str) -> bool:
    return not host or "*" in host or "<" in host or host in _LOCAL_DEVICE_HOSTS


def _mask_url_authority(match: re.Match[str]) -> str:
    host = match.group("host")
    masked = host if _host_is_already_masked(host) else _mask_host_name(host)
    return match.group("scheme") + ("***@" if match.group("userinfo") else "") + masked + (match.group("port") or "")


def _mask_unc_prefix(match: re.Match[str]) -> str:
    host = match.group(2)
    if _host_is_already_masked(host):
        return match.group(0)
    return f"{match.group(1)}{_mask_host_name(host)}{match.group(3)}"


def _mask_unc_host_only(match: re.Match[str]) -> str:
    host = match.group(2)
    if _host_is_already_masked(host):
        return match.group(0)
    return match.group(1) + _mask_host_name(host)


def _mask_bare_fqdn(match: re.Match[str]) -> str:
    host = match.group(0)
    labels = host.split(".")
    tld = labels[-1].casefold()
    if len(labels) < 2 or tld in _FILE_EXTENSIONS or tld not in _HOST_TLDS:
        return host
    return _mask_host_name(host)


def mask_value_locations(value):
    """Mask e-mail addresses, URL/UNC hosts, IP addresses and bare FQDNs inside free-form text.

    Written for values whose key says nothing about their content -- command lines, environment
    values, notes and adapter properties -- so it must leave file names, version numbers and
    dotted identifiers alone. Schemes, ports, paths and option names survive.
    """
    if isinstance(value, list):
        return [mask_value_locations(item) for item in value]
    if isinstance(value, dict):
        return {key: mask_value_locations(item) for key, item in value.items()}
    if not isinstance(value, str) or not value:
        return value
    value = _EMAIL_ADDRESS.sub("***@***.example", value)
    value = _URL_AUTHORITY.sub(_mask_url_authority, value)
    value = _UNC_HOST_PREFIX.sub(_mask_unc_prefix, value)
    value = _UNC_HOST_ONLY.sub(_mask_unc_host_only, value)
    return _BARE_FQDN.sub(_mask_bare_fqdn, _mask_free_text_ips(value))


# Free text only: an IPv4 must stand alone (not glued to letters, '-' or '_' as in
# "jdk-17.0.16.8-hotspot") and every octet must fit a byte ("10.0.19045.1" is a build number).
_FREE_TEXT_IPV4 = re.compile(r"(?<![\w.\-])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\w.\-])")


def _mask_free_text_ipv4(match: re.Match[str]) -> str:
    if any(int(octet) > 255 for octet in match.groups()):
        return match.group(0)
    return _mask_v4(match)


def _mask_free_text_ips(value: str) -> str:
    return _IPV6.sub(_mask_v6, _FREE_TEXT_IPV4.sub(_mask_free_text_ipv4, value))


def redact_free_text(value):
    """Notes, messages and partial-section errors: raw Windows text with no key to go on."""
    if not isinstance(value, str):
        return value
    return mask_value_locations(redact_network_locations(redact_user_paths(value)))


def redact_proxy_hosts(value):
    """Backward-compatible proxy host redaction helper."""
    if isinstance(value, list):
        return [redact_proxy_hosts(item) for item in value]
    return mask_hosts(value)


def redact_text(text: str) -> str:
    """Mask network identifiers in raw command-output fixtures."""
    value = str(text or "")
    value = _WIRELESS_LINE.sub(r"\1<redacted>", value)
    value = _PROXY_TEXT_LINE.sub(r"\1<redacted>", value)
    macs = []

    def stash_mac(match):
        macs.append(f"{match.group(1)}:{match.group(2)}:{match.group(3)}:**:**:**")
        return f"<masked-mac-{len(macs) - 1}>"

    value = _MAC.sub(stash_mac, value)
    value = mask_ip(value)
    for index, mac in enumerate(macs):
        value = value.replace(f"<masked-mac-{index}>", mac)
    return value


def redact_unc_host(value):
    if not isinstance(value, str):
        return value
    match = _UNC_PATH.match(value)
    if not match:
        return mask_ip(value)
    host = match.group(2)
    masked_host = mask_ip(host)
    if masked_host == host:
        masked_host = "<redacted>"
    return f"{match.group(1)}{masked_host}{match.group(3) or ''}"


def redact_network_locations(value):
    """Mask IP addresses and UNC hosts in printer/network text fields."""
    if isinstance(value, list):
        return [redact_network_locations(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_network_locations(item) for key, item in value.items()}
    if not isinstance(value, str):
        return mask_ip(value)

    def replace_unc(match):
        host = match.group(2)
        masked_host = mask_ip(host)
        if masked_host == host:
            masked_host = "<redacted>"
        return f"{match.group(1)}{masked_host}{match.group(3)}"

    value = _GUID_FULL.sub(lambda match: mask_string(match.group(0)), value)
    return mask_ip(_UNC_HOST_PREFIX.sub(replace_unc, value))


def redact_user_paths(path):
    if not path:
        return path
    return re.sub(
        r"((?:[A-Z]:)?[\\/#]Users[\\/#])[^\\/#;\"']+",
        r"\1<redacted>",
        str(path),
        flags=re.IGNORECASE,
    )


def redact_command_line(command):
    if not command:
        return command
    value = _mask_command_secrets(redact_user_paths(command))
    value = _PIPE_NAME.sub(r"\1<redacted>", value)
    return mask_value_locations(value)


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


# Keys that contain a sensitive token by accident of spelling but describe nothing identifying.
_NOT_SENSITIVE_KEYS = {"processoridentifier", "processorarchitecture", "processorlevel", "processorrevision"}
# Values the identity scrub already replaced; masking them again only hides the placeholder.
_PLACEHOLDER_PARTS = {"pc-name", "user", "workgroup", "example.local", "logon-srv"}


def _is_placeholder_value(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parts = [p for p in re.split(r"[\\@]", value) if p]
    # Only the DOMAIN\user / user@domain forms: fixtures use bare "PC-NAME" as a stand-in name.
    return len(parts) >= 2 and all(p.casefold() in _PLACEHOLDER_PARTS for p in parts)


def _name_is_sensitive(name: str) -> bool:
    if norm_key(name) in _NOT_SENSITIVE_KEYS:
        return False
    return name.upper() in SENSITIVE_ENV_NAMES or any(t in norm_key(name) for t in SENSITIVE_TOKENS)


def _keep_for_key(key_l: str) -> int:
    return 0 if any(token in key_l for token in _FULL_MASK_TOKENS) else 4


def redact_meta(meta, options=None) -> dict:
    """Mask the machine name in the report meta; used by both renderers so they cannot drift.

    The machine name is masked completely: whoever reads the report already knows which machine
    it came from, and the surviving tail of a long name is often the asset tag.
    """
    meta = dict(meta or {})
    options = options or {}
    machine = meta.get("machine") or ""
    if options.get("redact", True) and machine:
        meta["machine"] = mask_string(machine, keep=0)
    return meta


def _mask_device_identifier(value):
    if isinstance(value, str) and _GUID_FULL.fullmatch(value):
        return value if value.casefold() == _NULL_CONTAINER_GUID else mask_string(value)
    return redact_instance_id(value)


def redact_value(key, value):
    """Redact one value by what its normalised key says the value is."""
    if isinstance(value, (set, frozenset, tuple)):
        value = sorted(value, key=str)
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
                out[name_key] = _redact_personal_device_name(out[name_key])
        # Name/Value rows (environment variables, registry dumps): the name says what is sensitive,
        # and when it says nothing the value itself is still inspected for hosts and addresses.
        if isinstance(out.get("Name"), str) and "Value" in out:
            if _name_is_sensitive(out["Name"]):
                out["Value"] = mask_string(out["Value"], _keep_for_key(norm_key(out["Name"])))
            elif isinstance(out["Value"], str):
                out["Value"] = mask_value_locations(redact_user_paths(out["Value"]))
        return out
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if value is None or value == REQUIRES_ADMIN or isinstance(value, (bool, int, float)):
        return value
    key_l = norm_key(key)
    if key_l in _FREE_TEXT_KEYS:
        return redact_free_text(value)
    if key_l in _DEVICE_ID_KEYS:
        return _mask_device_identifier(value)
    if key_l == "mac" or any(t in key_l for t in MAC_TOKENS):
        return mask_mac(value)
    if (
        key_l in {"providername", "networkpathhostname", "networkpath"}
        or key_l.startswith("remotepath")
    ):
        return redact_unc_host(value)
    if key_l in _NETWORK_LOCATION_KEYS:
        return mask_value_locations(redact_network_locations(value))
    if any(token in key_l for token in HOST_TOKENS):
        return mask_hosts(value)
    if any(t in key_l for t in IP_TOKENS):
        return mask_ip(value)
    if any(t in key_l for t in SENSITIVE_TOKENS) and key_l not in _NOT_SENSITIVE_KEYS:
        if _is_placeholder_value(value):
            return value
        if (
            key_l in {"networkprofile", "netprofilename"}
            and isinstance(value, str)
            and _WELL_KNOWN_NETWORK_PROFILE.fullmatch(" ".join(value.split()))
        ):
            return value
        if any(token in key_l for token in _ACCOUNT_KEY_TOKENS) and _is_well_known_account(value):
            return value
        if _PASSWORD_POLICY_KEY.search(key_l):
            # "Minimum password length", "Maximum password age (days)": policy numbers, not secrets.
            return value
        return mask_string(value, _keep_for_key(key_l))
    if isinstance(value, str):
        if key_l == "name":
            value = _GUID_FULL.sub(lambda match: mask_string(match.group(0)), value)
        if key_l in _PERSONAL_NAME_KEYS:
            value = _redact_personal_device_name(value)
        return redact_command_line(value) if key_l in _COMMAND_KEYS else redact_user_paths(value)
    return value


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

    return redact_value("", scrub_identities(data))
