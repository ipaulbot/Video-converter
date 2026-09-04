"""Repo-wide guards for Qt objects that must not outlive their owner.

The failure mode these prevent is the reason this file exists rather than a
comment: PyQt reacts to an exception escaping a Qt slot by calling qFatal(),
which aborts the process with STATUS_STACK_BUFFER_OVERRUN (0xC0000409) and no
traceback on stderr. A callback that fires against a destroyed widget is
therefore not a caught error and not a visible crash report -- it is NVC
vanishing, or the test suite dying at some unrelated test seconds later.

Both guards are source scans. Behaviour tests cannot catch these: the offending
call is correct at the moment it runs and only becomes fatal once the widget is
gone, which is timing the test would have to arrange for every call site.
"""
import ast
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = ("ui", "utils", "conversion", "pc_report")


def _source_files():
    for package in _PACKAGES:
        yield from sorted((_ROOT / package).rglob("*.py"))


def _location(path, node):
    return f"{path.relative_to(_ROOT).as_posix()}:{node.lineno}"


class SingleShotOwnershipTests(unittest.TestCase):
    """`QTimer.singleShot` is a static method, so its timer belongs to nobody.

    It keeps running after the widget that scheduled it is destroyed. Every
    callback in this codebase touches the widget, so use the widget's own
    `_schedule()` helper instead -- it parents the timer to the widget, and Qt
    cancels it on destruction.

    This bit twice for real. The recorder escalates a stopped recording to
    terminate at 1.5s and kill at 3s, so closing NVC just after pressing Stop
    aborted it; and the easter-egg game schedules its level transitions up to
    10s out.
    """

    def test_nothing_schedules_through_the_static_single_shot(self):
        offenders = []
        for path in _source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (isinstance(func, ast.Attribute)
                        and func.attr == "singleShot"
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "QTimer"):
                    offenders.append(_location(path, node))
        self.assertEqual(offenders, [],
                         "use self._schedule(msec, callback) instead of "
                         "QTimer.singleShot, so the timer dies with the widget")

    def test_the_schedule_helper_exists_where_it_is_used(self):
        """A `_schedule` call needs a `_schedule` definition in the same class.

        Copying a call into a class that has no helper would restore the bug
        while satisfying the scan above.
        """
        missing = []
        for path in _source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for klass in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                calls = [n for n in ast.walk(klass)
                         if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Attribute)
                         and n.func.attr == "_schedule"
                         and isinstance(n.func.value, ast.Name)
                         and n.func.value.id == "self"]
                if not calls:
                    continue
                defined = any(isinstance(n, ast.FunctionDef) and n.name == "_schedule"
                              for n in klass.body)
                if not defined:
                    missing.append(f"{_location(path, klass)} ({klass.name})")
        self.assertEqual(missing, [],
                         "these classes call self._schedule without defining it")


if __name__ == "__main__":
    unittest.main()
