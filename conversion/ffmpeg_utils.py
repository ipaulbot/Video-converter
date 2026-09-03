import subprocess
import os
import shutil
from datetime import datetime, timezone
from utils.logger import logger
from utils.resources import resource_path
from utils.subprocess_helpers import get_subprocess_startupinfo
from conversion.gpu_encoders import GPU_ENCODERS

# Helper to hide console windows on Windows
def _get_subprocess_startupinfo():
    """Return (startupinfo, creationflags) that hide console windows on Windows."""
    return get_subprocess_startupinfo()

def is_within_allowed_time(settings):
    """
    Returns True if the current time is within the allowed conversion window,
    or if no restrictions are specified.
    """
    if settings.get('no_time_restrictions', True):
        return True

    current_time = datetime.now().time()
    start_str = settings.get('start_time', '00:00')
    end_str = settings.get('end_time', '23:59')
    try:
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
    except ValueError:
        return True

    if start_time <= end_time:
        return start_time <= current_time <= end_time
    else:
        # Handles time ranges that wrap past midnight.
        return current_time >= start_time or current_time <= end_time

def normalize_video_codec(video_codec):
    """Normalize UI codec labels to FFmpeg CPU encoder names."""
    codec = (video_codec or 'libx264').strip()
    aliases = {
        'h264': 'libx264',
        'x264': 'libx264',
        'hevc': 'libx265',
        'h265': 'libx265',
        'x265': 'libx265',
    }
    return aliases.get(codec.lower(), codec)

def video_codec_intent(video_codec):
    """Return the GPU encoder family implied by a selected codec."""
    normalized = normalize_video_codec(video_codec).lower()
    if normalized in {'libx265', 'hevc', 'h265'}:
        return 'hevc'
    return 'h264'

