from .utils import bytes_human, bitrate_to_mbps
from .privacy import mask_mac, mask_string, redact_user_paths, redact_payload
from utils.resources import resource_path
from utils.logger import logger

def render(meta, data, options):
    redact = options.get('redact', True)
    if redact:
        data = redact_payload(data, options)

    import html as _html
    def E(s):
        try:
            return _html.escape('' if s is None else str(s))
        except Exception:
            return ''

    def ths(cols):
        return '<tr>' + ''.join(f'<th>{E(c)}</th>' for c in cols) + '</tr>'

    def table(rows, cols):
        if not rows:
            return '<em>No data</em>'
        body = []
        for r in rows:
            tds = []
            for c in cols:
                val = r.get(c, '') if isinstance(r, dict) else ''
                tds.append(f'<td>{E(val)}</td>')
            body.append('<tr>' + ''.join(tds) + '</tr>')
        return '<table class="list">' + ths(cols) + ''.join(body) + '</table>'

    def count_rows(rows):
        return len(rows) if isinstance(rows, list) else (1 if rows else 0)

    # Date/time normalization helpers available to all sections
    import re, datetime
    _msjson = re.compile(r"/Date\((\d+)\)/")
    def norm_time(v):
        if isinstance(v, dict) and 'DateTime' in v:
            v = v['DateTime']
        if not isinstance(v, str):
            return v
        m = _msjson.search(v)
        if m:
            try:
                ms = int(m.group(1))
                dt = datetime.datetime.fromtimestamp(ms/1000.0)
                return dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                return v
        try:
            s = v
            if len(s) >= 14 and s[:14].isdigit():
                dt = datetime.datetime(
                    int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12]), int(s[12:14])
                )
                return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return v
        return v

    sections = []
    # Show a subtle badge for partial data blocks
    def _badge(title: str, block):
        try:
            if isinstance(block, dict) and block.get('status') == 'partial':
                return title + " <span style='color:#cc7a00;font-size:12px'>(partial)</span>"
        except Exception:
            logger.debug("_badge: suppressed error", exc_info=True)
        return title

    # --- Noldus NVC Summary Report ---
    if 'noldus_nvc_report' in data:
        nvc = data['noldus_nvc_report'] or {}
        noldus_soft = nvc.get('noldus_software', [])
        noldus_drivers = nvc.get('noldus_drivers', [])
        noldus_codecs = nvc.get('noldus_codecs', [])
        noldus_environment = nvc.get('noldus_environment', [])
        sys_sum = nvc.get('system_summary', {})
        if not isinstance(noldus_soft, list): noldus_soft = [noldus_soft] if noldus_soft else []
        if not isinstance(noldus_drivers, list): noldus_drivers = [noldus_drivers] if noldus_drivers else []
        if not isinstance(noldus_codecs, list): noldus_codecs = [noldus_codecs] if noldus_codecs else []
        if not isinstance(noldus_environment, list): noldus_environment = [noldus_environment] if noldus_environment else []

        # Build System Specs for NVC Report
        sys_rows = ""
        # Specific requested fields: OS, Computer Type, Model, Brand, GPU, CPU, Storage, Last Boot
        # Note: 'Storage' might need aggregation if multiple disks. 'Computer Type' ~ Desktop/Laptop inferred from Chassis or Battery?
        # For simplicity, we use the collected sys_sum keys which are populated from collectors.py

        # Helper to format key names nicely
        key_map = {
            'OS': 'Operating System',
            'CPU': 'Processor (CPU)',
            'RAM_GB': 'Memory (RAM)',
            'GPU': 'Graphics (GPU)',
            'LastBoot': 'Last Boot Time',
            'Uptime': 'Computer Uptime',
            'Model': 'Model',
            'Manufacturer': 'Brand/Manufacturer'
        }

        # Custom ordering for NVC report
        ordered_keys = ['Manufacturer', 'Model', 'OS', 'CPU', 'GPU', 'RAM_GB', 'LastBoot', 'Uptime']

        for k in ordered_keys:
            val = sys_sum.get(k, '')
            if k == 'LastBoot':
                val = norm_time(val)
            if k == 'RAM_GB' and val:
                val = f"{val} GB"
            label = key_map.get(k, k)
            sys_rows += f"<tr><th>{label}</th><td>{E(val)}</td></tr>"

        findings_rows = [
            {'Area': 'Software / Packages', 'Count': len(noldus_soft)},
            {'Area': 'Drivers', 'Count': len(noldus_drivers)},
            {'Area': 'Codecs / Filters / Dependencies', 'Count': len(noldus_codecs)},
            {'Area': 'Environment Variables', 'Count': len(noldus_environment)},
        ]
        soft_rows = ""
        if noldus_soft:
            soft_head = "<tr><th>Product</th><th>Version</th><th>Publisher</th><th>Install Date</th><th>Install Location</th></tr>"
            for s in noldus_soft:
                name = s.get('Name') or s.get('DisplayName') or ''
                version = s.get('Version') or s.get('DisplayVersion') or ''
                soft_rows += f"<tr><td>{E(name)}</td><td>{E(version)}</td><td>{E(s.get('Publisher',''))}</td><td>{E(norm_time(s.get('InstallDate','')))}</td><td>{E(s.get('InstallLocation',''))}</td></tr>"
        else:
            soft_head = ""
            soft_rows = "<tr><td colspan='5'>No Noldus/Basler/pylon software or package dependencies detected.</td></tr>"
        driver_rows = table(noldus_drivers, ['DeviceName', 'DriverVersion', 'DriverDate', 'Manufacturer', 'InfName', 'DeviceID'])
        codec_summary = {}
        for item in noldus_codecs:
            if not isinstance(item, dict):
                continue
            file_path = str(item.get('File') or '')
            folder = file_path.rsplit('\\', 1)[0] if '\\' in file_path else item.get('Source', 'Unknown')
            folder = folder or 'Unknown'
            codec_summary[folder] = codec_summary.get(folder, 0) + 1
        codec_summary_rows = [{'Folder / Source': k, 'Count': v} for k, v in sorted(codec_summary.items(), key=lambda item: item[0].lower())]
        codec_rows = table(noldus_codecs, ['Name', 'File', 'Source'])
        env_rows = table(noldus_environment, ['Name', 'Value'])

        html_nvc = f"""
        <h3>NVC Findings Summary</h3>
        {table(findings_rows, ['Area', 'Count'])}
        <h3>System Specifications</h3>
        <table class="kv">{sys_rows}</table>
        <h3>Noldus Software Inventory</h3>
        <table class="list">{soft_head}{soft_rows}</table>
        <h3>Noldus Driver Inventory</h3>
        {driver_rows}
        <h3>Noldus Codec / Filter / Dependency Inventory</h3>
        <p>This section includes installed DirectShow-style filters plus dependency files found under Noldus, Basler, pylon, Daheng, and related paths.</p>
        <h4>Dependency Folder Summary</h4>
        {table(codec_summary_rows, ['Folder / Source', 'Count'])}
        {codec_rows}
        <h3>Noldus / Camera Environment</h3>
        {env_rows}
        """
        sections.append(('NVC Report', html_nvc))

    # OS
    osd = data.get('operating_system') or {}
    if isinstance(osd, dict):
        os_core = osd.get('os') or {}
        # Normalizers
        import datetime as _dt
        def parse_to_dt(v):
            if isinstance(v, dict) and 'DateTime' in v:
                v = v['DateTime']
            # msjson /Date(ms)/ handled by norm_time
            s = v
            try:
                if isinstance(s, (int, float)):
                    # epoch seconds or ms
                    if s > 10_000_000_000:  # ms
                        return _dt.datetime.fromtimestamp(s/1000.0)
                    return _dt.datetime.fromtimestamp(s)
                if isinstance(s, str):
                    # Try MS JSON /Date(ms)/
                    m = _msjson.search(s)
                    if m:
                        try:
                            ms = int(m.group(1))
                            return _dt.datetime.fromtimestamp(ms/1000.0)
                        except Exception:
                            logger.debug("parse_to_dt: suppressed error", exc_info=True)
                    # try msjson or cim inside norm_time; but return parsed here where possible
                    # ISO
                    if 'T' in s:
                        try:
                            iso = s.replace('Z', '+00:00')
                            dt = _dt.datetime.fromisoformat(iso)
                            # Normalize to naive local
                            if dt.tzinfo is not None:
                                dt = dt.astimezone().replace(tzinfo=None)
                            return dt
                        except Exception:
                            logger.debug("parse_to_dt: suppressed error", exc_info=True)
                    # CIM yyyymmddHHMMSS...
                    if len(s) >= 14 and s[:14].isdigit():
                        return _dt.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12]), int(s[12:14]))
                return None
            except Exception:
                return None
        def uptime_human(dt_val):
            if not dt_val:
                return ''
            try:
                now = _dt.datetime.now(dt_val.tzinfo) if getattr(dt_val, 'tzinfo', None) else _dt.datetime.now()
            except Exception:
                now = _dt.datetime.now()
            delta = now - dt_val
            if delta.total_seconds() < 0:
                return ''
            days = delta.days
            hours, rem = divmod(delta.seconds, 3600)
            minutes = rem // 60
            parts = []
            if days:
                parts.append(f"{days} day{'s' if days!=1 else ''}")
            if hours:
                parts.append(f"{hours} hour{'s' if hours!=1 else ''}")
            parts.append(f"{minutes} minute{'s' if minutes!=1 else ''}")
            return ', '.join(parts)

        inst = norm_time(os_core.get('InstallDate'))
        last_boot_fmt = norm_time(os_core.get('LastBootUpTime'))
        last_boot_dt = parse_to_dt(os_core.get('LastBootUpTime'))
        up = uptime_human(last_boot_dt)
        # Build curated OS table
        os_rows = {
            'Caption': os_core.get('Caption'),
            'Version': os_core.get('Version'),
            'BuildNumber': os_core.get('BuildNumber'),
            'OSArchitecture': os_core.get('OSArchitecture'),
            'InstallDate': inst,
            'Last Boot Time': last_boot_fmt,
            'System Uptime': up,
        }
        os_tbl = '<table class="kv">' + ''.join(
            f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in os_rows.items()
        ) + '</table>'
        sections.append((_badge('Operating System', osd), os_tbl))

    # (norm_time defined above)

    # Updates
    upd = data.get('installed_updates') or {}
    hotfix = upd.get('hotfix') or []
    # Flatten InstalledOn to readable DateTime
    for h in hotfix:
        if isinstance(h, dict):
            h['InstalledOn'] = norm_time(h.get('InstalledOn'))
    sections.append((_badge('Installed Updates', upd), table(hotfix, ['HotFixID','Description','InstalledOn','InstalledBy'])))

    # Programs
    progs = data.get('installed_programs') or []
    sections.append((_badge('Installed Programs', data.get('installed_programs')), table(progs, ['Name','Version','InstallDate','Publisher','Uninstall'])))

    # Security
    sec = data.get('security') or {}
    fw = sec.get('firewall') or []
    sections.append(('Firewall Profiles', table([{ 'Name': f.get('Name'), 'Enabled': f.get('Enabled') } for f in fw], ['Name','Enabled'])))
    defender = sec.get('defender') or {}
    if isinstance(defender, dict) and defender:
        def_tbl = '<table class="kv">' + ''.join(
            f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in {
                'AntivirusEnabled': defender.get('AntivirusEnabled'),
                'RealTimeProtectionEnabled': defender.get('RealTimeProtectionEnabled'),
                'AMProductVersion': defender.get('AMProductVersion'),
                'AntispywareSignatureLastUpdated': norm_time(defender.get('AntispywareSignatureLastUpdated')),
            }.items()
        ) + '</table>'
        sections.append((_badge('Windows Defender', defender), def_tbl))
    # UAC / Device Guard / DEP / BitLocker
    if sec.get('uac'):
        uac = sec['uac'] if isinstance(sec['uac'], dict) else {}
        sections.append(('UAC', '<table class="kv">' + ''.join(f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in uac.items()) + '</table>'))
    if sec.get('device_guard'):
        dg = sec['device_guard'] if isinstance(sec['device_guard'], dict) else {}
        # Join list values as comma-separated
        rows = []
        for k, v in dg.items():
            if isinstance(v, list):
                v = ', '.join([str(x) for x in v])
            rows.append((k, v))
        sections.append(('Device Guard', '<table class="kv">' + ''.join(f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in rows) + '</table>'))
    if sec.get('dep'):
        dep = sec['dep'] if isinstance(sec['dep'], dict) else {}
        sections.append(('DEP', '<table class="kv">' + ''.join(f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in dep.items()) + '</table>'))
    bl = sec.get('bitlocker') or []
    if bl:
        sections.append(('BitLocker', table(bl, ['MountPoint','ProtectionStatus','VolumeStatus','EncryptionMethod'])))

    # Hardware summaries
    hw = data.get('hardware') or {}
    # System summary
    cs = hw.get('computer') or {}
    if isinstance(cs, dict) and cs:
        sys_tbl = '<table class="kv">' + ''.join(
            f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in {
                'Manufacturer': cs.get('Manufacturer'),
                'Model': cs.get('Model'),
                'TotalPhysicalMemory': bytes_human(cs.get('TotalPhysicalMemory')),
            }.items()
        ) + '</table>'
        sections.append((_badge('System Summary', cs), sys_tbl))
    # BIOS / Motherboard
    bios = hw.get('bios') or {}
    board = hw.get('board') or {}
    if isinstance(bios, dict) and bios:
        bios_tbl = '<table class="kv">' + ''.join(
            f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in {
                'Manufacturer': bios.get('Manufacturer'),
                'SMBIOSBIOSVersion': bios.get('SMBIOSBIOSVersion'),
                'ReleaseDate': norm_time(bios.get('ReleaseDate')),
            }.items()
        ) + '</table>'
        sections.append((_badge('BIOS', bios), bios_tbl))
    if isinstance(board, dict) and board:
        board_tbl = '<table class="kv">' + ''.join(
            f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in {
                'Manufacturer': board.get('Manufacturer'),
                'Product': board.get('Product'),
                'SerialNumber': (mask_string(board.get('SerialNumber')) if redact else board.get('SerialNumber')),
            }.items()
        ) + '</table>'
        sections.append((_badge('Motherboard', board), board_tbl))
    # CPU
    cpu = hw.get('cpu') or []
    cpu_rows = []
    for c in (cpu if isinstance(cpu, list) else [cpu]):
        if isinstance(c, dict):
            cpu_rows.append({'Name': c.get('Name'), 'Cores': c.get('NumberOfCores'), 'LogicalProcessors': c.get('NumberOfLogicalProcessors')})
    if cpu_rows:
        sections.append((_badge('CPU', cpu), table(cpu_rows, ['Name','Cores','LogicalProcessors'])))
    # Memory modules
    mem = hw.get('memory') or []
    mem_rows = []
    for m in (mem if isinstance(mem, list) else [mem]):
        if isinstance(m, dict):
            mem_rows.append({'Capacity': bytes_human(m.get('Capacity')), 'Speed': m.get('Speed'), 'Manufacturer': m.get('Manufacturer'), 'PartNumber': m.get('PartNumber')})
    if mem_rows:
        sections.append((_badge('Memory', mem), table(mem_rows, ['Capacity','Speed','Manufacturer','PartNumber'])))
    # Video
    video = hw.get('video') or []
    def _video_status(vobj: dict) -> str:
        try:
            cmec = vobj.get('ConfigManagerErrorCode')
            if cmec is not None:
                try:
                    cmec = int(cmec)
                except Exception:
                    cmec = None
            avail = vobj.get('Availability')
            if avail is not None:
                try:
                    avail = int(avail)
                except Exception:
                    avail = None
            status = (vobj.get('Status') or '').strip().lower()
            if cmec is not None and cmec != 0:
                return f"Error ({cmec})"
            if avail in (3, 14, 15):  # Running/Full power or Power save modes
                return 'Online'
            if avail in (7, 8, 11, 16, 18, 19, 20, 21):  # Off/Offline/Not Installed/etc.
                return 'Offline'
            if status in ('ok', 'running'):
                return 'Online'
            if status in ('error', 'degraded', 'stopped'):
                return 'Offline'
            return 'Unknown'
        except Exception:
            return 'Unknown'

    vid_rows = []
    for v in (video if isinstance(video, list) else [video]):
        if isinstance(v, dict):
            vid_rows.append({
                'Name': v.get('Name'),
                'Status': _video_status(v),
                'AdapterRAM': bytes_human(v.get('AdapterRAM')),
                'Resolution': f"{v.get('CurrentHorizontalResolution') or ''}x{v.get('CurrentVerticalResolution') or ''}".strip('x'),
                'RefreshRate': v.get('CurrentRefreshRate'),
                'DriverVersion': v.get('DriverVersion'),
                'DriverDate': norm_time(v.get('DriverDate')),
                'PNPDeviceID': v.get('PNPDeviceID'),
            })
    if vid_rows:
        sections.append((_badge('Video', video), table(vid_rows, ['Name','Status','AdapterRAM','Resolution','RefreshRate','DriverVersion','DriverDate','PNPDeviceID'])))
    # Sound
    sound = hw.get('sound') or []
    snd_rows = []
    for s in (sound if isinstance(sound, list) else [sound]):
        if isinstance(s, dict):
            snd_rows.append({'Name': s.get('Name'), 'Manufacturer': s.get('Manufacturer')})
    if snd_rows:
        sections.append((_badge('Sound', sound), table(snd_rows, ['Name','Manufacturer'])))
    # Storage devices
    disks = hw.get('disks') or []
    d_rows = []
    for d in (disks if isinstance(disks, list) else [disks]):
        if isinstance(d, dict):
            d_rows.append({'Model': d.get('Model'), 'Size': bytes_human(d.get('Size')), 'InterfaceType': d.get('InterfaceType')})
    if d_rows:
        sections.append((_badge('Storage Devices', disks), table(d_rows, ['Model','Size','InterfaceType'])))
    ldisks = hw.get('logical_disks') or []
    for d in ldisks:
        if isinstance(d, dict):
            d['Size'] = bytes_human(d.get('Size'))
            d['FreeSpace'] = bytes_human(d.get('FreeSpace'))
    sections.append((_badge('Logical Disks', ldisks), table(ldisks, ['DeviceID','FileSystem','Size','FreeSpace','VolumeName'])))

    # Network adapters
    net = data.get('network') or {}
    ad = net.get('adapters') or []
    rows = []
    for a in ad:
        if not isinstance(a, dict):
            continue
        mac = a.get('MACAddress')
        rows.append({
            'Name': a.get('Name'),
            'MAC': mask_mac(mac) if redact else mac,
            'Speed': bitrate_to_mbps(a.get('Speed')),
            'DriverVersion': a.get('DriverVersion')
        })
    sections.append((_badge('Network Adapters', ad), table(rows, ['Name','MAC','Speed','DriverVersion'])))
    shares = (net.get('shares') or [])
    if shares:
        sections.append(('Shares', table(shares, ['Name','Path','Description','ShareType'])))

    # Services / Processes (summary)
    services = data.get('services') or []
    if services:
        sections.append(('NT Services', table(services, ['Name','DisplayName','State','StartMode','StartName','PathName'])))
    procs = data.get('processes') or []
    if procs:
        # Normalize working set to MB if present
        for p in procs:
            if isinstance(p, dict) and 'WorkingSetSize' in p:
                p['WorkingSetSize'] = bytes_human(p.get('WorkingSetSize'))
        sections.append(('Running Processes', table(procs, ['Name','ProcessId','ParentProcessId','ThreadCount','WorkingSetSize','ExecutablePath','CommandLine'])))

    # Licenses (masked)
    lic = data.get('licenses') or {}
    if lic:
        rows = []
        pid = lic.get('product_id')
        svc = lic.get('licensing') or {}
        if pid:
            rows.append({'Product': 'Windows', 'Key': mask_string(pid, keep=4)})
        if isinstance(svc, dict):
            key = svc.get('OA3xOriginalProductKey') or svc.get('ProductKeyID')
            if key:
                rows.append({'Product': 'OEM', 'Key': mask_string(key, keep=4)})
        if rows:
            sections.append(('Licenses (masked)', table(rows, ['Product','Key'])))

    # Environment / Regional / Directories / Files
    env = data.get('environment') or {}
    if env:
        rs_tbl = '<table class="kv">' + ''.join(
            f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in {
                'Culture': (env.get('culture') or {}).get('Name'),
                'SystemLocale': (env.get('system_locale') or {}).get('Name')
            }.items()
        ) + '</table>'
        sections.append(('Regional Settings', rs_tbl))
        env_vars = env.get('env') or {}
        if isinstance(env_vars, dict):
            env_rows = [{'Name': k, 'Value': v} for k, v in sorted(env_vars.items(), key=lambda item: str(item[0]).lower())]
            sections.append(('Environment Variables', table(env_rows, ['Name', 'Value'])))
        dirs = env.get('directories') or {}
        if dirs:
            dir_rows = [{'Name': k, 'Path': v} for k,v in dirs.items()]
            sections.append(('System Directories', table(dir_rows, ['Name','Path'])))
        files = env.get('files') or []
        if files:
            sections.append(('System Files', table(files, ['Name','Path'])))

    # Printers
    printers = data.get('printers') or []
    if printers:
        sections.append(('Printers', table(printers, ['Name','DriverName','PortName','Default'])))

    # Autoruns (basic Run keys)
    autoruns = data.get('autoruns') or []
    if autoruns:
        rows_html = []
        rows_html.append('<table class="list">' + ths(['Location','Name','Command']) + '<tbody>')
        for it in autoruns:
            d = it or {}
            loc = E(d.get('Location'))
            name = E(d.get('Name'))
            cmd_raw = '' if d.get('Command') is None else str(d.get('Command'))
            if len(cmd_raw) > 512:
                short = E(cmd_raw[:512]) + '…'
                full = E(cmd_raw)
                cmd_cell = short + "<details><summary>Show more</summary><pre>" + full + "</pre></details>"
            else:
                cmd_cell = E(cmd_raw)
            rows_html.append(f'<tr><td>{loc}</td><td>{name}</td><td>{cmd_cell}</td></tr>')
        rows_html.append('</tbody></table>')
        sections.append(('Autorun (Run keys)', ''.join(rows_html)))

    # Additional sections to match SIW
    acc = data.get('accessibility') or {}
    if acc:
        sections.append(('Accessibility', '<table class="kv">' + ''.join(f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in acc.items()) + '</table>'))

    drivers = data.get('drivers') or []
    if drivers:
        for d in drivers:
            if isinstance(d, dict):
                d['DriverDate'] = norm_time(d.get('DriverDate'))
        sections.append(('Drivers', table(drivers, ['DeviceName','DriverVersion','DriverDate','Manufacturer','InfName','State','StartMode','DeviceID'])))

    codecs = data.get('codecs') or []
    if 'codecs' in data:
        sections.append(('Audio and Video Codecs', table(codecs, ['Name','File'])))

    snapins = data.get('snapins') or []
    if 'snapins' in data:
        sections.append(('MMC Snap-Ins', table(snapins, ['Name','Key'])))

    sensors = data.get('sensors') or []
    if 'sensors' in data:
        # Convert temperature from tenths of Kelvin to Celsius if present
        def sens_row(s):
            t = s.get('CurrentTemperature')
            try:
                c = (int(t) / 10.0) - 273.15
                s['CurrentTemperature'] = f"{c:.1f} °C"
            except Exception:
                logger.debug("sens_row: suppressed error", exc_info=True)
            return s
        sections.append(('Sensors', table([sens_row(dict(x)) for x in sensors], ['InstanceName','CurrentTemperature'])))

    devices = data.get('devices') or []
    if devices:
        imaging_terms = ('image', 'camera', 'basler', 'genicam', 'euresys', 'noldus', 'capture', 'video')
        imaging_devices = []
        for d in devices:
            if not isinstance(d, dict):
                continue
            searchable = ' '.join(str(d.get(k, '')) for k in ('Name', 'Manufacturer', 'PNPClass', 'DeviceID')).lower()
            if any(term in searchable for term in imaging_terms):
                imaging_devices.append(d)
        if imaging_devices:
            sections.append(('Imaging and Camera Devices', table(imaging_devices, ['Name','Manufacturer','PNPClass','ClassGuid','DeviceID'])))
        sections.append(('Devices', table(devices, ['Name','Manufacturer','PNPClass','ClassGuid','DeviceID'])))

    pci = data.get('pci') or []
    if pci:
        sections.append(('PCI', table(pci, ['Name','Manufacturer','DeviceID'])))

    slots = data.get('slots') or []
    if slots:
        sections.append(('System Slots', table(slots, ['SlotDesignation','Status','SupportsHotPlug'])))

    ports = data.get('ports') or []
    if ports:
        sections.append(('Ports', table(ports, ['Type','Name','Mapping'])))

    vm = data.get('virtual_machine') or {}
    if vm:
        sections.append(('Virtual Machine', '<table class="kv">' + ''.join(f'<tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k,v in vm.items()) + '</table>'))

    # Network details
    netinfo = data.get('network_info') or {}
    if netinfo:
        ipcfg = netinfo.get('ipconfig') or []
        sections.append(('Network Information', table(ipcfg, ['InterfaceAlias','IPv4Address','IPv6Address','IPv4DefaultGateway','DnsServer'])))

    conns = data.get('network_connections') or {}
    if conns:
        tcp = conns.get('tcp') or []
        udp = conns.get('udp') or []
        blocks = []
        if tcp:
            blocks.append('<h3>TCP</h3>' + table(tcp, ['LocalAddress','LocalPort','RemoteAddress','RemotePort','State']))
        if udp:
            blocks.append('<h3>UDP</h3>' + table(udp, ['LocalAddress','LocalPort']))
        if blocks:
            sections.append(('Network Connections', ''.join(blocks)))

    nvc_health = data.get('noldus_nvc_report') or {}
    empty_sections = [title for title, html in sections if '<em>No data</em>' in html]
    health_rows = [
        {'Check': 'Redaction', 'Status': 'Enabled' if redact else 'Disabled'},
        {'Check': 'Empty Sections', 'Status': len(empty_sections)},
        {'Check': 'NVC Software / Packages', 'Status': count_rows(nvc_health.get('noldus_software'))},
        {'Check': 'NVC Drivers', 'Status': count_rows(nvc_health.get('noldus_drivers'))},
        {'Check': 'NVC Codecs / Filters / Dependencies', 'Status': count_rows(nvc_health.get('noldus_codecs'))},
        {'Check': 'NVC Environment Variables', 'Status': count_rows(nvc_health.get('noldus_environment'))},
    ]
    health_html = table(health_rows, ['Check', 'Status'])
    if empty_sections:
        health_html += '<p><strong>Empty sections:</strong> ' + E(', '.join(empty_sections)) + '</p>'
    sections.insert(0, ('Report Health', health_html))

    toc = ''.join([f'<li><a href="#s{i}">{E(t)}</a></li>' for i,(t,_) in enumerate(sections)])
    body = ''.join([f'<h2 id="s{i}">{t}<a href="#top" class="top">Top ▲</a></h2>{h}' for i,(t,h) in enumerate(sections)])
    # Optional header logo – embed as base64 so exported HTML is self-contained
    # Ensures the logo shows even after compilation or when opened on another system
    import base64, os
    logo_tag = ''
    try:
        logo_path = resource_path('graphics/PCREPORT.png')
        if logo_path and logo_path.lower().endswith('.png') and os.path.exists(logo_path):
            with open(logo_path, 'rb') as _lf:
                _b64 = base64.b64encode(_lf.read()).decode('ascii')
            logo_src = f"data:image/png;base64,{_b64}"
            logo_tag = (
                f"<img src='{logo_src}' alt='PC Report' "
                "style='height:72px;vertical-align:middle;margin-right:14px;background:transparent;border:none'/>"
            )
    except Exception:
        logo_tag = ''
    html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>PC Report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:20px;color:#222}}
h1{{border-bottom:2px solid #43a296;padding-bottom:6px;margin-top:0;font-size:28px}}
<table>{{}}</table>
 table{{border-collapse:collapse;width:100%;margin:10px 0}}
 table.kv th{{text-align:left;background:#f3f7f6;padding:8px;border:1px solid #e0e0e0;width:260px}}
 table.kv td{{padding:8px;border:1px solid #e0e0e0}}
 table.list th{{background:#eaf5f3;text-align:left;border:1px solid #d6eae5;padding:8px;position:sticky;top:0}}
 table.list td{{border:1px solid #f0f0f0;padding:6px;word-break:break-word}}
 tr:nth-child(even) td{{background:#fafafa}}
 a{{color:#43a296;text-decoration:none}}
 .top{{float:right;font-size:12px;color:#3a8f82}}
 pre{{max-height:240px;overflow:auto;white-space:pre-wrap}}
 details summary{{cursor:pointer}}
</style>
</head>
<body>
<a id="top"></a>
<h1>{logo_tag}NVC PC REPORT</h1>
<p>Generated for {E(meta.get('machine',''))} on {E(meta.get('generated_at',''))}</p>
<ol>{toc}</ol>
{body}
</body></html>
"""
    return html


