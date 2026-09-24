"""System Directories: every Environment.SpecialFolder plus the core environment folders."""
from __future__ import annotations

import os
import re

from ..section import Section, list_table, rows_of

SCRIPT = r"""
[Enum]::GetNames([System.Environment+SpecialFolder]) | Sort-Object -Unique | ForEach-Object {
  $p = [Environment]::GetFolderPath($_)
  if ($p) { [pscustomobject]@{ Name = [string]$_; Path = [string]$p } }
}
"""

ENV_DIRS = ("SystemRoot", "SystemDrive", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432",
            "ProgramData", "CommonProgramFiles", "CommonProgramFiles(x86)", "PUBLIC", "TEMP", "TMP", "windir")

COLUMNS = [("Name", "Name"), ("Path", "Path"), ("Source", "Source")]

_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=X86)")


def humanise(name: str) -> str:
    return _CAMEL.sub(" ", str(name))


def build(folders, env: dict) -> dict:
    rows = [{"Name": humanise(k), "Path": env[k], "Source": "Environment"} for k in ENV_DIRS if env.get(k)]
    rows += [{"Name": humanise(r.get("Name", "")), "Path": r.get("Path", ""), "Source": "Shell folder"}
             for r in rows_of(folders)]
    return {"rows": rows}


def collect(ctx):
    return build(ctx.query("folders", SCRIPT), dict(os.environ))


def render(data, ctx):
    return list_table(COLUMNS, (data or {}).get("rows") if isinstance(data, dict) else None)


SECTION = Section(key="system_directories", title="System Directories", group="Software",
                  collect=collect, render=render)
