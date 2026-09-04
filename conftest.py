"""Pytest bootstrap for NVC 4.

Three jobs, all about making `python -m pytest` work with no arguments and no
environment setup:

1. Force the offscreen Qt platform *before* Qt is imported anywhere, so the
   suite never opens real windows. Without this the run stalls part-way and
   steals focus; with it the full suite finishes in about 17 seconds.
2. Put the project root on `sys.path`, so `ui.*` / `utils.*` / `conversion.*` /
   `pc_report.*` resolve regardless of the directory pytest was invoked from.
3. Destroy each test's own leftover windows while the QApplication is still
   alive (see `reap_hidden_top_level_widgets` below).
"""
import os
import sys
from pathlib import Path

# Must happen before the first PyQt5 import in the process.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Point NVC's data directory at a throwaway location for the whole session.
# utils.config derives config_file from it at import time, so this has to be
# set before anything imports it. Without this the suite reads -- and saves --
# the real user's settings: four tests in test_single_active_workflow were
# passing only because this developer happened to have the recorder tab
# enabled, and a test run could change which tabs the app shows.
import tempfile as _tempfile

_TEST_DATA_DIR = _tempfile.mkdtemp(prefix="nvc-test-data-")
os.environ["NVC_DATA_DIR"] = _TEST_DATA_DIR

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

# One QApplication for the session. The test modules each do
# `QApplication.instance() or QApplication([])` in setUpClass, so this simply
# means the first one to ask gets a ready-made instance; it also lets modules
# that build a QPixmap at import time work during collection.
_app = QApplication.instance() or QApplication([])


import pytest  # noqa: E402
from PyQt5.QtCore import QEvent  # noqa: E402


def _flush_deferred_deletes():
    """Run the pending DeferredDelete events and nothing else.

    This is the part that is easy to get wrong: `processEvents()` explicitly
    excludes DeferredDelete, so `deleteLater()` followed by `processEvents()`
    reads like a cleanup and destroys nothing at all. Three test modules did
    exactly that and leaked ~19,000 widgets between them.

    It is also deliberately *not* `processEvents()` for a second reason: that
    would fire timers, and the recorder suite arms preview-retry timers that
    then reopen capture devices in the middle of another test's teardown.
    """
    _app.sendPostedEvents(None, QEvent.DeferredDelete)


def _reap(widgets):
    for widget in widgets:
        try:
            shutdown = getattr(widget, "shutdown", None)
            if callable(shutdown):
                # Widgets that own timers, ffmpeg QProcesses or a watchdog
                # observer all expose shutdown(). Destroying one while those
                # are live delivers signals into a half-destroyed object,
                # which aborts the process instead of raising.
                shutdown()
        except Exception:
            pass          # a patched collaborator must not block destruction
        try:
            widget.deleteLater()
        except RuntimeError:
            pass          # the wrapped C++ object is already gone
    _flush_deferred_deletes()


@pytest.fixture(autouse=True)
def reap_hidden_top_level_widgets():
    """Destroy the hidden top-level windows each test created.

    `close()` only hides a QWidget; the C++ object survives until Python
    garbage-collects the wrapper, which under a session-long QApplication
    means "after the QApplication is gone" -- and destroying a QWidget at that
    point aborts the interpreter. Left alone this suite reached ~20,000 live
    widgets, ~3,900 of them top-level windows still holding armed timers and
    ffmpeg processes.

    To be clear about what this does and does not fix: the 0xC0000409 aborts
    that led here were *not* caused by the volume. They were an unowned
    `QTimer.singleShot` firing into a destroyed widget and a test fake missing
    a method -- see `TimerAndProcessOwnershipTests` in
    tests/test_multi_source_recorder_widget.py. This fixture keeps the leak
    from coming back and keeps destruction happening while the QApplication is
    still alive; it is not a substitute for widgets that clean up after
    themselves.

    Two guards, both learned the hard way:

    * **Never `close()`.** VIO's equivalent reaper does, but
      `VideoConverterApp.closeEvent` runs `shutdown()`, which waits on the
      preview QProcess, the watchdog observer and the conversion worker --
      that hangs the run. A hidden widget needs no close event to be
      destroyed. `_reap` calls `shutdown()` directly where it exists instead.
    * **Only already-hidden top-levels with no parent *widget*.**
      `topLevelWidgets()` also lists child windows -- a QComboBox popup, a
      QMenu -- whose owner may still be alive; deleting one out from under its
      owner is an access violation on the owner's next touch. Anything still
      visible belongs to something longer-lived than this test.

      The test is `parentWidget()`, not `parent()`: a widget parented to a
      plain QObject (a test's fake container, say) still *is* a top-level
      window and still has to be reaped, but `parent()` reports that QObject
      and would quietly skip it. That one exemption was enough to leave a live
      recorder widget, and its ffmpeg processes, running for the rest of the
      session.
    """
    before = list(QApplication.topLevelWidgets())
    yield
    _reap([w for w in QApplication.topLevelWidgets()
           if w not in before and w.parentWidget() is None and w.isHidden()])


def pytest_sessionfinish(session, exitstatus):
    """Tear the remaining top-levels down while the QApplication still exists,
    so nothing is destroyed by the interpreter's final GC pass."""
    _reap([w for w in QApplication.topLevelWidgets()
           if w.parentWidget() is None])
