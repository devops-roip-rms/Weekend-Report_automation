# Validation Catalog

Controlled placeholders (`<TBD>`, `<TO_VERIFY>`) are not production-ready. Required unresolved
values fail production preflight.

## Global Rules

- Config expected state lives in YAML.
- Collectors gather actual state or return a clear blocked/error payload.
- Validators make PASS/WARNING/FAIL/ERROR/SKIPPED/MANUAL_REVIEW decisions.
- Raw collector evidence and normalized result evidence are persisted with SHA-256 metadata.
- Parity is additive. It never converts site/module expected-state failures into PASS.
- Reviewer notes are additive. They never overwrite automated statuses.

## Portainer

### `portainer.collection`

- Actual source of truth: read-only HTTPS GETs to the configured Portainer Server/API.
- Expected source/value: `config/portainer_expected.yml` connection URL env, endpoint ID, auth,
  TLS, timeouts, retry policy, API contract.
- Comparison rule: verified read-only endpoints must return parseable service/task JSON.
- PASS: no separate collection PASS result is emitted when collection succeeds.
- WARNING/FAIL: not used.
- ERROR: auth, TLS, timeout, unsupported API, invalid JSON, malformed response, or unresolved
  required live configuration.
- Evidence: sanitized raw/error payload and normalized result evidence.
- Parity: collection errors are never converted into parity findings.

### `portainer.service.exists`

- Actual source of truth: normalized Swarm service names from Portainer/Docker.
- Expected source/value: effective common service inventory plus per-site overrides.
- Comparison rule: expected service name exists for the same site.
- PASS: service exists.
- WARNING: not used.
- FAIL: required service missing.
- ERROR: actual site state was not collected reliably.
- SKIPPED: optional service missing.
- Evidence: raw service list and normalized result.
- Parity: optional `service_presence` parity only after site validation.

### `portainer.service.desired_replicas`, `running_replicas`, `healthy_replicas`

- Actual source of truth: normalized Swarm service desired count, task running count, and verified
  health signal where available.
- Expected source/value: effective `expected.desired_replicas`, `expected.running_replicas`,
  `expected.healthy_replicas`.
- Comparison rule: desired/running equal expected; healthy is greater than or equal to expected.
- PASS: count satisfies expected value.
- WARNING: not used unless a future approved policy adds it.
- FAIL: reliable actual count does not satisfy expected value.
- ERROR: missing expected count, unavailable health signal when health is required, malformed
  response, or unreliable collection.
- Evidence: raw service/task JSON, normalized counts, health source/definition.
- Parity: optional per-field parity compares normalized values only.

### `portainer.service.image`

- Actual source of truth: normalized Swarm container image reference.
- Expected source/value: effective expected image reference and comparison policy.
- Comparison rule: `full_reference`, `repository_tag`, or `digest`.
- PASS: normalized image matches.
- WARNING: not used.
- FAIL: reliable mismatch.
- ERROR: unsupported comparison, malformed response, or unreliable collection.
- Evidence: raw service JSON and normalized image value.
- Parity: optional `image` parity compares actual image values only.

### `portainer.service.state`

- Actual source of truth: normalized service state/update metadata exposed by the verified API.
- Expected source/value: effective `expected.service_state`.
- Comparison rule: actual state equals expected state.
- PASS: state matches.
- WARNING: not used.
- FAIL: reliable mismatch.
- ERROR: malformed/unreliable collection.
- Evidence: raw service JSON and normalized state.
- Parity: optional `service_state` parity.

### `portainer.service.task_state`

- Actual source of truth: normalized Swarm task states and counts.
- Expected source/value: effective `expected.task_state_policy`.
- Comparison rule: `failed`, `rejected`, `restarting`, and `starting` are evaluated separately.
  Defaults are FAIL for failed/rejected/restarting and IGNORE for starting.
- PASS: no counted task state violates policy.
- WARNING: policy maps an observed state to WARNING.
- FAIL: policy maps an observed state to FAIL.
- ERROR: policy unresolved/invalid, or collection unreliable.
- Evidence: raw task JSON, normalized task states/counts, applied policy.
- Parity: not compared unless a future explicit parity field is added.

