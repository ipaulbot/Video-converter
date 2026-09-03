import os
import re
import datetime
from .utils import run_ps_json
from utils.logger import logger

NVC_RELATED_TERMS = (
    'noldus',
    'ethovision',
    'etho vision',
    'observer',
    'mediarecorder',
    'media recorder',
    'catwalk',
    'daniovision',
    'danioscope',
    'ultravox',
    'facereader',
    'viso',
    'basler',
    'pylon',
    'genicam',
    'gige vision',
    'coaxpress',
    'camera link',
    'euresys',
    'leadtools',
    'samplegrabber',
    'resizer filter',
    'rtsp source',
    'tee filter',
    'timestamp corrector',
    'video mixer',
    'hardwareinterface',
    'sentinel hasp',
    'sentinel ldk',
    'safenet',
    'thales',
    'hardlock',
)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _row_text(row):
    if isinstance(row, dict):
        return ' '.join(str(v or '') for v in row.values()).lower()
    return str(row or '').lower()


def filter_nvc_related_items(items):
    matches = []
    for item in _as_list(items):
        text = _row_text(item)
        if any(term in text for term in NVC_RELATED_TERMS):
            if 'hypervisor' in text and 'noldus' not in text:
                continue
            matches.append(item)
            continue
        if 'noldusipp' in text or 'noldus ipp' in text:
            matches.append(item)
    return matches


def normalize_nvc_program_row(row):
    return {
        'Name': row.get('Name') or row.get('DisplayName') or '',
        'Version': row.get('Version') or row.get('DisplayVersion') or '',
        'Publisher': row.get('Publisher') or '',
        'InstallDate': row.get('InstallDate') or '',
        'InstallLocation': row.get('InstallLocation') or '',
    }


def normalize_logical_disk_rows(rows):
    normalized = []
    for row in _as_list(rows):
        if not isinstance(row, dict):
            continue
        device_id = row.get('DeviceID') or row.get('DriveLetter') or ''
        if device_id and len(str(device_id)) == 1:
            device_id = f"{device_id}:"
        if not device_id:
            continue
        normalized.append({
            'DeviceID': device_id,
            'DriveType': row.get('DriveType') or '',
            'FileSystem': row.get('FileSystem') or '',
            'Size': row.get('Size'),
            'FreeSpace': row.get('FreeSpace') if 'FreeSpace' in row else row.get('SizeRemaining'),
            'VolumeName': row.get('VolumeName') or row.get('FileSystemLabel') or '',
        })
    return normalized


def scan_codec_files(root_paths, max_files=500):
    rows = []
    seen = set()
    extensions = ('.ax', '.acm')
    for root in root_paths:
        if not root or not os.path.isdir(root):
            continue
        try:
            filenames = sorted(os.listdir(root))
        except Exception:
            continue
        for filename in filenames:
            if len(rows) >= max_files:
                return rows
            if not filename.lower().endswith(extensions):
                continue
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({'Name': os.path.splitext(filename)[0], 'File': path, 'Source': 'filesystem'})
    return rows


