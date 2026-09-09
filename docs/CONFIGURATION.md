# Weekend Report Configuration

**Documentation synchronized:** 2026-09-07

## 1. Configuration Model

Weekend Report uses a strict separation between application code, deployment configuration, and business policy.

```text
Docker image
  -> application code and runtime scripts

deploy/docker/.env
deploy/docker/env/*.env
  -> environment-specific runtime values and secrets

deploy/docker/config/rules.yml
  -> version-controlled business and validation policy
```

The application does not use per-module deployment YAML for site inventory, server inventory,
expected services, or Splunk dashboard definitions.

There is one runtime policy source:

```text
deploy/docker/config/rules.yml
```

Production Compose mounts it read-only as:

```text
/app/config/rules.yml
```

Runtime secrets and deployment-specific values must not be baked into the image.

## 2. Deployment Files

The checked-in templates are:

```text
deploy/docker/.env.example

deploy/docker/env/
  app.env.example
  portainer.env.example
  doctor.env.example
  rabbitmq.env.example
  recording.env.example
  infrastructure.env.example
  splunk.env.example
```

On the deployment/build PC, create the real non-committed files:

```text
deploy/docker/.env

deploy/docker/env/
  app.env
  portainer.env
  doctor.env
  rabbitmq.env
  recording.env
  infrastructure.env
  splunk.env
```

The real files are intentionally ignored by Git and must remain outside source control.

## 3. Creating Runtime ENV Files

From the project root:

```powershell
Copy-Item .\deploy\docker\.env.example .\deploy\docker\.env

Get-ChildItem .\deploy\docker\env\*.env.example | ForEach-Object {
    $Target = $_.FullName -replace '\.example$',''
    Copy-Item $_.FullName $Target
}
```

Then edit the new runtime files locally.

Do not replace unknown values in the checked-in templates with real production values.

Controlled placeholders:

- `<TBD>` - required value not yet supplied.
- `<TO_VERIFY>` - candidate value that still requires verification.
- `<NOT_APPLICABLE>` - intentionally not applicable only where the application accepts it.

## 4. Compose-Level Configuration

`deploy/docker/.env` is only for values Docker Compose needs before containers start.

Typical values include:

```text
COMPOSE_PROJECT_NAME
WEEKEND_REPORT_IMAGE
```

For a release deployment:

```text
WEEKEND_REPORT_IMAGE=weekend-report:<version>
```

The same application image is used by both the `web` and `worker` services.

## 5. Application Runtime Configuration

`deploy/docker/env/app.env` contains application-wide runtime settings, including:

- PostgreSQL database name/user/password;
- `WEEKEND_REPORT_DATABASE_URL`;
- application version/build ID;
- optional Git commit metadata;
- authentication mode/provider;
- authorized reviewers;
- CSRF signing key;
- local-login session settings when applicable.

Production traceability requires real values for:

```text
WEEKEND_REPORT_APP_VERSION
WEEKEND_REPORT_BUILD_ID
```

The root `TAG` file remains the source version used by the release/image pipeline. Runtime
`WEEKEND_REPORT_APP_VERSION` should correspond to the deployed release.

## 6. Authentication Modes

The same application image supports two deployment modes.

### 6.1 Reverse Proxy / Trusted Header

Use:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=trusted_header
WEEKEND_REPORT_AUTH_TRUSTED_HEADER=X-Authenticated-User
WEEKEND_REPORT_AUTHORIZED_REVIEWERS=<approved identities>
WEEKEND_REPORT_CSRF_SIGNING_KEY=<secret>
```

The reverse proxy must authenticate the user and must overwrite/remove any client-supplied copy of
the trusted identity header.

`compose.proxy.yml` binds Weekend Report only to:

```text
127.0.0.1:8080
```

The current proxy override therefore assumes the reverse proxy runs on the same host.

### 6.2 Direct HTTPS / Local Login

Use:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=local_login
WEEKEND_REPORT_AUTHORIZED_REVIEWERS=<approved identities>
WEEKEND_REPORT_CSRF_SIGNING_KEY=<secret>
WEEKEND_REPORT_LOCAL_USERS_FILE=/app/secrets/local-users.json
WEEKEND_REPORT_SESSION_SIGNING_KEY=<secret>
WEEKEND_REPORT_SESSION_TTL_SECONDS=<approved value>
```

