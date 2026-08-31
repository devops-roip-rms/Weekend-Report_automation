from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class DatabaseSyncScriptBlocked(RuntimeError):
    def __init__(self, code: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.metadata = metadata or {}


@dataclass(slots=True)
class DatabaseScriptInspection:
    path: str
    exists: bool
    nonempty: bool
    line_count: int


def run_database_sync_test(
    database_config: dict[str, Any],
    full_config: dict[str, Any],
) -> dict[str, Any]:
    """Execution boundary for the approved PowerShell database synchronization script.

    Execution remains blocked until the script's runtime, arguments, result
    contract, timeout behavior, and cleanup semantics are verified.
    """

    inspection = inspect_database_sync_script(database_config, full_config)
    if not inspection.exists:
        raise DatabaseSyncScriptBlocked(
            "DATABASE_SYNC_SCRIPT_MISSING",
            "Approved database synchronization script is missing from the project.",
            asdict(inspection),
        )
    if not inspection.nonempty:
        raise DatabaseSyncScriptBlocked(
            "DATABASE_SYNC_SCRIPT_CONTRACT_UNAVAILABLE",
            (
                "Approved database synchronization script is empty; runtime, arguments, "
                "exit-code semantics, and cleanup behavior cannot be verified."
            ),
            asdict(inspection),
        )
    raise DatabaseSyncScriptBlocked(
        "DATABASE_SYNC_SCRIPT_EXECUTION_HOST_UNVERIFIED",
        (
            "Database script execution remains blocked until the owner verifies the "
            "PowerShell runtime, host environment, arguments, result mapping, and timeout contract."
        ),
        asdict(inspection),
    )


def inspect_database_sync_script(
    database_config: dict[str, Any],
    full_config: dict[str, Any],
) -> DatabaseScriptInspection:
    script = database_config.get("script") or {}
    script_path = str(script.get("path") or "")
    project_root = _project_root(full_config)
    path = project_root / script_path
    exists = path.is_file()
    text = path.read_text(encoding="utf-8-sig") if exists else ""
    return DatabaseScriptInspection(
        path=script_path,
        exists=exists,
        nonempty=bool(text.strip()),
        line_count=len(text.splitlines()),
    )


def _project_root(config: dict[str, Any]) -> Path:
    config_dir = config.get("_config_dir")
    if isinstance(config_dir, str) and config_dir:
        return Path(config_dir).resolve().parent
    return Path.cwd()
