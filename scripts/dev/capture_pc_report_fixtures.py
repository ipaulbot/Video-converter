"""Record redacted PC report fixtures from this machine.

Usage:
    python scripts/dev/capture_pc_report_fixtures.py                  # every section
    python scripts/dev/capture_pc_report_fixtures.py --section cpu memory
    python scripts/dev/capture_pc_report_fixtures.py --out D:\\tmp\\fixtures

Each named query a section issues is written to
tests/fixtures/pc_report/<section>/<query>.json after redact_payload and a
scrub that replaces this machine's name, user name and domain. Review the
files before committing them anyway. Run once elevated to record the
admin-only queries too.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import time
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pc_report import ps, registry  # noqa: E402
from pc_report.privacy import redact_payload  # noqa: E402
from pc_report.section import RunContext, Section, SharedSources, is_user_admin, wrap  # noqa: E402
from tests.pc_report.support import FIXTURES, RecordingSectionContext  # noqa: E402

ScrubValue = tuple[str | None, str, str]


def _default_scrub_values() -> list[ScrubValue]:
    return [
        (os.environ.get("COMPUTERNAME"), "PC-NAME", "COMPUTERNAME"),
        (getpass.getuser(), "user", "user"),
        (os.environ.get("USERDNSDOMAIN"), "example.local", "USERDNSDOMAIN"),
        (os.environ.get("USERDOMAIN"), "WORKGROUP", "USERDOMAIN"),
    ]


def make_scrub(values: Iterable[ScrubValue] | None = None):
    if values is None:
        values = _default_scrub_values()
    replacements = []
    for value, token, _label in values:
        if not value:
            continue
        if value.upper() == "WORKGROUP":
            continue
        pattern = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
        replacements.append((pattern, token))

    def scrub(text: str) -> str:
        for pattern, token in replacements:
            text = pattern.sub(token, text)
        return text

    return scrub


def dependency_depth(
    section: Section,
    by_key: dict[str, Section],
    memo: dict[str, int] | None = None,
) -> int:
    memo = {} if memo is None else memo
    visiting: set[str] = set()

    def depth(key: str) -> int:
        if key in memo:
            return memo[key]
        if key in visiting:
            return 0
        current = by_key[key]
        if not current.after:
            memo[key] = 0
            return 0

        visiting.add(key)
        try:
            result = 1 + max((depth(dep) for dep in current.after if dep in by_key), default=0)
        finally:
            visiting.remove(key)
        memo[key] = result
        return result

    return depth(section.key)


def sort_sections(sections: list[Section], order: tuple[str, ...] | None = None) -> list[Section]:
    order = registry.ORDER if order is None else order
    by_key = {s.key: s for s in sections}
    order_index = {key: idx for idx, key in enumerate(order)}
    depth_memo: dict[str, int] = {}

    def sort_key(section: Section) -> tuple[int, int]:
        return (dependency_depth(section, by_key, depth_memo), order_index.get(section.key, len(order)))

    return sorted(sections, key=sort_key)


def capture(sections: list[Section], run: RunContext, out: Path, redact, scrub) -> list[str]:
    failed: list[str] = []
    for section in sections:
        ctx = RecordingSectionContext(run, section, out, redact, scrub)
        started = time.monotonic()
        try:
            data = section.collect(ctx)
        except Exception as exc:  # keep capturing the rest
            print(f"{section.key}: FAILED {exc}")
            failed.append(section.key)
            continue
        run.results[section.key] = wrap(data, ctx.notes)
        print(f"{section.key}: {time.monotonic() - started:.1f} s, {len(ctx.notes)} note(s)")
        for note in ctx.notes:
            print(f"   - {note}")
    return failed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--section", nargs="*", default=[], help="section keys; default is every section")
    parser.add_argument("--out", default=str(FIXTURES), help="fixture root")
    args = parser.parse_args(argv)

    if args.section:
        sections = []
        for key in args.section:
            section = registry.by_key(key)
            if section is None:
                parser.error(f"unknown section {key!r}; known: {', '.join(s.key for s in registry.SECTIONS)}")
            sections.append(section)
    else:
        sections = list(registry.SECTIONS)
    sections = sort_sections(sections)

    run = RunContext(options={}, is_admin=is_user_admin(), results={},
                     shared=SharedSources(ps.SHARED_LOADERS),
                     runner=ps.run_ps_json, text_runner=ps.run_text)
    scrub = make_scrub()
    redact = lambda value: redact_payload(value, {"redact": True})  # noqa: E731
    print(f"elevated: {run.is_admin}; writing to {args.out}")
    failed = capture(sections, run, Path(args.out), redact, scrub)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
