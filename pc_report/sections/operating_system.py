"""Operating System: edition, build, activation, boot and policy state."""
from __future__ import annotations

from .. import decode
from ..format import fmt_datetime, uptime_human, yes_no
from ..ps import cim, ps_quote
from ..section import Section, as_list, first_dict, kv_groups

OS_PROPS = ("Caption", "Version", "BuildNumber", "OSArchitecture", "InstallDate", "LastBootUpTime",
            "WindowsDirectory", "SystemDirectory", "BootDevice", "SystemDevice", "SystemStartOptions",
            "RegisteredUser", "Organization", "OSLanguage", "MUILanguages", "Description", "CSName",
            "OperatingSystemSKU", "ProductType", "DataExecutionPrevention_Available",
            "DataExecutionPrevention_SupportPolicy", "EncryptionLevel", "PortableOperatingSystem")

VERSION_KEY = r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
VERSION_PROPS = ("ProductName,EditionID,DisplayVersion,ReleaseId,CurrentBuild,UBR,BuildLab,BuildLabEx,"
                 "BuildBranch,InstallationType,RegisteredOwner,RegisteredOrganization")

POLICY_SCRIPT = r"""
$o = [ordered]@{}
$sys = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction SilentlyContinue
$o.EnableLUA = $sys.EnableLUA
$o.ConsentPromptBehaviorAdmin = $sys.ConsentPromptBehaviorAdmin
$o.SecureBoot = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SecureBoot\State' -ErrorAction SilentlyContinue).UEFISecureBootEnabled
$o.LongPathsEnabled = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction SilentlyContinue).LongPathsEnabled
$pw = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -ErrorAction SilentlyContinue
$o.HiberbootEnabled = $pw.HiberbootEnabled
$o.HibernateEnabled = $pw.HibernateEnabled
$au = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
$o.NoAutoUpdate = $au.NoAutoUpdate
$o.AUOptions = $au.AUOptions
if ($null -eq $o.AUOptions) { $o.AUOptions = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update' -ErrorAction SilentlyContinue).AUOptions }
$o.InsiderBranch = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsSelfHost\Applicability' -ErrorAction SilentlyContinue).BranchName
$o.DisableSR = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -ErrorAction SilentlyContinue).DisableSR
$o.RebootPendingCBS = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$o.RebootRequiredWU = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
$o.PendingFileRename = [bool](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -ErrorAction SilentlyContinue).PendingFileRenameOperations
$o.FirmwareType = [string]$env:firmware_type
$o.SafeMode = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SafeBoot\Option' -ErrorAction SilentlyContinue).OptionValue
$o.KernelVersion = (Get-Item "$env:SystemRoot\System32\ntoskrnl.exe" -ErrorAction SilentlyContinue).VersionInfo.ProductVersion
$o.DotNetRelease = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue).Release
[pscustomobject]$o
"""

LICENSE_SCRIPT = (
    "Get-CimInstance SoftwareLicensingProduct -ErrorAction SilentlyContinue "
    "-Filter \"ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL\" "
    "| Select-Object Name,Description,LicenseStatus,LicenseStatusReason,GracePeriodRemaining,"
    "PartialProductKey,ProductKeyChannel,LicenseFamily"
)


def _minutes_human(minutes) -> str:
    n = decode.to_int(minutes)
    if n is None:
        return ""
    days, rem = divmod(n, 1440)
    hours, mins = divmod(rem, 60)
    return f"{days} days, {hours} hours, {mins} minutes"


