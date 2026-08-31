# Validation Catalog

**Documentation synchronized:** 2026-08-23

Controlled placeholders (`<TBD>`, `<TO_VERIFY>`) are not production-ready.

Required unresolved values fail production preflight.

## 1. Global Rules

- Expected state lives in YAML.
- Secrets live outside YAML.
- Collectors gather actual state or return a clear blocked/error payload.
- Validators produce `PASS`, `WARNING`, `FAIL`, `ERROR`, `SKIPPED`, or `MANUAL_REVIEW`.
- Raw/normalized evidence is persisted with checksum metadata.
- Cross-site parity is additive and never masks expected-state failures.
- Reviewer notes are additive and never rewrite automated statuses.
- `config/rules.yml` is authoritative for aggregation and approval readiness.
- CI fixture success does not mean production integration is configured.

## 2. Configuration / Runtime Identity

### `config.preflight`

Actual:
- loaded YAML;
- referenced runtime values;
- schema/reference integrity.

Expected:
- all required enabled values resolved;
- controlled placeholders absent where production requires real values;
- valid site/module references.

PASS:
- production-ready config resolves cleanly.

ERROR:
- unresolved required placeholders;
- invalid enum/reference;
- missing required runtime secret/reference.

Evidence:
- preflight diagnostics.

### `runtime.traceability`

Actual:
- `WEEKEND_REPORT_APP_VERSION`;
- `WEEKEND_REPORT_BUILD_ID`;
- configuration hash;
- optional Git commit.

Expected:
- real app version/build ID in production;
- deterministic config hash.

PASS:
- all mandatory values present.

ERROR:
- missing/placeholder production identity.

## 3. Portainer

### `portainer.collection`

Actual source:
- read-only HTTPS GET to configured Portainer Server/API.

Expected:
- connection URL env reference;
- auth;
- endpoint ID;
- API contract;
- TLS;
- timeout/retry.

PASS:
- no separate collection PASS required.

ERROR:
- auth/TLS/timeout/unsupported API/invalid JSON/malformed response/unresolved required live config.

Evidence:
- sanitized raw/error payload;
- normalized state.

### `portainer.service.exists`

PASS:
- required service exists.

FAIL:
- required service absent.

SKIPPED:
- explicitly optional service absent.

ERROR:
- site state was not collected reliably.

### `portainer.service.desired_replicas`

PASS:
- actual desired equals expected desired.

FAIL:
- reliable mismatch.

ERROR:
- missing/unreliable data.

### `portainer.service.running_replicas`

PASS:
- running equals configured expectation.

FAIL:
- reliable mismatch.

ERROR:
- unreliable count.

### `portainer.service.healthy_replicas`

PASS:
- healthy count satisfies expectation.

FAIL:
- reliable healthy-count shortfall.

ERROR:
- health signal unavailable/unverified when required.

### `portainer.service.image`

Comparison policy:
- `full_reference`;
- `repository_tag`;
- `digest`.

PASS:
- configured match.

FAIL:
- reliable mismatch.

ERROR:
- unsupported comparison/unreliable collection.

### `portainer.service.state`

PASS:
- actual service state equals expected.

FAIL:
- reliable mismatch.

ERROR:
- malformed/unreliable state.

### `portainer.service.task_state`

Evaluate independently:

- failed;
- rejected;
- restarting;
- starting.

Configured policy decides WARNING/FAIL/IGNORE as approved.

Unresolved policy is ERROR/preflight-blocking.

### Portainer parity

Parity runs after site validation.

Both sites being identically unhealthy must not become PASS because they match each other.

## 4. RabbitMQ

### `rabbitmq.collection`

Actual:
- read-only RabbitMQ Management API or fixture actuals.

ERROR:
- configuration/runtime value missing;
- authentication/TLS/timeout/API unavailable;
- malformed response.

Evidence:
- sanitized Management API error payloads;
- queue snapshots;
- node resource payloads.

### `rabbitmq.queue.counts`

Actual:
- observed live queues;
- `ready`;
- `unacked`;
- `total`;
- recheck snapshots/check count.

Expected:
- all observed queues have zero ready/unacked/total messages after configured rechecks.

PASS:
- all counts are zero.

ERROR:
- queue count is missing/malformed;
- any count remains non-zero after configured rechecks unless policy explicitly changes the status.

### `rabbitmq.node.file_descriptors`
### `rabbitmq.node.socket_descriptors`
### `rabbitmq.node.erlang_processes`
### `rabbitmq.node.disk_space`

