"""Tests for PC report orchestration, formatting, and PowerShell execution.

The orchestrator fans sections across a thread pool, each of which can shell
out to PowerShell. Nothing here runs PowerShell: sections use plain callables,
and the PowerShell runner's subprocess is patched.
"""
import threading
import unittest
from unittest.mock import patch

from pc_report import format as pcformat
from pc_report import orchestrator, registry
from pc_report import ps as pcps
from pc_report.section import Section


def _fake(key, group="Software", collect=None, after=(), default_on=True):
    return Section(key=key, title=key.replace("_", " ").title(), group=group,
                   collect=collect or (lambda ctx: {"ok": key}), render=lambda d, c: "",
                   after=after, default_on=default_on)


class RunAllTests(unittest.TestCase):
    def _sections(self, **overrides):
        base = {
            "operating_system": _fake("operating_system"),
            "cpu": _fake("cpu", "Hardware"),
            "memory": _fake("memory", "Hardware"),
            "shares": _fake("shares", "Network"),
            "processes": _fake("processes"),
        }
        base.update(overrides)
        return list(base.values())

    def _run(self, options=None, progress_cb=None, sections=None, runner=None, **kw):
        return orchestrator.run_all(
            options or {}, progress_cb=progress_cb,
            sections=self._sections() if sections is None else sections,
            runner=runner or (lambda script, timeout: (None, None)),
            text_runner=lambda args, timeout: ("", None),
            shared_loaders=kw.pop("shared_loaders", {}), is_admin=kw.pop("is_admin", False),
            **kw)

    def test_every_section_runs_by_default_and_is_wrapped(self):
        meta, results, errors = self._run()
        self.assertEqual(errors, {})
        self.assertEqual(set(results), {"operating_system", "cpu", "memory", "shares", "processes"})
        self.assertEqual(results["cpu"], {"data": {"ok": "cpu"}, "notes": []})

    def test_a_section_can_be_switched_off(self):
        _meta, results, _errors = self._run({"processes": False, "shares": False})
        self.assertEqual(set(results), {"operating_system", "cpu", "memory"})

    def test_group_alias_switches_off_the_split_sections(self):
        _meta, results, _errors = self._run({"hardware": False})
        self.assertEqual(set(results), {"operating_system", "shares", "processes"})

    def test_switching_everything_off_produces_no_results(self):
        options = dict.fromkeys(("operating_system", "cpu", "memory", "shares", "processes"), False)
        meta, results, errors = self._run(options)
        self.assertEqual(results, {})
        self.assertEqual(errors, {})
        self.assertIn("generated_at", meta)

    def test_metadata(self):
        meta, _results, _errors = self._run()
        import datetime
        datetime.datetime.fromisoformat(meta["generated_at"])
        self.assertIn("machine", meta)
        self.assertEqual(meta["elevated"], False)
        self.assertEqual(set(meta["elapsed_by_section"]), {"operating_system", "cpu", "memory", "shares", "processes"})
        self.assertIsInstance(meta["total_seconds"], float)
        self.assertTrue(meta["nvc_version"])

    # -- failure isolation ----------------------------------------------
    def test_one_failing_section_does_not_lose_the_others(self):
        def exploding(ctx):
            raise RuntimeError("WMI is unavailable")
        _meta, results, errors = self._run(sections=self._sections(cpu=_fake("cpu", collect=exploding)))
        self.assertIn("WMI is unavailable", errors["cpu"])
        self.assertEqual(results["cpu"], {"status": "partial", "error": "WMI is unavailable"})
        self.assertEqual(len(results), 5)

    def test_several_failures_are_all_recorded(self):
        def exploding(ctx):
            raise OSError("nope")
        _meta, _results, errors = self._run(sections=self._sections(
            cpu=_fake("cpu", collect=exploding), memory=_fake("memory", collect=exploding)))
        self.assertEqual(set(errors), {"cpu", "memory"})

    def test_query_errors_become_notes_not_failures(self):
        def collect(ctx):
            return {"value": ctx.query("thing", "Get-Thing")}
        _meta, results, errors = self._run(sections=[_fake("cpu", collect=collect)],
                                           runner=lambda s, t: (None, "access denied"))
        self.assertEqual(errors, {})
        self.assertEqual(results["cpu"], {"data": {"value": None}, "notes": ["thing: access denied"]})

    def test_preset_cancellation_marks_every_section_partial_without_spawning(self):
        cancel = threading.Event()
        cancel.set()
        calls = []
        _meta, results, errors = self._run(
            cancel=cancel,
            runner=lambda script, timeout: calls.append(script) or (None, None),
        )
        self.assertEqual(calls, [])
        self.assertEqual(set(results), {s.key for s in self._sections()})
        self.assertTrue(all(result == {"status": "partial", "error": "cancelled"}
                            for result in results.values()))
        self.assertEqual(set(errors), set(results))

    # -- progress -------------------------------------------------------
    def test_progress_is_reported_once_per_section_with_titles(self):
        seen = []
        self._run(progress_cb=lambda name, done, total: seen.append((name, done, total)))
        self.assertEqual(len(seen), 5)
        self.assertEqual([d for _n, d, _t in seen], [1, 2, 3, 4, 5])
        self.assertTrue(all(t == 5 for _n, _d, t in seen))
        self.assertIn("Operating System", [n for n, _d, _t in seen])

    def test_progress_is_reported_for_failed_sections_too(self):
        def exploding(ctx):
            raise RuntimeError("x")
        seen = []
        self._run(progress_cb=lambda *a: seen.append(a),
                  sections=self._sections(cpu=_fake("cpu", collect=exploding)))
        self.assertEqual(len(seen), 5)

    def test_a_raising_progress_callback_does_not_break_the_report(self):
        def hostile(*_args):
            raise RuntimeError("the dialog closed")
        _meta, results, errors = self._run(progress_cb=hostile)
        self.assertEqual(len(results), 5)
        self.assertEqual(errors, {})

    # -- options reach the sections ---------------------------------------
    def test_sections_read_limits_from_ctx_options(self):
        captured = {}
        def collect(ctx):
            captured["limit"] = ctx.options.get("services_limit", 1000)
            return {}
        self._run({"services_limit": 7}, sections=[_fake("services", collect=collect)])
        self.assertEqual(captured["limit"], 7)
        self._run({}, sections=[_fake("services", collect=collect)])
        self.assertEqual(captured["limit"], 1000)

    # -- dependencies ------------------------------------------------------
    def test_after_sections_see_their_dependencies_results(self):
        def summary(ctx):
            return {"cpu_seen": ctx.result("cpu")}
        sections = [_fake("noldus_summary", "NVC", collect=summary, after=("cpu",)), _fake("cpu", "Hardware")]
        _meta, results, _errors = self._run(sections=sections)
        self.assertEqual(results["noldus_summary"]["data"], {"cpu_seen": {"ok": "cpu"}})

    def test_a_dependency_that_is_switched_off_counts_as_satisfied(self):
        def summary(ctx):
            return {"cpu_seen": ctx.result("cpu")}
        sections = [_fake("noldus_summary", "NVC", collect=summary, after=("cpu",)), _fake("cpu", "Hardware")]
        _meta, results, _errors = self._run({"cpu": False}, sections=sections)
        self.assertEqual(results["noldus_summary"]["data"], {"cpu_seen": None})

    def test_later_phase_sees_elapsed_time_for_earlier_phase(self):
        captured_run_elapsed = {}

        def summary(ctx):
            captured_run_elapsed.update(dict(ctx.run.elapsed))
            return {"cpu_elapsed": "cpu" in ctx.run.elapsed}

        sections = [_fake("noldus_summary", "NVC", collect=summary, after=("cpu",)), _fake("cpu", "Hardware")]
        meta, results, _errors = self._run(sections=sections)
        self.assertEqual(results["noldus_summary"]["data"], {"cpu_elapsed": True})
        self.assertEqual(meta["elapsed_by_section"]["cpu"], captured_run_elapsed["cpu"])

    def test_failed_section_records_real_elapsed_time(self):
        import time

        def slow_then_fail(ctx):
            deadline = time.monotonic() + 0.05
            while time.monotonic() < deadline:
                time.sleep(0.001)
            raise RuntimeError("collect blew up")

        sections = [_fake("cpu", "Hardware", collect=slow_then_fail)]
        meta, results, errors = self._run(sections=sections)
        self.assertIn("collect blew up", errors["cpu"])
        self.assertEqual(results["cpu"]["status"], "partial")
        self.assertGreaterEqual(meta["elapsed_by_section"]["cpu"], 0.05)

    def test_a_dependency_cycle_is_reported_not_hung(self):
        sections = [_fake("a", after=("b",)), _fake("b", after=("a",))]
        _meta, results, errors = self._run(sections=sections)
        self.assertEqual(set(errors), {"a", "b"})
        self.assertIn("never completed", results["a"]["error"])

    # -- shared sources ----------------------------------------------------
    def test_shared_sources_are_loaded_once_for_the_whole_run(self):
        calls = []
        def loader():
            calls.append(1)
            return {"dx": True}, None
        def uses_dx(ctx):
            return {"dx": ctx.shared("dxdiag")}
        sections = [_fake(k, "Hardware", collect=uses_dx) for k in ("video", "monitors", "sound", "cameras")]
        _meta, results, _errors = self._run(sections=sections, shared_loaders={"dxdiag": loader})
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(results[k]["data"] == {"dx": {"dx": True}} for k in ("video", "monitors", "sound", "cameras")))

    def test_shared_source_failure_degrades_to_notes(self):
        def loader():
            return None, "dxdiag timed out"
        def uses_dx(ctx):
            return {"dx": ctx.shared("dxdiag")}
        _meta, results, errors = self._run(sections=[_fake("video", "Hardware", collect=uses_dx)],
                                           shared_loaders={"dxdiag": loader})
        self.assertEqual(errors, {})
        self.assertEqual(results["video"]["notes"], ["dxdiag: dxdiag timed out"])

    # -- the real registry ----------------------------------------------------
    def test_every_registered_section_tolerates_an_offline_machine(self):
        """Every query answering (None, 'offline') must still yield a wrapped result, never a raise."""
        _meta, results, errors = orchestrator.run_all(
            {}, sections=registry.SECTIONS, runner=lambda s, t: (None, "offline"),
            text_runner=lambda a, t: ("", "offline"),
            shared_loaders={"dxdiag": lambda: (None, "offline"), "pnp_entities": lambda: (None, "offline")},
            is_admin=False)
        self.assertEqual(errors, {}, errors)
        self.assertEqual(set(results), {s.key for s in registry.SECTIONS})


