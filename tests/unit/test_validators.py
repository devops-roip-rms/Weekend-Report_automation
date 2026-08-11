from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from app.config.loader import load_config_dir
from app.database.repository import Repository
from app.domain import CheckStatus
from app.evidence.manager import EvidenceManager
from app.orchestrator.run_context import RunContext
from app.validators.infrastructure import InfrastructureValidator
from app.validators.portainer import PortainerValidator
from app.validators.rabbitmq import RabbitMQValidator


class ValidatorTests(unittest.TestCase):
    def context(self, config):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return RunContext("WR-20260811-000000", config, Repository("sqlite:///:memory:"), EvidenceManager(Path(tmp.name)))

    def test_portainer_parity_does_not_mask_failed_health(self):
        config = load_config_dir("tests/fixtures/config_valid")
        actual = copy.deepcopy(config["portainer_expected"]["fixture_actual"])
        actual["site1"]["services"][0]["running_replicas"] = 2
        actual["site2"]["services"][0]["running_replicas"] = 2
        results = PortainerValidator().validate({"sites": actual}, config, self.context(config))
        replica_statuses = [r.status for r in results if r.check_id == "portainer.service.replicas"]
        self.assertEqual(replica_statuses, [CheckStatus.FAIL, CheckStatus.FAIL])

    def test_rabbitmq_threshold_boundaries_and_missing_queue(self):
        config = load_config_dir("tests/fixtures/config_valid")
        ctx = self.context(config)
        actual = copy.deepcopy(config["rabbitmq_expected"]["fixture_actual"])
        actual["site1"]["queues"][0]["messages"] = 10
        actual["site2"]["queues"] = []
        results = RabbitMQValidator().validate({"sites": actual}, config, ctx)
        self.assertIn(CheckStatus.WARNING, [r.status for r in results if r.check_id == "rabbitmq.queue.backlog"])
        self.assertIn(CheckStatus.FAIL, [r.status for r in results if r.check_id == "rabbitmq.queue.exists"])

    def test_infrastructure_missing_mount_and_chrony_unsynced(self):
        config = load_config_dir("tests/fixtures/config_valid")
        actual = copy.deepcopy(config["servers"]["fixture_actual"])
        actual["sites"]["site1"]["servers"]["srv1"]["df"] = "Filesystem Size Used Avail Use% Mounted on\n/dev/sdb1 10G 1G 9G 10% /data"
        actual["sites"]["site2"]["servers"]["srv2"]["chrony"]["synchronized"] = False
        results = InfrastructureValidator().validate(actual, config, self.context(config))
        self.assertIn(CheckStatus.FAIL, [r.status for r in results])


if __name__ == "__main__":
    unittest.main()
