"""Network Information: identity, per-interface IP configuration, DHCP/DNS, routes, proxies and Wi-Fi."""
from __future__ import annotations

import re

from .. import decode
from ..format import fmt_datetime, yes_no
from ..ps import cim
from ..section import Section, as_list, first_dict, kv_groups, list_table, rows_of, sub_heading

CS_SCRIPT = cim(
    "Win32_ComputerSystem",
    ("Name", "Domain", "PartOfDomain", "DomainRole", "Workgroup", "DNSHostName", "Description"),
)
IPC_SCRIPT = r"""
Get-NetIPConfiguration -Detailed -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ InterfaceAlias = $_.InterfaceAlias; InterfaceIndex = $_.InterfaceIndex; InterfaceDescription = $_.InterfaceDescription
    Status = [string]$_.NetAdapter.Status; MacAddress = [string]$_.NetAdapter.MacAddress; LinkSpeed = [string]$_.NetAdapter.LinkSpeed
    IPv4Address = @($_.IPv4Address | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" })
    IPv6Address = @($_.IPv6Address | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" })
    IPv4DefaultGateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
    IPv6DefaultGateway = @($_.IPv6DefaultGateway | ForEach-Object { $_.NextHop })
    DNSServer = @($_.DNSServer | ForEach-Object { $_.ServerAddresses } | ForEach-Object { $_ })
    NetProfileName = [string]$_.NetProfile.Name; NetProfileCategory = [string]$_.NetProfile.NetworkCategory
    IPv4Connectivity = [string]$_.NetProfile.IPv4Connectivity; IPv6Connectivity = [string]$_.NetProfile.IPv6Connectivity }
}
"""
WMI_SCRIPT = cim(
    "Win32_NetworkAdapterConfiguration",
    (
        "InterfaceIndex",
        "Description",
        "DHCPEnabled",
        "DHCPServer",
        "DHCPLeaseObtained",
        "DHCPLeaseExpires",
        "DNSDomain",
        "DNSDomainSuffixSearchOrder",
        "WINSPrimaryServer",
        "WINSSecondaryServer",
        "TcpipNetbiosOptions",
        "IPConnectionMetric",
        "MTU",
        "IPEnabled",
    ),
    where="IPEnabled=TRUE",
)
ROUTES_SCRIPT = (
    "Get-NetRoute -DestinationPrefix '0.0.0.0/0','::/0' -ErrorAction SilentlyContinue | "
    "Select-Object InterfaceAlias,DestinationPrefix,NextHop,RouteMetric,InterfaceMetric,AddressFamily"
)
PROXY_SCRIPT = (
    "Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' "
    "-ErrorAction SilentlyContinue | Select-Object ProxyEnable,ProxyServer,ProxyOverride,AutoConfigURL"
)
WINHTTP_ARGS = ["netsh", "winhttp", "show", "proxy"]
WLAN_ARGS = ["netsh", "wlan", "show", "interfaces"]

ROUTE_COLUMNS = [
    ("Interface", "Interface"),
    ("Destination", "Destination"),
    ("Next Hop", "Next Hop"),
    ("Route Metric", "Route Metric"),
    ("Interface Metric", "Interface Metric"),
    ("Family", "Family"),
]
WLAN_KEYS = {
    "name": "Interface",
    "description": "Adapter",
    "state": "State",
    "ssid": "SSID",
    "bssid": "BSSID",
    "radio type": "Radio Type",
    "authentication": "Authentication",
    "cipher": "Cipher",
    "channel": "Channel",
    "band": "Band",
    "receive rate (mbps)": "Receive Rate (Mbps)",
    "transmit rate (mbps)": "Transmit Rate (Mbps)",
    "signal": "Signal",
}
_KV_LINE = re.compile(r"^\s*([^:]+?)\s*:\s*(.*?)\s*$")


