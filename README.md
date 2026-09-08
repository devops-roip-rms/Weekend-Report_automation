# Weekend Report Automation

Weekend Report Automation is a manually triggered operational-validation application built with Python 3.14, FastAPI, PostgreSQL, a persistent worker, filesystem evidence, HTML review, immutable review snapshots, and one final PDF generated only after explicit human confirmation.

The Docker image contains application code only. Runtime values are external ENV/secrets, and validation policy is supplied through the read-only `deploy/docker/config/rules.yml` file.

## Operating Flow

```text
RUN WEEKEND REPORT
        |
        v
configuration preflight
        |
        v
database execution lock
        |
        v
CREATED -> RUNNING
        |
        v
collectors + validators + evidence
        |
        v
REVIEW_READY
        |
        v
HTML review + notes
        |
        v
APPROVE / REJECT
        |
        v
immutable snapshot
        |
        v
one final PDF
```

The operational Weekend Report is never scheduled by GitHub Actions or GitLab CI/CD.

## Repository Layout

```text
app/                     application code
  api/                   FastAPI route modules
  collectors/            external-state collection boundaries
  config/                configuration loading/schema/preflight
  database/              repository + SQL migrations
  evidence/              evidence paths/checksums/storage
  executors/             approved execution boundaries
  orchestrator/          run planning/execution/aggregation
  reporting/             snapshot/HTML/PDF generation
  review/                notes/finalization policy
  validators/            module validation logic
  web/                   FastAPI app, templates, static assets
  worker/                persistent run worker

deploy/docker/            production/CI Compose and runtime templates
  config/rules.yml        single runtime policy source
  env/*.env.example       module-specific ENV templates

docs/                     architecture, configuration, deployment, CI/CD, recovery, validation
scripts/                  CI, migration, configuration, deployment and database helpers
tests/                    unit, integration, contract and fixture tests

Dockerfile                final application image
Dockerfile.runtime-base   online-built production dependency base
Dockerfile.ci             online-built closed-network CI image
requirements.txt          production Python dependencies
requirements-dev.txt      development/online-CI tools + runtime dependencies
TAG                       release version/trigger source
```

Generated transfer artifacts, Docker image TAR files, wheelhouses, runtime ENV files, secrets, caches, and `.git` metadata are not source-repository content.

## Python and Dependency Model

The project baseline is Python 3.14.

Production runtime dependencies are pinned in:

```text
requirements.txt
```

Development and online CI tooling is pinned in:

```text
requirements-dev.txt
```

Local development:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the shared quality gates:

```powershell
python scripts/ci.py config
python scripts/ci.py lint
python scripts/ci.py typecheck
python scripts/ci.py unit
python scripts/ci.py contract
python scripts/ci.py integration
python scripts/ci.py e2e
python scripts/ci.py audit
python scripts/ci.py compose-config
```

The PostgreSQL concurrency gate additionally requires a disposable PostgreSQL database. Never point it at production/shared data.

## Docker Build Model

There are three distinct images/roles.

### 1. Runtime base

`Dockerfile.runtime-base` is built on an Internet-connected machine. It contains Python 3.14, production Python dependencies, CA certificates, and `openssh-client`.

```powershell
docker build --pull `
  -f Dockerfile.runtime-base `
  -t weekend-report-runtime-base:python314 `
  .
```

For the closed GitLab environment, transfer this image and publish/tag it as:

```text
weekend-report-runtime-base:python314
```

### 2. Closed-network CI image

`Dockerfile.ci` is also built online, then transferred to the closed environment. It contains Python quality tooling plus Docker CLI/Compose.

```powershell
docker build --pull `
  -f Dockerfile.ci `
  -t weekend-report-ci:python314 `
  .
```

The offline GitLab pipeline expects:

```text
weekend-report-ci:python314
```

Closed GitLab also expects the approved internal PostgreSQL image at `postgres-16-alpine`. GitHub-hosted CI uses public `postgres:16-alpine`.

### 3. Final application image

The final `Dockerfile` uses the prebuilt runtime base and copies only runtime application content.

Connected/local example:

```powershell
docker build `
  --build-arg RUNTIME_BASE_IMAGE=weekend-report-runtime-base:python314 `
  -t weekend-report:local `
  .
```

GitLab supplies the internal runtime-base image automatically from `.gitlab-ci-cd/image.yml`.

## CI/CD and Release

Normal source changes run quality gates only. They do not create a release image.

The root `TAG` file is both the release version source and the release-image trigger. A `TAG` change on the default branch reruns all pre-image gates, builds the exact image, smoke-tests it, version-tags that same image, exports it with a SHA-256 checksum, and optionally publishes it.

A Git tag is not required.

See `docs/CI_CD.md` for the exact GitHub/GitLab flow, support-image preparation, baked dependency-audit evidence, and closed-network prerequisites.

## Runtime Configuration

Production Compose uses:

```text
deploy/docker/compose.yml
+ deploy/docker/compose.proxy.yml   # reverse-proxy mode
or
deploy/docker/compose.direct.yml  # direct HTTPS mode
```

Runtime values are copied from templates into non-committed files under:

```text
deploy/docker/.env
deploy/docker/env/*.env
```

Secrets belong under `deploy/docker/secrets/` or another approved secret mechanism. Direct-mode TLS material belongs under `deploy/docker/tls/`.

Policy remains in:

```text
deploy/docker/config/rules.yml
```

Do not put production credentials in source YAML, fixtures, documentation, Docker layers, or CI artifacts.

## Authentication

Production supports two approved identity boundaries:

- `trusted_header` behind a trusted reverse proxy that overwrites/removes client-supplied identity headers;
- `local_login` using a non-committed `secrets/local-users.json` plus session signing key.

Manage local-login users from the source/build machine with:

```powershell
python scripts/manage_local_user.py add <username>
python scripts/manage_local_user.py list
python scripts/manage_local_user.py remove <username>
```

## Current Live Integration Status

- **Portainer:** live read-only Docker Swarm service discovery, independent site health, and cross-site parity implemented.
- **RabbitMQ:** live Management API queue/node validation implemented.
- **Infrastructure:** live read-only SSH collection for root filesystem and Chrony/NTP implemented.
- **Splunk:** human dashboard review flow implemented.
- **Database:** production PowerShell script adapter remains blocked while `scripts/database/database_sync_check.ps1` is empty/unverified.
- **DOCTOR:** dynamic service validation exists, but the live API adapter is not implemented.
- **Recording:** workflow/recovery semantics exist, but live collection/control remains intentionally blocked.

These are explicit readiness blockers, not hidden configuration defaults.

## Documentation

- `docs/ARCHITECTURE.md` — runtime architecture and module boundaries
- `docs/CONFIGURATION.md` — ENV, secrets, policy and helper scripts
- `docs/DEPLOYMENT.md` — image preparation and runtime deployment
- `docs/CI_CD.md` — GitHub/GitLab quality and image delivery
- `docs/RECOVERY_POLICY.md` — stale-run and recording recovery behavior
- `docs/VALIDATION_CATALOG.md` — validation checks/status semantics