`compose.direct.yml` terminates TLS in the Weekend Report container and expects:

```text
deploy/docker/tls/server.crt
deploy/docker/tls/server.key
```

The local users file belongs under:

```text
deploy/docker/secrets/local-users.json
```

## 7. Secrets and File Mounts

The base Compose file mounts:

```text
./secrets -> /app/secrets:ro
```

Typical deployment files may include:

```text
deploy/docker/secrets/
  ssh_private_key
  known_hosts
  local-users.json
```

Only include files required by the selected deployment mode and enabled modules.

Direct HTTPS additionally mounts:

```text
./tls -> /app/tls:ro
```

Never commit real secrets, private keys, tokens, passwords, or production `.env` files.

## 8. Sites and Infrastructure

Site identifiers and infrastructure inventory come from runtime ENV, not from `rules.yml`.

Infrastructure configuration includes:

- site display/identity values;
- SSH username;
- private key path;
- strict known-hosts path;
- expected Chrony source/timezone;
- numbered server lists per site.

Example container paths:

```text
SSH_PRIVATE_KEY_PATH=/app/secrets/ssh_private_key
SSH_KNOWN_HOSTS_PATH=/app/secrets/known_hosts
```

Server lists are dynamic. Increase the site server count and add the matching numbered variables
instead of modifying Python code.

Infrastructure policy remains in `rules.yml`, including filesystem and Chrony thresholds.

## 9. Portainer

Portainer runtime configuration contains only connection information.

It does not contain:

- a hardcoded expected service list;
- expected image references;
- image-comparison modes;
- hardcoded replica counts.

The application discovers Docker Swarm services dynamically from both sites.

For every discovered service it validates the actual site state, including desired/running replicas,
health when available, image traceability, and task/service state. Cross-site parity is then
evaluated separately.

Two sites being identically unhealthy must not produce a PASS.

Typical runtime fields include:

```text
PORTAINER_COLLECTION_MODE=live
PORTAINER_API_CONTRACT=docker_proxy_v1
PORTAINER_AUTH_TYPE=x_api_key

PORTAINER_SITE1_URL
PORTAINER_SITE1_ENDPOINT_ID
PORTAINER_SITE1_TOKEN
PORTAINER_SITE1_TLS_VERIFY

PORTAINER_SITE2_URL
PORTAINER_SITE2_ENDPOINT_ID
PORTAINER_SITE2_TOKEN
PORTAINER_SITE2_TLS_VERIFY
```

Portainer task-state and parity policy belongs in `rules.yml`.

## 10. RabbitMQ

RabbitMQ runtime ENV supplies Management API connection values for both sites.

Typical fields include:

```text
RABBITMQ_COLLECTION_MODE=live

RABBITMQ_SITE1_URL
RABBITMQ_SITE1_USER
RABBITMQ_SITE1_PASSWORD
RABBITMQ_SITE1_TLS_VERIFY

RABBITMQ_SITE2_URL
RABBITMQ_SITE2_USER
RABBITMQ_SITE2_PASSWORD
RABBITMQ_SITE2_TLS_VERIFY
```

Queue policy and node-health policy remain in `rules.yml`.

The current validation rule requires queue `Ready`, `Unacked`, and `Total` counts to reach zero after
the configured rechecks, and node health indicators must remain within policy.

## 11. DOCTOR

DOCTOR does not use a configured service inventory.

Runtime configuration is limited to the API contract, for example:

```text
DOCTOR_MODE=api
DOCTOR_SITE1_URL=<TBD>
DOCTOR_SITE2_URL=<TBD>
DOCTOR_API_SCHEMA=<TBD>
```

When the live adapter is implemented, each site's service inventory is discovered dynamically and
the two service sets are compared.

