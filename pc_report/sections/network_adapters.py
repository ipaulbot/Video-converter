"""Network Adapters: NDIS view, WMI view, IP interface settings and every advanced property per adapter."""
from __future__ import annotations

from .. import decode
from ..format import bitrate_to_mbps, fmt_date, fmt_datetime, yes_no
from ..ps import cim
from ..section import Section, as_list, kv_groups, list_table, rows_of, sub_heading

ADAPTERS_SCRIPT = ("Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue | Select-Object Name,InterfaceDescription,ifIndex,Status,"
                   "MacAddress,LinkSpeed,MediaType,PhysicalMediaType,MtuSize,DriverVersion,DriverDate,DriverProvider,"
                   "DriverFileName,DriverDescription,PnPDeviceID,InterfaceGuid,Virtual,Hidden,FullDuplex,PromiscuousMode,"
                   "ReceiveLinkSpeed,TransmitLinkSpeed,ConnectorPresent,NdisVersion")
ADVANCED_SCRIPT = ("Get-NetAdapterAdvancedProperty -ErrorAction SilentlyContinue | Select-Object Name,DisplayName,"
                   "DisplayValue,RegistryKeyword,RegistryValue")
IPIF_SCRIPT = ("Get-NetIPInterface -ErrorAction SilentlyContinue | Select-Object ifIndex,AddressFamily,NlMtu,"
               "InterfaceMetric,Dhcp,ConnectionState")
WMI_SCRIPT = cim("Win32_NetworkAdapter", ("Name", "NetConnectionID", "NetConnectionStatus", "PhysicalAdapter", "AdapterType",
                                          "Speed", "MACAddress", "Manufacturer", "PNPDeviceID", "Index", "InterfaceIndex",
                                          "TimeOfLastReset"))

GIGE_KEYWORDS = {"*JumboPacket": "Jumbo Packet", "*ReceiveBuffers": "Receive Buffers",
                 "*TransmitBuffers": "Transmit Buffers", "*InterruptModeration": "Interrupt Moderation",
                 "*FlowControl": "Flow Control", "*EEE": "Energy-Efficient Ethernet",
                 "*SpeedDuplex": "Speed and Duplex", "*RSS": "Receive Side Scaling"}
ADV_COLUMNS = [("Property", "Property"), ("Value", "Value"), ("Keyword", "Registry keyword"),
               ("Raw", "Registry value")]
GIGE_COLUMNS = [("Adapter", "Adapter"), ("Link Speed", "Link Speed")] + [
    (value, value) for value in GIGE_KEYWORDS.values()
]
DHCP = {0: "", 1: "Enabled", 2: "Disabled"}
CONNECTION = {0: "", 1: "Connected", 2: "Disconnected"}
_NON_PHYSICAL_NAMES = ("wan miniport", "bluetooth", "vethernet", "npcap")