def parse_kv_text(text: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        match = _KV_LINE.match(line)
        if not match:
            continue
        key = " ".join(match.group(1).split()).casefold()
        value = match.group(2).strip()
        if key and key not in out:
            out[key] = value
    return out


def winhttp_summary(text: str) -> str:
    value = text or ""
    if re.search(r"\bDirect\s+access\b", value, re.IGNORECASE):
        return "Direct access (no proxy server)"
    match = re.search(r"Proxy\s+Server\(s\)\s*:\s*(.+)", value, re.IGNORECASE)
    if match:
        bypass = re.search(r"Bypass\s+List\s*:\s*(.+)", value, re.IGNORECASE)
        return match.group(1).strip() + (
            f" (bypass: {bypass.group(1).strip()})" if bypass else ""
        )
    return "Not available"


def _flatten_ip_addresses(value) -> list:
    out = []
    for item in as_list(value):
        if isinstance(item, dict):
            address = item.get("IPAddress")
            if address in (None, ""):
                continue
            prefix = item.get("PrefixLength")
            out.append(str(address) if prefix in (None, "") else f"{address}/{prefix}")
        elif item not in (None, ""):
            out.append(item)
    return out


def _flatten_nested(value, field: str) -> list:
    out = []
    for item in as_list(value):
        if isinstance(item, dict):
            out.extend(_flatten_nested(item.get(field), field))
        elif item not in (None, ""):
            out.append(item)
    return out


def _wifi_rows(text: str) -> dict:
    parsed = parse_kv_text(text)
    wifi = {label: parsed[key] for key, label in WLAN_KEYS.items() if key in parsed}
    if wifi:
        return wifi
    if "no wireless interface" in (text or "").casefold():
        return {"Wi-Fi": "No wireless interface"}
    return {"Wi-Fi": "Not available"}


def build(cs, ipc, wmi, routes, proxy, winhttp_text, wlan_text) -> dict:
    cs, proxy = cs or {}, proxy or {}
    identity = {
        "Computer Name": cs.get("Name", ""),
        "DNS Host Name": cs.get("DNSHostName", ""),
        "Description": cs.get("Description") or "",
        "Domain Name": cs.get("Domain", "") if cs.get("PartOfDomain") else "",
        "Workgroup": cs.get("Workgroup")
        or ("" if cs.get("PartOfDomain") else cs.get("Domain", "")),
        "Part of Domain": yes_no(cs.get("PartOfDomain")),
        "Role": decode.lookup(decode.DOMAIN_ROLES, cs.get("DomainRole")),
    }
    wmi_by = {}
    for row in rows_of(wmi):
        index = decode.to_int(row.get("InterfaceIndex"))
        if index is not None:
            wmi_by[index] = row

    interfaces = []
    for row in rows_of(ipc):
        index = decode.to_int(row.get("InterfaceIndex"))
        config = wmi_by.get(index, {}) if index is not None else {}
        profile_name = row.get("NetProfileName", "")
        link = {
            "Description": row.get("InterfaceDescription", ""),
            "Interface Index": row.get("InterfaceIndex", ""),
            "Status": row.get("Status", ""),
            "MAC Address": row.get("MacAddress", ""),
            "Link Speed": row.get("LinkSpeed", ""),
            "Network Profile": (
                f"{profile_name} ({row.get('NetProfileCategory', '')})" if profile_name else ""
            ),
            "IPv4 Connectivity": row.get("IPv4Connectivity", ""),
            "IPv6 Connectivity": row.get("IPv6Connectivity", ""),
        }
        addressing = {
            "IPv4 Address": _flatten_ip_addresses(row.get("IPv4Address")),
            "IPv6 Address": _flatten_ip_addresses(row.get("IPv6Address")),
            "Default Gateway": (
                _flatten_nested(row.get("IPv4DefaultGateway"), "NextHop")
                + _flatten_nested(row.get("IPv6DefaultGateway"), "NextHop")
            ),
            "DNS Servers": _flatten_nested(row.get("DNSServer"), "ServerAddresses"),
            "DNS Suffix": config.get("DNSDomain") or "",
            "DNS Suffix Search Order": as_list(config.get("DNSDomainSuffixSearchOrder")),
            "Interface Metric": config.get("IPConnectionMetric", ""),
        }
        dhcp = {
            "DHCP Enabled": yes_no(config.get("DHCPEnabled")) if config else "",
            "DHCP Server": config.get("DHCPServer") or "",
            "Lease Obtained": (
                fmt_datetime(config.get("DHCPLeaseObtained"))
                if config.get("DHCPLeaseObtained")
                else ""
            ),
            "Lease Expires": (
                fmt_datetime(config.get("DHCPLeaseExpires"))
                if config.get("DHCPLeaseExpires")
                else ""
            ),
            "WINS Servers": [
                server
                for server in (
                    config.get("WINSPrimaryServer"),
                    config.get("WINSSecondaryServer"),
                )
                if server
            ],
            "NetBIOS over TCP/IP": (
                decode.lookup(decode.NETBIOS_OPTIONS, config.get("TcpipNetbiosOptions"))
                if config
                else ""
            ),
        }
        interfaces.append(
            {
                "name": row.get("InterfaceAlias", ""),
                "groups": [
                    {"title": "Link", "rows": link},
                    {"title": "Addressing", "rows": addressing},
                    {"title": "DHCP and Name Resolution", "rows": dhcp},
                ],
            }
        )
    interfaces.sort(
        key=lambda item: (
            str(item["groups"][0]["rows"]["Status"]).casefold() != "up",
            str(item["name"]).casefold(),
        )
    )

    proxies = {
        "User Proxy": (
            "Enabled: " + str(proxy.get("ProxyServer") or "")
            if decode.to_int(proxy.get("ProxyEnable"))
            else "Disabled"
        ),
        "Proxy Bypass": proxy.get("ProxyOverride") or "",
        "Auto-config URL": proxy.get("AutoConfigURL") or "",
        "WinHTTP Proxy": winhttp_summary(winhttp_text),
    }
    route_rows = [
        {
            "Interface": row.get("InterfaceAlias", ""),
            "Destination": row.get("DestinationPrefix", ""),
            "Next Hop": row.get("NextHop", ""),
            "Route Metric": row.get("RouteMetric", ""),
            "Interface Metric": row.get("InterfaceMetric", ""),
            "Family": "IPv6" if decode.to_int(row.get("AddressFamily")) == 23 else "IPv4",
        }
        for row in rows_of(routes)
    ]
    route_rows.sort(
        key=lambda row: (
            str(row["Interface"]).casefold(),
            str(row["Family"]),
            str(row["Destination"]),
        )
    )
    return {
        "groups": [
            {"title": "Identity", "rows": identity},
            {"title": "Proxy", "rows": proxies},
            {"title": "Wi-Fi", "rows": _wifi_rows(wlan_text)},
        ],
        "interfaces": interfaces,
        "routes": route_rows,
    }


def collect(ctx):
    winhttp_text = ctx.text("winhttp_proxy", WINHTTP_ARGS)
    wlan_text = ctx.text("wlan", WLAN_ARGS)
    if winhttp_summary(winhttp_text) == "Not available":
        ctx.note("winhttp_proxy: output format not recognised")
    if dict(_wifi_rows(wlan_text)).get("Wi-Fi") == "Not available":
        ctx.note("wlan: output format not recognised")
    return build(
        first_dict(ctx.query("computer", CS_SCRIPT)),
        ctx.query("ip_configuration", IPC_SCRIPT, timeout=45),
        ctx.query("wmi_configuration", WMI_SCRIPT),
        ctx.query("routes", ROUTES_SCRIPT),
        first_dict(ctx.query("proxy", PROXY_SCRIPT)),
        winhttp_text,
        wlan_text,
    )


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    interfaces = rows_of(data.get("interfaces"))
    if not interfaces:
        out.append(sub_heading("Interfaces") + list_table([("Name", "Name")], []))
    for interface in interfaces:
        out.append(
            sub_heading(interface.get("name", "")) + kv_groups(interface.get("groups"))
        )
    out.append(
        sub_heading("Default routes") + list_table(ROUTE_COLUMNS, data.get("routes"))
    )
    return "".join(out)


SECTION = Section(
    key="network_information",
    title="Network Information",
    group="Network",
    collect=collect,
    render=render,
    timeout=45,
)
