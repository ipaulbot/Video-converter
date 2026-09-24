"""Compatibility shims. New code imports from pc_report.ps and pc_report.format."""
from .format import bitrate_to_mbps, bytes_human  # noqa: F401
from .ps import run_ps_json  # noqa: F401
