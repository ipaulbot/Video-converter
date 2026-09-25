"""The figure catalog.

One entry per screenshot. Figure numbers are derived from the id, never
counted, so the printed caption and the id can never drift apart.

`capture_steps` is prose for whoever recaptures the shot by hand; it is not
used by the build. Keep it accurate -- it is the only record of how a given
screenshot was framed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Final

SCREENSHOTS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "screenshots"

FIGURES: Final[list[dict[str, str]]] = [
    {
        "id": "FIG-00",
        "filename": "fig-00-main-window.png",
        "caption": "The NVC main window, with the conversion log and preview panel.",
        "capture_steps": "Launch NVC with no job running. Full window, default size.",
    },
    {
        "id": "FIG-01",
        "filename": "fig-01-settings-general.png",
        "caption": "Settings, General tab: startup, Copy Only, tray and GPU options.",
        "capture_steps": ("Menu -> Settings. General tab as shipped. (Folders live on the "
                          "Folders tab, which shows the operator's own paths -- not captured.)"),
    },
    {
        "id": "FIG-02",
        "filename": "fig-02-settings-video.png",
        "caption": "Settings, Format tab: output format, codecs and presets.",
        "capture_steps": "Menu -> Settings. Format tab, output format set to mp4.",
    },
    {
        "id": "FIG-03",
        "filename": "fig-03-converted-files.png",
        "caption": "The Converted Files tab tracking queued and finished jobs.",
        "capture_steps": "Convert two short clips first so the list has rows.",
    },
    {
        "id": "FIG-04",
        "filename": "fig-04-inspection.png",
        "caption": "The Video Inspection Tool tab, ready for a file to be dropped.",
        "capture_steps": "Video Inspection Tool tab, Summary sub-tab, no file loaded.",
    },
    {
        "id": "FIG-05",
        "filename": "fig-05-pc-report.png",
        "caption": "The PC Report tab before a report is generated.",
        "capture_steps": ("PC Report tab as opened. Do not generate: a real report would show "
                          "this machine's name and hardware."),
    },
    {
        "id": "FIG-06",
        "filename": "fig-06-lossless-editor.png",
        "caption": "The Lossless Editor tab with its trim, remux and merge tools.",
        "capture_steps": "Lossless Editor tab as opened, no clip loaded.",
    },
    {
        "id": "FIG-07",
        "filename": "fig-07-multi-source-recorder.png",
        "caption": "The Multi-Source Recorder tab with two sources enabled.",
        "capture_steps": "Recorder tab, fill rows 1-2, enable both, do not start recording.",
    },
    {
        "id": "FIG-08",
        "filename": "fig-08-media-player.png",
        "caption": "The Media Player tab with a clip loaded in a single panel.",
        "capture_steps": ("Media Player tab, Panels set to 1, a short test clip loaded and "
                          "paused at about one second. Needs a real display: the video "
                          "surface is native, so the script grabs the screen region "
                          "under the window (widget.grab() sees black)."),
    },
    {
        "id": "FIG-09",
        "filename": "fig-09-recorder-video-settings.png",
        "caption": "The recorder's Video Settings dialog with two camera rows configured.",
        "capture_steps": ("Multi-Source Recorder tab -> Video Settings. Rows 1-2 set to USB "
                          "cameras with stand-in names (Camera A, Camera B; Microphone A, "
                          "Microphone B). Do not use real device names."),
    },
]

_ID_RE = re.compile(r"^FIG-(\d{2})$")

_BY_ID: Final[dict[str, dict[str, str]]] = {f["id"]: f for f in FIGURES}

KNOWN_FIGURE_IDS: Final[frozenset[str]] = frozenset(_BY_ID)


def figure(fig_id: str) -> dict[str, str]:
    try:
        return _BY_ID[fig_id]
    except KeyError:
        raise KeyError(
            f"unknown figure id {fig_id!r}; known ids are {sorted(_BY_ID)}"
        ) from None


def figure_number(fig_id: str) -> int:
    """Derive the printed figure number from the id, so they cannot diverge."""
    m = _ID_RE.match(fig_id)
    if not m:
        raise ValueError(f"malformed figure id {fig_id!r}; expected FIG-NN")
    return int(m.group(1))


def figure_label(fig_id: str) -> str:
    return f"Figure {figure_number(fig_id)}. {figure(fig_id)['caption']}"


def resolve_figure_path(fig_id: str, screenshots_dir: Path | None = None) -> Path | None:
    """Return the PNG path, or None when it has not been captured yet.

    An unknown id raises; a missing file does not. A screenshot that has not
    been taken should not break the build -- the builders draw a visible
    placeholder instead, which is what makes SHOTLIST.md actionable.
    """
    entry = figure(fig_id)
    base = screenshots_dir or SCREENSHOTS_DIR
    path = base / entry["filename"]
    return path if path.exists() else None
