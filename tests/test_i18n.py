"""Tests for the translation layer.

Two jobs. The first is the usual: check utils/localization.py behaves. The
second matters more over time -- an AST scan that fails when a new
user-facing string is added without _tr(). Without it, i18n coverage decays
one commit at a time and nobody notices until a translator asks why half the
window is still English.
"""
import ast
import sys
import unittest
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QSettings
from PyQt5.QtWidgets import QApplication

from utils import localization

app = QApplication.instance() or QApplication([])

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Modules that present UI and must therefore wrap their strings.
UI_MODULES = (
    "ui/main_window.py",
    "ui/settings_dialog.py",
    "ui/dialogs.py",
    "ui/inspection_widget.py",
    "ui/converted_files_widget.py",
    "ui/lossless_editor_widget.py",
    "ui/multi_source_recorder_widget.py",
    "ui/media_player_widget.py",
    "ui/pc_report_dialog.py",
    "ui/preview_controller.py",
    "main.py",
)

# Qt calls whose text a user reads.
TEXT_SETTERS = {
    "setText", "setWindowTitle", "setToolTip", "setPlaceholderText", "addTab",
    "addAction", "setStatusTip", "setTabText", "setLabelText", "setTitle",
    "setInformativeText",
}
MESSAGE_BOXES = {"information", "warning", "critical", "question", "about"}

# Widgets whose first constructor argument is the text a user reads. Missed by
# the first sweep, which only looked at setters -- 136 strings lived here.
TEXT_WIDGETS = {
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox",
    "QAction", "QToolButton", "QMenu",
}

# The easter-egg game is exempt: it is hidden, self-contained, and its strings
# are part of the joke rather than the product. Listed rather than silently
# skipped so the exemption is a decision.
EXEMPT = ("ui/extras/",)


def _literals_in(node):
    """Yield (lineno, text) for translatable literals reachable from `node`.

    Descends into ternaries and boolean expressions. Those hide a literal from
    a naive "is the argument a Constant?" check, which is how
    `setText("Stop Recording" if recording else "Stop")` stayed untranslated
    through the whole i18n pass -- the string was never a direct argument.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and node.value.strip():
            yield node.lineno, node.value
        return
    if isinstance(node, (ast.IfExp, ast.BoolOp)):
        for child in ast.iter_child_nodes(node):
            yield from _literals_in(child)


def _literal_setter_args(path: Path):
    """Yield (lineno, text) for every plain literal reaching a text setter."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        is_box = (isinstance(func, ast.Attribute) and func.attr in MESSAGE_BOXES
                  and isinstance(func.value, ast.Name)
                  and func.value.id == "QMessageBox")
        if name not in TEXT_SETTERS and not is_box:
            continue
        for arg in (node.args[1:] if is_box else node.args):
            yield from _literals_in(arg)


