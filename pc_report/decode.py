"""WMI enumeration tables and small decoders used by the sections."""
from __future__ import annotations


def to_int(value, default=None):
    try:
        if isinstance(value, bool):
            return int(value)
        return int(float(value))
    except (TypeError, ValueError):
        return default


def lookup(table: dict, code, other: str = "Other") -> str:
    """Decode one code or a list of codes; unknown codes become 'Other (n)'."""
    if code is None or code == "":
        return ""
    if isinstance(code, list):
        return ", ".join(lookup(table, c, other) for c in code)
    n = to_int(code)
    if n is None:
        return str(code)
    return table.get(n, f"{other} ({n})")


def flags(table: dict, value) -> list[str]:
    """Names of the bits set in ``value``."""
    n = to_int(value)
    if n is None:
        return []
    return [name for bit, name in table.items() if n & bit]


# --- operating system ---------------------------------------------------------

PRODUCT_TYPES = {1: "Workstation", 2: "Domain Controller", 3: "Server"}

_OS_SKU = {
    1: "Ultimate", 2: "Home Basic", 3: "Home Premium", 4: "Enterprise", 6: "Business",
    7: "Server Standard", 8: "Server Datacenter", 27: "Enterprise N", 48: "Professional",
    49: "Professional N", 98: "Home N", 100: "Home Single Language", 101: "Home",
    121: "Education", 122: "Education N", 125: "Enterprise LTSC", 126: "Enterprise N LTSC",
    161: "Pro for Workstations", 162: "Pro for Workstations N", 175: "Enterprise for Virtual Desktops",
    188: "IoT Enterprise", 191: "IoT Enterprise LTSC",
}


def os_sku(code) -> str:
    return lookup(_OS_SKU, code, "SKU")


LICENSE_STATUS = {0: "Unlicensed", 1: "Licensed", 2: "Initial grace period",
                  3: "Additional grace period", 4: "Non-genuine grace period",
                  5: "Notification", 6: "Extended grace period"}

UAC_PROMPT = {0: "Elevate without prompting", 1: "Prompt for credentials on the secure desktop",
              2: "Prompt for consent on the secure desktop", 3: "Prompt for credentials",
              4: "Prompt for consent", 5: "Prompt for consent for non-Windows binaries"}

DEP_POLICY = {0: "Always off", 1: "Always on", 2: "Opt in (Windows programs only)", 3: "Opt out"}

_LCID = {
    1033: "English (United States)", 2057: "English (United Kingdom)", 3081: "English (Australia)",
    4105: "English (Canada)", 1043: "Dutch (Netherlands)", 2067: "Dutch (Belgium)",
    2052: "Chinese (Simplified)", 1028: "Chinese (Traditional)", 1031: "German (Germany)",
    1036: "French (France)", 1034: "Spanish (Spain)", 1040: "Italian (Italy)", 1041: "Japanese",
    1042: "Korean", 1046: "Portuguese (Brazil)", 2070: "Portuguese (Portugal)", 1053: "Swedish",
    1030: "Danish", 1044: "Norwegian", 1035: "Finnish", 1045: "Polish", 1049: "Russian",
    1029: "Czech", 1038: "Hungarian", 1055: "Turkish", 1032: "Greek", 1037: "Hebrew",
    1025: "Arabic (Saudi Arabia)", 1054: "Thai", 1066: "Vietnamese",
}


def os_language(lcid) -> str:
    n = to_int(lcid)
    if n is None:
        return "" if lcid in (None, "") else str(lcid)
    return _LCID.get(n, f"LCID {n}")


_DOTNET = [(533320, "4.8.1"), (528040, "4.8"), (461808, "4.7.2"), (461308, "4.7.1"),
           (460798, "4.7"), (394802, "4.6.2"), (394254, "4.6.1"), (393295, "4.6"),
           (379893, "4.5.2"), (378675, "4.5.1"), (378389, "4.5")]


def dotnet_release(release) -> str:
    n = to_int(release)
    if n is None:
        return ""
    for floor, version in _DOTNET:
        if n >= floor:
            return version
    return f"release {n}"


_AU = {1: "Never check for updates", 2: "Notify before download",
       3: "Automatically download, notify before install",
       4: "Automatically download and schedule installation",
       5: "Local administrator chooses", 7: "Notify for install and restart"}