Expected:
- configured resource state is `green`.

PASS:
- collected resource state is `green`.

ERROR:
- collected state is non-green under current policy;
- required green-state mapping is unavailable.

## 5. Recording

### Workflow contract

No device creation/deletion.

Expected sequence:

```text
baseline
-> select existing non-recording device
-> start same device
-> verify increment/state
-> stop same device
-> verify restoration
-> cleanup
```

Subresults include:

- device selection;
- pre-start verification;
- four baselines;
- start action;
- four after-start observations;
- stop action;
- four after-stop observations;
- cleanup;
- module status.

PASS:
- reliable expected transition.

FAIL:
- reliable bad behavior/mismatch before cleanup risk is introduced.

ERROR:
- unreliable state/unreachable/parse/unknown state;
- live contract not approved;
- cleanup failure;
- recovery required.

SKIPPED:
- only if explicitly approved policy allows it.

Unknown state after a state-changing action:

```text
RECOVERY_REQUIRED
```

No automatic replay.

## 6. Database

### `database.sync_execution`

Actual:
- owner-supplied PowerShell script adapter result.

ERROR:
- script missing/empty;
- script runtime/result contract unverified;
- script exception;
- malformed result;
- unresolved live config.

### Structured steps

Expected true:

- create success;
- replication after create;
- delete success;
- replication after delete;
- cleanup complete.

PASS:
- true.

FAIL:
- reliable false.

ERROR:
- missing/unknown/malformed.

WARNING:
- only for explicitly non-blocking errors while required booleans remain true.

## 7. Infrastructure

### Collection

ERROR:
- SSH live mode unconfigured;
- unreachable;
- command/parse failure.

### Filesystem

PASS:
- mount exists and utilization below warning.

WARNING:
- warning range.

FAIL:
- required mount missing or utilization >= critical.

ERROR:
- actual state unavailable.

### Chrony

PASS:
- synchronized;
- expected source;
- offset below warning.

WARNING:
- warning offset range.

FAIL:
- unsynchronized/source mismatch/critical offset.

ERROR:
- output unavailable/malformed.

## 8. DOCTOR

API mode expects exactly 17 services per site.

### `doctor.collection`

ERROR:
- transport/API/authentication/timeout/schema/collection failure;
- malformed site payload.

### `doctor.service.health`

PASS:
- expected service is present and healthy.

ERROR:
- expected service is unhealthy;
- expected service is missing;
- health state is unknown/unparseable.

Only explicitly marked unhealthy/missing service-health findings are reviewable health issues.

### `doctor.module_status`

PASS:
- all 17 expected services are healthy on both sites.

MANUAL_REVIEW:
- one or more service-level health findings are reviewable health issues.

ERROR:
- any technical/transport/API/authentication/timeout/schema/collection error exists.

The underlying `doctor.service.health` `ERROR` remains recorded as `ERROR` in evidence and reporting.

## 9. Splunk

Actual:
- persisted human dashboard review state.

Expected:
- configured dashboard definitions/review-note policy.

MANUAL_REVIEW:
- dashboard awaits human review.

Finalization ERROR/block:
- required dashboard review/note missing according to policy.

Evidence:
- saved dashboard review acknowledgment and note in database/snapshot.

Opening a dashboard URL is not review completion.

## 10. Review / Finalization

### `review.note_ownership`

Validate:

- result belongs to run;
- dashboard exists;
- module valid;
- general notes enabled if used;
- run is editable.

ERROR:
- ownership/state/scope violation.

### `review.finalization_readiness`

Before APPROVE enforce configured:

- required module completion;
- dashboard review;
- required notes;
- manual-review acknowledgments;
- Recording cleanup acknowledgment;
- status-specific approval policy.

Narrow DOCTOR finalization exception:

- a `doctor.service.health` `ERROR` may be excluded from the `ERROR: BLOCK` finalization count only when it is explicitly marked as a reviewable health issue;
- the same result set contains `doctor.module_status=MANUAL_REVIEW`;
- the reviewer has saved the required acknowledgment/note on that module-level manual-review result.

This exception does not apply to DOCTOR transport/API/authentication/timeout/schema/collection errors, configuration errors, infrastructure errors, RabbitMQ errors, Recording errors, Database errors, Portainer errors, or any unrelated `ERROR`.

FAIL:
- explicit status policy blocks approval.

ERROR:
- required note/ack/state missing;
- snapshot/PDF failure.

