"""Simplified Chinese builder strings. Same keys as locales/en/strings.py."""
from __future__ import annotations

STRINGS: dict = {
    "contents": "目录",
    "note": "注意",
    "figure_label": "图 %(n)d. %(caption)s",
    "version": "版本 %(version)s",
    "language": "语言:%(tag)s",
    "missing_figure": "%(fig_id)s -- 尚未截取屏幕截图(参见 SHOTLIST.md)",
    "toc_placeholder": "请在 Word 中打开此文档以生成目录。",
    "titles": {
        "help": "帮助",
        "quickstart": "快速入门指南",
    },
    "figure_captions": {
        "FIG-00": "NVC 主窗口,包含转换日志和预览面板。",
        "FIG-01": "设置,“常规”选项卡:启动、仅复制、托盘和 GPU 选项。",
        "FIG-02": "设置,“格式”选项卡:输出格式、编解码器和预设。",
        "FIG-03": "“视频转换器”选项卡:转换日志上方的“已转换文件”表。",
        "FIG-04": "媒体播放器中位于视频旁的“检查”面板,“摘要”子选项卡。",
        "FIG-05": "生成报告之前的“PC 报告”选项卡。",
        "FIG-06": "“无损编辑器”选项卡及其剪辑、重新封装和合并工具。",
        "FIG-07": "启用了两个源的“多源录制器”选项卡。",
        "FIG-08": "在单个面板中加载了一个片段的“媒体播放器”选项卡。",
        "FIG-09": "录制器的“视频设置”对话框,已配置两行摄像头。",
    },
}
