"""Tests for pc_report/orchestrator.py and pc_report/utils.py.

The orchestrator fans 25 collectors across a thread pool, each of which
shells out to PowerShell. Neither module had tests. Nothing here runs
PowerShell: the collectors are replaced with plain callables, and
run_ps_json's subprocess is patched.
"""
import unittest
from unittest.mock import patch

from pc_report import orchestrator
from pc_report import ps as pcps
from pc_report import utils as pcutils


class RunAllTests(unittest.TestCase):
    def _patch_collectors(self, **overrides):
        """Replace every collector with a stub returning its own name."""
        names = [
            "collect_nvc_specific", "collect_os", "collect_updates",
            "collect_programs", "collect_security", "collect_hardware",
            "collect_network", "collect_network_connections",
            "collect_services", "collect_processes", "collect_licenses",
            "collect_environment", "collect_network_info", "collect_printers",
            "collect_autoruns", "collect_accessibility", "collect_drivers",
            "collect_codecs", "collect_snapins", "collect_sensors",
            "collect_devices", "collect_pci", "collect_slots", "collect_ports",
            "collect_virtual_machine",
        ]
        patches = []
        for name in names:
            fn = overrides.get(name)
            if fn is None:
                def fn(_name=name, **_kw):
                    return {"ok": _name}
            patches.append(patch.object(orchestrator.C, name, fn))
        return patches

    def _run(self, options=None, progress_cb=None, **overrides):
        patches = self._patch_collectors(**overrides)
        for p in patches:
            p.start()
        try:
            return orchestrator.run_all(options or {}, progress_cb=progress_cb)
        finally:
            for p in patches:
                p.stop()

    def test_every_section_runs_by_default(self):
        meta, results, errors = self._run()
        self.assertEqual(errors, {})
        self.assertEqual(len(results), 25)
        self.assertIn("operating_system", results)
        self.assertIn("noldus_nvc_report", results)

    def test_a_section_can_be_switched_off(self):
        _meta, results, _errors = self._run({"processes": False,
                                             "services": False})
        self.assertNotIn("processes", results)
        self.assertNotIn("services", results)
        self.assertIn("operating_system", results)

    def test_switching_everything_off_produces_no_results(self):
        options = dict.fromkeys(("noldus_nvc_report", "operating_system", "installed_updates", "installed_programs", "security", "hardware", "network", "network_connections", "services", "processes", "licenses", "environment", "network_info", "printers", "autoruns", "accessibility", "drivers", "codecs", "snapins", "sensors", "devices", "pci", "slots", "ports", "virtual_machine"), False)
        meta, results, errors = self._run(options)
        self.assertEqual(results, {})
        self.assertEqual(errors, {})
        self.assertIn("generated_at", meta, "metadata is still produced")

    def test_metadata_records_when_and_where(self):
        meta, _results, _errors = self._run()
        self.assertIn("generated_at", meta)
        self.assertIn("machine", meta)
        # ISO-8601, so it sorts and parses.
        import datetime
        datetime.datetime.fromisoformat(meta["generated_at"])

    # -- failure isolation ----------------------------------------------
    def test_one_failing_collector_does_not_lose_the_others(self):
        """A single collector raising must not abandon the whole report."""
        def exploding():
            raise RuntimeError("WMI is unavailable")

        _meta, results, errors = self._run(collect_hardware=exploding)

        self.assertIn("hardware", errors)
        self.assertIn("WMI is unavailable", errors["hardware"])
        self.assertEqual(len(results), 25, "every section still has an entry")
        self.assertIn("operating_system", results)

    def test_a_failed_section_is_marked_partial_in_the_results(self):
        # The renderers read results, not errors, so the placeholder is what
        # tells a reader that a section is incomplete rather than empty.
        def exploding():
            raise RuntimeError("access denied")

        _meta, results, _errors = self._run(collect_security=exploding)
        self.assertEqual(results["security"]["status"], "partial")
        self.assertIn("access denied", results["security"]["error"])

    def test_several_failures_are_all_recorded(self):
        def exploding():
            raise OSError("nope")

        _meta, _results, errors = self._run(collect_pci=exploding,
                                            collect_slots=exploding,
                                            collect_ports=exploding)
        self.assertEqual(set(errors), {"pci", "slots", "ports"})

    # -- progress -------------------------------------------------------
    def test_progress_is_reported_once_per_section(self):
        seen = []
        self._run(progress_cb=lambda name, done, total: seen.append((name, done, total)))
        self.assertEqual(len(seen), 25)
        self.assertEqual([d for _n, d, _t in seen], list(range(1, 26)),
                         "the completed count should advance by one each time")
        self.assertTrue(all(t == 25 for _n, _d, t in seen))

    def test_progress_is_reported_for_failed_sections_too(self):
        def exploding():
            raise RuntimeError("x")

        seen = []
        self._run(progress_cb=lambda *a: seen.append(a),
                  collect_codecs=exploding)
        self.assertEqual(len(seen), 25, "a failure must still advance progress")

    def test_a_raising_progress_callback_does_not_break_the_report(self):
        def hostile(*_args):
            raise RuntimeError("the dialog closed")

        _meta, results, errors = self._run(progress_cb=hostile)
        self.assertEqual(len(results), 25)
        self.assertEqual(errors, {})

    def test_the_section_limits_are_passed_through(self):
        captured = {}

        def services(limit=None):
            captured["services"] = limit
            return {}

        def processes(limit=None):
            captured["processes"] = limit
            return {}

        self._run({"services_limit": 7, "processes_limit": 9},
                  collect_services=services, collect_processes=processes)
        self.assertEqual(captured, {"services": 7, "processes": 9})

    def test_the_limits_have_defaults(self):
        captured = {}

        def services(limit=None):
            captured["services"] = limit
            return {}

        self._run(collect_services=services)
        self.assertEqual(captured["services"], 1000)


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
            pcutils.run_ps_json.__defaults__[0], 1,
            "run_ps_json should carry the real timeout")


