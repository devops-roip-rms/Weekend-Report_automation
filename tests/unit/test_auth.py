from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from app.auth import (
    SESSION_COOKIE_NAME,
    authenticate_local_user,
    hash_password,
    issue_csrf_token,
    issue_session_token,
    require_csrf_for_mutation,
    resolve_reviewer,
    validate_session_token,
    verify_password,
)


def request(
    headers: dict[str, str] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": Headers(headers or {}).raw,
        }
    )


class AuthTests(unittest.TestCase):
    def test_development_allows_x_reviewer(self):
        with patch.dict(
            os.environ,
            {
                "WEEKEND_REPORT_AUTH_MODE": "development",
            },
            clear=True,
        ):
            self.assertEqual(
                resolve_reviewer(
                    request(
                        {
                            "X-Reviewer": "alice",
                        }
                    )
                ),
                "alice",
            )

    def test_production_rejects_x_reviewer(self):
        env = {
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_AUTH_PROVIDER": "trusted_header",
            "WEEKEND_REPORT_AUTH_TRUSTED_HEADER": "X-Authenticated-User",
            "WEEKEND_REPORT_AUTHORIZED_REVIEWERS": "alice",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            with self.assertRaises(HTTPException) as raised:
                resolve_reviewer(
                    request(
                        {
                            "X-Reviewer": "mallory",
                            "X-Authenticated-User": "alice",
                        }
                    ),
                    mutating=True,
                )

            self.assertIn(
                "X-Reviewer",
                str(raised.exception.detail),
            )

    def test_production_trusted_header_and_csrf(self):
        env = {
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_AUTH_PROVIDER": "trusted_header",
            "WEEKEND_REPORT_AUTH_TRUSTED_HEADER": "X-Authenticated-User",
            "WEEKEND_REPORT_AUTHORIZED_REVIEWERS": "alice",
            "WEEKEND_REPORT_CSRF_SIGNING_KEY": "test-csrf-signing-key",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            token = issue_csrf_token("alice")

            req = request(
                {
                    "X-Authenticated-User": "alice",
                    "X-CSRF-Token": token,
                }
            )

            self.assertEqual(
                resolve_reviewer(
                    req,
                    mutating=True,
                ),
                "alice",
            )

            require_csrf_for_mutation(
                req,
                "alice",
            )

    def test_production_requires_authorized_reviewer(self):
        env = {
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_AUTH_PROVIDER": "trusted_header",
            "WEEKEND_REPORT_AUTH_TRUSTED_HEADER": "X-Authenticated-User",
            "WEEKEND_REPORT_AUTHORIZED_REVIEWERS": "alice",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            with self.assertRaises(HTTPException) as raised:
                resolve_reviewer(
                    request(
                        {
                            "X-Authenticated-User": "mallory",
                        }
                    )
                )

            self.assertEqual(
                raised.exception.status_code,
                403,
            )

    def test_csrf_token_is_bound_to_reviewer(self):
        env = {
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_CSRF_SIGNING_KEY": "test-csrf-signing-key",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            token = issue_csrf_token("alice")

            with self.assertRaises(HTTPException):
                require_csrf_for_mutation(
                    request(
                        {
                            "X-CSRF-Token": token,
                        }
                    ),
                    "bob",
                )

    def test_password_hash_round_trip(self):
        encoded = hash_password("correct-password")

        self.assertTrue(
            verify_password(
                "correct-password",
                encoded,
            )
        )

        self.assertFalse(
            verify_password(
                "wrong-password",
                encoded,
            )
        )

    def test_local_user_authentication(self):
        with tempfile.TemporaryDirectory() as tmp:
            users_file = Path(tmp) / "local-users.json"

            users_file.write_text(
                json.dumps(
                    {
                        "users": {
                            "alice": hash_password("correct-password"),
                        }
                    }
                ),
                encoding="utf-8",
            )

            env = {
                "WEEKEND_REPORT_LOCAL_USERS_FILE": str(users_file),
            }

            with patch.dict(
                os.environ,
                env,
                clear=True,
            ):
                self.assertTrue(
                    authenticate_local_user(
                        "alice",
                        "correct-password",
                    )
                )

                self.assertFalse(
                    authenticate_local_user(
                        "alice",
                        "wrong-password",
                    )
                )

                self.assertFalse(
                    authenticate_local_user(
                        "unknown",
                        "wrong-password",
                    )
                )

    def test_local_session_resolves_reviewer(self):
        env = {
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_AUTH_PROVIDER": "local_login",
            "WEEKEND_REPORT_AUTHORIZED_REVIEWERS": "alice",
            "WEEKEND_REPORT_SESSION_SIGNING_KEY": "test-session-signing-key",
            "WEEKEND_REPORT_SESSION_TTL_SECONDS": "14400",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            token = issue_session_token("alice")

            reviewer = resolve_reviewer(
                request(
                    {
                        "Cookie": (f"{SESSION_COOKIE_NAME}={token}"),
                    }
                )
            )

            self.assertEqual(
                reviewer,
                "alice",
            )

    def test_tampered_session_is_rejected(self):
        env = {
            "WEEKEND_REPORT_SESSION_SIGNING_KEY": "test-session-signing-key",
            "WEEKEND_REPORT_SESSION_TTL_SECONDS": "14400",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            token = issue_session_token("alice")

            tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

            self.assertIsNone(validate_session_token(tampered))

    def test_expired_session_is_rejected(self):
        env = {
            "WEEKEND_REPORT_SESSION_SIGNING_KEY": "test-session-signing-key",
            "WEEKEND_REPORT_SESSION_TTL_SECONDS": "1",
        }

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            with patch(
                "app.auth.time.time",
                return_value=1000,
            ):
                token = issue_session_token("alice")

            with patch(
                "app.auth.time.time",
                return_value=1002,
            ):
                self.assertIsNone(validate_session_token(token))


if __name__ == "__main__":
    unittest.main()
