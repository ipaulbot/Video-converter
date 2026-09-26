"""English builder strings: the words the PDF and Word builders print themselves.

Figure captions live here too (the English ones are also the catalog entries
in figures.py, asserted equal by test_help_docs.py) so a translated manual
gets a translated caption rather than an English one under a Dutch page.
"""
from __future__ import annotations

STRINGS: dict = {
    "contents": "Contents",
    "note": "Note",
    "figure_label": "Figure %(n)d. %(caption)s",
    "version": "Version %(version)s",
    "language": "Language: %(tag)s",
    "missing_figure": "%(fig_id)s -- screenshot not captured (see SHOTLIST.md)",
    "toc_placeholder": "Open this document in Word to build the table of contents.",
    "titles": {
        "help": "Help",
        "quickstart": "Quick Start Guide",
    },
    "figure_captions": {
        "FIG-00": "The NVC main window, with the conversion log and preview panel.",
        "FIG-01": "Settings, General tab: startup, Copy Only, tray and GPU options.",
        "FIG-02": "Settings, Format tab: output format, codecs and presets.",
        "FIG-03": "The Video Converter tab: the Converted Files table above the conversion log.",
        "FIG-04": "The Media Player's Inspect panel beside the video, Summary sub-tab.",
        "FIG-05": "The PC Report tab before a report is generated.",
        "FIG-06": "The Lossless Editor tab with its trim, remux and merge tools.",
        "FIG-07": "The Multi-Source Recorder tab with two sources enabled.",
        "FIG-08": "The Media Player tab with a clip loaded in a single panel.",
        "FIG-09": "The recorder's Video Settings dialog with two camera rows configured.",
    },
}
