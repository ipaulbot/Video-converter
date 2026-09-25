import tomllib
import unittest
from pathlib import Path

from utils.version import APP_VERSION


class VersionTests(unittest.TestCase):
    def test_pyproject_matches_app_version(self):
        data = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text("utf-8")
        )
        self.assertEqual(data["project"]["version"], APP_VERSION)
