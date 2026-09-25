import unittest
from unittest.mock import patch

from pc_report import ps


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class RunPsJsonTests(unittest.TestCase):
    def test_wraps_script_in_a_scriptblock_and_utf8(self):
        captured = {}

        def run(cmd, **kw):
            captured["cmd"] = cmd
            return _Completed(stdout="{}")

        with patch.object(ps.subprocess, "run", run):
            ps.run_ps_json("Get-Thing")
        joined = " ".join(captured["cmd"])
        self.assertIn("& { Get-Thing }", joined)
        self.assertIn("ConvertTo-Json", joined)
        self.assertIn("OutputEncoding", joined)
        self.assertIn("ProgressPreference", joined)

    def test_timeout_message_names_the_seconds(self):
        import subprocess as sp
        with patch.object(ps.subprocess, "run", side_effect=sp.TimeoutExpired("powershell", 30)):
            data, error = ps.run_ps_json("x", timeout=30)
        self.assertIsNone(data)
        self.assertEqual(error, "timed out after 30 s")

    def test_nonzero_exit_without_stderr_still_reports(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(returncode=1)):
            _data, error = ps.run_ps_json("x")
        self.assertEqual(error, "exit code 1")

    def test_empty_stdout_keeps_stderr(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(stderr="provider failed")):
            data, error = ps.run_ps_json("x")
        self.assertIsNone(data)
        self.assertEqual(error, "provider failed")

    def test_json_data_keeps_stderr(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(stdout='{"ok": true}', stderr="warning")):
            data, error = ps.run_ps_json("x")
        self.assertEqual(data, {"ok": True})
        self.assertEqual(error, "warning")


class RunTextTests(unittest.TestCase):
    def test_returns_stdout(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(stdout="hello")):
            self.assertEqual(ps.run_text(["cmd"]), ("hello", None))

    def test_failure_with_no_output_is_an_error(self):
        with patch.object(ps.subprocess, "run", return_value=_Completed(returncode=2, stderr="bad")):
            self.assertEqual(ps.run_text(["cmd"]), ("", "bad"))

    def test_missing_binary(self):
        with patch.object(ps.subprocess, "run", side_effect=FileNotFoundError("nope")):
            out, error = ps.run_text(["nope"])
        self.assertEqual(out, "")
        self.assertIn("nope", error)

    def test_decodes_console_output_code_page_bytes(self):
        encoded = "café".encode("cp850")
        with (
            patch.object(ps, "_console_encoding", return_value="cp850"),
            patch.object(ps.subprocess, "run", return_value=_Completed(stdout=encoded, stderr=b"")),
        ):
            out, error = ps.run_text(["cmd"])
        self.assertEqual(out, "café")
        self.assertIsNone(error)

    def test_timeout_reports_effective_floor(self):
        import subprocess as sp
        with patch.object(ps.subprocess, "run", side_effect=sp.TimeoutExpired("cmd", 5)):
            _out, error = ps.run_text(["cmd"], timeout=1)
        self.assertEqual(error, "timed out after 5 s")


class ScriptBuilderTests(unittest.TestCase):
    def test_cim(self):
        script = ps.cim("Win32_BIOS", ["Name", "Version"], namespace=r"root\wmi", where="Level=3")
        self.assertIn("Get-CimInstance -ClassName Win32_BIOS", script)
        self.assertIn("-Namespace 'root\\wmi'", script)
        self.assertIn("-Filter 'Level=3'", script)
        self.assertTrue(script.endswith("| Select-Object Name,Version"))

    def test_ps_quote_doubles_single_quotes(self):
        self.assertEqual(ps.ps_quote("it's"), "'it''s'")

    def test_reg_props(self):
        script = ps.reg_props(r"HKLM:\SOFTWARE\Test")
        self.assertIn("Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Test'", script)
        self.assertIn("PSPath", script)


class DxdiagTests(unittest.TestCase):
    def test_etree_to_dict_collapses_repeats_into_lists(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring("<DxDiag><A><B>1</B><B>2</B><C>x</C></A></DxDiag>")
        self.assertEqual(ps._etree_to_dict(root), {"A": {"B": ["1", "2"], "C": "x"}})

    def test_dx_list_handles_single_and_multiple(self):
        dx = {"DisplayDevices": {"DisplayDevice": {"CardName": "GPU"}}}
        self.assertEqual(ps.dx_list(dx, "DisplayDevices", "DisplayDevice"), [{"CardName": "GPU"}])
        dx = {"DisplayDevices": {"DisplayDevice": [{"CardName": "A"}, {"CardName": "B"}]}}
        self.assertEqual(len(ps.dx_list(dx, "DisplayDevices", "DisplayDevice")), 2)
        self.assertEqual(ps.dx_list(None, "X", "Y"), [])
        self.assertEqual(ps.dx_list({"X": "text"}, "X", "Y"), [])

    def test_shared_loaders_are_registered(self):
        self.assertEqual(set(ps.SHARED_LOADERS), {"dxdiag", "pnp_entities"})
