"""Local-socket transport for NVC's command-line switches.

The running NVC owns a `QLocalServer` (a named pipe on Windows). A second
`NVC.exe /R` connects to it, sends the parsed request as one JSON line, waits
for one reply line and exits with the reply's verdict. See
`utils/command_line.py` for the switches and `VideoConverterApp.run_command_request`
for what they do.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

from utils.command_line import CommandRequest

logger = logging.getLogger(__name__)

COMMAND_SERVER_NAME = "NVC_CommandServer"
_LINGER_MS = 5000
_REPLY_OK = "ok"
_REPLY_ERROR = "error"

Handler = Callable[[CommandRequest], tuple[bool, str]]


class CommandServer(QObject):
    """Listens for command requests and answers each with the handler's verdict."""

    def __init__(self, handler: Handler, server_name: str = COMMAND_SERVER_NAME, parent=None):
        super().__init__(parent)
        self._handler = handler
        self._name = server_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept)

    def start(self) -> bool:
        # A crashed instance leaves its pipe registered; take it over.
        QLocalServer.removeServer(self._name)
        if not self.server.listen(self._name):
            logger.error("Command server could not listen on %s: %s", self._name, self.server.errorString())
            return False
        return True

    def close(self):
        self.server.close()
        QLocalServer.removeServer(self._name)

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                return
            socket.readyRead.connect(lambda sock=socket: self._read(sock))
            socket.disconnected.connect(socket.deleteLater)
            if socket.canReadLine():
                self._read(socket)

    def _read(self, socket: QLocalSocket):
        if not socket.canReadLine():
            return
        line = bytes(socket.readLine()).decode("utf-8", "replace").strip()
        try:
            request = CommandRequest.from_json(line)
            ok, message = self._handler(request)
        except Exception as exc:  # the caller must always get an answer
            logger.exception("Command request failed")
            ok, message = False, f"{type(exc).__name__}: {exc}"
        verdict = _REPLY_OK if ok else _REPLY_ERROR
        socket.write(f"{verdict}\t{message}\n".encode())
        socket.flush()
        # The client closes once it has read the reply. Disconnecting here would
        # race it: on Windows DisconnectNamedPipe discards data the other end has
        # not read yet. A parented timer covers a client that never disconnects.
        linger = QTimer(socket)
        linger.setSingleShot(True)
        linger.timeout.connect(socket.disconnectFromServer)
        linger.start(_LINGER_MS)


def send_command(
    request: CommandRequest,
    server_name: str = COMMAND_SERVER_NAME,
    timeout_ms: int = 3000,
) -> tuple[bool, str]:
    """Deliver `request` to the running NVC. Blocking; meant for the short-lived CLI process."""
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(timeout_ms):
        return False, "NVC is not running (no command server): " + socket.errorString()
    socket.write((request.to_json() + "\n").encode("utf-8"))
    socket.flush()
    # waitForBytesWritten reports False when flush() already emptied the buffer,
    # so only wait while something is still pending.
    if socket.bytesToWrite() > 0 and not socket.waitForBytesWritten(timeout_ms):
        return False, "could not send the command to NVC: " + socket.errorString()
    while not socket.canReadLine():
        if not socket.waitForReadyRead(timeout_ms):
            return False, "NVC did not answer in time: " + socket.errorString()
    line = bytes(socket.readLine()).decode("utf-8", "replace").rstrip("\r\n")
    socket.disconnectFromServer()
    verdict, _tab, message = line.partition("\t")
    return verdict == _REPLY_OK, message
