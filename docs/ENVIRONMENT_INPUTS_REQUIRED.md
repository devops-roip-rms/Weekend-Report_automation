# Environment Inputs Required

Production execution is blocked until the owner supplies and approves the values below. Unknown
facts must remain `<TBD>` or `<TO_VERIFY>`; required unresolved values fail preflight.

## Runtime And Secrets

- Non-committed `.env`, Docker secret, or approved secret mechanism.
- `POSTGRES_PASSWORD`.
- `WEEKEND_REPORT_APP_VERSION`.
- `WEEKEND_REPORT_BUILD_ID`.
- `WEEKEND_REPORT_AUTH_MODE=production`.
- `WEEKEND_REPORT_AUTH_PROVIDER`.
- `WEEKEND_REPORT_AUTH_TRUSTED_HEADER` if `trusted_header` is approved.
- `WEEKEND_REPORT_AUTHORIZED_REVIEWERS`.
- `WEEKEND_REPORT_CSRF_SIGNING_KEY`.
- Approved value for `WEEKEND_REPORT_CSRF_TTL_SECONDS` if default 3600 seconds is not accepted.

## Portainer

- Site 1 and Site 2 Portainer Server/API URLs.
- Approved auth type and secret env names/secret delivery.
- Endpoint/environment IDs.
- Portainer version and verified read-only API contract.
- TLS verification policy and CA file secret/env paths if custom CA is required.
- Approved connect/read timeouts and retry attempts/backoff.
- Common Swarm service inventory.
- Per-site service overrides, if any.
- Required/optional classification.
- Expected desired, running, and healthy replica counts.
- Verified health signal source/semantics.
- Expected image references and image comparison policy.
- Expected service state.
- Task state policy for `failed`, `rejected`, `restarting`, and `starting`.
- Portainer parity fields and explicitly allowed differences.

## RabbitMQ

- Site 1 and Site 2 Management API URLs.
- RabbitMQ username/password secret delivery.
- TLS verification and retry/timeout values.
- Common vhosts, queues, exchanges, and bindings.
- Per-site topology overrides, if any.
- Queue durability, auto-delete, exclusivity, minimum consumers.
- Backlog metric plus warning/critical thresholds.
- Node alarm policy and any explicitly approved optional topology.
- Parity behavior, if any stable RabbitMQ fields should be compared.

## Recording

Recording must use an existing device. Do not provide create/delete-device definitions.

- WebApp URL/auth/query contract for current recording count.
- WebApp device recording status query.
- Backend URL/auth/query contract for current recording count.
- Exact selection criteria for the first suitable existing non-recording device.
- Approved start-recording action for the selected existing device.
- Approved stop-recording action for the same selected device.
- Poll interval and timeout values.
- Expected behavior for no eligible existing device.
- Cleanup verification source and operator procedure.
- Recovery procedure for crash/unknown state after start.
- Explicit approval before any state-changing start/stop call is enabled.

## Database

The project provides an adapter boundary only. The owner-supplied existing sync function remains the
source of truth.

- Approved function reference to insert behind `app/executors/database_sync_test.py`.
- Source database identifier.
- Expected replica database identifiers.
- Temp table definition used by the existing function.
- Cleanup policy and timeout.
- Replication wait/timeout semantics.
- Required secret env names/secret delivery.
- Structured result mapping for create success, replication after create, delete success,
  replication after delete, cleanup complete, and errors.

## Infrastructure

- Server inventory for each site.
- SSH username/auth secret delivery.
- SSH host-key policy.
- Approved read-only commands for filesystem, NFS, and Chrony/NTP state.
- Filesystem mountpoints, warning thresholds, critical thresholds.
- NFS source, destination/mountpoint, usability/reachability expectations, thresholds.
- Expected Chrony/NTP source, sync behavior, warning/critical offset thresholds.
- Timezone expectations if they remain in scope.

## DOCTOR

- Manual review URL/instructions or approved API endpoint.
- Auth/secret delivery if API mode is used.
- API schema, expected values, and PASS/WARNING/FAIL/ERROR semantics if automated mode is used.
- Required reviewer note/acknowledgment policy.

## Splunk

- Dashboard IDs, display names, URLs, order.
- Which dashboards require review.
- Which dashboard notes are required before approval.
- Human review instructions.

## Review, Recovery, Evidence, Distribution

- Required module notes.
- Statuses requiring result notes.
- General-note policy.
- Manual-review acknowledgment policy.
- Recording cleanup acknowledgment policy.
- Approval policy for WARNING/FAIL/ERROR/SKIPPED/MANUAL_REVIEW.
- Reject policy.
- Stale-worker heartbeat timeout.
- Operator recovery instructions for `RECOVERY_REQUIRED`.
- Evidence root/storage, retention, backup, and restore policy.
- Archive/email enablement, destinations, recipients, failure behavior, and checksum policy.

## Optional Verification Inputs

- Disposable PostgreSQL URL for concurrency tests: `WEEKEND_REPORT_TEST_POSTGRES_URL`.
- Approved network access or offline vulnerability database for `pip-audit`.
- Future GitLab/Git commit traceability policy, if desired after import.
