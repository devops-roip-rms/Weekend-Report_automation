from __future__ import annotations

import re
from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.base import Validator
from app.validators.engine import threshold_status


DF_RE = re.compile(r"^(?P<fs>\S+)\s+\S+\s+\S+\s+\S+\s+(?P<use>\d+)%\s+(?P<mount>\S+)")


def parse_df(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = DF_RE.match(line.strip())
        if match:
            rows.append({"filesystem": match.group("fs"), "utilization_percent": int(match.group("use")), "mountpoint": match.group("mount")})
    return rows


class InfrastructureValidator(Validator):
    def validate(self, actual: dict[str, Any], config: dict[str, Any], context: RunContext) -> list[CheckResult]:
        started = iso_now()
        results: list[CheckResult] = []
        expected_sites = config.get("servers", {}).get("sites", {})
        actual_sites = actual.get("sites", {})
        for site, site_expected in expected_sites.items():
            site_actual = actual_sites.get(site, {})
            server_outputs = site_actual.get("servers", {})
            for server in site_expected.get("servers", []):
                server_id = server["id"]
                outputs = server_outputs.get(server_id, {})
                if not outputs.get("reachable", True):
                    results.append(_r(context.run_id, "ssh.reachable", site, server_id, {"reachable": True}, outputs, CheckStatus.ERROR, "server unreachable", started))
                df_rows = parse_df(outputs.get("df", ""))
                by_mount = {row["mountpoint"]: row for row in df_rows}
                for fs in server.get("filesystems", []):
                    row = by_mount.get(fs["mountpoint"])
                    if not row:
                        results.append(_r(context.run_id, "filesystem.exists", site, server_id, fs, None, CheckStatus.FAIL, "expected filesystem missing", started))
                        continue
                    status = threshold_status(float(row["utilization_percent"]), float(fs["warning_percent"]), float(fs["critical_percent"]))
                    results.append(_r(context.run_id, "filesystem.utilization", site, server_id, fs, row, status, f"{row['mountpoint']} utilization {row['utilization_percent']}%", started))
                chrony = outputs.get("chrony", {})
                for ntp in server.get("chrony", []):
                    synced = bool(chrony.get("synchronized"))
                    status = CheckStatus.PASS if synced else CheckStatus.FAIL
                    results.append(_r(context.run_id, "chrony.synchronized", site, server_id, ntp, chrony, status, "chrony synchronized" if synced else "chrony unsynchronized", started))
                    offset = abs(float(chrony.get("offset", 999999)))
                    if synced:
                        status = threshold_status(offset, float(ntp["warning_offset"]), float(ntp["critical_offset"]))
                        results.append(_r(context.run_id, "chrony.offset", site, server_id, ntp, chrony, status, f"absolute offset {offset}", started))
        return results


def _r(run_id: str, check: str, site: str, target: str, expected: Any, actual: Any, status: CheckStatus, message: str, started: str) -> CheckResult:
    return CheckResult(run_id, "infrastructure", f"infrastructure.{check}", status, message, site=site, target=target, expected=expected, actual=actual, started_at=started, finished_at=iso_now())
