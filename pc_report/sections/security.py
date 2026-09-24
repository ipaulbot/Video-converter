"""Security: Security Center products, Defender, firewall, VBS, TPM, BitLocker, admins and account policy."""
from __future__ import annotations

from .. import decode
from ..format import fmt_datetime, yes_no
from ..ps import cim
from ..section import REQUIRES_ADMIN, Section, first_dict, kv_groups, kv_table, list_table, rows_of, sub_heading

SC_SCRIPT = r"""
foreach ($cls in 'AntiVirusProduct','AntiSpywareProduct','FirewallProduct') {
  Get-CimInstance -Namespace root/SecurityCenter2 -ClassName $cls -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ Kind = $cls; Name = [string]$_.displayName; State = $_.productState
                       Path = [string]$_.pathToSignedProductExe; Timestamp = [string]$_.timestamp }
  }
}
"""
DEFENDER_SCRIPT = ("Get-MpComputerStatus -ErrorAction SilentlyContinue | Select-Object AMProductVersion,AMEngineVersion,"
                   "AMServiceEnabled,AntivirusEnabled,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,"
                   "AntispywareEnabled,RealTimeProtectionEnabled,IsTamperProtected,NISEnabled,BehaviorMonitorEnabled,"
                   "IoavProtectionEnabled,QuickScanEndTime,FullScanEndTime,QuickScanAge,FullScanAge")
FIREWALL_SCRIPT = ("Get-NetFirewallProfile -ErrorAction SilentlyContinue | Select-Object Name,Enabled,DefaultInboundAction,"
                   "DefaultOutboundAction,NotifyOnListen,LogFileName,LogMaxSizeKilobytes")
DEVICE_GUARD_SCRIPT = cim("Win32_DeviceGuard", ("VirtualizationBasedSecurityStatus", "SecurityServicesConfigured",
                                                "SecurityServicesRunning", "AvailableSecurityProperties",
                                                "RequiredSecurityProperties", "CodeIntegrityPolicyEnforcementStatus",
                                                "UsermodeCodeIntegrityPolicyEnforcementStatus"),
                          namespace=r"root\Microsoft\Windows\DeviceGuard")
TPM_SCRIPT = ("Get-Tpm -ErrorAction SilentlyContinue | Select-Object TpmPresent,TpmReady,TpmEnabled,TpmActivated,"
              "ManufacturerIdTxt,ManufacturerVersion,ManagedAuthLevel,LockedOut")
BITLOCKER_SCRIPT = ("Get-BitLockerVolume -ErrorAction SilentlyContinue | Select-Object MountPoint,VolumeType,ProtectionStatus,"
                    "LockStatus,EncryptionMethod,EncryptionPercentage,VolumeStatus,"
                    "@{n='KeyProtector';e={($_.KeyProtector | ForEach-Object { [string]$_.KeyProtectorType }) -join ', '}}")
ADMINS_SCRIPT = "Get-LocalGroupMember -Group Administrators -ErrorAction SilentlyContinue | Select-Object Name,ObjectClass,PrincipalSource"

KINDS = {"AntiVirusProduct": "Antivirus", "AntiSpywareProduct": "Anti-spyware", "FirewallProduct": "Firewall"}
FW_ACTION = {0: "Not configured", 2: "Allow", 4: "Block"}
VBS_STATUS = {0: "Not enabled", 1: "Enabled, not running", 2: "Running"}
CI_STATUS = {0: "Off", 1: "Audit", 2: "Enforced"}
ENCRYPTION_METHOD = {0: "None", 1: "AES 128 with diffuser", 2: "AES 256 with diffuser", 3: "AES 128", 4: "AES 256",
                     5: "Hardware", 6: "XTS-AES 128", 7: "XTS-AES 256"}
PROTECTION = {0: "Off", 1: "On", 2: "Unknown"}

SC_COLUMNS = [("Kind", "Kind"), ("Name", "Product"), ("State", "State"), ("Signatures", "Signatures"),
              ("Path", "Path"), ("Timestamp", "Timestamp")]
