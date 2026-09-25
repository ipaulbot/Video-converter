"""Logical Disks: every volume with usage, health, allocation unit, backing disk and BitLocker state (admin)."""
from __future__ import annotations

from .. import decode
from ..format import bytes_human, percent
from ..ps import cim
from ..section import REQUIRES_ADMIN, Section, kv_groups, list_table, rows_of, sub_heading

LD_SCRIPT = cim("Win32_LogicalDisk", ("DeviceID", "VolumeName", "DriveType", "FileSystem", "Size", "FreeSpace", "VolumeSerialNumber",
                                      "Compressed", "ProviderName", "Description", "MediaType"))
VOL_SCRIPT = ("Get-Volume -ErrorAction SilentlyContinue | Where-Object DriveLetter | Select-Object DriveLetter,FileSystemLabel,FileSystem,"
              "HealthStatus,OperationalStatus,AllocationUnitSize,Size,SizeRemaining,DriveType")
PARTS_SCRIPT = ("Get-Partition -ErrorAction SilentlyContinue | Where-Object DriveLetter | ForEach-Object { "
                "$d = Get-Disk -Number $_.DiskNumber -ErrorAction SilentlyContinue; "
                "[pscustomobject]@{ DriveLetter = [string]$_.DriveLetter; DiskNumber = $_.DiskNumber; PartitionNumber = $_.PartitionNumber; "
                "BusType = [string]$d.BusType; DiskModel = [string]$d.FriendlyName } }")
BITLOCKER_SCRIPT = ("Get-BitLockerVolume -ErrorAction SilentlyContinue | Select-Object MountPoint,ProtectionStatus,VolumeStatus,"
                    "EncryptionPercentage")

COLUMNS = [("Drive", "Drive"), ("Label", "Label"), ("Type", "Type"), ("File System", "File System"), ("Total", "Total"),
           ("Used", "Used"), ("Free", "Free"), ("Free %", "Free %"), ("Health", "Health"), ("Allocation Unit", "Allocation Unit"),
           ("Compressed", "Compressed"), ("Disk", "Disk"), ("Bus Type", "Bus Type"), ("BitLocker", "BitLocker"),
           ("Volume Serial Number", "Volume Serial Number"), ("Network Path (host name)", "Network Path")]


def build(logical, volumes, partitions, bitlocker) -> dict:
    vol_by = {}
    for volume in rows_of(volumes):
        letter = str(volume.get("DriveLetter") or "").upper()
        if letter:
            vol_by[letter] = volume
    part_by = {}
    for partition in rows_of(partitions):
        letter = str(partition.get("DriveLetter") or "").upper()
        if letter:
            part_by[letter] = partition
    bl_by = {}
    if bitlocker != REQUIRES_ADMIN:
        for item in rows_of(bitlocker):
            letter = str(item.get("MountPoint") or "").upper().rstrip(":")
            if letter:
                bl_by[letter] = item

    rows, low = [], []
    logical_rows = sorted(rows_of(logical), key=lambda row: str(row.get("DeviceID") or "").upper())
    for ld in logical_rows:
        letter = str(ld.get("DeviceID") or "").rstrip(":").upper()
        v, p = vol_by.get(letter, {}), part_by.get(letter, {})
        size, free = decode.to_int(ld.get("Size")), decode.to_int(ld.get("FreeSpace"))
        valid_capacity = size is not None and free is not None and size > 0 and 0 <= free <= size
        used = size - free if valid_capacity else None
        pct = percent(free, size) if valid_capacity else ""
        if valid_capacity and free / size < 0.10:
            pct = f"⚠ {pct}"
            low.append(f"{letter}:")
        if bitlocker == REQUIRES_ADMIN:
            bl = REQUIRES_ADMIN
        else:
            b = bl_by.get(letter)
            bl = decode.lookup(decode.BITLOCKER_PROTECTION, b.get("ProtectionStatus")) if b else ""
        disk_number = decode.to_int(p.get("DiskNumber")) if p else None
        disk_model = p.get("DiskModel", "") if p else ""
        disk = f"{disk_number} ({disk_model})" if disk_number is not None else ""
        rows.append({
            "Drive": f"{letter}:" if letter else "", "Label": ld.get("VolumeName") or v.get("FileSystemLabel", ""),
            "Type": decode.lookup(decode.DRIVE_TYPES, ld.get("DriveType")), "File System": ld.get("FileSystem") or v.get("FileSystem", ""),
            "Total": bytes_human(size) if size is not None else "", "Used": bytes_human(used) if used is not None else "",
            "Free": bytes_human(free) if free is not None else "", "Free %": pct,
            "Health": v.get("HealthStatus", ""), "Allocation Unit": f"{decode.to_int(v.get('AllocationUnitSize'))} B"
            if decode.to_int(v.get("AllocationUnitSize")) is not None else "",
            "Compressed": "Yes" if ld.get("Compressed") else ("No" if ld.get("Compressed") is not None else ""),
            "Disk": disk, "Bus Type": p.get("BusType", ""),
            "BitLocker": bl, "Volume Serial Number": ld.get("VolumeSerialNumber", ""),
            "Network Path (host name)": ld.get("ProviderName") or "",
        })
    summary = {"Volumes": len(rows), "Fixed": sum(1 for r in rows if r["Type"] == "Local disk"),
               "Network": sum(1 for r in rows if r["Type"] == "Network drive"),
               "Removable": sum(1 for r in rows if r["Type"] == "Removable"),
               "Low Space (<10 %)": ", ".join(low) or "None"}
    return {"groups": [{"title": "Summary", "rows": summary}], "rows": rows}


def collect(ctx):
    return build(ctx.query("logical", LD_SCRIPT), ctx.query("volumes", VOL_SCRIPT, timeout=45),
                 ctx.query("partitions", PARTS_SCRIPT, timeout=45), ctx.admin_query("bitlocker", BITLOCKER_SCRIPT, timeout=30))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Volumes") + list_table(COLUMNS, data.get("rows"))


SECTION = Section(key="logical_disks", title="Logical Disks", group="Hardware", collect=collect, render=render, timeout=45)