def au_options(no_auto_update, au_option) -> str:
    if to_int(no_auto_update) == 1:
        return "Disabled by policy"
    n = to_int(au_option)
    if n is None:
        return "Default (managed by Windows)"
    return _AU.get(n, f"Option {n}")


# --- security -----------------------------------------------------------------

def security_center_state(product_state) -> tuple[str, str]:
    """Decode root\\SecurityCenter2 productState into (enabled, signature) words."""
    n = to_int(product_state, 0)
    enabled = "Enabled" if (n >> 12) & 0x1 else "Disabled"
    signature = "Out of date" if (n >> 4) & 0x1 else "Up to date"
    return enabled, signature


DEVICE_GUARD_ONOFF = {0: "Off", 1: "On", 2: "Not applicable"}
DEVICE_GUARD_SERVICES = {0: "None/Unknown", 1: "Credential Guard", 2: "Hypervisor Code Integrity (HVCI)",
                         3: "Secure Boot", 4: "DMA Protection", 5: "Secure Launch",
                         6: "SMM Firmware Measurement", 7: "Kernel-mode Hardware-enforced Stack Protection"}
DEVICE_GUARD_AVAILABLE = {1: "Secure Boot", 2: "DMA Protection", 3: "UEFI Memory Attributes Table",
                          4: "Secure Memory Overwrite", 5: "Kernel DMA Protection",
                          6: "Virtualization-based Security", 7: "HVCI", 8: "Credential Guard",
                          9: "Secure Launch", 10: "SMM Firmware Measurement"}

# --- accessibility ------------------------------------------------------------

_ACC_FLAGS = {0x01: "Enabled", 0x02: "Available", 0x04: "Hotkey activation enabled",
              0x08: "Confirm hotkey activation", 0x10: "Hotkey activation warning sound",
              0x20: "Visual indicator"}


def accessibility_flags(value) -> dict:
    n = to_int(value, 0)
    return {name: ("Yes" if n & bit else "No") for bit, name in _ACC_FLAGS.items()}


# --- system ------------------------------------------------------------------

CHASSIS_TYPES = {
    1: "Other", 2: "Unknown", 3: "Desktop", 4: "Low Profile Desktop", 5: "Pizza Box",
    6: "Mini Tower", 7: "Tower", 8: "Portable", 9: "Laptop", 10: "Notebook", 11: "Hand Held",
    12: "Docking Station", 13: "All in One", 14: "Sub Notebook", 15: "Space-Saving",
    16: "Lunch Box", 17: "Main System Chassis", 18: "Expansion Chassis", 19: "SubChassis",
    20: "Bus Expansion Chassis", 21: "Peripheral Chassis", 22: "Storage Chassis",
    23: "Rack Mount Chassis", 24: "Sealed-Case PC", 30: "Tablet", 31: "Convertible",
    32: "Detachable", 35: "Mini PC", 36: "Stick PC",
}

PC_SYSTEM_TYPES = {0: "Unspecified", 1: "Desktop", 2: "Mobile", 3: "Workstation",
                   4: "Enterprise Server", 5: "SOHO Server", 6: "Appliance PC",
                   7: "Performance Server", 8: "Maximum"}

DOMAIN_ROLES = {0: "Standalone Workstation", 1: "Member Workstation", 2: "Standalone Server",
                3: "Member Server", 4: "Backup Domain Controller", 5: "Primary Domain Controller"}

POWER_PLATFORM_ROLES = {0: "Unspecified", 1: "Desktop", 2: "Mobile", 3: "Workstation",
                        4: "Enterprise Server", 5: "SOHO Server", 6: "Appliance PC",
                        7: "Performance Server", 8: "Slate"}

# --- motherboard -------------------------------------------------------------

ONBOARD_DEVICE_TYPES = {1: "Other", 2: "Unknown", 3: "Video", 4: "SCSI Controller", 5: "Ethernet", 6: "Token Ring",
                        7: "Sound", 8: "PATA Controller", 9: "SATA Controller", 10: "SAS Controller"}
MEMORY_ARRAY_USE = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "System memory", 4: "Video memory", 5: "Flash memory",
                    6: "Non-volatile RAM", 7: "Cache memory"}
