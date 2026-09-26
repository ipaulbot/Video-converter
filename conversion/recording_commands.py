from conversion.recording_sources import screen_monitor_index, screen_region

PREVIEW_FPS = 20
PREVIEW_WIDTH = 480
RTSP_PREVIEW_FPS = 12
RTSP_PREVIEW_WIDTH = 360

# Screen capture (gdigrab). Its default is 29.97 fps of raw full-resolution BMP
# frames, which is heavy for a desktop that mostly does not move; 15 is a
# comfortable recording default and the user can raise it per source.
SCREEN_SOURCE_PREFIX = "screen="
SCREEN_CAPTURE_FPS = 15
SCREEN_PREVIEW_FPS = 8
# Both grabbers deliver BGRA. Left alone, libx264 encodes that as 4:4:4, which the
# Windows players and hardware decoders refuse to play, and the whole virtual
# desktop can have an odd height that yuv420p cannot represent.
SCREEN_ENCODE_FILTER = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"

# Picture-in-picture canvas. The first source fills it; the others are insets
# whose geometry comes from recording_layout_preview_rects, so the sidebar
# schematic and the recorded file agree.
PIP_CANVAS_W = 1280
PIP_CANVAS_H = 720

H264_QUALITY: dict[str, tuple[str, str]] = {
    "Default": ("veryfast", "18"),
    "High": ("medium", "16"),
    "Balanced": ("veryfast", "20"),
    "Compact": ("faster", "24"),
}


def h264_encode_args(quality: str = "Default", encoder: str = "") -> list[str]:
    """libx264 by default; a hardware encoder when the caller has verified one works.

    The hardware rate controls are mapped from the libx264 CRF of the tier:
    constant-quality values on NVENC/QSV/AMF sit a few points above the CRF
    that looks the same, so each tier stays visually in step with the software
    encode and the tiers keep their order.
    """
    preset, crf = H264_QUALITY.get(quality, H264_QUALITY["Default"])
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(int(crf) + 5), "-b:v", "0"]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(int(crf) + 5)]
    if encoder == "h264_amf":
        qp = str(int(crf) + 4)
        return ["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", qp, "-qp_p", qp]
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf]


# NOTE: We deliberately do NOT add fragmented MP4 movflags here. Adding
# "-movflags +frag_keyframe+empty_moov+default_base_moof" was tried as a way to keep
# the file playable when stop has to escalate to a forced kill, but on real-world
# FFmpeg builds those flags caused Axis RTSP stream-copy recordings to produce no
# output file at all and stalled the DirectShow filter_complex preview pipe behind
# the libx264 encoder. Plain MP4 saves reliably; an interrupted recording can be
# repaired, but losing every recording is not acceptable.

# Low-latency preview profile drops buffered frames so the live view stays close to wall clock.
# This is appropriate for the idle preview pipeline but is too aggressive for recording, where
# the codec parsing window of -analyzeduration/-probesize starves the muxer.
RTSP_PREVIEW_INPUT_OPTIONS = [
    "-rtsp_transport",
    "tcp",
    "-fflags",
    "nobuffer",
    "-flags",
    "low_delay",
    "-analyzeduration",
    "0",
    "-probesize",
    "32",
    "-max_delay",
    "0",
    "-reorder_queue_size",
    "0",
]

# Stable recording profile keeps TCP transport but lets FFmpeg analyze the stream normally so
# the resulting MP4 is well-formed. Long reads use a wall-clock timeout to avoid hangs.
RTSP_RECORDING_INPUT_OPTIONS = [
    "-rtsp_transport",
    "tcp",
    "-timeout",
    "5000000",
]

# Backwards-compatible alias kept for any external callers that still reference the previous
# constant name.
RTSP_LOW_LATENCY_INPUT_OPTIONS = RTSP_PREVIEW_INPUT_OPTIONS


def _normalize_recording_resolution(resolution):
    text = str(resolution or "").strip()
    if not text or text.lower() == "auto":
        return ""
    return text.lower().replace(" ", "")


def _normalize_recording_framerate(frame_rate):
    text = str(frame_rate or "").strip()
    if not text or text.lower() == "auto":
        return ""
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _is_genicam_source(source_text):
    text = (source_text or "").lower()
    return "genicam" in text or "basler" in text


