import unittest

from pc_report import section as S


def _section(key="k", **kw):
    return S.Section(key=key, title=key.title(), group="Software",
                     collect=lambda ctx: {}, render=lambda d, c: "", **kw)


class ResultShapeTests(unittest.TestCase):
    def test_wrap_and_unwrap(self):
        wrapped = S.wrap({"a": 1}, ["n1"])
        self.assertEqual(wrapped, {"data": {"a": 1}, "notes": ["n1"]})
        self.assertEqual(S.section_data(wrapped), {"a": 1})
        self.assertEqual(S.section_notes(wrapped), ["n1"])

    def test_partial_is_recognised_and_has_no_data(self):
        partial = {"status": "partial", "error": "boom"}
        self.assertTrue(S.is_partial(partial))
        self.assertIsNone(S.section_data(partial))
        self.assertIsNone(S.section_data(None))

    def test_legacy_unwrapped_result_passes_through(self):
        self.assertEqual(S.section_data([1, 2]), [1, 2])

    def test_shaping_helpers(self):
        self.assertEqual(S.as_list(None), [])
        self.assertEqual(S.as_list({"a": 1}), [{"a": 1}])
        self.assertEqual(S.rows_of([{"a": 1}, "junk", None]), [{"a": 1}])
        self.assertEqual(S.first_dict(["x", {"b": 2}]), {"b": 2})
        self.assertEqual(S.first_dict(None), {})


class SectionContextTests(unittest.TestCase):
    def _ctx(self, is_admin=False, runner=None, text_runner=None, loaders=None):
        run = S.RunContext(options={"x": 1}, is_admin=is_admin, results={"dep": S.wrap({"v": 7}, [])},
                           shared=S.SharedSources(loaders or {}),
                           runner=runner or (lambda script, timeout: ({"ok": True}, None)),
                           text_runner=text_runner or (lambda args, timeout: ("out", None)))
        return S.SectionContext(run, _section(timeout=42))

    def test_query_uses_section_timeout_and_records_errors(self):
        seen = {}

        def runner(script, timeout):
            seen["timeout"] = timeout
            return None, "timed out"

        ctx = self._ctx(runner=runner)
        self.assertIsNone(ctx.query("thing", "Get-Thing"))
        self.assertEqual(seen["timeout"], 42)
        self.assertEqual(ctx.notes, ["thing: timed out"])

    def test_query_timeout_override(self):
        seen = {}
        ctx = self._ctx(runner=lambda s, t: (seen.setdefault("t", t), None))
        ctx.query("x", "y", timeout=90)
        self.assertEqual(seen["t"], 90)

    def test_admin_query_without_admin_never_runs(self):
        ctx = self._ctx(runner=lambda s, t: self.fail("must not run"))
        self.assertEqual(ctx.admin_query("bitlocker", "Get-BitLockerVolume"), S.REQUIRES_ADMIN)
        self.assertEqual(ctx.notes, ["bitlocker: requires administrator"])

    def test_admin_query_with_admin_runs(self):
        ctx = self._ctx(is_admin=True)
        self.assertEqual(ctx.admin_query("x", "y"), {"ok": True})

    def test_text_returns_empty_string_on_error(self):
        ctx = self._ctx(text_runner=lambda a, t: ("", "no such command"))
        self.assertEqual(ctx.text("netsh", ["netsh"]), "")
        self.assertIn("netsh: no such command", ctx.notes)

    def test_shared_is_memoised_and_errors_noted(self):
        calls = []

        def loader():
            calls.append(1)
            return {"dx": 1}, None

        ctx = self._ctx(loaders={"dxdiag": loader})
        self.assertEqual(ctx.shared("dxdiag"), {"dx": 1})
        self.assertEqual(ctx.shared("dxdiag"), {"dx": 1})
        self.assertEqual(len(calls), 1)
        self.assertIsNone(ctx.shared("missing"))
        self.assertTrue(any("missing" in n for n in ctx.notes))

    def test_shared_loader_exception_is_captured(self):
        def loader():
            raise RuntimeError("dxdiag exploded")
        ctx = self._ctx(loaders={"dxdiag": loader})
        self.assertIsNone(ctx.shared("dxdiag"))
        self.assertIn("dxdiag: dxdiag exploded", ctx.notes)

    def test_result_reads_other_sections_data(self):
        ctx = self._ctx()
        self.assertEqual(ctx.result("dep"), {"v": 7})
        self.assertIsNone(ctx.result("absent"))
        self.assertEqual(ctx.options, {"x": 1})


class HtmlHelperTests(unittest.TestCase):
    def test_kv_table_escapes_and_subheads(self):
        html = S.kv_table([("Group", None), ("Name", "<b>"), ("Flag", True), ("List", ["a", "b"])])
        self.assertIn('<tr class="sub"><th colspan="2">Group</th></tr>', html)
        self.assertIn("<th>Name</th><td>&lt;b&gt;</td>", html)
        self.assertIn("<td>Yes</td>", html)
        self.assertIn("<td>a, b</td>", html)

    def test_kv_table_empty(self):
        self.assertEqual(S.kv_table([]), S.NO_DATA)

    def test_kv_groups_skips_empty_groups_and_keeps_none_values_blank(self):
        html = S.kv_groups([{"title": "Empty", "rows": {}},
                            {"title": "Real", "rows": {"A": None, "B": 2}}])
        self.assertNotIn("Empty", html)
        self.assertIn("<th>A</th><td></td>", html)
        self.assertIn("<th>B</th><td>2</td>", html)

    def test_kv_groups_skips_malformed_rows_instead_of_losing_the_section(self):
        groups = [{"title": "Mixed", "rows": ["abc", ("a", "b", "c"), 7, ["Good", "value"], ("Pair", 2)]},
                  {"title": "String rows", "rows": "abc"}]

        html = S.kv_groups(groups)

        self.assertIn("<th>Good</th><td>value</td>", html)
        self.assertIn("<th>Pair</th><td>2</td>", html)
        self.assertNotIn("abc", html)
        self.assertNotIn("String rows", html)

    def test_requires_admin_renders_warning(self):
        html = S.kv_table([("TPM", S.REQUIRES_ADMIN)])
        self.assertIn('<span class="warn">Requires administrator</span>', html)

    def test_list_table(self):
        html = S.list_table([("a", "Col A"), ("b", "Col B")], [{"a": 1}, "junk", {"b": "x"}])
        self.assertIn("<th>Col A</th><th>Col B</th>", html)
        self.assertIn("<td>1</td><td></td>", html)
        self.assertIn("<td></td><td>x</td>", html)
        self.assertEqual(S.list_table([("a", "A")], []), S.NO_DATA)

    def test_long_cell_is_folded(self):
        html = S.list_table([("c", "C")], [{"c": "x" * 600}])
        self.assertIn("<details>", html)

    def test_notes_block(self):
        self.assertEqual(S.notes_block([]), "")
        self.assertIn("a &amp; b", S.notes_block(["a & b"]))
        self.assertIn("<h3>T</h3>", S.sub_heading("T"))
