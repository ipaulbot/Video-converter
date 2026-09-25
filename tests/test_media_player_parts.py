import unittest

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QLabel

from ui.media_player_parts import FullscreenHost


class FullscreenHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_take_and_release_round_trip_widgets_in_order(self):
        host = FullscreenHost()
        self.addCleanup(host.close)
        first, second = QLabel("a"), QLabel("b")
        host.take(first)
        host.take(second)
        self.assertIs(first.parent(), host)
        released = host.release()
        self.assertEqual(released, [first, second])
        self.assertIsNone(first.parent())

    def test_escape_and_f_request_exit(self):
        host = FullscreenHost()
        self.addCleanup(host.close)
        requests = []
        host.exit_requested.connect(lambda: requests.append(1))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_F, Qt.NoModifier))
        host.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.NoModifier))
        self.assertEqual(len(requests), 2)