def _genicam_first_open_order(source_texts):
    # GenICam / Basler DirectShow sources must be instantiated before any other dshow
    # capture filter in the same FFmpeg process, otherwise they fail to BindToObject
    # ("device already in use" / I/O error). A stable sort opens those sources first
    # while every source keeps its original relative position for grid layout.
    return sorted(range(len(source_texts)), key=lambda index: 0 if _is_genicam_source(source_texts[index]) else 1)


def _normalize_itsoffset(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        seconds = float(text)
    except ValueError:
        return ""
    if abs(seconds) < 1e-6:
        return ""
    return f"{seconds:f}".rstrip("0").rstrip(".")


def _is_screen_source(source_text):
    return (source_text or "").strip().lower().startswith(SCREEN_SOURCE_PREFIX)


def _screen_target(source_text):
    target = (source_text or "").strip()[len(SCREEN_SOURCE_PREFIX):].strip()
    return target or "desktop"


def screen_gdi_fallback_source(source_text):
    """`screen=desktop` for a `screen=monitor=N` source, else "".

    Desktop Duplication needs a D3D11 device and a real console session; when it
    cannot start, the GDI grabber of the whole desktop is the safe substitute.
    """
    if screen_monitor_index(source_text) is None:
        return ""
    return f"{SCREEN_SOURCE_PREFIX}desktop"


def _screen_frame_rate(frame_rate, network_profile):
    default_fps = SCREEN_PREVIEW_FPS if network_profile == "preview" else SCREEN_CAPTURE_FPS
    return _normalize_recording_framerate(frame_rate) or str(default_fps)


def _add_input(command, source_text, network_profile="preview", frame_rate="", resolution="", use_wallclock=False, itsoffset=""):
    offset_value = _normalize_itsoffset(itsoffset)
    if offset_value:
        # Shift this input's timeline so the user can compensate for a constant capture
        # latency difference (e.g. a GigE camera buffering ~1s behind a USB webcam).
        command.extend(["-itsoffset", offset_value])
    if use_wallclock:
        # Stamp every frame with its real arrival time on a single shared clock. This
        # is what lets a multi-input graph keep two live cameras on the same timeline
        # instead of each starting from its own private zero.
        command.extend(["-use_wallclock_as_timestamps", "1"])
    if source_text.lower().startswith(("video=", "audio=")):
        fps_value = _normalize_recording_framerate(frame_rate)
        resolution_value = _normalize_recording_resolution(resolution)
        command.extend(["-rtbufsize", "512M"])
        if fps_value:
            command.extend(["-framerate", fps_value])
        if resolution_value:
            command.extend(["-video_size", resolution_value])
        command.extend(["-f", "dshow", "-i", source_text])
        return
    if _is_screen_source(source_text):
        fps_value = _screen_frame_rate(frame_rate, network_profile)
        monitor = screen_monitor_index(source_text)
        if monitor is not None:
            # One display through the Desktop Duplication API: the GPU hands over
            # frames, so DirectX content is captured and 4K/60 costs no CPU. The
            # filter creates its own D3D11 device; frames are downloaded for the
            # software encoder / layout filters that follow.
            command.extend([
                "-f", "lavfi",
                "-i", f"ddagrab=output_idx={monitor - 1}:framerate={fps_value},hwdownload,format=bgra",
            ])
            return
        # gdigrab: the whole desktop, a region of it, or one window by title. The
        # requested resolution is not applied -- for gdigrab -video_size means
        # "crop this region from the top-left", which is not what a camera-style
        # resolution setting promises; only an explicit region uses it. The
        # capture is scaled later where the layout needs it.
        command.extend(["-f", "gdigrab", "-framerate", fps_value])
        region = screen_region(source_text)
        if region:
            x, y, width, height = region
            command.extend(["-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{width}x{height}"])
            command.extend(["-i", "desktop"])
            return
        command.extend(["-i", _screen_target(source_text)])
        return
    if source_text.lower().startswith("rtsp://"):
        if network_profile == "recording":
            command.extend(RTSP_RECORDING_INPUT_OPTIONS)
        else:
            command.extend(RTSP_PREVIEW_INPUT_OPTIONS)
    command.extend(["-i", source_text])


def _audio_enabled(audio_device, mute=False, volume="100"):
    device = str(audio_device or "").strip()
    try:
        gain = int(str(volume or "100"))
    except ValueError:
        gain = 100
    return bool(device and device != "No Audio" and not mute and gain > 0)


def _silenced(mute=False, volume="100"):
    """Mute or volume 0: the row wants no sound at all, embedded or microphone."""
    try:
        gain = int(str(volume or "100"))
    except ValueError:
        gain = 100
    return bool(mute) or gain <= 0


def _directshow_av_source(video_source, audio_device):
    video_name = str(video_source or "").strip()
    if video_name.lower().startswith("video="):
        video_name = video_name[6:]
    video_name = video_name.strip('"')
    audio_name = str(audio_device or "").strip().strip('"')
    # No shell quotes: QProcess/subprocess pass argv verbatim, so FFmpeg would look for a
    # device literally named "\"HD Webcam\"" and fail with "Could not find video device".
    return f"video={video_name}:audio={audio_name}"


def _append_audio_encoding_options(command, volume="100"):
    command.extend(["-c:a", "aac", "-b:a", "128k"])
    if str(volume or "100") != "100":
        command.extend(["-af", f"volume={int(str(volume)) / 100:g}"])


def _add_directshow_audio_input(command, audio_device):
    audio_name = str(audio_device or "").strip().strip('"')
    command.extend([
        "-f", "dshow",
        "-thread_queue_size", "1024",
        "-use_wallclock_as_timestamps", "1",
        "-i", f"audio={audio_name}",
    ])


def build_record_command(
    ffmpeg_path,
    source,
    output_file,
    codec_mode="copy",
    duration_seconds="",
    preview_pipe=False,
    frame_rate="",
    resolution="",
    audio_device="",
    mute=False,
    volume="100",
    quality="Default",
    video_encoder="",
):
    command = [ffmpeg_path, "-hide_banner", "-y"]
    if duration_seconds:
        command.extend(["-t", str(duration_seconds)])

    source_text = (source or "").strip()
    is_directshow = source_text.lower().startswith(("video=", "audio="))
    has_audio = _audio_enabled(audio_device, mute=mute, volume=volume)
    if has_audio and is_directshow:
        source_text = _directshow_av_source(source_text, audio_device)
    _add_input(command, source_text, network_profile="recording", frame_rate=frame_rate, resolution=resolution)
    audio_map = ""
    if has_audio:
        if is_directshow:
            audio_map = "0:a"
        else:
            _add_directshow_audio_input(command, audio_device)
            audio_map = "1:a"
    # "No Audio" means no microphone was chosen, not "strip the source's own sound": a file or
    # network stream keeps its embedded audio unless the row is muted. RTSP stream-copy stays
    # video-only as before (camera audio codecs rarely copy into MP4).
    is_network_source = source_text.lower().startswith(("rtsp://", "http://", "https://"))
    is_screen = _is_screen_source(source_text)
    keep_embedded_audio = not has_audio and not _silenced(mute, volume) and not is_directshow and not is_screen

    if preview_pipe:
        # Both DirectShow and RTSP/HTTP sources use a single decoded video stream that
        # is split into the recording output and the MJPEG preview pipe. Sharing the
        # decoder + scheduler is the only configuration we have seen reliably keep the
        # preview tile updating while the file output is also active. A stream-copy
        # file output with a separate decoded preview tap on the same input does avoid
        # the re-encode cost, but in practice FFmpeg's scheduler starves the preview
        # tap on RTSP inputs (notably Axis cameras) and the preview freezes. The CPU
        # cost of re-encoding to libx264 veryfast is small relative to that trade-off.
        source_chain = f"{SCREEN_ENCODE_FILTER}," if is_screen else ""
        command.extend([
            "-filter_complex",
            f"[0:v]{source_chain}split=2[v][preview];[preview]fps={PREVIEW_FPS},scale={PREVIEW_WIDTH}:-1[p]",
            "-map", "[v]",
        ])
        if has_audio:
            command.extend(["-map", audio_map])
            if not is_directshow:
                command.append("-shortest")
        elif keep_embedded_audio:
            command.extend(["-map", "0:a?"])
        else:
            command.append("-an")
        command.extend(h264_encode_args(quality, video_encoder))
        if has_audio:
            _append_audio_encoding_options(command, volume)
        elif keep_embedded_audio:
            command.extend(["-c:a", "aac"])
        command.extend([
            output_file,
            "-map", "[p]",
            "-q:v", "7",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "pipe:1",
        ])
        return command

    # Raw capture devices (DirectShow, gdigrab) have nothing to stream-copy.
    copy_video = codec_mode == "copy" and not is_directshow and not is_screen
    if copy_video and is_network_source:
        keep_embedded_audio = False
    command.extend(["-map", "0:v"])
    if has_audio:
        command.extend(["-map", audio_map])
        if not is_directshow:
            command.append("-shortest")
    elif keep_embedded_audio:
        command.extend(["-map", "0:a?"])
    else:
        command.append("-an")
    if copy_video:
        command.extend(["-c:v", "copy"])
    else:
        if is_screen:
            command.extend(["-vf", SCREEN_ENCODE_FILTER])
        command.extend(h264_encode_args(quality, video_encoder))
    if has_audio:
        _append_audio_encoding_options(command, volume)
    elif keep_embedded_audio:
        command.extend(["-c:a", "copy" if copy_video else "aac"])
    command.append(output_file)
    return command


COMBINED_GRID_FPS = 30


def build_combined_grid_record_command(
    ffmpeg_path,
    sources,
    output_file,
    duration_seconds="",
    preview_pipe=False,
    preview_fps=PREVIEW_FPS,
    preview_width=PREVIEW_WIDTH,
    output_fps=COMBINED_GRID_FPS,
    offsets_per_source=None,
    audio_device="",
    mute=False,
    volume="100",
    quality="Default",
    options_per_source=None,
    layout="grid",
):
    """One process, one composite MP4 from every source.

    ``layout`` is ``"grid"`` (xstack tiles) or ``"pip"`` (source 1 fills the
    frame, the others are insets). ``options_per_source`` carries each source's
    ``frame_rate`` / ``resolution`` so a USB camera opens in its configured mode
    here exactly as it does in Separate videos; without them a 1080p MJPEG webcam
    fell back to the driver default (640x480 YUY2).
    """
    source_texts = [(source or "").strip() for source in sources if (source or "").strip()]
    offsets = list(offsets_per_source or [])
    options_list = list(options_per_source or [])
    command = [ffmpeg_path, "-hide_banner", "-y"]

    # Open GenICam/Basler sources first so they can bind, but remember each source's
    # original position so the grid tiles stay where the user arranged them.
    open_order = _genicam_first_open_order(source_texts)
    input_index_of = {original: opened for opened, original in enumerate(open_order)}
    for original in open_order:
        options = options_list[original] if original < len(options_list) else {}
        _add_input(
            command,
            source_texts[original],
            network_profile="recording",
            frame_rate=(options or {}).get("frame_rate", ""),
            resolution=(options or {}).get("resolution", ""),
        )

    audio_input_index = None
    if _audio_enabled(audio_device, mute=mute, volume=volume):
        audio_input_index = len(source_texts)
        _add_directshow_audio_input(command, audio_device)

    if len(source_texts) == 1 and not preview_pipe:
        command.extend(["-map", "0:v"])
        if audio_input_index is None:
            command.append("-an")
        else:
            command.extend(["-map", f"{audio_input_index}:a", "-shortest"])
        if _is_screen_source(source_texts[0]):
            command.extend(["-vf", SCREEN_ENCODE_FILTER])
        command.extend(["-r", str(output_fps), *h264_encode_args(quality)])
        if audio_input_index is not None:
            _append_audio_encoding_options(command, volume)
        if duration_seconds:
            command.extend(["-t", str(duration_seconds)])
        command.append(output_file)
        return command

    pip = str(layout or "grid").lower() == "pip" and len(source_texts) > 1
    if pip:
        # Every rect is normalised against the PiP canvas; source 1 is the full frame.
        rects = _pip_preview_rects(len(source_texts))
        tile_sizes = [
            (max(2, round(w * PIP_CANVAS_W)) // 2 * 2, max(2, round(h * PIP_CANVAS_H)) // 2 * 2)
            for (_x, _y, w, h) in rects
        ]
    else:
        tile_sizes = [(640, 360)] * len(source_texts)

    filters = []
    for opened_index in range(len(source_texts)):
        original = open_order[opened_index]
        offset_value = _normalize_itsoffset(offsets[original]) if original < len(offsets) else ""
        # Rebase each tile to its OWN first frame (timebase 0) and only then resample
        # to the common frame rate. Because both streams now share timebase 0 and the
        # same CFR cadence, xstack's frame-sync pairs them 1:1 -- no repeated/dropped
        # frames, which is what made the GigE tile choppy under the old wall-clock
        # approach. A constant capture-latency difference between cameras (e.g. a GigE
        # camera whose first frame lands ~1s after the webcam's) shows up as a fixed
        # content offset, corrected with the per-source sync offset added to setpts.
        if offset_value:
            setpts = f"setpts=PTS-STARTPTS+({offset_value})/TB"
        else:
            setpts = "setpts=PTS-STARTPTS"
        tile_w, tile_h = tile_sizes[original]
        # A BGRA screen tile is converted before stacking so xstack/overlay never
        # negotiate a 4:4:4 or RGB output for the whole composite.
        pixel_format = ",format=yuv420p" if _is_screen_source(source_texts[original]) else ""
        filters.append(
            f"[{opened_index}:v]{setpts},fps={output_fps},"
            f"scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease,"
            f"pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2,setsar=1{pixel_format}"
            f"[v{opened_index}]"
        )

    # Compose in ORIGINAL source order so tile positions match the user's rows,
    # even though the inputs were opened GenICam-first.
    labels = [f"[v{input_index_of[original]}]" for original in range(len(source_texts))]

    if len(source_texts) == 1:
        base_label = labels[0]
    else:
        base_label = "[stacked]" if preview_pipe else "[v]"
        if pip:
            # Chain one overlay per inset onto source 1.
            current = labels[0]
            for inset_index in range(1, len(source_texts)):
                x, y, _w, _h = rects[inset_index]
                out_label = base_label if inset_index == len(source_texts) - 1 else f"[pip{inset_index}]"
                filters.append(
                    f"{current}{labels[inset_index]}"
                    f"overlay={round(x * PIP_CANVAS_W)}:{round(y * PIP_CANVAS_H)}{out_label}"
                )
                current = out_label
        else:
            if len(source_texts) == 2:
                grid_layout = "0_0|w0_0"
            elif len(source_texts) == 3:
                grid_layout = "0_0|w0_0|0_h0"
            else:
                grid_layout = "0_0|w0_0|0_h0|w0_h0"
            filters.append(
                f"{''.join(labels)}xstack=inputs={len(source_texts)}:layout={grid_layout}:fill=black{base_label}"
            )

    if preview_pipe:
        filters.append(f"{base_label}split=2[v][preview]")
        filters.append(f"[preview]fps={preview_fps},scale={preview_width}:-1[p]")

    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[v]",
        "-r", str(output_fps),
        *h264_encode_args(quality),
    ])
    if audio_input_index is None:
        command.append("-an")
    else:
        command.extend([
            "-map", f"{audio_input_index}:a",
            "-shortest",
        ])
        _append_audio_encoding_options(command, volume)
    if duration_seconds:
        command.extend(["-t", str(duration_seconds)])
    command.append(output_file)
    if preview_pipe:
        command.extend(["-map", "[p]", "-q:v", "7"])
        if duration_seconds:
            command.extend(["-t", str(duration_seconds)])
        command.extend(["-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"])
    return command


