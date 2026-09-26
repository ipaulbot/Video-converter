#!/usr/bin/env python3
"""Capture help-guide screenshots by driving the real application.

    NVC_SHOTS_STUB_DEVICES=1 python docs/help/source/capture_screenshots.py
    NVC_SHOTS_OFFSCREEN=1 python docs/help/source/capture_screenshots.py

Nothing personal may end up in a figure: no user or machine names, no personal
device names, no paths under the user profile. Hence the device-name stubs,
the neutral clip location, the disabled live previews and the synthetic tile
frames below.

Techniques worth preserving if you extend this:

* `_pump()` calls processEvents() rather than sleeping, so the app settles
  without a fixed delay that is either too short or wasted.
* `widget.grab()` captures a specific widget, so the result does not depend on
  what else is on the desktop.
* Tabs are looked up by their label, never by index. Tab order changes.
* Every shot is wrapped individually, so one broken view does not lose the run.

By default the window is parked off-screen (moved to -7000,-7000) and every
shot is a `widget.grab()`, so the run never reads pixels from the display and
can go while other windows -- another NVC, a browser -- are open on top. The
one view grab() cannot render is the Media Player's native video surface;
FIG-08 gets the clip's decoded frame composited into that tile instead (see
`_composite_video_frame`). Set NVC_SHOTS_ONSCREEN=1 to show the window and
read FIG-08 from the screen the old way.

Offscreen mode (NVC_SHOTS_OFFSCREEN=1, Qt's offscreen platform) still works
for CI-style runs; it uses the same composite path for FIG-08.
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

# Park every window off-screen and render with grab() unless told otherwise.
ON_SCREEN = os.environ.get("NVC_SHOTS_ONSCREEN") == "1"
PARK_POS = (-7000, -7000)


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


def _disable_live_previews() -> None:
    """Build every recorder widget with auto_preview=False.

    The main window loads the operator's saved sources into the recorder as it
    starts, and with previews on that opens their real cameras -- or, for a
    screen-capture source, streams their own desktop into the FIG-07 tiles.
    A help figure must never contain that. The tiles get synthetic frames from
    `_stand_in_preview_frames()` instead.
    """
    import ui.multi_source_recorder_widget as recorder

    original_init = recorder.MultiSourceRecorderWidget.__init__

    def quiet_init(self, *args, **kwargs):
        kwargs["auto_preview"] = False
        original_init(self, *args, **kwargs)

    recorder.MultiSourceRecorderWidget.__init__ = quiet_init


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


def _park(window) -> None:
    """Keep a shown window off every monitor so it never covers the user's work."""
    if not ON_SCREEN:
        window.move(*PARK_POS)


def _extract_frame(clip: str, at_seconds: float) -> Path | None:
    """One decoded frame of `clip` as a PNG in %TEMP%, via the bundled ffmpeg."""
    import subprocess
    import tempfile

    from utils.resources import resource_path

    out = Path(tempfile.gettempdir()) / "nvc_help_fig08_frame.png"
    cmd = [resource_path("ffmpeg.exe"), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{at_seconds:.3f}", "-i", clip, "-frames:v", "1", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  -- FIG-08: could not extract a frame: {exc}")
        return None
    return out if out.exists() else None