MEMORY_ARRAY_LOCATION = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "System board or motherboard", 4: "ISA add-on card",
                         5: "EISA add-on card", 6: "PCI add-on card", 7: "MCA add-on card", 8: "PCMCIA add-on card",
                         9: "Proprietary add-on card", 10: "NuBus"}
CPU_UPGRADE_METHOD = {
    1: "Other", 2: "Unknown", 3: "Daughter Board", 4: "ZIF Socket", 5: "Replacement/Piggy Back", 6: "None",
    7: "LIF Socket", 8: "Slot 1", 9: "Slot 2", 10: "370 Pin Socket", 11: "Slot A", 12: "Slot M",
    13: "Socket 423", 14: "Socket A (Socket 462)", 15: "Socket 478", 16: "Socket 754", 17: "Socket 940",
    18: "Socket 939", 19: "Socket mPGA604", 20: "Socket LGA771", 21: "Socket LGA775", 22: "Socket S1",
    23: "Socket AM2", 24: "Socket F (1207)", 25: "Socket LGA1366", 26: "Socket G34", 27: "Socket AM3",
    28: "Socket C32", 29: "Socket LGA1156", 30: "Socket LGA1567", 31: "Socket PGA988A", 32: "Socket BGA1288",
    33: "rPGA988B", 34: "BGA1023", 35: "BGA1224", 36: "LGA1155", 37: "LGA1356", 38: "LGA2011", 39: "Socket FS1",
    40: "Socket FS2", 41: "Socket FM1", 42: "Socket FM2", 43: "Socket LGA2011-3", 44: "Socket LGA1356-3",
    45: "Socket LGA1150", 46: "Socket BGA1168", 47: "Socket BGA1234", 48: "Socket BGA1364", 49: "Socket AM4",
    50: "Socket LGA1151", 51: "Socket BGA1356", 52: "Socket BGA1440", 53: "Socket BGA1515", 54: "Socket LGA3647-1",
    55: "Socket SP3", 56: "Socket SP3r2", 57: "Socket LGA2066", 58: "Socket BGA1392", 59: "Socket BGA1510",
    60: "Socket BGA1528", 61: "Socket LGA4189", 62: "Socket LGA1200", 63: "Socket LGA4677", 64: "Socket LGA1700",
    65: "Socket BGA1744", 66: "Socket BGA1781", 67: "Socket BGA1211", 68: "Socket BGA2422", 69: "Socket LGA1211",
    70: "Socket LGA2422", 71: "Socket LGA5773", 72: "Socket BGA5773", 73: "Socket AM5", 74: "Socket SP5",
    75: "Socket SP6", 76: "Socket BGA883", 77: "Socket BGA1190", 78: "Socket BGA4129", 79: "Socket LGA4710",
    80: "Socket LGA7529", 81: "Socket BGA1964", 82: "Socket BGA1792", 83: "Socket BGA2049", 84: "Socket BGA2551",
    85: "Socket LGA1851", 86: "Socket BGA2114", 87: "Socket BGA2833",
}

# --- memory ------------------------------------------------------------------

MEMORY_TYPES = {
    0: "Unknown", 1: "Other", 2: "DRAM", 3: "Synchronous DRAM", 4: "Cache DRAM", 5: "EDO",
    6: "EDRAM", 7: "VRAM", 8: "SRAM", 9: "RAM", 10: "ROM", 11: "Flash", 12: "EEPROM",
    13: "FEPROM", 14: "EPROM", 15: "CDRAM", 16: "3DRAM", 17: "SDRAM", 18: "SGRAM",
    19: "RDRAM", 20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM", 24: "DDR3", 25: "FBD2",
    26: "DDR4", 27: "LPDDR", 28: "LPDDR2", 29: "LPDDR3", 30: "LPDDR4", 31: "Logical non-volatile",
    32: "HBM", 33: "HBM2", 34: "DDR5", 35: "LPDDR5", 36: "HBM3",
}

