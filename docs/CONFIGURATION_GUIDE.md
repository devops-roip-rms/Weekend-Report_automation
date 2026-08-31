# Configuration Guide

**Documentation synchronized:** 2026-08-23

## 1. Configuration Principles

Use YAML for expected state and operational policy.

Use a non-committed `.env`, Docker secrets, or another approved secret mechanism for runtime secrets.

Never put credentials in:

- YAML;
- documentation;
- fixtures;
- `TAG`;
- Docker image layers;
- CI artifacts.

Controlled placeholders:

- `<TBD>`: required information not supplied.
- `<TO_VERIFY>`: candidate information not yet verified.
- `<NOT_APPLICABLE>`: intentionally not applicable only where the schema permits it.

The default `config/` directory is a production template and is intentionally invalid until all required values are completed.

`tests/fixtures/config_valid` is safe fixture-only configuration.

## 2. Python / Runtime Baseline

Current project baseline:

```text
Python 3.14
Docker: python:3.14-slim-bookworm
```

A local `.venv` may be used for development but must not be treated as deployment configuration.

## 3. Release Version vs Runtime Identity

The root:

```text
TAG
```

is the software-release/image-version source for CI image creation.

Example:

```text
v1.0.2
```

The release pipeline preserves the `v`.

Runtime/report traceability still records:

- `WEEKEND_REPORT_APP_VERSION`;
- `WEEKEND_REPORT_BUILD_ID`;
- deterministic configuration hash.

For images built through the release pipeline, `WEEKEND_REPORT_APP_VERSION` is derived from the validated `TAG` value during the build/smoke context.

For manual/local production deployment, supply a real `WEEKEND_REPORT_APP_VERSION` and `WEEKEND_REPORT_BUILD_ID` explicitly.

`WEEKEND_REPORT_GIT_COMMIT` is optional and must not be required when Git metadata is unavailable.

## 4. Authentication and CSRF

