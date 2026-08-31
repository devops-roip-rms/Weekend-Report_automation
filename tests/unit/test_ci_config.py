from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class CIConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.github_quality = Path(".github/workflows/quality-gates.yml")
        self.github_image = Path(".github/workflows/build-image.yml")
        self.gitlab_root = Path(".gitlab-ci.yml")
        self.gitlab_quality = Path(".gitlab-ci-cd/quality.yml")
        self.gitlab_image = Path(".gitlab-ci-cd/image.yml")
        self.ci_compose = Path("deploy/docker/compose.ci.yml")
        self.github_scripts = Path(".github/scripts")
        self.gitlab_scripts = Path(".gitlab-ci-cd/scripts")

    def test_ci_yaml_files_parse(self):
        for path in (
            self.github_quality,
            self.github_image,
            self.gitlab_root,
            self.gitlab_quality,
            self.gitlab_image,
            self.ci_compose,
        ):
            self.assertTrue(path.exists(), path)
            self.assertIsNotNone(yaml.safe_load(path.read_text(encoding="utf-8")), path)

    def test_github_quality_exposes_each_release_blocking_gate(self):
        text = self.github_quality.read_text(encoding="utf-8")
        for gate in (
            "config-validation:",
            "ruff:",
            "mypy:",
            "unit-tests:",
            "integration-tests:",
            "contract-tests:",
            "postgres-concurrency:",
            "safe-e2e:",
            "dependency-audit:",
            "docker-compose-validate:",
        ):
            self.assertIn(gate, text)
        self.assertIn("workflow_call:", text)
        self.assertIn("postgres:16-alpine", text)
        self.assertNotIn("continue-on-error", text)

    def test_github_image_is_gated_and_smoked_before_export_or_publish(self):
        text = self.github_image.read_text(encoding="utf-8")
        self.assertIn("uses: ./.github/workflows/quality-gates.yml", text)
        self.assertIn("needs: quality", text)
        build = text.index("Build image only after all pre-image gates pass")
        smoke = text.index("Smoke-test the exact built image")
        version_tag = text.index("Version-tag the exact smoked image")
        export = text.index("Export verified offline image artifact")
        publish = text.index("Publish the exact verified image")
        self.assertLess(build, smoke)
        self.assertLess(smoke, version_tag)
        self.assertLess(version_tag, export)
        self.assertLess(export, publish)
        expected_scripts = (
            "derive-build-identity.sh",
            "record-built-image.sh",
            "version-tag-smoked-image.sh",
            "export-verified-image.sh",
            "decide-publish.sh",
            "login-ghcr.sh",
            "publish-verified-image.sh",
        )
        for script_name in expected_scripts:
            script_path = self.github_scripts / script_name
            self.assertTrue(script_path.is_file(), script_path)
            self.assertIn(f".github/scripts/{script_name}", text)
        identity_script = (
            self.github_scripts / "derive-build-identity.sh"
        ).read_text(encoding="utf-8")
        version_script = (
            self.github_scripts / "version-tag-smoked-image.sh"
        ).read_text(encoding="utf-8")
        export_script = (
            self.github_scripts / "export-verified-image.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("TAG", identity_script)
        self.assertTrue(
            "docker tag" in version_script
            or "docker image tag" in version_script
        )
        self.assertIn("docker save", export_script)
        self.assertNotIn("continue-on-error", text)

    def test_gitlab_image_needs_all_quality_jobs(self):
        text = self.gitlab_image.read_text(encoding="utf-8")
        for gate in (
            "config-validation",
            "ruff",
            "mypy",
            "unit-tests",
            "integration-tests",
            "contract-tests",
            "postgres-concurrency",
            "safe-e2e",
            "dependency-audit",
            "docker-compose-validate",
        ):
            self.assertIn(f"- {gate}", text)
        self.assertNotIn("allow_failure: true", text)
        main_script_path = (
            self.gitlab_scripts / "image-build-smoke-export.sh"
        )
        export_script_path = (
            self.gitlab_scripts / "export-offline-image.sh"
        )
        publish_script_path = (
            self.gitlab_scripts / "publish-image.sh"
        )
        verify_script_path = (
            self.gitlab_scripts / "verify-release-image.sh"
        )
        for script_path in (
            main_script_path,
            export_script_path,
            publish_script_path,
            verify_script_path,
        ):
            self.assertTrue(script_path.is_file(), script_path)
        self.assertIn(
            "sh .gitlab-ci-cd/scripts/image-build-smoke-export.sh",
            text,
        )
        main_script = main_script_path.read_text(encoding="utf-8")
        export_script = export_script_path.read_text(encoding="utf-8")
        verify_script = verify_script_path.read_text(encoding="utf-8")
        self.assertIn("docker build", main_script)
        self.assertIn("image-smoke", main_script)
        self.assertIn(
            "verify-release-image.sh",
            main_script,
        )
        self.assertIn(
            "export-offline-image.sh",
            main_script,
        )
        self.assertIn(
            "publish-image.sh",
            main_script,
        )
        smoke = main_script.index("image-smoke")
        verify = main_script.index("verify-release-image.sh")
        export = main_script.index("export-offline-image.sh")
        publish = main_script.index("publish-image.sh")
        self.assertLess(smoke, verify)
        self.assertLess(verify, export)
        self.assertLess(export, publish)
        combined_tag_logic = main_script + "\n" + verify_script
        self.assertTrue(
            "docker tag" in combined_tag_logic
            or "docker image tag" in combined_tag_logic
        )
        self.assertIn("docker save", export_script)

    def test_image_release_is_driven_by_tag_file(self):
        github_text = self.github_image.read_text(encoding="utf-8")
        gitlab_text = self.gitlab_image.read_text(encoding="utf-8")
        github_identity = (
            self.github_scripts / "derive-build-identity.sh"
        ).read_text(encoding="utf-8")
        gitlab_image_script = (
            self.gitlab_scripts / "image-build-smoke-export.sh"
        ).read_text(encoding="utf-8")
        # GitHub: image automation is triggered by changes to TAG
        # on the main branch, not by Git tags.
        self.assertIn("paths:", github_text)
        self.assertIn("- TAG", github_text)
        self.assertIn("branches:", github_text)
        self.assertIn("- main", github_text)
        self.assertNotIn("GITHUB_REF_NAME", github_text)
        self.assertNotIn("refs/tags/", github_text)
        # TAG parsing now lives in the extracted identity script.
        self.assertIn(
            ".github/scripts/derive-build-identity.sh",
            github_text,
        )
        self.assertIn("TAG", github_identity)
        # GitLab: image automation is likewise driven by TAG changes
        # and is not triggered by Git tags.
        self.assertIn("changes:", gitlab_text)
        self.assertIn("- TAG", gitlab_text)
        self.assertNotIn("CI_COMMIT_TAG", gitlab_text)
        # TAG parsing belongs to the extracted GitLab image script.
        self.assertIn(
            ".gitlab-ci-cd/scripts/image-build-smoke-export.sh",
            gitlab_text,
        )
        self.assertIn("TAG", gitlab_image_script)

    def test_manual_verified_image_rebuild_triggers_are_supported(self):
        github_text = self.github_image.read_text(encoding="utf-8")
        gitlab_root_text = self.gitlab_root.read_text(encoding="utf-8")
        gitlab_image_text = self.gitlab_image.read_text(encoding="utf-8")

        # GitHub: manual rebuild is allowed in addition to TAG-change automation.
        self.assertIn("workflow_dispatch:", github_text)

        # GitLab: manually created UI pipelines must be allowed globally.
        self.assertIn(
            'CI_PIPELINE_SOURCE == "web"',
            gitlab_root_text,
        )

        # GitLab: the image job must participate in a manual pipeline
        # only on the default branch.
        self.assertIn(
            'CI_PIPELINE_SOURCE == "web" && $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH',
            gitlab_image_text,
        )

        # Automatic TAG-driven image creation must still remain enabled.
        self.assertIn("changes:", gitlab_image_text)
        self.assertIn("- TAG", gitlab_image_text)

    def test_gitlab_pipeline_is_not_git_tag_triggered(self):
        text = self.gitlab_root.read_text(encoding="utf-8")

        self.assertNotIn("CI_COMMIT_TAG", text)
        self.assertIn('CI_PIPELINE_SOURCE == "web"', text)
        self.assertIn('CI_PIPELINE_SOURCE == "merge_request_event"', text)
        self.assertIn(
            '$CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS && $CI_PIPELINE_SOURCE == "push"',
            text,
        )

    def test_ci_compose_uses_exact_image_and_fixture_config(self):
        text = self.ci_compose.read_text(encoding="utf-8")
        self.assertIn("WEEKEND_REPORT_CI_IMAGE", text)
        self.assertIn("/app/tests/fixtures/config_valid", text)
        self.assertNotIn("build:", text)
        self.assertIn("postgres:16-alpine", text)

    def test_ci_files_do_not_contain_production_integration_secrets(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                self.github_quality,
                self.github_image,
                self.gitlab_root,
                self.gitlab_quality,
                self.gitlab_image,
            )
        )
        for forbidden in (
            "PORTAINER_SITE1_TOKEN",
            "PORTAINER_SITE2_TOKEN",
            "RABBITMQ_SITE1_PASSWORD",
            "RABBITMQ_SITE2_PASSWORD",
            "SSH_PRIVATE_KEY_PATH",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