def _literal_widget_args(path: Path):
    """Yield (lineno, text) for literal first arguments to text widgets."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in TEXT_WIDGETS:
            continue
        yield from _literals_in(node.args[0])


class StringCoverageTests(unittest.TestCase):
    """No user-facing literal may reach Qt unwrapped."""

    def test_no_bare_literal_reaches_a_text_setter(self):
        offenders = []
        for rel in UI_MODULES:
            path = ROOT / rel
            for lineno, text in _literal_setter_args(path):
                offenders.append(f"{rel}:{lineno}: {text!r}")
        self.assertEqual(
            offenders, [],
            "wrap these in _tr(...) -- see utils/localization.py:\n  "
            + "\n  ".join(offenders))

    def test_no_bare_literal_reaches_a_text_widget_constructor(self):
        offenders = []
        for rel in UI_MODULES:
            for lineno, text in _literal_widget_args(ROOT / rel):
                offenders.append(f"{rel}:{lineno}: {text!r}")
        self.assertEqual(
            offenders, [],
            "wrap these in _tr(...) too: a QLabel's constructor text is as "
            "visible as setText's:\n  " + "\n  ".join(offenders))

    def test_every_ui_module_defines_tr(self):
        for rel in UI_MODULES:
            source = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("def _tr(", source, rel)

    def test_every_tr_uses_a_distinct_literal_context(self):
        """Contexts must be literal, and one module must not borrow another's."""
        import build_translations as bt

        contexts = {}
        for rel in UI_MODULES:
            path = ROOT / rel
            tree = ast.parse(path.read_text(encoding="utf-8"))
            context = bt._module_context(tree, path)
            self.assertIsNotNone(context, f"{rel} has no literal context")
            self.assertNotIn(context, contexts,
                             f"{rel} reuses the context of {contexts.get(context)}")
            contexts[context] = rel

    def test_no_module_uses_self_tr(self):
        """self.tr() ties the context to the class name, which gets renamed."""
        offenders = []
        for rel in UI_MODULES:
            for lineno, line in enumerate(
                    (ROOT / rel).read_text(encoding="utf-8").splitlines(), 1):
                if "self.tr(" in line:
                    offenders.append(f"{rel}:{lineno}")
        self.assertEqual(offenders, [], f"use _tr() instead: {offenders}")


class ExtractorTests(unittest.TestCase):
    def setUp(self):
        import build_translations as bt
        self.bt = bt

    def test_extraction_finds_strings_and_reports_no_problems(self):
        catalogue, problems = self.bt.extract()
        self.assertEqual(problems, [], "\n  ".join(problems))
        self.assertGreater(sum(len(v) for v in catalogue.values()), 100)

    def test_every_ui_context_is_represented(self):
        catalogue, _ = self.bt.extract()
        for context in ("MainWindow", "SettingsDialog", "Recorder", "Preview"):
            self.assertIn(context, catalogue)

    def test_painter_translate_is_not_mistaken_for_a_string(self):
        """`translate` is also QPainter.translate(dx, dy)."""
        src = ("from PyQt5.QtGui import QPainter\n"
               "def paint(painter):\n"
               "    painter.translate(1, 2)\n")
        path = Path(self.bt.ROOT) / "translations" / "_probe_painter.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(src, encoding="utf-8")
        try:
            catalogue, problems = self.bt.extract([path])
            self.assertEqual(catalogue, {})
            self.assertEqual(problems, [])
        finally:
            path.unlink()

    def test_a_non_literal_argument_is_reported(self):
        src = ('from PyQt5.QtCore import QCoreApplication\n'
               'def _tr(source):\n'
               '    return QCoreApplication.translate("Probe", source)\n'
               'def build(name):\n'
               '    return _tr(f"Hello {name}")\n')
        path = Path(self.bt.ROOT) / "translations" / "_probe_fstring.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(src, encoding="utf-8")
        try:
            _catalogue, problems = self.bt.extract([path])
            self.assertTrue(problems)
            self.assertIn("plain string literal", problems[0])
        finally:
            path.unlink()

    def test_existing_translations_survive_a_rebuild(self):
        """A rebuild must never discard a translator's work."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ts = Path(tmp) / "probe.ts"
            catalogue = {"Probe": {"Hello": ["a.py:1"], "World": ["a.py:2"]}}
            self.bt.write_ts(ts, catalogue, {}, "nl_NL")

            existing = self.bt.read_ts(ts)
            existing[("Probe", "Hello")] = ("Hallo", "")
            stats = self.bt.write_ts(ts, catalogue, existing, "nl_NL")
            self.assertEqual(stats["translated"], 1)

            again = self.bt.read_ts(ts)
            self.assertEqual(again[("Probe", "Hello")][0], "Hallo")

    def test_a_removed_string_is_marked_vanished_not_deleted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ts = Path(tmp) / "probe.ts"
            existing = {("Probe", "Old wording"): ("Oude tekst", "")}
            stats = self.bt.write_ts(
                ts, {"Probe": {"New wording": ["a.py:1"]}}, existing, "nl_NL")
            self.assertEqual(stats["vanished"], 1)
            self.assertIn("Oude tekst", ts.read_text(encoding="utf-8"))

    def test_blank_lines_inside_a_string_survive_the_round_trip(self):
        """Dialog texts use "\\n\\n" paragraphs; the .ts writer used to drop
        the blank line, so those strings could never match at runtime."""
        import tempfile
        source = "Locked.\n\nUnlock first."
        with tempfile.TemporaryDirectory() as tmp:
            ts = Path(tmp) / "probe.ts"
            catalogue = {"Probe": {source: ["a.py:1"]}}
            existing = {("Probe", source): ("Vergrendeld.\n\nOntgrendel eerst.", "")}
            stats = self.bt.write_ts(ts, catalogue, existing, "nl_NL")
            self.assertEqual((stats["translated"], stats["vanished"]), (1, 0))
            again = self.bt.read_ts(ts)
            self.assertEqual(again[("Probe", source)][0], "Vergrendeld.\n\nOntgrendel eerst.")
            stats = self.bt.write_ts(ts, catalogue, again, "nl_NL")
            self.assertEqual((stats["translated"], stats["vanished"]), (1, 0))

    def test_ts_orders_location_before_source(self):
        """Qt's DTD requires it; Linguist refuses a file with them swapped."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ts = Path(tmp) / "probe.ts"
            self.bt.write_ts(ts, {"Probe": {"Hi": ["a.py:3"]}}, {}, "nl_NL")
            text = ts.read_text(encoding="utf-8")
            self.assertLess(text.index("<location"), text.index("<source>"))


