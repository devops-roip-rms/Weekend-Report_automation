# Weekend Report Deployment

**Documentation synchronized:** 2026-09-07

## 1. Deployment Goal

Weekend Report is designed so the runtime server does not need the source repository.

```text
Internet-connected build PC
  source + Dockerfile.ci + Dockerfile.runtime-base
        |
        | prepare support images
        v
Closed GitLab/build environment
  weekend-report-ci:python314
  weekend-report-runtime-base:python314
        |
        | quality -> final image build -> smoke -> export
        v
Runtime server
  weekend-report:<version>
  postgres-16-alpine
  Compose + external ENV/policy/secrets
```

The runtime server does not need Python, Git, tests, CI files, Dockerfiles, requirements files, wheelhouses, or application source once the verified application image has been exported.

## 2. Build-Time Support Images

Two support images are prepared on an Internet-connected machine. They are build/CI dependencies, not runtime-server dependencies.

### 2.1 Closed-network CI image

```powershell
docker build --pull `
  -f Dockerfile.ci `
  -t weekend-report-ci:python314 `
  .
```

The closed GitLab configuration expects this image at:

```text
weekend-report-ci:python314
```

### 2.2 Production runtime base

```powershell
docker build --pull `
  -f Dockerfile.runtime-base `
  -t weekend-report-runtime-base:python314 `
  .
```

The closed GitLab image job expects:

```text
weekend-report-runtime-base:python314
```

Transfer these support images through the approved offline process, then load/tag/push them into the closed registry. Generated support-image TAR files are transfer artifacts and must not be committed to Git.

See `docs/CI_CD.md` for the exact preparation commands and rebuild rules.

## 3. Required Runtime Images

The production Compose stack itself needs only:

```text
weekend-report:<version>
postgres-16-alpine
```

The runtime-base image is already incorporated into the final Weekend Report image layers and does not need to be deployed as a separate Compose service.

For an offline runtime server, both required runtime images must already be loaded locally.

## 4. Final Runtime Folder

A minimal deployment directory should look like:

```text
weekend-report/
  compose.yml
  compose.direct.yml        # only direct HTTPS mode
  compose.proxy.yml         # only reverse-proxy mode
  .env

  env/
    app.env
    portainer.env
    doctor.env
    rabbitmq.env
    recording.env
    infrastructure.env
    splunk.env

  config/
    rules.yml

  secrets/
    ...required secret files...

  tls/                      # direct HTTPS mode only
    server.crt
    server.key
```

`compose.ci.yml` is a source/CI file and does not belong in the production runtime bundle.

The runtime server does not need:

```text
app/
tests/
docs/
.github/
.gitlab-ci-cd/
.gitlab-ci.yml
Dockerfile*
pyproject.toml
requirements*.txt
```

## 5. Build the Weekend Report Image

On a connected/local build machine where `weekend-report-runtime-base:python314` exists:

```powershell
$Version = (Get-Content .\TAG -Raw).Trim()

docker build `
  --build-arg RUNTIME_BASE_IMAGE=weekend-report-runtime-base:python314 `
  -t "weekend-report:$Version" `
  .
```

In the closed GitLab pipeline, `.gitlab-ci-cd/image.yml` supplies the internal base automatically:

```text
weekend-report-runtime-base:python314
```

The root `TAG` is the release-version source used by CI/release automation.

## 6. Export Runtime Images for the Offline Server

Obtain the approved PostgreSQL image first:

```powershell
docker pull postgres-16-alpine
```

Then save the verified application image and PostgreSQL image:

```powershell
$Version = (Get-Content .\TAG -Raw).Trim()

docker save `
  -o "weekend-report-runtime_$Version.tar" `
  "weekend-report:$Version" `
  "postgres-16-alpine"

Get-FileHash `
  ".\weekend-report-runtime_$Version.tar" `
  -Algorithm SHA256
```

Transfer the TAR and SHA-256 through the approved process. On the runtime server:

