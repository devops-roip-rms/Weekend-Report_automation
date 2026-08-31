from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config.validation import (
    ValidationReport,
    _validate_runtime_environment,
)


def auth_errors(
    report: ValidationReport,
) -> list[str]:
    return [
        issue.message
        for issue in report.errors
        if issue.path
        in {
            "runtime.auth",
            "runtime.csrf",
        }
    ]


class AuthConfigValidationTests(unittest.TestCase):
    def base_env(self) -> dict[str, str]:
        return {
            "WEEKEND_REPORT_APP_VERSION": "v0.0.0-test",
            "WEEKEND_REPORT_BUILD_ID": "test-build",
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_AUTHORIZED_REVIEWERS": "alice",
            "WEEKEND_REPORT_CSRF_SIGNING_KEY": "csrf-secret",
            "WEEKEND_REPORT_CSRF_TTL_SECONDS": "3600",
        }

    def validate(
        self,
        env: dict[str, str],
    ) -> ValidationReport:
        report = ValidationReport()

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            _validate_runtime_environment(
                {},
                report,
                production_preflight=True,
            )

        return report

    def test_trusted_header_requires_header_name(self):
        env = self.base_env()
        env["WEEKEND_REPORT_AUTH_PROVIDER"] = "trusted_header"

        report = self.validate(env)

        self.assertTrue(any("TRUSTED_HEADER" in message for message in auth_errors(report)))

    def test_valid_trusted_header_configuration(self):
        env = self.base_env()

        env.update(
            {
                "WEEKEND_REPORT_AUTH_PROVIDER": "trusted_header",
                "WEEKEND_REPORT_AUTH_TRUSTED_HEADER": "X-Authenticated-User",
            }
        )

        report = self.validate(env)

        self.assertEqual(
            auth_errors(report),
            [],
        )

    def test_local_login_requires_local_auth_inputs(self):
        env = self.base_env()

        env["WEEKEND_REPORT_AUTH_PROVIDER"] = "local_login"

        report = self.validate(env)

        messages = auth_errors(report)

        self.assertTrue(any("LOCAL_USERS_FILE" in message for message in messages))

        self.assertTrue(any("SESSION_SIGNING_KEY" in message for message in messages))

    def test_valid_local_login_configuration(self):
        env = self.base_env()

        env.update(
            {
                "WEEKEND_REPORT_AUTH_PROVIDER": "local_login",
                "WEEKEND_REPORT_LOCAL_USERS_FILE": "/app/secrets/local-users.json",
                "WEEKEND_REPORT_SESSION_SIGNING_KEY": "session-secret",
                "WEEKEND_REPORT_SESSION_TTL_SECONDS": "14400",
            }
        )

        report = self.validate(env)

        self.assertEqual(
            auth_errors(report),
            [],
        )

    def test_unknown_provider_is_rejected(self):
        env = self.base_env()

        env["WEEKEND_REPORT_AUTH_PROVIDER"] = "invalid-provider"

        report = self.validate(env)

        self.assertTrue(
            any("trusted_header or local_login" in message for message in auth_errors(report))
        )


if __name__ == "__main__":
    unittest.main()
