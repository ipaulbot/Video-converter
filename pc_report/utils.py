import json, subprocess, os, sys

def run_ps_json(script: str, timeout: int = 15):
    # On Windows, use powershell.exe with hidden window
    cmd = [
        'powershell',
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        script + ' | ConvertTo-Json -Depth 6',
    ]
    try:
        # Raise sane timeout floor (12s) to avoid partial/empty data on slow machines
        eff_timeout = max(timeout, 12)
        kwargs = dict(capture_output=True, text=True, timeout=eff_timeout)
        if os.name == 'nt':
            # CREATE_NO_WINDOW to avoid flashing consoles in frozen apps
            kwargs['creationflags'] = 0x08000000  # subprocess.CREATE_NO_WINDOW
            # In PyInstaller frozen exe, explicitly set shell=False
            kwargs['shell'] = False
        cp = subprocess.run(cmd, **kwargs)
        if cp.returncode != 0:
            return None, cp.stderr
        if not cp.stdout:
            return None, None
        try:
            return json.loads(cp.stdout), None
        except Exception as e:
            return None, f'JSON parse error: {e}'
    except Exception as e:
        return None, str(e)

def bytes_human(n):
    try:
        n = int(n)
    except Exception:
        return n
    units = ['B','KB','MB','GB','TB']
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024
        i += 1
    return f"{f:.1f} {units[i]}"

def bitrate_to_mbps(n):
    try:
        n = int(n)
    except Exception:
        return 'Unknown'
    if n <= 0 or n >= 9_000_000_000_000_000_000:
        return 'Unknown'
    return f"{n/1_000_000:.1f} Mbps"