## RabbitMQ

### `rabbitmq.collection`

- Actual source of truth: RabbitMQ Management API fixture/live collector output.
- Expected source/value: `config/rabbitmq_expected.yml` collection mode and live connection fields.
- Comparison rule: actual site topology/metrics must be reliably collected.
- PASS: no separate collection PASS result on success.
- WARNING/FAIL: not used.
- ERROR: live collection blocked/unconfigured, API unavailable, malformed response.
- Evidence: raw/error payload and normalized result.
- Parity: collection errors are never hidden by topology parity.

### `rabbitmq.vhost.exists`, `queue.exists`, `exchange.exists`, `binding.exists`

- Actual source of truth: RabbitMQ Management API vhosts, queues, exchanges, bindings.
- Expected source/value: effective common topology plus per-site overrides.
- Comparison rule: required objects exist and match site/vhost/name/source/destination/routing key.
- PASS: object exists.
- WARNING: not used.
- FAIL: required object missing.
- ERROR: topology cannot be collected reliably.
- SKIPPED: explicitly optional object absent.
- Evidence: raw topology JSON and normalized result.
- Parity: stable topology parity only if explicitly configured.

### `rabbitmq.queue.*`, `rabbitmq.exchange.*`

- Actual source of truth: queue/exchange properties from Management API.
- Expected source/value: effective durability, auto-delete, exclusivity, type, consumers, backlog
  thresholds.
- Comparison rule: properties equal expected; consumers meet minimum; backlog uses thresholds.
- PASS: properties/metrics satisfy expected values.
- WARNING: backlog is in warning range.
- FAIL: property mismatch, consumers below minimum, or backlog at/above critical.
- ERROR: metric/property unavailable from unreliable collection.
- Evidence: queues/exchanges JSON and normalized result.
- Parity: dynamic backlog parity disabled unless explicitly approved.

### `rabbitmq.node.memory_alarm`, `rabbitmq.node.disk_alarm`

- Actual source of truth: RabbitMQ node alarm state.
- Expected source/value: no active memory or disk alarm.
- Comparison rule: alarm booleans must be false.
- PASS: not emitted when no alarm is active.
- WARNING: not used.
- FAIL: alarm active.
- ERROR: node state cannot be collected reliably.
- Evidence: node JSON and normalized result.
- Parity: not applicable.

## Recording

### Workflow Contract

- Actual source of truth: approved WebApp/backend/action adapters or fixture actuals.
- Expected source/value: `config/recording.yml` existing-device workflow.
- Comparison rule: no device create/delete. Select first suitable existing non-recording device,
  baseline WebApp count N and backend count M, start same device, require WebApp N+1/backend M+1,
  stop same device, require WebApp N/backend M restored, then cleanup verification.
- Evidence: selected device identity, baselines, action responses, poll results, cleanup state.
- Parity: none.

### Recording Subresults

Applies to:

- `recording.device_selection`
- `recording.webapp_baseline`
- `recording.backend_baseline`
- `recording.start_action`
- `recording.device_started`
- `recording.webapp_increment`
- `recording.backend_increment`
- `recording.stop_action`
- `recording.device_stopped`
- `recording.webapp_restored`
- `recording.backend_restored`
- `recording.cleanup`
- `recording.module_status`

Semantics:

- PASS: subresult succeeded and observed values match expected counts/state.
- WARNING: only if future approved policy explicitly maps a reliable condition to WARNING.
- FAIL: reliable bad behavior such as increment/restoration mismatch, wrong device recording state,
  failed start/stop action, or cleanup incomplete.
- ERROR: unreliable/unreachable/parse/unknown state, no approved live contract, no eligible device
  when policy is unresolved/error, or recovery required after unknown state.
- SKIPPED: only if an approved future no-eligible-device policy explicitly allows it.
- Evidence: raw action/poll evidence and normalized phase result.
- Recovery behavior: crash/unknown after start sets `RECOVERY_REQUIRED`; no automatic replay.

## Database

### `database.sync_execution`

