# CI/CD and Verified Image Delivery

## Purpose

The project has one shared quality-gate contract and two CI adapters:

```text
Local commands
    |
    +--> GitHub Actions
    |
    +--> GitLab CI/CD
```

GitHub and GitLab call the same `scripts/ci.py` gates. CI does not contain a second copy of the Weekend Report validation logic.

The operational Weekend Report remains a manual FastAPI action. CI never starts a real production Weekend Report and never performs a real state-changing Recording action.

## Delivery Model

```text
SOURCE CHANGE
    |
    v
CONFIG VALIDATION
    |
    v
QUALITY GATES
    |-- Ruff
    |-- Mypy
    |-- Unit tests
    |-- Integration tests
    |-- Contract tests
    |-- PostgreSQL concurrency tests
    |-- Safe fixture E2E
    |-- Dependency audit
    `-- Docker Compose validation
    |
    v
ALL PRE-IMAGE GATES PASS?
    | no
    +--> STOP: no image is built
    |
   yes
    v
BUILD EXACT IMAGE
    |
    v
SMOKE EXACT IMAGE
    |
    |-- PostgreSQL starts and becomes healthy
    |-- web container starts
    |-- worker container starts
    |-- /healthz succeeds
    `-- DB migration/access check succeeds
    |
    v
SMOKE PASS?
    | no
    +--> STOP: no verified image artifact or registry release
    |
   yes
    v
EXPORT VERIFIED IMAGE + SHA256
    |
    `--> optional registry push
```

The image is built once. The exact locally tagged image is smoke-tested. Only that already-tested image is exported and, if registry publication is explicitly enabled, tagged/pushed.

## Shared Local Gates

Install dependencies first:

```powershell
python -m pip install -r requirements.txt
```

Run gates individually:

```powershell
python scripts/ci.py config
python scripts/ci.py lint
python scripts/ci.py typecheck
python scripts/ci.py unit
python scripts/ci.py integration
python scripts/ci.py contract
python scripts/ci.py e2e
python scripts/ci.py audit
python scripts/ci.py compose-config
```

The PostgreSQL concurrency gate is intentionally strict. It requires a disposable PostgreSQL database:

```powershell
$env:WEEKEND_REPORT_TEST_POSTGRES_URL = "postgresql://USER:PASSWORD@HOST:PORT/weekend_report_ci_test"
$env:WEEKEND_REPORT_TEST_POSTGRES_DISPOSABLE = "1"
python scripts/ci.py postgres
```

Do not point this gate at a production or shared operational database.

## Safe E2E Gate

`scripts/ci_e2e.py` uses only fixture configuration, SQLite, temporary evidence storage, and local application code.

It covers:

```text
create run
  -> claim run
  -> execute fixture modules
  -> write evidence
  -> REVIEW_READY
  -> save reviewer/module/result/Splunk/general notes
  -> APPROVE using CI-only fixture approval policy
  -> freeze snapshot
  -> generate final PDF