class LocaleTests(unittest.TestCase):
    def test_locale_codes_are_unique_and_have_native_names(self):
        codes = [loc.code for loc in localization.ALL_LOCALES]
        self.assertEqual(len(codes), len(set(codes)))
        for loc in localization.ALL_LOCALES:
            self.assertTrue(loc.native_name)
            self.assertTrue(loc.qm_basename)

    def test_english_is_the_default_and_needs_no_catalogue(self):
        self.assertEqual(localization.DEFAULT_LOCALE, "en")
        self.assertIn("en", localization.PRODUCTION_LOCALES)

    def test_every_locale_names_a_document_tag(self):
        """The tag is the bridge to docs/help; it must at least be set.

        It is deliberately NOT asserted that a manual exists for every
        selectable language: the interface is translated ahead of the
        manuals, which are English-only. utils/help_resolution falls back to
        the English manual for a locale that has none, and the test below
        pins that fallback -- which is the invariant that actually matters.
        """
        for loc in localization.ALL_LOCALES:
            self.assertTrue(loc.document_tag, loc.code)

    def test_the_help_menu_falls_back_to_the_english_manual(self):
        """A translated UI with untranslated manuals must still open Help."""
        from utils import help_resolution
        for loc in localization.ALL_LOCALES:
            found = help_resolution.find_generated_manual(language=loc.code)
            if found is None:
                self.skipTest("no manuals built; run build_help_docs.py")
            self.assertTrue(found.exists(), loc.code)

    def test_the_docs_pipeline_knows_which_locales_it_covers(self):
        sys.path.insert(0, str(ROOT / "docs" / "help" / "source"))
        import document_registry
        known = set(document_registry.SUPPORTED_DOCUMENT_TAGS
                    + document_registry.DRAFT_DOCUMENT_TAGS)
        self.assertIn("en", known, "English manuals must always be buildable")

    def test_normalization_accepts_the_spellings_we_may_meet(self):
        cases = {
            "en": "en", "nl": "nl", "zh-CN": "zh-CN", "zh_CN": "zh-CN",
            "ZH-cn": "zh-CN", "zh": "zh-CN", "en_GB": "en", "en-AU": "en",
            "Dutch": "nl",
        }
        for value, expected in cases.items():
            self.assertEqual(localization.normalize_locale(value), expected, value)

    def test_unknown_values_fall_back_to_english(self):
        for value in ("", None, "nonsense", "de", "fr-CA", 42):
            self.assertEqual(localization.normalize_locale(value), "en", repr(value))

    def test_only_production_locales_are_offered_by_default(self):
        self.assertEqual(localization.selectable_locales(preview=False),
                         localization.PRODUCTION_LOCALES)

    def test_preview_mode_also_offers_the_drafts(self):
        offered = localization.selectable_locales(preview=True)
        for code in localization.DRAFT_LOCALES:
            self.assertIn(code, offered)

    def test_drafts_are_not_shipped_as_production(self):
        """Unreviewed machine output must not reach a user by default."""
        for loc in localization.ALL_LOCALES:
            if loc.review_status != "production":
                self.assertNotIn(loc.code, localization.PRODUCTION_LOCALES)

    def test_saving_and_reading_a_locale_round_trips(self):
        settings = QSettings("Noldus", "NVC-i18n-test")
        try:
            localization.save_locale("nl", settings)
            self.assertEqual(localization.saved_locale(settings), "nl")
            localization.save_locale("en", settings)
            self.assertEqual(localization.saved_locale(settings), "en")
        finally:
            settings.clear()

    def test_a_corrupt_saved_locale_does_not_break_startup(self):
        settings = QSettings("Noldus", "NVC-i18n-test")
        try:
            settings.setValue("locale", "klingon")
            self.assertEqual(localization.saved_locale(settings), "en")
        finally:
            settings.clear()

    def test_restart_message_names_the_language(self):
        message = localization.language_restart_message("Nederlands")
        self.assertIn("Nederlands", message)
        self.assertNotIn("%(", message, "the placeholder should be substituted")


class LanguageManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = localization.LanguageManager(app)

    def tearDown(self):
        self.manager.apply("en")

    def test_english_installs_no_translator(self):
        self.assertFalse(self.manager.apply("en"))
        self.assertEqual(self.manager.current, "en")

    def test_a_missing_catalogue_falls_back_to_english(self):
        # zh-CN has no compiled .qm until someone translates it.
        import os
        if os.path.exists(localization.qm_path("zh-CN")):
            self.skipTest("zh-CN has been translated and compiled")
        self.assertFalse(self.manager.apply("zh-CN"))
        self.assertEqual(self.manager.current, "en",
                         "a missing catalogue must not leave a dead locale set")

    def test_applying_a_built_catalogue_reports_success(self):
        import os
        if not os.path.exists(localization.qm_path("nl")):
            self.skipTest("nl has not been compiled; run build_translations.py")
        self.assertTrue(self.manager.apply("nl"))
        self.assertEqual(self.manager.current, "nl")

    def test_switching_back_to_english_removes_the_translator(self):
        import os
        if not os.path.exists(localization.qm_path("nl")):
            self.skipTest("nl has not been compiled")
        # A string that is in the code today (the sidebar's table title).
        self.manager.apply("nl")
        translated = QCoreApplication.translate("MainWindow", "Current Video Settings")
        self.manager.apply("en")
        english = QCoreApplication.translate("MainWindow", "Current Video Settings")
        self.assertEqual(english, "Current Video Settings")
        self.assertNotEqual(translated, english,
                            "the nl catalogue should have changed this string")

    def test_an_untranslated_string_falls_back_to_its_source(self):
        import os
        if not os.path.exists(localization.qm_path("nl")):
            self.skipTest("nl has not been compiled")
        self.manager.apply("nl")
        # Qt returns the source text when a catalogue has no entry.
        self.assertEqual(
            QCoreApplication.translate("MainWindow", "not-a-real-string"),
            "not-a-real-string")


if __name__ == "__main__":
    unittest.main()
