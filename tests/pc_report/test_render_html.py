import unittest
from html.parser import HTMLParser
from unittest.mock import patch

from pc_report import registry, render_html
from pc_report.section import NO_DATA, Section, kv_table, wrap


def _default_render(d, c):
    return kv_table([("Field", d.get("v", ""))]) if d else NO_DATA


def _fake(key, group, render=None, title=None):
    return Section(key=key, title=title or key.replace("_", " ").title(), group=group,
                   collect=lambda ctx: {}, render=render or _default_render)


FAKES = (
    _fake("noldus_summary", "NVC", title="Noldus Summary"),
    _fake("operating_system", "Software"),
    _fake("cpu", "Hardware", render=lambda d, c: kv_table([("Serial Number", (d or {}).get("Serial Number", ""))])),
    _fake("shares", "Network"),
)
META = {"generated_at": "2026-09-24T10:00:00", "machine": "WDGS-BH0020", "nvc_version": "2.3.0",
        "elevated": False, "elapsed_by_section": {"cpu": 3.2, "shares": 0.4, "operating_system": 1.1},
        "total_seconds": 4.7}


class _Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.errors = set(), set(), []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href", "").startswith("#"):
            self.hrefs.add(a["href"][1:])
        if tag not in ("br", "img", "meta", "link", "hr"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected </{tag}>; open: {self.stack[-3:]}")


def _render(data, options=None, meta=None):
    with patch.object(registry, "SECTIONS", FAKES):
        return render_html.render(meta or META, data, options or {"redact": True})


def _data(**kw):
    return {k: wrap(v, []) for k, v in kw.items()}


class PageShellTests(unittest.TestCase):
    def test_contents_are_grouped_in_order_and_anchors_resolve(self):
        html = _render(_data(noldus_summary={}, operating_system={}, cpu={}, shares={}))
        self.assertLess(html.index('id="g-NVC"'), html.index('id="g-Software"'))
        self.assertLess(html.index('id="g-Software"'), html.index('id="g-Hardware"'))
        self.assertLess(html.index('id="g-Hardware"'), html.index('id="g-Network"'))
        checker = _Checker()
        checker.feed(html)
        self.assertEqual(checker.errors, [])
        self.assertTrue(checker.hrefs)
        self.assertTrue(checker.hrefs <= checker.ids, checker.hrefs - checker.ids)

    def test_report_health_comes_first_and_summarises_the_run(self):
        html = _render(_data(operating_system={}, cpu={}, shares={}))
        self.assertLess(html.index('id="s-report_health"'), html.index('id="s-operating_system"'))
        self.assertIn("<th>Elevated (administrator)</th><td>No</td>", html)
        self.assertIn("Cpu (3.2 s)", html)
        self.assertIn("<th>Total collection time</th><td>4 s</td>", html)
        self.assertIn("Run NVC as administrator", html)

    def test_absent_sections_are_neither_listed_nor_rendered(self):
        html = _render(_data(cpu={}))
        self.assertNotIn('id="s-shares"', html)
        self.assertNotIn('href="#s-shares"', html)
        self.assertNotIn('id="g-Network"', html)

    def test_partial_section_shows_its_error_and_is_counted(self):
        html = _render({"cpu": {"status": "partial", "error": "WMI down"}})
        self.assertIn('class="bad">This section failed: WMI down', html)
        self.assertIn("<th>Partial sections</th><td>Cpu</td>", html)

    def test_notes_are_printed_under_the_section(self):
        html = _render({"cpu": wrap({}, ["cache: timed out after 30 s"])})
        self.assertIn('<p class="notes"><em>cache: timed out after 30 s</em></p>', html)
        self.assertIn("<th>Sections with notes</th><td>1: Cpu</td>", html)

    def test_empty_sections_are_counted(self):
        html = _render(_data(operating_system=None))
        self.assertIn("<th>Empty sections</th><td>1: Operating System</td>", html)

    def test_a_render_that_raises_does_not_sink_the_page(self):
        def boom(d, c):
            raise ValueError("bad data")
        with patch.object(registry, "SECTIONS", (_fake("cpu", "Hardware", render=boom),)):
            html = render_html.render(META, _data(cpu={}), {"redact": True})
        self.assertIn("Could not render this section.", html)

    def test_redaction_masks_payload_and_header_machine_name(self):
        html = _render(_data(cpu={"Serial Number": "ABCDEFGH12"}))
        self.assertNotIn("ABCDEFGH12", html)
        self.assertNotIn("WDGS-BH0020", html)
        self.assertIn("<th>Redaction</th><td>Enabled</td>", html)
        html = _render(_data(cpu={"Serial Number": "ABCDEFGH12"}), {"redact": False})
        self.assertIn("ABCDEFGH12", html)
        self.assertIn("WDGS-BH0020", html)

    def test_header_carries_version_and_time(self):
        html = _render(_data(cpu={}))
        self.assertIn("NVC 2.3.0", html)
        self.assertIn("2026-09-24T10:00:00", html)
        self.assertIn("<title>NVC PC Report", html)
