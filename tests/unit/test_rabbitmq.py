from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app.collectors.rabbitmq import RabbitMQCollector
from app.config.loader import load_config_dir
from app.database.repository import Repository
from app.domain import CheckStatus
from app.evidence.manager import EvidenceManager
from app.orchestrator.run_context import RunContext
from app.validators.rabbitmq import RabbitMQValidator


class RabbitMQTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config_dir("tests/fixtures/config_valid")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = RunContext(
            "WR-20260811-000000",
            self.config,
            Repository("sqlite:///:memory:"),
            EvidenceManager(Path(self.tmp.name)),
        )
        self.addCleanup(self.ctx.repository.close)

    def fixture_sites(self) -> dict:
        return copy.deepcopy(self.config["rabbitmq_expected"]["fixture_actual"]["sites"])

    def validate_sites(self, sites: dict) -> list:
        return RabbitMQValidator().validate({"sites": sites, "errors": []}, self.config, self.ctx)

    def statuses(self, results: list, check_id: str) -> list[CheckStatus]:
        return [result.status for result in results if result.check_id == check_id]

    def test_zero_queue_counts_and_green_nodes_pass(self):
        results = self.validate_sites(self.fixture_sites())
        self.assertEqual(
            self.statuses(results, "rabbitmq.queue.counts"),
            [CheckStatus.PASS, CheckStatus.PASS],
        )
        node_statuses = [
            result.status for result in results if result.check_id.startswith("rabbitmq.node.")
        ]
        self.assertEqual(node_statuses, [CheckStatus.PASS] * 8)

    def test_nonzero_queue_counts_remain_error_after_rechecks(self):
        sites = self.fixture_sites()
        sites["site1"]["queues"][0]["ready"] = 1
        sites["site1"]["queues"][0]["total"] = 1
        sites["site1"]["queues"][0]["checks_performed"] = 4
        results = self.validate_sites(sites)
        queue = [
            result
            for result in results
            if result.check_id == "rabbitmq.queue.counts" and result.site == "site1"
        ][0]
        self.assertEqual(queue.status, CheckStatus.ERROR)
        self.assertEqual(queue.actual["checks_performed"], 4)
        self.assertEqual(queue.actual["ready"], 1)

    def test_unhealthy_node_indicator_is_error(self):
        sites = self.fixture_sites()
        sites["site2"]["nodes"][0]["resource_states"]["disk_space"] = "red"
        results = self.validate_sites(sites)
        disk = [
            result
            for result in results
            if result.check_id == "rabbitmq.node.disk_space" and result.site == "site2"
        ][0]
        self.assertEqual(disk.status, CheckStatus.ERROR)
        self.assertIn("unhealthy", disk.message)

    def test_missing_node_mapping_is_technical_error(self):
        sites = self.fixture_sites()
        del sites["site1"]["nodes"][0]["resource_states"]["file_descriptors"]
        results = self.validate_sites(sites)
        file_descriptors = [
            result
            for result in results
            if result.check_id == "rabbitmq.node.file_descriptors" and result.site == "site1"
        ][0]
        self.assertEqual(file_descriptors.status, CheckStatus.ERROR)
        self.assertEqual(
            file_descriptors.metadata["error_code"],
            "RABBITMQ_NODE_HEALTH_MAPPING_UNRESOLVED",
        )

    def test_collection_errors_remain_blocking_errors(self):
        actual = {
            "sites": {},
            "errors": [
                {
                    "site": "site1",
                    "code": "RABBITMQ_AUTHENTICATION_ERROR",
                    "message": "authentication failed",
                }
            ],
        }
        results = RabbitMQValidator().validate(actual, self.config, self.ctx)
        self.assertEqual(results[0].status, CheckStatus.ERROR)
        self.assertEqual(results[0].metadata["error_code"], "RABBITMQ_AUTHENTICATION_ERROR")

    def test_api_retry_and_queue_recheck_are_separate(self):
        config = copy.deepcopy(self.config)
        config["rabbitmq_expected"]["collection_mode"] = "live"
        config["rabbitmq_expected"]["sites"] = {"site1": {"required": True}}
        config["rabbitmq_expected"]["connections"] = {
            "site1": {
                "url_env": "RABBITMQ_SITE1_URL",
                "user_env": "RABBITMQ_SITE1_USER",
                "password_env": "RABBITMQ_SITE1_PASSWORD",
                "tls_verify": True,
                "timeout_seconds": 1,
                "retry_attempts": 2,
            }
        }
        config["rabbitmq_expected"]["queues"]["recheck"]["refresh_attempts"] = 1
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path == "/api/queues" and calls.count("/api/queues") == 1:
                return httpx.Response(502, json={"temporary": True})
            if request.url.path == "/api/queues" and calls.count("/api/queues") == 2:
                return httpx.Response(200, json=[_queue(messages_ready=1, messages=1)])
            if request.url.path == "/api/queues":
                return httpx.Response(200, json=[_queue()])
            if request.url.path == "/api/nodes":
                return httpx.Response(200, json=[_node()])
            return httpx.Response(404, json={"missing": True})

        with patch.dict(
            os.environ,
            {
                "RABBITMQ_SITE1_URL": "https://rabbitmq.invalid",
                "RABBITMQ_SITE1_USER": "fixture",
                "RABBITMQ_SITE1_PASSWORD": "fixture",
            },
        ):
            actual = RabbitMQCollector(transport=httpx.MockTransport(handler)).collect(
                RunContext(self.ctx.run_id, config, self.ctx.repository, self.ctx.evidence)
            )
        self.assertEqual(actual["errors"], [])
        queue = actual["sites"]["site1"]["queues"][0]
        self.assertEqual(queue["ready"], 0)
        self.assertEqual(queue["total"], 0)
        self.assertEqual(queue["checks_performed"], 2)
        self.assertEqual(calls.count("/api/queues"), 3)
        self.assertEqual(calls.count("/api/nodes"), 1)

    def test_empty_queue_response_is_collection_error(self):
        config = copy.deepcopy(self.config)
        config["rabbitmq_expected"]["collection_mode"] = "live"
        config["rabbitmq_expected"]["sites"] = {"site1": {"required": True}}
        config["rabbitmq_expected"]["connections"] = {
            "site1": {
                "url_env": "RABBITMQ_SITE1_URL",
                "user_env": "RABBITMQ_SITE1_USER",
                "password_env": "RABBITMQ_SITE1_PASSWORD",
                "tls_verify": True,
                "timeout_seconds": 1,
                "retry_attempts": 1,
            }
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/queues":
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[_node()])

        with patch.dict(
            os.environ,
            {
                "RABBITMQ_SITE1_URL": "https://rabbitmq.invalid",
                "RABBITMQ_SITE1_USER": "fixture",
                "RABBITMQ_SITE1_PASSWORD": "fixture",
            },
        ):
            actual = RabbitMQCollector(transport=httpx.MockTransport(handler)).collect(
                RunContext(
                    self.ctx.run_id,
                    config,
                    self.ctx.repository,
                    self.ctx.evidence,
                )
            )

        self.assertEqual(len(actual["errors"]), 1)
        self.assertEqual(
            actual["errors"][0]["code"],
            "RABBITMQ_INVALID_RESPONSE",
        )

    def test_empty_node_response_is_collection_error(self):
        config = copy.deepcopy(self.config)
        config["rabbitmq_expected"]["collection_mode"] = "live"
        config["rabbitmq_expected"]["sites"] = {"site1": {"required": True}}
        config["rabbitmq_expected"]["connections"] = {
            "site1": {
                "url_env": "RABBITMQ_SITE1_URL",
                "user_env": "RABBITMQ_SITE1_USER",
                "password_env": "RABBITMQ_SITE1_PASSWORD",
                "tls_verify": True,
                "timeout_seconds": 1,
                "retry_attempts": 1,
            }
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/queues":
                return httpx.Response(200, json=[_queue()])
            if request.url.path == "/api/nodes":
                return httpx.Response(200, json=[])
            return httpx.Response(404)

        with patch.dict(
            os.environ,
            {
                "RABBITMQ_SITE1_URL": "https://rabbitmq.invalid",
                "RABBITMQ_SITE1_USER": "fixture",
                "RABBITMQ_SITE1_PASSWORD": "fixture",
            },
        ):
            actual = RabbitMQCollector(transport=httpx.MockTransport(handler)).collect(
                RunContext(
                    self.ctx.run_id,
                    config,
                    self.ctx.repository,
                    self.ctx.evidence,
                )
            )

        self.assertEqual(len(actual["errors"]), 1)
        self.assertEqual(
            actual["errors"][0]["code"],
            "RABBITMQ_INVALID_RESPONSE",
        )


def _queue(*, messages_ready: int = 0, messages_unacknowledged: int = 0, messages: int = 0) -> dict:
    return {
        "vhost": "/",
        "name": "recording.events",
        "messages_ready": messages_ready,
        "messages_unacknowledged": messages_unacknowledged,
        "messages": messages,
    }


def _node() -> dict:
    return {
        "name": "rabbit@fixture1",
        "fd_used": 10,
        "fd_total": 1000,
        "sockets_used": 5,
        "sockets_total": 900,
        "proc_used": 100,
        "proc_total": 100000,
        "disk_free": 1000000000,
        "disk_free_limit": 50000000,
        "disk_free_alarm": False,
    }


if __name__ == "__main__":
    unittest.main()
