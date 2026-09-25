"""Building blocks shared by every PC report section.

A section module exposes one ``SECTION`` object (see ``Section``). Its
``collect`` receives a ``SectionContext`` and returns JSON-able data; the
orchestrator wraps that as ``{"data": ..., "notes": [...]}``. Its ``render``
receives the unwrapped data and a ``RenderContext`` and returns an HTML
fragment built from the table helpers below.
"""
# ruff: noqa: UP035, UP037
from __future__ import annotations

import ctypes
import html as _html
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

REQUIRES_ADMIN = "__requires_admin__"
GROUPS: tuple[str, ...] = ("NVC", "Software", "Hardware", "Network")
NO_DATA = "<em>No data</em>"
CELL_LIMIT = 512


def is_user_admin() -> bool:
    """True when the process runs elevated. False on any failure or off Windows."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


class SharedSources:
    """Memoises expensive sources (dxdiag, the PnP dump) across sections in one run.

    ``loaders`` maps a name to a zero-argument callable returning
    ``(value, error)``. The first caller pays; later callers get the cached
    pair. A loader that raises is recorded as ``(None, str(exc))``.
    """

    def __init__(self, loaders: dict[str, Callable[[], tuple[Any, str | None]]]):
        self._loaders = dict(loaders)
        self._cache: dict[str, tuple[Any, str | None]] = {}
        self._lock = threading.Lock()
        self.calls: dict[str, int] = {}

    def get(self, name: str) -> tuple[Any, str | None]:
        with self._lock:
            if name not in self._cache:
                loader = self._loaders.get(name)
                if loader is None:
                    self._cache[name] = (None, f"unknown shared source {name!r}")
                else:
                    self.calls[name] = self.calls.get(name, 0) + 1
                    try:
                        self._cache[name] = loader()
                    except Exception as exc:  # a shared source must never sink its consumers
                        self._cache[name] = (None, str(exc))
            return self._cache[name]


@dataclass
class RunContext:
    """State shared by every section during one ``run_all``, including completed timings."""
    options: dict
    is_admin: bool
    results: dict
    shared: SharedSources
    runner: Callable[[str, int], tuple[Any, str | None]]
    text_runner: Callable[[list[str], int], tuple[str, str | None]]
    elapsed: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    group: str
    collect: Callable[["SectionContext"], Any]
    render: Callable[[Any, "RenderContext"], str]
    timeout: int = 30
    default_on: bool = True
    after: tuple[str, ...] = ()


class SectionContext:
    """What one section's ``collect`` receives.

    Every query is named so fixtures can be recorded and replayed by name,
    and so a failing query produces a readable note.
    """

    def __init__(self, run: RunContext, section: Section):
        self.run = run
        self.section = section
        self.notes: list[str] = []

    @property
    def is_admin(self) -> bool:
        return self.run.is_admin

    @property
    def options(self) -> dict:
        return self.run.options

    def note(self, text: str) -> None:
        self.notes.append(text)

    def query(self, name: str, script: str, timeout: int | None = None):
        data, error = self.run.runner(script, timeout or self.section.timeout)
        if error:
            self.note(f"{name}: {error}")
        return data

    def text(self, name: str, args: list[str], timeout: int | None = None) -> str:
        out, error = self.run.text_runner(list(args), timeout or self.section.timeout)
        if error:
            self.note(f"{name}: {error}")
        return out or ""

    def admin_query(self, name: str, script: str, timeout: int | None = None):
        if not self.is_admin:
            self.note(f"{name}: requires administrator")
            return REQUIRES_ADMIN
        return self.query(name, script, timeout)

    def shared(self, name: str):
        value, error = self.run.shared.get(name)
        if error:
            self.note(f"{name}: {error}")
        return value

    def result(self, key: str):
        return section_data(self.run.results.get(key))


@dataclass
class RenderContext:
    redact: bool = True
    meta: dict = field(default_factory=dict)


# --- result shape ----------------------------------------------------------

def wrap(data, notes) -> dict:
    return {"data": data, "notes": list(notes)}


def is_partial(result) -> bool:
    return isinstance(result, dict) and result.get("status") == "partial"


def section_data(result):
    if result is None or is_partial(result):
        return None
    if isinstance(result, dict) and set(result) == {"data", "notes"}:
        return result["data"]
    return result


def section_notes(result) -> list[str]:
    if isinstance(result, dict) and isinstance(result.get("notes"), list):
        return [str(n) for n in result["notes"]]
    return []


# --- data shaping ----------------------------------------------------------

def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def rows_of(value) -> list[dict]:
    return [row for row in as_list(value) if isinstance(row, dict)]


def first_dict(value) -> dict:
    for item in as_list(value):
        if isinstance(item, dict):
            return item
    return {}


# --- HTML ------------------------------------------------------------------

def esc(value) -> str:
    return _html.escape("" if value is None else str(value))


def render_value(value) -> str:
    if value is None:
        return ""
    if value == REQUIRES_ADMIN:
        return '<span class="warn">Requires administrator</span>'
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return esc(", ".join("" if v is None else str(v) for v in value))
    if isinstance(value, dict):
        return esc("; ".join(f"{k}: {v}" for k, v in value.items()))
    text = str(value)
    if len(text) > CELL_LIMIT:
        return (esc(text[:CELL_LIMIT]) + "…<details><summary>Show more</summary><pre>"
                + esc(text) + "</pre></details>")
    return esc(text)


def kv_table(rows) -> str:
    """rows: iterable of (label, value). (label, None) renders as a sub-heading row."""
    rows = list(rows)
    if not rows:
        return NO_DATA
    out = ['<table class="kv">']
    for label, value in rows:
        if value is None:
            out.append(f'<tr class="sub"><th colspan="2">{esc(label)}</th></tr>')
        else:
            out.append(f"<tr><th>{esc(label)}</th><td>{render_value(value)}</td></tr>")
    out.append("</table>")
    return "".join(out)


def _pairs_of(rows) -> list[tuple]:
    """Every (key, value) pair in ``rows``. Malformed entries are skipped, not raised on."""
    pairs = []
    for entry in as_list(rows):
        if isinstance(entry, str):
            continue
        try:
            pair = tuple(entry)
        except TypeError:
            continue
        if len(pair) == 2:
            pairs.append(pair)
    return pairs


def kv_groups(groups) -> str:
    """groups: list of {"title": str, "rows": dict | list of pairs}. Empty groups are skipped.

    A ``None`` value inside ``rows`` renders as a blank cell, not a sub-heading.
    """
    rows = []
    for group in as_list(groups):
        if not isinstance(group, dict):
            continue
        grows = group.get("rows") or {}
        pairs = list(grows.items()) if isinstance(grows, dict) else _pairs_of(grows)
        pairs = [(k, "" if v is None else v) for k, v in pairs]
        if not pairs:
            continue
        if group.get("title"):
            rows.append((group["title"], None))
        rows.extend(pairs)
    return kv_table(rows)


def list_table(columns, rows) -> str:
    """columns: list of (key, label); rows: list of dicts. Missing keys render blank."""
    rows = rows_of(rows)
    if not rows:
        return NO_DATA
    head = "".join(f"<th>{esc(label)}</th>" for _key, label in columns)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{render_value(row.get(key))}</td>"
                                     for key, _label in columns) + "</tr>")
    return (f'<table class="list"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def sub_heading(text) -> str:
    return f"<h3>{esc(text)}</h3>"


def notes_block(notes) -> str:
    notes = [n for n in as_list(notes) if n]
    if not notes:
        return ""
    return '<p class="notes"><em>' + "<br>".join(esc(n) for n in notes) + "</em></p>"
