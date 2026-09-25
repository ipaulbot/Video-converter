"""The PC report page: header, grouped contents, Report Health and every section in registry order."""
from __future__ import annotations

import base64
import os

from utils.logger import logger
from utils.resources import resource_path

from . import registry
from .format import duration
from .privacy import redact_meta, redact_payload
from .section import GROUPS, NO_DATA, RenderContext, esc, is_partial, kv_table, notes_block, section_data, section_notes

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:20px;color:#222;background:#fff}
h1{border-bottom:2px solid #43a296;padding-bottom:6px;margin-top:0;font-size:26px}
h2{font-size:18pt;margin:28px 0 4px;border-bottom:1px solid #d6eae5}
h3{font-size:12pt;margin:14px 0 4px;color:#2f6f66}
.logo{height:64px;vertical-align:middle;margin-right:12px}
.meta{color:#555;margin:0 0 12px}
.group{background:#eaf5f3;border:1px solid #b9dcd5;text-align:center;font-size:20px;font-weight:bold;padding:6px;margin-top:36px}
.toc{display:flex;gap:24px;border:1px solid #b9dcd5;padding:10px;margin:12px 0 20px}
.toc-col{flex:1}.toc h3{margin:0 0 6px}.toc ul{margin:0;padding-left:18px}.toc li{margin:2px 0}
table{border-collapse:collapse;width:100%;margin:6px 0 10px}
table.kv th{text-align:left;background:#f3f7f6;padding:5px 8px;border:1px solid #e0e0e0;width:33%;font-weight:normal}
table.kv td{padding:5px 8px;border:1px solid #e0e0e0}
table.kv tr.sub th{background:#cfe8e3;font-weight:bold;color:#1f4f48}
table.list th{background:#cfe8e3;text-align:left;border:1px solid #d6eae5;padding:5px 8px;position:sticky;top:0}
table.list td{border:1px solid #f0f0f0;padding:4px 8px;word-break:break-word;vertical-align:top}
tr:nth-child(even) td{background:#fafafa}
tr:hover td{background:#e8f4f1}
a{color:#2f7d72;text-decoration:none}a:hover{text-decoration:underline}
.top{float:right;font-size:11px;color:#3a8f82;font-weight:normal}
.warn{color:#9a6200}.bad{color:#b00020;font-weight:bold}.ok{color:#1f7a4d;font-weight:600}
.notes{color:#666;font-size:12px;margin:4px 0 0}
pre{max-height:240px;overflow:auto;white-space:pre-wrap;margin:4px 0}
details summary{cursor:pointer;color:#2f7d72}
"""


def _logo_tag() -> str:
    try:
        logo_path = resource_path("graphics/PCREPORT.png")
        if logo_path and os.path.exists(logo_path):
            with open(logo_path, "rb") as handle:
                b64 = base64.b64encode(handle.read()).decode("ascii")
            return f"<img src='data:image/png;base64,{b64}' alt='PC Report' class='logo'>"
    except OSError:
        logger.debug("render_html: logo unavailable", exc_info=True)
    return ""


def _h2(title: str, anchor: str) -> str:
    return f'<h2 id="{esc(anchor)}">{esc(title)}<a href="#top" class="top">Top ▲</a></h2>'


def _banner(group: str) -> str:
    return f'<div class="group" id="g-{esc(group)}">{esc(group)}</div>'


def _section_body(section, result, ctx: RenderContext) -> str:
    if is_partial(result):
        return f'<p class="bad">This section failed: {esc(result.get("error"))}</p>'
    try:
        body = section.render(section_data(result), ctx)
    except Exception:
        logger.exception("PC report: rendering %s failed", section.key)
        body = '<p class="bad">Could not render this section.</p>'
    return (body or NO_DATA) + notes_block(section_notes(result))


def is_empty_body(body: str) -> bool:
    """True when a rendered section shows no data at all (a 'No data' marker and no data cells).

    Sections with an empty optional subsection (e.g. no optical drive) are not empty.
    """
    return NO_DATA in body and "<td" not in body


def _report_health(meta: dict, data: dict, rendered, redact: bool) -> str:
    titles = {s.key: s.title for s, _a, _b in rendered}
    partial = [s.title for s, _a, _b in rendered if is_partial(data.get(s.key))]
    noted = [s.title for s, _a, _b in rendered if section_notes(data.get(s.key))]
    empty = [s.title for s, _a, body in rendered if is_empty_body(body)]
    elapsed = meta.get("elapsed_by_section") or {}
    timings = []
    for key, value in (elapsed.items() if isinstance(elapsed, dict) else ()):
        try:
            timings.append((key, float(value)))
        except (TypeError, ValueError):
            continue
    slowest = sorted(timings, key=lambda kv: kv[1], reverse=True)[:3]

    def counted(items):
        return f"{len(items)}" + (f": {', '.join(items)}" if items else "")

    rows = [
        ("Redaction", "Enabled" if redact else "Disabled"),
        ("Elevated (administrator)", "Yes" if meta.get("elevated") else "No"),
        ("Sections collected", str(len(rendered))),
        ("Partial sections", ", ".join(partial) if partial else "None"),
        ("Sections with notes", counted(noted)),
        ("Empty sections", counted(empty)),
        ("Total collection time", duration(meta.get("total_seconds")) or "Unknown"),
        ("Slowest sections", ", ".join(f"{titles.get(k, k)} ({v:.1f} s)" for k, v in slowest) or "Unknown"),
    ]
    html = kv_table(rows)
    if partial:
        html += f'<p class="bad">{len(partial)} section(s) failed to collect; see their entries below.</p>'
    if not meta.get("elevated"):
        html += ('<p class="warn">Run NVC as administrator to fill in the fields marked '
                 '"Requires administrator".</p>')
    return html


def _contents(rendered) -> str:
    groups: dict[str, list[tuple[str, str]]] = {g: [] for g in GROUPS}
    for section, anchor, _body in rendered:
        groups.setdefault(section.group, []).append((section.title, anchor))
    groups["NVC"].insert(0, ("Report Health", "s-report_health"))
    columns = []
    for group in GROUPS:
        items = groups.get(group) or []
        if not items:
            continue
        links = "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for t, a in items)
        columns.append(f'<div class="toc-col"><h3><a href="#g-{esc(group)}">{esc(group)}</a></h3><ul>{links}</ul></div>')
    return '<div class="toc">' + "".join(columns) + "</div>"


def render(meta, data, options):
    options = options or {}
    redact = options.get("redact", True)
    meta = redact_meta(meta, options)
    data = redact_payload(data or {}, options) if redact else (data or {})
    ctx = RenderContext(redact=redact, meta=meta)

    present = [s for s in registry.SECTIONS if s.key in data]
    rendered = [(s, f"s-{s.key}", _section_body(s, data[s.key], ctx)) for s in present]

    parts = [_banner("NVC"), _h2("Report Health", "s-report_health"), _report_health(meta, data, rendered, redact)]
    current_group = "NVC"
    for section, anchor, body in rendered:
        if section.group != current_group:
            current_group = section.group
            parts.append(_banner(current_group))
        parts.append(_h2(section.title, anchor))
        parts.append(body)

    machine = meta.get("machine", "")
    version = meta.get("nvc_version", "")
    header = (f"<h1>{_logo_tag()}NVC PC Report</h1>"
              f"<p class='meta'>Machine: {esc(machine)} &middot; Generated: {esc(meta.get('generated_at', ''))}"
              f" &middot; NVC {esc(version)} &middot; Elevated: {'Yes' if meta.get('elevated') else 'No'}</p>")

    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        f"<title>NVC PC Report - {esc(machine)}</title><style>{CSS}</style></head>\n"
        f"<body><a id=\"top\"></a>{header}{_contents(rendered)}{''.join(parts)}</body></html>\n"
    )