FW_COLUMNS = [("Profile", "Profile"), ("Enabled", "Enabled"), ("Inbound", "Inbound"),
              ("Outbound", "Default outbound"), ("Notify", "Notify on listen"), ("Log", "Log file"), ("Log Size", "Log size")]
BL_COLUMNS = [("Volume", "Volume"), ("Type", "Type"), ("Protection", "Protection"), ("Lock", "Lock"),
              ("Method", "Method"), ("Encrypted", "Encrypted"), ("Key Protectors", "Key protectors")]
ADMIN_COLUMNS = [("Local Administrators", "Member"), ("Class", "Class"), ("Source", "Source")]


def _fw_action(value):
    return decode.lookup(FW_ACTION, value) if decode.to_int(value) is not None else str(value or "")


def _scan_age(age):
    n = decode.to_int(age)
    if n is None:
        return ""
    return "Never" if n >= 4294967295 else f"{n} day{'s' if n != 1 else ''} ago"


def _kv_or_admin(label, value, rows_fn):
    if value == REQUIRES_ADMIN:
        return {label: REQUIRES_ADMIN}
    return rows_fn(first_dict(value) if not isinstance(value, dict) else value)


def _tpm_rows(t):
    return {"TPM Present": yes_no(t.get("TpmPresent")), "TPM Ready": yes_no(t.get("TpmReady")),
            "TPM Enabled": yes_no(t.get("TpmEnabled")), "TPM Activated": yes_no(t.get("TpmActivated")),
            "TPM Manufacturer": str(t.get("ManufacturerIdTxt") or "").strip(),
            "TPM Manufacturer Version": t.get("ManufacturerVersion", ""),
            "TPM Locked Out": yes_no(t.get("LockedOut"))} if t else {"TPM": "Not detected"}


def _net_accounts(text) -> dict:
    rows = {}
    for line in (text or "").splitlines():
        if ":" not in line or line.lower().startswith("the command"):
            continue
        key, _, value = line.partition(":")
        rows[key.strip().rstrip("?")] = value.strip()
    return rows


