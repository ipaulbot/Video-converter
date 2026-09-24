"""Environment: variables in Machine, User and Process scope. Redaction masks USERNAME-style values."""
from __future__ import annotations

from ..section import Section, list_table, rows_of, sub_heading

SCRIPT = r"""
foreach ($scope in 'Machine','User','Process') {
  $vars = [Environment]::GetEnvironmentVariables($scope)
  foreach ($k in ($vars.Keys | Sort-Object)) {
    [pscustomobject]@{ Scope = $scope; Name = [string]$k; Value = [string]$vars[$k] }
  }
}
"""

SCOPES = ("Machine", "User", "Process")
COLUMNS = [("Name", "Name"), ("Value", "Value")]


def build(variables) -> dict:
    out = {scope: [] for scope in SCOPES}
    for row in rows_of(variables):
        scope = row.get("Scope") if row.get("Scope") in SCOPES else "Process"
        out[scope].append({"Name": row.get("Name", ""), "Value": row.get("Value", "")})
    return out


def collect(ctx):
    return build(ctx.query("variables", SCRIPT))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return "".join(sub_heading(scope) + list_table(COLUMNS, data.get(scope)) for scope in SCOPES)


SECTION = Section(key="environment", title="Environment", group="Software", collect=collect, render=render)
