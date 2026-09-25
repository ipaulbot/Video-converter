"""Runs every enabled section and assembles ``(meta, results, errors)``.

Sections without dependencies run first on a thread pool; a section that
names ``after`` keys is submitted once those have finished. A section that
raises becomes ``{"status": "partial", "error": ...}`` so the report still
renders. The only real time bound is the subprocess timeout inside each
query; see pc_report.ps.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime
import os
import time

from utils.logger import logger
from utils.version import APP_VERSION

from . import ps, registry
from .section import RunContext, SectionContext, SharedSources, is_user_admin, wrap

MAX_WORKERS = 6


def _collect_one(run: RunContext, section):
    started = time.monotonic()
    try:
        ctx = SectionContext(run, section)
        data = section.collect(ctx)
        return wrap(data, ctx.notes), None, time.monotonic() - started
    except Exception as exc:
        return None, exc, time.monotonic() - started


def run_all(options: dict, progress_cb=None, sections=None, runner=None, text_runner=None,
            shared_loaders=None, is_admin=None):
    options = options or {}
    selected = registry.select(options, sections if sections is not None else registry.SECTIONS)
    selected_keys = {s.key for s in selected}
    run = RunContext(
        options=options,
        is_admin=is_user_admin() if is_admin is None else bool(is_admin),
        results={},
        shared=SharedSources(shared_loaders if shared_loaders is not None else ps.SHARED_LOADERS),
        runner=runner or ps.run_ps_json,
        text_runner=text_runner or ps.run_text,
    )
    results = run.results
    errors: dict[str, str] = {}
    elapsed = run.elapsed
    total = len(selected)
    completed = 0
    started_at = time.monotonic()

    def report(section):
        nonlocal completed
        completed += 1
        if progress_cb:
            try:
                progress_cb(section.title, completed, total)
            except Exception:
                logger.debug("run_all: progress callback failed", exc_info=True)

    def deps_done(section):
        return all(dep in results or dep not in selected_keys for dep in section.after)

    pending = list(selected)
    running: dict[cf.Future, object] = {}
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        while pending or running:
            for section in [s for s in pending if deps_done(s)]:
                pending.remove(section)
                running[ex.submit(_collect_one, run, section)] = section
            if not running:
                # Nothing can start: a dependency will never complete (cycle).
                for section in pending:
                    message = f"dependencies never completed: {', '.join(section.after)}"
                    results[section.key] = {"status": "partial", "error": message}
                    errors[section.key] = message
                    report(section)
                break
            done, _ = cf.wait(running, return_when=cf.FIRST_COMPLETED)
            for fut in done:
                section = running.pop(fut)
                result, exc, raw_seconds = fut.result()
                if exc is not None:
                    logger.warning("PC report section %s failed: %s", section.key, exc)
                    result = {"status": "partial", "error": str(exc)}
                    errors[section.key] = str(exc)
                seconds = round(raw_seconds, 3)
                results[section.key] = result
                elapsed[section.key] = seconds
                report(section)

    meta = {
        "generated_at": datetime.datetime.now().isoformat(),
        "machine": os.environ.get("COMPUTERNAME", ""),
        "nvc_version": APP_VERSION,
        "elevated": run.is_admin,
        "elapsed_by_section": elapsed,
        "total_seconds": round(time.monotonic() - started_at, 2),
    }
    return meta, dict(results), errors


