# Environment Inputs Required

**Documentation synchronized:** 2026-08-23

Production execution remains blocked until the owner supplies and approves the environment-specific values and policy decisions below.

Unknown required facts must remain:

```text
<TBD>
<TO_VERIFY>
<SERVICE_01>
<DASHBOARD_1_ID>
<VERIFY_AUTH_ENUM>
<TO_IMPLEMENT>
```

until verified.

## 1. Manager / Owner Decisions

The following are policy decisions, not implementation guesses:

- which modules are enabled;
- which modules are required;
- unavailable status per module;
- whether FAIL blocks approval;
- whether ERROR blocks approval;
- whether MANUAL_REVIEW blocks approval;
- whether SKIPPED blocks approval;
- WARNING overall behavior;
- result-note requirements;
- general-note requirements;
- manual-review acknowledgment;
- Recording cleanup acknowledgment;
- status-specific APPROVE policy;
- REJECT policy;
- parity mismatch policy;
- stale-worker heartbeat timeout;
- evidence retention;
- archive/email/distribution policy.

These should be approved internally before `config/rules.yml` is considered production-ready.

## 2. Site Definitions

Supply locally:

- Site 1 stable ID;
- Site 1 display name;
- Site 1 role/purpose;
- Site 2 stable ID;
- Site 2 display name;
- Site 2 role/purpose.

These values may remain organization-private. They do not need to be shared externally.

## 3. Runtime and Secrets

- non-committed `.env`, Docker secret, or approved secret mechanism;
- `WEEKEND_REPORT_IMAGE` such as `weekend-report:v1.0.2` after loading a verified release artifact;
- `POSTGRES_PASSWORD`;
- `WEEKEND_REPORT_APP_VERSION`;
- `WEEKEND_REPORT_BUILD_ID`;
- `WEEKEND_REPORT_AUTH_MODE=production`;
- `WEEKEND_REPORT_AUTH_PROVIDER`;
- `WEEKEND_REPORT_AUTH_TRUSTED_HEADER` if applicable;
- `WEEKEND_REPORT_AUTHORIZED_REVIEWERS`;
- `WEEKEND_REPORT_CSRF_SIGNING_KEY`;
- approved CSRF TTL if default is not accepted.

The release pipeline can derive app-version context from root `TAG`, but production runtime still needs explicit traceability values.

## 4. Portainer

For each site, supply locally:

- Portainer Server/API URL;
- auth type;
- secret env/secret-delivery method;
- endpoint/environment ID;
- Portainer version;
- verified read-only API contract;
- TLS verification policy;
- custom CA path/mount if required;
- connect timeout;
- read timeout;
- retry count/backoff;
- Swarm service inventory;
- required/optional services;
- desired replicas;
- running replicas;
- healthy replica expectations;
- health signal semantics;
- expected images;
- image comparison policy;
- expected service state;
- task-state policy;
- parity fields;
- allowed parity differences.

Do not place actual tokens in YAML/docs/chat.

## 5. RabbitMQ

- Management API URLs;
- user/password secret delivery;
- TLS verification;
- timeouts/retries;
- confirmation that all live queues should be checked;
- approved zero-count policy for ready/unacked/total messages;
- queue recheck attempts and delay;
- approved node resource-state mapping for file descriptors;
- approved node resource-state mapping for socket descriptors;
- approved node resource-state mapping for Erlang processes;
- approved node resource-state mapping for disk space.

## 6. Recording

Recording uses an existing device.

Required:

- Manager WebApp URL/auth/action contract;
- Manager existing-device selection contract;
- Site 1 WebApp read-only recording-count observation;
- Site 2 WebApp read-only recording-count observation;
- Site 1 server read-only recording-count observation;
- Site 2 server read-only recording-count observation;
- suitable existing-device selection criteria;
- approved start action;
- approved stop action;
- poll interval;
- timeout;
- no-eligible-device behavior;
- cleanup verification;
- operator recovery procedure;
- explicit approval before state-changing calls are enabled.

## 7. Database

- non-empty approved `scripts/database/database_sync_check.ps1`;
- verified PowerShell runtime and host environment;
- approved script arguments, if any;
- approved script timeout;
- source/replica/topology details owned inside the script contract;
- temp-table creation/deletion behavior owned inside the script contract;
- cleanup policy owned inside the script contract;
- structured result mapping returned to Weekend Report.

## 8. Infrastructure

- per-site server inventory;
- SSH username/auth delivery;
- SSH host-key verification policy;
- strict known-hosts file delivery;
- approved read-only commands;
- expected filesystems/mountpoints;
- warning/critical utilization;
- expected Chrony/NTP source;
- warning/critical clock offset;
- timezone expectations if applicable.

## 9. DOCTOR

- endpoint;
- authentication;
- schema;
- exactly 17 expected services;
- healthy/unhealthy/missing-service semantics;
- unhealthy reason field;
- manual-review acknowledgment instructions for reviewable health findings;
- transport/API/authentication/timeout/schema error semantics.

## 10. Splunk

- dashboard IDs;
- display names;
- URLs;
- order;
- required-review flags;
- note-required flags;
- human review instructions.

## 11. Evidence / Backup / Distribution

- production evidence root/storage;
- filesystem/volume ownership;
- retention;
- backup;
- restore;
- archival destination;
- email/distribution enablement;
- recipients;
- failure behavior;
- checksum policy.

## 12. CI / Delivery Environment Inputs

### GitHub

Only if registry publication is used:

- approved GHCR/package permission;
- `WEEKEND_REPORT_PUBLISH_IMAGE`;
- optional `WEEKEND_REPORT_PUBLISH_LATEST`.

No production integration credentials are required for standard quality/image CI.

### GitLab

After later GitLab import:

- compatible Runner;
- Docker/DinD or approved equivalent;
- package/audit source access;
- artifact size/retention;
- Container Registry enablement if desired;
- protected publication variables if registry push is approved.

## 13. PostgreSQL Concurrency

The local concurrency gate has already been exercised with a disposable PostgreSQL container during the Python 3.14 validation cycle.

For future manual reruns, provide:

```text
WEEKEND_REPORT_TEST_POSTGRES_URL
WEEKEND_REPORT_TEST_POSTGRES_DISPOSABLE=1
```

only for a disposable/test database.

Hosted CI definitions create their own disposable PostgreSQL 16 service.

This is no longer a missing production input; it is a test-environment input only.

## 14. Release Version

The release version is controlled by the root:

```text
TAG
```

Example:

```text
v1.0.2
```

No secret or environment-specific information belongs in this file.