### Automated-status immutability

Reviewer acceptance never changes machine:

```text
WARNING -> PASS
FAIL -> PASS
ERROR -> PASS
```

Automated status and reviewer decision remain separate facts.

## 11. Evidence

### `evidence.persistence`

PASS:
- safe run-owned path;
- file exists;
- checksum metadata recorded.

ERROR:
- unsafe path;
- write failure;
- missing file;
- checksum/path validation failure.

Raw evidence must be sanitized of known credentials/tokens.

## 12. Auth / CSRF

### `auth.production_reviewer_identity`

PASS:
- authorized reviewer resolved through approved provider.

FAIL:
- unauthorized reviewer.

ERROR:
- missing/invalid provider configuration.

### `auth.browser_csrf`

PASS:
- reviewer-bound signed token valid.

FAIL:
- invalid/expired/mismatched token.

ERROR:
- signing configuration missing.

## 13. Recovery

### `recovery.stale_worker`

Non-Recording stale:
- fail without replay.

Recording stale/uncertain:
- `RECOVERY_REQUIRED`.

### `recovery.manual_resolution`

PASS:
- explicit safe human resolution completed;
- new run unblocked without replaying uncertain state-changing call.

ERROR:
- unresolved/invalid recovery.

## 14. Reporting

### `reporting.final_pdf_access`

PASS:
- route serves recorded run-owned final PDF;
- safe path;
- authorized access.

ERROR:
- unsafe/missing/arbitrary path.

### `reporting.snapshot_completeness`

PASS:
- all persisted notes represented;
- results/evidence/summaries/traceability represented.

ERROR:
- completeness mismatch.

## 15. Docker Runtime

### `docker.runtime_secret_boundary`

PASS:
- Compose receives real required runtime values.

ERROR:
- required secret missing;
- literal controlled placeholder used as runtime secret.

### `docker.exact_image_smoke`

Actual:
- supplied `WEEKEND_REPORT_CI_IMAGE`.

Expected:
- PostgreSQL healthy;
- web running;
- worker running;
- `/healthz` OK;
- migration/access succeeds.

PASS:
- exact image passes all checks.

ERROR/FAIL:
- any required container/health/migration check fails.

Important:
`compose.ci.yml` must not rebuild a different image.

## 16. CI / Release Validation

### `ci.pre_image_quality`

Required gates:

- config;
- Ruff;
- Mypy;
- unit;
- contract;
- integration;
- PostgreSQL concurrency;
- safe E2E;
- dependency audit;
- Compose validation.

PASS:
- every required gate succeeds.

FAIL:
- any gate fails.

Effect:
- image build must not start.

### `ci.postgres_concurrency`

PASS:
- simultaneous create protected;
- single worker claim protected.

FAIL:
- race/concurrency invariant broken.

Must use disposable PostgreSQL.

### `ci.release_tag_file`

Actual:
- root `TAG` content.

Expected:
- one semantic-style version with leading `v`.

PASS example:

```text
v1.0.2
```

ERROR:
- file missing;
- malformed;
- empty;
- release workflow derives version from Git tag instead.

GitHub must not require `GITHUB_REF_NAME` for release version.

GitLab must not require `CI_COMMIT_TAG` for release version.

### `ci.release_trigger`

Normal source change:

```text
quality only
```

TAG change on configured release/default branch:

```text
quality -> image
```

FAIL:
- normal source-only commit builds release image;
- TAG change bypasses required quality gates.

### `ci.image_delivery`

Required sequence:

```text
build exact image
-> record identity
-> smoke exact image
-> tag same image as weekend-report:<TAG>
-> verify image IDs match
-> export weekend-report:<TAG>
-> optional push same image
```

FAIL:
- export/publish happens before smoke;
- exported archive contains only the CI tag instead of weekend-report:<TAG>;
- release tag does not point to the same image ID as the smoked CI tag;
- a different image is rebuilt after smoke;
- smoke failure still permits release.

### `ci.secret_boundary`

PASS:
- only disposable/test credentials;
- no production integration secrets in CI definitions/artifacts.

FAIL:
- production secret names/values are embedded where forbidden.

## 17. Release Artifact

Verified artifact contains:

```text
weekend-report_<TAG-version>_<short-sha>.tar.gz
weekend-report_<TAG-version>_<short-sha>.tar.gz.sha256
image-id.txt
```

The SHA-256 must be verified after offline transfer before loading/deployment.