class ByteFormattingTests(unittest.TestCase):
    def test_it_scales_through_the_units(self):
        self.assertEqual(pcutils.bytes_human(0), "0.0 B")
        self.assertEqual(pcutils.bytes_human(512), "512.0 B")
        self.assertEqual(pcutils.bytes_human(1024), "1.0 KB")
        self.assertEqual(pcutils.bytes_human(1024 ** 2), "1.0 MB")
        self.assertEqual(pcutils.bytes_human(1024 ** 3), "1.0 GB")
        self.assertEqual(pcutils.bytes_human(1024 ** 4), "1.0 TB")

    def test_it_stops_at_terabytes_rather_than_running_off_the_list(self):
        self.assertTrue(pcutils.bytes_human(1024 ** 6).endswith("TB"))

    def test_a_numeric_string_is_accepted(self):
        self.assertEqual(pcutils.bytes_human("2048"), "2.0 KB")

    def test_something_unparseable_is_returned_unchanged(self):
        # Comes straight out of WMI, which can return anything.
        for value in ("Unknown", None, "", "n/a"):
            self.assertEqual(pcutils.bytes_human(value), value)


class BitrateTests(unittest.TestCase):
    def test_it_converts_to_mbps(self):
        self.assertEqual(pcutils.bitrate_to_mbps(1_000_000), "1.0 Mbps")
        self.assertEqual(pcutils.bitrate_to_mbps(1_000_000_000), "1000.0 Mbps")

    def test_zero_and_negative_are_unknown(self):
        self.assertEqual(pcutils.bitrate_to_mbps(0), "Unknown")
        self.assertEqual(pcutils.bitrate_to_mbps(-1), "Unknown")

    def test_the_uint64_sentinel_is_unknown(self):
        """Windows reports an unset speed as a huge number, not as null."""
        self.assertEqual(pcutils.bitrate_to_mbps(9_223_372_036_854_775_807),
                         "Unknown")

    def test_unparseable_input_is_unknown(self):
        for value in (None, "", "fast", [1]):
            self.assertEqual(pcutils.bitrate_to_mbps(value), "Unknown")


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
            data, error = pcutils.run_ps_json("Get-Thing")
        self.assertEqual(data, {"a": 1})
        self.assertIsNone(error)

    def test_a_non_zero_exit_returns_its_stderr(self):
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(returncode=1,
                                                       stderr="not recognised")):
            data, error = pcutils.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertEqual(error, "not recognised")

    def test_empty_output_is_neither_data_nor_an_error(self):
        # A query that legitimately matched nothing.
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(stdout="")):
            data, error = pcutils.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIsNone(error)

    def test_unparseable_output_is_reported_as_a_parse_error(self):
        with patch.object(pcps.subprocess, "run",
                          return_value=self._Completed(stdout="not json")):
            data, error = pcutils.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIn("JSON parse error", error)

    def test_a_timeout_is_reported_rather_than_raising(self):
        import subprocess as sp
        with patch.object(pcps.subprocess, "run",
                          side_effect=sp.TimeoutExpired("powershell", 12)):
            data, error = pcutils.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIsNotNone(error)

    def test_a_missing_powershell_is_reported_rather_than_raising(self):
        with patch.object(pcps.subprocess, "run",
                          side_effect=FileNotFoundError("powershell")):
            data, error = pcutils.run_ps_json("Get-Thing")
        self.assertIsNone(data)
        self.assertIn("powershell", error)

    def test_the_timeout_has_a_floor(self):
        """A caller asking for 1s would produce empty data on a slow machine."""
        captured = {}

        def capture(cmd, **kwargs):
            captured.update(kwargs)
            return self._Completed(stdout="{}")

        with patch.object(pcps.subprocess, "run", capture):
            pcutils.run_ps_json("Get-Thing", timeout=1)
        self.assertGreaterEqual(captured["timeout"], 12)

    def test_a_longer_timeout_is_respected(self):
        captured = {}

        def capture(cmd, **kwargs):
            captured.update(kwargs)
            return self._Completed(stdout="{}")

        with patch.object(pcps.subprocess, "run", capture):
            pcutils.run_ps_json("Get-Thing", timeout=60)
        self.assertEqual(captured["timeout"], 60)

    def test_the_script_is_piped_through_convertto_json(self):
        captured = {}

        def capture(cmd, **kwargs):
            captured["cmd"] = cmd
            return self._Completed(stdout="{}")

        with patch.object(pcps.subprocess, "run", capture):
            pcutils.run_ps_json("Get-Process")
        joined = " ".join(captured["cmd"])
        self.assertIn("Get-Process", joined)
        self.assertIn("ConvertTo-Json", joined)
        self.assertIn("-NonInteractive", captured["cmd"])
        self.assertIn("-NoProfile", captured["cmd"])


if __name__ == "__main__":
    unittest.main()
