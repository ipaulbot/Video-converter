SETTINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "source_folder": {"type": "string"},
        "destination_folder": {"type": "string"},
        "backup_folder": {"type": "string"},
        "auto_run": {"type": "boolean"},
        "delete_after_conversion": {"type": "boolean"},
        "retention_time": {"type": "integer", "minimum": 0},
        "use_backup": {"type": "boolean"},
        "output_format": {"type": "string"},
        "video_codec": {"type": ["string", "null"]},
        "audio_codec": {"type": "string"},
        "copy_only": {"type": "boolean"},
        "locked": {"type": "boolean"},
        "start_time": {"type": "string"},
        "end_time": {"type": "string"},
        "no_time_restrictions": {"type": "boolean"},
        "video_size": {"type": ["string", "null"]},
        "video_bitrate": {"type": ["string", "null"]},
        "framerate": {"type": ["string", "null"]}
    },
    "required": [
        "auto_run",
        "delete_after_conversion",
        "retention_time",
        "use_backup",
        "output_format",
        "copy_only",
        "locked",
        "start_time",
        "end_time",
        "no_time_restrictions",
        "close_on_x",
        "startup_common"
    ]
}
