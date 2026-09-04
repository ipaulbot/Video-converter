import json
import os
from typing import List, Tuple, Dict, Any

from .paths import get_data_dir
from utils.logger import logger

SYSTEM_FILE_NAME = "system.nvc"


def _state_path() -> str:
    return os.path.join(get_data_dir(), SYSTEM_FILE_NAME)


def _read_state() -> Dict[str, Any]:
    path = _state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_state(state: Dict[str, Any]) -> None:
    path = _state_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        # Fail silently; caller can ignore persistence failures
        pass


def get_game_unlocked() -> bool:
    state = _read_state()
    return bool(state.get("game_unlocked", False))


def set_game_unlocked(unlocked: bool) -> None:
    state = _read_state()
    state["game_unlocked"] = bool(unlocked)
    _write_state(state)


def get_high_scores() -> List[Tuple[str, int, int]]:
    """Return the saved high scores, skipping any row that will not parse.

    The try used to wrap the whole loop, so a single malformed row -- a
    non-numeric score in a hand-edited or partly-written file -- returned []
    and silently discarded every score the user had earned. Each row is now
    validated on its own.
    """
    state = _read_state()
    raw = state.get("high_scores")
    if not isinstance(raw, (list, tuple)):
        return []

    out: List[Tuple[str, int, int]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        try:
            name, score, level = str(item[0]), int(item[1]), int(item[2])
        except (TypeError, ValueError):
            logger.debug("Skipping an unreadable high-score row: %r", item)
            continue
        out.append((name[:3].upper(), score, level))
    return out


def set_high_scores(scores: List[Tuple[str, int, int]]) -> None:
    """Persist high scores as [name, score, level] triples.

    A row that will not coerce is dropped rather than raising: this is called
    from the game loop, where losing one score must not take the game with it.
    """
    state = _read_state()
    serializable: List[List[Any]] = []
    for item in scores or []:
        try:
            name, score, level = item
            serializable.append([str(name)[:3].upper(), int(score), int(level)])
        except (TypeError, ValueError):
            logger.debug("Skipping an unstorable high-score row: %r", item)
    state["high_scores"] = serializable
    _write_state(state)


def get_best_level() -> int:
    state = _read_state()
    try:
        return int(state.get("best_level", 0))
    except Exception:
        return 0


def set_best_level(level: int) -> None:
    state = _read_state()
    try:
        state["best_level"] = int(level)
        _write_state(state)
    except Exception:
        logger.debug("set_best_level: suppressed error", exc_info=True)


