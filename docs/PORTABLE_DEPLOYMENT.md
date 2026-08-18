# Portable Deployment

This project is portable as a complete `weekend-report` folder. GitLab may be introduced later for source control and optional CI/CD, but it is not required for runtime, validation, or deployment.

## Lifecycle

Development PC -> validated `weekend-report` folder -> external hard disk -> target PC -> optional GitLab repository/import -> create real `.env` and secret inputs -> complete/verify environment YAML -> validate configuration -> Docker build -> Docker Compose startup -> controlled acceptance testing -> production operation.

## Target-PC Prerequisites

- Docker Engine and Docker Compose plugin.
- Network access to approved production systems only after configuration is supplied and approved.
- Approved reverse proxy/auth boundary if using `WEEKEND_REPORT_AUTH_PROVIDER=trusted_header`.
- Persistent PostgreSQL storage location or Docker volume.
- Persistent evidence storage location or Docker volume.
- Approved certificate/private-key locations if TLS, SSH, or internal PKI is used.

## Transfer

Transfer the complete `weekend-report` folder, including:

- `app/`
- `config/`
- `deploy/`
- `docs/`
- `scripts/`
- `tests/`
- `.env.example`
- `.gitignore`
- `.gitlab-ci.yml`
- `Dockerfile`
- `pyproject.toml`
- `requirements.txt`
- `README.md`

Do not transfer generated local runtime state unless intentionally backing up a run:

- `.env`
- Python virtual environments
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- local SQLite data files
- local `runs/` evidence from development unless needed as an audit artifact
- real certificates, credentials, or private keys embedded in the project tree

## Secrets And Runtime Values

Create real secrets separately on the target PC through a non-committed `.env`, Docker secrets, or an approved secret mechanism. `env.example` files are templates only.

Required runtime values include:

- `POSTGRES_PASSWORD`
- `WEEKEND_REPORT_APP_VERSION`
- `WEEKEND_REPORT_BUILD_ID`
- `WEEKEND_REPORT_AUTH_MODE=production`
- `WEEKEND_REPORT_AUTH_PROVIDER`
- `WEEKEND_REPORT_AUTH_TRUSTED_HEADER` if `trusted_header` is approved
- `WEEKEND_REPORT_AUTHORIZED_REVIEWERS`
- `WEEKEND_REPORT_CSRF_SIGNING_KEY`
- integration-specific tokens/password references only after each live integration is approved

Never leave `"<TBD>"`, `"<TO_VERIFY>"`, or `UNKNOWN` as a runtime password, token, app version, build ID, or auth value.

## Configuration

Complete `config/*.yml` with verified production values only. Keep unresolved facts as controlled placeholders until the owner supplies them. Real runs remain blocked while required placeholders are present.

Validate before startup:

```powershell
python scripts/validate_config.py --config tests/fixtures/config_valid
python scripts/validate_config.py --config config --expect-invalid
python -m unittest discover -s tests
python scripts/smoke_local.py
```

After production YAML is completed, run:

```powershell
python scripts/validate_config.py --config config
```

## Docker Build And Compose

From the project root:

```powershell
docker build -t weekend-report:local .
docker compose -f deploy/docker/compose.yml config
docker compose -f deploy/docker/compose.yml up -d
```

If Compose config validation is run before real `.env` exists, provide safe local dummy values in the shell for syntax validation only. Do not use `env.example` as a real `.env`.

## Startup Validation

- Confirm PostgreSQL health.
- Confirm web health endpoint.
- Confirm protected pages reject unauthenticated production access.
- Confirm an authorized reviewer can load the main page through the approved auth boundary.
- Confirm default production templates still fail preflight until real values are supplied.
- Confirm no live Portainer/RabbitMQ/SSH/Database/DOCTOR/Recording calls occur until that integration is explicitly configured and approved.

## Evidence And Backups

Evidence is stored under `WEEKEND_REPORT_EVIDENCE_ROOT` or the Docker `evidence` volume. Back up PostgreSQL and evidence together so run metadata and files remain consistent.

Recommended backup set:

- PostgreSQL database dump or volume snapshot.
- Evidence volume/root snapshot.
- Completed `config/` directory used for the run.
- Final PDFs and frozen snapshots if copied to archival storage.

Retention, archive destinations, and deletion policies are still environment inputs and must be approved before production use.

## Upgrade And Rollback

For upgrades, copy the new validated folder to the target PC, set a new `WEEKEND_REPORT_APP_VERSION` and `WEEKEND_REPORT_BUILD_ID`, run local quality commands, rebuild the Docker image, and restart Compose.

For rollback, restore the previous folder/image plus matching `.env`, configuration, PostgreSQL backup, and evidence backup. The configuration hash in run metadata identifies which effective config produced a report.

## Troubleshooting

- Preflight fails: replace only verified production values; leave unknowns as placeholders until approved.
- Production page returns 401/403: check auth provider, trusted header, and authorized reviewers.
- Production mutation returns 403: reload the HTML page to get a fresh reviewer-bound CSRF token; verify signing key/TTL.
- Compose config fails: required runtime variable is missing; create a real `.env` or approved secret source.
- New run blocked by `RECOVERY_REQUIRED`: open the affected run page, review evidence/instructions, perform approved cleanup, and submit an explicit recovery resolution note.
- Final PDF missing: check the run state and recorded final PDF path/checksum; PDFs are generated only after final confirmation.

## Future GitLab Onboarding

GitLab is optional. If the folder is imported later, keep CI aligned with the same local commands in this document. Do not schedule Weekend Report execution through GitLab unless a separate approved design is created. Git commit SHA may be recorded as optional additional traceability after Git metadata exists, but `application_version`, `build_id`, and `configuration_hash` remain mandatory.