def build_ffmpeg_command(settings, input_file, output_file):
    """
    Build the FFmpeg command list based on settings.
    Skips options whose value is "Auto" (or empty).
    If GPU acceleration is enabled, override the video codec with the appropriate GPU encoder.
    """
    ffmpeg_path = resource_path('ffmpeg.exe')
    # Special case: palette-optimized GIF workflow handled by worker in two-pass.
    # Here we only build the standard single-pass command for non-GIF or quick GIF.
    command = [ffmpeg_path, '-i', input_file]

    if settings.get('copy_only', False):
        command.extend(['-c', 'copy'])
    else:
        # If GPU acceleration is enabled, check for "Auto" or specific vendor
        if settings.get('use_gpu', False):
            gpu_vendor = settings.get('gpu_encoder', 'Auto')

            # If Auto, try to detect best
            if gpu_vendor.lower() == 'auto':
                from conversion.gpu_encoders import get_best_gpu_encoder
                detected_vendor, detected_encoders = get_best_gpu_encoder()
                if detected_vendor:
                    gpu_vendor = detected_vendor
                    logger.info(f"Auto-detected GPU: {detected_vendor.upper()}")
                else:
                    # Fallback to CPU if no GPU found
                    gpu_vendor = 'none'
                    logger.info("No supported GPU detected. Falling back to CPU.")

            # Look up encoder for the specific/detected vendor
            if gpu_vendor.lower() != 'none':
                gpu_encoder_map = GPU_ENCODERS.get(gpu_vendor.lower(), {})
                codec_intent = video_codec_intent(settings.get('video_codec', 'libx264'))
                gpu_encoder = gpu_encoder_map.get(codec_intent, '')

                if gpu_encoder:
                    command.extend(['-c:v', gpu_encoder])
                    logger.info(f"Using GPU Encoder: {gpu_encoder}")
                else:
                    # Fall back to the normal video codec if mapping not found.
                    video_codec = normalize_video_codec(settings.get('video_codec', 'libx264'))
                    if video_codec:
                        command.extend(['-c:v', video_codec])
                        logger.warning(f"GPU {gpu_vendor} found but no {codec_intent.upper()} encoder mapped. Using CPU codec: {video_codec}")
            else:
                 # GPU requested but none found/selected -> CPU fallback
                video_codec = normalize_video_codec(settings.get('video_codec', 'libx264'))
                if video_codec:
                    command.extend(['-c:v', video_codec])
                    logger.info(f"GPU not used. Using CPU codec: {video_codec}")
        else:
            video_codec = normalize_video_codec(settings.get('video_codec', 'libx264'))
            if video_codec:
                command.extend(['-c:v', video_codec])
        audio_codec = settings.get('audio_codec', 'aac')
        if audio_codec:
            command.extend(['-c:a', audio_codec])
        video_bitrate = settings.get('video_bitrate', '')
        if video_bitrate and video_bitrate.lower() != "auto":
            command.extend(['-b:v', video_bitrate])
        audio_bitrate = settings.get('audio_bitrate', '')
        if audio_bitrate and audio_bitrate.lower() != "auto":
            command.extend(['-b:a', audio_bitrate])

        # Volume Adjustment
        volume = settings.get('volume_percentage', 100)
        if volume != 100:
             # ffmpeg volume filter: 256 is 100%, but 'volume=1.0' syntax is easier.
             # 50% -> 0.5, 200% -> 2.0
             vol_float = float(volume) / 100.0
             command.extend(['-af', f"volume={vol_float:.2f}"])

        # Text Overlay
        overlay_type = settings.get('text_overlay', 'None') or 'None'
        # Backwards compatibility (older saved values)
        _overlay_norm = {
            "Timestamp": "Elapsed Time",
            "Date/Time": "Recorded Date/Time",
            "CRTV Style": "CRTV Cam",
            "Elapsed Timestamp (top-left)": "Elapsed Time",
            "Recorded Time (top-left)": "Recorded Time",
            "Recorded Date/Time (top-left)": "Recorded Date/Time",
            "Recorded Date/Time + Remaining (top-left)": "Recorded Date/Time + Remaining",
            "CRTV Cam (Recorded, top-left)": "CRTV Cam",
        }
        overlay_type = _overlay_norm.get(overlay_type, overlay_type)
        if overlay_type != 'None':
            # Note: Video filters (-vf) are incompatible with -c copy and often conflict with GPU encoding
            # unless using complex filters or specific GPU filters.
            # For simplicity, if overlay is enabled, we might need to rely on CPU filters or ensure the codec supports it.
            # Since we construct command linearly, we need to append to -vf.

            # Since we have scale filter from 'video_size' usually passed as -s, let's convert -s to scale filter if we use other filters?
            # Actually ffmpeg can mix -s and -vf but order matters.
            # Ideally we use -vf for everything if one filter is used.

            drawtext = ""

            def _escape_font_path_for_drawtext(p: str) -> str:
                """
                ffmpeg drawtext parses ':' as option separators, so Windows drive-letter paths like
                'C:/Windows/Fonts/arial.ttf' must escape the colon: 'C\\:/Windows/Fonts/arial.ttf'.
                """
                if not p:
                    return p
                p = p.replace("\\", "/")
                # Escape ':' for ffmpeg filter option parsing.
                # On Windows, the most robust form in drawtext is C\\:/Windows/... when used inside quotes.
                if os.name == 'nt' and len(p) >= 2 and p[1] == ':' and p[0].isalpha():
                    # drive letter
                    p = p.replace(":", "\\\\:")
                else:
                    p = p.replace(":", "\\:")
                # Avoid single quotes inside filter values
                p = p.replace("'", "\\'")
                return p

            def _probe_recorded_epoch_seconds(path: str) -> int:
                """
                Try to read recording time from metadata (creation_time). If missing,
                fall back to file modified time. Returns epoch seconds (local time).
                """
                # 1) ffprobe creation_time
                try:
                    ffprobe_path = resource_path('ffprobe.exe')
                    if os.path.exists(ffprobe_path) and os.path.exists(path):
                        cmd = [
                            ffprobe_path,
                            "-v", "error",
                            "-show_entries", "format_tags=creation_time:stream_tags=creation_time",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            path
                        ]
                        startupinfo, creationflags = _get_subprocess_startupinfo()
                        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                             startupinfo=startupinfo, creationflags=creationflags, check=False)
                        raw = (res.stdout or "").strip().splitlines()
                        raw = [x.strip() for x in raw if x.strip()]
                        if raw:
                            # ffprobe may output multiple lines; use the first one.
                            s = raw[0]
                            # Normalize ISO-8601
                            # Example: 2025-12-11T22:34:01.000000Z
                            if s.endswith("Z"):
                                s = s[:-1] + "+00:00"
                            dt = datetime.fromisoformat(s)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            # Convert to local time then to epoch seconds
                            return int(dt.astimezone().timestamp())
                except Exception:
                    pass
                # 2) fallback: file modified time
                try:
                    return int(os.path.getmtime(path))
                except Exception:
                    return int(datetime.now().timestamp())

            def _probe_duration_seconds(path: str) -> float:
                try:
                    ffprobe_path = resource_path('ffprobe.exe')
                    if not os.path.exists(ffprobe_path) or not os.path.exists(path):
                        return 0.0
                    cmd = [
                        ffprobe_path,
                        "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        path
                    ]
                    startupinfo, creationflags = _get_subprocess_startupinfo()
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                         startupinfo=startupinfo, creationflags=creationflags, check=False)
                    s = (res.stdout or "").strip()
                    return float(s) if s else 0.0
                except Exception:
                    return 0.0

            def _escape_drawtext_text(text: str) -> str:
                """Escape characters that conflict with drawtext option parsing."""
                return (
                    text.replace("\\", "\\\\")
                        .replace(":", "\\:")
                        .replace("'", "\\'")
                )

            # IMPORTANT:
            # Your ffmpeg build is emitting "Fontconfig error: Cannot load default config file",
            # which happens when using drawtext with `font=` (fontconfig). To avoid fontconfig,
            # we always use `fontfile=` and point at a concrete TTF file.
            #
            # On Windows the drive-letter colon (C:) MUST be escaped for drawtext parsing.
            # The canonical working form is: C\\:/Windows/Fonts/arial.ttf  (which ffmpeg sees as C\:/...)
            if os.name == 'nt':
                # Prefer known Windows font files.
                candidates = [
                    "C:/Windows/Fonts/arial.ttf",
                    "C:/Windows/Fonts/segoeui.ttf",
                    "C:/Windows/Fonts/calibri.ttf",
                ]
                font_path = next((p for p in candidates if os.path.exists(p)), "")
                font_mono_path = "C:/Windows/Fonts/consola.ttf" if os.path.exists("C:/Windows/Fonts/consola.ttf") else font_path
                font_spec_main = f"fontfile={_escape_font_path_for_drawtext(font_path)}"
                font_spec_mono = f"fontfile={_escape_font_path_for_drawtext(font_mono_path)}"
            else:
                font_path = "C:/Windows/Fonts/arial.ttf"
                if not os.path.exists(font_path):
                    font_path = ""
                font_spec_main = f"fontfile={_escape_font_path_for_drawtext(font_path)}" if font_path else ""
                font_spec_mono = font_spec_main

            # Recorded time base (epoch seconds); used for "recorded" overlays.
            rec_epoch = _probe_recorded_epoch_seconds(input_file)
            dur_sec = _probe_duration_seconds(input_file)

            # Helpers for drawtext expansions:
            # - Use localtime(epoch_seconds + t) so the overlay reflects recorded time-of-day.
            # - Use eif() to force integer seconds for localtime/gmtime.
            rec_dt = datetime.fromtimestamp(rec_epoch).astimezone()
            rec_dt_text = _escape_drawtext_text(rec_dt.strftime("%Y-%m-%d %H:%M:%S"))
            rec_time_only_text = _escape_drawtext_text(rec_dt.strftime("%H:%M:%S"))
            remaining_text = (
                f"%{{eif\\:({dur_sec:.3f}-t)\\:d}}s" if dur_sec > 0 else "N/A"
            )

            # All presets: top-left (x=10,y=10)
            if overlay_type == 'Elapsed Time':
                drawtext = (
                    "drawtext="
                    f"{font_spec_main}:"
                    "text='%{pts\\:hms}':"
                    "x=10:y=10:"
                    "fontcolor=white:fontsize=22:"
                    "box=1:boxcolor=black@0.35"
                )
            elif overlay_type == 'Recorded Time':
                drawtext = (
                    "drawtext="
                    f"{font_spec_main}:"
                    f"text='Recorded {rec_time_only_text}':"
                    "x=10:y=10:"
                    "fontcolor=white:fontsize=22:"
                    "box=1:boxcolor=black@0.35"
                )
            elif overlay_type == 'Recorded Date/Time':
                drawtext = (
                    "drawtext="
                    f"{font_spec_main}:"
                    f"text='Recorded {rec_dt_text}':"
                    "x=10:y=10:"
                    "fontcolor=white:fontsize=22:"
                    "box=1:boxcolor=black@0.35"
                )
            elif overlay_type == 'Recorded Date/Time + Remaining':
                # Two lines: date/time then remaining
                drawtext = (
                    "drawtext="
                    f"{font_spec_main}:"
                    f"text='Recorded {rec_dt_text}':"
                    "x=10:y=10:"
                    "fontcolor=white:fontsize=22:"
                    "box=1:boxcolor=black@0.35"
                    ","
                    "drawtext="
                    f"{font_spec_main}:"
                    f"text='Remaining {remaining_text}':"
                    "x=10:y=10+lh+4:"
                    "fontcolor=white:fontsize=20:"
                    "box=1:boxcolor=black@0.35"
                )
            elif overlay_type == 'CRTV Cam':
                # Two lines: blinking REC + recorded time
                # enable expression uses commas; escape them as \, so they don't split filterchain parsing.
                rec_enable = "enable='lt(mod(t\\,1)\\,0.5)'"
                drawtext = (
                    "drawtext="
                    f"{font_spec_main}:"
                    "text='REC':"
                    "x=10:y=10:"
                    "fontcolor=red:fontsize=22:"
                    "box=1:boxcolor=black@0.35:"
                    f"{rec_enable}"
                    ","
                    "drawtext="
                    f"{font_spec_mono}:"
                    f"text='Recorded {rec_time_only_text}':"
                    "x=10:y=10+lh+4:"
                    "fontcolor=0x00FF00:fontsize=22:"
                    "box=1:boxcolor=black@0.35"
                )
            else:
                # Unknown label -> treat as none
                drawtext = ""

            # Check if we already have a filter (like scale from gif code, though this func is main command)
            # This function uses -s for size, but let's check if we can append -vf
            if drawtext:
                logger.info(f"Text overlay enabled: {overlay_type}")
                command.extend(['-vf', drawtext])

        video_size = settings.get('video_size', '')
        if video_size and video_size.lower() != 'auto':
            command.extend(['-s', video_size])
        framerate = settings.get('framerate', '')
        if framerate and framerate.lower() != 'auto':
            command.extend(['-r', framerate])

        # Keyframe Interval (GOP)
        gop = settings.get('keyframe_interval', 0)
        try:
            gop = int(gop)
            if gop > 0:
                command.extend(['-g', str(gop)])
        except Exception:
            pass

    output_format = settings.get('output_format', 'mp4')
    if output_format:
        command.extend(['-f', output_format])

    # Custom Console Command
    custom_args = settings.get('custom_console_command', '').strip()
    if custom_args:
        # Split by spaces but respect quotes would be better, but for simple flags split is okay
        # For more robust parsing we could use shlex.split
        import shlex
        try:
            command.extend(shlex.split(custom_args))
        except Exception:
            # Fallback for simple split if shlex fails
            command.extend(custom_args.split())

    command.append(output_file)
    logger.debug(f"FFmpeg command: {' '.join(command)}")
    return command

