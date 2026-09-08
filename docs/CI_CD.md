# CI/CD and Verified Image Delivery

**Documentation synchronized:** 2026-09-07

## 1. Purpose

Weekend Report uses one shared quality-gate implementation:

```text
scripts/ci.py
```

GitHub Actions and GitLab CI/CD are thin orchestration layers around that shared contract. They do not contain separate business-validation logic and they never trigger a real Weekend Report run against production systems.

## 2. Python and Image Roles

```text
Python baseline:             3.14
Runtime dependency file:    requirements.txt
Development/CI dependency:  requirements-dev.txt
Application DB:              PostgreSQL 16
```

Three Docker image roles are intentionally separate:

```text
weekend-report-runtime-base:python314
  production Python dependencies + CA certificates + openssh-client

weekend-report-ci:python314
  Python quality tools + Docker CLI + Compose for closed GitLab jobs

weekend-report:<version>
  final production application image
```

The runtime-base and CI images are support images. They are not the deployed Weekend Report application image.

## 3. Quality Gates

Normal source changes run quality only:

```text
config validation
ruff
mypy
unit tests
contract tests
integration tests
PostgreSQL concurrency
safe fixture E2E
dependency audit (GitHub online; GitLab verifies baked online evidence)
Docker Compose validation
```

A normal source commit does not create a release image.

The PostgreSQL concurrency gate requires disposable data and must never target a production/shared database.

The dependency audit needs approved network/package vulnerability sources. GitHub runs it online. `Dockerfile.ci` also performs the runtime dependency audit while that support image is built online and stores checksum/audit evidence inside the image. Closed GitLab verifies that the current `requirements.txt` and `requirements-dev.txt` match that baked evidence before continuing.

## 4. Release Trigger

The root file:

```text
TAG
```

is the authoritative release version and image-release trigger.

Example:

```text
v1.2.0
```

A Git tag is not required.

Release flow:

```text
TAG changed on default branch
        |
        v
all pre-image quality gates
        |
        +--> any failure: STOP
        |
        v
build exact application image
        |
        v
record image ID
        |
        v
smoke exact image
        |
        v
tag same image weekend-report:<TAG>
        |
        v
verify image ID unchanged
        |
        v
export .tar.gz + SHA-256
        |
        `--> optional registry publish
```

## 5. GitHub Actions

Files:

```text
.github/workflows/quality-gates.yml
.github/workflows/build-image.yml
.github/scripts/
```

GitHub-hosted runners have Internet access, so the image workflow builds the production runtime base from `Dockerfile.runtime-base` before building the final application image.

The final image build uses:

```text
RUNTIME_BASE_IMAGE=weekend-report-runtime-base:python314
```

The exact built image is then smoke-tested through `deploy/docker/compose.ci.yml` before version tagging/export/publication.

Optional GHCR publication is controlled by repository variables:

```text
WEEKEND_REPORT_PUBLISH_IMAGE=1
WEEKEND_REPORT_PUBLISH_LATEST=1   # optional
```

No production integration secrets are required for standard CI.

## 6. Closed GitLab Prerequisites

The closed GitLab runner must already be able to access these support images:

```text
weekend-report-ci:python314
weekend-report-runtime-base:python314
postgres-16-alpine
```

The GitLab definitions intentionally use the internal registry for all three images. GitHub-hosted jobs use public `postgres:16-alpine` instead.

### Build the CI image online

On an Internet-connected machine:

```powershell
docker build --pull `
  -f Dockerfile.ci `
  -t weekend-report-ci:python314 `
  .

docker save `
  -o weekend-report-ci-python314.tar `
  weekend-report-ci:python314
```

Transfer the TAR through the approved offline process, then on the closed side:

```bash
docker load -i weekend-report-ci-python314.tar
docker tag weekend-report-ci:python314 weekend-report-ci:python314
docker push weekend-report-ci:python314
```

### Build the runtime base online

```powershell
docker build --pull `
  -f Dockerfile.runtime-base `
  -t weekend-report-runtime-base:python314 `
  .

docker save `
  -o weekend-report-runtime-base-python314.tar `
  weekend-report-runtime-base:python314
```

On the closed side:

```bash
docker load -i weekend-report-runtime-base-python314.tar
docker tag weekend-report-runtime-base:python314 weekend-report-runtime-base:python314
docker push weekend-report-runtime-base:python314
```

The generated TAR files are transfer artifacts and are intentionally excluded from Git.

## 7. GitLab Layout

```text
.gitlab-ci.yml
.gitlab-ci-cd/
  quality.yml
  image.yml
  scripts/
    wait-for-docker.sh
    verify-ci-image-audit.sh
    image-build-smoke-export.sh
    verify-release-image.sh
    export-offline-image.sh
    publish-image.sh
