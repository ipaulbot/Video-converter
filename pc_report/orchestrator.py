import concurrent.futures as cf
import datetime, os
from . import collectors as C


def run_all(options: dict, progress_cb=None):
    # Map names -> callables
    tasks = {
        'noldus_nvc_report': C.collect_nvc_specific, # New specialized section
        'operating_system': C.collect_os,
        'installed_updates': C.collect_updates,
        'installed_programs': C.collect_programs,
        'security': C.collect_security,
        'hardware': C.collect_hardware,
        'network': C.collect_network,
        'network_connections': C.collect_network_connections,
        'services': lambda: C.collect_services(limit=options.get('services_limit', 1000)),
        'processes': lambda: C.collect_processes(limit=options.get('processes_limit', 1000)),
        'licenses': C.collect_licenses,
        'environment': C.collect_environment,
        'network_info': C.collect_network_info,
        'printers': C.collect_printers,
        'autoruns': C.collect_autoruns,
        'accessibility': C.collect_accessibility,
        'drivers': C.collect_drivers,
        'codecs': C.collect_codecs,
        'snapins': C.collect_snapins,
        'sensors': C.collect_sensors,
        'devices': C.collect_devices,
        'pci': C.collect_pci,
        'slots': C.collect_slots,
        'ports': C.collect_ports,
        'virtual_machine': C.collect_virtual_machine,
    }
    selected = {k:v for k,v in tasks.items() if options.get(k, True)}
    results = {}
    errors = {}
    total = len(selected)
    completed = 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futmap = {ex.submit(func): name for name, func in selected.items()}
        for fut in cf.as_completed(futmap, timeout=None):
            name = futmap[fut]
            try:
                # Raise per-collector timeout floor to 12s
                results[name] = fut.result(timeout=12)
            except Exception as e:
                errors[name] = str(e)
                # Tag partial status in result placeholder
                results[name] = {"status":"partial","error":str(e)}
            completed += 1
            if progress_cb:
                try:
                    progress_cb(name, completed, total)
                except Exception:
                    pass
    meta = {
        'generated_at': datetime.datetime.now().isoformat(),
        'machine': os.environ.get('COMPUTERNAME','')
    }
    return meta, results, errors


