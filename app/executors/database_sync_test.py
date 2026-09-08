import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.time_utils import iso_now


class DatabaseSyncScriptBlocked(RuntimeError):
    def __init__(self, code: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.metadata = metadata or {}

class DatabaseSyncResultError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.metadata = metadata or {}

class DatabaseSyncExecutionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
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

def _build_database_script_env(
    database_config: dict[str, Any],
) -> dict[str, str]:
    pairs = database_config.get("pairs")
    credentials = database_config.get("credentials")

    if not isinstance(pairs, list) or len(pairs) != 3:
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
            "Database synchronization runtime requires exactly 3 database pairs",
        )

    if not isinstance(credentials, dict):
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
            "Database synchronization credentials configuration is invalid",
        )

    username = credentials.get("username")
    password_file = credentials.get("password_file")

    if not isinstance(username, str) or not username.strip():
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
            "Database synchronization username is not configured",
        )

    if not isinstance(password_file, str) or not password_file.strip():
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
            "Database synchronization password-file path is not configured",
        )

    #
    # Preserve PATH and other process-level runtime values, but remove
    # inherited DATABASE_* variables first.
    #
    # Only the canonical database variables derived from validated
    # application configuration are supplied to the PowerShell process.
    #
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DATABASE_")
    }

    env["DATABASE_PAIR_COUNT"] = str(len(pairs))
    env["DATABASE_USERNAME"] = username.strip()
    env["DATABASE_PASSWORD_FILE"] = password_file.strip()

    for index, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            raise DatabaseSyncExecutionError(
                "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
                f"Database pair {index} is invalid",
            )

        name = pair.get("name")
        site1_host = pair.get("site1_host")
        site2_host = pair.get("site2_host")
        port = pair.get("port")

        if not isinstance(name, str) or not name.strip():
            raise DatabaseSyncExecutionError(
                "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
                f"Database pair {index} name is invalid",
            )

        if not isinstance(site1_host, str) or not site1_host.strip():
            raise DatabaseSyncExecutionError(
                "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
                f"Database pair {index} Site 1 host is invalid",
            )

        if not isinstance(site2_host, str) or not site2_host.strip():
            raise DatabaseSyncExecutionError(
                "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
                f"Database pair {index} Site 2 host is invalid",
            )

        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise DatabaseSyncExecutionError(
                "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
                f"Database pair {index} port is invalid",
            )

        prefix = f"DATABASE_PAIR_{index}"

        env[f"{prefix}_NAME"] = name.strip()
        env[f"{prefix}_SITE1_HOST"] = site1_host.strip()
        env[f"{prefix}_SITE2_HOST"] = site2_host.strip()
        env[f"{prefix}_PORT"] = str(port)

    return env

