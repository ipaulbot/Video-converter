"""Bookkeeping for the conversion queue.

Deliberately free of Qt and of any UI: this is the part of the queue that can
be reasoned about and tested on its own. The main window keeps the widget
updates and owns the QThreadPool; it asks this class whether a file may be
converted and to remember what is in flight.

Before this existed the same state lived as four separate attributes on
VideoConverterApp -- `in_flight_conversions`, `conversion_workers`,
`per_file_logs` and `active_conversion_count` -- incremented in one method and
decremented in another, with `max(0, ...)` papering over any mismatch. Pairing
start() with finish() here means the count cannot drift, and keying
everything on the absolute path fixes a bug where two files with the same
basename in different folders overwrote each other's log.
"""
from __future__ import annotations

import os
from enum import Enum


class Admission(Enum):
    """Why a file was or was not accepted for conversion."""

    OK = "ok"
    LOCKED = "locked"                  # the app is locked and this is not forced
    DUPLICATE = "duplicate"            # already in flight
    NOT_RUNNING = "not_running"        # monitoring is stopped and this is not forced
    OUTSIDE_TIME = "outside_time"      # outside the configured conversion window

    @property
    def accepted(self) -> bool:
        return self is Admission.OK


class ConversionQueueState:
    """What is queued, what is running, and what may start."""

    def __init__(self):
        self._in_flight: set[str] = set()
        self._workers: dict[str, object] = {}
        self._logs: dict[str, list[str]] = {}
        # Files dropped into the Converted tab while idle, converted once
        # monitoring starts.
        self._manual: list[str] = []

    # -- admission ------------------------------------------------------
    def admit(self, file_path: str, *, locked: bool, running: bool,
              force: bool = False, within_allowed_time: bool = True) -> Admission:
        """Decide whether `file_path` may start converting.

        `force` covers a manual, explicit request -- a drag-and-drop onto the
        Converted tab -- which bypasses the lock and the not-running check but
        never the duplicate check, since converting the same file twice
        concurrently would have the two runs fight over the output name.
        """
        path = self.normalize(file_path)
        if locked and not force:
            return Admission.LOCKED
        if path in self._in_flight:
            return Admission.DUPLICATE
        if not running and not force:
            return Admission.NOT_RUNNING
        if not within_allowed_time:
            return Admission.OUTSIDE_TIME
        return Admission.OK

    # -- lifecycle ------------------------------------------------------
    def start(self, file_path: str, worker=None) -> str:
        """Record a conversion as in flight. Returns the normalized path."""
        path = self.normalize(file_path)
        self._in_flight.add(path)
        self._logs.setdefault(path, [])
        if worker is not None:
            self._workers[path] = worker
        return path

    def finish(self, file_path: str) -> list[str]:
        """Clear a conversion and return its buffered log lines.

        Safe to call for a path that was never started, or twice for the same
        path: the queue must not be corrupted by a duplicate completion
        signal.
        """
        path = self.normalize(file_path)
        self._in_flight.discard(path)
        self._workers.pop(path, None)
        return self._logs.pop(path, [])

    def log_line(self, file_path: str, message: str) -> None:
        """Buffer one log line against a conversion, for its per-file log."""
        self._logs.setdefault(self.normalize(file_path), []).append(message)

    def lines_for(self, file_path: str) -> list[str]:
        return list(self._logs.get(self.normalize(file_path), []))

    # -- queries --------------------------------------------------------
    @property
    def active_count(self) -> int:
        """How many conversions are in flight. Cannot go negative by design."""
        return len(self._in_flight)

    @property
    def is_converting(self) -> bool:
        return bool(self._in_flight)

    def is_in_flight(self, file_path: str) -> bool:
        return self.normalize(file_path) in self._in_flight

    def in_flight_paths(self) -> list[str]:
        return sorted(self._in_flight)

    def workers(self) -> list[object]:
        """Live workers, for cancelling on shutdown."""
        return list(self._workers.values())

    # -- the manual queue -----------------------------------------------
    def queue_manual(self, file_path: str) -> None:
        self._manual.append(self.normalize(file_path))

    def take_manual(self) -> list[str]:
        """Drain the manual queue, de-duplicated and in the order added."""
        pending = list(dict.fromkeys(self._manual))
        self._manual.clear()
        return pending

    @property
    def manual_count(self) -> int:
        return len(self._manual)

    # -- teardown -------------------------------------------------------
    def clear(self) -> None:
        self._in_flight.clear()
        self._workers.clear()
        self._logs.clear()
        self._manual.clear()

    @staticmethod
    def normalize(file_path: str) -> str:
        """Absolute path, so the same file named two ways is one entry.

        Everything is keyed on this rather than on the basename: two files
        called clip.mov in different folders are different conversions.
        """
        return os.path.abspath(str(file_path))