FORM_FACTORS = {0: "Unknown", 1: "Other", 2: "SIP", 3: "DIP", 4: "ZIP", 5: "SOJ", 6: "Proprietary",
                7: "SIMM", 8: "DIMM", 9: "TSOP", 10: "PGA", 11: "RIMM", 12: "SODIMM",
                13: "SRIMM", 14: "SMD", 15: "SSMP", 16: "QFP", 17: "TQFP", 18: "SOIC",
                19: "LCC", 20: "PLCC", 21: "BGA", 22: "FPBGA", 23: "LGA", 24: "FB-DIMM"}

TYPE_DETAIL = {1: "Reserved", 2: "Other", 4: "Unknown", 8: "Fast-paged", 16: "Static column",
               32: "Pseudo-static", 64: "RAMBUS", 128: "Synchronous", 256: "CMOS", 512: "EDO",
               1024: "Window DRAM", 2048: "Cache DRAM", 4096: "Non-volatile", 8192: "Registered (Buffered)",
               16384: "Unbuffered (Unregistered)", 32768: "LRDIMM"}

ERROR_CORRECTION = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "None", 4: "Parity",
                    5: "Single-bit ECC", 6: "Multi-bit ECC", 7: "CRC"}

# --- cpu ---------------------------------------------------------------------

CPU_ARCHITECTURE = {0: "x86", 1: "MIPS", 2: "Alpha", 3: "PowerPC", 5: "ARM", 6: "ia64",
                    9: "x64", 12: "ARM64"}

CACHE_LEVEL = {3: "L1", 4: "L2", 5: "L3"}

CACHE_ASSOCIATIVITY = {1: "Other", 2: "Unknown", 3: "Direct Mapped", 4: "2-way", 5: "4-way",
                       6: "Fully Associative", 7: "8-way", 8: "16-way", 9: "12-way", 10: "24-way",
                       11: "32-way", 12: "48-way", 13: "64-way", 14: "20-way"}

CACHE_TYPE = {1: "Other", 2: "Unknown", 3: "Instruction", 4: "Data", 5: "Unified"}

CPU_STATUS = {0: "Unknown", 1: "Enabled", 2: "Disabled by user", 3: "Disabled by BIOS",
              4: "Idle", 7: "Other"}

# --- bios --------------------------------------------------------------------

_BIOS_CHARACTERISTICS = {
    0: "Reserved", 1: "Reserved", 2: "Unknown", 3: "BIOS characteristics not supported",
    4: "ISA is supported", 5: "MCA is supported", 6: "EISA is supported", 7: "Supports PCI",
    8: "Supports PC Card (PCMCIA)", 9: "Supports Plug and Play", 10: "Supports APM",
    11: "Upgradeable (Flash) BIOS", 12: "Allows BIOS shadowing", 13: "Supports VL-VESA",
    14: "ESCD support is available", 15: "Supports booting from CD-ROM", 16: "Supports selectable boot",
    17: "BIOS ROM is socketed", 18: "Supports booting from PC Card (PCMCIA)",
    19: "Supports Enhanced Disk Drive specification", 20: "Supports INT 13 NEC 9800 1.2M floppy",
    21: "Supports INT 13 Toshiba 1.2M floppy", 22: "Supports INT 13 5.25-inch/360K floppy",
    23: "Supports INT 13 5.25-inch/1.2M floppy", 24: "Supports INT 13 3.5-inch/720K floppy",
    25: "Supports INT 13 3.5-inch/2.88M floppy", 26: "Supports INT 05 print-screen",
    27: "Supports INT 09 and 8042 keyboard services", 28: "Supports INT 14 serial services",
    29: "Supports INT 17 printer services", 30: "Supports INT 10 CGA/Mono video services",
    31: "NEC PC-98", 32: "Supports ACPI", 33: "Supports legacy USB", 34: "Supports AGP",
    35: "Supports booting from I2O device", 36: "Supports booting from LS-120",
    37: "Supports booting from ATAPI ZIP drive", 38: "Supports booting from IEEE 1394 device",
    39: "Smart Battery supported",
}


def bios_characteristics(codes) -> str:
    names = []
    for code in codes or []:
        n = to_int(code)
        if n is None:
            continue
        # SMBIOS reserves bits 40-47 for the vendor; report the number rather than a guessed name.
        if n >= 40:
            names.append(f"Reserved ({n})")
        else:
            names.append(_BIOS_CHARACTERISTICS.get(n, f"Reserved ({n})"))
    return ", ".join(names)


