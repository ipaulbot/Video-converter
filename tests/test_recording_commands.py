import unittest

from conversion.recording_commands import (
    build_combined_grid_record_command,
    build_directshow_camera_settings_command,
    build_directshow_list_options_command,
    build_directshow_preview_frame_command,
    build_directshow_preview_stream_command,
    build_directshow_record_with_preview_command,
    build_multi_source_record_command,
    build_preview_stream_command,
    build_record_command,
    recording_layout_preview_rects,
)
from conversion.recording_sources import (
    apply_axis_rtsp_recording_options,
    axis_mjpeg_preview_url,
    parse_directshow_video_options,
)


class RecordingCommandTests(unittest.TestCase):
    def test_axis_mjpeg_preview_url_uses_vapix_preview_endpoint(self):
        preview_url = axis_mjpeg_preview_url("rtsp://root:pw@192.168.200.4:554/axis-media/media.amp")

        self.assertEqual(
            preview_url,
            "http://root:pw@192.168.200.4/axis-cgi/mjpg/video.cgi?resolution=480x270&fps=15",
        )

    def test_axis_mjpeg_preview_url_ignores_non_axis_rtsp_sources(self):
        self.assertEqual(axis_mjpeg_preview_url("rtsp://camera/stream"), "")

    def test_axis_rtsp_recording_options_add_resolution_and_fps_query(self):
        source = apply_axis_rtsp_recording_options(
            "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp",
            frame_rate="30.00",
            resolution="1920 x 1080",
        )

        self.assertEqual(
            source,
            "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp?resolution=1920x1080&fps=30",
        )

    def test_axis_rtsp_recording_options_preserve_existing_query(self):
        source = apply_axis_rtsp_recording_options(
            "rtsp://camera/axis-media/media.amp?videocodec=h264",
            frame_rate="25.00",
            resolution="Auto",
        )

        self.assertEqual(source, "rtsp://camera/axis-media/media.amp?videocodec=h264&fps=25")

    def test_axis_rtsp_recording_options_treat_auto_frame_rate_as_driver_default(self):
        source = apply_axis_rtsp_recording_options(
            "rtsp://camera/axis-media/media.amp?videocodec=h264",
            frame_rate="Auto",
            resolution="1280 x 720",
        )

        self.assertEqual(source, "rtsp://camera/axis-media/media.amp?videocodec=h264&resolution=1280x720")

    def test_url_source_uses_normal_input(self):
        command = build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", "")

        self.assertIn("-i", command)
        self.assertNotIn("dshow", command)
        self.assertEqual(command[-1], "out.mp4")

    def test_dshow_source_uses_dshow_input(self):
        command = build_record_command("ffmpeg.exe", "video=Camera 1", "out.mp4", "h264", "60")

        self.assertIn("-f", command)
        self.assertEqual(command[command.index("-f") + 1], "dshow")
        self.assertIn("-t", command)

    def test_directshow_record_uses_video_and_audio_in_one_input(self):
        command = build_record_command(
            "ffmpeg.exe",
            "video=Camera A",
            "out.mp4",
            "h264",
            "",
            audio_device="Microphone A",
        )

        self.assertEqual(
            command,
            [
                "ffmpeg.exe", "-hide_banner", "-y",
                "-rtbufsize", "512M", "-f", "dshow",
                "-i", 'video="Camera A":audio="Microphone A"',
                "-map", "0:v", "-map", "0:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k",
                "out.mp4",
            ],
        )

    def test_directshow_specialized_builder_uses_same_input_audio(self):
        command = build_directshow_record_with_preview_command(
            "ffmpeg.exe",
            "video=Camera A",
            "out.mp4",
            audio_device="Microphone A",
        )

        self.assertEqual(command.count("-i"), 1)
        self.assertEqual(command[command.index("-i") + 1], 'video="Camera A":audio="Microphone A"')
        self.assertIn(
            ["-map", "0:v", "-map", "0:a"],
            [command[index:index + 4] for index in range(len(command) - 3)],
        )
        self.assertEqual(command[command.index("-b:a") + 1], "128k")

    def test_copy_mode_uses_stream_copy(self):
        command = build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mkv", "copy", "")

        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        self.assertIn("-an", command)

    def test_rtsp_copy_mode_drops_audio_for_mp4_compatibility(self):
        command = build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", "")

        self.assertIn("-c:v", command)
        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        self.assertIn("-an", command)
        self.assertNotIn("-c", command)

    def test_rtsp_record_adds_directshow_audio_as_second_input(self):
        command = build_record_command(
            "ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "h264", "",
            audio_device="Microphone A",
        )

        self.assertEqual(
            command,
            [
                "ffmpeg.exe", "-hide_banner", "-y",
                "-rtsp_transport", "tcp", "-timeout", "5000000",
                "-i", "rtsp://camera/stream",
                "-f", "dshow", "-thread_queue_size", "1024",
                "-use_wallclock_as_timestamps", "1",
                "-i", 'audio="Microphone A"',
                "-map", "0:v", "-map", "1:a", "-shortest",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k",
                "out.mp4",
            ],
        )

    def test_file_copy_mode_keeps_video_copy_and_encodes_audio(self):
        command = build_record_command(
            "ffmpeg.exe", "sample.mp4", "out.mp4", "copy", "",
            audio_device="Microphone A",
        )

        self.assertEqual(
            command,
            [
                "ffmpeg.exe", "-hide_banner", "-y", "-i", "sample.mp4",
                "-f", "dshow", "-thread_queue_size", "1024",
                "-use_wallclock_as_timestamps", "1",
                "-i", 'audio="Microphone A"',
                "-map", "0:v", "-map", "1:a", "-shortest",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "out.mp4",
            ],
        )

    def test_audio_volume_fifty_adds_half_gain(self):
        command = build_record_command(
            "ffmpeg.exe", "sample.mp4", "out.mp4", "h264", "",
            audio_device="Microphone A", volume="50",
        )

        self.assertIn(
            ["-af", "volume=0.5"],
            [command[index:index + 2] for index in range(len(command) - 1)],
        )

    def test_no_audio_mute_and_zero_volume_all_emit_an(self):
        cases = [
            {"audio_device": "No Audio"},
            {"audio_device": "Microphone A", "mute": True},
            {"audio_device": "Microphone A", "volume": "0"},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                command = build_record_command(
                    "ffmpeg.exe", "sample.mp4", "out.mp4", "h264", "", **kwargs,
                )
                self.assertEqual(command.count("-i"), 1)
                self.assertIn("-an", command)
                self.assertNotIn("-c:a", command)

    def test_record_command_with_preview_pipe_for_rtsp_uses_shared_decoder_split(self):
        command = build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", "", preview_pipe=True)

        # RTSP recording with a live preview must share a single decoder/scheduler with
        # the preview tap, otherwise FFmpeg starves the MJPEG output and the preview
        # tile freezes while the file output keeps going. The same filter_complex
        # split=2 layout that works for DirectShow keeps the preview reliable here.
        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("split=2", filter_complex)
        self.assertIn("fps=20,scale=480:-1", filter_complex)
        self.assertIn("image2pipe", command)
        self.assertEqual(command[-1], "pipe:1")

    def test_record_preview_tee_maps_audio_only_to_file_leg(self):
        command = build_record_command(
            "ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "h264", "",
            preview_pipe=True, audio_device="Microphone A",
        )

        self.assertEqual(
            command,
            [
                "ffmpeg.exe", "-hide_banner", "-y",
                "-rtsp_transport", "tcp", "-timeout", "5000000",
                "-i", "rtsp://camera/stream",
                "-f", "dshow", "-thread_queue_size", "1024",
                "-use_wallclock_as_timestamps", "1",
                "-i", 'audio="Microphone A"',
                "-filter_complex",
                "[0:v]split=2[v][preview];[preview]fps=20,scale=480:-1[p]",
                "-map", "[v]", "-map", "1:a", "-shortest",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", "out.mp4",
                "-map", "[p]", "-q:v", "7",
                "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
            ],
        )
        pipe_map = command.index("[p]")
        self.assertNotIn("1:a", command[pipe_map:])

    def test_directshow_preview_tee_pipe_leg_is_video_only(self):
        command = build_directshow_record_with_preview_command(
            "ffmpeg.exe", "video=Camera A", "out.mp4",
            preview_pipe=True, audio_device="Microphone A",
        )

        self.assertEqual(command.count("0:a"), 1)
        pipe_map = command.index("[p]")
        self.assertNotIn("0:a", command[pipe_map:])
        self.assertEqual(command[-1], "pipe:1")

    def test_record_command_with_preview_pipe_for_directshow_uses_split_filter(self):
        command = build_record_command(
            "ffmpeg.exe",
            "video=HD Pro Webcam C920",
            "out.mp4",
            "copy",
            "",
            preview_pipe=True,
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("split=2", filter_complex)
        self.assertIn("fps=20,scale=480:-1", filter_complex)
        self.assertIn("image2pipe", command)
        self.assertEqual(command[-1], "pipe:1")

    def test_directshow_record_with_preview_applies_requested_input_format(self):
        command = build_directshow_record_with_preview_command(
            "ffmpeg.exe",
            "video=HD Pro Webcam C920",
            "out.mp4",
            "",
            frame_rate="30.00",
            resolution="1920 x 1080",
            preview_pipe=True,
        )
        input_index = command.index("-i")

        self.assertLess(command.index("-framerate"), input_index)
        self.assertEqual(command[command.index("-framerate") + 1], "30")
        self.assertLess(command.index("-video_size"), input_index)
        self.assertEqual(command[command.index("-video_size") + 1], "1920x1080")

    def test_directshow_preview_treats_auto_frame_rate_as_driver_default(self):
        command = build_directshow_preview_stream_command(
            "ffmpeg.exe",
            "Basler GenICam Source",
            frame_rate="Auto",
            resolution="1280 x 1024",
        )
        input_index = command.index("-i")

        self.assertNotIn("-framerate", command[:input_index])
        self.assertLess(command.index("-video_size"), input_index)
        self.assertEqual(command[command.index("-video_size") + 1], "1280x1024")

    def test_directshow_recording_uses_larger_realtime_buffer_for_high_bandwidth_cameras(self):
        command = build_directshow_record_with_preview_command(
            "ffmpeg.exe",
            "video=Basler GenICam Source",
            "out.mp4",
            "",
            preview_pipe=True,
        )
        input_index = command.index("-i")

        self.assertLess(command.index("-rtbufsize"), input_index)
        self.assertEqual(command[command.index("-rtbufsize") + 1], "512M")

    def test_recording_commands_do_not_request_experimental_movflags(self):
        # Fragmented MP4 (+frag_keyframe+empty_moov+default_base_moof) was tried as a way to
        # keep the file playable when stop has to escalate to a forced kill, but on the user's
        # FFmpeg those flags caused the Axis RTSP stream-copy to produce no output file at all
        # and stalled the DirectShow preview pipe behind the libx264 encoder. Plain MP4
        # recordings save reliably; an interrupted recording will need to be repaired, which
        # is an acceptable trade-off versus losing every recording.
        commands = [
            build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", "", preview_pipe=True),
            build_record_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "copy", "", preview_pipe=True),
            build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", ""),
            build_record_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "h264", ""),
            build_directshow_record_with_preview_command(
                "ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "", preview_pipe=True,
            ),
            build_directshow_record_with_preview_command(
                "ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "5",
            ),
            build_combined_grid_record_command(
                "ffmpeg.exe",
                ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
                "combined.mp4",
                "",
                preview_pipe=True,
            ),
        ]

        for command in commands:
            self.assertNotIn("-movflags", command, f"unexpected -movflags in {command}")

    def test_h264_mode_uses_fast_encoding(self):
        command = build_record_command("ffmpeg.exe", "video=Camera 1", "out.mp4", "h264", "")

        self.assertEqual(command[command.index("-c:v") + 1], "libx264")
        self.assertIn("veryfast", command)

    def test_directshow_copy_mode_falls_back_to_h264_for_mp4_webcam_recording(self):
        command = build_record_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "copy", "")

        self.assertNotIn("-c", command)
        self.assertEqual(command[command.index("-c:v") + 1], "libx264")

    def test_directshow_camera_settings_command_opens_native_device_dialog(self):
        command = build_directshow_camera_settings_command("ffmpeg.exe", "HD Pro Webcam C920")

        self.assertIn("-show_video_device_dialog", command)
        self.assertEqual(command[command.index("-i") + 1], "video=HD Pro Webcam C920")
        self.assertIn("-f", command[command.index("-i") + 2:])
        self.assertEqual(command[-1], "NUL")

    def test_directshow_list_options_command_queries_driver_modes(self):
        command = build_directshow_list_options_command("ffmpeg.exe", "Basler GenICam Source")

        self.assertIn("-list_options", command)
        self.assertEqual(command[command.index("-list_options") + 1], "true")
        self.assertEqual(command[command.index("-i") + 1], "video=Basler GenICam Source")

    def test_parse_directshow_video_options_reads_resolution_and_fps(self):
        output = """
        [dshow @ 000]   pixel_format=yuyv422  min s=1280x1024 fps=30 max s=1280x1024 fps=30
        [dshow @ 000]   vcodec=mjpeg  min s=640x480 fps=15 max s=640x480 fps=15
        """

        modes = parse_directshow_video_options(output)

        self.assertIn({"resolution": "1280 x 1024", "frame_rate": "30.00"}, modes)
        self.assertIn({"resolution": "640 x 480", "frame_rate": "15.00"}, modes)
        self.assertEqual(len(modes), 2)

    def test_parse_directshow_video_options_includes_range_endpoints_for_dynamic_cameras(self):
        output = """
        [dshow @ 000]   vcodec=mjpeg  min s=640x480 fps=5 max s=1920x1080 fps=30
        [dshow @ 000]   pixel_format=yuyv422  min s=1280x1024 fps=30 max s=1280x1024 fps=30
        """

        modes = parse_directshow_video_options(output)

        self.assertEqual(
            modes,
            [
                {"resolution": "640 x 480", "frame_rate": "5.00"},
                {"resolution": "1920 x 1080", "frame_rate": "30.00"},
                {"resolution": "1280 x 1024", "frame_rate": "30.00"},
            ],
        )

    def test_directshow_preview_frame_command_captures_one_image(self):
        command = build_directshow_preview_frame_command("ffmpeg.exe", "HD Pro Webcam C920", "preview.jpg")

        self.assertEqual(command[command.index("-i") + 1], "video=HD Pro Webcam C920")
        self.assertEqual(command[command.index("-frames:v") + 1], "1")
        self.assertEqual(command[-1], "preview.jpg")

    def test_directshow_preview_stream_command_outputs_mjpeg_pipe(self):
        command = build_directshow_preview_stream_command("ffmpeg.exe", "HD Pro Webcam C920")

        self.assertEqual(command[command.index("-i") + 1], "video=HD Pro Webcam C920")
        self.assertIn("image2pipe", command)
        self.assertEqual(command[-1], "-")
        self.assertIn("fps=20,scale=480:-1", command)
        self.assertIn("-nostats", command)

    def test_directshow_preview_stream_command_applies_requested_input_mode(self):
        command = build_directshow_preview_stream_command(
            "ffmpeg.exe",
            "HD Pro Webcam C920",
            frame_rate="30.00",
            resolution="1920 x 1080",
        )
        input_index = command.index("-i")

        self.assertLess(command.index("-framerate"), input_index)
        self.assertEqual(command[command.index("-framerate") + 1], "30")
        self.assertLess(command.index("-video_size"), input_index)
        self.assertEqual(command[command.index("-video_size") + 1], "1920x1080")

    def test_rtsp_preview_stream_command_uses_normal_input(self):
        command = build_preview_stream_command("ffmpeg.exe", "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp")

        self.assertNotIn("dshow", command)
        self.assertEqual(command[command.index("-i") + 1], "rtsp://root:pw@192.168.200.4:554/axis-media/media.amp")
        self.assertIn("image2pipe", command)
        self.assertIn("fps=12,scale=360:-1", command)
        self.assertEqual(command[command.index("-q:v") + 1], "9")
        self.assertIn("-an", command)
        self.assertIn("-nostats", command)

    def test_rtsp_preview_stream_command_requests_low_latency_input(self):
        command = build_preview_stream_command("ffmpeg.exe", "rtsp://camera/stream")
        input_index = command.index("-i")

        self.assertLess(command.index("-fflags"), input_index)
        self.assertEqual(command[command.index("-fflags") + 1], "nobuffer")
        self.assertLess(command.index("-flags"), input_index)
        self.assertEqual(command[command.index("-flags") + 1], "low_delay")
        self.assertLess(command.index("-analyzeduration"), input_index)
        self.assertEqual(command[command.index("-analyzeduration") + 1], "0")
        self.assertLess(command.index("-probesize"), input_index)
        self.assertLess(command.index("-max_delay"), input_index)
        self.assertLess(command.index("-reorder_queue_size"), input_index)

    def test_rtsp_record_command_uses_stable_input_profile_without_low_latency_flags(self):
        command = build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", "")
        input_index = command.index("-i")

        self.assertLess(command.index("-rtsp_transport"), input_index)
        self.assertEqual(command[command.index("-rtsp_transport") + 1], "tcp")
        self.assertLess(command.index("-timeout"), input_index)
        self.assertNotIn("-stimeout", command)
        self.assertNotIn("-fflags", command)
        self.assertNotIn("-flags", command)
        self.assertNotIn("-analyzeduration", command)
        self.assertNotIn("-probesize", command)

    def test_rtsp_record_preview_command_uses_stable_input_profile_for_recording_quality(self):
        command = build_record_command("ffmpeg.exe", "rtsp://camera/stream", "out.mp4", "copy", "", preview_pipe=True)
        input_index = command.index("-i")

        self.assertLess(command.index("-rtsp_transport"), input_index)
        self.assertEqual(command[command.index("-rtsp_transport") + 1], "tcp")
        self.assertNotIn("-fflags", command)
        self.assertNotIn("-flags", command)
        self.assertNotIn("-analyzeduration", command)
        self.assertNotIn("-probesize", command)

    def test_combined_grid_rtsp_inputs_use_stable_recording_profile(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
            preview_pipe=True,
        )
        input_index = command.index("-i")

        self.assertLess(command.index("-rtsp_transport"), input_index)
        self.assertEqual(command[command.index("-rtsp_transport") + 1], "tcp")
        self.assertNotIn("-fflags", command)
        self.assertNotIn("-flags", command)
        self.assertNotIn("-analyzeduration", command)
        self.assertNotIn("-probesize", command)

    def test_preview_stream_command_keeps_low_latency_flags_for_idle_preview(self):
        command = build_preview_stream_command("ffmpeg.exe", "rtsp://camera/stream")

        self.assertIn("-fflags", command)
        self.assertEqual(command[command.index("-fflags") + 1], "nobuffer")
        self.assertIn("-flags", command)
        self.assertEqual(command[command.index("-flags") + 1], "low_delay")

    def test_directshow_record_command_writes_single_mp4_output(self):
        command = build_directshow_record_with_preview_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "5")

        self.assertIn("out.mp4", command)
        self.assertNotIn("image2pipe", command)
        self.assertEqual(command[-1], "out.mp4")
        self.assertIn("-t", command)

    def test_directshow_record_command_can_stream_preview_from_same_capture(self):
        command = build_directshow_record_with_preview_command(
            "ffmpeg.exe",
            "video=HD Pro Webcam C920",
            "out.mp4",
            "",
            preview_pipe=True,
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("split=2", filter_complex)
        self.assertIn("fps=20,scale=480:-1", filter_complex)
        self.assertIn("image2pipe", command)
        self.assertEqual(command[-1], "pipe:1")

    def test_directshow_record_command_does_not_attach_preview_pipe(self):
        command = build_directshow_record_with_preview_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "")

        self.assertNotIn("-filter_complex", command)
        self.assertNotIn("-", command[-1:])

    def test_directshow_record_command_uses_single_input(self):
        command = build_directshow_record_with_preview_command("ffmpeg.exe", "video=HD Pro Webcam C920", "out.mp4", "")

        self.assertEqual(command.count("-i"), 1)
        self.assertEqual(command[command.index("-i") + 1], "video=HD Pro Webcam C920")

    def test_combined_grid_command_writes_one_mp4_from_multiple_sources(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
        )

        self.assertEqual(command.count("-i"), 2)
        self.assertIn("xstack=inputs=2", command[command.index("-filter_complex") + 1])
        self.assertIn("-map", command)
        self.assertEqual(command[command.index("-map") + 1], "[v]")
        self.assertEqual(command[-1], "combined.mp4")

    def test_single_source_combined_grid_maps_optional_audio(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe", ["video=Camera A"], "combined.mp4",
            audio_device="Microphone A",
        )

        self.assertEqual(
            command,
            [
                "ffmpeg.exe", "-hide_banner", "-y",
                "-rtbufsize", "512M", "-f", "dshow", "-i", "video=Camera A",
                "-f", "dshow", "-thread_queue_size", "1024",
                "-use_wallclock_as_timestamps", "1",
                "-i", 'audio="Microphone A"',
                "-map", "0:v", "-map", "1:a", "-shortest",
                "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", "combined.mp4",
            ],
        )

    def test_combined_grid_maps_one_audio_stream_and_video_only_preview(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/one", "rtsp://camera/two"],
            "combined.mp4",
            preview_pipe=True,
            audio_device="Microphone A",
        )

        self.assertEqual(command.count('audio="Microphone A"'), 1)
        self.assertIn("2:a", command)
        self.assertEqual(command.count("-c:a"), 1)
        self.assertEqual(command[command.index("-b:a") + 1], "128k")
        pipe_map = command.index("[p]")
        self.assertNotIn("2:a", command[pipe_map:])

    def test_combined_grid_without_audio_keeps_an(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe", ["rtsp://camera/one", "rtsp://camera/two"], "combined.mp4",
        )

        self.assertIn("-an", command)
        self.assertNotIn("-c:a", command)

    def test_combined_grid_applies_selected_audio_volume(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe", ["rtsp://camera/one", "rtsp://camera/two"],
            "combined.mp4", audio_device="Microphone A", volume="50",
        )

        self.assertIn(
            ["-af", "volume=0.5"],
            [command[index:index + 2] for index in range(len(command) - 1)],
        )

    def test_combined_grid_command_uses_valid_three_source_layout(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920", "video=Basler GenICam Source"],
            "combined.mp4",
            "",
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("xstack=inputs=3", filter_complex)
        self.assertIn("layout=0_0|w0_0|0_h0", filter_complex)
        self.assertNotIn("0_0|w0_0|0_h0|w0_h0", filter_complex)

    def test_combined_grid_command_can_pipe_live_preview_frames(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
            preview_pipe=True,
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("split=2", filter_complex)
        self.assertIn("fps=20,scale=480:-1", filter_complex)
        self.assertIn("image2pipe", command)
        self.assertEqual(command[-1], "pipe:1")


class CombinedGridSyncTests(unittest.TestCase):
    def test_combined_grid_does_not_stamp_inputs_with_wall_clock(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
        )

        # Wall-clock timestamps gave each input a different timebase, so xstack's
        # frame-sync had to repeat/drop frames to reconcile them -- that is what made
        # the GigE tile choppy. The tiles are now aligned by per-input rebasing instead.
        self.assertNotIn("-use_wallclock_as_timestamps", command)

    def test_combined_grid_rebases_each_input_before_stacking(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        # Each tile is rebased to its OWN first frame so both streams share timebase 0
        # and the same CFR cadence; xstack then pairs them 1:1 (smooth, equal length).
        self.assertEqual(filter_complex.count("setpts=PTS-STARTPTS"), 2)
        self.assertLess(filter_complex.index("setpts=PTS-STARTPTS"), filter_complex.index("xstack"))

    def test_combined_grid_normalizes_each_input_to_a_common_frame_rate(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
            output_fps=25,
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        # Each input is resampled to the same rate so the tiles advance in lockstep
        # and end with identical frame counts.
        self.assertEqual(filter_complex.count("fps=25"), 2)

    def test_combined_grid_locks_the_output_frame_rate(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "",
            output_fps=25,
        )

        self.assertIn("-r", command)
        self.assertEqual(command[command.index("-r") + 1], "25")

    def test_combined_grid_opens_genicam_source_before_other_capture_devices(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920", "video=Basler GenICam Source"],
            "combined.mp4",
            "",
        )

        # Basler/GenICam must be the first dshow input opened or it fails BindToObject
        # when co-opened with another capture device in one process.
        webcam_input = command.index("video=HD Pro Webcam C920")
        basler_input = command.index("video=Basler GenICam Source")
        self.assertLess(basler_input, webcam_input)

    def test_combined_grid_keeps_tiles_in_original_row_order_despite_reordered_inputs(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920", "video=Basler GenICam Source"],
            "combined.mp4",
            "",
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        # Basler was opened first (input 0), webcam second (input 1), but the grid must
        # feed xstack in the user's row order: webcam tile (input 1) then Basler (input 0).
        xstack_segment = filter_complex[filter_complex.index("xstack") - 12:filter_complex.index("xstack")]
        self.assertIn("[v1][v0]", xstack_segment)

    def test_combined_grid_applies_per_source_sync_offset(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920", "video=Basler GenICam Source"],
            "combined.mp4",
            "",
            offsets_per_source=["0.75", ""],
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        # The webcam carries a +0.75s offset to fall back in line with a slower camera.
        # The offset is folded into that tile's own setpts (a plain -itsoffset would be
        # cancelled by the per-input PTS-STARTPTS rebase), and only one tile carries it.
        self.assertIn("setpts=PTS-STARTPTS+(0.75)/TB", filter_complex)
        self.assertEqual(filter_complex.count("/TB"), 1)

    def test_combined_grid_ignores_zero_or_blank_offsets(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920", "video=Basler GenICam Source"],
            "combined.mp4",
            "",
            offsets_per_source=["0", "0.00"],
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertNotIn("/TB", filter_complex)

    def test_combined_grid_duration_bounds_both_file_and_preview_outputs(self):
        command = build_combined_grid_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            "combined.mp4",
            "30",
            preview_pipe=True,
        )

        # File output and preview output both honor the duration so the never-ending
        # live preview tap cannot keep the process running past the requested length.
        self.assertEqual(command.count("-t"), 2)


class LayoutPreviewRectTests(unittest.TestCase):
    def test_no_sources_returns_no_rects(self):
        self.assertEqual(recording_layout_preview_rects("Combined grid", 0), [])

    def test_single_source_fills_the_frame(self):
        self.assertEqual(recording_layout_preview_rects("Combined grid", 1), [(0.0, 0.0, 1.0, 1.0)])

    def test_two_sources_are_side_by_side(self):
        rects = recording_layout_preview_rects("Combined grid", 2)
        self.assertEqual(rects, [(0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.5, 1.0)])

    def test_three_sources_use_two_over_one_grid(self):
        rects = recording_layout_preview_rects("Separate videos", 3)
        self.assertEqual(
            rects,
            [(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5), (0.0, 0.5, 0.5, 0.5)],
        )

    def test_four_sources_use_two_by_two_grid(self):
        rects = recording_layout_preview_rects("Combined grid", 4)
        self.assertEqual(len(rects), 4)
        self.assertIn((0.5, 0.5, 0.5, 0.5), rects)

    def test_picture_in_picture_keeps_first_source_full_and_insets_others(self):
        rects = recording_layout_preview_rects("Picture-in-picture", 3)
        self.assertEqual(rects[0], (0.0, 0.0, 1.0, 1.0))
        self.assertEqual(len(rects), 3)
        # Insets are smaller than the background tile.
        for _x, _y, w, h in rects[1:]:
            self.assertLess(w, 1.0)
            self.assertLess(h, 1.0)

    def test_count_is_clamped_to_four(self):
        self.assertEqual(len(recording_layout_preview_rects("Combined grid", 9)), 4)


class MultiSourceRecordCommandTests(unittest.TestCase):
    def test_opens_each_source_exactly_once(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920", "video=Basler GenICam Source"],
            ["axis.mp4", "webcam.mp4", "basler.mp4"],
        )

        # A single process opens every device exactly once: this is what avoids the
        # DirectShow "device already in use" conflict between a preview process and a
        # recording process.
        self.assertEqual(command.count("-i"), 3)
        self.assertEqual(command.count("video=HD Pro Webcam C920"), 1)
        self.assertEqual(command.count("video=Basler GenICam Source"), 1)

    def test_writes_one_output_file_per_source(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            ["axis.mp4", "webcam.mp4"],
        )

        self.assertEqual(command.count("axis.mp4"), 1)
        self.assertEqual(command.count("webcam.mp4"), 1)
        # File outputs appear in source order.
        self.assertLess(command.index("axis.mp4"), command.index("webcam.mp4"))

    def test_each_output_is_mapped_to_its_own_recording_label(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            ["axis.mp4", "webcam.mp4"],
        )

        def map_label_before(output_name):
            output_index = command.index(output_name)
            for token_index in range(output_index - 1, -1, -1):
                if command[token_index] == "-map":
                    return command[token_index + 1]
            return None

        self.assertEqual(map_label_before("axis.mp4"), "[rec0]")
        self.assertEqual(map_label_before("webcam.mp4"), "[rec1]")

    def test_normalizes_timestamps_per_input_for_synchronization(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            ["axis.mp4", "webcam.mp4"],
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        # Every input stream is rebased to a common zero start so cameras that connect
        # at slightly different wall-clock times line up instead of drifting ~1s apart.
        self.assertEqual(filter_complex.count("setpts=PTS-STARTPTS"), 2)

    def test_rtsp_inputs_use_stable_recording_profile(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            ["axis.mp4", "webcam.mp4"],
        )

        self.assertIn("-rtsp_transport", command)
        self.assertEqual(command[command.index("-rtsp_transport") + 1], "tcp")
        self.assertNotIn("-fflags", command)

    def test_directshow_inputs_request_large_realtime_buffer(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920"],
            ["webcam.mp4"],
        )

        self.assertIn("-rtbufsize", command)
        self.assertEqual(command[command.index("-rtbufsize") + 1], "512M")

    def test_applies_per_source_input_mode_options(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920"],
            ["webcam.mp4"],
            options_per_source=[{"frame_rate": "30.00", "resolution": "1920 x 1080"}],
        )
        input_index = command.index("-i")

        self.assertLess(command.index("-framerate"), input_index)
        self.assertEqual(command[command.index("-framerate") + 1], "30")
        self.assertLess(command.index("-video_size"), input_index)
        self.assertEqual(command[command.index("-video_size") + 1], "1920x1080")

    def test_combined_preview_pipe_stacks_all_sources(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            ["axis.mp4", "webcam.mp4"],
            preview_pipe=True,
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("split=2", filter_complex)
        self.assertIn("xstack=inputs=2", filter_complex)
        self.assertIn(f"fps={20},scale={480}:-1", filter_complex)
        self.assertIn("image2pipe", command)
        self.assertEqual(command[-1], "pipe:1")

    def test_single_source_preview_pipe_skips_xstack(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920"],
            ["webcam.mp4"],
            preview_pipe=True,
        )

        filter_complex = command[command.index("-filter_complex") + 1]
        self.assertIn("split=2", filter_complex)
        self.assertNotIn("xstack", filter_complex)
        self.assertEqual(command[-1], "pipe:1")

    def test_without_preview_pipe_there_is_no_image2pipe_output(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920"],
            ["webcam.mp4"],
        )

        self.assertNotIn("image2pipe", command)
        self.assertEqual(command[-1], "webcam.mp4")

    def test_duration_limit_applies_to_each_file_output(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["rtsp://camera/stream", "video=HD Pro Webcam C920"],
            ["axis.mp4", "webcam.mp4"],
            duration_seconds="10",
        )

        self.assertEqual(command.count("-t"), 2)

    def test_duration_limit_also_bounds_the_preview_pipe_output(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920"],
            ["webcam.mp4"],
            duration_seconds="10",
            preview_pipe=True,
        )

        # One -t for the file output and one for the preview output, otherwise the
        # never-ending live preview tap keeps the process running past the duration.
        self.assertEqual(command.count("-t"), 2)
        pipe_index = command.index("pipe:1")
        preview_t = command.index("-t", command.index("-q:v"))
        self.assertLess(preview_t, pipe_index)

    def test_audio_source_is_opened_once_and_mapped_into_a_file(self):
        command = build_multi_source_record_command(
            "ffmpeg.exe",
            ["video=HD Pro Webcam C920"],
            ["webcam.mp4"],
            audio_source="audio=Microphone (HD Pro Webcam C920)",
        )

        self.assertEqual(command.count("audio=Microphone (HD Pro Webcam C920)"), 1)
        # The audio input is the last input, so it is stream index 1 here and must be
        # mapped with an AAC encoder into the recording output.
        self.assertIn("1:a", command)
        self.assertEqual(command[command.index("-c:a") + 1], "aac")


if __name__ == "__main__":
    unittest.main()
