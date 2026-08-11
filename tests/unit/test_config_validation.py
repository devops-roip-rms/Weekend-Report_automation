from __future__ import annotations

import unittest

from app.config.loader import load_config_dir
from app.config.validation import validate_config


class ConfigValidationTests(unittest.TestCase):
    def test_default_config_blocks_unresolved_placeholders(self):
        report = validate_config(load_config_dir("config"))
        self.assertFalse(report.ok)
        self.assertTrue(any("<TBD>" in issue.message for issue in report.errors))

    def test_fixture_config_is_valid(self):
        report = validate_config(load_config_dir("tests/fixtures/config_valid"))
        self.assertTrue(report.ok, report.lines())


if __name__ == "__main__":
    unittest.main()
