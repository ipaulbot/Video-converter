"""PowerShell and command-line plumbing for the PC report.

Everything the sections need to reach Windows goes through here, so tests can
replace two functions (``run_ps_json`` and ``run_text``) and never spawn a
process.
"""
# ruff: noqa: C408
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

CREATE_NO_WINDOW = 0x08000000

_PREAMBLE = (
    "$ErrorActionPreference='Continue'; $WarningPreference='SilentlyContinue'; "
    "$ProgressPreference='SilentlyContinue'; "
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
)


def _run_kwargs(timeout):
    kwargs = dict(capture_output=True, text=True, timeout=timeout,
                  encoding="utf-8", errors="replace")
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        kwargs["shell"] = False
    return kwargs


def run_ps_json(script: str, timeout: int = 15):
    """Run a PowerShell snippet and parse its ConvertTo-Json output.

    Returns ``(data, error)`` and never raises. The snippet is wrapped in a
    scriptblock so multi-statement scripts pipe all their output.
    """
    eff_timeout = max(timeout, 12)
    cmd = [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
        _PREAMBLE + "& { " + script + " } | ConvertTo-Json -Depth 6 -Compress -WarningAction SilentlyContinue",
    ]
    try:
        cp = subprocess.run(cmd, **_run_kwargs(eff_timeout))
    except subprocess.TimeoutExpired:
        return None, f"timed out after {eff_timeout} s"
    except Exception as e:
        return None, str(e)
    if cp.returncode != 0:
        return None, (cp.stderr or f"exit code {cp.returncode}").strip()[:500]
    if not cp.stdout or not cp.stdout.strip():
        return None, None
    try:
        return json.loads(cp.stdout), None
    except Exception as e:
        return None, f"JSON parse error: {e}"


def run_text(args: list[str], timeout: int = 15) -> tuple[str, str | None]:
    """Run a command line (netsh, powercfg, ...) and return ``(stdout, error)``."""
    try:
        cp = subprocess.run(list(args), **_run_kwargs(max(timeout, 5)))
    except subprocess.TimeoutExpired:
        return "", f"timed out after {timeout} s"
    except Exception as e:
        return "", str(e)
    if cp.returncode != 0 and not cp.stdout:
        return "", (cp.stderr or f"exit code {cp.returncode}").strip()[:500]
    return cp.stdout or "", None


def ps_quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def cim(class_name: str, props=None, namespace: str | None = None, where: str | None = None) -> str:
    parts = ["Get-CimInstance", "-ClassName", class_name, "-ErrorAction", "SilentlyContinue"]
    if namespace:
        parts += ["-Namespace", ps_quote(namespace)]
    if where:
        parts += ["-Filter", ps_quote(where)]
    script = " ".join(parts)
    if props:
        script += " | Select-Object " + ",".join(props)
    return script


def reg_props(path: str) -> str:
    """Script returning ``[{Name, Value}]`` for every value under a registry key."""
    return (
        f"$p = Get-ItemProperty -Path {ps_quote(path)} -ErrorAction SilentlyContinue; "
        "if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notmatch "
        "'^(PSPath|PSParentPath|PSChildName|PSDrive|PSProvider)$' } | ForEach-Object { "
        "[pscustomobject]@{ Name = [string]$_.Name; Value = [string]$_.Value } } }"
    )


# --- shared sources ----------------------------------------------------------

def _etree_to_dict(node):
    children = list(node)
    if not children:
        return (node.text or "").strip()
    out: dict = {}
    for child in children:
        value = _etree_to_dict(child)
        if child.tag in out:
            if not isinstance(out[child.tag], list):
                out[child.tag] = [out[child.tag]]
            out[child.tag].append(value)
        else:
            out[child.tag] = value
    return out


def dxdiag_xml(timeout: int = 90):
    """Run ``dxdiag /whql:off /x`` and return ``(dict, error)``. Slow but rich."""
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "dxdiag.exe")
    fd, path = tempfile.mkstemp(suffix=".xml", prefix="nvc_dxdiag_")
    os.close(fd)
    try:
        os.remove(path)
        cp = subprocess.run([exe, "/whql:off", "/x", path], **_run_kwargs(timeout))
        if not os.path.exists(path):
            return None, (cp.stderr or "dxdiag produced no output").strip()[:200]
        return _etree_to_dict(ET.parse(path).getroot()), None
    except subprocess.TimeoutExpired:
        return None, f"dxdiag timed out after {timeout} s"
    except Exception as e:
        return None, f"dxdiag failed: {e}"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def dx_list(dx, container: str, item: str) -> list[dict]:
    """Items under e.g. ``('DisplayDevices', 'DisplayDevice')`` as a list of dicts."""
    if not isinstance(dx, dict):
        return []
    block = dx.get(container)
    if not isinstance(block, dict):
        return []
    value = block.get(item)
    if value is None:
        return []
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, dict)]


PNP_PROPS = ("Name", "Manufacturer", "PNPClass", "ClassGuid", "DeviceID", "PNPDeviceID",
             "Status", "ConfigManagerErrorCode", "Service", "Present", "Description")


def pnp_entities(timeout: int = 60):
    return run_ps_json(cim("Win32_PnPEntity", PNP_PROPS) + " | Sort-Object PNPClass, Name", timeout)


SHARED_LOADERS = {"dxdiag": dxdiag_xml, "pnp_entities": pnp_entities}
