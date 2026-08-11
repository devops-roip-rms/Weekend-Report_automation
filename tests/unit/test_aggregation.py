from __future__ import annotations

import unittest

from app.domain import CheckResult, CheckStatus
from app.orchestrator.aggregation import aggregate_status


class AggregationTests(unittest.TestCase):
    def r(self, status: CheckStatus) -> CheckResult:
        return CheckResult("WR-1", "m", "c", status, status.value)

    def test_error_and_fail_are_blocking(self):
        self.assertEqual(aggregate_status([self.r(CheckStatus.PASS), self.r(CheckStatus.ERROR)]), CheckStatus.ERROR)
        self.assertEqual(aggregate_status([self.r(CheckStatus.PASS), self.r(CheckStatus.FAIL)]), CheckStatus.FAIL)

    def test_skipped_and_manual_review_never_become_pass(self):
        self.assertEqual(aggregate_status([self.r(CheckStatus.SKIPPED)]), CheckStatus.SKIPPED)
        self.assertEqual(aggregate_status([self.r(CheckStatus.MANUAL_REVIEW)]), CheckStatus.MANUAL_REVIEW)


if __name__ == "__main__":
    unittest.main()
