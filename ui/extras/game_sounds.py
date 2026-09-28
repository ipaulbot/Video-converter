"""BallBuster XT sound effects: the WAVs in graphics/balls/sfx (made by
scripts/make_game_sounds.py) played through QSoundEffect.

`enabled` is the player's speaker toggle (persisted as settings['game_sound']);
`auto_muted` is set by the host while a conversion or recording runs so the
game never plays over real work. A file that fails to load is skipped (logged
once) and never raises."""
from __future__ import annotations

import os

from PyQt5.QtCore import QObject, QUrl

from utils.logger import logger
from utils.resources import resource_path

SOUND_NAMES = (
    "shoot", "bounce", "stick", "pop", "pop2", "pop3", "drop", "bomb",
    "reel", "payout", "level", "over",
)


def sfx_dir() -> str:
    return resource_path(os.path.join("graphics", "balls", "sfx"))


class GameSounds(QObject):
    def __init__(self, parent=None, enabled: bool = True, persist=None):
        super().__init__(parent)
        self.enabled = bool(enabled)
        self.auto_muted = False
        # persist(key, value) writes the setting; None = do not persist (tests)
        self.persist = persist
        self._effects = {}
        self._load_failed = set()
        self._loaded = False

    # ── state ────────────────────────────────────────────────────────
    @property
    def muted(self) -> bool:
        return (not self.enabled) or self.auto_muted

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if self.persist is not None:
            self.persist("game_sound", self.enabled)

    def set_auto_muted(self, muted: bool):
        self.auto_muted = bool(muted)

    # ── playback ─────────────────────────────────────────────────────
    def play(self, name: str):
        if self.muted or name not in SOUND_NAMES:
            return
        self._play_effect(name)

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            from PyQt5.QtMultimedia import QSoundEffect
        except ImportError:
            logger.info("BallBuster sounds: QtMultimedia not available; staying silent")
            return
        for name in SOUND_NAMES:
            path = os.path.join(sfx_dir(), f"{name}.wav")
            if not os.path.exists(path):
                self._load_failed.add(name)
                continue
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(0.6)
            self._effects[name] = effect
        if self._load_failed:
            logger.info("BallBuster sounds missing: %s", ", ".join(sorted(self._load_failed)))

    def _play_effect(self, name: str):
        self._ensure_loaded()
        effect = self._effects.get(name)
        if effect is None:
            return
        try:
            if effect.status() == effect.Error:
                if name not in self._load_failed:
                    self._load_failed.add(name)
                    logger.info("BallBuster sound %s failed to load", name)
                return
            effect.play()
        except Exception:
            logger.debug("GameSounds._play_effect: suppressed error", exc_info=True)

    def loaded_names(self):
        """Names with a usable effect (after the first play attempt)."""
        self._ensure_loaded()
        return sorted(n for n, e in self._effects.items() if e.status() != e.Error)