# --- devices -----------------------------------------------------------------

PNP_ERROR_CODES = {
    0: "Working properly", 1: "Not configured correctly", 2: "Cannot load the driver",
    3: "Driver may be corrupted or the system is low on resources", 4: "Driver or registry may be corrupted",
    5: "Needs a resource Windows cannot manage", 6: "Boot configuration conflicts with other devices",
    7: "Cannot filter", 8: "Driver loader is missing", 9: "Firmware is reporting resources incorrectly",
    10: "Cannot start", 11: "Failed", 12: "Not enough free resources", 13: "Cannot verify resources",
    14: "Cannot work until the computer restarts", 15: "Re-enumeration problem",
    16: "Cannot identify all resources", 17: "Asking for an unknown resource type",
    18: "Drivers must be reinstalled", 19: "Registry may be corrupted", 20: "VxD loader failure",
    21: "System failure; try changing the driver", 22: "Disabled", 23: "System failure; try changing the driver",
    24: "Not present, not working properly, or drivers missing", 25: "Windows is still setting up",
    26: "Windows is still setting up", 27: "No valid log configuration", 28: "Drivers not installed",
    29: "Disabled by firmware", 30: "Using an IRQ another device is using", 31: "Cannot load the required drivers",
    32: "Driver start type is disabled", 33: "Cannot determine which resources are required",
    34: "Requires manual configuration", 35: "Firmware lacks resources for this device",
    36: "IRQ translation failed", 37: "Driver returned failure from DriverEntry",
    38: "A previous driver instance is still in memory", 39: "Driver is corrupted or missing",
    40: "Registry service key information is invalid", 41: "Driver loaded but device not found",
    42: "Duplicate device detected", 43: "Driver reported a device failure", 44: "Stopped by an application or service",
    45: "Not connected", 46: "Not available while Windows shuts down", 47: "Prepared for safe removal",
    48: "Blocked from starting because of known problems", 49: "System hive too large",
    50: "Failed to apply one or more properties", 51: "Waiting on another device",
    52: "Driver signature cannot be verified", 53: "Reserved by the debugger", 54: "Failed and is undergoing a reset",
}

SLOT_USAGE = {0: "Reserved", 1: "Other", 2: "Unknown", 3: "Available", 4: "In use"}

SLOT_MAX_DATA_WIDTH = {0: "8 bit", 1: "16 bit", 2: "32 bit", 3: "64 bit", 4: "128 bit",
                       5: "x1", 6: "x2", 7: "x4", 8: "x8", 9: "x12", 10: "x16", 11: "x32"}

DRIVE_TYPES = {0: "Unknown", 1: "No root directory", 2: "Removable", 3: "Local disk",
               4: "Network drive", 5: "CD-ROM", 6: "RAM disk"}

GPT_PARTITION_TYPES = {
    "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}": "EFI System",
    "{e3c9e316-0b5c-4db8-817d-f92df00215ae}": "Microsoft Reserved",
    "{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}": "Basic Data",
    "{de94bba4-06d1-4d40-a16a-bfd50179d6ac}": "Windows Recovery",
    "{5808c8aa-7e8f-42e0-85d2-e1e90434cfb3}": "LDM Metadata",
    "{af9b60a0-1431-4f62-bc68-3311714a69ad}": "LDM Data",
    "{0fc63daf-8483-4772-8e79-3d69d8477de4}": "Linux Filesystem",
    "{0657fd6d-a4ab-43c4-84e5-0933c84b4f4f}": "Linux Swap",
}

BITLOCKER_PROTECTION = {0: "Off", 1: "On", 2: "Unknown"}

VIDEO_ARCHITECTURE = {1: "Other", 2: "Unknown", 3: "CGA", 4: "EGA", 5: "VGA", 6: "SVGA", 7: "MDA",
                      8: "HGC", 9: "MCGA", 10: "8514A", 11: "XGA", 12: "Linear Frame Buffer",
                      160: "PC-98"}

AVAILABILITY = {1: "Other", 2: "Unknown", 3: "Running / Full power", 4: "Warning", 5: "In test",
                6: "Not applicable", 7: "Power off", 8: "Off line", 9: "Off duty", 10: "Degraded",
                11: "Not installed", 12: "Install error", 13: "Power save - unknown",
                14: "Power save - low power", 15: "Power save - standby", 16: "Power cycle",
                17: "Power save - warning", 18: "Paused", 19: "Not ready", 20: "Not configured",
                21: "Quiesced"}

