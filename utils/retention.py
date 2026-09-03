import json
import os
import time
from typing import List, Dict

from utils.paths import get_data_dir
from utils.logger import logger

_PENDING_FILE = os.path.join(get_data_dir(), 'pending_deletions.json')

def _read_pending() -> List[Dict[str, str]]:
    if not os.path.exists(_PENDING_FILE):
        return []
    try:
        with open(_PENDING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) or []
    except Exception:
        return []

def _write_pending(items: List[Dict[str, str]]) -> None:
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
    """Delete any files whose due_utc <= now. Returns number of deletions attempted."""
    items = _read_pending()
    if not items:
        return 0
    now = time.time()
    remaining = []
    deleted = 0
    for it in items:
        path = it.get('path')
        due = float(it.get('due_utc', 0))
        if due <= now and path:
            try:
                if os.path.exists(path):
                    os.remove(path)
                deleted += 1
                if log_cb:
                    try:
                        log_cb(f"[retention] Deleted overdue file: {path}")
                    except Exception:
                        logger.debug("process_pending_deletions: suppressed error", exc_info=True)
            except Exception:
                # Keep entry to retry later
                remaining.append(it)
        else:
            remaining.append(it)
    _write_pending(remaining)
    return deleted