- Actual source of truth: `app/executors/database_sync_test.py` adapter result.
- Expected source/value: approved existing sync function reference in `config/database.yml`.
- Comparison rule: adapter must return structured per-site results.
- PASS: not emitted separately on successful structured execution.
- WARNING/FAIL: not used for adapter startup.
- ERROR: approved function not supplied, function error, malformed result, unresolved live config.
- Evidence: adapter output/error payload and normalized result.
- Parity: not applicable.

### Database Structured Steps

Applies to:

- `database.create`
- `database.replication_after_create`
- `database.delete`
- `database.replication_after_delete`
- `database.cleanup`
- `database.module_status`

Semantics:

- Actual source of truth: owner-supplied existing function that creates a temp table, checks
  replication to expected DBs, deletes it, and checks deletion replication.
- Expected source/value: each structured boolean is expected to be true.
- Comparison rule: every mandatory boolean must be true.
- PASS: value is true.
- WARNING: non-blocking errors recorded while all booleans are true.
- FAIL: reliable false for create, replication, delete, or cleanup.
- ERROR: missing/unknown value or malformed structured result.
- Evidence: function evidence payload, target names, errors, normalized result.
- Parity: none unless future explicit database parity is approved.

## Infrastructure

### `infrastructure.collection`

- Actual source of truth: approved read-only SSH/command collectors or fixtures.
- Expected source/value: `config/servers.yml` server inventory and command contracts.
- Comparison rule: actual server outputs must be reliable and parseable.
- PASS: no separate PASS on successful collection.
- WARNING/FAIL: not used.
- ERROR: live SSH collection blocked/unconfigured, unreachable server, parse failure.
- Evidence: raw command output/error payload.
- Parity: collection failures remain independent.

### `infrastructure.filesystem.exists`, `filesystem.utilization`

- Actual source of truth: parsed `df` output.
- Expected source/value: configured filesystems, mountpoints, warning/critical thresholds.
- Comparison rule: required mount exists; utilization compared to thresholds.
- PASS: mount exists and utilization below warning.
- WARNING: utilization in warning range.
- FAIL: required mount missing or utilization at/above critical.
- ERROR: command/parse unavailable.
- Evidence: raw `df`, parsed rows, normalized result.
- Parity: missing mount never passes because another site matches.

### `infrastructure.nfs.exists`, `nfs.source`, `nfs.usable`, `nfs.utilization`

- Actual source of truth: configured NFS mount fixture/live parser and `df` fallback for
  `server:/path` filesystems.
- Expected source/value: configured NFS source, mountpoint/destination, usability, thresholds.
- Comparison rule: required NFS mount exists, source matches, mount is usable, utilization within
  thresholds.
- PASS: expected NFS state is present and healthy.
- WARNING: utilization in warning range.
- FAIL: required mount missing, source mismatch, unusable mount, or critical utilization.
- ERROR: actual NFS state cannot be determined reliably.
- Evidence: raw command output or fixture actual, normalized mount mapping.
- Parity: additive only if explicitly configured.

### `infrastructure.chrony.synchronized`, `chrony.source`, `chrony.offset`

- Actual source of truth: normalized `chronyc tracking` and `chronyc sources` output.
- Expected source/value: configured Chrony/NTP source and offset thresholds.
- Comparison rule: synchronized true, selected source matches expected, absolute offset within
  thresholds.
- PASS: synchronized/source/offset satisfy config.
- WARNING: offset in warning range.
- FAIL: unsynchronized, source mismatch, or critical offset.
- ERROR: command output missing/malformed/unreliable.
- Evidence: raw Chrony outputs and normalized `{synchronized, source, offset}`.
- Parity: additive only if explicitly configured.

## DOCTOR

- Actual source of truth: configured manual/API source.
- Expected source/value: `config/doctor.yml`.
- Comparison rule: manual mode emits `MANUAL_REVIEW`; future API mode must compare explicit
  expected status/schema.
- PASS/WARNING/FAIL: only for future approved API semantics.
- ERROR: invalid config/API failure.
- MANUAL_REVIEW: manual review required.
- Evidence: manual note/link or API payload.
- Parity: none unless explicitly approved.

## Splunk