def build_gif_commands(settings, input_file, output_file, temp_palette_path):
    """Return (palette_cmd, encode_cmd) for palette-optimized GIF.
    If quick mode is enabled, return (None, single_pass_cmd).
    """
    ffmpeg_path = resource_path('ffmpeg.exe')
    def _coerce_int(value, default_value):
        try:
            return int(value)
        except Exception:
            try:
                return int(float(str(value).strip()))
            except Exception:
                return default_value
    fps = _coerce_int(settings.get('gif_fps', 10), 10)
    max_w = _coerce_int(settings.get('gif_max_width', 640), 640)
    loop = 0 if settings.get('gif_loop', True) else 1  # ffmpeg -loop 0 means infinite
    quick = bool(settings.get('gif_quick', False))
    scale = f"scale=min({max_w},iw):-2:flags=lanczos"
    vf = f"fps={fps},{scale}"

    if quick:
        # No palettegen/use; fast but lower quality
        quick_cmd = [
            ffmpeg_path, '-y', '-i', input_file,
            '-vf', vf,
            '-loop', str(loop),
            output_file
        ]
        return None, quick_cmd

    palette_cmd = [
        ffmpeg_path, '-y', '-i', input_file,
        '-vf', f"{vf},palettegen=stats_mode=full",
        temp_palette_path
    ]
    encode_cmd = [
        ffmpeg_path, '-y', '-i', input_file, '-i', temp_palette_path,
        '-lavfi', f"{vf}[x];[x][1:v]paletteuse=dither=sierra2_4a",
        '-loop', str(loop),
        output_file
    ]
    return palette_cmd, encode_cmd

def preprocess_file(file_path):
    """
    Attempt to fix minor file corruption by re-muxing with '-c copy'.
    """
    ffmpeg_path = resource_path('ffmpeg.exe')
    fixed_file = f"{file_path}_fixed"
    command = [ffmpeg_path, '-i', file_path, '-c', 'copy', fixed_file]
    try:
        startupinfo, creationflags = _get_subprocess_startupinfo()
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                       startupinfo=startupinfo, creationflags=creationflags)
        shutil.move(fixed_file, file_path)
        logger.info(f"Preprocessed and fixed file {file_path}.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to preprocess file {file_path}: {e}")
        if os.path.exists(fixed_file):
            os.remove(fixed_file)
        return False

def has_audio_stream(file_path):
    """
    Check if a given file contains an audio stream.
    """
    ffprobe_path = resource_path('ffprobe.exe')
    command = [
        ffprobe_path,
        '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=codec_type',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    try:
        startupinfo, creationflags = _get_subprocess_startupinfo()
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
                                startupinfo=startupinfo, creationflags=creationflags)
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking audio stream for {file_path}: {e}")
        return False
