"""Pytest bootstrap for NVC 4.

Two jobs, both about making `python -m pytest` work with no arguments and no
environment setup:

1. Force the offscreen Qt platform *before* Qt is imported anywhere, so the
   suite never opens real windows. Without this the run stalls part-way and
   steals focus; with it the full suite finishes in about 17 seconds.
2. Put the project root on `sys.path`, so `ui.*` / `utils.*` / `conversion.*` /
   `pc_report.*` resolve regardless of the directory pytest was invoked from.

Deliberately NOT copied from VIO's conftest: its autouse top-level-widget
reaper and its `pytest_sessionfinish` cleanup. VIO needs those because a
session-long QApplication accumulating hidden windows crashes at interpreter
exit. NVC does not exhibit that -- the suite passes 315/315 cleanly without
them -- and both hang it:

  * `widget.close()` in teardown runs `VideoConverterApp.closeEvent`
    (ui/main_window.py:1676), whose `shutdown()` waits on the preview QProcess,
    the watchdog observer and the conversion worker.
  * even without `close()`, pumping `processEvents()` after every test re-arms
    the recorder's preview-retry timers in tests/test_multi_source_recorder_widget.py.

If a crash-at-exit ever does appear here, port the reaper then -- and gate it
so it never touches a widget with a custom `closeEvent`.
"""
import os
import sys
from pathlib import Path

# Must happen before the first PyQt5 import in the process.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

# One QApplication for the session. The test modules each do
# `QApplication.instance() or QApplication([])` in setUpClass, so this simply
# means the first one to ask gets a ready-made instance; it also lets modules
# that build a QPixmap at import time work during collection.
_app = QApplication.instance() or QApplication([])
