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


def main() -> int:
    import figures as figures_mod

    app = QApplication.instance() or QApplication([])

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
