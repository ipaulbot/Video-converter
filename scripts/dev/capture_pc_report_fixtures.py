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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pc_report import ps, registry  # noqa: E402
from pc_report.privacy import redact_payload  # noqa: E402
from pc_report.section import RunContext, SharedSources, is_user_admin, wrap  # noqa: E402
from tests.pc_report.support import FIXTURES, RecordingSectionContext  # noqa: E402


def make_scrub():
    replacements = []
    for value, token in (
        (os.environ.get("COMPUTERNAME"), "PC-NAME"),
        (getpass.getuser(), "user"),
        (os.environ.get("USERDNSDOMAIN"), "example.local"),
        (os.environ.get("USERDOMAIN"), "WORKGROUP"),
    ):
        if value and len(value) >= 3 and value.upper() != "WORKGROUP":
            replacements.append((re.compile(re.escape(value), re.IGNORECASE), token))

    def scrub(text: str) -> str:
        for pattern, token in replacements:
            text = pattern.sub(token, text)
        return text

    return scrub


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
    # Sections that read others' results go last so their inputs exist.
    sections.sort(key=lambda s: (bool(s.after), registry.ORDER.index(s.key)))

    run = RunContext(options={}, is_admin=is_user_admin(), results={},
                     shared=SharedSources(ps.SHARED_LOADERS),
                     runner=ps.run_ps_json, text_runner=ps.run_text)
    scrub = make_scrub()
    redact = lambda value: redact_payload(value, {"redact": True})  # noqa: E731
    print(f"elevated: {run.is_admin}; writing to {args.out}")
    for section in sections:
        ctx = RecordingSectionContext(run, section, Path(args.out), redact, scrub)
        started = time.monotonic()
        try:
            data = section.collect(ctx)
        except Exception as exc:  # keep capturing the rest
            print(f"{section.key}: FAILED {exc}")
            continue
        run.results[section.key] = wrap(data, ctx.notes)
        print(f"{section.key}: {time.monotonic() - started:.1f} s, {len(ctx.notes)} note(s)")
        for note in ctx.notes:
            print(f"   - {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
