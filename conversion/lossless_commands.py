def format_concat_file_line(path):
    normalized = path.replace("\\", "/")
    escaped = normalized.replace("'", "\\'")
    return f"file '{escaped}'"


def build_trim_command(ffmpeg_path, input_file, output_file, start_time, end_time):
    command = [ffmpeg_path, "-hide_banner", "-y"]
    if start_time:
        command.extend(["-ss", start_time])
    if end_time:
        command.extend(["-to", end_time])
    command.extend(["-i", input_file, "-map", "0", "-c", "copy", "-avoid_negative_ts", "make_zero", output_file])
    return command


def build_remux_command(ffmpeg_path, input_file, output_file):
    return [ffmpeg_path, "-hide_banner", "-y", "-i", input_file, "-map", "0", "-c", "copy", output_file]


def build_extract_audio_command(ffmpeg_path, input_file, output_file):
    return [ffmpeg_path, "-hide_banner", "-y", "-i", input_file, "-vn", "-map", "0:a:0?", "-c:a", "copy", output_file]


def build_remove_audio_command(ffmpeg_path, input_file, output_file):
    return [ffmpeg_path, "-hide_banner", "-y", "-i", input_file, "-map", "0:v", "-c:v", "copy", "-an", output_file]


def build_concat_command(ffmpeg_path, concat_list_file, output_file):
    return [
        ffmpeg_path,
        "-hide_banner",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_list_file,
        "-c",
        "copy",
        output_file,
    ]
