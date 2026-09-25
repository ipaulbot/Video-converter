"""Network Connections: mapped drives, VPNs, and aggregated TCP/UDP endpoints."""
from __future__ import annotations

from collections import Counter

from .. import decode
from ..format import bytes_human, yes_no
from ..ps import cim
from ..section import Section, as_list, kv_groups, list_table, rows_of, sub_heading

MAPPED_SCRIPT = cim(
    "Win32_MappedLogicalDisk",
    ("Name", "ProviderName", "FileSystem", "Size", "FreeSpace", "VolumeName"),
)
SMB_SCRIPT = (
    "Get-SmbMapping -ErrorAction SilentlyContinue | "
    "Select-Object LocalPath,RemotePath,Status"
)
VPN_SCRIPT = (
    "Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object "
    "Name,ServerAddress,ConnectionStatus,TunnelType,AuthenticationMethod,SplitTunneling"
)
TCP_SCRIPT = (
    "Get-NetTCPConnection -ErrorAction SilentlyContinue | Select-Object "
    "LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess"
)
UDP_SCRIPT = (
    "Get-NetUDPEndpoint -ErrorAction SilentlyContinue | "
    "Select-Object LocalAddress,LocalPort,OwningProcess"
)
PROCS_SCRIPT = "Get-Process -ErrorAction SilentlyContinue | Select-Object Id,ProcessName"

MAPPED_COLUMNS = [
    ("Drive", "Drive"),
    ("Remote Path (host name)", "Remote Path"),
    ("Label", "Label"),
    ("File System", "File System"),
    ("Total", "Total"),
    ("Free", "Free"),
    ("Status", "Status"),
]
VPN_COLUMNS = [
    ("Name", "Name"),
    ("Server (host name)", "Server"),
    ("Status", "Status"),
    ("Tunnel", "Tunnel"),
    ("Authentication", "Authentication"),
    ("Split Tunneling", "Split Tunneling"),
]
LISTENING_COLUMNS = [
    ("Local Address", "Local Address"),
    ("Local Port", "Local Port"),
    ("Process", "Process"),
]
ESTABLISHED_COLUMNS = [
    ("Process", "Process"),
    ("Connections", "Connections"),
    ("Remote Hosts", "Distinct Remote Hosts"),
]
UDP_COLUMNS = [
    ("Local Address", "Local Address"),
    ("Local Port", "Local Port"),
    ("Process", "Process"),
]


def _state(value) -> str:
    return (
        decode.lookup(decode.TCP_STATE, value)
        if decode.to_int(value) is not None
        else str(value or "")
    )


def _sort_number(value):
    number = decode.to_int(value)
    return (number is None, number or 0, str(value or ""))