def run_database_sync_test(
    database_config: dict[str, Any],
    full_config: dict[str, Any],
) -> dict[str, Any]:
    """Execute the approved PowerShell database synchronization test."""

    inspection = inspect_database_sync_script(
        database_config,
        full_config,
    )

    if not inspection.exists:
        raise DatabaseSyncScriptBlocked(
            "DATABASE_SYNC_SCRIPT_MISSING",
            "Approved database synchronization script is missing from the project.",
            asdict(inspection),
        )

    if not inspection.nonempty:
        raise DatabaseSyncScriptBlocked(
            "DATABASE_SYNC_SCRIPT_CONTRACT_UNAVAILABLE",
            "Approved database synchronization script is empty.",
            asdict(inspection),
        )

    project_root = _project_root(full_config).resolve()

    script_path = (
        project_root / inspection.path
    ).resolve()

    #
    # Defense in depth: even though configuration validation already
    # rejects unsafe project-relative paths, do not execute anything
    # that resolves outside the project root.
    #
    try:
        script_path.relative_to(project_root)
    except ValueError as exc:
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_SCRIPT_PATH_UNSAFE",
            "Database synchronization script resolved outside the project root",
            asdict(inspection),
        ) from exc

    pwsh = shutil.which("pwsh")

    if pwsh is None:
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_POWERSHELL_UNAVAILABLE",
            "PowerShell executable 'pwsh' is not available in the runtime environment",
        )

    script_config = database_config.get("script") or {}

    timeout_value = script_config.get(
        "execution_timeout_seconds"
    )

    if (
        isinstance(timeout_value, bool)
        or not isinstance(timeout_value, (int, float))
        or timeout_value <= 0
    ):
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_RUNTIME_CONFIG_INVALID",
            "Database synchronization execution timeout is invalid",
        )

    timeout_seconds = float(timeout_value)

    child_env = _build_database_script_env(
        database_config
    )

    command = [
        pwsh,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=child_env,
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
        )

    except subprocess.TimeoutExpired as exc:
        #
        # The external timeout is a hard safety boundary.
        #
        # Because the PowerShell process was terminated, its finally
        # block may not have completed. Cleanup therefore cannot be
        # claimed.
        #
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_SCRIPT_TIMEOUT_CLEANUP_UNPROVEN",
            (
                "Database synchronization script exceeded its execution timeout; "
                "temporary-database cleanup cannot be proven"
            ),
            {
                "timeout_seconds": timeout_seconds,
                "cleanup": "UNPROVEN",
            },
        ) from exc

    except OSError as exc:
        raise DatabaseSyncExecutionError(
            "DATABASE_SYNC_SCRIPT_LAUNCH_FAILED",
            "PowerShell database synchronization process could not be started",
            {
                "error_type": type(exc).__name__,
            },
        ) from exc

    try:
        return parse_database_script_result(
            completed.stdout,
            completed.returncode,
        )

    except DatabaseSyncResultError as exc:
        #
        # Do not put raw stderr into evidence. It may contain
        # environment-specific DB/runtime information.
        #
        metadata = {
            **exc.metadata,
            "exit_code": completed.returncode,
            "stderr_present": bool(
                completed.stderr.strip()
            ),
        }

        raise DatabaseSyncResultError(
            exc.code,
            exc.message,
            metadata,
        ) from exc


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

