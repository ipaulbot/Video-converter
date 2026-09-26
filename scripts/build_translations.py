#!/usr/bin/env python3
"""Extract translatable strings and compile the Qt catalogues.

    python scripts/build_translations.py            # extract, merge, compile
    python scripts/build_translations.py --check     # report drift, change nothing
    python scripts/build_translations.py --locale nl

Extraction walks the AST rather than using pylupdate5. pylupdate5 matches call
names textually, so it cannot see a string passed through a wrapper like
`_tr("...")` -- it only finds `QCoreApplication.translate(...)` and
`self.tr(...)` directly. Walking the AST finds all three, and lets the
literal-only rule be checked rather than merely documented.

Existing translations are preserved: a .ts file is merged, never overwritten.
Sources that disappear from the code are marked `vanished` rather than
deleted, so a rewording does not throw away a translator's work.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.localization import ALL_LOCALES, DEFAULT_LOCALE, locale_spec  # noqa: E402

TRANSLATIONS_DIR = ROOT / "translations"

# Where to look for translatable strings.
SOURCE_DIRS = ("ui", "utils", "conversion", "pc_report")
SOURCE_FILES = ("main.py",)
EXCLUDE_NAMES = ("test_",)

# The call forms that mark a translatable string.
WRAPPER_NAMES = ("_tr",)
QT_TRANSLATE = "translate"
QT_TR = "tr"

# `translate` is also QPainter.translate(dx, dy) and QTransform.translate, so
# the name alone is not enough -- the call has to be on QCoreApplication.
TRANSLATE_OWNERS = ("QCoreApplication", "QtCore")


class ExtractionError(Exception):
    """A translatable call the extractor cannot handle."""


def _iter_sources():
    for name in SOURCE_FILES:
        path = ROOT / name
        if path.exists():
            yield path
    for directory in SOURCE_DIRS:
        for path in sorted((ROOT / directory).rglob("*.py")):
            if any(part.startswith(EXCLUDE_NAMES) for part in path.parts):
                continue
            if path.name.startswith(EXCLUDE_NAMES):
                continue
            yield path


def _is_qt_translate(func) -> bool:
    """True for QCoreApplication.translate, false for painter.translate."""
    if not isinstance(func, ast.Attribute) or func.attr != QT_TRANSLATE:
        return False
    owner = func.value
    if isinstance(owner, ast.Name):
        return owner.id in TRANSLATE_OWNERS
    if isinstance(owner, ast.Attribute):
        return owner.attr in TRANSLATE_OWNERS
    return False


def _module_context(tree: ast.Module, path: Path) -> str | None:
    """Read the context string out of the module's own `_tr` definition."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WRAPPER_NAMES:
            for call in ast.walk(node):
                if (isinstance(call, ast.Call)
                        and getattr(call.func, "attr", None) == QT_TRANSLATE
                        and call.args
                        and isinstance(call.args[0], ast.Constant)):
                    return call.args[0].value
            raise ExtractionError(
                f"{path.name}: {node.name}() does not call "
                f"QCoreApplication.translate with a literal context")
    return None


def extract(paths=None) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    """Return ({context: {source: [locations]}}, [problems])."""
    catalogue: dict[str, dict[str, list[str]]] = {}
    problems: list[str] = []

    for path in paths or _iter_sources():
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            problems.append(f"{path}: {exc}")
            continue

        try:
            module_context = _module_context(tree, path)
        except ExtractionError as exc:
            problems.append(str(exc))
            module_context = None

        rel = path.relative_to(ROOT).as_posix()

        # The wrapper's own body calls translate() with a variable, which is
        # correct there and must not be reported as a violation.
        wrapper_lines = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in WRAPPER_NAMES:
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        wrapper_lines.add(inner.lineno)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.lineno in wrapper_lines:
                continue
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)

            if name in WRAPPER_NAMES:
                # Skip the definition's own body, handled above.
                if not node.args:
                    continue
                context, arg = module_context, node.args[0]
                if context is None:
                    problems.append(
                        f"{rel}:{node.lineno}: _tr() used but the module does "
                        f"not define it")
                    continue
            elif name == QT_TRANSLATE and _is_qt_translate(func):
                if len(node.args) < 2:
                    problems.append(
                        f"{rel}:{node.lineno}: translate() needs a context and "
                        f"a source string")
                    continue
                if not isinstance(node.args[0], ast.Constant):
                    problems.append(
                        f"{rel}:{node.lineno}: translate() needs a literal context")
                    continue
                context, arg = node.args[0].value, node.args[1]
            elif name == QT_TR and isinstance(func, ast.Attribute) and node.args:
                # self.tr(...) -- context is the enclosing class, which the AST
                # does not give us cheaply; NVC uses _tr() instead.
                problems.append(
                    f"{rel}:{node.lineno}: use _tr() rather than self.tr(), so "
                    f"the context does not depend on the class name")
                continue
            else:
                continue

            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                kind = type(arg).__name__
                problems.append(
                    f"{rel}:{node.lineno}: the argument must be a plain string "
                    f"literal, got {kind} (use %(name)s placeholders and "
                    f"substitute after the call)")
                continue

            catalogue.setdefault(context, {}).setdefault(arg.value, []).append(
                f"{rel}:{node.lineno}")

    return catalogue, problems


