"""Licenses: Windows product ID, OEM key and every licensed product. All keys are masked by redaction."""
from __future__ import annotations

from .. import decode
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
$o = [ordered]@{}
$o.ProductId = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue).ProductId
$svc = Get-CimInstance SoftwareLicensingService -ErrorAction SilentlyContinue
$o.OA3xOriginalProductKey = [string]$svc.OA3xOriginalProductKey
$o.OA3xOriginalProductKeyDescription = [string]$svc.OA3xOriginalProductKeyDescription
$o.KeyManagementServiceMachine = [string]$svc.KeyManagementServiceMachine
$o.Products = @(Get-CimInstance SoftwareLicensingProduct -ErrorAction SilentlyContinue -Filter "PartialProductKey IS NOT NULL" |
  Select-Object Name,Description,LicenseStatus,PartialProductKey,ProductKeyChannel,LicenseFamily,GracePeriodRemaining)
[pscustomobject]$o
"""

COLUMNS = [("Product", "Product"), ("Description", "Description"), ("Status", "Status"),
           ("Channel", "Channel"), ("Partial Product Key", "Partial Product Key"), ("Family", "Family")]


def build(raw: dict) -> dict:
    raw = raw or {}
    summary = {
        "Windows Product ID": raw.get("ProductId", ""),
        "OEM Original Product Key": raw.get("OA3xOriginalProductKey", ""),
        "OEM Key Description": raw.get("OA3xOriginalProductKeyDescription", ""),
        "KMS Host Name": raw.get("KeyManagementServiceMachine", ""),
    }
    products = [{
        "Product": p.get("Name", ""), "Description": p.get("Description", ""),
        "Status": decode.lookup(decode.LICENSE_STATUS, p.get("LicenseStatus")),
        "Channel": p.get("ProductKeyChannel", ""), "Partial Product Key": p.get("PartialProductKey", ""),
        "Family": p.get("LicenseFamily", ""),
    } for p in rows_of(raw.get("Products"))]
    return {"groups": [{"title": "Windows", "rows": summary}], "products": products}


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Licensed products") + list_table(COLUMNS, data.get("products"))


def collect(ctx):
    return build(first_dict(ctx.query("licensing", SCRIPT, timeout=45)))


SECTION = Section(key="licenses", title="Licenses", group="Software", collect=collect, render=render, timeout=45)
