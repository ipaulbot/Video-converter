"""The ordered list of report sections and the option keys that switch them.

``ORDER`` is the page order and the only place it is defined. A section
module that is not yet written is simply absent from ``SECTIONS``.
"""
from __future__ import annotations

import importlib
import pkgutil

from . import sections as _pkg
from .section import GROUPS, Section

ORDER: tuple[str, ...] = (
    "noldus_summary",
    "operating_system", "installed_updates", "licenses", "system_directories", "system_files",
    "installed_programs", "security", "accessibility", "environment", "regional_settings",
    "processes", "services", "drivers", "autorun", "codecs", "mmc_snapins",
    "system_summary", "motherboard", "bios", "cpu", "memory", "sensors", "devices", "pci",
    "system_slots", "network_adapters", "video", "monitors", "sound", "storage_devices",
    "logical_disks", "ports", "usb", "printers", "virtual_machine", "cameras",
    "network_information", "shares", "network_connections",
)

# Option keys the dialog (and older callers) pass that map onto several or renamed sections.
ALIASES: dict[str, tuple[str, ...]] = {
    "hardware": ("system_summary", "motherboard", "bios", "cpu", "memory", "video", "sound",
                 "storage_devices", "logical_disks"),
    "network": ("network_adapters", "shares"),
    "noldus_nvc_report": ("noldus_summary",),
    "network_info": ("network_information",),
    "autoruns": ("autorun",),
    "snapins": ("mmc_snapins",),
    "slots": ("system_slots",),
}


def _discover() -> list[Section]:
    found = []
    for module_info in pkgutil.iter_modules(_pkg.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{_pkg.__name__}.{module_info.name}")
        section = getattr(module, "SECTION", None)
        if isinstance(section, Section):
            found.append(section)
    unknown = [s.key for s in found if s.key not in ORDER]
    if unknown:
        raise RuntimeError(f"sections not in registry.ORDER: {unknown}")
    return sorted(found, key=lambda s: ORDER.index(s.key))


SECTIONS: tuple[Section, ...] = tuple(_discover())


def by_key(key: str, sections=None) -> Section | None:
    for section in (sections if sections is not None else SECTIONS):
        if section.key == key:
            return section
    return None


def grouped(sections=None) -> dict[str, list[Section]]:
    out: dict[str, list[Section]] = {group: [] for group in GROUPS}
    for section in (sections if sections is not None else SECTIONS):
        out.setdefault(section.group, []).append(section)
    return out


def is_enabled(section: Section, options: dict) -> bool:
    if section.key in options:
        return bool(options[section.key])
    for alias, targets in ALIASES.items():
        if section.key in targets and alias in options:
            return bool(options[alias])
    return section.default_on


def select(options: dict, sections=None) -> list[Section]:
    options = options or {}
    return [s for s in (sections if sections is not None else SECTIONS) if is_enabled(s, options)]
