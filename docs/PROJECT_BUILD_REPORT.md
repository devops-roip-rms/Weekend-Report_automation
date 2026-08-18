# Project Build Report

Date: 2026-08-18

Scope: core framework hardening, operational-model correction, and professional UI/UX redesign.
This pass did not start production integrations, did not execute real Recording state-changing
calls, and did not perform Git operations.

## What Changed

- Added shared expected-configuration resolution in `app/config/effective.py` for Portainer common
  service inventory/defaults/per-site overrides and RabbitMQ common topology/defaults/per-site
  overrides.
- Refactored Portainer config templates and fixtures to remove duplicated per-site service lists.
  Required services default to `true`; optional services must be explicit.
- Updated Portainer task-state semantics so `failed`, `rejected`, `restarting`, and `starting` are
  distinct. `starting` is policy-controlled and is not treated as permanently unhealthy by default.
- Refactored RabbitMQ config templates and fixtures to use common vhost/queue/exchange/binding
  topology with overrides and explicit optional topology behavior.
- Replaced the Recording synthetic create/delete model with an existing-device start/stop workflow:
  baseline WebApp/backend counts, select existing non-recording device, start same device, verify
  increments, stop same device, verify restoration, cleanup/recovery.
- Added structured Recording subresults for device selection, baselines, start/stop actions,
  WebApp/backend increments/restoration, cleanup, and module status.
- Added `config/database.yml`, `tests/fixtures/config_valid/database.yml`, and
  `app/executors/database_sync_test.py` as an adapter boundary for the owner-supplied existing
  database sync function. The temp-table algorithm is not rewritten in this project.
- Replaced database exit-code validation with structured create/replicate/delete/replicate/cleanup
  result validation.
- Added Chrony parser boundary for `chronyc tracking` and `chronyc sources`, plus NFS mount source,
  existence, usability, and utilization validation.
- Kept fixture mode explicit and blocked live collectors when required environment contracts are
  unknown. No silent live-to-fixture fallback was added.
- Preserved review/evidence/finalization hardening from earlier work: additive reviewer notes,
  ownership validation, frozen snapshots, final PDF from the snapshot only, production auth boundary,
  CSRF protection, row-lock/atomic run semantics, and stale-worker recovery.
- Redesigned the FastAPI/Jinja web UI into a consistent operations dashboard shell with a top
  header, persistent module navigation, responsive content area, cards/panels, professional status
  badges, and clear primary/secondary actions.
- Rebuilt the run overview around summary-first information: RUN_ID, run state, automation status,
  site summaries, module summaries, PASS/WARNING/FAIL/ERROR/MANUAL_REVIEW counts, important
  findings, timestamps, current-module information, and reviewer/final-decision metadata.
- Replaced raw wide module tables with readable result cards showing Check/Status/Expected/Actual/
  Message, evidence links, reviewer notes, and expandable technical details.
- Added module-specific UI presentations: two-site Portainer service comparison, RabbitMQ Queues/
  Exchanges/Bindings/Node Alarms sections, existing-device Recording workflow steps, and
  server-oriented Infrastructure panels.
- Reworked Splunk review into dashboard cards with `OPEN ALL DASHBOARDS`, per-dashboard reviewer
  notes, save/reload controls, and persisted-note display.
- Reworked the Review page into summary-first grouped panels for findings, module notes, result
  notes, Splunk notes, general notes, and final decision. Final confirmation now has visually
  distinct APPROVE/REJECT choices, an explicit second confirmation step, and a clear immutable
  findings warning.
- Replaced browser-native alert feedback with accessible inline status and toast messages in
  `app/web/static/app.js`.
- Added UI regression tests for summary-first rendering, specialized module layouts, Splunk cards,
  explicit final confirmation, no raw tables, and no `alert(` usage.

## Current Project Structure

- `app/api/`: FastAPI routes for runs, notes, review, reports, evidence, and health.
- `app/auth.py`: development vs production reviewer identity and CSRF boundary.
- `app/collectors/`: fixture/live collection boundaries for modules.
- `app/config/`: config loading, schema constants, effective common-config resolution, preflight.
- `app/database/`: migrations, models, repository, run locks, notes, evidence metadata.
- `app/evidence/`: safe evidence paths, checksum writes, metadata models.
- `app/executors/`: command/SSH/browser/database adapter boundaries.
- `app/orchestrator/`: execution plan, worker runner, aggregation, run context, locks.
- `app/reporting/`: frozen HTML/snapshot rendering and final multi-page PDF generation.
- `app/review/`: note ownership and finalization readiness policy.
- `app/validators/`: module validators and site parity validator.
- `app/web/`: HTML templates, shared Jinja UI macros, CSS, and browser JavaScript for review/
  finalization.