def _grid_preview_rects(count):
    # Normalized tile rectangles matching the combined-grid / separate-file arrangement.
    if count == 1:
        return [(0.0, 0.0, 1.0, 1.0)]
    if count == 2:
        return [(0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0)]
    if count == 3:
        return [(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5)]
    return [
        (0.0, 0.0, 0.5, 0.5),
        (0.5, 0.0, 0.5, 0.5),
        (0.0, 0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5, 0.5),
    ]


def _pip_preview_rects(count):
    # Source 1 fills the frame; the remaining sources are small insets stacked along the
    # bottom-left, like a picture-in-picture composite.
    rects = [(0.0, 0.0, 1.0, 1.0)]
    inset_w = 0.28
    inset_h = 0.28
    gap = 0.04
    margin = 0.05
    for inset_index in range(count - 1):
        x = margin + inset_index * (inset_w + gap)
        y = 1.0 - margin - inset_h
        rects.append((x, y, inset_w, inset_h))
    return rects


def recording_layout_preview_rects(mode, count):
    """Describe where each numbered source lands in the recorder's output.

    Returns a list of normalized ``(x, y, w, h)`` rectangles (each value in 0..1), one
    per source in source order. This drives the layout schematic shown in the sidebar
    preview so the user can see at a glance whether the output will be a side-by-side
    grid, a picture-in-picture composite, or a single tile.
    """
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    count = max(0, min(count, 4))
    if count == 0:
        return []
    mode_text = (mode or "").strip().lower()
    if mode_text.startswith("picture"):
        return _pip_preview_rects(count)
    return _grid_preview_rects(count)


