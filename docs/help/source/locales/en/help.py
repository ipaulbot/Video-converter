"""English content for the full Help manual.

Block grammar (shared by every manual and locale):

    {"type": "para",   "text": str}
    {"type": "steps",  "items": [str, ...]}      auto-numbered
    {"type": "note",   "items": [str, ...]}      bulleted callout
    {"type": "figure", "fig_id": "FIG-NN"}
    {"type": "code",   "lines": [str, ...]}
    {"type": "table",  "headers": (str, str), "rows": [(str, str), ...]}

Every chapter carries a stable "id" separate from its display "title". Anchors
and cross-references derive from the id, so retitling or translating a chapter
never breaks a link.
"""
from __future__ import annotations

CHAPTERS: list[dict] = [
    {
        "id": "introduction",
        "title": "Introduction",
        "blocks": [
            {"type": "para", "text": (
                "NVC is a Windows video conversion utility built around FFmpeg. It can watch a "
                "source folder, convert supported media into your chosen output format, inspect "
                "media metadata, keep logs, generate PC support reports, and optionally clean up "
                "original files after conversion.")},
            {"type": "figure", "fig_id": "FIG-00"},
            {"type": "note", "items": [
                "Overwrite policy: NVC never overwrites an already converted video. If the "
                "destination already contains video.mp4, the next output becomes video (1).mp4, "
                "then video (2).mp4 -- the same style web browsers use for duplicate downloads.",
            ]},
        ],
    },
    {
        "id": "quick-start",
        "title": "Quick Start",
        "blocks": [
            {"type": "para", "text": "Six steps from a fresh install to a converted file."},
            {"type": "steps", "items": [
                "Open Settings from the menu.",
                "Choose a Source Folder. This is where new videos will be watched or scanned.",
                "Choose a Destination Folder. Converted videos are written here.",
                "Select the desired output format, codec, bitrate, size, and optional GIF settings.",
                "Click Start to begin monitoring the source folder.",
                "Add or drop supported videos into the source folder. NVC queues and converts "
                "them automatically.",
            ]},
            {"type": "figure", "fig_id": "FIG-01"},
        ],
    },
    {
        "id": "main-window",
        "title": "Main Window Overview",
        "blocks": [
            {"type": "para", "text": (
                "The main window is organised into tabs, with a shared preview panel and a "
                "status footer.")},
            {"type": "table", "headers": ("Area", "What it does"), "rows": [
                ("Conversion Log",
                 "Shows FFmpeg output, progress messages, warnings, and completion results."),
                ("Converted Files",
                 "Tracks queued, processing, successful, and failed conversions, and links "
                 "converted-file logs."),
                ("Inspection",
                 "Drag a media file here to view the FFprobe summary and raw JSON metadata."),
                ("PC Report",
                 "Generates a detailed system report covering software, drivers, devices, "
                 "codecs, networking, and NVC-related components."),
                ("Lossless Editor",
                 "Trim, remux, merge, extract audio, or remove audio using FFmpeg stream-copy "
                 "operations that avoid re-encoding where the source and container allow it."),
                ("Multi-Source Recorder",
                 "Records up to four FFmpeg sources, including RTSP and HTTP streams or Windows "
                 "DirectShow inputs such as video=Camera Name."),
                ("Preview Panel",
                 "Shows a thumbnail or video preview when a file is selected or dropped."),
                ("Menu",
                 "Access to settings, help, info, PC reports, and extra tools."),
            ]},
        ],
    },
    {
        "id": "converting-files",
        "title": "Converting Files",
        "blocks": [
            {"type": "para", "text": (
                "When monitoring is active, NVC watches the source folder for new supported "
                "videos. Existing files in the source folder are scanned when monitoring starts. "
                "Files can also be dragged directly into the app.")},
            {"type": "para", "text": (
                "NVC protects existing converted files. If a converted output name already "
                "exists, NVC chooses the next available browser-style filename:")},
            {"type": "code", "lines": [
                "Session.mp4",
                "Session (1).mp4",
                "Session (2).mp4",
            ]},
            {"type": "para", "text": (
                "NVC accepts common video formats including MP4, AVI, WMV, MKV, FLV, WebM, MOV, "
                "MPEG, MPG, M4V, 3GP, TS, VOB, RM, RMVB, ASF, M2TS, MTS, OGV, DIVX, DV and F4V.")},
            {"type": "figure", "fig_id": "FIG-03"},
        ],
    },
    {
        "id": "conversion-settings",
        "title": "Conversion Settings",
        "blocks": [
            {"type": "figure", "fig_id": "FIG-02"},
            {"type": "table", "headers": ("Setting", "Guidance"), "rows": [
                ("Output Format",
                 "The container to write, such as MP4 or GIF. MP4 is usually the safest "
                 "general-purpose choice."),
                ("Video Codec",
                 "libx264 is widely compatible. HEVC/H.265 can create smaller files but may not "
                 "play everywhere. NVC maps HEVC to the correct FFmpeg encoder."),
                ("Audio Codec",
                 "AAC is the most compatible default for MP4 output."),
                ("Video Bitrate",
                 "Use Auto unless you need a specific file size or quality target. Higher "
                 "bitrate means larger files and usually better quality."),
                ("Video Size",
                 "Use Auto to preserve the original size. Choose a smaller size to reduce file "
                 "size."),
                ("Frame Rate",
                 "Use Auto to preserve the source frame rate. Set this only when you need a "
                 "specific playback rate."),
                ("Keyframe Interval",
                 "Advanced. Useful for streaming, scrubbing, or compatibility workflows. Leave "
                 "at 0 unless you know the GOP interval you need."),
                ("Copy Only",
                 "Remuxes streams without re-encoding. Fast, but it can fail if the selected "
                 "container does not support the source streams."),
                ("Custom FFmpeg Flags",
                 "Advanced users can append FFmpeg arguments. Use carefully, because invalid "
                 "flags can break conversion."),
            ]},
        ],
    },
    {
        "id": "gpu-encoding",
        "title": "GPU Encoding",
        "blocks": [
            {"type": "para", "text": (
                "If enabled, NVC attempts to use a supported GPU encoder for NVIDIA, AMD or "
                "Intel hardware. GPU encoding can be much faster than CPU encoding, but the "
                "available codecs depend on your installed GPU drivers and FFmpeg build.")},
            {"type": "code", "lines": [
                "H.264 GPU encoders:  h264_nvenc   h264_amf   h264_qsv",
                "HEVC  GPU encoders:  hevc_nvenc   hevc_amf   hevc_qsv",
            ]},
            {"type": "note", "items": [
                "If the selected GPU encoder is unavailable, NVC falls back to CPU encoding "
                "where possible.",
                "Detection runs once per session and is cached. If you install new GPU drivers, "
                "restart NVC so it re-detects the available encoders.",
            ]},
        ],
    },
    {
        "id": "gif-export",
        "title": "GIF Export",
        "blocks": [
            {"type": "para", "text": (
                "GIF output can use a two-pass palette workflow for better colour quality. You "
                "can adjust frame rate, maximum width, looping, and quick mode. A lower frame "
                "rate and a smaller width both reduce file size.")},
            {"type": "note", "items": [
                "GIF files grow quickly. For long clips, convert to MP4 instead.",
            ]},
        ],
    },
    {
        "id": "text-overlays",
        "title": "Text Overlays",
        "blocks": [
            {"type": "para", "text": (
                "NVC can add overlays such as elapsed time, recorded time, recorded date and "
                "time, remaining time, or CRTV-style recording labels. Overlays require video "
                "filtering, so they may reduce GPU compatibility and conversion speed.")},
        ],
    },
    {
        "id": "original-files",
        "title": "Original File Handling",
        "blocks": [
            {"type": "table", "headers": ("Option", "Behaviour"), "rows": [
                ("Keep Originals",
                 "The original file remains in place after conversion."),
                ("Delete After Conversion",
                 "NVC deletes the original immediately, or schedules deletion after the "
                 "retention period."),
                ("Retention Days",
                 "0 to 30 days. NVC stores pending deletions on disk, so overdue files are "
                 "processed after a restart."),
                ("Backup Folder",
                 "Moves originals to a backup folder instead of deleting them."),
            ]},
            {"type": "note", "items": [
                "Keep originals until you have confirmed the converted files play correctly.",
            ]},
        ],
    },
    {
        "id": "media-inspection",
        "title": "Media Inspection",
        "blocks": [
            {"type": "para", "text": (
                "The Inspection tab uses FFprobe to show a readable summary and the detailed "
                "JSON metadata. The summary includes duration, file size, bitrate, streams, "
                "codecs, dimensions, frame rate, audio details, and keyframe estimates.")},
            {"type": "figure", "fig_id": "FIG-04"},
        ],
    },
    {
        "id": "pc-report",
        "title": "PC Report Tool",
        "blocks": [
            {"type": "para", "text": (
                "The PC Report tool gathers system information to help with support and "
                "troubleshooting. It covers the operating system, updates, installed programs, "
                "security status, hardware, network, services, processes, environment details, "
                "printers, drivers, codecs, and NVC-specific information.")},
            {"type": "figure", "fig_id": "FIG-05"},
            {"type": "note", "items": [
                "Privacy: PC reports can include sensitive machine details. With redaction "
                "enabled, NVC masks common sensitive values such as licence keys, serial "
                "numbers, MAC addresses and user profile paths. Review any report before "
                "sharing it outside your organisation.",
                "Some Windows collectors -- drivers, devices, network connections and "
                "processes -- can take a while on large systems.",
            ]},
        ],
    },
    {
        "id": "lossless-editor",
        "title": "Lossless Editor",
        "blocks": [
            {"type": "para", "text": (
                "The Lossless Editor tab provides FFmpeg stream-copy tools. These operations are "
                "fast because they avoid re-encoding wherever possible.")},
            {"type": "figure", "fig_id": "FIG-06"},
            {"type": "table", "headers": ("Operation", "What it does"), "rows": [
                ("Trim Losslessly",
                 "Cuts a section between start and end timestamps using stream copy."),
                ("Remux",
                 "Rewraps media into another container such as MP4, MKV, MOV or AVI."),
                ("Extract Audio",
                 "Writes the first audio stream to an audio-only file."),
                ("Remove Audio",
                 "Writes a silent, video-only copy."),
                ("Merge Losslessly",
                 "Joins compatible clips using the FFmpeg concat demuxer."),
            ]},
            {"type": "note", "items": [
                "Lossless operations need compatible codecs and containers. If FFmpeg fails, the "
                "source streams may need re-encoding, or a different output container.",
                "A lossless trim can only cut on a keyframe, so the actual start may shift "
                "slightly earlier than the timestamp you enter.",
            ]},
        ],
    },
    {
        "id": "multi-source-recorder",
        "title": "Multi-Source Recorder",
        "blocks": [
            {"type": "para", "text": (
                "The Multi-Source Recorder tab is a lightweight recorder for up to four FFmpeg "
                "inputs. Enter one source per row and enable the rows you want to record.")},
            {"type": "figure", "fig_id": "FIG-07"},
            {"type": "steps", "items": [
                "Use RTSP, HTTP or file URLs directly, for example rtsp://192.168.1.10/stream.",
                "Use Windows DirectShow input strings for local capture devices, for example "
                "video=Camera Name.",
                "Choose copy mode for compatible streams, or h264 mode when the source needs "
                "encoding.",
                "Open Video Settings to choose a DirectShow microphone for each source. Mute "
                "or Volume 0 records that source without audio; lower volume values reduce "
                "the recorded audio gain. Without a microphone, a file or RTSP source in "
                "h264 mode keeps its own sound track.",
                "Choose Separate videos to write one file per source, or Combined grid to "
                "write one file whose audio comes from the first enabled, unmuted row with "
                "a selected microphone.",
                "Use Load to apply a preset, Set to overwrite the selected preset, Save as... "
                "to create one, and Delete to remove one. An asterisk marks settings changed "
                "since the selected preset was loaded or saved.",
                "Leave duration blank to record until you press Stop.",
            ]},
            {"type": "note", "items": [
                "If a saved microphone is not connected, it appears as (not found). NVC keeps "
                "the saved name and retries an early audio-device failure as video-only so the "
                "camera recording is not lost.",
            ]},
        ],
    },
    {
        "id": "troubleshooting",
        "title": "Troubleshooting",
        "blocks": [
            {"type": "table", "headers": ("Problem", "What to try"), "rows": [
                ("Missing FFmpeg or FFprobe",
                 "Make sure ffmpeg.exe and ffprobe.exe are present alongside the app files."),
                ("Conversion fails immediately",
                 "Check the conversion log. Invalid codec and container combinations, and "
                 "custom FFmpeg flags, are the common causes."),
                ("Output file already exists",
                 "NVC creates a numbered filename automatically. Check the destination folder "
                 "for (1), (2), and so on."),
                ("GPU option does not work",
                 "Update your GPU drivers, confirm FFmpeg supports your encoder, or disable GPU "
                 "encoding to fall back to the CPU."),
                ("App appears idle after dropping a file",
                 "Confirm the app is unlocked, monitoring is started, and the file extension is "
                 "supported."),
                ("PC report is slow",
                 "Some Windows collectors take time on large systems. Let it finish."),
                ("Something failed with no message",
                 "Set the NVC_LOG_LEVEL environment variable to DEBUG and reproduce the "
                 "problem. NVC then records the full traceback for errors it would otherwise "
                 "handle quietly."),
            ]},
            {"type": "para", "text": (
                "NVC stores logs in its configured log folder, under the application data "
                "location unless the app configuration changes it.")},
        ],
    },
    {
        "id": "best-practices",
        "title": "Best Practices",
        "blocks": [
            {"type": "steps", "items": [
                "Use a dedicated source folder and destination folder.",
                "Keep originals until you have confirmed the converted files play correctly.",
                "Use MP4 with H.264 and AAC for the broadest compatibility.",
                "Use HEVC only when smaller files matter and the target players support it.",
                "Review PC reports before sharing them.",
                "Keep custom FFmpeg flags simple, and test them on a small file first.",
            ]},
        ],
    },
    {
        "id": "faq",
        "title": "Frequently Asked Questions",
        "blocks": [
            {"type": "table", "headers": ("Question", "Answer"), "rows": [
                ("Will NVC overwrite my converted videos?",
                 "No. NVC creates a numbered filename when an output already exists."),
                ("Can I convert files while monitoring is stopped?",
                 "Dropped files may be queued and processed when monitoring starts, depending on "
                 "where they are dropped. Files can also be force-converted through the "
                 "drag-and-drop paths meant for manual conversion."),
                ("Why did my HEVC file fail to play somewhere?",
                 "HEVC is efficient but less universally supported than H.264. If compatibility "
                 "matters, use H.264."),
                ("Where are logs stored?",
                 "In the configured log folder, typically under the application data location."),
                ("Can I run two copies of NVC at once?",
                 "No. NVC allows a single instance, so two copies cannot process the same "
                 "source folder."),
            ]},
        ],
    },
]
