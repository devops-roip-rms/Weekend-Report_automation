# Docker Deployment

`compose.yml` defines the common Weekend Report runtime:

- web;
- worker;
- PostgreSQL.

The same Weekend Report image is used by web and worker through:

```text
WEEKEND_REPORT_IMAGE
````

For local development it may default to:

```text
weekend-report:local
```

PostgreSQL is attached only to the backend Docker network and is not exposed publicly.

Production web exposure is selected using one of these mutually exclusive overrides:

```text
compose.direct.yml
compose.proxy.yml
```

---

## 1. Runtime Environment

The checked-in:

```text
deploy/docker/.env.example
```

is a template only.

Do not use it directly as the production runtime environment.

Create a non-committed:

```text
deploy/docker/.env
```

or use Docker secrets / another approved secret mechanism.

Required runtime values include at least:

```text
POSTGRES_PASSWORD
WEEKEND_REPORT_IMAGE
WEEKEND_REPORT_APP_VERSION
WEEKEND_REPORT_BUILD_ID
WEEKEND_REPORT_AUTH_MODE
WEEKEND_REPORT_AUTH_PROVIDER
WEEKEND_REPORT_AUTHORIZED_REVIEWERS
WEEKEND_REPORT_CSRF_SIGNING_KEY
```

Provider-specific authentication values are documented below.

Never put production secrets in:

* Git;
* YAML configuration;
* documentation;
* Docker image layers;
* CI artifacts.

---

## 2. Verified Release Image

For a verified offline release, load the CI-generated image artifact and configure the actual release version.

Example:

```text
WEEKEND_REPORT_IMAGE=weekend-report:<VERSION>
WEEKEND_REPORT_APP_VERSION=<VERSION>
WEEKEND_REPORT_BUILD_ID=<ACTUAL_BUILD_ID>
```

Do not invent the production build ID.

Obtain it from the loaded image:

```powershell
docker image inspect weekend-report:<VERSION> --format '{{ index .Config.Labels "io.weekend-report.build-id" }}'
```

Use the exact value stored in the verified image.

---

## 3. Production Authentication Modes

Weekend Report supports two mutually exclusive production authentication modes.

```text
Mode A: Direct HTTPS + local_login
Mode B: Reverse Proxy + trusted_header
```

The same Weekend Report application image supports both modes.

Changing deployment mode does not require rebuilding the application image.

---

## 4. Mode A - Direct HTTPS Access

Architecture:

```text
Browser
   |
   | HTTPS :8080
   v
Weekend Report
   |
   +-- local_login
       |
       +-- local password hashes
       +-- signed secure session cookie
```

Use:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=local_login
```

Required local-login values:

```text
WEEKEND_REPORT_LOCAL_USERS_FILE=/app/secrets/local-users.json
WEEKEND_REPORT_SESSION_SIGNING_KEY=<SECRET>
WEEKEND_REPORT_SESSION_TTL_SECONDS=14400
```

The session cookie is:

* signed;
* HttpOnly;
* Secure;
* SameSite=Lax;
* time-limited.

Because the cookie is `Secure`, production direct-login mode must use HTTPS.

Do not deploy production local-login as:

```text
http://server:8080
```

Use:

```text
https://server:8080
```

### 4.1 Local User Database

The local user database is stored at:

```text
deploy/docker/secrets/local-users.json
```

Inside the container it is mounted as:

```text
/app/secrets/local-users.json
```

Passwords are never stored in plaintext.

The file contains password hashes only.

Initial structure:

```json
{
  "users": {}
}
```

Manage users with:

```powershell
python scripts\manage_local_user.py add <username>
```

List configured users:

```powershell
python scripts\manage_local_user.py list
```

Remove a user:

```powershell
python scripts\manage_local_user.py remove <username>
```

Passwords are entered interactively and are not passed on the command line.

A local-login user must exist in both:

```text
local-users.json
```

and:

```text
WEEKEND_REPORT_AUTHORIZED_REVIEWERS
```

The local user database authenticates the identity.

`WEEKEND_REPORT_AUTHORIZED_REVIEWERS` authorizes that identity to operate Weekend Report.

### 4.2 Direct HTTPS TLS Files

Direct mode expects local TLS files:

```text
deploy/docker/tls/server.crt
deploy/docker/tls/server.key
```

Use organization-approved certificates when available.

Do not commit the private key.

### 4.3 Start Direct Mode

From the repository root:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  -f deploy/docker/compose.prod.yml `
  -f deploy/docker/compose.direct.yml `
  up -d
```

Open:

```text
https://<WEEKEND_REPORT_HOST>:8080
```

---

## 5. Mode B - Reverse Proxy

Architecture:

```text
Browser
   |
   | HTTPS
   v
Authenticated Reverse Proxy
   |
   | trusted identity header
   v
Weekend Report :8080
```

Use:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTH_PROVIDER=trusted_header
WEEKEND_REPORT_AUTH_TRUSTED_HEADER=X-Authenticated-User
```

