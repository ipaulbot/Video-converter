"""Virtual Machine: guest detection from firmware/model markers and devices; host-side hypervisor services."""
from __future__ import annotations

import re

from ..format import yes_no
from ..ps import cim
from ..section import Section, first_dict, flatten_groups, kv_groups, rows_of

SYSTEM_SCRIPT = cim("Win32_ComputerSystem", ("Manufacturer", "Model", "HypervisorPresent"))
FIRMWARE_SCRIPT = ("$b = Get-CimInstance Win32_BIOS -ErrorAction SilentlyContinue; $bb = Get-CimInstance Win32_BaseBoard -ErrorAction SilentlyContinue; "
                   "[pscustomobject]@{ Manufacturer = [string]$b.Manufacturer; Version = [string]$b.Version; "
                   "BaseBoardManufacturer = [string]$bb.Manufacturer; BaseBoardProduct = [string]$bb.Product }")
SERVICES_SCRIPT = cim("Win32_Service", ("Name", "State", "StartMode"),
                      where="Name='vmms' OR Name='vmcompute' OR Name='HvHost' OR Name='LxssManager' OR Name='CmService' "
                            "OR Name='VMTools' OR Name='VBoxService' OR Name='vmicheartbeat' OR Name='WSLService' "
                            "OR Name='xenevtchn' OR Name='qemu-ga' OR Name='QEMU Guest Agent'")

SERVICE_LABELS = {"vmms": "Hyper-V Management (vmms)", "vmcompute": "Hyper-V Host Compute (vmcompute)", "hvhost": "HV Host Service",
                  "lxssmanager": "WSL (LxssManager)", "wslservice": "WSL (WSLService)", "cmservice": "Windows Sandbox (CmService)",
                  "vmtools": "VMware Tools (guest)", "vboxservice": "VirtualBox Guest Additions (guest)",
                  "vmicheartbeat": "Hyper-V Heartbeat (guest)", "xenevtchn": "Xen Event Channel (guest)",
                  "qemu-ga": "QEMU Guest Agent (guest)"}
GUEST_MARKERS = re.compile(r"vmware svga|vmware vmci|virtualbox graphics|hyper-v video|red hat virtio|\bvirtio\b", re.I)

GUEST_SERVICE_VENDORS = {
    "vmtools": "VMware",
    "vboxservice": "VirtualBox",
    "vmicheartbeat": "Hyper-V",
    "xenevtchn": "Xen",
    "qemu-ga": "QEMU/KVM",
    "qemu guest agent": "QEMU/KVM",
}


def detect_vendor(manufacturer, model, bios) -> str:
    text = f"{manufacturer} {model} {bios}".lower()
    if "vmware" in text:
        return "VMware"
    if "virtualbox" in text or "innotek" in text or "vbox" in text:
        return "VirtualBox"
    if "microsoft corporation" in text and "virtual machine" in text:
        return "Hyper-V"
    if "qemu" in text or "kvm" in text or "bochs" in text:
        return "QEMU/KVM"
    if "parallels" in text:
        return "Parallels"
    if "xen" in text:
        return "Xen"
    if "amazon ec2" in text:
        return "Amazon EC2"
    if "google compute engine" in text:
        return "Google Compute Engine"
    return ""


def _marker_vendor(markers: list[str]) -> str:
    text = " ".join(markers).casefold()
    if "vmware" in text:
        return "VMware"
    if "virtualbox" in text:
        return "VirtualBox"
    if "hyper-v" in text:
        return "Hyper-V"
    if "virtio" in text:
        return "QEMU/KVM"
    return ""


def build(system, firmware, services, pnp) -> dict:
    system, firmware = first_dict(system), first_dict(firmware)
    vendor = detect_vendor(system.get("Manufacturer", ""), system.get("Model", ""),
                           f"{firmware.get('Manufacturer', '')} {firmware.get('Version', '')} "
                           f"{firmware.get('BaseBoardManufacturer', '')} {firmware.get('BaseBoardProduct', '')}")
    markers = sorted({str(d.get("Name")) for d in rows_of(pnp) if d.get("Name") and GUEST_MARKERS.search(str(d.get("Name")))},
                     key=str.casefold)
    service_rows = rows_of(services)
    running_guest_services = [
        s for s in service_rows
        if str(s.get("Name", "")).casefold() in GUEST_SERVICE_VENDORS
        and str(s.get("State", "")).casefold() == "running"
    ]
    inferred_vendor = next(
        (GUEST_SERVICE_VENDORS[str(s.get("Name", "")).casefold()] for s in running_guest_services),
        _marker_vendor(markers),
    )
    inside = bool(vendor) or bool(running_guest_services) or bool(markers)
    vendor = vendor or inferred_vendor
    hypervisor = yes_no(system.get("HypervisorPresent")) == "Yes"
    if inside:
        interpretation = f"Virtual machine ({vendor or 'vendor not identified'})"
    elif hypervisor:
        interpretation = "Physical machine with a hypervisor active (Hyper-V role, VBS or WSL 2)"
    else:
        interpretation = "Physical machine, no hypervisor"
    rows = {"Running Inside a VM": yes_no(inside), "Detected Hypervisor": vendor or ("Not identified" if inside else "None"),
            "Hypervisor Present": yes_no(hypervisor), "Interpretation": interpretation,
            "System Manufacturer": system.get("Manufacturer", ""), "System Model": system.get("Model", ""),
            "BIOS Vendor": firmware.get("Manufacturer", ""), "BIOS Version": firmware.get("Version", ""),
            "Guest Device Markers": ", ".join(markers) or "None"}
    svc = {}
    by_name = {
        ("qemu-ga" if str(s.get("Name", "")).casefold() == "qemu guest agent" else str(s.get("Name", "")).casefold()): s
        for s in service_rows
    }
    for name, label in SERVICE_LABELS.items():
        s = by_name.get(name)
        svc[label] = f"{s.get('State')} ({s.get('StartMode')})" if s else "Not installed"
    return {"groups": [{"title": "Detection", "rows": rows}, {"title": "Virtualization Services", "rows": svc}]}


def flatten(data) -> dict:
    return flatten_groups(data)


def collect(ctx):
    pnp = ctx.shared("pnp_entities")
    if pnp is None:
        ctx.note("pnp_entities: unavailable")
    return build(first_dict(ctx.query("system", SYSTEM_SCRIPT)), first_dict(ctx.query("firmware", FIRMWARE_SCRIPT)),
                 ctx.query("services", SERVICES_SCRIPT), pnp)


def render(data, ctx):
    return kv_groups((data or {}).get("groups") if isinstance(data, dict) else None)


SECTION = Section(key="virtual_machine", title="Virtual Machine", group="Hardware", collect=collect, render=render, timeout=60)