def _link_speed(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        if any(char.isalpha() for char in stripped):
            return stripped
        value = stripped
    return bitrate_to_mbps(value)


def _is_physical(adapter: dict, wmi: dict) -> bool:
    name = f"{adapter.get('Name', '')} {adapter.get('InterfaceDescription', '')}".casefold()
    excluded = bool(adapter.get("Virtual")) or bool(adapter.get("Hidden"))
    excluded = excluded or any(token in name for token in _NON_PHYSICAL_NAMES)
    detected = bool(wmi.get("PhysicalAdapter")) or (
        not adapter.get("Virtual") and bool(adapter.get("ConnectorPresent"))
    )
    return detected and not excluded


def build(adapters, advanced, ipif, wmi) -> dict:
    adv_by_name: dict[str, list] = {}
    for item in rows_of(advanced):
        adv_by_name.setdefault(str(item.get("Name") or ""), []).append(item)
    ip_by_index: dict[int | None, dict] = {}
    for item in rows_of(ipif):
        fam = "IPv6" if decode.to_int(item.get("AddressFamily")) == 23 else "IPv4"
        ip_by_index.setdefault(decode.to_int(item.get("ifIndex")), {})[fam] = item
    wmi_by_index = {decode.to_int(item.get("InterfaceIndex")): item for item in rows_of(wmi)}

    out = []
    connected = 0
    for adapter in rows_of(adapters):
        name = str(adapter.get("Name") or adapter.get("InterfaceDescription") or "")
        idx = decode.to_int(adapter.get("ifIndex"))
        wmi_row = wmi_by_index.get(idx, {})
        ips = ip_by_index.get(idx, {})
        physical = _is_physical(adapter, wmi_row)
        connected += str(adapter.get("Status")).casefold() == "up"
        identity = {
            "Description": adapter.get("InterfaceDescription", ""),
            "Manufacturer": wmi_row.get("Manufacturer", ""),
            "Adapter Type": wmi_row.get("AdapterType", ""),
            "Physical": yes_no(physical),
            "Virtual": yes_no(adapter.get("Virtual")),
            "Hidden": yes_no(adapter.get("Hidden")),
            "Interface Index": "" if idx is None else idx,
            "Interface GUID": adapter.get("InterfaceGuid", ""),
            "PnP Device ID": adapter.get("PnPDeviceID", ""),
            "MAC Address": adapter.get("MacAddress") or wmi_row.get("MACAddress", ""),
        }
        link = {
            "Status": adapter.get("Status", ""),
            "Connection Status": decode.lookup(decode.NET_CONNECTION_STATUS, wmi_row.get("NetConnectionStatus")),
            "Link Speed": _link_speed(adapter.get("LinkSpeed", "")),
            "Full Duplex": yes_no(adapter.get("FullDuplex")),
            "Media Type": adapter.get("MediaType", ""),
            "Physical Media": adapter.get("PhysicalMediaType", ""),
            "MTU": adapter.get("MtuSize", ""),
            "Promiscuous Mode": yes_no(adapter.get("PromiscuousMode")),
            "Connector Present": yes_no(adapter.get("ConnectorPresent")),
            "NDIS Version": adapter.get("NdisVersion", ""),
            "Last Reset": fmt_datetime(wmi_row.get("TimeOfLastReset")) if wmi_row.get("TimeOfLastReset") else "",
        }
        for fam in ("IPv4", "IPv6"):
            interface = ips.get(fam, {})
            link[f"{fam} Metric"] = interface.get("InterfaceMetric", "")
            link[f"{fam} DHCP"] = decode.lookup(DHCP, interface.get("Dhcp")) if interface else ""
            link[f"{fam} MTU"] = interface.get("NlMtu", "")
            link[f"{fam} State"] = decode.lookup(CONNECTION, interface.get("ConnectionState")) if interface else ""
        driver = {
            "Driver Description": adapter.get("DriverDescription", ""),
            "Driver Version": adapter.get("DriverVersion", ""),
            "Driver Date": fmt_date(adapter.get("DriverDate")) if adapter.get("DriverDate") else "",
            "Driver Provider": adapter.get("DriverProvider", ""),
            "Driver File": adapter.get("DriverFileName", ""),
        }
        advanced_rows = [
            {
                "Property": prop.get("DisplayName", ""),
                "Value": prop.get("DisplayValue", ""),
                "Keyword": prop.get("RegistryKeyword", ""),
                "Raw": ", ".join(str(value) for value in as_list(prop.get("RegistryValue"))),
            }
            for prop in adv_by_name.get(name, [])
        ]
        out.append({
            "name": name,
            "groups": [
                {"title": "Adapter", "rows": identity},
                {"title": "Link", "rows": link},
                {"title": "Driver", "rows": driver},
            ],
            "advanced": advanced_rows,
            "_physical": physical,
        })

    out.sort(key=lambda item: (not item["_physical"], item["name"].casefold()))
    gige = []
    for item in out:
        if item["_physical"]:
            name = item["name"]
            by_keyword = {
                prop.get("RegistryKeyword"): prop.get("DisplayValue", "")
                for prop in adv_by_name.get(name, [])
            }
            link_rows = item["groups"][1]["rows"]
            gige_row = {"Adapter": name, "Link Speed": link_rows["Link Speed"]}
            for keyword, label in GIGE_KEYWORDS.items():
                gige_row[label] = by_keyword.get(keyword, "")
            gige.append(gige_row)
        del item["_physical"]

    summary = {
        "Adapters": len(out),
        "Physical Adapters": len(gige),
        "Connected": connected,
    }
    return {"groups": [{"title": "Summary", "rows": summary}], "adapters": out, "gige": gige}


def collect(ctx):
    return build(
        ctx.query("adapters", ADAPTERS_SCRIPT),
        ctx.query("advanced", ADVANCED_SCRIPT, timeout=60),
        ctx.query("ip_interfaces", IPIF_SCRIPT),
        ctx.query("wmi", WMI_SCRIPT),
    )


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [
        kv_groups(data.get("groups")),
        sub_heading("Physical adapters: GigE-relevant settings"),
        list_table(GIGE_COLUMNS, data.get("gige")),
    ]
    adapters = rows_of(data.get("adapters"))
    if not adapters:
        out.append(sub_heading("Adapters") + list_table([("Name", "Name")], []))
    for adapter in adapters:
        out.append(
            sub_heading(adapter.get("name", ""))
            + kv_groups(adapter.get("groups"))
            + list_table(ADV_COLUMNS, adapter.get("advanced"))
        )
    return "".join(out)


SECTION = Section(
    key="network_adapters",
    title="Network Adapters",
    group="Hardware",
    collect=collect,
    render=render,
    timeout=60,
)