- Actual source of truth: human review of configured dashboard URL.
- Expected source/value: `config/splunk_dashboards.yml`.
- Comparison rule: each configured dashboard requiring review must have a saved note before
  approval when policy requires it.
- MANUAL_REVIEW: dashboard awaits human review.
- ERROR: invalid dashboard definition or missing required note at finalization.
- Evidence: saved Splunk dashboard note and frozen snapshot entry.
- Parity: not applicable.

## Review, Evidence, Auth, Recovery, Reporting

### `review.note_ownership` and `review.note_editable_state`

- Actual source of truth: database runs/results/notes and configured dashboards/modules.
- Expected source/value: requested run/result/module/dashboard plus `rules.review`.
- Comparison rule: result belongs to run, dashboard exists, module is valid, general notes enabled,
  run state is `REVIEW_READY`.
- PASS: note accepted.
- ERROR: invalid ownership, disabled scope, wrong state.
- Evidence: persisted note row and frozen snapshot note.

### `review.final_confirmation` and `review.finalization_readiness`

- Actual source of truth: database results/notes, rules, configured dashboards, explicit reviewer
  APPROVE/REJECT.
- Expected source/value: `rules.review`, `rules.aggregation`, dashboard note requirements.
- Comparison rule: approval policy and required notes/acks must be satisfied before APPROVE.
- PASS: run moves to APPROVED/REJECTED and freezes snapshot/PDF.
- FAIL: configured status policy blocks approval.
- ERROR: missing required note/ack, invalid decision/state, snapshot/PDF failure.
- Evidence: frozen snapshot, final PDF path/checksum, note rows.

### `evidence.persistence`

- Actual source of truth: evidence filesystem and database evidence rows.
- Expected source/value: safe paths under `runs/<RUN_ID>/...`.
- Comparison rule: raw and normalized evidence are written under root with checksum metadata.
- PASS: evidence exists and path/checksum are recorded.
- ERROR: write failure, unsafe path, missing file, checksum/path validation failure.
- Evidence: evidence row itself.

### `auth.production_reviewer_identity` and `auth.browser_csrf`

- Actual source of truth: configured production auth provider and reviewer-bound CSRF tokens.
- Expected source/value: runtime auth/CSRF env vars.
- Comparison rule: production rejects arbitrary `X-Reviewer`; mutations require valid CSRF token.
- PASS: authorized reviewer access/mutation succeeds.
- FAIL: unauthorized reviewer rejected.
- ERROR: provider/signing configuration missing or invalid.
- Evidence: API responses and final reviewer metadata.

### `recovery.stale_worker` and `recovery.manual_resolution`

- Actual source of truth: database run state/current module/heartbeat.
- Expected source/value: `rules.recovery.heartbeat_timeout_seconds` and operator instructions.
- Comparison rule: stale non-Recording runs fail without replay; stale Recording runs enter
  `RECOVERY_REQUIRED` and block new runs until manual resolution.
- PASS: explicit recovery resolution unblocks future run without replay.
- ERROR: unresolved Recording recovery, invalid resolution, or blocked new run.
- Evidence: run state/current-module message and recovery note/API response.

### `reporting.final_pdf_access` and `runtime.portable_traceability`

- Actual source of truth: run metadata, frozen snapshot, evidence root final PDF.
- Expected source/value: `WEEKEND_REPORT_APP_VERSION`, `WEEKEND_REPORT_BUILD_ID`, config hash,
  run-owned final PDF path.
- Comparison rule: snapshot/PDF contain traceability; route serves only registered safe PDF path.
- PASS: metadata/path/checksum valid.
- ERROR: missing runtime identity, unsafe/missing PDF path, arbitrary path attempt.
- Evidence: frozen snapshot and final PDF checksum/path.

### `docker.runtime_secret_boundary`

- Actual source of truth: Docker Compose model and runtime env/secrets.
- Expected source/value: non-committed `.env`, Docker secret, or approved secret mechanism.
- Comparison rule: Compose must fail clearly for missing required secrets and must not use literal
  `<TBD>` as a runtime secret.
- PASS: Compose config renders only when required runtime values are supplied.
- ERROR: missing or placeholder runtime secret.
- Evidence: Compose config validation output and startup error where applicable.
