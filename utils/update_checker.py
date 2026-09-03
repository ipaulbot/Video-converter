"""Checking whether a newer NVC is available.

**Update checking is not configured.** `UPDATE_URL` below is still a
placeholder, so nothing is ever fetched. Rather than fabricate an answer,
both entry points now report that the feature is unconfigured:

* This module emitted `no_update` from a hardcoded mock response, so the app
  silently claimed to be up to date without asking anything.
* ui/main_window.check_for_updates hardcoded `latest_version = "2.3.0"` and
  compared it with a *string* comparison, so it always announced a fake
  update and offered to open `https://example.com/nvc/downloads`.

To turn the feature on, publish a JSON document shaped like

    {"version": "2.3.0", "url": "https://.../releases"}

set UPDATE_URL to it, and delete the `_is_configured` guard. `requests` is
already a declared dependency.
"""
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from utils.logger import logger
from utils.version import APP_VERSION

# Replace with a real, published version document to enable update checking.
UPDATE_URL = "https://raw.githubusercontent.com/yourusername/NVC/main/version.json"

# How long to wait for the version document before giving up.
REQUEST_TIMEOUT_SECONDS = 5

# Substrings that mark UPDATE_URL as still being the placeholder.
_PLACEHOLDER_MARKERS = ("yourusername", "example.com", "example.org")


def is_configured(url: str = None) -> bool:
    """True once UPDATE_URL points at a real version document."""
    target = UPDATE_URL if url is None else url
    if not target:
        return False
    return not any(marker in target for marker in _PLACEHOLDER_MARKERS)


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    """True if `latest` is a higher version than `current`.

    Compares numerically per component, so 2.10.0 beats 2.9.0 -- a string
    comparison gets that backwards, which is the bug the menu action had.
    Missing components count as zero, so 2.2 and 2.2.0 are equal rather than
    2.2 being treated as older.
    """
    def parts(value):
        return [int(piece) for piece in str(value).strip().split(".")]

    try:
        latest_parts, current_parts = parts(latest), parts(current)
    except (AttributeError, TypeError, ValueError):
        return False

    length = max(len(latest_parts), len(current_parts))
    latest_parts += [0] * (length - len(latest_parts))
    current_parts += [0] * (length - len(current_parts))
    return latest_parts > current_parts


class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str)   # version, url
    error_occurred = pyqtSignal(str)
    no_update = pyqtSignal()
    not_configured = pyqtSignal()

    def check_for_updates(self):
        if not is_configured():
            # Deliberately not `no_update`: nothing was checked, so claiming
            # the app is up to date would be a guess presented as a fact.
            logger.info("Update checking is not configured; skipping the check.")
            self.not_configured.emit()
            return

        try:
            import requests

            response = requests.get(UPDATE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()

            latest_version = data.get("version")
            download_url = data.get("url")
            if not latest_version or not download_url:
                self.error_occurred.emit(
                    "The version document is missing 'version' or 'url'.")
                return

            if is_newer(latest_version, APP_VERSION):
                self.update_available.emit(str(latest_version), str(download_url))
            else:
                self.no_update.emit()
        except Exception as exc:
            logger.warning("Update check failed: %s", exc)
            self.error_occurred.emit(str(exc))

    # Kept as a method for backwards compatibility with existing callers.
    def _is_newer(self, latest, current):
        return is_newer(latest, current)


class UpdateWorker(QThread):
    def __init__(self, checker):
        super().__init__()
        self.checker = checker

    def run(self):
        self.checker.check_for_updates()
