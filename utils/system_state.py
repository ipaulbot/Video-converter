import json
import os
from typing import List, Tuple, Dict, Any

from .paths import get_data_dir

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
    state = _read_state()
    raw = state.get("high_scores") or []
    out: List[Tuple[str, int, int]] = []
    try:
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                name, score, level = item[0], int(item[1]), int(item[2])
                out.append((str(name)[:3].upper(), score, level))
    except Exception:
        return []
    return out


def set_high_scores(scores: List[Tuple[str, int, int]]) -> None:
    # Store as list of triples [name, score, level]
    state = _read_state()
    serializable: List[List[Any]] = []
    for name, score, level in scores:
        serializable.append([str(name)[:3].upper(), int(score), int(level)])
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
        pass


