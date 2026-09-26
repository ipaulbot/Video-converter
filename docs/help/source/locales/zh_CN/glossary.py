"""Simplified Chinese glossary. Term keys stay in English (see locales/en/glossary.py)."""
from __future__ import annotations

GLOSSARY_TITLE = "术语表"

GLOSSARY_INTRO = (
    "本指南中使用的术语。凡是在转换日志中会看到的 FFmpeg 术语,均保留原文。"
)

GLOSSARY_HEADERS = ("术语", "含义")

GLOSSARY_ROWS: list[tuple[str, str]] = [
    ("Container",
     "容器:承载视频和音频流的文件封装格式,例如 MP4、MKV 或 AVI。容器就是文件扩展名"
     "所表示的内容;它与内部使用的编解码器是两回事。"),
    ("Codec",
     "编解码器:用于压缩流的方案。H.264 (libx264) 和 HEVC (libx265) 是视频编解码器;"
     "AAC 和 MP3 是音频编解码器。"),
    ("FFmpeg",
     "NVC 用来执行实际转换的命令行媒体工具。它的输出就是转换日志中显示的内容。"),
    ("FFprobe",
     "FFmpeg 的检查工具。NVC 用它读取时长、流、编解码器和其他元数据,而无需转换任何"
     "内容。"),
    ("Stream copy",
     "流复制:将媒体重写到新容器而不重新编码。快速且无损,但只有在目标容器支持现有流"
     "时才可行。也称为重新封装 (remux)。"),
    ("Remux",
     "重新封装:更改文件的容器,同时保持其中的流不变。参见流复制。"),
    ("Transcode",
     "转码:对流进行解码并重新编码,会改变画质,并且比流复制耗时得多。"),
    ("Keyframe",
     "关键帧:完整存储的帧,而不是相对于相邻帧的差异。定位和无损剪辑只能精确落在关键"
     "帧上。"),
    ("GOP",
     "图像组 (Group of Pictures):关键帧之间的间隔。GOP 越短,拖动定位越精确,但文件"
     "也越大。"),
    ("Bitrate",
     "比特率:每秒媒体所用的数据量,通常以 kbps 或 Mbps 计。比特率越高,画质通常越好,"
     "文件也越大。"),
    ("GPU encoding",
     "GPU 编码:使用专用视频硬件(NVIDIA 的 NVENC、AMD 的 AMF、Intel 的 Quick Sync)"
     "代替 CPU 进行编码。速度快得多,编解码器支持取决于您的驱动程序。"),
    ("DirectShow",
     "NVC 用来从本地设备录制的 Windows 采集接口。源写作 video=设备名称。"),
    ("Media Foundation",
     "媒体播放器用来解码和播放受支持媒体的 Windows 播放框架。"),
    ("RTSP",
     "大多数 IP 和网络摄像头使用的流媒体协议。源写作 URL,例如 "
     "rtsp://192.168.1.10/stream。"),
    ("GenICam",
     "Basler 及其他工业摄像头使用的通用摄像头接口。请在 Basler pylon Viewer 中配置这些"
     "摄像头。"),
    ("Preset",
     "预设:保存的录制器配置,以 JSON 形式存放在 "
     r"Public\Documents\Noldus\NVC\MediaRecorder\Presets 下。"),
    ("Sync offset",
     "同步偏移:在组合网格或画中画录制中将某一源提前或延后的时间调整,使各源对齐。"),
    ("Picture-in-picture",
     "画中画:一种录制器输出模式,源 1 填满画面,其他已启用的源以小窗形式显示在左下"
     "方,全部保存在一个文件中。"),
    ("Screen capture",
     "屏幕捕获:一种录制器源类型,录制整个桌面、单个显示器、单个窗口或屏幕的某个区域,"
     "而不是摄像头。"),
    ("Frame step",
     "逐帧:按照片段的帧率精确前进或后退一帧。"),
    ("Playlist",
     "播放列表:媒体播放器单个面板的有序媒体文件列表。只有一个面板时,下一项会自动"
     "开始播放。"),
    ("Administrator (elevation)",
     "管理员(提权):以管理员权限运行 NVC,以便 PC 报告能够读取受保护的 Windows "
     "数据。"),
    ("Tool tab",
     "工具选项卡:主窗口中可通过“设置 -- 工具”隐藏或显示的选项卡。"),
    ("Retention period",
     "保留期:转换成功后,NVC 在删除原始文件之前保留它的时长。待删除项在重新启动后"
     "仍然有效。"),
    ("Redaction",
     "脱敏:在共享 PC 报告之前,始终对许可证密钥、序列号、MAC 地址和用户路径等敏感值"
     "进行遮蔽。"),
]