```bash
docker load -i weekend-report-runtime_<version>.tar
docker image ls
```

## 7. Prepare Deployment Configuration on the Build/Second PC

From the source project:

```powershell
Copy-Item .\deploy\docker\.env.example .\deploy\docker\.env

Get-ChildItem .\deploy\docker\env\*.env.example | ForEach-Object {
    $Target = $_.FullName -replace '\.example$',''
    Copy-Item $_.FullName $Target
}
```

Fill the real values on this PC. Do not commit them.

Complete:

```text
deploy/docker/.env
deploy/docker/env/app.env
deploy/docker/env/portainer.env
deploy/docker/env/doctor.env
deploy/docker/env/rabbitmq.env
deploy/docker/env/recording.env
deploy/docker/env/infrastructure.env
deploy/docker/env/splunk.env
```

Keep:

```text
deploy/docker/config/rules.yml
```

as the single version-controlled runtime policy file.

Place required secret files under:

```text
deploy/docker/secrets/
```

## 8. Optional Deployment Helpers

The source project includes optional helpers under:

```text
scripts/deployment/
```

They can assist with selected ENV files and unresolved-value scanning.

They are not copied to the minimal runtime server bundle.

The runtime server only needs the completed deployment files and images.

## 9. Select One Access Mode

The base file:

```text
compose.yml
```

does not publish the web port by itself.

Use exactly one production override.

### 9.1 Reverse Proxy Mode

Use:

```text
compose.proxy.yml
```

Expected authentication configuration in `env/app.env`:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=trusted_header
WEEKEND_REPORT_AUTH_TRUSTED_HEADER=X-Authenticated-User
```

The application is bound to:

```text
127.0.0.1:8080
```

so the current override expects the reverse proxy to run on the same host.

The proxy must:

- terminate HTTPS;
- authenticate the user;
- overwrite/remove client-supplied trusted identity headers;
- pass the approved identity header to Weekend Report.

### 9.2 Direct HTTPS Mode

Use:

```text
compose.direct.yml
```

Expected authentication configuration in `env/app.env`:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=local_login
WEEKEND_REPORT_LOCAL_USERS_FILE=/app/secrets/local-users.json
WEEKEND_REPORT_SESSION_SIGNING_KEY=<secret>
```

Provide:

```text
tls/server.crt
tls/server.key
secrets/local-users.json
```

The direct override publishes:

```text
8080:8080
```

with TLS handled by the Weekend Report web container.

## 10. Validate Configuration Before Packaging Runtime Files

If Python is available on the build/second PC:

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

You can also run:

```powershell
.\scripts\deployment\scan-unresolved-config.ps1
```

The runtime server itself does not require Python for normal container operation.

## 11. Current Production Blockers

Before building the final production image, decide what to do with these modules:

```text
DOCTOR
  live API adapter is not implemented

Recording
  live collector is intentionally blocked

Database
  scripts/database/database_sync_check.ps1 is empty
```

If these modules remain enabled/required in `rules.yml`, a complete production run cannot be treated
as fully ready merely because all ENV files were populated.

Production options are:

1. implement and validate the missing contracts before building the final image; or
2. explicitly disable/non-require unfinished modules in `rules.yml` through an approved policy
   decision until their implementation is completed.

Do not insert fake ENV values to bypass these blockers.

## 12. Build the Minimal Runtime Bundle

After configuration is complete, create a clean deployment directory containing only runtime files.

Example PowerShell from the source project:

```powershell
$Bundle = ".\runtime-bundle"

Remove-Item $Bundle -Recurse -Force -ErrorAction SilentlyContinue

New-Item "$Bundle\env" -ItemType Directory -Force | Out-Null
New-Item "$Bundle\config" -ItemType Directory -Force | Out-Null
New-Item "$Bundle\secrets" -ItemType Directory -Force | Out-Null

Copy-Item .\deploy\docker\compose.yml $Bundle
Copy-Item .\deploy\docker\.env $Bundle
Copy-Item .\deploy\docker\env\*.env "$Bundle\env\"
Copy-Item .\deploy\docker\config\rules.yml "$Bundle\config\"

# Choose ONE mode:
Copy-Item .\deploy\docker\compose.proxy.yml $Bundle
# OR:
# Copy-Item .\deploy\docker\compose.direct.yml $Bundle
```

