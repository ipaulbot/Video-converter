import json
import tempfile
import unittest
from pathlib import Path

from pc_report.section import REQUIRES_ADMIN, RunContext, Section, SharedSources
from tests.pc_report import support


def _section(key="demo", collect=None):
    return Section(key=key, title="Demo", group="Software",
                   collect=collect or (lambda ctx: {}), render=lambda d, c: "")


class FixtureContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "demo").mkdir()
        (self.root / "demo" / "os.json").write_text('{"Caption": "Windows"}', encoding="utf-8")
        (self.root / "demo" / "netsh_wlan.txt").write_text("SSID : lab", encoding="utf-8")
        (self.root / "_shared").mkdir()
        (self.root / "_shared" / "dxdiag.json").write_text('{"DxDiag": 1}', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_json_and_text_by_query_name(self):
        ctx = support.FixtureSectionContext(_section(), root=self.root)
        self.assertEqual(ctx.query("os", "Get-CimInstance ..."), {"Caption": "Windows"})
        self.assertEqual(ctx.text("netsh wlan", ["netsh", "wlan"]), "SSID : lab")
        self.assertEqual(ctx.shared("dxdiag"), {"DxDiag": 1})
        self.assertEqual(ctx.requested, ["os", "netsh wlan", "dxdiag"])

    def test_missing_fixture_is_none_with_a_note(self):
        ctx = support.FixtureSectionContext(_section(), root=self.root)
        self.assertIsNone(ctx.query("absent", "x"))
        self.assertEqual(ctx.text("absent txt", ["x"]), "")
        self.assertTrue(any(n.startswith("absent: no fixture") for n in ctx.notes))

    def test_admin_query_respects_flag(self):
        ctx = support.FixtureSectionContext(_section(), root=self.root)
        self.assertEqual(ctx.admin_query("os", "x"), REQUIRES_ADMIN)
        ctx = support.FixtureSectionContext(_section(), is_admin=True, root=self.root)
        self.assertEqual(ctx.admin_query("os", "x"), {"Caption": "Windows"})

    def test_results_are_visible_to_dependent_sections(self):
        ctx = support.FixtureSectionContext(_section(), results={"cpu": {"data": {"n": 1}, "notes": []}},
                                            root=self.root)
        self.assertEqual(ctx.result("cpu"), {"n": 1})

    def test_query_names_are_made_filesystem_safe(self):
        self.assertEqual(support.safe_name("Win32 Bios/version"), "Win32_Bios_version")


class RecordingContextTests(unittest.TestCase):
    def test_scrub_values_changes_string_values_not_dict_keys(self):
        value = {"Host": ["Host", 1, {"Host": "x Host"}]}
        scrubbed = support.scrub_values(value, lambda s: s.replace("Host", "PC"))
        self.assertEqual(scrubbed, {"Host": ["PC", 1, {"Host": "x PC"}]})

    def test_recording_scrubs_json_values_without_changing_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = RunContext(
                options={},
                is_admin=False,
                results={},
                shared=SharedSources({}),
                runner=lambda s, t: ({"Host": "Host"}, None),
                text_runner=lambda a, t: ("", None),
            )
            ctx = support.RecordingSectionContext(
                run,
                _section(),
                root,
                lambda value: value,
                lambda text: text.replace("Host", "PC-NAME"),
            )

            ctx.query("os", "x")

            saved = json.loads((root / "demo" / "os.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, {"Host": "PC-NAME"})

    def test_records_redacted_and_scrubbed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = RunContext(options={}, is_admin=False, results={},
                             shared=SharedSources({"dxdiag": lambda: ({"Machine": "LAB-PC-01"}, None)}),
                             runner=lambda s, t: ({"SerialNumber": "ABC123456", "Host": "LAB-PC-01"}, None),
                             text_runner=lambda a, t: ("host LAB-PC-01", None))
            redact = lambda v: {**v, "SerialNumber": "masked"} if isinstance(v, dict) and "SerialNumber" in v else v  # noqa: E731
            scrub = lambda text: text.replace("LAB-PC-01", "PC-NAME")  # noqa: E731
            ctx = support.RecordingSectionContext(run, _section(), root, redact, scrub)

            ctx.query("os", "x")
            ctx.text("netsh", ["netsh"])
            ctx.shared("dxdiag")
            self.assertEqual(ctx.admin_query("bitlocker", "x"), REQUIRES_ADMIN)

            saved = json.loads((root / "demo" / "os.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, {"SerialNumber": "masked", "Host": "PC-NAME"})
            self.assertEqual((root / "demo" / "netsh.txt").read_text(encoding="utf-8"), "host PC-NAME")
            self.assertEqual(json.loads((root / "_shared" / "dxdiag.json").read_text(encoding="utf-8")),
                             {"Machine": "PC-NAME"})
            self.assertFalse((root / "demo" / "bitlocker.json").exists())


class HelperTests(unittest.TestCase):
    def test_assert_renders_empty_passes_for_a_tolerant_section(self):
        support.assert_renders_empty(self, _section())

    def test_collect_and_render_uses_fixtures_and_redacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo").mkdir()
            (root / "demo" / "q.json").write_text('{"SerialNumber": "ABCDEFGH"}', encoding="utf-8")
            import dataclasses
            section = dataclasses.replace(_section(collect=lambda ctx: ctx.query("q", "x")),
                                          render=lambda d, c: str(d))
            data, html, ctx = support.collect_and_render(section, root=root)
        self.assertEqual(data, {"SerialNumber": "ABCDEFGH"})
        self.assertNotIn("ABCDEFGH", html)
