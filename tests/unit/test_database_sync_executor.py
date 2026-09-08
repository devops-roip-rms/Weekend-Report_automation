import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.executors.database_sync_test import (
    DatabaseSyncExecutionError,
    DatabaseSyncResultError,
    parse_database_script_result,
    run_database_sync_test,
)
from tests.fixtures.config_factory import load_valid_config


def _site(
    name: str,
    *,
    create: str = "PASS",
    drop: str = "PASS",
) -> dict:
    status = (
        "PASS"
        if create == "PASS" and drop == "PASS"
        else "FAIL"
    )

    return {
        "name": name,
        "status": status,
        "code": (
            "DATABASE_SITE_SYNC_PASS"
            if status == "PASS"
            else "DATABASE_SITE_SYNC_FAIL"
        ),
        "create_visibility": create,
        "drop_visibility": drop,
        "node_count": 3,
    }


def _result(
    *,
    status: str,
    cleanup: str = "PASS",
    sites: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "status": status,
            "code": f"DATABASE_SYNC_{status}",
            "message": f"database result {status}",
            "run_id": "20260908_test",
            "sites": sites if sites is not None else [],
            "cleanup": cleanup,
        }
    )


class DatabaseSyncExecutorContractTests(unittest.TestCase):
    def test_pass_result_normalizes_to_existing_validator_contract(self):
        stdout = _result(
            status="PASS",
            sites=[
                _site("site1"),
                _site("site2"),
            ],
        )

        actual = parse_database_script_result(
            stdout,
            0,
        )

        self.assertNotIn("error", actual)

        self.assertEqual(
            set(actual["sites"]),
            {"site1", "site2"},
        )

        for site in actual["sites"].values():
            self.assertIs(site["create_success"], True)
            self.assertIs(
                site["replication_after_create"],
                True,
            )
            self.assertIs(site["delete_success"], True)
            self.assertIs(
                site["replication_after_delete"],
                True,
            )
            self.assertIs(site["cleanup_complete"], True)

    def test_functional_sync_failure_remains_fail_not_error(self):
        stdout = _result(
            status="FAIL",
            sites=[
                _site(
                    "site1",
                    create="FAIL",
                    drop="PASS",
                ),
                _site("site2"),
            ],
        )

        actual = parse_database_script_result(
            stdout,
            1,
        )

        self.assertNotIn("error", actual)

        self.assertIs(
            actual["sites"]["site1"]["create_success"],
            True,
        )
        self.assertIs(
            actual["sites"]["site1"][
                "replication_after_create"
            ],
            False,
        )
        self.assertIs(
            actual["sites"]["site1"]["delete_success"],
            True,
        )
        self.assertIs(
            actual["sites"]["site1"][
                "replication_after_delete"
            ],
            True,
        )
        self.assertIs(
            actual["sites"]["site1"]["cleanup_complete"],
            True,
        )

    def test_exit_2_normalizes_to_technical_error(self):
        stdout = _result(
            status="ERROR",
            cleanup="NOT_RUN",
            sites=[],
        )

        actual = parse_database_script_result(
            stdout,
            2,
        )

        self.assertIn("error", actual)
        self.assertEqual(actual["sites"], {})
        self.assertEqual(
            actual["errors"][0]["code"],
            "DATABASE_SYNC_ERROR",
        )

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(DatabaseSyncResultError) as ctx:
            parse_database_script_result(
                "this is not json",
                2,
            )

        self.assertEqual(
            ctx.exception.code,
            "DATABASE_SYNC_SCRIPT_INVALID_JSON",
        )

    def test_exit_code_and_status_must_match(self):
        stdout = _result(
            status="PASS",
            sites=[
                _site("site1"),
                _site("site2"),
            ],
        )

        with self.assertRaises(DatabaseSyncResultError) as ctx:
            parse_database_script_result(
                stdout,
                1,
            )

        self.assertEqual(
            ctx.exception.code,
            "DATABASE_SYNC_SCRIPT_EXIT_STATUS_MISMATCH",
        )

    def test_functional_result_requires_proven_cleanup(self):
        stdout = _result(
            status="FAIL",
            cleanup="ERROR",
            sites=[
                _site(
                    "site1",
                    create="FAIL",
                ),
                _site("site2"),
            ],
        )

        with self.assertRaises(DatabaseSyncResultError) as ctx:
            parse_database_script_result(
                stdout,
                1,
            )

        self.assertEqual(
            ctx.exception.code,
            "DATABASE_SYNC_SCRIPT_CLEANUP_UNPROVEN",
        )

    def test_exactly_three_nodes_per_site_are_required(self):
        site1 = _site("site1")
        site1["node_count"] = 2

        stdout = _result(
            status="PASS",
            sites=[
                site1,
                _site("site2"),
            ],
        )

        with self.assertRaises(DatabaseSyncResultError):
            parse_database_script_result(
                stdout,
                0,
            )
    def test_run_passes_canonical_database_environment_to_powershell(self):
      config = load_valid_config()
      stdout = _result(
          status="PASS",
          sites=[
              _site("site1"),
              _site("site2"),
          ],
      )
      completed = SimpleNamespace(
          returncode=0,
          stdout=stdout,
          stderr="",
      )
      with patch(
          "app.executors.database_sync_test.shutil.which",
          return_value="/usr/bin/pwsh",
      ), patch(
          "app.executors.database_sync_test.subprocess.run",
          return_value=completed,
      ) as process_run:
          actual = run_database_sync_test(
              config["database"],
              config,
          )
      self.assertEqual(
          actual["script_result"]["status"],
          "PASS",
      )
      command = process_run.call_args.args[0]
      kwargs = process_run.call_args.kwargs
      self.assertEqual(
          command[0],
          "/usr/bin/pwsh",
      )
      self.assertIn(
          "-NonInteractive",
          command,
      )
      self.assertTrue(
          command[-1].endswith(
              "scripts/database/database_sync_check.ps1"
          )
          or command[-1].endswith(
              "scripts\\database\\database_sync_check.ps1"
          )
      )
      env = kwargs["env"]
      self.assertEqual(
          env["DATABASE_PAIR_COUNT"],
          "3",
      )
      self.assertEqual(
          env["DATABASE_PAIR_1_SITE1_HOST"],
          "192.0.2.11",
      )
      self.assertEqual(
          env["DATABASE_PAIR_1_SITE2_HOST"],
          "192.0.2.21",
      )
      self.assertEqual(
          env["DATABASE_PAIR_3_SITE1_HOST"],
          "192.0.2.13",
      )
      self.assertEqual(
          env["DATABASE_PAIR_3_SITE2_HOST"],
          "192.0.2.23",
      )
      self.assertEqual(
          env["DATABASE_USERNAME"],
          "fixture-db-user",
      )
      self.assertEqual(
          env["DATABASE_PASSWORD_FILE"],
          "/app/secrets/database_sync_password",
      )
      self.assertNotIn(
          "DATABASE_PASSWORD",
          env,
      )
      self.assertEqual(
          kwargs["timeout"],
          300.0,
      )
    def test_run_rejects_runtime_without_pwsh(self):
      config = load_valid_config()
      with patch(
          "app.executors.database_sync_test.shutil.which",
          return_value=None,
      ):
          with self.assertRaises(
              DatabaseSyncExecutionError
          ) as ctx:
              run_database_sync_test(
                  config["database"],
                  config,
              )
      self.assertEqual(
          ctx.exception.code,
          "DATABASE_SYNC_POWERSHELL_UNAVAILABLE",
      )
    def test_run_timeout_marks_cleanup_unproven(self):
      config = load_valid_config()
      with patch(
          "app.executors.database_sync_test.shutil.which",
          return_value="/usr/bin/pwsh",
      ), patch(
          "app.executors.database_sync_test.subprocess.run",
          side_effect=subprocess.TimeoutExpired(
              cmd=["pwsh"],
              timeout=300,
          ),
      ):
          with self.assertRaises(
              DatabaseSyncExecutionError
          ) as ctx:
              run_database_sync_test(
                  config["database"],
                  config,
              )
      self.assertEqual(
          ctx.exception.code,
          "DATABASE_SYNC_SCRIPT_TIMEOUT_CLEANUP_UNPROVEN",
      )
      self.assertEqual(
          ctx.exception.metadata["cleanup"],
          "UNPROVEN",
      )


if __name__ == "__main__":
    unittest.main()