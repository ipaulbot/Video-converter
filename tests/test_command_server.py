import threading
import time
import unittest
from unittest.mock import patch

from PyQt5.QtNetwork import QLocalServer
from PyQt5.QtWidgets import QApplication

from ui.command_server import CommandServer, send_command
from utils.command_line import CommandRequest, parse_command_switches


class CommandServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.server_name = f"NVC_Test_{id(self)}_{int(time.time() * 1000)}"

    def _send_in_thread(self, request, timeout_ms=3000):
        """Run the blocking client off the GUI thread so the server can answer."""
        result = {}

        def run():
            result["reply"] = send_command(request, server_name=self.server_name, timeout_ms=timeout_ms)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while thread.is_alive() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(thread.is_alive(), "client did not finish")
        return result["reply"]

    def test_request_reaches_the_handler_and_its_verdict_comes_back(self):
        seen = []

        def handler(request):
            seen.append(request)
            return True, "recording started"

        server = CommandServer(handler, server_name=self.server_name)
        try:
            self.assertTrue(server.start())
            ok, message = self._send_in_thread(parse_command_switches(["/C=Lab", "/R"]))
        finally:
            server.close()

        self.assertEqual(seen, [CommandRequest(record=True, preset="Lab")])
        self.assertEqual((ok, message), (True, "recording started"))

    def test_handler_failure_is_reported_to_the_caller(self):
        server = CommandServer(lambda _request: (False, "NVC is locked"), server_name=self.server_name)
        try:
            server.start()
            ok, message = self._send_in_thread(CommandRequest(record=True))
        finally:
            server.close()
        self.assertEqual((ok, message), (False, "NVC is locked"))

    def test_handler_exception_does_not_hang_the_caller(self):
        def handler(_request):
            raise RuntimeError("boom")

        server = CommandServer(handler, server_name=self.server_name)
        try:
            server.start()
            ok, message = self._send_in_thread(CommandRequest(record=True))
        finally:
            server.close()
        self.assertFalse(ok)
        self.assertIn("boom", message)

    def test_no_server_is_a_clear_error_not_a_hang(self):
        started = time.monotonic()
        ok, message = send_command(CommandRequest(record=True), server_name=self.server_name, timeout_ms=500)
        self.assertFalse(ok)
        self.assertIn("not running", message)
        self.assertLess(time.monotonic() - started, 3)

    def test_start_clears_a_stale_registration_before_listening(self):
        # On Unix a crashed instance leaves its socket file behind and listen()
        # would fail; QLocalServer.removeServer(name) clears it first.
        removed = []
        with patch.object(QLocalServer, "removeServer", staticmethod(lambda name: removed.append(name) or True)):
            server = CommandServer(lambda _request: (True, ""), server_name=self.server_name)
            try:
                self.assertTrue(server.start())
            finally:
                server.close()
        self.assertEqual(removed[0], self.server_name)

    def test_a_new_server_takes_over_after_the_previous_one_closed(self):
        first = CommandServer(lambda _request: (True, "first"), server_name=self.server_name)
        self.assertTrue(first.start())
        first.close()
        second = CommandServer(lambda _request: (True, "second"), server_name=self.server_name)
        try:
            self.assertTrue(second.start())
            ok, message = self._send_in_thread(CommandRequest(launch=True))
        finally:
            second.close()
        self.assertEqual((ok, message), (True, "second"))


if __name__ == "__main__":
    unittest.main()
