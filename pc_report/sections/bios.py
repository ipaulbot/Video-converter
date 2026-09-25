"""BIOS: vendor, versions, release date, decoded characteristics, firmware type and ACPI tables."""
from __future__ import annotations

from .. import decode
from ..format import fmt_date, yes_no
from ..ps import cim
from ..section import Section, first_dict, flatten_groups, kv_groups, rows_of

BIOS_PROPS = ("Manufacturer", "Name", "Version", "SMBIOSBIOSVersion", "SMBIOSMajorVersion", "SMBIOSMinorVersion",
              "ReleaseDate", "BiosCharacteristics", "EmbeddedControllerMajorVersion", "EmbeddedControllerMinorVersion",
              "SystemBiosMajorVersion", "SystemBiosMinorVersion", "SerialNumber", "PrimaryBIOS", "Status",
              "CurrentLanguage", "InstallableLanguages")
BIOS_SCRIPT = cim("Win32_BIOS", BIOS_PROPS)
ACPI_SCRIPT = ("Get-ChildItem 'HKLM:\\HARDWARE\\ACPI' -ErrorAction SilentlyContinue | ForEach-Object { "
               "[pscustomobject]@{ Table = $_.PSChildName } }")
BOOT_SCRIPT = ("[pscustomobject]@{ FirmwareType = [string]$env:firmware_type; SecureBoot = (Get-ItemProperty "
               "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecureBoot\\State' -ErrorAction SilentlyContinue).UEFISecureBootEnabled }")


def _ver(major, minor):
    if major in (None, "") or minor in (None, ""):
        return ""
    return f"{major}.{minor}"


def build(bios, acpi, boot) -> dict:
    bios, boot = bios or {}, boot or {}
    rows = {
        "Vendor": bios.get("Manufacturer", ""), "Name": bios.get("Name", ""), "Version": bios.get("Version", ""),
        "SMBIOS BIOS Version": bios.get("SMBIOSBIOSVersion", ""),
        "SMBIOS Version": _ver(bios.get("SMBIOSMajorVersion"), bios.get("SMBIOSMinorVersion")),
        "System BIOS Version": _ver(bios.get("SystemBiosMajorVersion"), bios.get("SystemBiosMinorVersion")),
        "Embedded Controller Version": _ver(bios.get("EmbeddedControllerMajorVersion"), bios.get("EmbeddedControllerMinorVersion")),
        "Release Date": fmt_date(bios.get("ReleaseDate")) if bios.get("ReleaseDate") else "",
        "Primary BIOS": yes_no(bios.get("PrimaryBIOS")), "Status": bios.get("Status", ""),
        "Current Language": bios.get("CurrentLanguage", ""), "Installable Languages": bios.get("InstallableLanguages", ""),
        "Serial Number": bios.get("SerialNumber", ""),
        "Firmware Type": boot.get("FirmwareType", ""), "Secure Boot": yes_no(boot.get("SecureBoot")),
        "Characteristics": decode.bios_characteristics(bios.get("BiosCharacteristics")),
        "ACPI Tables": ", ".join(str(t.get("Table")) for t in rows_of(acpi) if t.get("Table")),
    }
    return {"groups": [{"title": "BIOS", "rows": rows}]}


def flatten(data) -> dict:
    return flatten_groups(data)


def collect(ctx):
    return build(first_dict(ctx.query("bios", BIOS_SCRIPT)), ctx.query("acpi", ACPI_SCRIPT),
                 first_dict(ctx.query("boot", BOOT_SCRIPT)))


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="bios", title="BIOS", group="Hardware", collect=collect, render=render)
