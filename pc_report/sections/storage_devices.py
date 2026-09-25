"""Storage Devices: physical disks with partitions, SMART status, reliability counters (admin) and optical drives."""
from __future__ import annotations

from .. import decode
from ..format import bytes_human, yes_no
from ..ps import cim
from ..section import REQUIRES_ADMIN, Section, kv_groups, list_table, rows_of, sub_heading

PHYS_SCRIPT = ("Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object DeviceId,FriendlyName,Model,Manufacturer,SerialNumber,"
               "MediaType,BusType,Size,HealthStatus,OperationalStatus,FirmwareVersion,SpindleSpeed,PhysicalSectorSize,"
               "LogicalSectorSize,Usage,UniqueId")
DISKS_SCRIPT = ("Get-Disk -ErrorAction SilentlyContinue | Select-Object Number,FriendlyName,SerialNumber,PartitionStyle,IsBoot,IsSystem,"
                "IsReadOnly,IsOffline,NumberOfPartitions,Size,AllocatedSize,Location,Guid,OperationalStatus")
PARTS_SCRIPT = ("Get-Partition -ErrorAction SilentlyContinue | Select-Object DiskNumber,PartitionNumber,DriveLetter,Size,Type,GptType,"
                "IsActive,IsBoot,IsSystem,IsHidden,Offset")
SMART_SCRIPT = cim("MSStorageDriver_FailurePredictStatus", ("InstanceName", "PredictFailure", "Reason"), namespace="root/wmi")
RELIABILITY_SCRIPT = ("Get-PhysicalDisk -ErrorAction SilentlyContinue | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | "
                      "Select-Object DeviceId,Temperature,TemperatureMax,PowerOnHours,Wear,ReadErrorsTotal,WriteErrorsTotal,"
                      "ReadErrorsUncorrected,WriteErrorsUncorrected,StartStopCycleCount")
OPTICAL_SCRIPT = cim("Win32_CDROMDrive", ("Name", "Drive", "MediaType", "Manufacturer", "Status", "MediaLoaded"))

PART_COLUMNS = [("Partition", "Partition"), ("Drive", "Drive"), ("Size", "Size"), ("Type", "Type"), ("GPT Type", "GPT Type"),
                ("Boot", "Boot"), ("System", "System"), ("Active", "Active"), ("Hidden", "Hidden"), ("Offset", "Offset")]
OPT_COLUMNS = [("Name", "Name"), ("Drive", "Drive"), ("Media Type", "Media Type"), ("Manufacturer", "Manufacturer"),
               ("Status", "Status"), ("Media Loaded", "Media Loaded")]


def _hours(h):
    n = decode.to_int(h)
    return f"{n} h ({n // 24} days)" if n is not None else ""