```

Quality jobs use:

```text
weekend-report-ci:python314
```

The image job uses the same CI image because it already contains Python, Docker CLI, Compose, gzip, and checksum tooling. No `apk add`, `apt-get`, or `pip install` is performed by the closed pipeline.

The `dependency-audit` GitLab job runs `verify-ci-image-audit.sh`. It compares the current dependency-file SHA-256 values with the values baked into `weekend-report-ci:python314` and verifies that the online `pip-audit` evidence exists and is valid JSON. A dependency change therefore forces the support CI image to be rebuilt and transferred before the closed pipeline can pass.

The application build receives:

```text
WEEKEND_REPORT_RUNTIME_BASE_IMAGE=weekend-report-runtime-base:python314
```

and passes it into the final Dockerfile as `RUNTIME_BASE_IMAGE`.

## 8. Exact-Image Smoke Contract

`scripts/ci.py image-smoke --image <tag>` uses:

```text
deploy/docker/compose.ci.yml
```

That Compose file contains no `build:` directive. It must run the exact already-built image supplied through `WEEKEND_REPORT_CI_IMAGE`.

The CI PostgreSQL image is parameterized:

```text
GitHub default:  postgres:16-alpine
GitLab:          postgres-16-alpine
```

The GitLab Docker daemon does not share the job container filesystem. For that reason, the smoke flow creates the containers first and then copies the version-controlled `deploy/docker/config/rules.yml` into the web and worker containers before startup rather than relying on a host bind mount.

The smoke verifies:

- PostgreSQL starts and becomes healthy;
- web starts;
- worker starts;
- `/healthz` returns OK;
- migrations/database access work;
- PostgreSQL/web/worker remain running;
- temporary CI containers, volumes and networks are removed afterward.

The image ID recorded before smoke must match the release-tag image ID before export.

## 9. Offline Artifact

Both delivery pipelines export the verified release image as:

```text
weekend-report_<version>.tar.gz
weekend-report_<version>.tar.gz.sha256
image-id.txt
release-image-id.txt
```

For example:

```text
weekend-report_v1.2.0.tar.gz
```

After loading, the image tag is:

```text
weekend-report:v1.2.0
```

## 10. Local Gate Commands

Install development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Then run:

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

PostgreSQL concurrency is separate because it requires a disposable PostgreSQL URL:

```powershell
$env:WEEKEND_REPORT_TEST_POSTGRES_URL = "postgresql://USER:PASSWORD@HOST:PORT/weekend_report_test"
$env:WEEKEND_REPORT_TEST_POSTGRES_DISPOSABLE = "1"
python scripts/ci.py postgres
```

## 11. When Support Images Must Be Rebuilt

Rebuild `weekend-report-ci:python314` when any of these change:

```text
Dockerfile.ci
requirements.txt
requirements-dev.txt
Python/Docker CLI/Compose/tooling versions baked into Dockerfile.ci
```

Rebuild `weekend-report-runtime-base:python314` when any of these change:

```text
Dockerfile.runtime-base
requirements.txt
Python runtime version
required OS runtime packages
```

Normal application code, docs, Compose templates, or tests do not require rebuilding either support image unless they also change one of the inputs above. If either dependency file changes without rebuilding the CI image, the closed GitLab dependency-evidence gate fails deliberately.

## 12. Security Boundary

Standard CI must not receive production Portainer tokens, RabbitMQ passwords, SSH private keys, production DB validation credentials, DOCTOR credentials, Recording credentials, or production evidence.

CI uses fixtures and disposable infrastructure only.

## 13. Regression Coverage

`tests/unit/test_ci_config.py` protects delivery invariants including:

- CI YAML parses;
- required quality gates stay visible;
- release builds depend on quality gates;
- release version comes from `TAG`, not Git tags;
- the exact built image is smoked before export/publish;
- the smoke-tested image is the image that receives the release tag;
- CI Compose uses an exact image and contains no `build:`;
- GitHub uses public PostgreSQL while closed GitLab uses the internal mirror;
- closed GitLab dependency files match baked online audit evidence;
- CI files contain no known production integration secrets.

Do not weaken these tests to make a pipeline green. Fix the delivery configuration that violated the invariant.
