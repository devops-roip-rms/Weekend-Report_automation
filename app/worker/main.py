from __future__ import annotations

import os
import socket
import time

from app.config.loader import load_config_dir
from app.config.validation import validate_config
from app.database.repository import Repository
from app.evidence.manager import EvidenceManager
from app.orchestrator.runner import OrchestratorRunner
from app.orchestrator.run_context import RunContext


def main() -> None:
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    repo = Repository(os.getenv("WEEKEND_REPORT_DATABASE_URL", "sqlite:///data/weekend-report.sqlite"))
    config = load_config_dir(os.getenv("WEEKEND_REPORT_CONFIG_DIR", "config"))
    evidence = EvidenceManager(os.getenv("WEEKEND_REPORT_EVIDENCE_ROOT", "runs"))
    while True:
        run = repo.claim_next_run(worker_id)
        if run:
            preflight = validate_config(config)
            if not preflight.ok:
                repo.mark_failed(run.run_id, "; ".join(preflight.lines()))
                continue
            try:
                OrchestratorRunner().run(RunContext(run.run_id, config, repo, evidence))
            except Exception as exc:
                repo.mark_failed(run.run_id, str(exc))
        time.sleep(float(os.getenv("WEEKEND_REPORT_WORKER_POLL_SECONDS", "2")))


if __name__ == "__main__":
    main()