def _stand_in_preview_frames(count: int) -> list[bytes]:
    """`count` synthetic MJPEG frames (ffmpeg test patterns) for the FIG-07 tiles.

    Returned as JPEG bytes so they can go through the recorder's own
    `_render_pending_preview_frames()` path, exactly like a live preview frame.
    """
    import subprocess
    import tempfile

    from utils.resources import resource_path

    patterns = ["smptebars", "testsrc2", "rgbtestsrc", "yuvtestsrc"]
    frames: list[bytes] = []
    for index in range(count):
        out = Path(tempfile.gettempdir()) / f"nvc_help_fig07_tile{index + 1}.jpg"
        source = f"{patterns[index % len(patterns)]}=size=640x360:rate=1"
        cmd = [resource_path("ffmpeg.exe"), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", source, "-frames:v", "1", "-q:v", "3", str(out)]
        try:
            subprocess.run(cmd, check=True, timeout=60)
            frames.append(out.read_bytes())
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  -- FIG-07: could not make a stand-in tile frame: {exc}")
            break
    return frames


def _composite_video_frame(pixmap, window, video_widget, frame_png: Path):
    """Paint the clip's frame where the native video surface sits in `pixmap`.

    grab() renders the widget tree, but Media Foundation draws the video into
    its own child window, so the tile comes out black. The frame is the same
    one the player is showing (extracted at the paused position), letterboxed
    into the surface rectangle exactly as the presenter would show it.
    """
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtGui import QColor, QPainter, QPixmap

    frame = QPixmap(str(frame_png))
    if frame.isNull():
        return pixmap
    origin = video_widget.mapTo(window, QPoint(0, 0))
    target_w, target_h = video_widget.width(), video_widget.height()
    scaled = frame.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    painter = QPainter(pixmap)
    painter.fillRect(origin.x(), origin.y(), target_w, target_h, QColor("black"))
    painter.drawPixmap(origin.x() + (target_w - scaled.width()) // 2,
                       origin.y() + (target_h - scaled.height()) // 2, scaled)
    painter.end()
    return pixmap


def _grab(widget, fig_id: str, filename: str, app, screen: bool = False,
          composite=None) -> bool:
    """Save `widget` as `filename`.

    `screen=True` (only honoured with NVC_SHOTS_ONSCREEN=1) captures the
    widget's on-screen rectangle from the display instead of rendering the
    widget tree; the window must then be visible and unobscured. Otherwise the
    shot is widget.grab(), and `composite`, if given, is applied to the pixmap
    before saving -- how FIG-08 gets its video frame without reading the screen.
    """
    import hashlib

    _pump(app)
    if screen and ON_SCREEN:
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        pixmap = app.primaryScreen().grabWindow(
            0, top_left.x(), top_left.y(), widget.width(), widget.height())
    else:
        pixmap = widget.grab()
        if composite is not None:
            pixmap = composite(pixmap)
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


def _clip_dir() -> Path:
    """Where the FIG-08 test clip lives while the run lasts.

    The Inspect panel prints the clip's full path in the shot, so it must not
    be under the user's profile (%TEMP% contains the user name). The Public
    Videos folder is neutral; it is removed again by _remove_test_clip().
    """
    public = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    return public / "Videos" / "NVC Help"


def _make_test_clip():
    """A 6 s colour-bar MP4, made with the bundled ffmpeg. None on failure."""
    import subprocess

    from utils.resources import resource_path

    try:
        _clip_dir().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"  -- FIG-08: cannot create {_clip_dir()}: {exc}")
        return None
    out = _clip_dir() / "Session 1.mp4"
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


def _remove_test_clip() -> None:
    import shutil
    shutil.rmtree(_clip_dir(), ignore_errors=True)


def main() -> int:
    import figures as figures_mod

    app = QApplication.instance() or QApplication([])

    if STUB_DEVICES:
        _stub_device_discovery()
        print("  (DirectShow discovery stubbed: stand-in camera and microphone names)")
    _disable_live_previews()
    print("  (recorder live previews off: FIG-07 tiles show ffmpeg test patterns)")

    from ui.main_window import VideoConverterApp
    window = VideoConverterApp()
    window.resize(1400, 900)
    window.show()
    _park(window)
    _pump(app, 20)
    if not ON_SCREEN:
        print("  (window parked off-screen; every shot is a widget.grab())")

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

    composites: dict[str, object] = {}

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
            if _grab(widget, fig_id, catalog[fig_id], app, screen=screen,
                     composite=composites.pop(fig_id, None)):
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
        _park(dialog)
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
        # Live previews are off (see _disable_live_previews); fill the enabled
        # tiles through the recorder's own frame path with test patterns.
        recorder.stop_preview_processes()
        enabled_rows = [i for i, row in enumerate(recorder.source_rows) if row[0].isChecked()]
        frames = _stand_in_preview_frames(len(enabled_rows))
        for row_index, frame in zip(enabled_rows, frames, strict=False):
            recorder.preview_pending_frames[row_index] = frame
        recorder._render_pending_preview_frames()
        _pump(app, 4)
        return window

    def restore_recorder_tab():
        folder_edit.setText(original_folder)
        row2_enabled.setChecked(row2_was_checked)

    attempt("FIG-07", recorder_tab, after=restore_recorder_tab)

    # FIG-08: the Media Player with a clip. The widget is built lazily by the
    # main window, so ask the window for it rather than reaching into the tab.
    original_size = window.size()

    def media_player_with_clip():
        if show_tab("Media Player") is None:
            return None
        widget = window._ensure_media_player_widget()
        # The transport row is wider than the default window; widen it so the
        # shot is not cut off by the tab's horizontal scrollbar.
        window.resize(1600, 900)
        if ON_SCREEN:
            window.move(0, 0)
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
        if not ON_SCREEN:
            # grab() cannot see the native surface: paint the frame the player
            # is paused on into the tile instead of reading the display.
            position_s = (panel.player.position() if panel.player else 1000) / 1000.0
            frame = _extract_frame(clip, position_s)
            if frame is None or panel.video_widget is None:
                return None
            composites["FIG-08"] = (
                lambda pixmap: _composite_video_frame(pixmap, window,
                                                      panel.video_widget, frame))
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
            recorder.directshow_audio_devices = list(STUB_MICROPHONES)
        dialog = VideoSettingsDialog(
            recorder.source_rows,
            recorder.output_controls(),
            recorder,
            recorder.button_style,
        )
        dialog.setModal(False)
        dialog.show()
        _park(dialog)
        open_dialogs.append(dialog)
        _pump(app, 12)
        if STUB_DEVICES:
            dialog.apply_discovered_audio_devices(STUB_MICROPHONES)
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

    # Tear the window down while the QApplication is still alive, then remove
    # the test clip (the player must have released it first).
    player_widget = getattr(window, "media_player_widget", None)
    if player_widget is not None:
        player_widget.shutdown()
        _pump(app, 10)
    window.close()
    window.deleteLater()
    from PyQt5.QtCore import QEvent
    for _ in range(3):
        _pump(app, 10)
        # processEvents() does not run deferred deletes; the media backend only
        # lets go of the clip once the QMediaPlayer objects are really destroyed.
        app.sendPostedEvents(None, QEvent.DeferredDelete)
    _remove_test_clip()
    if _clip_dir().exists():
        print(f"  (note: {_clip_dir()} still held open; remove it by hand)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
