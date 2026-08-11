# Weekend Report Automation

Manual-run Weekend Report Automation implemented as a Python/FastAPI web app, persistent worker, PostgreSQL-ready state store, filesystem evidence store, HTML review workflow, frozen review snapshots, and a final PDF generated only after human confirmation.

The repository is intentionally configuration-driven. The default `config/` files are templates with controlled placeholders; they are not production-ready and will fail preflight until real environment values are supplied.

## Architecture

- `web`: FastAPI UI/API for run creation, HTML review, notes, evidence, and final confirmation.
- `worker`: persistent Python process that atomically claims `CREATED` runs and executes the orchestrator.
- `database`: run lifecycle, results, evidence metadata, notes, lock, heartbeat, snapshot/PDF metadata.
- `evidence`: persistent filesystem paths under `runs/<RUN_ID>/`.
- `config`: version-controlled expected state and validation policy.

## Local Development

```powershell
python scripts/validate_config.py --config tests/fixtures/config_valid
python scripts/validate_config.py --config config --expect-invalid
python -m unittest discover -s tests
```

The fixture configuration is safe and does not contact production systems. The production template configuration fails by design because unresolved required values are still present.

## Docker

```powershell
docker compose -f deploy/docker/compose.yml config
docker build -t weekend-report:local .
docker compose -f deploy/docker/compose.yml up
```

The same image runs both web and worker. The FastAPI container never mounts the Docker socket.

## Configuration

Fill YAML files in `config/` using only verified environment values. Secrets should be supplied through `.env`, Docker secrets, or an approved secret manager; never commit credentials. Unknown required values must remain `"<TBD>"` or `"<TO_VERIFY>"` and will block real runs.

## Review And Finalization

Reviewers inspect HTML module pages, raw evidence, module notes, result notes, and Splunk dashboard notes. Final confirmation freezes all automated results and all saved notes into `runs/<RUN_ID>/final/review_snapshot.json`; the final PDF is rendered from that immutable snapshot.
