"""Command-line switches that drive a running NVC, MediaRecorder-style.

The Observer XT's "external applications" feature runs a command when an
observation is opened, started, stopped and closed. MediaRecorder ships
`MRCmd.exe` for this; NVC accepts the same switch letters on its own
executable so those entries can be copied over unchanged:

    NVC.exe /E                launch NVC (or bring the running one forward)
    NVC.exe /R                start recording
    NVC.exe /S                stop recording
    NVC.exe /X                close NVC
    NVC.exe /C=<preset>       load a video preset (a name, or a path to its .json)
    NVC.exe /B=<base name>    set the recording file base name

Switches combine and always run in the order preset, base name, record,
stop, close, whatever order they appear in. `/`, `-` and `--` prefixes are
accepted, letters are case-insensitive, and values follow `=` or `:`.

This module is pure Python so it can be tested without Qt; the transport to
the running instance lives in `ui/command_server.py`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

SWITCH_HELP = (
    "NVC command-line switches (MediaRecorder MRCmd compatible):\n"
    "  /E             launch NVC or bring the running NVC forward\n"
    "  /R             start recording\n"
    "  /S             stop recording\n"
    "  /X             close NVC\n"
    "  /C=<preset>    load a video preset by name, or from a .json file\n"
    "  /B=<name>      set the recording file base name\n"
    "Switches combine, e.g.  NVC.exe /E /C=Lab1 /R"
)


class ParseError(ValueError):
    """A switch NVC does not understand, or a value switch without a value."""


class HelpRequested(ParseError):
    """`/?`, `/H` or `--help`: the message is the switch summary."""


@dataclass(frozen=True)
class CommandRequest:
    launch: bool = False
    record: bool = False
    stop: bool = False
    close: bool = False
    preset: str | None = None
    base_name: str | None = None

    def has_commands(self) -> bool:
        return any((self.launch, self.record, self.stop, self.close, self.preset, self.base_name))

    def needs_a_window(self) -> bool:
        """True when the request makes sense to launch NVC for."""
        return any((self.launch, self.record, self.preset, self.base_name))

    def steps(self) -> list[tuple[str, str | None]]:
        """(action, value) pairs in execution order."""
        steps: list[tuple[str, str | None]] = []
        if self.preset:
            steps.append(("preset", self.preset))
        if self.base_name:
            steps.append(("base_name", self.base_name))
        if self.record:
            steps.append(("record", None))
        if self.stop:
            steps.append(("stop", None))
        if self.close:
            steps.append(("close", None))
        return steps

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> CommandRequest:
        data = json.loads(text)
        return cls(
            launch=bool(data.get("launch")),
            record=bool(data.get("record")),
            stop=bool(data.get("stop")),
            close=bool(data.get("close")),
            preset=data.get("preset") or None,
            base_name=data.get("base_name") or None,
        )


_FLAG_SWITCHES = {"E": "launch", "R": "record", "S": "stop", "X": "close"}
_VALUE_SWITCHES = {"C": "preset", "B": "base_name"}


def _split_switch(argument: str) -> tuple[str, str | None]:
    """"/C=Lab 1" -> ("C", "Lab 1"); "/R" -> ("R", None)."""
    body = argument
    for prefix in ("--", "-", "/"):
        if body.startswith(prefix):
            body = body[len(prefix):]
            break
    else:
        raise ParseError(f"Unknown argument {argument!r}.\n{SWITCH_HELP}")
    for separator in ("=", ":"):
        if separator in body:
            letter, value = body.split(separator, 1)
            return letter.strip().upper(), value
    return body.strip().upper(), None


def parse_command_switches(argv: list[str]) -> CommandRequest:
    values: dict[str, object] = {}
    for argument in argv:
        if not argument.strip():
            continue
        letter, value = _split_switch(argument)
        if letter in ("?", "H", "HELP"):
            raise HelpRequested(SWITCH_HELP)
        if letter in _FLAG_SWITCHES:
            if value is not None:
                raise ParseError(f"/{letter} does not take a value.\n{SWITCH_HELP}")
            values[_FLAG_SWITCHES[letter]] = True
        elif letter in _VALUE_SWITCHES:
            if not value or not value.strip():
                raise ParseError(f"/{letter} needs a value, e.g. /{letter}=name.\n{SWITCH_HELP}")
            values[_VALUE_SWITCHES[letter]] = value.strip()
        else:
            raise ParseError(f"Unknown switch /{letter}.\n{SWITCH_HELP}")
    return CommandRequest(**values)  # type: ignore[arg-type]


def startup_action(request: CommandRequest, already_running: bool) -> str:
    """What main() should do with the parsed switches.

    "launch"          start the window (and apply the switches once it is up)
    "already_running" plain double-click while NVC runs: show the notice
    "send"            hand the switches to the running instance and exit
    "nothing"         /S or /X with no NVC running: nothing to stop or close
    """
    if not request.has_commands():
        return "already_running" if already_running else "launch"
    if already_running:
        return "send"
    return "launch" if request.needs_a_window() else "nothing"
