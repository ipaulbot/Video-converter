#!/usr/bin/env python3
"""Capture help-guide screenshots by driving the real application.

    python docs/help/source/capture_screenshots.py
    NVC_SHOTS_OFFSCREEN=1 python docs/help/source/capture_screenshots.py

Techniques worth preserving if you extend this:

* `_pump()` calls processEvents() rather than sleeping, so the app settles
  without a fixed delay that is either too short or wasted.
* `widget.grab()` captures a specific widget, so the result does not depend on
  what else is on the desktop.
* Tabs are looked up by their label, never by index. Tab order changes.
* Every shot is wrapped individually, so one broken view does not lose the run.

Offscreen mode produces usable images for most views, but anything relying on a
real video surface (the preview panel) renders empty. Those want a real
display; the script says which it skipped.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHOTS_DIR = Path(__file__).resolve().parents[1] / "screenshots"

if os.environ.get("NVC_SHOTS_OFFSCREEN") == "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Import the app the way it imports itself.
sys.path.insert(0, str(ROOT))

STUB_DEVICES = os.environ.get("NVC_SHOTS_STUB_DEVICES") == "1"
STUB_CAMERAS = ["Camera A", "Camera B"]
STUB_MICROPHONES = ["Microphone A", "Microphone B"]


def _stub_device_discovery() -> None:
    """Replace DirectShow discovery so screenshots never show real device names.

    The recorder widget imports the discovery functions by name, so the patch
    has to land on the widget module, not just on conversion.recording_sources.
    """
    import conversion.recording_sources as sources
    import ui.multi_source_recorder_widget as recorder

    def cameras(*_args, **_kwargs):
        return list(STUB_CAMERAS)

    def microphones(*_args, **_kwargs):
        return list(STUB_MICROPHONES)

    for module in (sources, recorder):
        module.discover_directshow_video_devices = cameras
        module.discover_directshow_audio_devices = microphones


from PyQt5.QtWidgets import QApplication, QTabWidget  # noqa: E402


def _pump(app, times: int = 8) -> None:
    """Let queued work and layout settle without a fixed sleep."""
    for _ in range(times):
        app.processEvents()


def _tab_index(tabs: QTabWidget, label: str) -> int | None:
    """Find a tab by its visible label. Never trust tab order."""
    for i in range(tabs.count()):
        if tabs.tabText(i).strip().lower() == label.strip().lower():
            return i
    return None


_seen_digests: dict[str, str] = {}


def _grab(widget, fig_id: str, filename: str, app) -> bool:
    import hashlib

    _pump(app)
    pixmap = widget.grab()
    if pixmap.isNull() or pixmap.width() < 8:
        print(f"  -- {fig_id}: nothing to grab")
        return False

    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SHOTS_DIR / filename
    if not pixmap.save(str(out)):
        print(f"  -- {fig_id}: could not write {out.name}")
        return False

    # A byte-identical render means the view never changed -- a hidden tab that
    # refused to become current, or a label that no longer matches. Saving it
    # anyway ships the wrong picture silently, so treat it as a failure and
    # remove the file.
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    if digest in _seen_digests:
        print(f"  -- {fig_id}: identical to {_seen_digests[digest]}; the view did "
              f"not change, so not keeping it")
        out.unlink(missing_ok=True)
        return False
    _seen_digests[digest] = fig_id

    print(f"  ok {fig_id} -> {out.name} ({pixmap.width()}x{pixmap.height()})")
    return True


def _make_test_clip():
    """A 6 s colour-bar MP4 in %TEMP%, made with the bundled ffmpeg. None on failure."""
    import subprocess
    import tempfile

    from utils.resources import resource_path

    out = Path(tempfile.gettempdir()) / "nvc_help_fig08_clip.mp4"
    cmd = [resource_path("ffmpeg.exe"), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=25",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  -- FIG-08: could not make a test clip: {exc}")
        return None
    return str(out)


def main() -> int:
    import figures as figures_mod

    app = QApplication.instance() or QApplication([])

    if STUB_DEVICES:
        _stub_device_discovery()
        print("  (DirectShow discovery stubbed: stand-in camera and microphone names)")

    from ui.main_window import VideoConverterApp
    window = VideoConverterApp()
    window.resize(1400, 900)
    window.show()
    _pump(app, 20)

    # apply_tool_tab_visibility() hides any tool tab that is switched off in
    # settings, and setCurrentIndex on a hidden tab silently falls back to tab
    # 0. Force every tool tab visible for the capture run WITHOUT saving, so
    # the operator's own settings are untouched.
    try:
        visible = window.settings.get("visible_tool_tabs", {})
        window.settings["visible_tool_tabs"] = dict.fromkeys(visible, True)
        window.apply_tool_tab_visibility()
        _pump(app, 10)
        print(f"  (forced {sum(1 for v in visible.values() if not v)} hidden "
              f"tool tab(s) visible for this run; settings not saved)")
    except Exception:
        print("  ! could not force tool tabs visible; some shots may be skipped")

    catalog = {f["id"]: f["filename"] for f in figures_mod.FIGURES}
    captured: list[str] = []
    skipped: list[str] = []

    def attempt(fig_id: str, fn) -> None:
        try:
            widget = fn()
            if widget is None:
                skipped.append(fig_id)
                print(f"  -- {fig_id}: view not reachable here")
                return
            if _grab(widget, fig_id, catalog[fig_id], app):
                captured.append(fig_id)
            else:
                skipped.append(fig_id)
        except Exception:
            skipped.append(fig_id)
            print(f"  -- {fig_id}: {traceback.format_exc(limit=1).strip().splitlines()[-1]}")

    tabs = getattr(window, "tabs", None) or window.findChild(QTabWidget)

    def show_tab(label: str):
        if tabs is None:
            return None
        index = _tab_index(tabs, label)
        if index is None:
            return None
        tabs.setCurrentIndex(index)
        _pump(app, 12)
        return window

    # FIG-00: the whole window at rest.
    attempt("FIG-00", lambda: window)

    # FIG-01 / FIG-02: the settings dialog. Built directly rather than through
    # the menu action, so it can be grabbed without a modal event loop.
    def settings_tab(label: str):
        from ui.settings_dialog import SettingsDialog
        from utils.config import load_settings
        dialog = SettingsDialog(load_settings(), parent=window)
        dialog.setModal(False)
        dialog.show()
        _pump(app, 12)
        inner = dialog.findChild(QTabWidget)
        if inner is not None:
            index = _tab_index(inner, label)
            if index is not None:
                inner.setCurrentIndex(index)
                _pump(app, 8)
        return dialog

    attempt("FIG-01", lambda: settings_tab("General"))
    attempt("FIG-02", lambda: settings_tab("Format"))

    attempt("FIG-03", lambda: show_tab("Converted Files"))
    attempt("FIG-04", lambda: show_tab("Video Inspection Tool"))
    attempt("FIG-05", lambda: show_tab("PC Report"))
    attempt("FIG-06", lambda: show_tab("Lossless Editor"))
    attempt("FIG-07", lambda: show_tab("Multi-Source Recorder"))

    # FIG-08: the Media Player with a clip. The widget is built lazily by the
    # main window, so ask the window for it rather than reaching into the tab.
    def media_player_with_clip():
        if os.environ.get("NVC_SHOTS_OFFSCREEN") == "1":
            print("  -- FIG-08: needs a real display (video surface is black offscreen)")
            return None
        if show_tab("Media Player") is None:
            return None
        widget = window._ensure_media_player_widget()
        _pump(app, 10)
        clip = _make_test_clip()
        if clip is None:
            return None
        widget.set_visible_panel_count(1)
        panel = widget.panels[0]
        if not panel.load_media(clip):
            return None
        # Let the backend report duration, then park on a visible frame.
        for _ in range(60):
            _pump(app, 4)
            if panel.player is not None and panel.player.duration() > 0:
                break
        widget.play_all()
        for _ in range(30):
            _pump(app, 4)
            if panel.player is not None and panel.player.position() >= 1000:
                break
        widget.pause_all()
        _pump(app, 10)
        return window

    attempt("FIG-08", media_player_with_clip)

    # FIG-09: the recorder's Video Settings dialog, shown non-modally like the
    # settings dialog above, with rows 1-2 filled from the stub device list.
    def recorder_video_settings():
        if show_tab("Multi-Source Recorder") is None:
            return None
        from ui.multi_source_recorder_widget import VideoSettingsDialog
        recorder = window.multi_source_recorder_widget
        recorder.directshow_devices = (
            list(STUB_CAMERAS)
            if STUB_DEVICES
            else recorder.discover_directshow_devices()
        )
        if STUB_DEVICES:
            recorder._apply_audio_devices(STUB_MICROPHONES)
        dialog = VideoSettingsDialog(
            recorder.source_rows,
            recorder.output_controls(),
            recorder,
            recorder.button_style,
        )
        dialog.setModal(False)
        dialog.show()
        _pump(app, 12)
        cameras = recorder.directshow_devices[:2]
        for index, camera in enumerate(cameras):
            (
                row_enabled,
                row_label,
                _type,
                row_device,
                _fps,
                _res,
                row_audio_name,
                row_audio,
                _off,
            ) = dialog.dialog_rows[index]
            row_enabled.setChecked(True)
            row_label.setText(f"Video {index + 1}")
            row_device.setText(camera)
            row_audio_name.setText(f"Audio {index + 1}")
            if STUB_DEVICES:
                mic_index = row_audio.findText(
                    STUB_MICROPHONES[index % len(STUB_MICROPHONES)]
                )
                if mic_index >= 0:
                    row_audio.setCurrentIndex(mic_index)
        _pump(app, 12)
        return dialog

    attempt("FIG-09", recorder_video_settings)

    print(f"\ncaptured {len(captured)}, skipped {len(skipped)}")
    if skipped:
        print("skipped: " + ", ".join(skipped))
        print("Take these by hand on a real display; see SHOTLIST.md.")

    # Tear the window down while the QApplication is still alive.
    window.close()
    window.deleteLater()
    _pump(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
