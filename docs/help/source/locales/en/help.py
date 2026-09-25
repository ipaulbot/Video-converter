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
                "NVC is a Windows video converter built around FFmpeg. It watches a source "
                "folder, converts supported media, inspects media information, records up to "
                "four sources, plays media side by side, generates a PC report, and can clean "
                "up original files after conversion.")},
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
                "On the Folders tab, choose the Source Folder.",
                "On the Folders tab, choose the Destination Folder.",
                "On the Format tab, choose the Output Format, Video Codec and Audio Codec. The "
                "defaults suit most cases.",
                "Click OK, and then click Start.",
                "Drop videos into the source folder.",
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
                 "Shows conversion messages, progress, warnings and results."),
                ("Converted Files",
                 "Lists queued, processing, successful and failed conversions."),
                ("Video Inspection Tool",
                 "Shows a summary and detailed media information for a selected file."),
                ("PC Report",
                 "Generates a PC report for support and troubleshooting."),
                ("Lossless Editor",
                 "Provides trim, remux, merge and audio stream-copy tools."),
                ("Multi-Source Recorder",
                 "Records up to four video sources."),
                ("Media Player",
                 "Plays media in one, two or four panels."),
                ("Preview Panel",
                 "Shows a preview of the current file or recorder layout."),
                ("Menu",
                 "Opens Info, Help, folders, Settings, Language, updates and Quit."),
            ]},
            {"type": "note", "items": [
                "PC Report, Lossless Editor and Media Player are hidden by default. Turn them "
                "on in Settings -- Tools. Play in Media Player shows the Media Player tab for "
                "the current session even when it is switched off.",
                "The Menu contains Info, Help, Open Source Folder, Open Destination Folder, "
                "Open Backup Folder, Settings, Language, Check for Updates and Quit.",
                "The footer has the Start/Stop button, a lock icon, a file picker, a broom and "
                "a status label. On the recorder tab the button reads Start Recording or Stop "
                "Recording. The lock icon locks settings, and the Start button then reads "
                "Locked. The file picker selects media files to convert, and the broom clears "
                "the log.",
                "Clicking X closes NVC by default. Clear "
                "\"Close on X (don't minimize to tray)\" in Settings -- General to minimise "
                "to the system tray instead. The tray menu has Show and Quit. Only one copy "
                "of NVC can run at a time.",
            ]},
        ],
    },
    {
        "id": "converting-files",
        "title": "Converting Files",
        "blocks": [
            {"type": "para", "text": (
                "When monitoring is active, NVC watches the source folder for new supported "
                "videos. It also scans existing files in that folder when monitoring starts.")},
            {"type": "para", "text": (
                "You can drag files onto Conversion Log, Converted Files or Video Inspection "
                "Tool. You can also use the file picker in the footer to select media files "
                "to convert.")},
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
            {"type": "para", "text": (
                "Settings has six tabs: General, Folders, Deletion, Format, Time and Tools. "
                "Default restores every value, OK saves, and Cancel discards changes.")},
            {"type": "figure", "fig_id": "FIG-02"},
            {"type": "para", "text": "The General tab controls application behaviour and GPU encoding."},
            {"type": "table", "headers": ("Setting", "Guidance"), "rows": [
                ("Auto Run on Startup",
                 "Starts monitoring automatically with the previous settings."),
                ("Copy Only",
                 "Remuxes the source streams into the selected Output Format without "
                 "re-encoding (FFmpeg -c copy), which is fast but fails when the container "
                 "cannot hold the source streams. The Lossless Editor's Remux does the same "
                 "for single files."),
                ("Close on X (don't minimize to tray)",
                 "Ticked by default. Clear it to minimise NVC to the system tray when you "
                 "click X."),
                ("Launch at Windows startup (All Users)",
                 "Launches NVC when Windows starts for all users and requires permission."),
                ("Use GPU Acceleration",
                 "Enables GPU acceleration when supported."),
                ("GPU Encoder",
                 "Choose Auto, nvidia, intel or amd."),
            ]},
            {"type": "para", "text": "The Folders tab selects the folders used by NVC."},
            {"type": "table", "headers": ("Setting", "Guidance"), "rows": [
                ("Source Folder", "Click Change to select the folder NVC watches and scans."),
                ("Destination Folder", "Click Change to select where converted files are written."),
                ("Backup Folder", "Click Change to select where backed-up originals are moved."),
                ("Log Folder", "Click Change to select where logs are written."),
            ]},
            {"type": "para", "text": (
                "The Deletion tab controls original files. See the Original File Handling "
                "chapter.")},
            {"type": "para", "text": "The Format tab controls the conversion output."},
            {"type": "table", "headers": ("Setting", "Guidance"), "rows": [
                ("Output Format",
                 "Choose mp4, mov, avi, mkv, flv, webm, mpeg, mpg, 3gp, ogg, wmv, m4v, mp3 "
                 "or gif."),
                ("Video Codec",
                 "Choose libx264, mpeg4, libvpx, hevc, flv, libtheora or wmv2."),
                ("Audio Codec",
                 "Choose aac, mp3, ac3, opus or vorbis."),
                ("GIF options",
                 "FPS, Max Width, Loop and Quick GIF (no palette) appear when Output Format "
                 "is gif."),
                ("Show Advanced Options",
                 "Shows Video Size, Bitrate, Frame Rate, Keyframe Interval (GOP), Volume, Text "
                 "Overlay and Console Integration."),
                ("Video Size",
                 "Choose Auto, 640x480, 1280x720, 1920x1080 or 3840x2160."),
                ("Bitrate",
                 "Choose Auto or a listed value from 512k to 3000k."),
                ("Frame Rate",
                 "Choose Auto or a listed rate from 8 to 60."),
                ("Keyframe Interval (GOP)",
                 "Choose 0 for Auto or a value up to 300."),
                ("Volume",
                 "Set output audio volume from 0 to 500 %."),
                ("Text Overlay",
                 "Adds text to the output. See the Text Overlays chapter."),
                ("Console Integration",
                 "Appends custom FFmpeg flags to the command."),
                ("Presets",
                 "Use Ethovision, Custom 1, Custom 2, Save to 1 or Save to 2."),
            ]},
            {"type": "para", "text": "The Time tab limits when conversion may start."},
            {"type": "table", "headers": ("Setting", "Guidance"), "rows": [
                ("No Time Restrictions", "Allows conversion at any time."),
                ("Start Time", "Sets the start of the allowed conversion window."),
                ("End Time", "Sets the end of the allowed conversion window. See Time Restrictions."),
            ]},
            {"type": "para", "text": "The Tools tab controls which tool tabs appear in the main window."},
            {"type": "table", "headers": ("Setting", "Guidance"), "rows": [
                ("Tool checkboxes",
                 "There is one checkbox for each tool tab. Unticked tabs are hidden from the "
                 "main window."),
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
                "can adjust FPS, Max Width and Loop, or select Quick GIF (no palette). A lower "
                "FPS and a smaller Max Width both reduce file size.")},
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
                "Text Overlay burns the selected text into the output video.")},
            {"type": "table", "headers": ("Overlay", "Shows"), "rows": [
                ("None", "No overlay."),
                ("Elapsed Time", "The elapsed playback time."),
                ("Recorded Time", "The recorded time of day."),
                ("Recorded Date/Time", "The recorded date and time."),
                ("Recorded Date/Time + Remaining",
                 "The recorded date and time on one line and remaining seconds on another."),
                ("CRTV Cam", "A blinking REC label and the recorded time."),
            ]},
            {"type": "note", "items": [
                "Overlays require video filtering and may reduce GPU compatibility and "
                "conversion speed.",
                "Recorded overlays use the file's recorded time when present and otherwise use "
                "the file modified time.",
            ]},
        ],
    },
    {
        "id": "original-files",
        "title": "Original File Handling",
        "blocks": [
            {"type": "table", "headers": ("Option", "Behaviour"), "rows": [
                ("Delete files after conversion",
                 "Deletes the original after a successful conversion, immediately when "
                 "retention is 0 or after the retention period."),
                ("Retention time (days)",
                 "Choose 0 to 30 days. Pending deletions are stored on disk and processed after "
                 "a restart."),
                ("Use Backup Folder",
                 "Moves originals to the Backup Folder instead of deleting them."),
            ]},
            {"type": "note", "items": [
                "Keep originals until you have confirmed the converted files play correctly.",
            ]},
        ],
    },
    {
        "id": "time-restrictions",
        "title": "Time Restrictions",
        "blocks": [
            {"type": "para", "text": (
                "Settings -- Time lets you select No Time Restrictions or set a Start Time and "
                "End Time for conversion.")},
            {"type": "note", "items": [
                "A file detected outside the window is skipped with \"Current time outside "
                "allowed range\" in the Conversion Log. It is not queued for later. Drop the "
                "file again, or let monitoring re-detect it, inside the permitted window.",
                "An End Time earlier than the Start Time means an overnight window.",
                "The default is No Time Restrictions.",
            ]},
        ],
    },
    {
        "id": "converted-files",
        "title": "Converted Files",
        "blocks": [
            {"type": "para", "text": (
                "Converted Files has File Name, Destination Folder and Date Modified columns. "
                "Status icons identify queued, processing, successful and failed conversions.")},
            {"type": "table", "headers": ("Control", "What it does"), "rows": [
                ("Play", "Opens the selected file in the Media Player tab."),
                ("Clear", "Clears the Converted Files table."),
                ("Play in Media Player", "Opens the selected file in the Media Player tab."),
                ("Open Containing Folder", "Opens the selected file's destination folder."),
                ("Open Log File", "Opens a dialog containing the per-file conversion log."),
                ("Copy File Path", "Copies the selected file path."),
                ("Settings", "Opens Settings."),
            ]},
        ],
    },
    {
        "id": "media-inspection",
        "title": "Media Inspection",
        "blocks": [
            {"type": "para", "text": (
                "The Video Inspection Tool tab has Summary and Detailed JSON sub-tabs. Drop a "
                "file on either sub-tab to populate both. Summary lists File, Container, "
                "Duration, Size, Bitrate and Number of Streams. It then lists each video, "
                "audio and subtitle stream, including its codec and the applicable resolution, "
                "frame rate or channels. A Keyframe Analysis (First 30s) block follows the "
                "stream details. Detailed JSON shows the raw ffprobe -print_format json output.")},
            {"type": "figure", "fig_id": "FIG-04"},
        ],
    },
    {
        "id": "pc-report",
        "title": "PC Report Tool",
        "blocks": [
            {"type": "para", "text": (
                "The PC Report tool gathers system information for support and troubleshooting.")},
            {"type": "steps", "items": [
                "Click Generate PC Report.",
                "Wait for collection to finish. Some collectors can take a while.",
                "Click Open Report to open the generated HTML. Open Folder opens whichever folder "
                "the report was written to.",
                "Reports are saved to your Desktop by default, with the path pattern "
                "Desktop\\PC_Report_YYYYMMDD_HHMMSS.html. If there is no Desktop folder, NVC "
                "uses your user profile folder instead. If that file name already exists, NVC "
                "chooses a unique name and never overwrites the existing file.",
            ]},
            {"type": "figure", "fig_id": "FIG-05"},
            {"type": "para", "text": (
                "The report opens with Report Health (timing, empty sections and warnings) and "
                "then these sections:")},
            {"type": "code", "lines": [
                "Noldus Summary",
                "Operating System",
                "Installed Updates",
                "Licenses",
                "System Directories",
                "System Files",
                "Installed Programs",
                "Security",
                "Accessibility",
                "Environment",
                "Regional Settings",
                "Processes",
                "Services",
                "Drivers",
                "Autorun",
                "Codecs",
                "MMC Snap-ins",
                "System Summary",
                "Motherboard",
                "BIOS",
                "CPU",
                "Memory",
                "Sensors",
                "Devices",
                "PCI",
                "System Slots",
                "Network Adapters",
                "Video",
                "Monitors",
                "Sound",
                "Storage Devices",
                "Logical Disks",
                "Ports",
                "USB",
                "Printers",
                "Virtual Machine",
                "Cameras",
                "Network Information",
                "Shares",
                "Network Connections",
            ]},
            {"type": "note", "items": [
                "Redaction is always on. NVC masks serial numbers, licence keys, passwords and "
                "tokens, user and machine names, hostnames, IP and MAC addresses, proxy settings, "
                "UNC paths and user profile paths. Review a report before sharing it anyway.",
                "Some values need administrator rights and show \"Requires administrator\" when "
                "NVC runs normally. Right-click NVC and choose Run as administrator for a "
                "complete report.",
                "Drivers, devices, network connections and processes are the slow collectors on "
                "large systems.",
            ]},
        ],
    },
    {
        "id": "lossless-editor",
        "title": "Lossless Editor",
        "blocks": [
            {"type": "para", "text": (
                "The Lossless Editor tab provides FFmpeg stream-copy tools. These operations are "
                "fast because they avoid re-encoding wherever possible. Output container choices "
                "are mp4, mkv, mov, avi and m4a; Extract Audio always uses m4a.")},
            {"type": "figure", "fig_id": "FIG-06"},
            {"type": "table", "headers": ("Operation", "What it does"), "rows": [
                ("Trim Losslessly",
                 "Cuts a section between start and end timestamps using stream copy."),
                ("Remux",
                 "Rewraps media into mp4, mkv, mov or avi without re-encoding."),
                ("Extract Audio",
                 "Writes the first audio stream to an audio-only m4a file."),
                ("Remove Audio",
                 "Writes a silent, video-only copy."),
                ("Merge Losslessly",
                 "Joins compatible clips using the FFmpeg concat demuxer."),
                ("Add Files",
                 "Adds source clips to the merge list."),
                ("Clear",
                 "Removes every source clip from the merge list."),
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
                "The Multi-Source Recorder records up to four sources at once with FFmpeg. "
                "The tab shows one row per source; configure the sources in the Video Settings "
                "dialog.")},
            {"type": "figure", "fig_id": "FIG-07"},
            {"type": "para", "text": "The recorder tab"},
            {"type": "table", "headers": ("Control", "What it does"), "rows": [
                ("Use", "Records this row."),
                ("Video name", "Sets the label used in the file name."),
                ("Audio name", "Sets the audio label for the row."),
                ("Mute", "Records the row without sound."),
                ("Volume", "Sets the audio level to 100, 75, 50, 25 or 0 %."),
                ("Encoding", "copy keeps the source's own compressed video only for RTSP, "
                 "stream and file sources. USB (DirectShow) cameras are always re-encoded "
                 "with H.264 regardless of the Encoding choice."),
                ("Output mode", "Separate videos writes one file per row; Combined grid writes "
                 "one file with all sources tiled."),
                ("File location", "Sets the recording folder. The default is your Videos folder."),
                ("File base name", "The default is Video. Files are named "
                 "<base>_<Video name>_<timestamp>.mp4, or "
                 "<base>_Combined_<timestamp>.mp4."),
                ("Timer", "Leave blank to record until you press Stop Recording."),
                ("Show recording log", "Opens the recording log."),
                ("Start Recording / Stop Recording", "The footer button starts or stops recording."),
            ]},
            {"type": "para", "text": "Video Settings"},
            {"type": "figure", "fig_id": "FIG-09"},
            {"type": "steps", "items": [
                "Open Video Settings. Each row has Use, Video name, Video device, a camera "
                "settings button, Frame rate, Resolution, Audio name, Audio device and Sync "
                "offset.",
                "In Video device choose a USB camera by its Windows name, choose RTSP/IP Camera "
                "and click the camera button to enter Address / URL, Username, Password, Port "
                "and Stream path, or type an rtsp://, http:// or https:// URL, a file path, or "
                "a Basler / GenICam source string directly. Refresh USB devices... rescans.",
                "The default Frame rate list is 30.00, 25.00 and 15.00; the default Resolution "
                "list is 1920 x 1080, 1280 x 720, 640 x 480 and Auto. When a USB camera is "
                "selected, NVC replaces both lists with the modes the driver reports and adds "
                "Auto to each. If detection fails, the lists are left as they were: leave "
                "Resolution at Auto and choose a frame rate the camera supports. Auto is only "
                "offered for Frame rate after successful detection.",
                "Choose an Audio device per row, or No Audio. Refresh devices rescans "
                "microphones. Mute or Volume 0 on the tab records that row without sound.",
                "Sync offset shifts a source earlier or later in a Combined grid recording so "
                "clips that started at slightly different times line up.",
                "Apply keeps the dialog open; OK applies and closes.",
            ]},
            {"type": "para", "text": "Presets"},
            {"type": "steps", "items": [
                "Load applies the selected preset; Set overwrites it with the current settings; "
                "Save as... creates a new one; Delete removes it. An asterisk after the name "
                "marks unsaved changes.",
                "Presets are JSON files under "
                r"Public\Documents\Noldus\NVC\MediaRecorder\Presets.",
            ]},
            {"type": "note", "items": [
                "Without a microphone, a file or RTSP source in h264 mode keeps its own sound "
                "track; in copy mode an RTSP source is recorded without audio; a USB camera "
                "without a microphone is silent. Combined grid takes its audio from the first "
                "enabled, unmuted row with a microphone.",
                "A saved microphone that is not connected shows as (not found). If the audio "
                "device fails as recording starts, NVC restarts that row as video only and says "
                "so in the recording log, so the camera recording is not lost.",
                "FFmpeg needs the exact Windows camera name; close other applications that may "
                "be using the camera.",
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
