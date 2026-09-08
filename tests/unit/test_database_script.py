import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "database" / "database_sync_check.ps1"


class DatabaseScriptTests(unittest.TestCase):
    def test_database_script_uses_external_runtime_configuration(self):
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("DATABASE_PAIR_COUNT", text)
        self.assertIn("DATABASE_USERNAME", text)
        self.assertIn("DATABASE_PASSWORD_FILE", text)

        self.assertIn("DATABASE_PAIR_${Index}_SITE1_HOST", text)
        self.assertIn("DATABASE_PAIR_${Index}_SITE2_HOST", text)

        self.assertIn("Import-Module SimplySql", text)
        self.assertIn("Open-MySqlConnection", text)
        self.assertIn("Invoke-SqlQuery", text)

        self.assertNotIn("$User = root", text)
        self.assertNotIn("XXXXXXXX", text)

    def test_database_script_has_machine_readable_result_contract(self):
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ConvertTo-Json", text)
        self.assertIn("DATABASE_SYNC_PASS", text)
        self.assertIn("DATABASE_SYNC_FAIL", text)
        self.assertIn("DATABASE_SYNC_SCRIPT_ERROR", text)
        self.assertIn("DATABASE_SYNC_CLEANUP_FAILED", text)

        self.assertIn("exit $ExitCode", text)

    def test_database_script_uses_unique_tests_and_cleanup(self):
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("[guid]::NewGuid()", text)
        self.assertIn("CREATE DATABASE", text)
        self.assertIn("DROP DATABASE", text)
        self.assertIn("DROP DATABASE IF EXISTS", text)


if __name__ == "__main__":
    unittest.main()