def parse_database_script_result(
    stdout: str,
    exit_code: int,
) -> dict[str, Any]:
    expected_status_by_exit_code = {
        0: "PASS",
        1: "FAIL",
        2: "ERROR",
    }

    expected_status = expected_status_by_exit_code.get(exit_code)

    if expected_status is None:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_EXIT_CODE",
            f"Database synchronization script returned unsupported exit code {exit_code}",
            {"exit_code": exit_code},
        )

    raw = stdout.strip()

    if not raw:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_EMPTY_OUTPUT",
            "Database synchronization script returned no JSON result",
            {"exit_code": exit_code},
        )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_JSON",
            "Database synchronization script output is not valid JSON",
            {
                "exit_code": exit_code,
                "json_error": str(exc),
            },
        ) from exc

    if not isinstance(result, dict):
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
            "Database synchronization script result must be a JSON object",
        )

    if result.get("schema_version") != 1:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_UNSUPPORTED_SCHEMA",
            "Database synchronization script must return schema_version 1",
            {"schema_version": result.get("schema_version")},
        )

    status = result.get("status")

    if status not in {"PASS", "FAIL", "ERROR"}:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_STATUS",
            "Database synchronization script returned an invalid status",
            {"status": status},
        )

    if status != expected_status:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_EXIT_STATUS_MISMATCH",
            (
                f"Database synchronization script exit code {exit_code} "
                f"requires status {expected_status}, but returned {status}"
            ),
            {
                "exit_code": exit_code,
                "status": status,
            },
        )

    code = result.get("code")
    message = result.get("message")
    run_id = result.get("run_id")
    cleanup = result.get("cleanup")

    for field_name, value in (
        ("code", code),
        ("message", message),
        ("run_id", run_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"Database synchronization script field {field_name!r} must be non-empty",
            )

    if cleanup not in {"NOT_RUN", "PASS", "ERROR"}:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
            "Database synchronization script returned an invalid cleanup state",
            {"cleanup": cleanup},
        )

    #
    # A technical script ERROR stays an execution ERROR.
    # Do not try to manufacture per-site PASS/FAIL results.
    #
    if status == "ERROR":
        return {
            "mode": "live",
            "collection_timestamp": iso_now(),
            "sites": {},
            "error": message,
            "errors": [
                {
                    "code": code,
                    "message": message,
                    "metadata": {
                        "schema_version": 1,
                        "run_id": run_id,
                        "cleanup": cleanup,
                    },
                }
            ],
        }

    #
    # PASS/FAIL are reliable functional results and therefore require
    # complete results for both sites plus proven cleanup.
    #
    if cleanup != "PASS":
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_CLEANUP_UNPROVEN",
            "Functional database result requires cleanup=PASS",
            {
                "status": status,
                "cleanup": cleanup,
            },
        )

    raw_sites = result.get("sites")

    if not isinstance(raw_sites, list) or len(raw_sites) != 2:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
            "Database synchronization script must return exactly two site results",
        )

    normalized_sites: dict[str, Any] = {}

    for raw_site in raw_sites:
        if not isinstance(raw_site, dict):
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                "Each database site result must be a JSON object",
            )

        site_name = raw_site.get("name")

        if site_name not in {"site1", "site2"}:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                "Database site name must be site1 or site2",
                {"site": site_name},
            )

        if site_name in normalized_sites:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"Duplicate database site result: {site_name}",
            )

        node_count = raw_site.get("node_count")

        if node_count != 3:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"{site_name} must contain exactly 3 database nodes",
                {
                    "site": site_name,
                    "node_count": node_count,
                },
            )

        site_status = raw_site.get("status")
        create_visibility = raw_site.get("create_visibility")
        drop_visibility = raw_site.get("drop_visibility")

        if site_status not in {"PASS", "FAIL"}:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"{site_name} returned an invalid site status",
                {"site_status": site_status},
            )

        if create_visibility not in {"PASS", "FAIL"}:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"{site_name} returned an invalid create_visibility value",
                {"create_visibility": create_visibility},
            )

        if drop_visibility not in {"PASS", "FAIL"}:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"{site_name} returned an invalid drop_visibility value",
                {"drop_visibility": drop_visibility},
            )

        calculated_site_status = (
            "PASS"
            if create_visibility == "PASS"
            and drop_visibility == "PASS"
            else "FAIL"
        )

        if site_status != calculated_site_status:
            raise DatabaseSyncResultError(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                f"{site_name} status does not match its synchronization results",
                {
                    "site_status": site_status,
                    "calculated_status": calculated_site_status,
                },
            )

        #
        # CREATE/DROP SQL failures are technical exceptions in the
        # PowerShell script and therefore result in exit 2 / ERROR.
        #
        # Reaching a functional site result proves both SQL commands ran.
        #
        normalized_sites[site_name] = {
            "target": "database_sync_test",
            "create_success": True,
            "replication_after_create": create_visibility == "PASS",
            "delete_success": True,
            "replication_after_delete": drop_visibility == "PASS",
            "cleanup_complete": True,
            "errors": [],
        }

    if set(normalized_sites) != {"site1", "site2"}:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
            "Database synchronization script must return site1 and site2 exactly once",
        )

    functional_failure = any(
        not site["replication_after_create"]
        or not site["replication_after_delete"]
        for site in normalized_sites.values()
    )

    if status == "PASS" and functional_failure:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
            "Script returned PASS while a site synchronization check failed",
        )

    if status == "FAIL" and not functional_failure:
        raise DatabaseSyncResultError(
            "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
            "Script returned FAIL but both sites passed synchronization",
        )

    return {
        "mode": "live",
        "collection_timestamp": iso_now(),
        "sites": normalized_sites,
        "errors": [],
        "script_result": {
            "schema_version": 1,
            "run_id": run_id,
            "status": status,
            "code": code,
            "message": message,
            "cleanup": cleanup,
        },
    }

def _project_root(config: dict[str, Any]) -> Path:
    project_root = config.get("_project_root")
    if isinstance(project_root, str) and project_root:
        return Path(project_root).resolve()
    config_dir = config.get("_config_dir")
    if isinstance(config_dir, str) and config_dir:
        return Path(config_dir).resolve().parent
    return Path.cwd()
