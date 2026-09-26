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


def _wait_ms(app, ms: int) -> None:
    """Let real time pass while the event loop runs.

    _pump() only drains queued events; a media backend that decodes on its own
    threads needs wall-clock time. A QTimer object is used rather than
    QTimer.singleShot, which this repository forbids.
    """
    from PyQt5.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(ms)
    loop.exec_()


def _tab_index(tabs: QTabWidget, label: str) -> int | None:
    """Find a tab by its visible label. Never trust tab order."""
    for i in range(tabs.count()):
        if tabs.tabText(i).strip().lower() == label.strip().lower():
            return i
    return None


_seen_digests: dict[str, str] = {}


def _grab(widget, fig_id: str, filename: str, app, screen: bool = False) -> bool:
    """Save `widget` as `filename`.

    `screen=True` captures the widget's on-screen rectangle from the display
    instead of rendering the widget tree. widget.grab() cannot see a native
    video surface (the Media Player's QVideoWidget renders through Media
    Foundation's own presenter), so that view comes out black unless it is
    read back from the screen. The window must be visible and unobscured.
    """
    import hashlib

    _pump(app)
    if screen:
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        pixmap = app.primaryScreen().grabWindow(
            0, top_left.x(), top_left.y(), widget.width(), widget.height())
    else:
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

    def attempt(fig_id: str, fn, screen: bool = False, after=None) -> None:
        """Run `fn` to reach a view, grab it, then always run `after` (if any).

        `after` undoes any state `fn` changed for the shot -- a scrubbed path,
        a resized window -- so a failed grab never leaves the app altered.
        """
        try:
            widget = fn()
            if widget is None:
                skipped.append(fig_id)
                print(f"  -- {fig_id}: view not reachable here")
                return
            if _grab(widget, fig_id, catalog[fig_id], app, screen=screen):
                captured.append(fig_id)
            else:
                skipped.append(fig_id)
        except Exception:
            skipped.append(fig_id)
            print(f"  -- {fig_id}: {traceback.format_exc(limit=1).strip().splitlines()[-1]}")
        finally:
            if after is not None:
                try:
                    after()
                    _pump(app, 4)
                except Exception:
                    print(f"  ! {fig_id}: cleanup failed; check the app state")

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
    open_dialogs: list = []

    def settings_tab(label: str):
        from ui.settings_dialog import SettingsDialog
        from utils.config import load_settings
        dialog = SettingsDialog(load_settings(), parent=window)
        dialog.setModal(False)
        dialog.show()
        open_dialogs.append(dialog)
        _pump(app, 12)
        inner = dialog.findChild(QTabWidget)
        if inner is not None:
            index = _tab_index(inner, label)
            if index is not None:
                inner.setCurrentIndex(index)
                _pump(app, 8)
        return dialog

    def close_dialogs():
        # A non-modal dialog left open would sit on top of every later
        # screen-grabbed view (FIG-08 reads pixels from the display).
        while open_dialogs:
            open_dialogs.pop().close()

    attempt("FIG-01", lambda: settings_tab("General"), after=close_dialogs)
    attempt("FIG-02", lambda: settings_tab("Format"), after=close_dialogs)

    # FIG-03: the Video Converter tab, its Converted Files table filled with
    # stand-in rows so the status icons are visible without converting anything
    # and without listing the operator's own files.
    def converted_files_with_rows():
        if show_tab("Video Converter") is None:
            return None
        table = window.converted_files_widget
        table.add_queued_file("Session 1.mp4", r"C:\Videos\Converted")
        table.update_file_status("Session 1.mp4", "success")
        table.add_queued_file("Session 2.mp4", r"C:\Videos\Converted")
        table.update_file_status("Session 2.mp4", "processing")
        table.add_queued_file("Session 3.mp4", r"C:\Videos\Converted")
        _pump(app, 8)
        return window

    attempt("FIG-03", converted_files_with_rows)
    # FIG-04: the Media Player with its Inspect panel open (the inspector moved
    # here from its own tab on 2026-09-26).
    def player_with_inspect_panel():
        if show_tab("Media Player") is None:
            return None
        player = window._ensure_media_player_widget()
        _pump(app, 8)
        player.inspect_btn.setChecked(True)
        _pump(app, 8)
        return window

    attempt("FIG-04", player_with_inspect_panel)
    attempt("FIG-05", lambda: show_tab("PC Report"))
    attempt("FIG-06", lambda: show_tab("Lossless Editor"))

    # FIG-07: the recorder tab. The File location field defaults to the
    # operator's own Videos folder, which contains their user name; show a
    # neutral path instead and put it back afterwards. Row 2 is enabled so the
    # shot matches its caption.
    recorder = window.multi_source_recorder_widget
    folder_edit = recorder.output_controls()["output_folder"]
    original_folder = folder_edit.text()
    row2_enabled = recorder.source_rows[1][0]
    row2_was_checked = row2_enabled.isChecked()

    def recorder_tab():
        if show_tab("Multi-Source Recorder") is None:
            return None
        folder_edit.setText(r"C:\Videos")
        row2_enabled.setChecked(True)
        _pump(app, 8)
        return window

    def restore_recorder_tab():
        folder_edit.setText(original_folder)
        row2_enabled.setChecked(row2_was_checked)

    attempt("FIG-07", recorder_tab, after=restore_recorder_tab)

    # FIG-08: the Media Player with a clip. The widget is built lazily by the
    # main window, so ask the window for it rather than reaching into the tab.
    original_size = window.size()

    def media_player_with_clip():
        if os.environ.get("NVC_SHOTS_OFFSCREEN") == "1":
            print("  -- FIG-08: needs a real display (video surface is black offscreen)")
            return None
        if show_tab("Media Player") is None:
            return None
        widget = window._ensure_media_player_widget()
        # The transport row is wider than the default window; widen it so the
        # shot is not cut off by the tab's horizontal scrollbar.
        window.move(0, 0)
        window.resize(1600, 900)
        window.raise_()
        window.activateWindow()
        _pump(app, 10)
        clip = _make_test_clip()
        if clip is None:
            return None
        # Drive the Panels combo rather than the layout method so the combo
        # and the panel count agree in the picture.
        from ui.media_player_widget import PANEL_COUNT_OPTIONS
        widget.panels_combo.setCurrentIndex(PANEL_COUNT_OPTIONS.index(1))
        _pump(app, 6)
        panel = widget.panels[0]
        if not panel.load_media(clip):
            return None
        # Media Foundation reports duration and decodes asynchronously; the
        # pumps above do not let wall-clock time pass, so wait for real.
        for _ in range(40):
            _wait_ms(app, 100)
            if panel.player is not None and panel.player.duration() > 0:
                break
        widget.play_all()
        for _ in range(40):
            _wait_ms(app, 100)
            if panel.player is not None and panel.player.position() >= 1000:
                break
        widget.pause_all()
        _wait_ms(app, 300)
        return window

    attempt("FIG-08", media_player_with_clip, screen=True,
            after=lambda: window.resize(original_size))

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
        open_dialogs.append(dialog)
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

    attempt("FIG-09", recorder_video_settings, after=close_dialogs)

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