def _uptime_from_last_boot(last_boot):
    if not last_boot:
        return ''
    dt = None
    if isinstance(last_boot, dict):
        last_boot = last_boot.get('DateTime') or ''
    if isinstance(last_boot, str):
        match = re.search(r"/Date\((\d+)\)/", last_boot)
        try:
            if match:
                dt = datetime.datetime.fromtimestamp(int(match.group(1)) / 1000.0)
            elif len(last_boot) >= 14 and last_boot[:14].isdigit():
                dt = datetime.datetime(
                    int(last_boot[0:4]), int(last_boot[4:6]), int(last_boot[6:8]),
                    int(last_boot[8:10]), int(last_boot[10:12]), int(last_boot[12:14])
                )
            elif 'T' in last_boot:
                dt = datetime.datetime.fromisoformat(last_boot.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.astimezone().replace(tzinfo=None)
        except Exception:
            dt = None
    if not dt:
        return ''
    delta = datetime.datetime.now() - dt
    if delta.total_seconds() < 0:
        return ''
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ', '.join(parts)


def scan_nvc_filter_files(root_paths, max_files=500):
    rows = []
    seen = set()
    extensions = ('.ax', '.dll')
    for root in root_paths:
        if not root or not os.path.isdir(root):
            continue
        for current_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith('$') and d.lower() not in {'windowsapps'}]
            for filename in files:
                if len(rows) >= max_files:
                    return rows
                path = os.path.join(current_root, filename)
                if not filename.lower().endswith(extensions):
                    continue
                row = {'Name': os.path.splitext(filename)[0], 'File': path, 'Source': 'filesystem'}
                if not filter_nvc_related_items([row]):
                    continue
                key = path.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def _nvc_filter_roots():
    roots = [
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Common Files', 'Noldus'),
        os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'Common Files', 'Noldus'),
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Basler'),
        os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'Basler'),
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Daheng Imaging'),
    ]
    for value in os.environ.values():
        if not isinstance(value, str):
            continue
        for part in value.split(';'):
            part = part.strip()
            if not part:
                continue
            lower_part = part.lower()
            if (
                filter_nvc_related_items([{'Value': part}])
                and os.path.isdir(part)
                and (
                    'program files' in lower_part
                    or 'common files' in lower_part
                    or 'basler' in lower_part
                    or 'daheng' in lower_part
                )
            ):
                roots.append(part)
    deduped = []
    seen = set()
    for root in roots:
        normalized = os.path.abspath(root)
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        deduped.append(normalized)
    return deduped