def _preview_grid_layout(count):
    # Compact grids for the common 2-4 camera setups, matching the combined-grid
    # recorder layout. For larger counts fall back to a single horizontal row, which
    # is always a valid xstack layout regardless of how many tiles there are.
    if count == 2:
        return "0_0|w0_0"
    if count == 3:
        return "0_0|w0_0|0_h0"
    if count == 4:
        return "0_0|w0_0|0_h0|w0_h0"
    positions = ["0_0"]
    for index in range(1, count):
        positions.append("+".join(f"w{j}" for j in range(index)) + "_0")
    return "|".join(positions)


def build_multi_source_record_command(
    ffmpeg_path,
    sources,
    output_files,
    duration_seconds="",
    options_per_source=None,
    preview_pipe=False,
    preview_fps=PREVIEW_FPS,
    preview_width=PREVIEW_WIDTH,
    audio_source="",
    quality="Default",
):
    """Build one FFmpeg command that records every source in a single process.

    Each source is opened exactly once and written to its own MP4 file, which avoids
    the DirectShow "device already in use" conflict that breaks a separate
    preview-process + recording-process design. Every video stream is rebased with
    ``setpts=PTS-STARTPTS`` so cameras that connect at slightly different times stay
    aligned instead of drifting apart. When ``preview_pipe`` is set, the same process
    also taps each input, scales it, stacks the tiles, and emits a single combined
    MJPEG preview on stdout so the live view never has to re-open any device.

    This is the unified-pipeline prototype; it is intentionally not yet wired into the
    live recorder so the proven per-source paths keep working untouched.
    """
    source_texts = [(source or "").strip() for source in sources]
    output_files = list(output_files or [])
    options_list = list(options_per_source or [])

    command = [ffmpeg_path, "-hide_banner", "-y"]

    for index, source_text in enumerate(source_texts):
        options = options_list[index] if index < len(options_list) else {}
        _add_input(
            command,
            source_text,
            network_profile="recording",
            frame_rate=(options or {}).get("frame_rate", ""),
            resolution=(options or {}).get("resolution", ""),
        )

    audio_text = (audio_source or "").strip()
    audio_input_index = None
    if audio_text:
        audio_input_index = len(source_texts)
        _add_input(command, audio_text, network_profile="recording")

    filters = []
    preview_scaled_labels = []
    for index in range(len(source_texts)):
        if preview_pipe:
            filters.append(
                f"[{index}:v]setpts=PTS-STARTPTS,split=2[rec{index}][pre{index}]"
            )
            filters.append(
                f"[pre{index}]fps={preview_fps},scale={preview_width}:-1[p{index}]"
            )
            preview_scaled_labels.append(f"[p{index}]")
        else:
            filters.append(f"[{index}:v]setpts=PTS-STARTPTS[rec{index}]")

    preview_map_label = None
    if preview_pipe and preview_scaled_labels:
        if len(preview_scaled_labels) == 1:
            preview_map_label = preview_scaled_labels[0]
        else:
            layout = _preview_grid_layout(len(preview_scaled_labels))
            filters.append(
                f"{''.join(preview_scaled_labels)}"
                f"xstack=inputs={len(preview_scaled_labels)}:layout={layout}:fill=black[grid]"
            )
            preview_map_label = "[grid]"

    command.extend(["-filter_complex", ";".join(filters)])

    duration = str(duration_seconds or "").strip()
    for index, output_file in enumerate(output_files):
        command.extend(["-map", f"[rec{index}]"])
        attach_audio = audio_input_index is not None and index == 0
        if attach_audio:
            command.extend(["-map", f"{audio_input_index}:a"])
        command.extend(h264_encode_args(quality))
        if attach_audio:
            command.extend(["-c:a", "aac"])
        if duration:
            command.extend(["-t", duration])
        command.append(output_file)

    if preview_pipe and preview_map_label:
        command.extend(["-map", preview_map_label, "-q:v", "7"])
        if duration:
            # The preview output must honor the same duration as the file outputs;
            # otherwise the live (never-ending) preview tap keeps the whole process
            # alive past the requested recording length.
            command.extend(["-t", duration])
        command.extend(["-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"])
    return command


