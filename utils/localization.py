"""Runtime translation: which languages exist, and loading the active one.

The pattern, which every UI module follows:

    from PyQt5.QtCore import QCoreApplication

    def _tr(source: str) -> str:
        \"\"\"Translate this module's strings under a stable context.\"\"\"
        return QCoreApplication.translate("MainWindow", source)

    label.setText(_tr("No Preview"))

Three rules make the strings extractable, and are enforced by
tests/test_i18n.py:

1. The argument is a plain string literal. Never an f-string, a variable, or a
   concatenation -- the extractor reads the source, so it can only see
   literals, and a translator needs the whole sentence anyway.
2. Interpolation uses ``%(name)s`` placeholders substituted *after* the call:
   ``_tr("Converted %(count)s files") % {"count": n}``. Word order differs
   between languages, so named placeholders let a translator reorder them.
3. The context string is fixed per module and never computed.

Strings are extracted and compiled by scripts/build_translations.py. Note
that pylupdate5 cannot see through a wrapper like ``_tr`` -- it matches call
names textually -- so extraction is done by walking the AST instead, which
also lets rule 1 be checked rather than merely documented.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from PyQt5.QtCore import QCoreApplication, QLocale, QSettings, QTranslator

from utils.logger import logger
from utils.resources import resource_path

TRANSLATIONS_DIRNAME: Final[str] = "translations"


@dataclass(frozen=True)
class LocaleSpec:
    """One selectable language."""

    code: str            # the tag used in settings and filenames, e.g. "zh-CN"
    native_name: str     # shown in the Language menu, in that language
    qm_basename: str     # translations/<qm_basename>.qm
    document_tag: str    # the matching manual in docs/help (see help_resolution)
    review_status: str   # "production" once a human has reviewed it


EN = LocaleSpec("en", "English", "nvc_en", "en", "production")
NL = LocaleSpec("nl", "Nederlands", "nvc_nl", "nl", "draft")
ZH_CN = LocaleSpec("zh-CN", "简体中文", "nvc_zh_CN", "zh-CN", "draft")

ALL_LOCALES: Final[tuple[LocaleSpec, ...]] = (EN, NL, ZH_CN)
_BY_CODE: Final[dict[str, LocaleSpec]] = {loc.code: loc for loc in ALL_LOCALES}

DEFAULT_LOCALE: Final[str] = EN.code

# Only reviewed languages are offered by default. The drafts exist so the
# pipeline and the .ts files are real and reviewable, not so that unreviewed
# machine output reaches a user.
PRODUCTION_LOCALES: Final[tuple[str, ...]] = tuple(
    loc.code for loc in ALL_LOCALES if loc.review_status == "production"
)
DRAFT_LOCALES: Final[tuple[str, ...]] = tuple(
    loc.code for loc in ALL_LOCALES if loc.review_status != "production"
)

# Set NVC_I18N_PREVIEW=1 to also offer the drafts, for reviewing them in situ.
PREVIEW_ENV_VAR: Final[str] = "NVC_I18N_PREVIEW"

_SETTINGS_ORG: Final[str] = "Noldus"
_SETTINGS_APP: Final[str] = "NVC"
_SETTINGS_KEY: Final[str] = "locale"

# Tolerated spellings of a locale tag, so a value saved by an older build or
# typed by hand still resolves.
_ALIASES: Final[dict[str, str]] = {
    "en-us": "en", "en_us": "en", "en_gb": "en", "en-gb": "en",
    "nl_nl": "nl", "nl-nl": "nl", "dutch": "nl",
    "zh": "zh-CN", "zh_cn": "zh-CN", "zh-cn": "zh-CN", "zh_hans": "zh-CN",
}


def locale_spec(code: str) -> LocaleSpec:
    return _BY_CODE[normalize_locale(code)]


def normalize_locale(value: object) -> str:
    """Map anything user- or settings-supplied onto a known locale code.

    Falls back to English rather than raising: this reads a settings value a
    previous build, or a person, may have written.
    """
    text = str(value or "").strip()
    if text in _BY_CODE:
        return text
    key = text.lower()
    for candidate in (key, key.replace("-", "_"), key.replace("_", "-")):
        if candidate in _ALIASES:
            return _ALIASES[candidate]
        if candidate in _BY_CODE:
            return candidate
    # Accept a bare or regional tag when only one locale uses it: en-AU -> en.
    prefix = key.split("-")[0].split("_")[0]
    matches = [c for c in _BY_CODE if c.lower().split("-")[0] == prefix]
    if len(matches) == 1:
        return matches[0]
    return DEFAULT_LOCALE


def preview_enabled() -> bool:
    return os.environ.get(PREVIEW_ENV_VAR, "").strip() == "1"


def selectable_locales(*, preview: bool | None = None) -> tuple[str, ...]:
    """The locale codes the Language menu should offer."""
    if preview is None:
        preview = preview_enabled()
    return PRODUCTION_LOCALES + DRAFT_LOCALES if preview else PRODUCTION_LOCALES


def _settings() -> QSettings:
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def saved_locale(settings: QSettings | None = None) -> str:
    store = settings or _settings()
    return normalize_locale(store.value(_SETTINGS_KEY, DEFAULT_LOCALE))


def save_locale(code: str, settings: QSettings | None = None) -> str:
    normalized = normalize_locale(code)
    (settings or _settings()).setValue(_SETTINGS_KEY, normalized)
    return normalized


def language_restart_message(native_name: str) -> str:
    """What to tell the user after they pick a language.

    Qt can retranslate a live window, but only if every widget re-reads its
    strings; NVC's widgets set their text once at construction, so a restart
    is the honest answer rather than a half-translated window.
    """
    return QCoreApplication.translate(
        "Localization",
        "NVC will show %(language)s the next time it starts.",
    ) % {"language": native_name}


def qm_path(code: str) -> str:
    """Where the compiled catalogue for a locale lives."""
    spec = locale_spec(code)
    return resource_path(os.path.join(TRANSLATIONS_DIRNAME, f"{spec.qm_basename}.qm"))


class LanguageManager:
    """Installs the active translator and remembers the choice."""

    def __init__(self, app):
        self._app = app
        self._translator: QTranslator | None = None
        self._qt_translator: QTranslator | None = None
        self._current = DEFAULT_LOCALE

    @property
    def current(self) -> str:
        return self._current

    @property
    def current_spec(self) -> LocaleSpec:
        return locale_spec(self._current)

    def apply(self, code: str) -> bool:
        """Install the catalogue for `code`. Returns True if one was loaded.

        English needs no catalogue -- the sources *are* English -- so applying
        it just removes any installed translator and reports False.
        """
        normalized = normalize_locale(code)
        self._current = normalized

        if self._translator is not None:
            self._app.removeTranslator(self._translator)
            self._translator = None

        if normalized == DEFAULT_LOCALE:
            return False

        path = qm_path(normalized)
        if not os.path.exists(path):
            logger.warning(
                "No compiled catalogue for %s at %s; falling back to English. "
                "Build it with: python scripts/build_translations.py",
                normalized, path)
            self._current = DEFAULT_LOCALE
            return False

        translator = QTranslator(self._app)
        if not translator.load(path):
            logger.warning("Could not load %s; falling back to English.", path)
            self._current = DEFAULT_LOCALE
            return False

        self._app.installTranslator(translator)
        self._translator = translator
        self._install_qt_builtin(normalized)
        logger.info("Loaded the %s translation.", normalized)
        return True

    def _install_qt_builtin(self, code: str) -> None:
        """Also translate Qt's own strings (file dialogs, standard buttons).

        Best effort: these ship with Qt and may not be present in a frozen
        build, in which case Qt falls back to English for its own widgets.
        """
        try:
            from PyQt5.QtCore import QLibraryInfo
            translator = QTranslator(self._app)
            qt_locale = QLocale(code.replace("-", "_"))
            base = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
            if translator.load(qt_locale, "qtbase", "_", base):
                self._app.installTranslator(translator)
                self._qt_translator = translator
        except Exception:
            logger.debug("Qt's own catalogue is unavailable", exc_info=True)


def initialize_localization(app) -> LanguageManager:
    """Create the manager and apply the saved language. Call once at startup."""
    manager = LanguageManager(app)
    manager.apply(saved_locale())
    return manager