def build(sc, defender, firewall, dg, tpm, bitlocker, admins, accounts_text) -> dict:
    defender, dg = defender or {}, dg or {}
    security_center = []
    for p in rows_of(sc):
        enabled, signature = decode.security_center_state(p.get("State"))
        security_center.append({"Kind": KINDS.get(p.get("Kind"), p.get("Kind", "")), "Name": p.get("Name", ""),
                                "State": enabled, "Signatures": signature if p.get("Kind") != "FirewallProduct" else "",
                                "Path": p.get("Path", ""), "Timestamp": p.get("Timestamp", "")})
    defender_rows = {
        "Platform Version": defender.get("AMProductVersion", ""), "Engine Version": defender.get("AMEngineVersion", ""),
        "Signature Version": defender.get("AntivirusSignatureVersion", ""),
        "Signatures Updated": fmt_datetime(defender.get("AntivirusSignatureLastUpdated")),
        "Antivirus Enabled": yes_no(defender.get("AntivirusEnabled")),
        "Real-time Protection": yes_no(defender.get("RealTimeProtectionEnabled")),
        "Behavior Monitoring": yes_no(defender.get("BehaviorMonitorEnabled")),
        "Network Inspection": yes_no(defender.get("NISEnabled")),
        "Tamper Protection": yes_no(defender.get("IsTamperProtected")),
        "Last Quick Scan": _scan_age(defender.get("QuickScanAge")) or fmt_datetime(defender.get("QuickScanEndTime")),
        "Last Full Scan": _scan_age(defender.get("FullScanAge")) or fmt_datetime(defender.get("FullScanEndTime")),
    } if defender else {"Microsoft Defender": "Not available (another product may be registered)"}
    fw_rows = [{"Profile": f.get("Name", ""), "Enabled": yes_no(f.get("Enabled")),
                "Inbound": _fw_action(f.get("DefaultInboundAction")), "Outbound": _fw_action(f.get("DefaultOutboundAction")),
                "Notify": yes_no(f.get("NotifyOnListen")), "Log": f.get("LogFileName", ""),
                "Log Size": f"{f.get('LogMaxSizeKilobytes')} KB" if f.get("LogMaxSizeKilobytes") else ""}
               for f in rows_of(firewall)]
    vbs = {
        "Virtualization-based Security": decode.lookup(VBS_STATUS, dg.get("VirtualizationBasedSecurityStatus")),
        "Security Services Configured": decode.lookup(decode.DEVICE_GUARD_SERVICES, dg.get("SecurityServicesConfigured")),
        "Security Services Running": decode.lookup(decode.DEVICE_GUARD_SERVICES, dg.get("SecurityServicesRunning")),
        "Available Security Properties": decode.lookup(decode.DEVICE_GUARD_AVAILABLE, dg.get("AvailableSecurityProperties")),
        "Kernel-mode Code Integrity": decode.lookup(CI_STATUS, dg.get("CodeIntegrityPolicyEnforcementStatus")),
        "User-mode Code Integrity": decode.lookup(CI_STATUS, dg.get("UsermodeCodeIntegrityPolicyEnforcementStatus")),
    } if dg else {"Virtualization-based Security": "Not reported"}
    tpm_rows = _kv_or_admin("TPM", tpm, _tpm_rows)
    if bitlocker == REQUIRES_ADMIN:
        bl_rows = REQUIRES_ADMIN
    else:
        bl_rows = [{"Volume": v.get("MountPoint", ""), "Type": str(v.get("VolumeType") or ""),
                    "Protection": decode.lookup(PROTECTION, v.get("ProtectionStatus")),
                    "Lock": str(v.get("LockStatus") or ""), "Method": decode.lookup(ENCRYPTION_METHOD, v.get("EncryptionMethod")),
                    "Encrypted": f"{v.get('EncryptionPercentage')} %" if v.get("EncryptionPercentage") is not None else "",
                    "Key Protectors": v.get("KeyProtector", "")} for v in rows_of(bitlocker)]
    admin_rows = [{"Local Administrators": a.get("Name", ""), "Class": a.get("ObjectClass", ""),
                   "Source": {1: "Local", 2: "Active Directory", 3: "Azure AD", 4: "Microsoft account"}.get(
                       decode.to_int(a.get("PrincipalSource")), str(a.get("PrincipalSource") or ""))}
                  for a in rows_of(admins)]
    return {
        "groups": [{"title": "Microsoft Defender", "rows": defender_rows},
                   {"title": "Virtualization-based Security", "rows": vbs},
                   {"title": "TPM", "rows": tpm_rows},
                   {"title": "Account Policy", "rows": _net_accounts(accounts_text)}],
        "security_center": security_center, "firewall": fw_rows, "bitlocker": bl_rows, "admins": admin_rows,
    }


def flatten(data) -> dict:
    out = {}
    for group in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        out.update(group.get("rows") or {})
    return out


def collect(ctx):
    return build(ctx.query("security_center", SC_SCRIPT),
                 first_dict(ctx.query("defender", DEFENDER_SCRIPT, timeout=30)),
                 ctx.query("firewall", FIREWALL_SCRIPT),
                 first_dict(ctx.query("device_guard", DEVICE_GUARD_SCRIPT)),
                 ctx.admin_query("tpm", TPM_SCRIPT),
                 ctx.admin_query("bitlocker", BITLOCKER_SCRIPT, timeout=30),
                 ctx.query("local_admins", ADMINS_SCRIPT),
                 ctx.text("net_accounts", ["net", "accounts"]))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    out = [sub_heading("Security Center"), list_table(SC_COLUMNS, data.get("security_center")),
           kv_groups(data.get("groups")),
           sub_heading("Firewall profiles"), list_table(FW_COLUMNS, data.get("firewall")),
           sub_heading("BitLocker")]
    bl = data.get("bitlocker")
    out.append(kv_table([("BitLocker", REQUIRES_ADMIN)]) if bl == REQUIRES_ADMIN else list_table(BL_COLUMNS, bl))
    out += [sub_heading("Local Administrators"), list_table(ADMIN_COLUMNS, data.get("admins"))]
    return "".join(out)


SECTION = Section(key="security", title="Security", group="Software", collect=collect, render=render, timeout=30)