Current implementation status:

```text
LIVE DOCTOR API ADAPTER: NOT IMPLEMENTED
```

Filling the three ENV values alone does not make the DOCTOR module production-ready.

## 12. Recording

Recording uses the existing-device workflow only.

Runtime ENV provides the Manager/WebApp endpoints and site server references. Safety, polling,
expected count deltas, cleanup, and recovery behavior remain in `rules.yml`.

Device creation/deletion is not part of this project.

Current implementation status:

```text
LIVE RECORDING COLLECTOR: INTENTIONALLY BLOCKED
```

The live control/read contract must be implemented and approved before the module can be enabled in
production.

## 13. Database Synchronization

Database synchronization remains behind the approved PowerShell adapter boundary:

```text
scripts/database/database_sync_check.ps1
```

The Weekend Report application must not invent the database synchronization algorithm.

Current implementation status:

```text
scripts/database/database_sync_check.ps1 is empty
```

Production preflight must continue to block live database execution until the approved script and
its result contract are supplied.

Because this script is part of the application image, it must be completed before building the
production image unless the project is deliberately changed to mount the script externally.

## 14. Splunk

Splunk dashboard definitions come from numbered runtime ENV values.

Typical structure:

```text
SPLUNK_DASHBOARD_COUNT=<number>

SPLUNK_DASHBOARD_1_ID=<value>
SPLUNK_DASHBOARD_1_DISPLAY_NAME=<value>
SPLUNK_DASHBOARD_1_URL=<value>
```

The dashboard count is dynamic. Add/remove numbered entries rather than changing application code.

Dashboard review requirements and note policy remain in `rules.yml`.

## 15. Business Policy in rules.yml

`deploy/docker/config/rules.yml` is the single runtime policy file.

It controls stable, reviewable policy such as:

- module enablement and requiredness;
- unavailable/error behavior;
- aggregation;
- cross-site parity;
- Portainer task-state policy;
- RabbitMQ queue/node rules;
- infrastructure thresholds;
- Recording safety/recovery policy;
- review-note requirements;
- approve/reject readiness;
- stale-worker and recovery behavior.

Environment-specific addresses, credentials, server lists, dashboard URLs, and tokens do not belong
in `rules.yml`.

## 16. Deployment Helper Scripts

Optional helper scripts are stored under:

```text
scripts/deployment/
```

Current helpers:

```text
configure-app-env.ps1
configure-portainer-env.ps1
configure-rabbitmq-env.ps1
configure-infrastructure-env.ps1
configure-splunk-env.ps1
scan-unresolved-config.ps1
```

They resolve the project root relative to their own location and do not contain this development
PC's absolute path.

They are convenience tools, not runtime dependencies.

Important:

- create the real `.env` files from templates before running a configure helper;
- `configure-app-env.ps1` currently follows the trusted-header-oriented setup used during the
  refactor; a `local_login` deployment still requires a real session signing key and local users
  file;
- `scan-unresolved-config.ps1` is useful on the deployment/build PC after the real ENV files exist.

## 17. Configuration Validation

From the project root, with all runtime ENV files created:

```powershell
python scripts/validate_config.py `
  --config deploy/docker/config `
  --env-file deploy/docker/env/app.env `
  --env-file deploy/docker/env/portainer.env `
  --env-file deploy/docker/env/doctor.env `
  --env-file deploy/docker/env/rabbitmq.env `
  --env-file deploy/docker/env/recording.env `
  --env-file deploy/docker/env/infrastructure.env `
  --env-file deploy/docker/env/splunk.env
```

For non-production shape/schema validation:

```powershell
python scripts/validate_config.py `
  --config deploy/docker/config `
  --no-production-preflight
```

The deployment helper scan can also be run after real ENV files exist:

```powershell
.\scripts\deployment\scan-unresolved-config.ps1
```

A production deployment is not ready merely because ENV syntax is valid. Live-module implementation
blockers described above must also be resolved or explicitly disabled according to approved
`rules.yml` policy.
