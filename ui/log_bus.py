from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from collections import deque
from threading import Lock
from typing import List


class LogBus(QObject):
    lines_ready = pyqtSignal(list)

    def __init__(self, maxlen: int = 5000, parent=None):
        super().__init__(parent)
        self._buf = deque(maxlen=maxlen)
        self._lock = Lock()

    @pyqtSlot(str)
    def append(self, line: str) -> None:
        try:
            with self._lock:
                self._buf.append(line)
        except Exception:
            pass

    def drain(self, max_items: int = 500) -> List[str]:
        out: List[str] = []
        try:
            with self._lock:
                for _ in range(min(max_items, len(self._buf))):
                    out.append(self._buf.popleft())
        except Exception:
            return out
        return out

    def start_delivery(self, receiver_slot, interval_ms: int = 75):
        """Periodically deliver accumulated lines to the provided slot.
        Uses a QTimer to batch updates; receiver_slot should append to the UI.
        """
        from PyQt5.QtCore import QTimer
        if not hasattr(self, '_timer') or self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(lambda: self._emit_batched(receiver_slot))
        self._timer.stop()
        self._timer.start(max(10, int(interval_ms)))

    def _emit_batched(self, receiver_slot):
        lines = self.drain(500)
        if not lines:
            return
        try:
            receiver_slot(lines)
        except Exception:
            try:
                self.lines_ready.emit(lines)
            except Exception:
                pass