def build(physical, disks, partitions, smart, reliability, optical) -> dict:
    disks_by_no = {}
    for disk in rows_of(disks):
        number = decode.to_int(disk.get("Number"))
        if number is not None:
            disks_by_no[number] = disk
    parts_by_no: dict[int, list] = {}
    for partition in rows_of(partitions):
        number = decode.to_int(partition.get("DiskNumber"))
        if number is not None:
            parts_by_no.setdefault(number, []).append(partition)
    smart_rows = rows_of(smart)
    rel_by_id = {}
    if reliability != REQUIRES_ADMIN:
        for row in rows_of(reliability):
            device_id = row.get("DeviceId")
            if device_id is not None:
                rel_by_id[str(device_id)] = row

    out = []
    physical_rows = sorted(
        rows_of(physical),
        key=lambda row: (
            decode.to_int(row.get("DeviceId")) is None,
            decode.to_int(row.get("DeviceId")) or 0,
        ),
    )
    for ph in physical_rows:
        no = decode.to_int(ph.get("DeviceId"))
        d = disks_by_no.get(no, {}) if no is not None else {}
        model_token = str(ph.get("Model") or ph.get("FriendlyName") or "").split(" ")[0].lower()
        sm = next((s for s in smart_rows if model_token and model_token in str(s.get("InstanceName", "")).lower()), None)
        identity = {"Model": ph.get("Model") or ph.get("FriendlyName", ""), "Friendly Name": ph.get("FriendlyName", ""),
                    "Manufacturer": ph.get("Manufacturer", ""), "Serial Number": ph.get("SerialNumber") or d.get("SerialNumber", ""),
                    "Firmware": ph.get("FirmwareVersion", ""), "Unique ID": ph.get("UniqueId", ""), "Location": d.get("Location", "")}
        geometry = {"Size": bytes_human(ph.get("Size")) if decode.to_int(ph.get("Size")) is not None else "",
                    "Media Type": ph.get("MediaType", ""), "Bus Type": ph.get("BusType", ""),
                    "Spindle Speed": f"{decode.to_int(ph.get('SpindleSpeed'))} RPM" if decode.to_int(ph.get("SpindleSpeed"))
                    else ("N/A (solid state)" if ph.get("MediaType") == "SSD" else ""),
                    "Sector Size (logical / physical)": f"{ph.get('LogicalSectorSize', '')} / {ph.get('PhysicalSectorSize', '')}",
                    "Partition Style": d.get("PartitionStyle", ""), "Partitions": d.get("NumberOfPartitions", ""),
                    "Boot / System Disk": f"{yes_no(d.get('IsBoot'))} / {yes_no(d.get('IsSystem'))}" if d else "",
                    "Read Only": yes_no(d.get("IsReadOnly")), "Offline": yes_no(d.get("IsOffline")), "Usage": ph.get("Usage", "")}
        health = {"Health": ph.get("HealthStatus", ""), "Operational Status": str(ph.get("OperationalStatus") or ""),
                  "SMART Predict Failure": yes_no(sm.get("PredictFailure")) if sm else "Not reported"}
        if reliability == REQUIRES_ADMIN:
            health["Reliability Counters"] = REQUIRES_ADMIN
        else:
            r = rel_by_id.get(str(ph.get("DeviceId")), {}) if ph.get("DeviceId") is not None else {}
            t, tmax = decode.to_int(r.get("Temperature")), decode.to_int(r.get("TemperatureMax"))
            health.update({
                "Temperature": (f"{t} °C" + (f" (max {tmax} °C)" if tmax is not None else "")) if t is not None else "",
                "Power-on Hours": _hours(r.get("PowerOnHours")),
                "Wear": f"{decode.to_int(r.get('Wear'))} %" if decode.to_int(r.get("Wear")) is not None else "",
                "Start/Stop Cycles": r.get("StartStopCycleCount", ""),
                "Read Errors (total / uncorrected)": f"{r.get('ReadErrorsTotal', '')} / {r.get('ReadErrorsUncorrected', '')}" if r else "",
                "Write Errors (total / uncorrected)": f"{r.get('WriteErrorsTotal', '')} / {r.get('WriteErrorsUncorrected', '')}" if r else "",
            })
        parts = sorted(parts_by_no.get(no, []), key=lambda p: decode.to_int(p.get("PartitionNumber")) or 0)
        part_rows = [{"Partition": p.get("PartitionNumber"), "Drive": f"{p['DriveLetter']}:" if p.get("DriveLetter") else "",
                      "Size": bytes_human(p.get("Size")) if decode.to_int(p.get("Size")) is not None else "", "Type": p.get("Type", ""),
                      "GPT Type": decode.GPT_PARTITION_TYPES.get(str(p.get("GptType") or "").lower(), p.get("GptType") or ""),
                      "Boot": yes_no(p.get("IsBoot")), "System": yes_no(p.get("IsSystem")), "Active": yes_no(p.get("IsActive")),
                      "Hidden": yes_no(p.get("IsHidden")), "Offset": p.get("Offset", "")} for p in parts]
        out.append({"name": identity["Model"], "groups": [{"title": "Identity", "rows": identity}, {"title": "Geometry", "rows": geometry},
                                                          {"title": "Health", "rows": health}], "partitions": part_rows})
    optical_rows = [{"Name": o.get("Name", ""), "Drive": o.get("Drive", ""), "Media Type": o.get("MediaType", ""),
                     "Manufacturer": o.get("Manufacturer", ""), "Status": o.get("Status", ""), "Media Loaded": yes_no(o.get("MediaLoaded"))}
                    for o in rows_of(optical)]
    summary = {"Physical Disks": len(out),
               "Total Capacity": bytes_human(sum(decode.to_int(p.get("Size")) or 0 for p in physical_rows)) if physical_rows else "",
               "Unhealthy": ", ".join(d["name"] for d in out if any(g["rows"].get("Health") not in ("Healthy", "", None) for g in d["groups"])) or "None",
               "Optical Drives": len(optical_rows)}
    return {"groups": [{"title": "Summary", "rows": summary}], "disks": out, "optical": optical_rows}


def collect(ctx):
    smart = ctx.query("smart", SMART_SCRIPT)
    if smart is None:
        ctx.note("SMART status: not reported (the WMI provider may require administrator)")
    return build(ctx.query("physical", PHYS_SCRIPT, timeout=45), ctx.query("disks", DISKS_SCRIPT, timeout=45),
                 ctx.query("partitions", PARTS_SCRIPT, timeout=45), smart,
                 ctx.admin_query("reliability", RELIABILITY_SCRIPT, timeout=45), ctx.query("optical", OPTICAL_SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [kv_groups(data.get("groups"))]
    for d in rows_of(data.get("disks")):
        out.append(sub_heading(d.get("name", "")) + kv_groups(d.get("groups")) + list_table(PART_COLUMNS, d.get("partitions")))
    out.append(sub_heading("Optical drives") + list_table(OPT_COLUMNS, data.get("optical")))
    return "".join(out)


SECTION = Section(key="storage_devices", title="Storage Devices", group="Hardware", collect=collect, render=render, timeout=45)
