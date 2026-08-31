from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_auth
from app.auth import hash_password


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

        self.users_file = Path(self.tmp.name) / "local-users.json"

        self.users_file.write_text(
            json.dumps(
                {
                    "users": {
                        "alice": hash_password("correct-password"),
                    }
                }
            ),
            encoding="utf-8",
        )

        self.env = {
            "WEEKEND_REPORT_AUTH_MODE": "production",
            "WEEKEND_REPORT_AUTH_PROVIDER": "local_login",
            "WEEKEND_REPORT_AUTHORIZED_REVIEWERS": "alice",
            "WEEKEND_REPORT_LOCAL_USERS_FILE": str(self.users_file),
            "WEEKEND_REPORT_SESSION_SIGNING_KEY": "test-session-signing-key",
            "WEEKEND_REPORT_SESSION_TTL_SECONDS": "14400",
        }

        app = FastAPI()
        app.include_router(routes_auth.router)

        self.client = TestClient(
            app,
            base_url="https://testserver",
        )

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_login_page(self):
        with patch.dict(
            os.environ,
            self.env,
            clear=True,
        ):
            response = self.client.get("/login")

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "Weekend Report Automation",
            response.text,
        )

    def test_valid_login_sets_secure_session_cookie(self):
        with patch.dict(
            os.environ,
            self.env,
            clear=True,
        ):
            response = self.client.post(
                "/login",
                data={
                    "username": "alice",
                    "password": "correct-password",
                    "next": "/",
                },
                follow_redirects=False,
            )

        self.assertEqual(
            response.status_code,
            303,
        )

        cookie = response.headers.get(
            "set-cookie",
            "",
        ).lower()

        self.assertIn(
            "weekend_report_session=",
            cookie,
        )

        self.assertIn(
            "httponly",
            cookie,
        )

        self.assertIn(
            "secure",
            cookie,
        )

        self.assertIn(
            "samesite=lax",
            cookie,
        )

    def test_invalid_login_is_rejected(self):
        with patch.dict(
            os.environ,
            self.env,
            clear=True,
        ):
            response = self.client.post(
                "/login",
                data={
                    "username": "alice",
                    "password": "wrong-password",
                    "next": "/",
                },
                follow_redirects=False,
            )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertIn(
            "Invalid username or password",
            response.text,
        )

    def test_login_route_hidden_in_trusted_header_mode(self):
        env = dict(self.env)

        env["WEEKEND_REPORT_AUTH_PROVIDER"] = "trusted_header"

        with patch.dict(
            os.environ,
            env,
            clear=True,
        ):
            response = self.client.get("/login")

        self.assertEqual(
            response.status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
