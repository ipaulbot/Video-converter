"""Which jobs may run together, and the one status line every footer shows.

The main window owns the facts (is a recording running? how many conversions?
is the folder monitor on? is NVC locked?) and packs them into an `Activity`.
The rules here are pure functions over that snapshot so they can be read --
and tested -- in one place:

1. Switching tabs never stops or pauses anything.
2. Recording is exclusive with the other ffmpeg jobs (conversion, folder
   monitoring, lossless edits).
3. A conversion or a running monitor blocks recording only; the rest of the
   recorder stays usable.
4. Viewing (Media Player, PC Report) is never blocked and blocks nothing.
5. Locked blocks every start action.
"""
from dataclasses import dataclass

from PyQt5.QtCore import QCoreApplication


def _tr(source: str) -> str:
    """Translate under the stable "Workflow" context (plain literals only)."""
    return QCoreApplication.translate("Workflow", source)


RECORDING_PHASES_ACTIVE = ("starting", "recording", "stopping")

_TEAL = "#43a296"
_GREEN = "#00cc00"
_AMBER = "#FFD700"
_RED = "#dc3545"
_GREY = "#888888"


@dataclass(frozen=True)
class Activity:
    """A snapshot of what NVC is doing right now."""

    locked: bool = False
    # "", "starting", "recording", "stopping" or "failed".
    recording_phase: str = ""
    # Number of conversions in flight (the queue's active count).
    converting: int = 0
    # The converter's folder monitor is on.
    monitoring: bool = False

    @property
    def recording(self) -> bool:
        return self.recording_phase in RECORDING_PHASES_ACTIVE

    @property
    def converting_or_monitoring(self) -> bool:
        return self.converting > 0 or self.monitoring

    @property
    def busy(self) -> bool:
        return self.recording or self.converting_or_monitoring


def blocked_reason(activity: Activity, action: str) -> str:
    """Why `action` may not start now, or "" when it may.

    Actions: "convert" (start a conversion or the folder monitor), "record",
    "lossless_edit". Anything else is viewing and is never blocked.
    """
    if action not in ("convert", "record", "lossless_edit"):
        return ""
    if activity.locked:
        return _tr("NVC is locked. Unlock it first.")
    if action == "record" and activity.converting_or_monitoring:
        return _tr("Recording is unavailable while conversion is running.")
    if action == "convert" and activity.recording:
        return _tr("Conversion is unavailable while a recording is active.")
    if action == "lossless_edit" and activity.recording:
        return _tr("Lossless edits are unavailable while a recording is active.")
    return ""


def status_parts(activity: Activity) -> list:
    """The words of the status line, in a fixed order; ["Idle"] when nothing runs."""
    parts = []
    if activity.locked:
        parts.append(_tr("Locked"))
    phase_words = {
        "starting": _tr("Starting recording"),
        "recording": _tr("Recording"),
        "stopping": _tr("Stopping recording"),
        "failed": _tr("Recording failed"),
    }
    if activity.recording_phase in phase_words:
        parts.append(phase_words[activity.recording_phase])
    if activity.converting > 0:
        parts.append(_tr("Converting"))
    if activity.monitoring:
        parts.append(_tr("Monitoring"))
    return parts or [_tr("Idle")]


def status_dot_color(activity: Activity) -> str:
    if activity.locked:
        return _GREY
    if activity.recording_phase == "failed" and not activity.busy:
        return _RED
    if activity.recording or activity.converting > 0:
        return _GREEN
    if activity.monitoring:
        return _AMBER
    return _TEAL


def status_markup(activity: Activity) -> str:
    """Rich text for the footer: `Status: A · B <dot>`."""
    text = " · ".join(status_parts(activity))
    return _tr("Status: %(text)s <font color='%(color)s'>●</font>") % {
        "text": text,
        "color": status_dot_color(activity),
    }
