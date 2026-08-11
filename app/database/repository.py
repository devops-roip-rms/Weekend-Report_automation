from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.database.models import POSTGRES_SCHEMA, SQLITE_SCHEMA
from app.domain import CheckResult, CheckStatus, EvidenceRecord, ReviewNote, RunRecord, RunState, to_jsonable
from app.orchestrator.lock import ACTIVE_STATES, DuplicateActiveRun, InvalidRunTransition
from app.time_utils import iso_now, utcnow

class Repository:
    def __init__(self, database_url: str = "sqlite:///:memory:") -> None:
        self.backend = "sqlite" if database_url.startswith("sqlite:///") else "postgres"
        if self.backend == "sqlite":
            path = database_url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self.conn.row_factory = sqlite3.Row
        else:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ModuleNotFoundError as exc:
                raise RuntimeError("PostgreSQL database URLs require psycopg; install requirements.txt") from exc
            self.conn = psycopg.connect(database_url, autocommit=True, row_factory=dict_row)
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        schema = SQLITE_SCHEMA if self.backend == "sqlite" else POSTGRES_SCHEMA
        for statement in schema:
            self._execute(statement)
        if self.backend == "sqlite":
            self._execute("INSERT OR IGNORE INTO run_lock(name, active_run_id, updated_at) VALUES('weekend_report', NULL, ?)", (iso_now(),))
        else:
            self._execute("INSERT INTO run_lock(name, active_run_id, updated_at) VALUES('weekend_report', NULL, ?) ON CONFLICT (name) DO NOTHING", (iso_now(),))

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.backend == "postgres" else sql

    def _execute(self, sql: str, params: tuple[Any, ...] = ()):
        return self.conn.execute(self._sql(sql), params)

    def _insert_id(self, sql: str, params: tuple[Any, ...]) -> int:
        if self.backend == "postgres":
            row = self._execute(sql + " RETURNING id", params).fetchone()
            return int(row["id"])
        cur = self._execute(sql, params)
        return int(cur.lastrowid)

    def transaction(self):
        return _Transaction(self.conn, self.backend)

    def create_run(
        self,
        *,
        started_by: str,
        run_id: str | None = None,
        application_version: str = "0.1.0",
        git_commit: str = "UNKNOWN",
        config_version: str = "UNKNOWN",
    ) -> RunRecord:
        run_id = run_id or utcnow().strftime("WR-%Y%m%d-%H%M%S")
        with self.transaction():
            active = self._execute(
                "SELECT active_run_id FROM run_lock WHERE name='weekend_report'"
            ).fetchone()["active_run_id"]
            if active:
                active_state = self._execute("SELECT state FROM runs WHERE run_id=?", (active,)).fetchone()
                if active_state and active_state["state"] in ACTIVE_STATES:
                    raise DuplicateActiveRun(f"active run already exists: {active}")
            now = iso_now()
            self._execute(
                """
                INSERT INTO runs(run_id,state,automation_status,started_by,created_at,application_version,git_commit,config_version,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    RunState.CREATED.value,
                    None,
                    started_by,
                    now,
                    application_version,
                    git_commit,
                    config_version,
                    now,
                ),
            )
            self._execute(
                "UPDATE run_lock SET active_run_id=?, updated_at=? WHERE name='weekend_report'",
                (run_id, now),
            )
        return self.get_run(run_id)

    def claim_next_run(self, worker_id: str) -> RunRecord | None:
        with self.transaction():
            row = self._execute(
                "SELECT run_id FROM runs WHERE state=? ORDER BY created_at LIMIT 1",
                (RunState.CREATED.value,),
            ).fetchone()
            if not row:
                return None
            run_id = row["run_id"]
            now = iso_now()
            updated = self._execute(
                "UPDATE runs SET state=?, worker_id=?, started_at=?, last_heartbeat=?, updated_at=? WHERE run_id=? AND state=?",
                (RunState.RUNNING.value, worker_id, now, now, now, run_id, RunState.CREATED.value),
            ).rowcount
            if updated != 1:
                return None
        return self.get_run(run_id)

    def heartbeat(
        self, run_id: str, current_module: str | None = None, worker_id: str | None = None
    ) -> None:
        now = iso_now()
        self._execute(
            "UPDATE runs SET last_heartbeat=?, current_module=COALESCE(?, current_module), worker_id=COALESCE(?, worker_id), updated_at=? WHERE run_id=?",
            (now, current_module, worker_id, now, run_id),
        )

    def mark_review_ready(self, run_id: str, status: CheckStatus) -> None:
        now = iso_now()
        with self.transaction():
            self._execute(
                "UPDATE runs SET state=?, automation_status=?, finished_at=?, current_module=NULL, updated_at=? WHERE run_id=?",
                (RunState.REVIEW_READY.value, status.value, now, now, run_id),
            )
            self._execute(
                "UPDATE run_lock SET active_run_id=NULL, updated_at=? WHERE active_run_id=?",
                (now, run_id),
            )

    def mark_failed(self, run_id: str, message: str) -> None:
        now = iso_now()
        with self.transaction():
            self._execute(
                "UPDATE runs SET state=?, automation_status=?, finished_at=?, current_module=?, updated_at=? WHERE run_id=?",
                (RunState.FAILED.value, CheckStatus.ERROR.value, now, message, now, run_id),
            )
            self._execute(
                "UPDATE run_lock SET active_run_id=NULL, updated_at=? WHERE active_run_id=?",
                (now, run_id),
            )

    def add_result(self, result: CheckResult) -> int:
        return self._insert_id(
            """
            INSERT INTO results(run_id,module,site,check_id,target,status,expected_json,actual_json,message,started_at,finished_at,metadata_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                result.run_id,
                result.module,
                result.site,
                result.check_id,
                result.target,
                result.status.value,
                json.dumps(to_jsonable(result.expected), sort_keys=True),
                json.dumps(to_jsonable(result.actual), sort_keys=True),
                result.message,
                result.started_at,
                result.finished_at,
                json.dumps(to_jsonable(result.metadata), sort_keys=True),
            ),
        )

    def add_evidence(self, evidence: EvidenceRecord) -> int:
        return self._insert_id(
            "INSERT INTO evidence(run_id,result_id,module,site,evidence_type,path,checksum,mime_type,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                evidence.run_id,
                evidence.result_id,
                evidence.module,
                evidence.site,
                evidence.evidence_type,
                evidence.path,
                evidence.checksum,
                evidence.mime_type,
                evidence.created_at or iso_now(),
            ),
        )

    def save_note(self, note: ReviewNote) -> int:
        now = iso_now()
        existing = self._execute(
            "SELECT id, created_at FROM review_notes WHERE run_id=? AND scope=? AND COALESCE(module,'')=COALESCE(?, '') AND COALESCE(result_id,-1)=COALESCE(?, -1) AND COALESCE(dashboard_id,'')=COALESCE(?, '')",
            (note.run_id, note.scope.value, note.module, note.result_id, note.dashboard_id),
        ).fetchone()
        if existing:
            self._execute(
                "UPDATE review_notes SET author=?, note=?, updated_at=? WHERE id=?",
                (note.author, note.note, now, existing["id"]),
            )
            return int(existing["id"])
        return self._insert_id(
            "INSERT INTO review_notes(run_id,scope,module,result_id,dashboard_id,author,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                note.run_id,
                note.scope.value,
                note.module,
                note.result_id,
                note.dashboard_id,
                note.author,
                note.note,
                now,
                now,
            ),
        )

    def get_run(self, run_id: str) -> RunRecord:
        row = self._execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        return _run_from_row(row)

    def list_runs(self) -> list[RunRecord]:
        return [
            _run_from_row(row)
            for row in self._execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        ]

    def list_results(self, run_id: str, module: str | None = None) -> list[CheckResult]:
        if module:
            rows = self._execute(
                "SELECT * FROM results WHERE run_id=? AND module=? ORDER BY id",
                (run_id, module),
            ).fetchall()
        else:
            rows = self._execute(
                "SELECT * FROM results WHERE run_id=? ORDER BY id", (run_id,)
            ).fetchall()
        return [_result_from_row(row) for row in rows]

    def list_evidence(self, run_id: str) -> list[EvidenceRecord]:
        return [
            _evidence_from_row(row)
            for row in self._execute("SELECT * FROM evidence WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        ]

    def list_notes(self, run_id: str) -> list[ReviewNote]:
        return [
            _note_from_row(row)
            for row in self._execute("SELECT * FROM review_notes WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        ]

    def set_snapshot_path(self, run_id: str, path: str) -> None:
        self._execute(
            "UPDATE runs SET final_snapshot_path=?, updated_at=? WHERE run_id=?",
            (path, iso_now(), run_id),
        )

    def set_final_pdf(
        self,
        run_id: str,
        *,
        state: RunState,
        reviewer: str,
        decision: str,
        pdf_path: str,
        checksum: str,
    ) -> None:
        now = iso_now()
        self._execute(
            "UPDATE runs SET state=?, reviewed_by=?, reviewed_at=?, review_decision=?, final_pdf_path=?, final_pdf_checksum=?, updated_at=? WHERE run_id=?",
            (state.value, reviewer, now, decision, pdf_path, checksum, now, run_id),
        )

    def require_review_ready(self, run_id: str) -> RunRecord:
        run = self.get_run(run_id)
        if run.state != RunState.REVIEW_READY:
            raise InvalidRunTransition(f"run must be REVIEW_READY, got {run.state}")
        return run


class _Transaction:
    def __init__(self, conn, backend: str) -> None:
        self.conn = conn
        self.backend = backend

    def __enter__(self):
        if self.backend == "postgres":
            self.conn.execute("BEGIN")
            return self
        for _ in range(20):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                return self
            except sqlite3.OperationalError:
                time.sleep(0.01)
        self.conn.execute("BEGIN IMMEDIATE")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.conn.execute("ROLLBACK" if exc else "COMMIT")


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    status = CheckStatus(row["automation_status"]) if row["automation_status"] else None
    return RunRecord(row["run_id"], RunState(row["state"]), status, row["started_by"], row["created_at"], row["started_at"], row["finished_at"], row["worker_id"], row["last_heartbeat"], row["current_module"], row["reviewed_by"], row["reviewed_at"], row["review_decision"], row["application_version"], row["git_commit"], row["config_version"], row["final_snapshot_path"], row["final_pdf_path"], row["final_pdf_checksum"])


def _result_from_row(row: sqlite3.Row) -> CheckResult:
    return CheckResult(row["run_id"], row["module"], row["check_id"], CheckStatus(row["status"]), row["message"], site=row["site"], target=row["target"], expected=json.loads(row["expected_json"]) if row["expected_json"] else None, actual=json.loads(row["actual_json"]) if row["actual_json"] else None, started_at=row["started_at"], finished_at=row["finished_at"], metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {}, id=row["id"])


def _evidence_from_row(row: sqlite3.Row) -> EvidenceRecord:
    return EvidenceRecord(row["run_id"], row["module"], row["site"], row["evidence_type"], row["path"], row["checksum"], row["mime_type"], row["result_id"], row["id"], row["created_at"])


def _note_from_row(row: sqlite3.Row) -> ReviewNote:
    from app.domain import NoteScope

    return ReviewNote(row["run_id"], NoteScope(row["scope"]), row["author"], row["note"], row["module"], row["result_id"], row["dashboard_id"], row["id"], row["created_at"], row["updated_at"])
