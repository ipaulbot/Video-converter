"""English content for the Quick Start Guide.

Same block grammar as help.py. This is a short, task-focused subset for someone
converting their first file; the full reference lives in the Help manual.
Chapters are authored separately rather than transcluded from help.py, so the
tone can stay imperative here without constraining the reference text.
"""
from __future__ import annotations

CHAPTERS: list[dict] = [
    {
        "id": "before-you-start",
        "title": "Before You Start",
        "blocks": [
            {"type": "para", "text": (
                "NVC converts video using FFmpeg. It needs two things before it can do anything: "
                "a source folder to watch, and a destination folder to write to.")},
            {"type": "note", "items": [
                "ffmpeg.exe and ffprobe.exe must sit alongside the application files. NVC reports "
                "them as missing at startup if they are not there.",
            ]},
            {"type": "figure", "fig_id": "FIG-00"},
        ],
    },
    {
        "id": "first-conversion",
        "title": "Your First Conversion",
        "blocks": [
            {"type": "steps", "items": [
                "Open Settings from the menu.",
                "Set a Source Folder -- the folder NVC watches for new video.",
                "Set a Destination Folder -- where converted video is written.",
                "Leave the output format at MP4 and the codecs at their defaults. These suit "
                "almost every case.",
                "Close Settings and click Start.",
                "Copy a video into the source folder. NVC queues it and converts it "
                "automatically.",
            ]},
            {"type": "figure", "fig_id": "FIG-01"},
            {"type": "para", "text": (
                "Progress appears in the conversion log. When the job finishes, the Converted "
                "Files tab records the result.")},
        ],
    },
    {
        "id": "safe-defaults",
        "title": "Settings Worth Knowing",
        "blocks": [
            {"type": "table", "headers": ("Setting", "Start with"), "rows": [
                ("Output Format", "MP4. The most widely playable container."),
                ("Video Codec", "libx264. Plays essentially everywhere."),
                ("Audio Codec", "AAC. The standard partner for MP4."),
                ("Video Bitrate", "Auto, unless you are targeting a specific file size."),
                ("Video Size", "Auto, to keep the original dimensions."),
                ("Original Files", "Keep Originals, until you trust the output."),
            ]},
            {"type": "note", "items": [
                "NVC never overwrites an existing output. A second conversion of video.mp4 "
                "becomes video (1).mp4, exactly like a repeated browser download.",
            ]},
        ],
    },
    {
        "id": "if-something-goes-wrong",
        "title": "If Something Goes Wrong",
        "blocks": [
            {"type": "steps", "items": [
                "Read the conversion log first. FFmpeg usually says exactly what it objected to.",
                "Check the app is unlocked and monitoring is started.",
                "Confirm the file extension is one NVC supports.",
                "If GPU encoding is on, turn it off and retry on the CPU.",
                "For a failure with no message at all, set the NVC_LOG_LEVEL environment "
                "variable to DEBUG and reproduce it. NVC then logs the full traceback.",
            ]},
            {"type": "para", "text": (
                "The Help manual covers every tab and setting in full, including the Lossless "
                "Editor, the Multi-Source Recorder, and the PC Report tool.")},
        ],
    },
]
