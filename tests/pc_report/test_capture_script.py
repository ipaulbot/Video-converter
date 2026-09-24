import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from pc_report.section import RunContext, Section, SharedSources

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "capture_pc_report_fixtures",
    ROOT / "scripts" / "dev" / "capture_pc_report_fixtures.py",
)
cap = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(cap)


def _section(key="demo", collect=None, after=()):
    return Section(
        key=key,
        title="Demo",
        group="Software",
        collect=collect or (lambda ctx: {}),
        render=lambda d, c: "",
        after=after,
    )


class MakeScrubTests(unittest.TestCase):
    def test_whole_token_only_does_not_touch_json_keys(self):
        scrub = cap.make_scrub([("name", "user", "user")])
        self.assertEqual(scrub('{"UserName": "name"}'), '{"UserName": "user"}')

    def test_short_identifier_is_not_scrubbed_and_warns(self):
        err = io.StringIO()
        with redirect_stderr(err):
            scrub = cap.make_scrub([("ab", "user", "user")])
        self.assertEqual(scrub("keep ab here"), "keep ab here")
        self.assertIn("warning: not scrubbing short identifier 'user'", err.getvalue())


class CaptureTests(unittest.TestCase):
    def test_capture_records_failures_and_continues(self):
        ok = _section(key="ok", collect=lambda ctx: {"ok": True})
        def _boom(_ctx):
            raise RuntimeError("nope")

        bad = _section(key="bad", collect=_boom)
        run = RunContext(
            options={},
            is_admin=False,
            results={},
            shared=SharedSources({}),
            runner=lambda s, t: ({}, None),
            text_runner=lambda a, t: ("", None),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            failed = cap.capture([bad, ok], run, out, lambda v: v, lambda t: t)
        self.assertEqual(failed, ["bad"])
        self.assertIn("ok", run.results)


class DependencyOrderTests(unittest.TestCase):
    def test_sorts_by_dependency_depth_not_input_order(self):
        a = _section(key="a", after=())
        b = _section(key="b", after=("a",))
        c = _section(key="c", after=("b",))
        order = ("a", "b", "c")
        for incoming in [(c, b, a), (b, a, c), (a, c, b)]:
            sorted_sections = cap.sort_sections(list(incoming), order=order)
            self.assertEqual([s.key for s in sorted_sections], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