The reverse proxy is responsible for authenticating the user.

Weekend Report trusts the identity supplied in the configured trusted header.

### 5.1 Trusted Header Security Requirement

The reverse proxy must remove or overwrite any client-supplied copy of:

```text
X-Authenticated-User
```

or whatever header is configured through:

```text
WEEKEND_REPORT_AUTH_TRUSTED_HEADER
```

A normal client must never be able to bypass the reverse proxy and directly submit the trusted identity header to Weekend Report.

Therefore trusted-header mode must not expose:

```text
0.0.0.0:8080
```

to normal clients.

The provided:

```text
compose.proxy.yml
```

binds Weekend Report to:

```text
127.0.0.1:8080
```

and therefore assumes the reverse proxy runs on the same host.

If the reverse proxy runs on another server, the deployment must be adjusted so that port 8080 is reachable only from the approved proxy address or network using an approved firewall/private-network boundary.

### 5.2 Start Reverse-Proxy Mode

From the repository root:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  -f deploy/docker/compose.prod.yml `
  -f deploy/docker/compose.proxy.yml `
  up -d
```

Users should open the approved reverse-proxy URL.

They should not access application port 8080 directly.

---

## 6. Common Authentication Requirements

Both production modes require:

```text
WEEKEND_REPORT_AUTH_MODE=production
WEEKEND_REPORT_AUTHORIZED_REVIEWERS=<AUTHORIZED_IDENTITIES>
WEEKEND_REPORT_CSRF_SIGNING_KEY=<SECRET>
WEEKEND_REPORT_CSRF_TTL_SECONDS=3600
```

Production rejects arbitrary:

```text
X-Reviewer
```

because that identity mechanism is development-only.

Browser mutations use reviewer-bound signed CSRF tokens.

The CSRF signing key and local-login session signing key must be different secrets.

---

## 7. Portainer Runtime Variables

Portainer runtime variables are supplied through the runtime environment:

```text
PORTAINER_SITE1_URL
PORTAINER_SITE1_TOKEN
PORTAINER_SITE1_CA_FILE

PORTAINER_SITE2_URL
PORTAINER_SITE2_TOKEN
PORTAINER_SITE2_CA_FILE
```

Do not place real values in template files, documentation, or Git.

Live Portainer collection remains blocked by application preflight until the approved:

* authentication method;
* TLS policy;
* API contract;
* endpoint IDs;
* service expectations;
* timeout policy;
* retry policy

are configured.

---

## 8. Local Development Build

For local development:

```powershell
docker build -t weekend-report:local .
```

The local development image is not automatically equivalent to a verified production release image.

---

## 9. Compose Validation

Validate the common Compose configuration:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  config
```

Validate direct mode:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  -f deploy/docker/compose.prod.yml `
  -f deploy/docker/compose.direct.yml `
  config
```

Validate reverse-proxy mode:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  -f deploy/docker/compose.prod.yml `
  -f deploy/docker/compose.proxy.yml `
  config
```

For syntax-only validation before real secrets exist, safe disposable shell values may be used.

Do not copy `.env.example` to `.env` and leave controlled placeholders unresolved.

Production must not run using literal values such as:

```text
<TBD>
<TO_VERIFY>
<SERVICE_01>
<DASHBOARD_1_ID>
<VERIFY_AUTH_ENUM>
<TO_IMPLEMENT>
UNKNOWN
```

---

## 10. Application Configuration Validation

Before production deployment run:

```powershell
python scripts/validate_config.py --config config
```

Do not replace unknown production facts with guesses merely to make validation pass.

Production preflight validates the selected authentication provider.

For:

```text
trusted_header
```

the trusted identity header configuration is required.

For:

```text
local_login
```

the local user file and session-signing configuration are required.

---

## 11. Stop The Deployment

Use the same Compose file combination that was used to start the deployment.

Direct mode:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  -f deploy/docker/compose.prod.yml `
  -f deploy/docker/compose.direct.yml `
  down
```

Reverse-proxy mode:

```powershell
docker compose `
  --env-file deploy/docker/.env `
  -f deploy/docker/compose.yml `
  -f deploy/docker/compose.prod.yml `
  -f deploy/docker/compose.proxy.yml `
  down
```

---

## 12. Runtime-Only Files

The following are deployment/runtime material and must not be added to the Docker image or committed to Git:

```text
deploy/docker/.env
deploy/docker/secrets/
deploy/docker/tls/
```

The project `.gitignore` and `.dockerignore` must exclude these paths.

---

## 13. Deployment Summary

Direct mode:

```text
compose.yml
      +
compose.prod.yml
      +
compose.direct.yml
      |
      v
HTTPS :8080
local_login
```

Reverse-proxy mode:

```text
compose.yml
      +
compose.prod.yml
      +
compose.proxy.yml
      |
      v
127.0.0.1:8080
trusted_header
      ^
      |
authenticated reverse proxy
```
Only one production authentication mode should be active for a deployment at a time.