```

The gate verifies that automated statuses do not change during review and that every persisted CI review note is represented in the snapshot and generated PDF.

It does not contact Portainer, RabbitMQ, SSH servers, DOCTOR, Splunk, a production DB-validation target, or Recording systems.

## Built-Image Smoke

The built-image smoke uses `deploy/docker/compose.ci.yml`.

This Compose file is intentionally separate from the production Compose file. It:

- accepts the exact already-built image through `WEEKEND_REPORT_CI_IMAGE`;
- never contains a `build:` directive;
- uses PostgreSQL 16;
- uses `tests/fixtures/config_valid` inside the image;
- runs web and worker from the same image;
- exposes only the web health port on loopback;
- uses development authentication;
- uses disposable Docker volumes/networks created under a unique Compose project name;
- is removed with volumes after the smoke test.

Local example:

```powershell
docker build -t weekend-report:local-ci .
python scripts/ci.py image-smoke --image weekend-report:local-ci
```

## GitHub Actions

Files:

```text
.github/workflows/quality-gates.yml
.github/workflows/build-image.yml
```

### Quality workflow

`quality-gates.yml` runs on:

- branch pushes;
- pull requests;
- manual `workflow_dispatch`;
- reusable `workflow_call` from the image workflow.

The config-validation job runs first. Once it passes, the remaining pre-image gates run independently so the Actions UI identifies the exact failing category without waiting for unrelated gates to run serially.

PostgreSQL uses a disposable `postgres:16-alpine` service and sets:

```text
WEEKEND_REPORT_TEST_POSTGRES_URL
WEEKEND_REPORT_TEST_POSTGRES_DISPOSABLE=1
```

A PostgreSQL concurrency failure fails the workflow; it is not converted to a skip/pass.

### Image workflow

`build-image.yml` runs on:

- manual `workflow_dispatch`;
- semantic-style tags matching `v*.*.*`.

It first calls the reusable quality workflow. The Docker job declares `needs: quality`, so it cannot start when a pre-image gate fails.

The workflow then:

1. derives build/version identity;
2. builds with Buildx and loads the image into the runner Docker daemon;
3. records the exact Docker image ID;
4. smoke-tests that exact image;
5. exports a compressed offline image archive;
6. writes a SHA-256 checksum;
7. uploads the verified archive as a workflow artifact;
8. optionally pushes the same image to GHCR.

A pull request never publishes an image.

### GitHub registry controls

Registry publication is off unless explicitly enabled.

Manual run:

- set `publish_registry=true` in the workflow input.

Tagged run:

- repository variable `WEEKEND_REPORT_PUBLISH_IMAGE=1` enables GHCR publishing;
- repository variable `WEEKEND_REPORT_PUBLISH_LATEST=1` additionally enables `latest` for a version tag.

The workflow uses the GitHub-provided token and `packages: write`; no hardcoded registry password is stored in the repository.

Generated registry tags include:

```text
sha-<12-character-commit>
<semantic-version>       # version-tag builds
latest                   # only when explicitly enabled
```

## GitLab CI/CD

Files:

```text
.gitlab-ci.yml
.gitlab/ci/quality.yml
.gitlab/ci/image.yml
```

The root file owns the pipeline stages and includes the quality/image definitions.

### Quality jobs

The GitLab quality layer contains separately visible jobs for:

```text
config-validation
ruff
mypy
unit-tests
integration-tests
contract-tests
postgres-concurrency
safe-e2e
dependency-audit
docker-compose-validate
```

`config-validation` runs first. The remaining quality jobs use `needs: [config-validation]` and can run in parallel after configuration is confirmed.

The image job has explicit `needs` on every release-blocking quality job. If any gate fails, the image job cannot start.

### GitLab PostgreSQL

The concurrency job uses a disposable `postgres:16-alpine` GitLab service with a test-only database and credentials. The test database name includes `test`, and `WEEKEND_REPORT_TEST_POSTGRES_DISPOSABLE=1` is also set.

### GitLab image job

The default implementation uses Docker-in-Docker because the same job must both build and run the exact image for the smoke test.

Runner requirement:

```text
Docker executor or equivalent runner able to use docker:27-dind
```

On many self-managed installations, DinD requires a runner configuration that permits privileged Docker services. If organizational policy forbids privileged DinD, replace only the GitLab image execution adapter with an approved runner that exposes a Docker daemon or an approved build/run combination. Do not weaken the pre-image gates.

The job runs only when one of these applies:

- a semantic version tag such as `v1.2.3`;
- the default branch and `WEEKEND_REPORT_BUILD_IMAGE_ON_DEFAULT_BRANCH=1`;
- a web/manual pipeline with `WEEKEND_REPORT_BUILD_IMAGE=1`;
- a web/manual pipeline where the user explicitly starts the manual image job.

Normal feature-branch and merge-request pipelines run the quality gates but do not build a release image.

### GitLab registry controls

Registry publication is disabled by default.

Set this protected CI/CD variable when publication is approved:

```text
WEEKEND_REPORT_PUBLISH_IMAGE=1
```

Optional:

```text
WEEKEND_REPORT_PUBLISH_LATEST=1
```

When enabled, the job uses GitLab predefined registry credentials. No registry credential is hardcoded in YAML.

## Offline Image Artifact

Both platforms create a verified artifact after the smoke test:

```text
weekend-report_<version>_<short-sha>.tar.gz
weekend-report_<version>_<short-sha>.tar.gz.sha256
image-id.txt
```

Verify after transfer:

```powershell
Get-FileHash .\weekend-report_<version>_<short-sha>.tar.gz -Algorithm SHA256
```

Compare it with the `.sha256` file, then load it:

```powershell
docker load -i .\weekend-report_<version>_<short-sha>.tar.gz
```

If the local Docker version does not accept the compressed archive directly, decompress it first and pass the resulting `.tar` to `docker load`.

## Dependency Audit and Closed Networks

`pip-audit` is a release-blocking pre-image gate. On an internet-connected GitHub-hosted runner it can use its normal vulnerability/index sources.

For a closed/self-managed GitLab environment, provide an organization-approved path to the required Python package/vulnerability data. If the environment cannot access an approved audit source, the dependency-audit job should remain failed/blocked rather than silently claiming a security PASS.

Do not disable the audit only to make image creation green without an approved replacement control.

## Secrets and Production Isolation

The CI definitions contain only disposable CI credentials.

They must not receive:

- Portainer production tokens;
- RabbitMQ production passwords;
- production SSH private keys;
- production DB-validation credentials;
- production DOCTOR credentials;
- Recording credentials;
- production evidence.

Future live-integration tests should use an explicitly approved isolated test environment and a separately reviewed workflow. They must not be added to normal pull-request/merge-request quality jobs by default.

## Diagnosing Failure

Examples:

```text
Config validation FAIL
  -> all downstream quality jobs skipped
  -> image not built

Ruff PASS
Mypy PASS
Unit tests PASS
PostgreSQL concurrency FAIL
  -> image not built

All quality gates PASS
Image build PASS
Built-image smoke FAIL
  -> verified archive not exported
  -> registry push not executed
```

The CI YAML exposes separate job names while `scripts/ci.py` keeps the actual command contract centralized.

## What Must Be Verified After Repository Upload

Local checks can validate the scripts and YAML structure, but actual hosted behavior must be verified after upload.

GitHub:

- Actions are enabled for the repository;
- selected runner supports the pinned action runtime versions;
- GHCR package permission is allowed if publishing is enabled;
- repository variables for publication are reviewed.

GitLab:

- a compatible Runner is registered;
- Docker/DinD or the approved alternative works;
- external/package mirrors required by `pip install` and `pip-audit` are reachable;
- artifact size/retention policy permits the compressed image archive;
- GitLab Container Registry is enabled if registry publication is desired.

Neither hosted CI platform is required for normal application runtime.
