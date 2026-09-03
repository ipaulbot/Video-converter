"""Tests for utils/update_checker.py.

Update checking was two contradicting mocks. This module emitted `no_update`
from a hardcoded response, so the app silently claimed to be up to date;
ui/main_window.check_for_updates hardcoded "2.3.0" and compared it with a
*string* comparison, so the menu always announced a fake update and offered
to open https://example.com/nvc/downloads.

Nothing here touches the network: `is_configured()` is False for the
placeholder URL, so the check short-circuits, and the configured path is
tested with a stubbed requests module.
"""
import sys
import types
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication

from utils import update_checker
from utils.version import APP_VERSION

app = QApplication.instance() or QApplication([])


class _Recorder:
    """Collects which signal a checker emitted."""

    def __init__(self, checker):
        self.available = []
        self.errors = []
        self.no_update = 0
        self.not_configured = 0
        checker.update_available.connect(lambda v, u: self.available.append((v, u)))
        checker.error_occurred.connect(self.errors.append)
        checker.no_update.connect(self._no_update)
        checker.not_configured.connect(self._not_configured)

    def _no_update(self):
        self.no_update += 1

    def _not_configured(self):
        self.not_configured += 1


class ConfigurationTests(unittest.TestCase):
    def test_the_shipped_url_is_still_a_placeholder(self):
        """If this fails, someone configured a real endpoint -- update the docs."""
        self.assertFalse(update_checker.is_configured(),
                         "UPDATE_URL now looks real; remove the not-configured "
                         "guard and its tests")

    def test_placeholder_hosts_are_recognised(self):
        for url in ("https://raw.githubusercontent.com/yourusername/NVC/main/version.json",
                    "https://example.com/nvc/version.json",
                    "https://example.org/v.json",
                    "", None):
            self.assertFalse(update_checker.is_configured(url), repr(url))

    def test_a_real_url_counts_as_configured(self):
        self.assertTrue(
            update_checker.is_configured("https://noldus.com/nvc/version.json"))


class VersionComparisonTests(unittest.TestCase):
    def test_a_higher_version_is_newer(self):
        self.assertTrue(update_checker.is_newer("2.3.0", "2.2.0"))

    def test_the_same_version_is_not_newer(self):
        self.assertFalse(update_checker.is_newer("2.2.0", "2.2.0"))

    def test_a_lower_version_is_not_newer(self):
        self.assertFalse(update_checker.is_newer("2.1.0", "2.2.0"))

    def test_components_compare_numerically_not_as_text(self):
        """The bug the old string comparison had: "2.9" > "2.10" is True."""
        self.assertTrue(update_checker.is_newer("2.10.0", "2.9.0"))
        self.assertFalse(update_checker.is_newer("2.9.0", "2.10.0"))

    def test_missing_components_count_as_zero(self):
        self.assertFalse(update_checker.is_newer("2.2", "2.2.0"))
        self.assertFalse(update_checker.is_newer("2.2.0", "2.2"))
        self.assertTrue(update_checker.is_newer("2.2.1", "2.2"))

    def test_a_single_component_works(self):
        self.assertTrue(update_checker.is_newer("3", "2.9.9"))

    def test_garbage_is_not_newer_rather_than_raising(self):
        # Comes from a remote document, so it can be anything.
        for value in ("", None, "v2.3", "2.3.0-beta", "not a version", [2, 3]):
            self.assertFalse(update_checker.is_newer(value, "2.2.0"), repr(value))

    def test_a_bare_number_is_read_as_a_version(self):
        """Not garbage: 42 parses as version 42, which really is higher.

        Worth pinning because it comes from a remote document -- the point is
        that the behaviour is decided rather than accidental.
        """
        self.assertTrue(update_checker.is_newer(42, "2.2.0"))
        self.assertFalse(update_checker.is_newer(1, "2.2.0"))

    def test_it_defaults_to_comparing_against_the_app_version(self):
        self.assertFalse(update_checker.is_newer(APP_VERSION))