PNP_MONITOR_VENDORS = {
    "DEL": "Dell", "SAM": "Samsung", "LGD": "LG Display", "GSM": "LG", "AUO": "AU Optronics", "BOE": "BOE",
    "ACR": "Acer", "AOC": "AOC", "BNQ": "BenQ", "HWP": "HP", "HPN": "HP", "LEN": "Lenovo", "PHL": "Philips",
    "VSC": "ViewSonic", "IVM": "Iiyama", "SNY": "Sony", "NEC": "NEC", "MSI": "MSI", "ASU": "ASUS", "AUS": "ASUS",
    "EIZ": "Eizo", "ENC": "Eizo", "CMN": "Chi Mei", "SHP": "Sharp", "APP": "Apple", "MEI": "Panasonic",
}

BATTERY_STATUS = {
    1: "Discharging", 2: "Unknown / AC power", 3: "Fully charged", 4: "Low", 5: "Critical",
    6: "Charging", 7: "Charging and high", 8: "Charging and low", 9: "Charging and critical",
    10: "Undefined", 11: "Partially charged",
}

BATTERY_CHEMISTRY = {
    1: "Other", 2: "Unknown", 3: "Lead acid", 4: "Nickel cadmium",
    5: "Nickel metal hydride", 6: "Lithium-ion", 7: "Zinc air", 8: "Lithium polymer",
}

PRINTER_STATUS = {1: "Other", 2: "Unknown", 3: "Idle", 4: "Printing", 5: "Warming up",
                  6: "Stopped printing", 7: "Offline"}

NET_CONNECTION_STATUS = {0: "Disconnected", 1: "Connecting", 2: "Connected", 3: "Disconnecting",
                         4: "Hardware not present", 5: "Hardware disabled", 6: "Hardware malfunction",
                         7: "Media disconnected", 8: "Authenticating", 9: "Authentication succeeded",
                         10: "Authentication failed", 11: "Invalid address", 12: "Credentials required"}

PORT_CONNECTOR_TYPES = {
    0: "Unknown", 1: "Other", 2: "Male", 3: "Female", 4: "Shielded", 5: "Unshielded", 6: "SCSI (A) High-Density",
    7: "SCSI (A) Low-Density", 8: "SCSI (P) High-Density", 9: "SCSI SCA-I", 10: "SCSI SCA-II",
    11: "Fibre Channel (DB-9)", 12: "Fibre Channel Optical", 13: "Fibre Channel SCA-II", 14: "Fibre Channel SSA",
    15: "Fibre Channel Copper", 16: "Fibre Channel Optical", 17: "Fibre Channel Style-2", 18: "Fibre Channel SCA-II",
    19: "Fibre Channel Copper", 20: "Fibre Channel Optical", 21: "PCI", 22: "ISA", 23: "EISA",
    24: "VESA", 25: "MCA", 26: "PCMCIA", 27: "Centronics", 28: "Mini-Centronics", 29: "DB-9", 30: "DB-15",
    31: "DB-25", 32: "DB-37", 33: "DB-50", 34: "ACR", 35: "CardBus", 36: "IEEE-1394", 37: "PS/2",
    38: "Infrared", 39: "HP-HIL", 40: "Access Bus (USB)", 41: "SSA SCSI", 42: "Circular DIN-8 Male",
    43: "Circular DIN-8 Female", 44: "On Board IDE", 45: "On Board Floppy", 46: "9 Pin Dual Inline",
    47: "25 Pin Dual Inline", 48: "50 Pin Dual Inline", 49: "68 Pin Dual Inline", 50: "On Board Sound Input from CD-ROM",
    51: "Mini-Centronics Type-14", 52: "Mini-Centronics Type-26", 53: "Mini-Jack (headphones)", 54: "BNC",
    55: "1394", 56: "PC-98", 57: "PC-98Hireso", 58: "PC-H98", 59: "PC-98Note", 60: "PC-98Full",
    61: "SAS/SATA Plug Receptacle", 62: "USB Type-C", 63: "USB Type-A", 64: "USB Type-B", 65: "USB Type-C Receptacle",
    255: "Other", 160: "RJ-45", 161: "RJ-11", 162: "DVI", 163: "HDMI", 164: "DisplayPort",
}

