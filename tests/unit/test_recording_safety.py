from __future__ import annotations

import unittest

from app.collectors.recording import RecordingTestOrchestrator
from app.domain import CheckStatus


class RecordingSafetyTests(unittest.TestCase):
    def test_cleanup_is_attempted_and_failure_blocks_module(self):
        orchestrator = RecordingTestOrchestrator()
        orchestrator.run(create_ok=True, propagation_ok=True, backend_ok=True, cleanup_ok=False)
        self.assertTrue(orchestrator.last_outcome.cleanup_attempted)
        self.assertEqual(orchestrator.last_outcome.cleanup_status, CheckStatus.FAIL)
        self.assertEqual(orchestrator.last_outcome.functional_status, CheckStatus.FAIL)

    def test_creation_failure_does_not_claim_cleanup(self):
        orchestrator = RecordingTestOrchestrator()
        outcome = orchestrator.run(create_ok=False, propagation_ok=False, backend_ok=False, cleanup_ok=True)
        self.assertFalse(outcome.cleanup_attempted)


if __name__ == "__main__":
    unittest.main()
