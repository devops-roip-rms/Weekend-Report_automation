# Configuration Guide

Use YAML for expected state and policy. Use a non-committed `.env`, Docker secrets, or another
approved mechanism for runtime secrets. Do not put credentials in YAML, docs, fixtures, or example
files.

Controlled placeholders:

- `<TBD>`: required information not supplied.
- `<TO_VERIFY>`: candidate information not yet verified.
- `<NOT_APPLICABLE>`: only where the schema explicitly permits it.

The default `config/` directory is a production template and is expected to fail until all required
values are completed. `tests/fixtures/config_valid` is safe fixture-only configuration for local
tests.

## Runtime Identity

Production runs require:

- `WEEKEND_REPORT_APP_VERSION`
- `WEEKEND_REPORT_BUILD_ID`
- deterministic configuration hash from the loaded YAML files

`WEEKEND_REPORT_GIT_COMMIT` is optional and may remain `<NOT_APPLICABLE>` for the local-folder
deployment model.

## Authentication And CSRF

Production requires `WEEKEND_REPORT_AUTH_MODE=production`, an approved provider,
`WEEKEND_REPORT_AUTHORIZED_REVIEWERS`, and `WEEKEND_REPORT_CSRF_SIGNING_KEY`.

The implemented production provider is `trusted_header`. Use it only behind an approved reverse
proxy/auth boundary and configure `WEEKEND_REPORT_AUTH_TRUSTED_HEADER`. Production rejects arbitrary
`X-Reviewer` identity. Browser mutations require reviewer-bound signed CSRF tokens.

## Rules

`config/rules.yml` controls module enablement, module requiredness, unavailable-status handling,
aggregation, parity, review notes, approval policy, reject policy, and stale-worker recovery.

`rules.yml` must not contain fixture actuals. Database fixture data belongs in
`tests/fixtures/config_valid/database.yml`; production database expected/adapter config belongs in
`config/database.yml`.

ERROR, FAIL, SKIPPED, and MANUAL_REVIEW are never silently converted to PASS.

## Portainer

`config/portainer_expected.yml` supports:

- `collection_mode: fixture|live`
- common `defaults`
- common `services`
- per-site `service_inventory: common`
- per-site `overrides.services`
- per-site live `connection`

Expected config is expected state only. Actual state comes from the Portainer collector or fixture
actuals. Required defaults to `true`; optional services must explicitly set `required: false`.

Task state policy distinguishes `failed`, `rejected`, `restarting`, and `starting`. The default
fixture policy fails failed/rejected/restarting and ignores starting. Production can leave `starting`
as `<TO_VERIFY>` until the organization approves the policy.

Parity is configured in `rules.yml` and is additive. It never hides independent site failures.

## RabbitMQ

`config/rabbitmq_expected.yml` supports:

- `collection_mode: fixture|live`
- live `connections`
- common topology in `topology.vhosts`, `topology.queues`, `topology.exchanges`,
  `topology.bindings`
- common defaults in `defaults`
- per-site `topology: common`
- per-site `overrides`

Expected config is topology/threshold policy only. Actual vhosts, queues, exchanges, bindings,
nodes, and metrics come from the collector or fixture actuals. Required defaults to `true`;
optional topology must explicitly set `required: false`.

## Recording

Recording is an existing-device start/stop workflow. Do not configure synthetic device create/delete.

Required workflow:

1. Read WebApp baseline count N.
2. Read backend baseline count M.
3. Select the first suitable existing non-recording device.
4. Start recording on that same selected device.
5. Poll for device recording, WebApp N+1, and backend M+1.
6. Stop recording on the same selected device.
7. Poll for device not recording, WebApp N, and backend M.
8. Verify cleanup/recovery state.

Live Recording remains blocked until WebApp/backend/action contracts are supplied and explicitly
approved. A crash or unknown state after start must enter manual recovery; the worker must not
replay a possibly state-changing operation.

## Database

`config/database.yml` defines the adapter boundary for the owner's existing database sync function.
The project does not rewrite the temp-table algorithm.

The adapter result must contain per-site structured booleans:

- `create_success`
- `replication_after_create`
- `delete_success`
- `replication_after_delete`
- `cleanup_complete`
- `errors`

Fixture actuals for this contract belong only in fixture config. Live mode returns a clear
`DATABASE_SYNC_FUNCTION_NOT_PROVIDED` error until the approved function is inserted.

## Infrastructure

`config/servers.yml` defines expected servers, filesystems, NFS mappings, and Chrony/NTP policy.
Live SSH collection is blocked until approved targets, credentials, commands, and host-key policy
are supplied.

Chrony normalization is based on approved `chronyc tracking` and `chronyc sources` output and
produces `{synchronized, source, offset}`. NFS validation checks expected source, mountpoint,
usability/reachability, and utilization.

## Review And Finalization

Notes are saved through HTML/API review pages and are ownership-validated:

- module must be valid
- result note `result_id` must belong to `run_id`
- dashboard ID must exist in `config/splunk_dashboards.yml`
- general notes require `rules.review.general_notes_enabled`
- note mutation requires `REVIEW_READY`

Final confirmation creates one frozen snapshot and one final PDF. Intermediate PDFs are not
generated. Automated findings are preserved exactly; reviewer notes are additive.

## Docker

`env.example` files are templates only. Compose uses required environment-variable substitution for
runtime secrets and must not consume literal `<TBD>` values as secrets.

For syntax validation, use disposable shell values. For production, create a real non-committed
`.env`, Docker secret, or approved secret source.