# ---------------------------------------------------------------------------
# .ts reading and writing
# ---------------------------------------------------------------------------
def read_ts(path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """Existing translations as {(context, source): (translation, type)}."""
    if not path.exists():
        return {}
    out: dict[tuple[str, str], tuple[str, str]] = {}
    root = ET.parse(path).getroot()
    for context in root.findall("context"):
        name_el = context.find("name")
        name = name_el.text if name_el is not None else ""
        for message in context.findall("message"):
            source_el = message.find("source")
            translation_el = message.find("translation")
            if source_el is None or source_el.text is None:
                continue
            text = translation_el.text if translation_el is not None else ""
            kind = (translation_el.get("type") or "") if translation_el is not None else ""
            out[(name, source_el.text)] = (text or "", kind)
    return out


def write_ts(path: Path, catalogue, existing, language: str) -> dict[str, int]:
    """Merge the catalogue into a .ts file, preserving existing translations."""
    ts = ET.Element("TS", {"version": "2.1", "language": language})
    stats = {"total": 0, "translated": 0, "new": 0, "vanished": 0}
    seen: set[tuple[str, str]] = set()

    for context_name in sorted(catalogue):
        context_el = ET.SubElement(ts, "context")
        ET.SubElement(context_el, "name").text = context_name
        for source in sorted(catalogue[context_name]):
            seen.add((context_name, source))
            stats["total"] += 1
            message = ET.SubElement(context_el, "message")
            # Qt's TS DTD orders a message location* -> source -> translation;
            # Linguist will not open a file with them the other way round.
            for location in catalogue[context_name][source]:
                file_part, _, line = location.rpartition(":")
                ET.SubElement(message, "location",
                              {"filename": file_part, "line": line})
            ET.SubElement(message, "source").text = source
            previous, _kind = existing.get((context_name, source), ("", ""))
            translation = ET.SubElement(message, "translation")
            if previous:
                translation.text = previous
                stats["translated"] += 1
            else:
                translation.set("type", "unfinished")
                stats["new"] += 1

    # Keep anything that has a translation but no longer appears in the code,
    # so rewording a string does not discard the translator's work.
    stale = {key: value for key, value in existing.items()
             if key not in seen and value[0]}
    if stale:
        by_context: dict[str, list[tuple[str, str]]] = {}
        for (context_name, source), (text, _kind) in stale.items():
            by_context.setdefault(context_name, []).append((source, text))
        for context_name in sorted(by_context):
            context_el = ET.SubElement(ts, "context")
            ET.SubElement(context_el, "name").text = context_name
            for source, text in sorted(by_context[context_name]):
                message = ET.SubElement(context_el, "message")
                ET.SubElement(message, "source").text = source
                translation = ET.SubElement(message, "translation")
                translation.text = text
                translation.set("type", "vanished")
                stats["vanished"] += 1

    # ET.indent only touches whitespace between elements, so a "\n\n"
    # paragraph break inside a source or translation survives untouched
    # (the old minidom pretty-print dropped every blank line, which silently
    # broke matching for every multi-paragraph dialog text).
    ET.indent(ts, space="    ")
    body = ET.tostring(ts, encoding="unicode")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
                    + body + "\n", encoding="utf-8")
    return stats


def find_lrelease() -> str | None:
    """lrelease compiles .ts to .qm. It ships with qt5-tools, not PyQt5."""
    import shutil
    import site

    found = shutil.which("lrelease")
    if found:
        return found
    candidates = []
    for base in set(site.getsitepackages() + [site.getusersitepackages()]):
        candidates.append(Path(base) / "qt5_applications" / "Qt" / "bin" / "lrelease.exe")
        candidates.append(Path(base) / "qt5_applications" / "Qt" / "bin" / "lrelease")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def compile_qm(ts_path: Path, qm_path: Path) -> bool:
    lrelease = find_lrelease()
    if lrelease is None:
        print("  ! lrelease not found; install it with: pip install qt5-tools")
        return False
    result = subprocess.run([lrelease, str(ts_path), "-qm", str(qm_path)],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  ! lrelease failed: {result.stderr.strip()}")
        return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--locale", action="append", dest="locales",
                        choices=[loc.code for loc in ALL_LOCALES],
                        help="only this locale (repeatable)")
    parser.add_argument("--check", action="store_true",
                        help="report problems and drift; write nothing")
    args = parser.parse_args(argv)

    catalogue, problems = extract()
    total = sum(len(v) for v in catalogue.values())
    print(f"Extracted {total} string(s) in {len(catalogue)} context(s).")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  {problem}")

    if args.check:
        return 1 if problems else 0

    codes = args.locales or [loc.code for loc in ALL_LOCALES]
    for code in codes:
        spec = locale_spec(code)
        ts_path = TRANSLATIONS_DIR / f"{spec.qm_basename}.ts"
        qm_path = TRANSLATIONS_DIR / f"{spec.qm_basename}.qm"

        existing = read_ts(ts_path)
        language = code.replace("-", "_")
        stats = write_ts(ts_path, catalogue, existing, language)
        print(f"\n{code}: {ts_path.name}")
        print(f"  {stats['translated']} translated, {stats['new']} untranslated, "
              f"{stats['vanished']} vanished")

        # English needs no catalogue: the sources are the English strings.
        if code == DEFAULT_LOCALE:
            print("  (no .qm needed -- the source strings are English)")
            continue
        if stats["translated"] == 0:
            print("  (nothing translated yet, so no .qm written)")
            continue
        if compile_qm(ts_path, qm_path):
            print(f"  compiled {qm_path.name}")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
