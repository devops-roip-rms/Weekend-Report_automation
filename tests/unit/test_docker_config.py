from __future__ import annotations

import unittest
from pathlib import Path


class DockerConfigTests(unittest.TestCase):
    def test_dockerfile_uses_expected_python_base_image(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.14-slim-bookworm", dockerfile)
        self.assertNotIn("FROM python:latest", dockerfile)

    def test_production_compose_uses_configurable_loaded_image(self):
        compose = Path("deploy/docker/compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("build:", compose)
        self.assertGreaterEqual(
            compose.count("image: ${WEEKEND_REPORT_IMAGE:-weekend-report:local}"),
            2,
        )

    def test_compose_does_not_use_template_placeholders_as_runtime_secrets(self):
        compose = Path("deploy/docker/compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("<TBD>", compose)
        self.assertNotIn("env.example", compose)
        self.assertNotIn("env_file", compose)
        self.assertIn("POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?", compose)
        self.assertIn("WEEKEND_REPORT_APP_VERSION: ${WEEKEND_REPORT_APP_VERSION:?", compose)
        self.assertIn("WEEKEND_REPORT_BUILD_ID: ${WEEKEND_REPORT_BUILD_ID:?", compose)
        self.assertIn(
            "WEEKEND_REPORT_CSRF_SIGNING_KEY: ${WEEKEND_REPORT_CSRF_SIGNING_KEY:?",
            compose,
        )
        self.assertIn("PORTAINER_SITE1_URL: ${PORTAINER_SITE1_URL:-}", compose)
        self.assertIn("PORTAINER_SITE1_TOKEN: ${PORTAINER_SITE1_TOKEN:-}", compose)
        self.assertIn("PORTAINER_SITE2_URL: ${PORTAINER_SITE2_URL:-}", compose)
        self.assertIn("PORTAINER_SITE2_TOKEN: ${PORTAINER_SITE2_TOKEN:-}", compose)
        self.assertIn("RABBITMQ_SITE1_URL: ${RABBITMQ_SITE1_URL:-}", compose)
        self.assertIn("RABBITMQ_SITE1_USER: ${RABBITMQ_SITE1_USER:-}", compose)
        self.assertIn("RABBITMQ_SITE1_PASSWORD: ${RABBITMQ_SITE1_PASSWORD:-}", compose)
        self.assertIn("RABBITMQ_SITE2_URL: ${RABBITMQ_SITE2_URL:-}", compose)
        self.assertIn("RABBITMQ_SITE2_USER: ${RABBITMQ_SITE2_USER:-}", compose)
        self.assertIn("RABBITMQ_SITE2_PASSWORD: ${RABBITMQ_SITE2_PASSWORD:-}", compose)
        self.assertIn(
            "RECORDING_MANAGER_WEBAPP_URL: ${RECORDING_MANAGER_WEBAPP_URL:-}",
            compose,
        )
        self.assertIn("RECORDING_SITE1_WEBAPP_URL: ${RECORDING_SITE1_WEBAPP_URL:-}", compose)
        self.assertIn("RECORDING_SITE2_WEBAPP_URL: ${RECORDING_SITE2_WEBAPP_URL:-}", compose)
        self.assertIn("SSH_PRIVATE_KEY_PATH: ${SSH_PRIVATE_KEY_PATH:-}", compose)
        self.assertIn("SSH_KNOWN_HOSTS_PATH: ${SSH_KNOWN_HOSTS_PATH:-}", compose)
        self.assertNotIn("DATABASE_SYNC_SCRIPT_PATH", compose)
        self.assertNotIn("WEEKEND_REPORT_CSRF_TOKEN", compose)

    def test_environment_examples_are_templates_only(self):
        for path in (Path(".env.example"), Path("deploy/docker/.env.example")):
            text = path.read_text(encoding="utf-8")
            self.assertIn("WEEKEND_REPORT_IMAGE=weekend-report:local", text)
            self.assertIn("WEEKEND_REPORT_APP_VERSION=<TBD>", text)
            self.assertIn("WEEKEND_REPORT_BUILD_ID=<TBD>", text)
            self.assertIn("RABBITMQ_SITE1_URL=<TBD>", text)
            self.assertIn("RECORDING_MANAGER_WEBAPP_URL=<TBD>", text)
            self.assertIn("SSH_PRIVATE_KEY_PATH=<TBD>", text)
            self.assertIn("SSH_KNOWN_HOSTS_PATH=<TBD>", text)
            self.assertNotIn("DATABASE_SYNC_SCRIPT_PATH", text)
            self.assertNotIn("WEEKEND_REPORT_APP_VERSION=1.0.1", text)
            self.assertNotIn("WR-20260812-01", text)


if __name__ == "__main__":
    unittest.main()
