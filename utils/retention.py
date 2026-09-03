import json
import os
import time

from utils.logger import logger
from utils.paths import get_data_dir

_PENDING_FILE = os.path.join(get_data_dir(), 'pending_deletions.json')

def _read_pending() -> list[dict[str, str]]:
    if not os.path.exists(_PENDING_FILE):
        return []
    try:
        with open(_PENDING_FILE, encoding='utf-8') as f:
            return json.load(f) or []
    except Exception:
        return []

def _write_pending(items: list[dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(_PENDING_FILE), exist_ok=True)
    # Atomic-ish write
    tmp = _PENDING_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            logger.debug("_write_pending: suppressed error", exc_info=True)
    try:
        os.replace(tmp, _PENDING_FILE)
    except Exception:
        # The scheduled-deletion list was not updated, so files the user asked
        # to be removed later will simply never be removed. Worth reporting.
        logger.exception("Could not update the pending-deletion list at %s.", _PENDING_FILE)
        try:
            os.remove(tmp)
        except OSError:
            logger.debug("_write_pending: could not remove temp file", exc_info=True)

def add_pending_deletion(path: str, due_utc_epoch: float) -> None:
    items = _read_pending()
    # De-duplicate by path
    found = False
    for it in items:
        if it.get('path') == path:
            it['due_utc'] = float(due_utc_epoch)
            found = True
            break
    if not found:
        items.append({'path': path, 'due_utc': float(due_utc_epoch)})
    _write_pending(items)

def process_pending_deletions(log_cb=None) -> int:
    """Delete any files whose due_utc has passed. Returns files actually deleted.

    Runs at every startup, over a JSON file that may have been written by an
    older build, half-written by a crash, or edited by hand. An entry that
    cannot be acted on is therefore *discarded* rather than kept: keeping it
    means reconsidering it at every start forever, and one such entry used to
    raise out of this whole function -- the due time was parsed outside the
    try -- so a single bad record silently stopped all retention.

    Only a genuine, retryable failure (the file is locked, say) keeps its
    entry for a later attempt.
    """
    items = _read_pending()
    if not items:
        return 0

    now = time.time()
    remaining: list[dict[str, str]] = []
    deleted = 0

    for entry in items:
        if not isinstance(entry, dict):
            logger.warning("Discarding a malformed pending deletion: %r", entry)
            continue

        path = entry.get('path')
        if not path or not isinstance(path, str):
            logger.warning("Discarding a pending deletion with no usable path: %r",
                           entry)
            continue

        try:
            due = float(entry.get('due_utc', 0))
        except (TypeError, ValueError):
            logger.warning(
                "Discarding the pending deletion for %s: its due time %r is not "
                "a number.", path, entry.get('due_utc'))
            continue

        if due > now:
            remaining.append(entry)
            continue

        if os.path.isdir(path):
            # os.remove refuses a directory, so this would be retried at every
            # startup for as long as the folder exists.
            logger.warning(
                "Discarding the pending deletion for %s: it is a directory, not "
                "a file.", path)
            continue

        try:
            if os.path.exists(path):
                os.remove(path)
                deleted += 1
                if log_cb:
                    try:
                        log_cb(f"[retention] Deleted overdue file: {path}")
                    except Exception:
                        logger.debug("retention log callback failed", exc_info=True)
            # A file that has already gone needs no further action, and its
            # entry is dropped by not being added to `remaining`.
        except OSError:
            logger.warning("Could not delete %s yet; will retry.", path,
                           exc_info=True)
            remaining.append(entry)

    _write_pending(remaining)
    return deleted
