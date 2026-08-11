from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config.loader import load_config_dir
from app.database.repository import Repository
from app.domain import NoteScope, ReviewDecision, ReviewNote, RunState
from app.evidence.manager import EvidenceManager
from app.orchestrator.lock import DuplicateActiveRun
from app.orchestrator.runner import OrchestratorRunner
from app.orchestrator.run_context import RunContext
from app.reporting.html import render_final_html
from app.reporting.snapshot import finalize_run


class RunWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = Repository("sqlite:///:memory:")
        self.addCleanup(self.repo.close)
        self.evidence = EvidenceManager(self.root / "evidence")
        self.config = load_config_dir("tests/fixtures/config_valid")

    def test_duplicate_run_rejected_and_worker_claim_single(self):
        self.repo.create_run(started_by="alice", run_id="WR-20260811-000000")
        with self.assertRaises(DuplicateActiveRun):
            self.repo.create_run(started_by="alice", run_id="WR-20260811-000001")
        claimed = self.repo.claim_next_run("worker-a")
        self.assertIsNotNone(claimed)
        self.assertIsNone(self.repo.claim_next_run("worker-b"))

    def test_fake_run_to_review_ready_and_notes_finalize_pdf(self):
        run = self.repo.create_run(started_by="alice", run_id="WR-20260811-000000", config_version=self.config["_config_hash"])
        claimed = self.repo.claim_next_run("worker-a")
        self.assertEqual(claimed.run_id, run.run_id)
        OrchestratorRunner().run(RunContext(run.run_id, self.config, self.repo, self.evidence))
        self.assertEqual(self.repo.get_run(run.run_id).state, RunState.REVIEW_READY)
        result = self.repo.list_results(run.run_id)[0]
        self.repo.save_note(ReviewNote(run.run_id, NoteScope.MODULE, "reviewer", "module note", module=result.module))
        self.repo.save_note(ReviewNote(run.run_id, NoteScope.RESULT, "reviewer", "result note", result_id=result.id))
        for dashboard in self.config["splunk_dashboards"]["dashboards"]:
            self.repo.save_note(ReviewNote(run.run_id, NoteScope.SPLUNK_DASHBOARD, "reviewer", f"note for {dashboard['id']}", dashboard_id=dashboard["id"]))
        snapshot = finalize_run(self.repo, self.evidence, self.config, run.run_id, "reviewer", ReviewDecision.APPROVE)
        self.assertEqual(self.repo.get_run(run.run_id).state, RunState.APPROVED)
        note_text = [n["note"] for n in snapshot["notes"]]
        self.assertIn("module note", note_text)
        self.assertIn("result note", note_text)
        for dashboard in self.config["splunk_dashboards"]["dashboards"]:
            self.assertIn(f"note for {dashboard['id']}", note_text)
        html = render_final_html(snapshot)
        self.assertIn("module note", html)
        self.assertTrue((self.evidence.root / self.repo.get_run(run.run_id).final_pdf_path).exists())

    def test_reject_generates_pdf(self):
        run = self.repo.create_run(started_by="alice", run_id="WR-20260811-000000", config_version=self.config["_config_hash"])
        self.repo.claim_next_run("worker-a")
        OrchestratorRunner().run(RunContext(run.run_id, self.config, self.repo, self.evidence))
        finalize_run(self.repo, self.evidence, self.config, run.run_id, "reviewer", ReviewDecision.REJECT)
        self.assertEqual(self.repo.get_run(run.run_id).state, RunState.REJECTED)

    def test_pdf_failure_preserves_snapshot(self):
        run = self.repo.create_run(started_by="alice", run_id="WR-20260811-000000", config_version=self.config["_config_hash"])
        self.repo.claim_next_run("worker-a")
        OrchestratorRunner().run(RunContext(run.run_id, self.config, self.repo, self.evidence))
        with self.assertRaises(RuntimeError):
            finalize_run(self.repo, self.evidence, self.config, run.run_id, "reviewer", ReviewDecision.APPROVE, fail_pdf=True)
        self.assertTrue(self.repo.get_run(run.run_id).final_snapshot_path)
        self.assertEqual(self.repo.get_run(run.run_id).state, RunState.REVIEW_READY)


if __name__ == "__main__":
    unittest.main()