class TimeoutLocationTests(unittest.TestCase):
    """Where a slow collector is actually bounded.

    run_all used to call fut.result(timeout=12), which reads like a
    per-collector limit but can never fire: as_completed only yields a future
    once it has already finished. The real bound is the subprocess timeout in
    run_ps_json.
    """

    def test_run_all_does_not_claim_a_timeout_it_cannot_enforce(self):
        import inspect
        source = inspect.getsource(orchestrator.run_all)
        self.assertNotIn("fut.result(timeout=", source,
                         "a timeout on an already-completed future never fires")

    def test_a_slow_collector_is_bounded_by_the_subprocess_timeout(self):
        self.assertGreaterEqual(
            pcps.run_ps_json.__defaults__[0], 1,
            "run_ps_json should carry the real timeout")


class ByteFormattingTests(unittest.TestCase):
    def test_it_scales_through_the_units(self):
        self.assertEqual(pcformat.bytes_human(0), "0.0 B")
        self.assertEqual(pcformat.bytes_human(512), "512.0 B")
        self.assertEqual(pcformat.bytes_human(1024), "1.0 KB")
        self.assertEqual(pcformat.bytes_human(1024 ** 2), "1.0 MB")
        self.assertEqual(pcformat.bytes_human(1024 ** 3), "1.0 GB")
        self.assertEqual(pcformat.bytes_human(1024 ** 4), "1.0 TB")

    def test_it_stops_at_terabytes_rather_than_running_off_the_list(self):
        self.assertTrue(pcformat.bytes_human(1024 ** 6).endswith("TB"))

    def test_a_numeric_string_is_accepted(self):
        self.assertEqual(pcformat.bytes_human("2048"), "2.0 KB")

    def test_something_unparseable_is_returned_unchanged(self):
        # Comes straight out of WMI, which can return anything.
        for value in ("Unknown", None, "", "n/a"):
            self.assertEqual(pcformat.bytes_human(value), value)


