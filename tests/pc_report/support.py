"""Fixture-backed contexts so section tests never spawn PowerShell or dxdiag."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pc_report.privacy import redact_payload
from pc_report.section import REQUIRES_ADMIN, RenderContext, RunContext, SectionContext, SharedSources, is_partial

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pc_report"
SHARED_DIR = "_shared"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def scrub_values(obj, scrub):
    if isinstance(obj, dict):
        return {key: scrub_values(value, scrub) for key, value in obj.items()}
    if isinstance(obj, list):
        return [scrub_values(value, scrub) for value in obj]
    if isinstance(obj, str):
        return scrub(obj)
    return obj


def _refuse(*_args, **_kwargs):
    raise AssertionError("a section test tried to run a real command; add a fixture instead")


class FixtureSectionContext(SectionContext):
    """Serves recorded results by query name from ``<root>/<section>/<name>.json|.txt``."""

    def __init__(self, section, is_admin=False, results=None, root: Path = FIXTURES):
        run = RunContext(options={}, is_admin=is_admin, results=results or {},
                         shared=SharedSources({}), runner=_refuse, text_runner=_refuse)
        super().__init__(run, section)
        self.dir = Path(root) / section.key
        self.shared_dir = Path(root) / SHARED_DIR
        self.requested: list[str] = []

    def _load(self, directory: Path, name: str, suffix: str):
        self.requested.append(name)
        path = directory / f"{safe_name(name)}{suffix}"
        if not path.exists():
            self.note(f"{name}: no fixture {path.name}")
            return None
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if suffix == ".json" else text

    def query(self, name, script, timeout=None):
        return self._load(self.dir, name, ".json")

    def text(self, name, args, timeout=None):
        return self._load(self.dir, name, ".txt") or ""

    def admin_query(self, name, script, timeout=None):
        if not self.is_admin:
            self.note(f"{name}: requires administrator")
            return REQUIRES_ADMIN
        return self.query(name, script, timeout)

    def shared(self, name):
        return self._load(self.shared_dir, name, ".json")


class RecordingSectionContext(SectionContext):
    """Runs real queries and writes each result to the fixture folder, redacted and scrubbed.

    Admin-only queries are recorded only when the capture itself runs elevated.
    """

    def __init__(self, run, section, root: Path, redact, scrub):
        super().__init__(run, section)
        self.dir = Path(root) / section.key
        self.shared_dir = Path(root) / SHARED_DIR
        self.redact = redact
        self.scrub = scrub

    def _save(self, directory: Path, name: str, value, suffix: str):
        directory.mkdir(parents=True, exist_ok=True)
        if suffix == ".json":
            value = scrub_values(self.redact(value), self.scrub)
            text = json.dumps(value, indent=1, default=str)
        else:
            text = self.scrub(value or "")
        (directory / f"{safe_name(name)}{suffix}").write_text(text, encoding="utf-8")

    def query(self, name, script, timeout=None):
        data = super().query(name, script, timeout)
        self._save(self.dir, name, data, ".json")
        return data

    def text(self, name, args, timeout=None):
        out = super().text(name, args, timeout)
        self._save(self.dir, name, out, ".txt")
        return out

    def shared(self, name):
        value = super().shared(name)
        self._save(self.shared_dir, name, value, ".json")
        return value


def render_ctx(redact=True, meta=None) -> RenderContext:
    return RenderContext(redact=redact, meta=meta or {})


def assert_renders_empty(testcase, section):
    """Every render must tolerate nothing, an empty dict, an empty list and a partial placeholder."""
    ctx = render_ctx()
    for payload in ({}, None, [], {"status": "partial", "error": "x"}):
        out = section.render(None if is_partial(payload) else payload, ctx)
        testcase.assertIsInstance(out, str, f"{section.key} render returned non-str for {payload!r}")


def collect_and_render(section, is_admin=False, results=None, root: Path = FIXTURES):
    """Collect from fixtures, redact, render; return ``(data, html, ctx)``."""
    ctx = FixtureSectionContext(section, is_admin=is_admin, results=results, root=root)
    data = section.collect(ctx)
    html = section.render(redact_payload(data, {"redact": True}), render_ctx())
    return data, html, ctx
