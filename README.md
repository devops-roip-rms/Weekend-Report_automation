# Weekend Report Automation

Manual-run Weekend Report Automation implemented as a Python/FastAPI web app, persistent worker, PostgreSQL-ready state store, filesystem evidence store, HTML review workflow, frozen review snapshots, and a final PDF generated only after human confirmation.

The repository is intentionally configuration-driven. The default `config/` files are templates with controlled placeholders; they are not production-ready and will fail preflight until real environment values are supplied.

This project is currently developed as a local folder. GitLab/Git may be added later for source control or CI/CD, but Git metadata is not required to build, test, run, deploy, or trace a Weekend Report run.

## Architecture

- `web`: FastAPI UI/API for run creation, HTML review, notes, evidence, and final confirmation.
- `worker`: persistent Python process that atomically claims `CREATED` runs and executes the orchestrator.
- `database`: run lifecycle, results, evidence metadata, notes, lock, heartbeat, snapshot/PDF metadata.
- `evidence`: persistent filesystem paths under `runs/<RUN_ID>/`.
- `config`: expected state and validation policy carried with the project folder.
- `traceability`: every run records `application_version`, `build_id`, and deterministic `configuration_hash`; `git_commit` is optional and defaults to `"<NOT_APPLICABLE>"` when Git metadata is unavailable.

## Local Development

```powershell
python scripts/validate_config.py --config tests/fixtures/config_valid
python scripts/validate_config.py --config config --expect-invalid
python -m unittest discover -s tests
python scripts/smoke_local.py
```

The fixture configuration is safe and does not contact production systems. The production template configuration fails by design because unresolved required values are still present.

## Docker

Set real runtime values in a non-committed `.env`, Docker secret, or approved secret mechanism before Compose startup. For local Compose syntax validation, provide safe dummy values in the shell rather than copying `env.example` as a real secret file.

The same image runs both web and worker. The FastAPI container never mounts the Docker socket.
`deploy/docker/env.example` is a template only; Compose reads real runtime values from a
non-committed `.env`, Docker secrets, or another approved mechanism. `POSTGRES_PASSWORD`,
`WEEKEND_REPORT_APP_VERSION`, `WEEKEND_REPORT_BUILD_ID`, production auth settings, and
`WEEKEND_REPORT_CSRF_SIGNING_KEY` must be supplied at runtime and must not be left as
controlled placeholders.

## Configuration

Fill YAML files in `config/` using only verified environment values. Secrets should be supplied through `.env`, Docker secrets, or an approved secret manager; never put credentials in YAML or docs. Unknown required values must remain `"<TBD>"` or `"<TO_VERIFY>"` and will block real runs.

The Portainer integration is implemented generically for two read-only Portainer Server/API
connections that observe Docker Swarm Services only. Local tests use fixture mode. Live Portainer
mode remains blocked until real URLs, authentication, TLS policy, endpoint IDs, API contract,
service inventory, replica/image/health expectations, and parity exceptions are supplied and
approved. The application does not expose Portainer mutation operations.

## Review And Finalization

In production, all pages except health checks require authenticated and authorized access through the configured auth provider. Browser mutations use reviewer-bound signed CSRF tokens, not a permanent shared public token.

Reviewers inspect HTML module pages, raw evidence, module notes, result notes, and Splunk dashboard notes. APPROVE enforces `config/rules.yml` finalization readiness policy. REJECT follows its explicit policy. Final confirmation freezes all automated results and all saved notes into `runs/<RUN_ID>/final/review_snapshot.json`; the final PDF is rendered from that immutable snapshot and served only through the protected run-owned final-report route.