def _dedupe_rows(rows, key_fields):
    seen = set()
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = tuple(str(row.get(field, '') or '') for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _first_dict(value):
    items = _as_list(value)
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def collect_nvc_specific():
    """
    Collect specific information related to Noldus software (Ethovision, Observer, etc.)
    and system specs relevant for Noldus products.
    """
    # Reuse the broad installed-program inventory. It captures MSI/package/appx
    # rows that a narrow uninstall-key query can miss.
    programs = [
        normalize_nvc_program_row(row)
        for row in filter_nvc_related_items(collect_programs())
    ]
    programs = _dedupe_rows(programs, ('Name', 'Version', 'Publisher'))

    drivers = filter_nvc_related_items(collect_drivers())
    drivers = _dedupe_rows(drivers, ('DeviceName', 'DriverVersion', 'InfName', 'DeviceID'))

    script_codecs = r"""
    $paths = @(
      'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Drivers32',
      'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Drivers32',
      'HKLM:\SOFTWARE\Classes\CLSID',
      'HKLM:\SOFTWARE\WOW6432Node\Classes\CLSID'
    )
    $rows = foreach($p in $paths){
      if(Test-Path $p){
        if($p -like '*Drivers32'){
          $props = Get-ItemProperty $p -ErrorAction SilentlyContinue
          $props.PSObject.Properties | Where-Object { $_.MemberType -eq 'NoteProperty' } | ForEach-Object {
            [pscustomobject]@{ Name=[string]$_.Name; File=[string]$_.Value; Source=$p }
          }
        } else {
          Get-ChildItem $p -ErrorAction SilentlyContinue | ForEach-Object {
            $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue
            $name = [string]$x.'(default)'
            $server = ''
            try { $server = [string](Get-ItemProperty ($_.PsPath + '\InprocServer32') -ErrorAction SilentlyContinue).'(default)' } catch {}
            if($name -or $server){ [pscustomobject]@{ Name=$name; File=$server; Source=$p } }
          }
        }
      }
    }
    $rows | Where-Object { ($_.Name,$_.File -join ' ') -match 'Noldus|Basler|pylon|GenICam|GigE|CoaXPress|Euresys|SampleGrabber|Resizer|RTSP|Tee|Video Mixer' } | Sort-Object Name
    """
    codecs, _ = run_ps_json(script_codecs, timeout=25)
    codecs = filter_nvc_related_items(codecs)
    codecs = codecs + filter_nvc_related_items(collect_codecs()) + scan_nvc_filter_files(_nvc_filter_roots())
    codecs = _dedupe_rows(codecs, ('Name', 'File'))

    env_rows = []
    for key, value in os.environ.items():
        row = {'Name': key, 'Value': value}
        if filter_nvc_related_items([row]):
            env_rows.append(row)

    os_info = collect_os().get('os') or {}
    hardware = collect_hardware()
    computer = hardware.get('computer') or {}
    cpu = _first_dict(hardware.get('cpu'))
    video_names = []
    for video in _as_list(hardware.get('video')):
        if isinstance(video, dict) and video.get('Name'):
            video_names.append(str(video.get('Name')))
    hw_info = {
        'OS': os_info.get('Caption', ''),
        'CPU': cpu.get('Name', ''),
        'RAM_GB': '',
        'GPU': ', '.join(video_names),
        'LastBoot': os_info.get('LastBootUpTime', ''),
        'Uptime': _uptime_from_last_boot(os_info.get('LastBootUpTime')),
        'Model': computer.get('Model', ''),
        'Manufacturer': computer.get('Manufacturer', ''),
    }
    try:
        total_memory = float(computer.get('TotalPhysicalMemory') or 0)
        if total_memory:
            hw_info['RAM_GB'] = round(total_memory / (1024 ** 3), 2)
    except Exception:
        logger.debug("collect_nvc_specific: suppressed error", exc_info=True)

    return {
        'noldus_software': programs or [],
        'noldus_drivers': drivers or [],
        'noldus_codecs': codecs or [],
        'noldus_environment': env_rows,
        'system_summary': hw_info or {}
    }

def collect_os():
    os_info, _ = run_ps_json('Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,InstallDate,LastBootUpTime,OSArchitecture,SerialNumber,CSName')
    comp_info, _ = run_ps_json('Get-ComputerInfo | Select-Object OsName,WindowsVersion,WindowsBuildLabEx,OsLanguage')
    reg, _ = run_ps_json("Get-Item 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' | Select-Object -ExpandProperty Property | ForEach-Object { @{ ($_)= (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').$_ } }")
    return {
        'os': os_info or {},
        'computer': comp_info or {},
        'registry': reg or {}
    }


def collect_updates():
    hotfix, _ = run_ps_json('Get-HotFix | Select-Object HotFixID,Description,InstalledOn,InstalledBy')
    defender, _ = run_ps_json('Get-MpComputerStatus -ErrorAction SilentlyContinue')
    return {'hotfix': hotfix or [], 'defender': defender or {}}


def collect_programs():
    # 1) Classic installers from registry Uninstall keys
    ps_registry = (
        "$paths = @('HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall',"
        "'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall',"
        "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall');"
        "$acc=@(); foreach($p in $paths){ if(Test-Path $p){ Get-ChildItem $p | ForEach-Object { $x = Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue; if($x.DisplayName){ $acc += [PSCustomObject]@{Name=$x.DisplayName; Version=$x.DisplayVersion; InstallDate=$x.InstallDate; Publisher=$x.Publisher; Uninstall=$x.UninstallString } } } }; $acc | Sort-Object Name"
    )
    reg_items, _ = run_ps_json(ps_registry)
    if reg_items is None:
        reg_items = []

    # 2) PowerShell package providers (winget, msi, etc.)
    ps_packages = (
        "Get-Package -ErrorAction SilentlyContinue | ForEach-Object { "
        "  $pub = '' ; if ($_ | Get-Member -Name Publisher -MemberType NoteProperty,AliasProperty -ErrorAction SilentlyContinue) { $pub = [string]$_.Publisher } "
        "  [pscustomobject]@{ Name = [string]$_.Name; Version = [string]$_.Version; Publisher = $pub } "
        "} | Sort-Object Name"
    )
    pkg_items, _ = run_ps_json(ps_packages)
    if pkg_items is None:
        pkg_items = []

    # 3) Microsoft Store apps
    ps_appx = (
        "Get-AppxPackage -ErrorAction SilentlyContinue | ForEach-Object { "
        "  $pub = [string]$_.Publisher; if ($pub -match 'CN=([^,]+)') { $pub = $matches[1] } "
        "  $inst = '' ; try { if ($_.InstallLocation) { $fi = Get-Item $_.InstallLocation -ErrorAction SilentlyContinue; if ($fi) { $inst = $fi.CreationTime.ToString('yyyy-MM-dd') } } } catch {} "
        "  [pscustomobject]@{ Name = [string]$_.Name; Version = [string]$_.Version; Publisher = $pub; InstallDate = $inst } "
        "} | Sort-Object Name"
    )
    appx_items, _ = run_ps_json(ps_appx)
    if appx_items is None:
        appx_items = []

    # Normalize helper: ensure list
    def _as_list(x):
        if x is None:
            return []
        if isinstance(x, list):
            return x
        return [x]

    reg_list = _as_list(reg_items)
    pkg_list = _as_list(pkg_items)
    appx_list = _as_list(appx_items)

    # Normalize shapes into unified rows
    normalized = []
    def _add(name, version='', install_date='', publisher='', uninstall=''):
        if not name:
            return
        normalized.append({
            'Name': str(name) if name is not None else '',
            'Version': str(version) if version is not None else '',
            'InstallDate': str(install_date) if install_date is not None else '',
            'Publisher': str(publisher) if publisher is not None else '',
            'Uninstall': str(uninstall) if uninstall is not None else ''
        })

    for it in reg_list:
        try:
            # Normalize InstallDate from formats like YYYYMMDD
            inst = it.get('InstallDate')
            if isinstance(inst, str):
                s = inst.strip()
                if len(s) == 8 and s.isdigit():
                    inst = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
            _add(it.get('Name'), it.get('Version'), inst, it.get('Publisher'), it.get('Uninstall'))
        except Exception:
            logger.debug("collect_programs: suppressed error", exc_info=True)

    for it in pkg_list:
        try:
            _add(it.get('Name'), it.get('Version'), it.get('InstallDate') or '', it.get('Publisher') or '', '')
        except Exception:
            logger.debug("collect_programs: suppressed error", exc_info=True)

    for it in appx_list:
        try:
            _add(it.get('Name'), it.get('Version'), it.get('InstallDate') or '', it.get('Publisher') or '', '')
        except Exception:
            logger.debug("collect_programs: suppressed error", exc_info=True)

    # Deduplicate by (Name, Version, Publisher)
    seen = set()
    deduped = []
    for row in normalized:
        key = (row['Name'], row['Version'], row['Publisher'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def collect_security():
    fw, _ = run_ps_json('Get-NetFirewallProfile -ErrorAction SilentlyContinue')
    defender, _ = run_ps_json('Get-MpComputerStatus -ErrorAction SilentlyContinue')
    # UAC
    uac, _ = run_ps_json("(Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -ErrorAction SilentlyContinue) | Select-Object EnableLUA,ConsentPromptBehaviorAdmin")
    # Device Guard (clean, mapped fields only)
    raw_dg, _ = run_ps_json('Get-CimInstance -Namespace root\\Microsoft\\Windows\\DeviceGuard -ClassName Win32_DeviceGuard -ErrorAction SilentlyContinue')
    dg = {}
    def map_onoff(v):
        try:
            i = int(v)
        except Exception:
            return 'Unknown'
        return {0:'Off',1:'On',2:'Not applicable'}.get(i,'Unknown')
    def map_services(arr):
        mapping = {0:'None/Unknown',1:'Credential Guard',2:'Hypervisor Code Integrity (HVCI)',3:'Secure Boot',4:'DMA Protection'}
        if not isinstance(arr, list):
            return []
        out = []
        for x in arr:
            try:
                out.append(mapping.get(int(x), f"Unknown({x})"))
            except Exception:
                out.append(str(x))
        return out
    def map_avail(arr):
        mapping = {1:'Secure Boot',2:'DMA Protection',3:'UEFI Memory Attributes Table',4:'Secure Memory Overwrite',5:'Kernel DMA Protection',6:'Virtualization-based Security',7:'HVCI',8:'Credential Guard'}
        if not isinstance(arr, list):
            return []
        out = []
        for x in arr:
            try:
                out.append(mapping.get(int(x), f"Unknown({x})"))
            except Exception:
                out.append(str(x))
        return out
    if isinstance(raw_dg, dict) and raw_dg:
        dg = {
            'Version': str(raw_dg.get('Version') or ''),
            'VBS Status': map_onoff(raw_dg.get('VirtualizationBasedSecurityStatus')),
            'Usermode CI Enforcement': map_onoff(raw_dg.get('UsermodeCodeIntegrityPolicyEnforcementStatus')),
            'Kernel CI Enforcement': map_onoff(raw_dg.get('CodeIntegrityPolicyEnforcementStatus')),
            'Security Services (Configured)': map_services(raw_dg.get('SecurityServicesConfigured')),
            'Security Services (Running)': map_services(raw_dg.get('SecurityServicesRunning')),
            'Available Security Properties': map_avail(raw_dg.get('AvailableSecurityProperties')),
            'Virtual Machine Isolation': ('Enabled' if raw_dg.get('VirtualMachineIsolation') else 'Disabled'),
            'Virtual Machine Isolation Properties': raw_dg.get('VirtualMachineIsolationProperties') or []
        }
    # DEP flags via OS CIM
    dep, _ = run_ps_json('Get-CimInstance Win32_OperatingSystem | Select-Object DataExecutionPrevention_Available,DataExecutionPrevention_Drivers,DataExecutionPrevention_SupportPolicy,DataExecutionPrevention_32BitApplications')
    # BitLocker (best-effort)
    bl, _ = run_ps_json('Get-BitLockerVolume -ErrorAction SilentlyContinue | Select-Object MountPoint,ProtectionStatus,VolumeStatus,EncryptionMethod')
    return {'firewall': fw or [], 'defender': defender or {}, 'uac': uac or {}, 'device_guard': dg or {}, 'dep': dep or {}, 'bitlocker': bl or []}


def collect_hardware():
    cs, _ = run_ps_json('Get-CimInstance Win32_ComputerSystem')
    bios, _ = run_ps_json('Get-CimInstance Win32_BIOS')
    board, _ = run_ps_json('Get-CimInstance Win32_BaseBoard')
    cpu, _ = run_ps_json('Get-CimInstance Win32_Processor')
    mem, _ = run_ps_json('Get-CimInstance Win32_PhysicalMemory')
    video, _ = run_ps_json('Get-CimInstance Win32_VideoController | Select-Object Name,Status,Availability,ConfigManagerErrorCode,AdapterRAM,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,DriverVersion,DriverDate,PNPDeviceID,VideoProcessor')
    sound, _ = run_ps_json('Get-CimInstance Win32_SoundDevice')
    disk, _ = run_ps_json('Get-CimInstance Win32_DiskDrive')
    ldisks, _ = run_ps_json('Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,DriveType,FileSystem,Size,FreeSpace,VolumeName')
    ldisks = normalize_logical_disk_rows(ldisks)
    if not ldisks:
        volumes, _ = run_ps_json('Get-Volume -ErrorAction SilentlyContinue | Select-Object DriveLetter,DriveType,FileSystem,Size,SizeRemaining,FileSystemLabel')
        ldisks = normalize_logical_disk_rows(volumes)
    return {'computer':cs or {}, 'bios':bios or {}, 'board':board or {}, 'cpu':cpu or [], 'memory':mem or [], 'video':video or [], 'sound':sound or [], 'disks':disk or [], 'logical_disks':ldisks or []}


def collect_network():
    adapters, _ = run_ps_json('Get-CimInstance Win32_NetworkAdapter')
    cfg, _ = run_ps_json('Get-CimInstance Win32_NetworkAdapterConfiguration')
    shares, _ = run_ps_json('Get-SmbShare -ErrorAction SilentlyContinue | Select-Object Name,Path,Description,ShareType')
    return {'adapters': adapters or [], 'config': cfg or [], 'shares': shares or []}


def collect_services(limit=1000):
    svc, _ = run_ps_json('Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode,StartName,PathName | Sort-Object Name')
    return (svc or [])[:limit]


def collect_processes(limit=1000):
    ps, _ = run_ps_json('Get-CimInstance Win32_Process | Select-Object Name,ProcessId,ParentProcessId,ThreadCount,WorkingSetSize,ExecutablePath,CommandLine | Sort-Object Name')
    return (ps or [])[:limit]


def collect_licenses():
    # Best effort: Windows ProductId and OA3x key (masked by renderer)
    pid, _ = run_ps_json("(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').ProductId")
    svc, _ = run_ps_json("Get-CimInstance -ClassName SoftwareLicensingService | Select-Object OA3xOriginalProductKey,ProductKeyID")
    return {'product_id': pid, 'licensing': svc}


def collect_environment():
    env, _ = run_ps_json('[System.Environment]::GetEnvironmentVariables()')
    cult, _ = run_ps_json('Get-Culture | Select-Object Name,DisplayName,LCID')
    sysloc, _ = run_ps_json('Get-WinSystemLocale | Select-Object Name,DisplayName,LCID')
    # System directories
    dirs = {
        'SystemRoot': os.environ.get('SystemRoot',''),
        'ProgramFiles': os.environ.get('ProgramFiles',''),
        'ProgramFiles(x86)': os.environ.get('ProgramFiles(x86)',''),
        'ProgramData': os.environ.get('ProgramData',''),
        'UserProfile': os.environ.get('UserProfile',''),
        'Temp': os.environ.get('TEMP',''),
    }
    # System files (paths-only)
    system32 = os.path.join(os.environ.get('SystemRoot','C\\Windows'), 'System32')
    files = [
        {'Name':'hosts','Path': os.path.join(system32, 'drivers', 'etc', 'hosts')},
        {'Name':'services','Path': os.path.join(system32, 'drivers', 'etc', 'services')},
        {'Name':'win.ini','Path': os.path.join(os.environ.get('SystemRoot','C\\Windows'), 'win.ini')},
        {'Name':'system.ini','Path': os.path.join(os.environ.get('SystemRoot','C\\Windows'), 'system.ini')},
    ]
    return {'env': env or {}, 'culture': cult or {}, 'system_locale': sysloc or {}, 'directories': dirs, 'files': files}


def collect_network_info():
    ipcfg, _ = run_ps_json(
        "Get-NetIPConfiguration -ErrorAction SilentlyContinue | "
        "Select-Object InterfaceAlias, "
        "@{n='IPv4Address';e={ ($_.IPv4Address | ForEach-Object { $_.IPAddress }) -join ', ' }}, "
        "@{n='IPv6Address';e={ ($_.IPv6Address | ForEach-Object { $_.IPAddress }) -join ', ' }}, "
        "@{n='IPv4DefaultGateway';e={ ($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop }) -join ', ' }}, "
        "@{n='DnsServer';e={ ($_.DnsServer.ServerAddresses) -join ', ' }}"
    )
    return {'ipconfig': ipcfg or []}


def collect_printers():
    printers, _ = run_ps_json('Get-CimInstance Win32_Printer | Select-Object Name,DriverName,PortName,Default')
    return printers or []


def collect_autoruns():
    ps = (
        "$runKeys = @('HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',"
        "'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce',"
        "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',"
        "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce');"
        "$skipProps = @('PSPath','PSParentPath','PSChildName','PSDrive','PSProvider','(Default)');"
        "$rows = foreach ($key in $runKeys) {"
        "  try {"
        "    $item = Get-ItemProperty -Path $key -ErrorAction Stop;"
        "    foreach ($p in $item.PSObject.Properties) {"
        "      if ($p.MemberType -ne 'NoteProperty') { continue }"
        "      if ($skipProps -contains $p.Name) { continue }"
        "      if ([string]::IsNullOrWhiteSpace($p.Name)) { continue }"
        "      [pscustomobject]@{ Location = $key; Name = [string]$p.Name; Command = [string]$p.Value }"
        "    }"
        "  } catch { }"
        "}; $rows"
    )
    items, _ = run_ps_json(ps)
    return items or []


# --- Additional collectors to reach SIW parity ---

def collect_accessibility():
    ps = (
        "Get-ItemProperty 'HKCU:\\Control Panel\\Accessibility' -ErrorAction SilentlyContinue | "
        "Select-Object StickyKeys, ToggleKeys, FilterKeys, SoundSentry, ShowSounds, HighContrast"
    )
    data, _ = run_ps_json(ps)
    return data or {}


def collect_drivers():
    ps = (
        "$pnp = Get-CimInstance Win32_PnPSignedDriver | "
        "Select-Object DeviceName,DriverVersion,DriverDate,Manufacturer,InfName,DeviceID;"
        "$sys = Get-CimInstance Win32_SystemDriver | "
        "Select-Object @{n='DeviceName';e={$_.DisplayName}},@{n='DriverVersion';e={''}},@{n='DriverDate';e={''}},@{n='Manufacturer';e={''}},@{n='InfName';e={$_.PathName}},@{n='DeviceID';e={$_.Name}},State,StartMode;"
        "$pnp + $sys | Sort-Object DeviceName"
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_codecs():
    ps = r"""
    $keys = @(
      'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Drivers32',
      'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Drivers32'
    )
    foreach($k in $keys){
      if(Test-Path $k){
        $props = Get-ItemProperty -Path $k -ErrorAction SilentlyContinue
        foreach($p in $props.PSObject.Properties){
          if($p.MemberType -ne 'NoteProperty'){ continue }
          if($p.Name -like 'PS*'){ continue }
          [PSCustomObject]@{ Name=[string]$p.Name; File=[string]$p.Value; Source=$k }
        }
      }
    }
    """
    items, _ = run_ps_json(ps)
    roots = [
        os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32'),
        os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'SysWOW64'),
    ]
    rows = (items or []) + scan_codec_files(roots) + scan_nvc_filter_files(_nvc_filter_roots())
    return _dedupe_rows(rows, ('Name', 'File'))


def collect_snapins():
    ps = (
        "if(Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\MMC\\SnapIns'){ "
        "Get-ChildItem 'HKLM:\\SOFTWARE\\Microsoft\\MMC\\SnapIns' | ForEach-Object {"
        "$n=(Get-ItemProperty $_.PsPath -ErrorAction SilentlyContinue).NameString;"
        "if($n){[PSCustomObject]@{ Name=$n; Key=$_.PsChildName }} } }"
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_sensors():
    # Best-effort thermal zones
    ps = (
        'Get-CimInstance -Namespace root\\wmi MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | '
        'Select-Object InstanceName, CurrentTemperature'
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_devices():
    ps = (
        'Get-CimInstance Win32_PnPEntity | '
        'Select-Object Name, Manufacturer, ClassGuid, PNPClass, DeviceID | Sort-Object Name'
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_pci():
    ps = (
        "Get-CimInstance Win32_PnPEntity | Where-Object { $_.DeviceID -like 'PCI*' -or $_.PNPClass -like 'PCI*' -or $_.Name -like '*PCI*' } | "
        'Select-Object Name, Manufacturer, DeviceID | Sort-Object Name'
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_slots():
    ps = (
        "Get-CimInstance Win32_SystemSlot | ForEach-Object { "
        "[pscustomobject]@{ SlotDesignation = [string]$_.SlotDesignation; Status = [string]$_.Status; SupportsHotPlug = [string]$_.SupportsHotPlug } }"
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_ports():
    ps = (
        "$acc=@(); "
        # COM ports from registry mapping (cast to string)
        "$rk='HKLM:\\HARDWARE\\DEVICEMAP\\SERIALCOMM'; if(Test-Path $rk){ Get-ItemProperty $rk | Get-Member -MemberType NoteProperty | ForEach-Object { $n=[string]$_.Name; $v=[string](Get-ItemProperty $rk).$n; $acc += [PSCustomObject]@{ Type='COM'; Name=$v; Mapping=$n } } } "
        # LPT ports
        "; $lpt = Get-CimInstance Win32_ParallelPort -ErrorAction SilentlyContinue; if($lpt){ $lpt | ForEach-Object { $acc += [PSCustomObject]@{ Type='LPT'; Name=[string]$_.Name; Mapping=[string]$_.DeviceID } } } "
        # USB devices (summary)
        "; $usb = Get-CimInstance Win32_USBControllerDevice -ErrorAction SilentlyContinue | ForEach-Object { [wmi]($_.Dependent) }; if($usb){ $usb | ForEach-Object { $acc += [PSCustomObject]@{ Type='USB'; Name=[string]$_.Name; Mapping=[string]$_.DeviceID } } } ; $acc"
    )
    items, _ = run_ps_json(ps)
    return items or []


def collect_virtual_machine():
    cs, _ = run_ps_json('Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model')
    vm = False
    vendor = ''
    manufacturer = ''
    model = ''
    if isinstance(cs, dict):
        manufacturer = str(cs.get('Manufacturer') or '')
        model = str(cs.get('Model') or '')
        man_low = manufacturer.lower()
        model_low = model.lower()
        for mark in ['vmware','virtualbox','kvm','qemu','hyper-v','xen']:
            if mark in man_low or mark in model_low:
                vm = True
                vendor = mark
                break
    return {'is_vm': vm, 'vendor': vendor, 'manufacturer': manufacturer, 'model': model}


def collect_network_connections():
    tcp, _ = run_ps_json('Get-NetTCPConnection -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State')
    udp, _ = run_ps_json('Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort')
    return {'tcp': tcp or [], 'udp': udp or []}


