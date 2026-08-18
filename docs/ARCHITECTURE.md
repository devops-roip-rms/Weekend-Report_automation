# Architecture

The application is manual-run only. FastAPI creates run records after configuration preflight, a persistent worker atomically claims `CREATED` runs, collectors gather actual state/evidence, validators generate immutable automated findings, and reviewers use HTML pages to add module/result/Splunk/general notes.

## Runtime Boundary

- Health endpoints are public.
- In production, main pages, run pages, module/review pages, evidence endpoints, evidence downloads, and final-report access require an authenticated and authorized reviewer.
- Development mode allows local convenience identity. Production rejects arbitrary `X-Reviewer` and requires an explicitly configured provider such as `trusted_header` behind an approved reverse-proxy/auth boundary.
- Browser mutations use reviewer-bound signed CSRF tokens created from `WEEKEND_REPORT_CSRF_SIGNING_KEY`. A permanent shared public CSRF token is not supported.

## Run And Worker Model

Run creation uses a database-backed single-run lock. PostgreSQL uses explicit row locks/atomic updates, and SQLite uses `BEGIN IMMEDIATE` for local testing. Any run in `CREATED`, `RUNNING`, or `RECOVERY_REQUIRED` blocks a new run.

The worker never replays an uncertain Recording start/stop operation. Stale non-Recording runs fail without replay. Stale Recording runs enter `RECOVERY_REQUIRED` and require explicit human resolution before a new run can be created.

## Evidence And Review

Every collector/check can persist raw evidence and every stored result gets normalized evidence with checksum metadata. Evidence paths are stored relative to the evidence root with portable separators. Review UI evidence links are protected and must reference registered database evidence.

Reviewer notes are additive and never rewrite automated statuses. The frozen review snapshot includes all results, all evidence references, all module/result/Splunk/general notes, site summaries, module summaries, parity summaries, reviewer decision, and timestamp.

## Module Integration Boundaries

Collectors gather actual state; validators compare it to expected YAML. Fixture mode is explicit.
Live mode is blocked until approved environment information is supplied. There is no silent
live-to-fixture fallback.

### Portainer

Portainer is strictly read-only and limited to Docker Swarm Services. Expected configuration uses a
common service inventory, defaults, and per-site overrides.

```text
Weekend Report Worker
  |
  +-- HTTPS READ ONLY --> Portainer Site 1 Server/API
  |                         |
  |                         v
  |                       Docker Swarm
  |                         |
  |                         v
  |                       Swarm Services
  |                         |
  |                         +-- tasks inspected only when needed for service health/state
  |
  +-- HTTPS READ ONLY --> Portainer Site 2 Server/API
                            |
                            v
                          Docker Swarm
                            |
                            v
                          Swarm Services
                            |
                            +-- tasks inspected only when needed for service health/state
```

The application communicates with the Portainer Server/API. The Portainer Agent remains part of
Portainer's own environment connectivity and is not a direct Weekend Report monitoring target.
The app does not expose Portainer start/stop/restart/scale/update/delete/redeploy/stack/container
mutation operations.

Validation sequence:

```text
Site 1 actual state -> Site 1 expected-state validation
Site 2 actual state -> Site 2 expected-state validation
                                      |
                                      v
                            Cross-site parity
```

### RabbitMQ

RabbitMQ expected state uses common vhost/queue/exchange/binding topology, defaults, and per-site
overrides. Actual topology and metrics must come from the RabbitMQ Management API or fixture actuals.
Required topology defaults to true; optional topology must be explicit.

### Recording

Recording uses an existing-device workflow only. The application must not create or delete devices.
The workflow selects a suitable existing non-recording device, records WebApp/backend baselines,
starts recording on the same device, verifies WebApp/backend increments, stops the same device,
verifies restoration, and records cleanup/recovery evidence. A crash or unknown state after start
requires `RECOVERY_REQUIRED`; the worker must not replay the state-changing call.

### Database

The database module is an adapter boundary for the owner-supplied existing sync function. The
project expects structured create/replicate/delete/replicate/cleanup booleans and errors. It does
not rewrite the temp-table sync algorithm.

### Infrastructure

Infrastructure collection is read-only. Live SSH is blocked until targets, credentials, host-key
policy, and command contracts are approved. Validators cover filesystems, NFS mappings/source/
usability/utilization, and Chrony synchronization/source/offset.

### Parity

Parity compares explicitly configured normalized fields after site validation. It never hides
expected-state failures, so both sites being identically wrong still leaves the site findings as
FAIL/ERROR.

## Finalization

`config/rules.yml` drives aggregation, module unavailability behavior, and APPROVE readiness. APPROVE can require required modules completed, Splunk dashboards reviewed, Splunk notes, module/result/general notes, manual-review acknowledgments, Recording cleanup acknowledgments, and status-specific approval policy. REJECT follows `rules.review.reject_allowed`.

Final confirmation freezes `runs/<RUN_ID>/final/review_snapshot.json` and then generates exactly one final PDF from that immutable snapshot. The PDF route serves only the recorded run-owned final PDF path and rejects traversal or arbitrary filesystem paths.

## Portable Traceability

Every run, snapshot, and final PDF records:

- `application_version` from `WEEKEND_REPORT_APP_VERSION`
- `build_id` from `WEEKEND_REPORT_BUILD_ID`
- deterministic `configuration_hash` from the effective YAML files

`git_commit` is optional future traceability and is `"<NOT_APPLICABLE>"` when Git metadata is unavailable. GitLab is not a runtime dependency.

The default configuration intentionally contains placeholders and blocks real execution.