class BitrateTests(unittest.TestCase):
    def test_it_converts_to_mbps(self):
        self.assertEqual(pcformat.bitrate_to_mbps(1_000_000), "1.0 Mbps")
        self.assertEqual(pcformat.bitrate_to_mbps(1_000_000_000), "1000.0 Mbps")

    def test_zero_and_negative_are_unknown(self):
        self.assertEqual(pcformat.bitrate_to_mbps(0), "Unknown")
        self.assertEqual(pcformat.bitrate_to_mbps(-1), "Unknown")

    def test_the_uint64_sentinel_is_unknown(self):
        """Windows reports an unset speed as a huge number, not as null."""
        self.assertEqual(pcformat.bitrate_to_mbps(9_223_372_036_854_775_807),
                         "Unknown")

    def test_unparseable_input_is_unknown(self):
        for value in (None, "", "fast", [1]):
            self.assertEqual(pcformat.bitrate_to_mbps(value), "Unknown")


class PowerShellJsonTests(unittest.TestCase):
    """run_ps_json returns (data, error) and must never raise."""

    class _Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def test_valid_json_is_parsed(self):
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(stdout='{"a": 1}')):
            data, error = pcps.run_ps_json("Get-Thing")
        self.assertEqual(data, {"a": 1})
        self.assertIsNone(error)

    def test_a_non_zero_exit_returns_its_stderr(self):
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(returncode=1,
                                                       stderr="not recognised")):
            data, error = pcps.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertEqual(error, "not recognised")

    def test_empty_output_is_neither_data_nor_an_error(self):
        # A query that legitimately matched nothing.
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(stdout="")):
            data, error = pcps.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIsNone(error)

    def test_unparseable_output_is_reported_as_a_parse_error(self):
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(stdout="not json")):
            data, error = pcps.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIn("JSON parse error", error)

    def test_a_timeout_is_reported_rather_than_raising(self):
        import subprocess as sp
        with patch.object(pcps.subprocess, "run",
                          side_effect=sp.TimeoutExpired("powershell", 12)):
            data, error = pcps.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIsNotNone(error)

    def test_a_missing_powershell_is_reported_rather_than_raising(self):
        with patch.object(pcps.subprocess, "run",
                          side_effect=FileNotFoundError("powershell")):
            data, error = pcps.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIn("powershell", error)

    def test_the_timeout_has_a_floor(self):
        """A caller asking for 1s would produce empty data on a slow machine."""
        captured = {}

        def capture(cmd, **kwargs):
            captured.update(kwargs)
            return self._Completed(stdout="{}")

        with patch.object(pcps.subprocess, "run", capture):
            pcps.run_ps_json("Get-Thing", timeout=1)
        self.assertGreaterEqual(captured["timeout"], 12)

    def test_a_longer_timeout_is_respected(self):
        captured = {}

        def capture(cmd, **kwargs):
            captured.update(kwargs)
            return self._Completed(stdout="{}")

        with patch.object(pcps.subprocess, "run", capture):
            pcps.run_ps_json("Get-Thing", timeout=60)
        self.assertEqual(captured["timeout"], 60)

    def test_the_script_is_piped_through_convertto_json(self):
        captured = {}

        def capture(cmd, **kwargs):
            captured["cmd"] = cmd
            return self._Completed(stdout="{}")

        with patch.object(pcps.subprocess, "run", capture):
            pcps.run_ps_json("Get-Process")
        joined = " ".join(captured["cmd"])
        self.assertIn("Get-Process", joined)
        self.assertIn("ConvertTo-Json", joined)
        self.assertIn("-NonInteractive", captured["cmd"])
        self.assertIn("-NoProfile", captured["cmd"])


if __name__ == "__main__":
    unittest.main()