- `app/worker/`: worker loop, heartbeat, stale-run recovery.
- `config/`: production templates with controlled placeholders.
- `deploy/docker/`: Docker Compose files and deployment notes.
- `docs/`: architecture, configuration, validation, recovery, deployment, and this report.
- `scripts/`: config validation and local smoke helpers.
- `tests/fixtures/config_valid/`: safe fixture configuration.
- `tests/unit/`, `tests/integration/`: local quality suite.

## Tests And Checks

- PASS: `python scripts/validate_config.py --config tests/fixtures/config_valid`.
- PASS: `python scripts/validate_config.py --config config --expect-invalid`.
  - Production templates remain intentionally invalid until required `<TBD>` and `<TO_VERIFY>`
    values are supplied.
- PASS: `python -m unittest discover -s tests -v`.
  - Result: 75 tests passed, 2 skipped.
  - Skipped: PostgreSQL concurrency tests because `WEEKEND_REPORT_TEST_POSTGRES_URL` is not set.
- PASS: `python -m ruff check . --no-cache`.
- PASS: `python -m mypy app tests`.
- PASS: `pip-audit -r requirements.txt --cache-dir <writable-cache>`.
  - Result: no known vulnerabilities found.
  - Required approved network/index access after the default cache directory was not writable.
- PASS: Headless Edge visual inspection of `/`, run overview, Portainer, DOCTOR, RabbitMQ,
  Recording, Infrastructure, Database, Splunk, Review, Review final-confirmation area, and mobile
  Overview/Review screenshots.
  - Corrected two responsive metric-grid issues found during visual inspection.
  - The in-app browser connector failed during setup with a missing kernel-assets path, so local
    headless Edge screenshots were used for visual QA.

## Docker Results

- PASS: `docker compose -f deploy/docker/compose.yml config` with disposable validation values.
- PASS: `docker build -t weekend-report:ui-validation .` after approved Docker daemon access.
- PASS: safe Compose smoke with `postgres` and `web` only, no worker, using `--build` against the
  final source state.
  - `GET http://localhost:8080/healthz` returned `{"status":"ok"}`.
  - `docker compose ... ps` showed PostgreSQL healthy and web up.
  - Teardown succeeded with `docker compose -p weekend-report-ui-smoke ... down -v`.
  - Follow-up `docker ps` showed no `weekend-report-ui-smoke` containers.

## Remaining Controlled Placeholders

Across `config/`, `.env.example`, and `deploy/docker/env.example`:

- `<TBD>`: 234
- `<TO_VERIFY>`: 11

Selected production templates:

- `config/portainer_expected.yml`: 18 `<TBD>`, 8 `<TO_VERIFY>`
- `config/rabbitmq_expected.yml`: 29 `<TBD>`, 0 `<TO_VERIFY>`
- `config/recording.yml`: 20 `<TBD>`, 2 `<TO_VERIFY>`
- `config/database.yml`: 7 `<TBD>`, 1 `<TO_VERIFY>`

## Still Awaiting Environment Information

- Portainer URLs, auth method, tokens/secret mechanism, TLS policy, endpoint IDs, API contract,
  service inventory, expected replicas/health/images/state, task-state policy, and parity rules.
- RabbitMQ Management API URLs, users/passwords, TLS/retry policy, common topology, per-site
  overrides, thresholds, and alarm policy.
- Recording WebApp/backend query/action contracts, auth, polling values, cleanup verification,
  no-eligible-device policy, and explicit approval for any state-changing start/stop calls.
- Database approved existing sync function binding, source/replica identifiers, temp table
  definition, cleanup policy, timeouts, and secret delivery.
- Infrastructure SSH targets, approved read-only commands, host-key policy, filesystem/NFS/Chrony
  expected values and thresholds.
- DOCTOR API/manual source, Splunk dashboard definitions, production auth provider, reviewer
  authorization list/group, CSRF signing key delivery, evidence storage/retention, archive/email
  policies, and stale-worker timeout.

## Known Limitations

- No real production systems were contacted.
- Recording live execution is intentionally blocked until the existing-device start/stop contracts
  are supplied and approved.
- Database live execution raises a clear adapter-not-provided error until the owner inserts the
  approved existing sync function behind `app/executors/database_sync_test.py`.
- PostgreSQL concurrency tests are not verified without a disposable PostgreSQL URL.
- `pip-audit` is not verified because network audit access was blocked.
- `.env.example` and `deploy/docker/env.example` remain templates only. They must not be used as
  runtime secret files.

## Exact Next Inputs Needed

1. Approved production auth provider and reviewer authorization source.
2. Real non-committed runtime secret delivery mechanism.
3. Completed Portainer, RabbitMQ, Recording, Database, Infrastructure, DOCTOR, Splunk, recovery,
   evidence, archive, and email values listed in `docs/ENVIRONMENT_INPUTS_REQUIRED.md`.
4. Disposable PostgreSQL URL for concurrency tests, if those must be verified locally.
5. Approval to run `pip-audit` with network access, or an offline vulnerability database/source.