def build_directshow_camera_settings_command(ffmpeg_path, device_name):
    source = device_name if str(device_name or "").lower().startswith("video=") else f"video={device_name}"
    return [
        ffmpeg_path,
        "-hide_banner",
        "-f",
        "dshow",
        "-show_video_device_dialog",
        "true",
        "-i",
        source,
        "-t",
        "0.1",
        "-f",
        "null",
        "NUL",
    ]


def build_directshow_list_options_command(ffmpeg_path, device_name):
    source = device_name if str(device_name or "").lower().startswith("video=") else f"video={device_name}"
    return [
        ffmpeg_path,
        "-hide_banner",
        "-list_options",
        "true",
        "-f",
        "dshow",
        "-i",
        source,
    ]


def build_directshow_preview_frame_command(ffmpeg_path, device_name, output_file):
    source = device_name if str(device_name or "").lower().startswith("video=") else f"video={device_name}"
    return [
        ffmpeg_path,
        "-hide_banner",
        "-y",
        "-f",
        "dshow",
        "-i",
        source,
        "-frames:v",
        "1",
        output_file,
    ]


def build_directshow_preview_stream_command(
    ffmpeg_path,
    device_name,
    fps=PREVIEW_FPS,
    width=PREVIEW_WIDTH,
    frame_rate="",
    resolution="",
):
    source = device_name if str(device_name or "").lower().startswith("video=") else f"video={device_name}"
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-nostats",
        "-rtbufsize",
        "512M",
    ]
    fps_value = _normalize_recording_framerate(frame_rate)
    resolution_value = _normalize_recording_resolution(resolution)
    if fps_value:
        command.extend(["-framerate", fps_value])
    if resolution_value:
        command.extend(["-video_size", resolution_value])
    command.extend([
        "-f",
        "dshow",
        "-i",
        source,
        "-vf",
        f"fps={fps},scale={width}:-1",
        "-q:v",
        "5",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-",
    ])
    return command


