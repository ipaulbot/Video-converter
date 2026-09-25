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
        "id": "record-a-webcam",
        "title": "Record From a Webcam",
        "blocks": [
            {"type": "para", "text": (
                "The Multi-Source Recorder captures up to four cameras or streams. One USB "
                "webcam is the simplest case.")},
            {"type": "steps", "items": [
                "Open the Multi-Source Recorder tab and click Video Settings.",
                "In row 1, open the Video device list and pick your camera by its Windows "
                "name. If it is missing, choose Refresh USB devices...",
                "Pick a microphone in Audio device, or No Audio. Leave Frame rate and "
                "Resolution at the detected values. If detection failed, leave Resolution "
                "at Auto and choose a frame rate the camera supports.",
                "Click OK. Back on the tab, choose Separate videos and a File location.",
                "Leave Timer blank, then click Start Recording in the footer. Click Stop "
                "Recording when you are done.",
            ]},
            {"type": "para", "text": (
                "The file is written to the File location as "
                "Video_<Video name>_<timestamp>.mp4. In Video Settings, use Save as... to save "
                "the setup as a preset so the next session is one Load away.")},
        ],
    },
    {
        "id": "review-a-recording",
        "title": "Review a Recording",
        "blocks": [
            {"type": "steps", "items": [
                "In Converted Files, select a file and click Play, or right-click it and choose "
                "Play in Media Player. You can also open the Media Player tab and click Load on "
                "a panel.",
                "Press Space to play or pause, Left and Right to step one frame, "
                "Shift+Left and Shift+Right to jump 5 seconds.",
                "Press F for fullscreen and Escape to come back.",
                "Set Panels to 1, 2 or 4. Use 2 or 4 to compare recordings side by side; each "
                "panel has its own offset to line up clips that started at different times.",
            ]},
            {"type": "note", "items": [
                "The Media Player tab is hidden by default. Play in Media Player shows it "
                "for this session; tick it in Settings, Tools tab, to keep it.",
            ]},
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