def build(mapped, smb, vpn, tcp, udp, procs) -> dict:
    names = {
        pid: row.get("ProcessName", "")
        for row in rows_of(procs)
        if (pid := decode.to_int(row.get("Id"))) is not None
    }
    smb_by = {
        str(row.get("LocalPath") or "").upper(): row for row in rows_of(smb)
    }

    def process(pid):
        number = decode.to_int(pid)
        if number is None:
            return ""
        return f"{names.get(number) or 'unknown'} ({number})"

    mapped_rows = []
    seen_drives = set()
    for row in rows_of(mapped):
        drive = str(row.get("Name") or "").upper()
        seen_drives.add(drive)
        mapping = smb_by.get(drive, {})
        mapped_rows.append(
            {
                "Drive": drive,
                "Remote Path (host name)": row.get("ProviderName")
                or mapping.get("RemotePath", ""),
                "Label": row.get("VolumeName") or "",
                "File System": row.get("FileSystem") or "",
                "Total": (
                    bytes_human(row.get("Size"))
                    if row.get("Size") not in (None, "")
                    else ""
                ),
                "Free": (
                    bytes_human(row.get("FreeSpace"))
                    if row.get("FreeSpace") not in (None, "")
                    else ""
                ),
                "Status": mapping.get("Status", ""),
            }
        )
    for drive, mapping in smb_by.items():
        if drive not in seen_drives:
            mapped_rows.append(
                {
                    "Drive": drive,
                    "Remote Path (host name)": mapping.get("RemotePath", ""),
                    "Label": "",
                    "File System": "",
                    "Total": "",
                    "Free": "",
                    "Status": mapping.get("Status", ""),
                }
            )
    mapped_rows.sort(key=lambda row: str(row["Drive"]).casefold())

    vpn_rows = [
        {
            "Name": row.get("Name", ""),
            "Server (host name)": row.get("ServerAddress", ""),
            "Status": row.get("ConnectionStatus", ""),
            "Tunnel": row.get("TunnelType", ""),
            "Authentication": ", ".join(
                str(item) for item in as_list(row.get("AuthenticationMethod"))
            ),
            "Split Tunneling": yes_no(row.get("SplitTunneling")),
        }
        for row in rows_of(vpn)
    ]
    vpn_rows.sort(key=lambda row: str(row["Name"]).casefold())

    tcp_rows = [
        {
            "local_address": row.get("LocalAddress") or "",
            "local_port": row.get("LocalPort"),
            "remote_address": row.get("RemoteAddress") or "",
            "state": _state(row.get("State")),
            "process": process(row.get("OwningProcess")),
        }
        for row in rows_of(tcp)
    ]
    state_counts = Counter(row["state"] or "Unknown" for row in tcp_rows)

    listeners = {}
    for row in tcp_rows:
        if row["state"] != "Listen":
            continue
        key = (str(row["local_port"]), row["process"])
        current = listeners.get(key)
        if current is None or str(row["local_address"]) < str(current["Local Address"]):
            listeners[key] = {
                "Local Address": row["local_address"],
                "Local Port": row["local_port"],
                "Process": row["process"],
            }
    listening_rows = sorted(
        listeners.values(),
        key=lambda row: (_sort_number(row["Local Port"]), str(row["Process"]).casefold()),
    )

    established_by_process = {}
    for row in tcp_rows:
        if row["state"] != "Established":
            continue
        aggregate = established_by_process.setdefault(
            row["process"], {"connections": 0, "hosts": set()}
        )
        aggregate["connections"] += 1
        if row["remote_address"]:
            aggregate["hosts"].add(str(row["remote_address"]))
    established_rows = [
        {
            "Process": process_name,
            "Connections": aggregate["connections"],
            "Remote Hosts": len(aggregate["hosts"]),
        }
        for process_name, aggregate in established_by_process.items()
    ]
    established_rows.sort(
        key=lambda row: (
            not bool(row["Process"]),
            str(row["Process"]).casefold(),
        )
    )

    udp_by_port_process = {}
    for row in rows_of(udp):
        endpoint = {
            "Local Address": row.get("LocalAddress") or "",
            "Local Port": row.get("LocalPort"),
            "Process": process(row.get("OwningProcess")),
        }
        key = (str(endpoint["Local Port"]), endpoint["Process"])
        current = udp_by_port_process.get(key)
        if current is None or str(endpoint["Local Address"]) < str(current["Local Address"]):
            udp_by_port_process[key] = endpoint
    udp_rows = sorted(
        udp_by_port_process.values(),
        key=lambda row: (_sort_number(row["Local Port"]), str(row["Process"]).casefold()),
    )

    summary = {
        "Mapped Drives": len(mapped_rows),
        "VPN Profiles": len(vpn_rows),
        "Listening TCP Ports": len(listening_rows),
        "Established TCP Connections": state_counts.get("Established", 0),
        "Other TCP States": sum(
            count
            for state, count in state_counts.items()
            if state not in {"Listen", "Established"}
        ),
        "UDP Endpoints": len(udp_rows),
    }
    states = dict(sorted(state_counts.items(), key=lambda item: item[0].casefold()))
    return {
        "groups": [
            {"title": "Summary", "rows": summary},
            {"title": "TCP States", "rows": states},
        ],
        "mapped": mapped_rows,
        "vpn": vpn_rows,
        "listening": listening_rows,
        "established": established_rows,
        "udp": udp_rows,
    }


def collect(ctx):
    return build(
        ctx.query("mapped", MAPPED_SCRIPT),
        ctx.query("smb_mappings", SMB_SCRIPT),
        ctx.query("vpn", VPN_SCRIPT),
        ctx.query("tcp", TCP_SCRIPT, timeout=30),
        ctx.query("udp", UDP_SCRIPT, timeout=30),
        ctx.query("processes", PROCS_SCRIPT),
    )


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (
        kv_groups(data.get("groups"))
        + sub_heading("Mapped drives")
        + list_table(MAPPED_COLUMNS, data.get("mapped"))
        + sub_heading("VPN profiles")
        + list_table(VPN_COLUMNS, data.get("vpn"))
        + sub_heading("Listening TCP ports")
        + list_table(LISTENING_COLUMNS, data.get("listening"))
        + sub_heading("Established TCP connections")
        + list_table(ESTABLISHED_COLUMNS, data.get("established"))
        + sub_heading("UDP endpoints")
        + list_table(UDP_COLUMNS, data.get("udp"))
    )


SECTION = Section(
    key="network_connections",
    title="Network Connections",
    group="Network",
    collect=collect,
    render=render,
    timeout=30,
)
