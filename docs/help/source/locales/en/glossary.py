"""Glossary terms, shared by every manual.

Term keys stay in English in every locale so that anchors and cross-references
do not move when the prose is translated; only the meanings are translated.
"""
from __future__ import annotations

GLOSSARY_TITLE = "Glossary"

GLOSSARY_INTRO = (
    "Terms used throughout this guide. FFmpeg terminology is kept where it is "
    "what you will see in the conversion log."
)

GLOSSARY_HEADERS = ("Term", "Meaning")

GLOSSARY_ROWS: list[tuple[str, str]] = [
    ("Container",
     "The file wrapper that holds video and audio streams, such as MP4, MKV or "
     "AVI. The container is what the file extension names; it is separate from "
     "the codec used inside it."),
    ("Codec",
     "The scheme used to compress a stream. H.264 (libx264) and HEVC (libx265) "
     "are video codecs; AAC and MP3 are audio codecs."),
    ("FFmpeg",
     "The command-line media tool NVC runs to do the actual conversion. Its "
     "output is what appears in the conversion log."),
    ("FFprobe",
     "FFmpeg's inspection tool. NVC uses it to read duration, streams, codecs "
     "and other metadata without converting anything."),
    ("Stream copy",
     "Rewriting media into a new container without re-encoding it. Fast and "
     "lossless, but only possible when the target container supports the "
     "existing streams. Also called remuxing."),
    ("Remux",
     "Changing a file's container while keeping its streams untouched. See "
     "stream copy."),
    ("Transcode",
     "Decoding and re-encoding a stream, which changes quality and takes "
     "significantly longer than a stream copy."),
    ("Keyframe",
     "A frame stored in full rather than as a difference from its neighbours. "
     "Seeking and lossless trimming can only land cleanly on a keyframe."),
    ("GOP",
     "Group of Pictures: the interval between keyframes. A shorter GOP makes "
     "scrubbing more precise at the cost of file size."),
    ("Bitrate",
     "Data used per second of media, usually in kbps or Mbps. Higher bitrate "
     "generally means better quality and a larger file."),
    ("GPU encoding",
     "Using dedicated video hardware (NVENC on NVIDIA, AMF on AMD, Quick Sync "
     "on Intel) to encode instead of the CPU. Much faster, with codec support "
     "depending on your drivers."),
    ("DirectShow",
     "The Windows capture interface NVC uses to record from local devices. "
     "Sources are written as video=Device Name."),
    ("Media Foundation",
     "The Windows playback framework the Media Player uses to decode and play "
     "supported media."),
    ("RTSP",
     "A streaming protocol used by most IP and network cameras. Sources are "
     "written as a URL, such as rtsp://192.168.1.10/stream."),
    ("GenICam",
     "The generic camera interface used by Basler and other industrial cameras. "
     "Configure these cameras in Basler pylon Viewer."),
    ("Preset",
     "A saved recorder configuration stored as JSON under "
     r"Public\Documents\Noldus\NVC\MediaRecorder\Presets."),
    ("Sync offset",
     "A time adjustment that shifts one source earlier or later in a Combined "
     "grid recording so sources line up."),
    ("Frame step",
     "Moving exactly one frame forward or backward using the clip's frame rate."),
    ("Playlist",
     "An ordered list of media files for one Media Player panel. With one panel, "
     "the next item starts automatically."),
    ("Administrator (elevation)",
     "Running NVC with administrator rights so the PC report can read protected "
     "Windows data."),
    ("Tool tab",
     "A main-window tab that can be hidden or shown in Settings -- Tools."),
    ("Retention period",
     "How long NVC keeps an original file after a successful conversion before "
     "deleting it. Pending deletions survive a restart."),
    ("Redaction",
     "Always-on masking of sensitive values such as licence keys, serial numbers, "
     "MAC addresses and user paths in a PC report before it is shared."),
]
