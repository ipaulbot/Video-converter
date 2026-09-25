"""Runs the real report on this machine. Opt in with NVC_PC_REPORT_LIVE=1; skipped otherwise."""
import os
import unittest

from pc_report import orchestrator, registry, render_html


@unittest.skipUnless(os.environ.get("NVC_PC_REPORT_LIVE") == "1", "set NVC_PC_REPORT_LIVE=1 to run the live report")
class LiveReportTests(unittest.TestCase):
    def test_every_section_collects_and_renders(self):
        meta, data, errors = orchestrator.run_all({})
        self.assertEqual(set(data), {s.key for s in registry.SECTIONS})
        self.assertEqual(errors, {}, errors)
        html = render_html.render(meta, data, {"redact": True})
        empty = []
        for section in registry.SECTIONS:
            body = html.split(f'id="s-{section.key}"', 1)[-1].split("<h2", 1)[0]
            if render_html.is_empty_body(body):
                empty.append(section.title)
        # Sections that can legitimately be empty on a desktop without the hardware:
        allowed_empty = {"Printers", "Shares", "Sensors", "Ports", "Virtual Machine"}
        self.assertLessEqual(set(empty) - allowed_empty, set(), f"unexpectedly empty: {empty}")
        out = os.path.join(os.environ.get("TEMP", "."), "nvc_live_pc_report.html")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"\nlive report written to {out} in {meta['total_seconds']:.1f} s")