PORT_TYPES = {0: "None", 1: "Parallel Port XT/AT Compatible", 2: "Parallel Port PS/2", 3: "Parallel Port ECP",
              4: "Parallel Port EPP", 5: "Parallel Port ECP/EPP", 6: "Serial Port XT/AT Compatible",
              7: "Serial Port 16450 Compatible", 8: "Serial Port 16550 Compatible", 9: "Serial Port 16550A Compatible",
              10: "SCSI Port", 11: "MIDI Port", 12: "Joy Stick Port", 13: "Keyboard Port", 14: "Mouse Port",
              15: "SSA SCSI", 16: "USB", 17: "FireWire (IEEE P1394)", 18: "PCMCIA Type I", 19: "PCMCIA Type II",
              20: "PCMCIA Type III", 21: "Cardbus", 22: "Access Bus Port", 23: "SCSI II", 24: "SCSI Wide",
              25: "PC-98", 26: "PC-98-Hireso", 27: "PC-H98", 28: "Video Port", 29: "Audio Port", 30: "Modem Port",
              31: "Network Port", 32: "SATA", 33: "SAS", 34: "MFDP (Multi-Function Display Port)",
              35: "Thunderbolt", 160: "8251 Compatible", 161: "8251 FIFO Compatible", 255: "Other"}

USB_PROTOCOLS = {
    16: "USB",
    17: "USB 1.1",
    18: "USB 2.0",
    19: "USB 3.0",
}

# --- windows update ----------------------------------------------------------

WU_OPERATION = {1: "Installation", 2: "Uninstallation", 3: "Other"}
WU_RESULT = {0: "Not started", 1: "In progress", 2: "Succeeded", 3: "Succeeded with errors",
             4: "Failed", 5: "Aborted"}

# --- pci vendors -------------------------------------------------------------

_PCI_VENDORS = {
    "8086": "Intel Corporation", "10DE": "NVIDIA Corporation", "1002": "Advanced Micro Devices (ATI)",
    "1022": "Advanced Micro Devices", "10EC": "Realtek Semiconductor", "14E4": "Broadcom",
    "11AB": "Marvell Technology", "1B4B": "Marvell Technology", "17CB": "Qualcomm", "168C": "Qualcomm Atheros",
    "1969": "Qualcomm Atheros", "10B5": "PLX Technology", "1106": "VIA Technologies", "1039": "Silicon Integrated Systems",
    "104C": "Texas Instruments", "1180": "Ricoh", "1217": "O2 Micro", "1033": "NEC", "1912": "Renesas",
    "1B21": "ASMedia Technology", "1B73": "Fresco Logic", "1AF4": "Red Hat (virtio)", "15AD": "VMware",
    "80EE": "Oracle (VirtualBox)", "1414": "Microsoft", "5333": "S3 Graphics", "102B": "Matrox",
    "1AF1": "Euresys", "1C6C": "Silicom", "15B3": "Mellanox", "144D": "Samsung Electronics",
    "1987": "Phison Electronics", "1E0F": "Kioxia", "1C5C": "SK hynix", "15B7": "Sandisk / Western Digital",
    "1179": "Toshiba", "1CC1": "ADATA", "126F": "Silicon Motion", "1E49": "Yangtze Memory (YMTC)",
    "1D6A": "Aquantia", "1FC9": "Tehuti Networks", "1077": "QLogic", "1000": "Broadcom / LSI",
    "9005": "Adaptec", "1B85": "OCZ", "1344": "Micron Technology", "1E4B": "Maxio Technology",
    "1D79": "Transcend", "8087": "Intel Corporation", "1013": "Cirrus Logic", "1102": "Creative Labs",
    "13F6": "C-Media", "1412": "VIA (ICE)", "1B96": "Western Digital", "1E95": "Solid State Storage Technology",
}


def pci_vendor(vendor_id) -> str:
    vid = str(vendor_id or "").upper().replace("0X", "")
    return _PCI_VENDORS.get(vid, f"Vendor {vid}" if vid else "")
