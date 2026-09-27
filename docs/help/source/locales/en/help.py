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
                "The main window is organised into tabs, with a sidebar on the left and a "
                "status footer. Under the logo the sidebar names the current tab: a glyph for "
                "the tool (a magnifier with an eye for the Media Player, an arrow cycle around "
                "a play symbol for the Video Converter, a camera for the Recorder, scissors for "
                "the Lossless Editor, a monitor for PC Report) beside the tab's title, a short "
                "description under them, then the preview box and the Start button. The header "
                "keeps one height whatever the tab, so the preview box never moves. Drag a tab along the "
                "tab bar to put the tabs in the order you prefer; right-click a tab to hide "
                "that tool, and bring it back from Menu -- Tools. NVC remembers both.")},
            {"type": "table", "headers": ("Area", "What it does"), "rows": [
                ("Video Converter",
                 "The Converted Files table (queued, processing, successful and failed "
                 "conversions) above the conversion log with its messages, progress, "
                 "warnings and results. Drag the divider between them. The Current Video "
                 "Settings table beside the log summarises the format, codecs, resolution, "
                 "bitrate and frame rate; click it to open the Format settings."),
                ("PC Report",
                 "Generates a PC report for support and troubleshooting."),
                ("Lossless Editor",
                 "Provides trim, remux, merge and audio stream-copy tools."),
                ("Multi-Source Recorder",
                 "Records up to four video sources."),
                ("Media Player",
                 "Plays media in one, two or four panels, with an Inspect panel showing "
                 "the selected clip's ffprobe summary and JSON."),
                ("Preview Panel",
                 "The leaf-shaped box in the sidebar shows a preview of the current file or "
                 "the recorder layout, and a pulsing heart while a PC report runs. It is "
                 "blank when there is nothing to preview."),
                ("Menu",
                 "Opens Info, Help, folders, Settings, Window, Tools, Language, updates and Quit."),
            ]},
            {"type": "note", "items": [
                "PC Report and Lossless Editor are hidden by default. Turn them on in "
                "Menu -- Tools or Settings -- Tools. Play or Inspect in Media Player shows the "
                "Media Player tab for the current session even when it is switched off. The "
                "last visible tool cannot be hidden.",
                "The Menu contains Info, Help, Open Source Folder, Open Destination Folder, "
                "Open Backup Folder, Settings, Window, Tools, Language, Check for Updates and Quit.",
                "The footer has the Start/Stop button, a lock icon, a file picker, a broom and "
                "a status label. On the recorder tab the button reads Start Recording or Stop "
                "Recording. The lock icon locks settings, and the Start button then reads "
                "Locked. The file picker selects media files to convert, and the broom clears "
                "the log.",
                "The status label is the same on every tab and lists whatever is running -- "
                "Recording, Converting, Monitoring, or Locked -- joined by dots; when nothing "
                "runs it reads Idle. The dot is green while a job runs, amber while only the "
                "folder monitor is on, red after a failed recording and grey when locked.",
                "Switching tabs never stops anything: recording, conversion, folder monitoring "
                "and media playback carry on whatever tab is in front, and no tab is ever "
                "greyed out. Recording is exclusive with the other ffmpeg jobs: while a "
                "recording is starting, running or stopping, the Start button on the converter "
                "tab reads Recording... and the Lossless Editor's Trim, Remux, Extract audio, "
                "Remove audio and Merge are greyed out, each with the reason as tooltip. While "
                "a conversion or the folder monitor runs, Start Recording is unavailable "
                "(the button reads Converting...) but the rest of the recorder -- previews, "
                "settings, devices -- stays usable. Media Player and PC Report always work.",
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
                "You can drag files onto either half of the Video Converter tab. You can also "
                "use the file picker in the footer to select media files to convert.")},
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
                ("Log Folder",
                 r"Where the per-file conversion logs are written. Leave it empty for the "
                 r"default, %APPDATA%\NVC\logs. The main application log always stays in the "
                 r"default folder because it opens before settings are read."),
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
                 "main window. The same list is in Menu -- Tools, and right-clicking a tab "
                 "hides it; the last visible tool always stays."),
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
                "allowed range\" in the conversion log. It is not queued for later. Drop the "
                "file again, or let monitoring re-detect it, inside the permitted window.",
                "An End Time earlier than the Start Time means an overnight window.",
                "The default is No Time Restrictions.",
            ]},
        ],
    },
    {
        "id": "converted-files",
        "title": "Video Converter: Converted Files",
        "blocks": [
            {"type": "para", "text": (
                "The Video Converter tab shows the Converted Files table above the conversion "
                "log; drag the divider between them to change the split. The table has File "
                "Name, Destination Folder and Date Modified columns. Status icons identify "
                "queued, processing, successful and failed conversions. Play and Inspect are "
                "small glyph buttons under the table's right edge; they appear once a row is "
                "selected. The remaining actions are on the row's right-click menu. "
                "Right-clicking the empty part of the table offers Add videos to convert... "
                "and Monitor a folder.... While the table is empty, thin grey rules mark where "
                "the rows will appear. The footer's file button adds videos to convert and its "
                "broom clears the table together with the log.")},
            {"type": "table", "headers": ("Control", "What it does"), "rows": [
                ("Play", "Opens the selected file in the Media Player tab."),
                ("Inspect", "Opens the selected file in the Media Player with the Inspect panel showing its ffprobe details."),
                ("Add videos to convert...", "Opens the file picker, the same as the Add Files button."),
                ("Monitor a folder...", "Chooses a folder to watch; it becomes the Source Folder in Settings. If monitoring is running it restarts on the new folder."),
                ("Monitor this file's folder", "Makes the selected file's folder the Source Folder."),
                ("Play in Media Player", "Opens the selected file in the Media Player tab."),
                ("Inspect in Media Player", "Same as the Inspect button."),
                ("Open in", "Submenu: Media Player, Lossless Editor (fills its input file and shows the tab) or the Windows default app."),
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
                "Media inspection lives in the Media Player: the Inspect panel beside the "
                "video (open by default; the magnifier button on the transport bar hides and "
                "shows it) has Summary and Detailed JSON sub-tabs for the selected panel's "
                "clip. Selecting another panel, or loading a different file into the selected "
                "one, updates it. Drag the divider between the video and the panel to resize "
                "it; the panel keeps its share of the window as the window grows. Drop a file "
                "on either sub-tab to inspect that file without loading it. Summary lists "
                "File, Container, "
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
                 "stream and file sources. USB (DirectShow) cameras and screen captures are "
                 "always re-encoded with H.264 regardless of the Encoding choice."),
                ("Output mode", "Separate videos writes one file per row; Combined grid writes "
                 "one file with all sources tiled side by side; Picture-in-picture writes one "
                 "file with source 1 filling the frame and the other enabled sources as "
                 "insets along the bottom left, as the sidebar schematic shows."),
                ("File location", "Sets the recording folder. The default is your Videos folder."),
                ("File base name", "The default is Video. Separate videos, and Combined grid "
                 "or Picture-in-picture with one enabled source, use "
                 "<base>_<Video name>_<timestamp>.mp4. Combined grid and Picture-in-picture "
                 "with more than one enabled source use <base>_Combined_<timestamp>.mp4."),
                ("Timer", 'The field shows "blank = until stopped"; leave it blank to record '
                 "until you press Stop Recording."),
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
                "a Basler / GenICam source string directly. Refresh USB devices... rescans. "
                "The camera dialog refuses an Address that looks like an IP but is not one "
                "(a number over 255, or three or five numbers); if a saved address is wrong, "
                "the preview tile reads \"Cannot resolve the camera address\" instead of "
                "reconnecting -- open Video Settings and correct it.",
                "To record the screen, choose Screen capture in Video device and click the "
                "camera button to open Screen Capture Settings: the whole desktop (every "
                "monitor), one display through the GPU, one window chosen from a live list "
                "of open windows, or part of the desktop entered as X, Y, width and height or "
                "drawn with Select on screen... (Escape cancels). The device box then reads "
                "Screen capture (desktop | monitor N, GPU | window: title | region X,Y WxH). "
                "Screen captures record at the row's frame rate (15 fps when set to Auto), "
                "are always encoded to H.264, preview like a network stream and can be mixed "
                "with cameras in Combined grid or Picture-in-picture.",
                "The default Frame rate list is 30.00, 25.00 and 15.00; the default Resolution "
                "list is 1920 x 1080, 1280 x 720, 640 x 480 and Auto. When a USB camera is "
                "selected, NVC replaces both lists with the modes the driver reports and adds "
                "Auto to each. If detection fails, the lists are left as they were: leave "
                "Resolution at Auto and choose a frame rate the camera supports. Auto is only "
                "offered for Frame rate after successful detection.",
                "Choose an Audio device per row, or No Audio. Long device names are shortened "
                "in the list to keep the dialog narrow; hover the box to read the full name. "
                "Refresh devices rescans microphones. Mute or Volume 0 on the tab records that "
                "row without sound.",
                "Sync offset shifts a source earlier or later in a Combined grid or "
                "Picture-in-picture recording so clips that started at slightly different "
                "times line up.",
                "Untick Use to leave a row out -- any row, including the first. With no row in "
                "use the video area stays put as one black tile reading \"No source enabled\", "
                "the Start button is disabled and the tab reads \"Enable at least one "
                "source\". Apply keeps the dialog open; OK applies and closes.",
            ]},
            {"type": "para", "text": "Presets"},
            {"type": "steps", "items": [
                "Load applies the selected preset; Set overwrites it with the current settings; "
                "the small Save as... and Delete links create a new one or remove it. An "
                "asterisk after the name marks unsaved changes.",
                "Presets are JSON files under "
                r"Public\Documents\Noldus\NVC\MediaRecorder\Presets.",
            ]},
            {"type": "para", "text": "Control from the command line"},
            {"type": "para", "text": (
                "Another program can start and stop a recording by running NVC.exe with a "
                "switch. The switches are the same letters MediaRecorder's MRCmd.exe uses, so "
                "entries in The Observer XT's external applications list can be reused with "
                "NVC.exe as the program. If NVC is already running the switch is passed to it; "
                "if not, /E, /R, /C and /B start NVC first, while /S and /X do nothing.")},
            {"type": "table", "headers": ("Switch", "What it does"), "rows": [
                ("/E", "Starts NVC, or brings the running NVC to the front."),
                ("/R", "Starts recording with the current recorder settings."),
                ("/S", "Stops the recording."),
                ("/X", "Stops any recording and closes NVC."),
                ("/C=name", "Loads the video preset with that name, or from a .json file path."),
                ("/B=name", "Sets the recording file base name."),
            ]},
            {"type": "steps", "items": [
                "Switches combine and always run in the order preset, base name, record, stop, "
                r"close. Example: NVC.exe /E /C=Lab1 /B=Trial07 /R",
                "Put a value with spaces in quotes: NVC.exe \"/C=Two cameras\".",
                "The process exits with code 0 when the request succeeded and 1 when it did "
                "not, for example when NVC is locked, a conversion is running, or the preset "
                "does not exist. The reason is written to the console and to the conversion log.",
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
        "id": "media-player",
        "title": "Media Player",
        "blocks": [
            {"type": "para", "text": (
                "The Media Player loads up to four clips for synchronized review. The tab is "
                "hidden by default; enable it under Settings -> Tools. Play in Media Player "
                "from Converted Files shows the tab for the current session, loads the selected "
                "file and starts playback.")},
            {"type": "figure", "fig_id": "FIG-08"},
            {"type": "table", "headers": ("Control", "What it does"), "rows": [
                ("Load", "Loads a clip into that panel."),
                ("Clear", "Removes the clip from that panel."),
                ("Offset (playlist column)", "Shifts that clip in seconds relative to the shared seek position; double-click the cell to edit."),
                ("Play all", "Plays every visible loaded panel and reads Pause all while playing."),
                ("Stop all", "Stops every loaded panel and returns the shared position to zero."),
                ("Restart", "Returns to the beginning and plays every visible loaded panel."),
                ("Seek slider", "Moves every visible loaded panel on the shared timeline."),
                ("Speed", "Sets every panel to 0.25x, 0.5x, 1x, 1.5x or 2x playback."),
                ("Panels", "Shows 1, 2 or 4 panels."),
                ("Volume", "Sets the volume for every panel from 0 to 100."),
                ("Mute", "Mutes every panel and reads Unmute while muted."),
                ("Fullscreen", "Shows the panels and transport bar fullscreen; the Inspect and Playlist panels step aside until you leave."),
                ("Playlist", "Shows or hides the playlist strip under the video; one list is shared by every panel."),
                ("Inspect", "Shows or hides the Inspect panel beside the video (see Media Inspection)."),
            ]},
            {"type": "para", "text": (
                "The readout shows H:MM:SS.mmm / H:MM:SS.mmm · frame N / M. "
                "NVC reads the clip's real frame rate with FFprobe, so Left and Right step "
                "exactly one frame. Frame stepping pauses playback.")},
            {"type": "table", "headers": ("Keys", "Action"), "rows": [
                ("Space", "Play or pause"),
                ("Home", "Restart from the beginning"),
                ("Left", "Step back one frame"),
                ("Right", "Step forward one frame"),
                ("Shift+Left", "Seek back 5 seconds"),
                ("Shift+Right", "Seek forward 5 seconds"),
                ("Up", "Volume up 5"),
                ("Down", "Volume down 5"),
                ("M", "Mute or unmute"),
                ("F", "Toggle fullscreen"),
                ("Escape", "Leave fullscreen"),
                ("N", "Next playlist item"),
                ("P", "Previous playlist item"),
            ]},
            {"type": "para", "text": (
                "Shortcuts work while the Media Player tab has focus. Press F, click "
                "Fullscreen, or double-click a panel to enter fullscreen. The transport bar "
                "hides three seconds after the mouse stops moving and returns when the mouse "
                "moves. Press Escape or F, or double-click, to leave fullscreen.")},
            {"type": "para", "text": (
                "The transport bar sits under the seek slider in three groups from the left: "
                "Play, Stop and Restart; Fullscreen, Playlist and Inspect; then Panels, Speed, "
                "Volume and Mute. Under each tile a caption names its clip, shortened in the "
                "middle when the name is long (hover for the full name).")},
            {"type": "para", "text": (
                "Loading a clip into a panel -- by drop, its Load button or the playlist -- "
                "also selects that panel: the playlist highlights that clip and the Inspect "
                "panel shows its details, so a drop on the second panel is visible at once.")},
            {"type": "para", "text": (
                "Playlist opens a strip under the video with Add files..., Add folder..., "
                "Remove and Clear. There is one list for the whole tab: every clip you load "
                "or drop onto any panel is added to it, so the strip shows everything the "
                "player has seen. The strip has columns File Name, Panel and Offset; Panel "
                "lists the panels showing that clip right now and only appears when more than "
                "one panel is on screen. Double-click a row to load it into the selected "
                "panel. Highlighting a row shows that clip's details in the Inspect panel "
                "without loading it; clicking a panel does the same for its clip. Drag rows "
                "to reorder them, or drop files from Explorer into the strip. N and P move "
                "the selected panel through the list. With Panels set to 1, the next item "
                "starts automatically when a clip ends. In compact mode the strip keeps to a "
                "few rows and scrolls on its own.")},
            {"type": "para", "text": (
                "Offset is a per-clip sync shift in seconds: a negative value plays that clip "
                "earlier than the others, a positive value later, so recordings of the same "
                "moment from two cameras line up. Double-click the Offset cell and type or "
                "step the value; a paused panel moves to the new position at once.")},
            {"type": "para", "text": (
                "A clip shows its first frame as soon as it is loaded or dropped onto a panel "
                "(the tile reads Loading... for a moment), and the seek slider moves the "
                "picture before you press Play. The sidebar preview on the left follows the "
                "selected panel's clip.")},
            {"type": "note", "items": [
                'A file Windows cannot decode shows "Windows cannot play this file." or names '
                'the codec and container, with "Convert to MP4 (H.264) and play". The converted '
                "copy is written to your Destination Folder with a unique name and then loaded.",
                "NVC remembers the last folder, panel count, volume, mute and whether the "
                "Inspect and Playlist panels were open between sessions.",
                "Playback uses Windows Media Foundation. MP4, MOV, MKV, AVI and WMV files with "
                "common codecs play directly; use the convert offer for anything else.",
            ]},
        ],
    },
    {
        "id": "language",
        "title": "Language",
        "blocks": [
            {"type": "para", "text": (
                "Menu -- Language lists English, Nederlands and Simplified Chinese; the last "
                "entry appears in the menu in Chinese characters. NVC saves the choice and "
                "says \"NVC will show <language> the next time it starts.\" The Help and the "
                "Quick Start Guide exist in all three languages; Menu -- Help opens the "
                "manual for the chosen language and falls back to English when that file is "
                "missing.")},
        ],
    },
    {
        "id": "updates-and-logs",
        "title": "Updates and Logs",
        "blocks": [
            {"type": "table", "headers": ("Item", "Where / what"), "rows": [
                ("Check for Updates",
                 "Open it from the menu. A build without an update address answers "
                 "\"Updates Not Configured\". When an address is configured and a newer "
                 "version exists, \"Update v<version> Available!\" appears in the sidebar."),
                ("Log file",
                 r"The rotating application log, conversion_log.txt, is under "
                 r"%APPDATA%\NVC\logs. Each conversion has an <output file name>.txt log in "
                 r"the same folder, or in the Log Folder chosen under Settings -- Folders."),
                ("NVC_LOG_LEVEL",
                 "Set this environment variable to DEBUG to record full tracebacks."),
                ("Settings file", r"%APPDATA%\NVC\config.json."),
                ("Default media folders",
                 r"Public\Documents\Noldus\NVC\Source, "
                 r"Public\Documents\Noldus\NVC\Destination and "
                 r"Public\Documents\Noldus\NVC\Backup."),
                ("Recorder presets",
                 r"Public\Documents\Noldus\NVC\MediaRecorder\Presets."),
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
                 "Drivers, devices, network connections and processes are the slow collectors "
                 "on large systems. Let them finish."),
                ("Camera: Could not find video device",
                 "FFmpeg needs the exact Windows camera name. Pick it from the Video device "
                 "list rather than typing it, and close other applications that may hold the "
                 "camera."),
                ("Microphone shows (not found)",
                 "The saved microphone is not connected. Plug it in and click Refresh devices, "
                 "or choose another device or No Audio."),
                ("Recording has no sound",
                 "Check Mute and Volume on the tab and the Audio device in Video Settings. If "
                 "the audio device failed at start, NVC recorded video only and says so in the "
                 "recording log."),
                ("Media Player says Windows cannot play this file",
                 "The codec or container is not supported by Windows Media Foundation. Click "
                 "Convert to MP4 (H.264) and play."),
                ("A tool tab is missing",
                 "Open Settings, Tools tab, and tick it."),
                ("Help menu says the document was not found",
                 "The generated manual must sit in docs/help, a help folder, or next to the "
                 "executable. Rebuild it with python docs/help/source/build_help_docs.py."),
                ("Something failed with no message",
                 "Set the NVC_LOG_LEVEL environment variable to DEBUG and reproduce the "
                 "problem. NVC then records the full traceback for errors it would otherwise "
                 "handle quietly."),
            ]},
            {"type": "para", "text": (
                r"NVC stores logs under %APPDATA%\NVC\logs: conversion_log.txt is the rotating "
                "application log, and each conversion has an <output file name>.txt log that "
                "Converted Files -- Open Log File opens (per-conversion logs move to the Log "
                "Folder if one is set under Settings -- Folders).")},
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
                "Save a recorder preset for each camera setup so a session starts with one Load.",
                "Review recordings with Panels set to 1 when you want the playlist to advance "
                "automatically.",
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
                 r"By default under %APPDATA%\NVC\logs: conversion_log.txt is the rotating "
                 "application log, with one <output file name>.txt log per conversion. "
                 "Settings -- Folders -- Log Folder moves the per-conversion logs elsewhere."),
                ("Can I run two copies of NVC at once?",
                 "No. NVC allows a single instance, so two copies cannot process the same "
                 "source folder."),
                ("Where do recordings go?",
                 "The File location on the recorder tab, your Videos folder by default, named "
                 "<base>_<Video name>_<timestamp>.mp4 or "
                 "<base>_Combined_<timestamp>.mp4."),
                ("Why does my MKV not play in the Media Player?",
                 "Windows Media Foundation does not decode every codec. Use Convert to MP4 "
                 "(H.264) and play; the copy goes to your Destination Folder."),
                ("Can I record without a microphone?",
                 "Yes. Choose No Audio, or Mute the row. A file or RTSP source in h264 mode "
                 "keeps its own sound track."),
                ("Why does the PC report say Requires administrator?",
                 "Some Windows data is only readable elevated. Run NVC as administrator for a "
                 "complete report; redaction still applies."),
            ]},
        ],
    },
]