Production requires:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=<approved>
WEEKEND_REPORT_AUTHORIZED_REVIEWERS=<approved>
WEEKEND_REPORT_CSRF_SIGNING_KEY=<secret>
```

If using the implemented `trusted_header` provider, also configure:

```text
WEEKEND_REPORT_AUTH_TRUSTED_HEADER
```

Use trusted-header authentication only behind an approved reverse-proxy/authentication boundary.

Production rejects arbitrary `X-Reviewer`.

Browser mutations require reviewer-bound signed CSRF tokens.

## 5. Rules

`config/rules.yml` controls:

- module enablement;
- required/optional modules;
- unavailable status;
- aggregation;
- parity;
- note requirements;
- APPROVE status policy;
- REJECT policy;
- stale-worker/recovery timeout.

Do not let reviewer approval rewrite automated findings.

ERROR, FAIL, SKIPPED, and MANUAL_REVIEW are never silently converted into PASS.

Global approval and failure semantics must be owner/manager-approved; Codex/automation must not invent them.

## 6. Site Definitions

`config/sites.yml` defines the real site IDs/display names/purpose.

Site IDs must match references in all module configuration files.

Do not use duplicate placeholder IDs in a production-ready config.

Real site names/IDs may remain private to the organization and do not need to be shared externally; they only need to be supplied locally to the project before production preflight can pass.

## 7. Portainer

`config/portainer_expected.yml` supports:

- `collection_mode: fixture|live`;
- common defaults;
- common service inventory;
- per-site overrides;
- per-site live connection settings.

Expected config contains expected state only.

Actual state comes from the collector.

Live values include:

- URL env reference;
- auth/secret reference;
- Portainer/API contract;
- endpoint/environment ID;
- TLS verification/CA;
- connect/read timeouts;
- retry policy;
- service inventory;
- desired/running/healthy replicas;
- image policy;
- service/task-state policy;
- parity fields/exceptions.

Portainer is read-only.

## 8. RabbitMQ

`config/rabbitmq_expected.yml` supports:

- `collection_mode: fixture|live`;
- Management API connections;
- all-queue count validation;
- configured queue recheck attempts/delay;
- expected zero values for ready/unacked/total counts;
- all-node resource-state validation;
- per-site required flags.

Expected queue-count and node-health policy belongs in YAML.

Actual queues, node resources, recheck snapshots, and Management API errors belong to collector output/evidence.

## 9. Recording

Recording uses an existing-device workflow only.

Do not configure device create/delete.

Approved live configuration must define:

- Manager WebApp URL/auth/action contract;
- Site 1 WebApp read-only count observation;
- Site 2 WebApp read-only count observation;
- Site 1 server read-only count observation;
- Site 2 server read-only count observation;
- suitable-device selection;
- start action;
- stop action;
- polling;
- cleanup verification;
- no-eligible-device policy;
- human recovery procedure.

Unknown state after a state-changing operation requires `RECOVERY_REQUIRED`.

## 10. Database

`config/database.yml` defines the adapter contract for the owner-supplied existing PowerShell synchronization script.

The checked-in script path is:

```text
scripts/database/database_sync_check.ps1
```

An empty script is a production blocker because runtime, arguments, exit-code semantics, cleanup behavior, and structured result mapping cannot be verified.

The adapter must return structured results for:

- create;
- replication after create;
- delete;
- replication after delete;
- cleanup;
- errors.

Do not invent exit-code semantics or rewrite the owner algorithm.

## 11. Infrastructure

`config/servers.yml` defines:

- server inventory;
- SSH policy;
- filesystems;
- Chrony/NTP expected state;
- thresholds.

Live SSH remains blocked until targets, credentials, strict known-host verification, and read-only commands are approved.

## 12. DOCTOR

Current `config/doctor.yml` is API mode and expects exactly 17 services per site.

API mode requires a verified endpoint/schema/auth/status contract.

If live API schema/auth is not verified, the live adapter remains blocked and normalized contract fixtures/tests are the only safe execution path.

Reviewable service-health findings may roll the DOCTOR module to `MANUAL_REVIEW`; the underlying service-level `ERROR` remains unchanged in evidence/reporting.

## 13. Splunk

`config/splunk_dashboards.yml` defines dashboard review metadata.

Each dashboard can define:

- ID;
- name;
- URL;
- order;
- required review;
- required note.

No secret should be stored in a dashboard URL.

## 14. Review / Finalization

Notes are ownership-validated.

Final confirmation:

- validates configured readiness;
- freezes all persisted notes;
- preserves automated statuses;
- freezes traceability;
- creates one immutable snapshot;
- renders one final PDF from that snapshot.

## 15. Docker Runtime Values

`.env.example` and `deploy/docker/.env.example` are templates only.

Compose must not run production using literal:

```text
<TBD>
<TO_VERIFY>
<SERVICE_01>
<DASHBOARD_1_ID>
<VERIFY_AUTH_ENUM>
<TO_IMPLEMENT>
UNKNOWN
```

as credentials or runtime identity.

At minimum, production requires real:

- verified application image selector through `WEEKEND_REPORT_IMAGE`;
- PostgreSQL secret;
- app version;
- build ID;
- auth configuration;
- CSRF signing secret;
- integration secrets for enabled live modules.

For a verified release, set `WEEKEND_REPORT_IMAGE` to the loaded release tag, for example
`weekend-report:v1.0.2`. Do not run production Compose with literal controlled placeholders as
runtime values.

## 16. CI Configuration Is Not Production Configuration

CI uses:

- fixture YAML;
- disposable PostgreSQL;
- CI-only credentials;
- safe local evidence.

The release version comes from `TAG`.

Production integration values must not be inserted into CI merely to make pre-image gates pass.

## 17. Validation Commands

Fixture + expected-invalid template gate:

```powershell
python scripts/ci.py config
```

Production-ready config, when intentionally completed:

```powershell
python scripts/validate_config.py --config config
```

Never replace unknown production facts with guesses just to make this command green.