class UnconfiguredCheckTests(unittest.TestCase):
    def test_it_reports_not_configured_rather_than_no_update(self):
        """Claiming "up to date" without checking states a guess as a fact."""
        checker = update_checker.UpdateChecker()
        seen = _Recorder(checker)
        checker.check_for_updates()

        self.assertEqual(seen.not_configured, 1)
        self.assertEqual(seen.no_update, 0, "nothing was checked")
        self.assertEqual(seen.available, [])
        self.assertEqual(seen.errors, [])

    def test_it_does_not_touch_the_network(self):
        checker = update_checker.UpdateChecker()
        _Recorder(checker)
        with patch.dict(sys.modules, {"requests": None}):
            checker.check_for_updates()   # would raise if requests were used


class ConfiguredCheckTests(unittest.TestCase):
    """The real path, with requests stubbed."""

    def _run(self, payload=None, status_error=None, json_error=None):
        class _Response:
            def raise_for_status(self):
                if status_error:
                    raise status_error

            def json(self):
                if json_error:
                    raise json_error
                return payload

        stub = types.SimpleNamespace(get=lambda url, timeout=None: _Response())
        checker = update_checker.UpdateChecker()
        seen = _Recorder(checker)
        with patch.object(update_checker, "UPDATE_URL",
                          "https://noldus.com/nvc/version.json"), \
             patch.dict(sys.modules, {"requests": stub}):
            checker.check_for_updates()
        return seen

    def test_a_newer_version_is_announced_with_its_url(self):
        seen = self._run({"version": "9.9.9", "url": "https://noldus.com/dl"})
        self.assertEqual(seen.available, [("9.9.9", "https://noldus.com/dl")])
        self.assertEqual(seen.no_update, 0)

    def test_the_current_version_reports_no_update(self):
        seen = self._run({"version": APP_VERSION, "url": "https://noldus.com/dl"})
        self.assertEqual(seen.no_update, 1)
        self.assertEqual(seen.available, [])

    def test_an_older_remote_version_reports_no_update(self):
        seen = self._run({"version": "0.0.1", "url": "https://noldus.com/dl"})
        self.assertEqual(seen.no_update, 1)

    def test_a_document_missing_its_fields_is_an_error_not_an_update(self):
        for payload in ({}, {"version": "9.9.9"}, {"url": "https://x"}):
            seen = self._run(payload)
            self.assertEqual(seen.available, [], repr(payload))
            self.assertEqual(len(seen.errors), 1, repr(payload))

    def test_an_http_error_is_reported(self):
        seen = self._run(status_error=RuntimeError("404 Not Found"))
        self.assertEqual(len(seen.errors), 1)
        self.assertIn("404", seen.errors[0])

    def test_unparseable_json_is_reported(self):
        seen = self._run(json_error=ValueError("Expecting value"))
        self.assertEqual(len(seen.errors), 1)

    def test_a_network_failure_is_reported_rather_than_raising(self):
        def exploding(url, timeout=None):
            raise OSError("network unreachable")

        checker = update_checker.UpdateChecker()
        seen = _Recorder(checker)
        with patch.object(update_checker, "UPDATE_URL",
                          "https://noldus.com/nvc/version.json"), \
             patch.dict(sys.modules,
                        {"requests": types.SimpleNamespace(get=exploding)}):
            checker.check_for_updates()
        self.assertEqual(len(seen.errors), 1)
        self.assertIn("unreachable", seen.errors[0])

    def test_a_timeout_is_passed_to_requests(self):
        captured = {}

        def capture(url, timeout=None):
            captured["timeout"] = timeout

            class _R:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"version": "0.0.1", "url": "https://x"}
            return _R()

        checker = update_checker.UpdateChecker()
        _Recorder(checker)
        with patch.object(update_checker, "UPDATE_URL",
                          "https://noldus.com/nvc/version.json"), \
             patch.dict(sys.modules,
                        {"requests": types.SimpleNamespace(get=capture)}):
            checker.check_for_updates()
        self.assertEqual(captured["timeout"],
                         update_checker.REQUEST_TIMEOUT_SECONDS)


class BackwardsCompatibilityTests(unittest.TestCase):
    def test_the_old_private_helper_still_works(self):
        checker = update_checker.UpdateChecker()
        self.assertTrue(checker._is_newer("2.3.0", "2.2.0"))
        self.assertFalse(checker._is_newer("2.1.0", "2.2.0"))


if __name__ == "__main__":
    unittest.main()