If secrets exist:

```powershell
Copy-Item .\deploy\docker\secrets\* "$Bundle\secrets\" -Recurse
```

For direct HTTPS:

```powershell
New-Item "$Bundle\tls" -ItemType Directory -Force | Out-Null
Copy-Item .\deploy\docker\tls\* "$Bundle\tls\" -Recurse
```

Transfer the runtime bundle separately from the Docker image archive.

## 13. Validate Compose on the Runtime Server

Change into the runtime deployment directory first.

### Reverse proxy mode

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  -f compose.proxy.yml \
  config
```

### Direct HTTPS mode

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  -f compose.direct.yml \
  config
```

Do not run only `compose.yml` for production web access because the base file intentionally does not
publish the web port.

## 14. Start the Stack

### Reverse proxy mode

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  -f compose.proxy.yml \
  up -d
```

### Direct HTTPS mode

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  -f compose.direct.yml \
  up -d
```

The stack starts:

```text
postgres
web
worker
```

PostgreSQL uses persistent storage. Evidence also uses persistent storage.

The worker is attached to a non-internal egress network so it can reach configured Portainer,
RabbitMQ, SSH, DOCTOR, Recording, and other external integration endpoints.

The PostgreSQL backend network remains internal.

## 15. Initial Runtime Checks

Check container state:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  -f compose.proxy.yml \
  ps
```

Use `compose.direct.yml` instead when direct mode is selected.

Review logs if needed:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  -f compose.proxy.yml \
  logs --tail=200
```

Confirm at minimum:

- PostgreSQL becomes healthy;
- `web` stays running;
- `worker` stays running;
- `/healthz` responds;
- unauthenticated production access is rejected;
- the approved reviewer can authenticate;
- evidence persists across container restarts;
- database data persists across container restarts;
- required integration endpoints are reachable from the worker.

## 16. Reverse Proxy Security Requirement

For `trusted_header` mode, never expose the Weekend Report application port directly to untrusted
clients.

The trusted identity header is an authentication boundary.

The reverse proxy must ensure users cannot choose their own value for:

```text
X-Authenticated-User
```

or whichever header is configured.

## 17. Backup

Treat the PostgreSQL database and evidence storage as one logical application dataset.

Back up:

- PostgreSQL;
- evidence volume/data;
- deployed `rules.yml`;
- deployed runtime ENV/secrets through the approved secure backup process;
- final PDFs/snapshots where required operationally.

Do not place backup copies of production secrets into the source repository.

## 18. Upgrade

Recommended sequence:

1. update/test the source project;
2. run quality gates;
3. update `TAG` for the release;
4. build and smoke-test the exact new image;
5. export/checksum the image archive;
6. back up production;
7. load the new image on the server;
8. update `WEEKEND_REPORT_IMAGE`, app version, and build ID;
9. validate Compose;
10. restart the stack;
11. run acceptance checks.

## 19. Rollback

Preserve the previous:

- Weekend Report image;
- PostgreSQL-compatible application state;
- runtime ENV/secrets;
- `rules.yml`;
- database/evidence backup;
- build ID and application version.

Do not mix an older image with incompatible database or configuration state without validating the
combination first.

## 20. What Belongs Where

```text
SOURCE / BUILD PC ONLY
  app/
  tests/
  docs/
  scripts/
  Dockerfile*
  requirements*.txt
  CI/CD files
  TAG
  ENV templates

RUNTIME SERVER
  weekend-report image
  postgres-16-alpine image
  compose.yml
  one mode override
  .env
  env/*.env
  config/rules.yml
  secrets/
  tls/ when direct mode is used
```

This is the supported target deployment model for the project.