def build_preview_stream_command(ffmpeg_path, source, fps=PREVIEW_FPS, width=PREVIEW_WIDTH):
    source_text = (source or "").strip()
    is_rtsp = source_text.lower().startswith("rtsp://")
    preview_fps = RTSP_PREVIEW_FPS if is_rtsp else fps
    preview_width = RTSP_PREVIEW_WIDTH if is_rtsp else width
    preview_quality = "9" if is_rtsp else "7"
    command = [ffmpeg_path, "-hide_banner", "-nostats"]
    _add_input(command, source_text, network_profile="preview")
    command.extend([
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"fps={preview_fps},scale={preview_width}:-1",
        "-q:v",
        preview_quality,
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-",
    ])
    return command


def build_directshow_record_with_preview_command(
    ffmpeg_path,
    source,
    output_file,
    duration_seconds="",
    fps=5,
    preview_pipe=False,
    frame_rate="",
    resolution="",
    audio_device="",
    mute=False,
    volume="100",
    quality="Default",
):
    source_text = (source or "").strip()
    if not source_text.lower().startswith("video="):
        source_text = f"video={source_text}"
    has_audio = _audio_enabled(audio_device, mute=mute, volume=volume)
    if has_audio:
        source_text = _directshow_av_source(source_text, audio_device)
    command = [ffmpeg_path, "-hide_banner", "-y"]
    if duration_seconds:
        command.extend(["-t", str(duration_seconds)])
    _add_input(command, source_text, network_profile="recording", frame_rate=frame_rate, resolution=resolution)
    if preview_pipe:
        command.extend([
            "-filter_complex",
            f"[0:v]split=2[v][preview];[preview]fps={PREVIEW_FPS},scale={PREVIEW_WIDTH}:-1[p]",
            "-map", "[v]",
        ])
        if has_audio:
            command.extend(["-map", "0:a"])
        else:
            command.append("-an")
        command.extend(h264_encode_args(quality))
        if has_audio:
            _append_audio_encoding_options(command, volume)
        command.extend([
            output_file,
            "-map", "[p]",
            "-q:v", "7",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "pipe:1",
        ])
        return command
    command.extend(["-map", "0:v"])
    if has_audio:
        command.extend(["-map", "0:a"])
    else:
        command.append("-an")
    command.extend(h264_encode_args(quality))
    if has_audio:
        _append_audio_encoding_options(command, volume)
    command.append(output_file)
    return command
