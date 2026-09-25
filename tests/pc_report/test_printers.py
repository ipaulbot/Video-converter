import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import printers as mod
from tests.pc_report import support

PR = [{"Name": "Microsoft Print to PDF", "DriverName": "Microsoft Print To PDF", "PortName": "PORTPROMPT:", "Default": True, "Shared": False,
       "ShareName": "", "Network": False, "Local": True, "PrinterStatus": 3, "Location": "", "WorkOffline": False, "Comment": "",
       "PrintProcessor": "winprint", "Priority": 1}]
SP = {"State": "Running", "StartMode": "Auto"}


class BuildTests(unittest.TestCase):
    def test_rows(self):
        data = mod.build(PR, SP)
        self.assertEqual(data["rows"][0]["Status"], "Idle")
        self.assertEqual(data["rows"][0]["Default"], "Yes")
        self.assertEqual(data["rows"][0]["Port Type"], "Virtual")
        self.assertEqual(data["rows"][0]["Error State"], "")
        self.assertEqual(data["rows"][0]["Extended Status"], "")
        rows = dict(data["groups"][0]["rows"])
        self.assertEqual(rows["Print Spooler"], "Running (Auto)")
        self.assertEqual(rows["Default Printer"], "Microsoft Print to PDF")

    def test_port_kind_classifies_supported_port_families(self):
        cases = {
            "WSD-b8136383": "WSD",
            "IP_192.168.1.20": "TCP/IP",
            "192.168.1.20": "TCP/IP",
            "printer.example.test": "TCP/IP",
            "_printer.example.test": "TCP/IP",
            r"\\PRINTSRV\HP": "Network share",
            "USB001": "USB",
            "USB": "USB",
            "LPT1": "Local",
            "COM3": "Local",
            "nul:": "Virtual",
            "PORTPROMPT:": "Virtual",
            "SHRFAX:": "Virtual",
            "FILE:": "Virtual",
            "Microsoft.Office.OneNote_123": "App",
            "OneNote_S-1-5-21-123": "App",
            "custom-port": "Other",
        }
        for port_name, expected in cases.items():
            with self.subTest(port_name=port_name):
                self.assertEqual(mod.port_kind(port_name), expected)

    def test_decodes_error_state_and_extended_status(self):
        printer = {
            **PR[0],
            "DetectedErrorState": 8,
            "ExtendedPrinterStatus": 7,
        }

        row = mod.build([printer], SP)["rows"][0]

        self.assertEqual(row["Error State"], "Jammed")
        self.assertEqual(row["Extended Status"], "Offline")


class PrivacyTests(unittest.TestCase):
    def _html(self, printers, spooler=SP):
        data = mod.build(printers, spooler)
        return mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

    def test_every_port_family_loses_its_host_address_or_identifier(self):
        guid = "b8136383-1826-454b-810e-0c4a05d5a2e0"
        ports = {
            "IP_203.0.113.20": "203.0.113.20",
            "203.0.113.21": "203.0.113.21",
            "queue.corp.example": "queue.corp.example",
            r"\\PRINTSRV\HP": "PRINTSRV",
            f"WSD-{guid}": guid,
            "OneNote_S-1-5-21-2734529186-23328706-2630127308-5137": "2734529186",
        }
        for port, sensitive in ports.items():
            with self.subTest(port=port):
                html = self._html([{**PR[0], "PortName": port, "Name": "Lab Printer"}])
                self.assertNotIn(sensitive, html)
                self.assertIn("Lab Printer", html)

    def test_local_ports_stay_readable(self):
        for port in ("USB001", "LPT1", "PORTPROMPT:", "nul:"):
            with self.subTest(port=port):
                self.assertIn(port, self._html([{**PR[0], "PortName": port}]))

    def test_default_and_offline_summaries_mask_network_queue_names(self):
        printers = [
            {**PR[0], "Name": r"\\PRINTSRV\HP LaserJet", "Default": True, "WorkOffline": False},
            {**PR[0], "Name": "queue.corp.example", "Default": False, "WorkOffline": True},
        ]

        html = self._html(printers)

        for sensitive in ("PRINTSRV", "queue.corp.example"):
            self.assertNotIn(sensitive, html)
        self.assertIn("HP LaserJet", html)
        self.assertIn("<th>Default Printer</th>", html)
        self.assertIn("<th>Offline</th>", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Print Spooler</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
