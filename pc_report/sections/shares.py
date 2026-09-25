"""Shares: SMB shares with permissions, client configuration, server configuration."""
from __future__ import annotations

from .. import decode
from ..format import yes_no
from ..section import REQUIRES_ADMIN, Section, first_dict, kv_groups, list_table, rows_of, sub_heading

SHARES_SCRIPT = (
    "Get-SmbShare -ErrorAction SilentlyContinue | Select-Object Name,Path,Description,"
    "ShareType,ShareState,CurrentUsers,CachingMode,EncryptData,FolderEnumerationMode,Special"
)
ACCESS_SCRIPT = (
    "Get-SmbShare -ErrorAction SilentlyContinue | Get-SmbShareAccess "
    "-ErrorAction SilentlyContinue | Select-Object Name,AccountName,AccessControlType,AccessRight"
)
CLIENT_SCRIPT = (
    "$c = Get-SmbClientConfiguration -ErrorAction SilentlyContinue; "
    "[pscustomobject]@{ EnableInsecureGuestLogons = $c.EnableInsecureGuestLogons; "
    "RequireSecuritySignature = $c.RequireSecuritySignature; "
    "EnableSecuritySignature = $c.EnableSecuritySignature; "
    "EnableMultiChannel = $c.EnableMultiChannel; "
    "SMB1 = (Get-ItemProperty "
    "'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Parameters' "
    "-ErrorAction SilentlyContinue).SMB1 }"
)
SERVER_SCRIPT = (
    "Get-SmbServerConfiguration -ErrorAction SilentlyContinue | Select-Object "
    "EnableSMB1Protocol,EnableSMB2Protocol,RequireSecuritySignature,"
    "EnableSecuritySignature,AutoShareServer,AutoShareWorkstation"
)

COLUMNS = [
    ("Name", "Name"),
    ("Path", "Path"),
    ("Description", "Description"),
    ("Type", "Type"),
    ("State", "State"),
    ("Current Users", "Current Users"),
    ("Caching", "Caching"),
    ("Encrypted", "Encrypted"),
    ("Special", "Special"),
]
ACCESS_COLUMNS = [
    ("Share", "Share"),
    ("Account Name", "Account"),
    ("Control", "Control"),
    ("Right", "Right"),
]
_ADMIN_SHARE_NAMES = {"admin$", "c$", "ipc$", "print$"}


def _special(row: dict) -> bool:
    name = str(row.get("Name") or "").casefold()
    return bool(row.get("Special")) or name in _ADMIN_SHARE_NAMES


def build(shares, access, client, server) -> dict:
    client = first_dict(client)
    share_rows = [
        {
            "Name": row.get("Name", ""),
            "Path": row.get("Path") or "",
            "Description": row.get("Description") or "",
            "Type": decode.lookup(decode.SHARE_TYPE, row.get("ShareType")),
            "State": decode.lookup(decode.SHARE_STATE, row.get("ShareState")),
            "Current Users": row.get("CurrentUsers", ""),
            "Caching": decode.lookup(decode.SHARE_CACHING, row.get("CachingMode")),
            "Encrypted": yes_no(row.get("EncryptData")),
            "Special": yes_no(_special(row)),
        }
        for row in rows_of(shares)
    ]
    share_rows.sort(
        key=lambda row: (row["Special"] == "Yes", str(row["Name"]).casefold())
    )

    access_rows = [
        {
            "Share": row.get("Name", ""),
            "Account Name": row.get("AccountName", ""),
            "Control": decode.lookup(
                decode.SHARE_ACCESS_CONTROL, row.get("AccessControlType")
            ),
            "Right": decode.lookup(decode.SHARE_ACCESS_RIGHT, row.get("AccessRight")),
        }
        for row in rows_of(access)
    ]
    access_rows.sort(
        key=lambda row: (
            str(row["Share"]).casefold(),
            str(row["Account Name"]).casefold(),
            str(row["Control"]),
        )
    )

    client_rows = (
        {
            "Insecure Guest Logons": yes_no(client.get("EnableInsecureGuestLogons")),
            "Signing Required (client)": yes_no(client.get("RequireSecuritySignature")),
            "Signing Enabled (client)": yes_no(client.get("EnableSecuritySignature")),
            "Multichannel": yes_no(client.get("EnableMultiChannel")),
            "SMB1 Registry Override": (
                ""
                if client.get("SMB1") is None
                else yes_no(client.get("SMB1"))
            ),
        }
        if client
        else {"Client Configuration": "Not available"}
    )
    if server == REQUIRES_ADMIN:
        server_rows = {"Server Configuration": REQUIRES_ADMIN}
    else:
        server = first_dict(server)
        server_rows = (
            {
                "SMB1 Protocol (server)": yes_no(server.get("EnableSMB1Protocol")),
                "SMB2/3 Protocol (server)": yes_no(server.get("EnableSMB2Protocol")),
                "Signing Required (server)": yes_no(
                    server.get("RequireSecuritySignature")
                ),
                "Administrative Shares (server)": yes_no(
                    server.get("AutoShareServer")
                ),
                "Administrative Shares (workstation)": yes_no(
                    server.get("AutoShareWorkstation")
                ),
            }
            if server
            else {"Server Configuration": "Not available"}
        )
    summary = {
        "Shares": len(share_rows),
        "User Shares": sum(row["Special"] == "No" for row in share_rows),
        "Administrative Shares": sum(row["Special"] == "Yes" for row in share_rows),
        "Connected Users": sum(
            decode.to_int(row["Current Users"]) or 0 for row in share_rows
        ),
    }
    return {
        "groups": [
            {"title": "Summary", "rows": summary},
            {"title": "SMB Client", "rows": client_rows},
            {"title": "SMB Server", "rows": server_rows},
        ],
        "rows": share_rows,
        "access": access_rows,
    }


def flatten(data) -> dict:
    out = {}
    for group in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(group.get("rows") or {})
    return out


def collect(ctx):
    return build(
        ctx.query("shares", SHARES_SCRIPT, timeout=30),
        ctx.query("access", ACCESS_SCRIPT, timeout=30),
        ctx.query("client", CLIENT_SCRIPT),
        ctx.admin_query("server", SERVER_SCRIPT, timeout=30),
    )


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return (
        kv_groups(data.get("groups"))
        + sub_heading("Shares")
        + list_table(COLUMNS, data.get("rows"))
        + sub_heading("Share permissions")
        + list_table(ACCESS_COLUMNS, data.get("access"))
    )


SECTION = Section(
    key="shares",
    title="Shares",
    group="Network",
    collect=collect,
    render=render,
    timeout=30,
)
