from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header

from app.config.loader import load_config_dir
from app.database.repository import Repository
from app.evidence.manager import EvidenceManager


_repo: Repository | None = None


def get_config():
    return load_config_dir(os.getenv("WEEKEND_REPORT_CONFIG_DIR", "config"))


def get_repository() -> Repository:
    global _repo
    if _repo is None:
        url = os.getenv("WEEKEND_REPORT_DATABASE_URL", "sqlite:///data/weekend-report.sqlite")
        _repo = Repository(url)
    return _repo


def get_evidence_manager() -> EvidenceManager:
    return EvidenceManager(os.getenv("WEEKEND_REPORT_EVIDENCE_ROOT", "runs"))


def get_reviewer(x_reviewer: str | None = Header(default=None)) -> str:
    return x_reviewer or os.getenv("WEEKEND_REPORT_DEV_REVIEWER", "anonymous")