def build(os_: dict, ver: dict, pol: dict, lic: dict) -> dict:
    os_, ver, pol, lic = os_ or {}, ver or {}, pol or {}, lic or {}
    build_no = str(os_.get("BuildNumber") or ver.get("CurrentBuild") or "")
    ubr = ver.get("UBR")
    full_build = f"{build_no}.{ubr}" if build_no and ubr is not None else build_no
    display = ver.get("DisplayVersion") or ver.get("ReleaseId") or ""
    version = f"{display} (OS Build {full_build})".strip() if (display or full_build) else ""

    windows = {
        "Name": os_.get("Caption", ""),
        "Product Name": ver.get("ProductName", ""),
        "Edition": ver.get("EditionID", ""),
        "SKU": decode.os_sku(os_.get("OperatingSystemSKU")),
        "Version": version,
        "Kernel Version": pol.get("KernelVersion") or os_.get("Version", ""),
        "Build Lab": ver.get("BuildLab", ""),
        "Build Lab Ex": ver.get("BuildLabEx", ""),
        "Build Branch": ver.get("BuildBranch", ""),
        "Installation Type": ver.get("InstallationType", ""),
        "Product Type": decode.lookup(decode.PRODUCT_TYPES, os_.get("ProductType")),
        "Architecture": os_.get("OSArchitecture", ""),
        "Language": decode.os_language(os_.get("OSLanguage")),
        "MUI Languages": as_list(os_.get("MUILanguages")),
        "Computer Name": os_.get("CSName", ""),
        "Computer Description": os_.get("Description", ""),
        "Registered Owner": ver.get("RegisteredOwner") or os_.get("RegisteredUser", ""),
        "Registered Organization": ver.get("RegisteredOrganization") or os_.get("Organization", ""),
    }
    activation = {
        "Activation Status": decode.lookup(decode.LICENSE_STATUS, lic.get("LicenseStatus")) if lic else "Unknown",
        "License": lic.get("Name", ""),
        "License Description": lic.get("Description", ""),
        "License Channel": lic.get("ProductKeyChannel", ""),
        "Partial Product Key": lic.get("PartialProductKey", ""),
        "Remaining Grace Period": _minutes_human(lic.get("GracePeriodRemaining")),
    }
    pending = bool(pol.get("RebootPendingCBS") or pol.get("RebootRequiredWU") or pol.get("PendingFileRename"))
    boot = {
        "Install Date": fmt_datetime(os_.get("InstallDate")),
        "Boot Time": fmt_datetime(os_.get("LastBootUpTime")),
        "Up Time": uptime_human(os_.get("LastBootUpTime")),
        "OS Root": os_.get("WindowsDirectory", ""),
        "System Directory": os_.get("SystemDirectory", ""),
        "Boot Device": os_.get("BootDevice", ""),
        "System Device": os_.get("SystemDevice", ""),
        "System Start Options": os_.get("SystemStartOptions", ""),
        "Firmware Type": pol.get("FirmwareType", ""),
        "Safe Mode": pol.get("SafeMode") or "No",
        "Fast Startup": yes_no(pol.get("HiberbootEnabled")),
        "Hibernation": yes_no(pol.get("HibernateEnabled")),
        "Portable Operating System": yes_no(os_.get("PortableOperatingSystem")),
        "Pending Reboot": yes_no(pending),
    }
    security = {
        "UAC Enabled": yes_no(pol.get("EnableLUA")),
        "UAC Prompt (Administrators)": decode.lookup(decode.UAC_PROMPT, pol.get("ConsentPromptBehaviorAdmin")),
        "Secure Boot": yes_no(pol.get("SecureBoot")),
        "Hardware DEP Available": yes_no(os_.get("DataExecutionPrevention_Available")),
        "DEP Policy": decode.lookup(decode.DEP_POLICY, os_.get("DataExecutionPrevention_SupportPolicy")),
        "Encryption Level": f"{os_.get('EncryptionLevel')} bits" if os_.get("EncryptionLevel") else "",
        "Long Paths Enabled": yes_no(pol.get("LongPathsEnabled")),
        "Automatic Updates": decode.au_options(pol.get("NoAutoUpdate"), pol.get("AUOptions")),
        "Windows Insider Program": pol.get("InsiderBranch") or "Not enrolled",
        "System Restore": "Disabled" if decode.to_int(pol.get("DisableSR")) == 1 else "Enabled",
        ".NET Framework 4.x": decode.dotnet_release(pol.get("DotNetRelease")),
    }
    return {"groups": [
        {"title": "Windows", "rows": windows},
        {"title": "Activation", "rows": activation},
        {"title": "Boot", "rows": boot},
        {"title": "Security and Policies", "rows": security},
    ]}


def flatten(data) -> dict:
    """All rows of a kv-groups payload in one dict (later groups win on duplicate labels)."""
    out = {}
    for group in as_list((data or {}).get("groups") if isinstance(data, dict) else None):
        if isinstance(group, dict) and isinstance(group.get("rows"), dict):
            out.update(group["rows"])
    return out


def value_of(data, label: str):
    return flatten(data).get(label, "")


def collect(ctx):
    os_ = first_dict(ctx.query("os", cim("Win32_OperatingSystem", OS_PROPS)))
    ver = first_dict(ctx.query("version_registry",
                               f"Get-ItemProperty {ps_quote(VERSION_KEY)} | Select-Object {VERSION_PROPS}"))
    pol = first_dict(ctx.query("policies", POLICY_SCRIPT))
    lic = first_dict(ctx.query("licensing", LICENSE_SCRIPT, timeout=45))
    return build(os_, ver, pol, lic)


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="operating_system", title="Operating System", group="Software",
                  collect=collect, render=render, timeout=45)
