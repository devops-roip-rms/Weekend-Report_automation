# Validation Catalog

Every validation must define source of truth, expected state, comparison rule, status semantics, and evidence. Values marked `"<TBD>"` or `"<TO_VERIFY>"` are not production-ready.

## Rule: portainer.service.exists

- Module: Portainer
- Actual source of truth: Portainer Management API service listing per site
- Expected source/value: `config/portainer_expected.yml` `sites.<site>.services[].name`
- Comparison rule: required service name must exist in actual service set for the same site
- PASS: required service exists
- WARNING: not used unless explicitly configured later
- FAIL: required service missing
- ERROR: API cannot be queried or parsed reliably
- Evidence requirement: raw API JSON and normalized service JSON
- Parity behavior: none; separate parity rules may compare configured fields only

## Rule: portainer.service.replicas

- Actual source of truth: Portainer API desired/running/healthy task state
- Expected source/value: `config/portainer_expected.yml` expected and healthy replicas
- Comparison rule: running replicas equal expected and healthy replicas meet requirement
- PASS: running and healthy counts satisfy expected state
- WARNING: only if an approved grace policy is configured
- FAIL: running or healthy replicas below expected requirement
- ERROR: state cannot be collected reliably
- Evidence requirement: raw API JSON and normalized result
- Parity behavior: parity never masks failed site health

## Rule: doctor.manual_review

- Module: DOCTOR
- Actual source of truth: configured manual review link/instructions
- Expected source/value: `config/doctor.yml`
- Comparison rule: no automated decision in manual mode
- PASS: not produced automatically in manual mode
- WARNING: not produced automatically
- FAIL: not produced automatically
- ERROR: manual review configuration invalid
- MANUAL_REVIEW: DOCTOR mode is manual
- Evidence requirement: reviewer notes and optional link/instructions
- Parity behavior: only if explicitly configured after real interface is known

## Rule: rabbitmq.queue.backlog

- Actual source of truth: RabbitMQ Management API queue metrics
- Expected source/value: `config/rabbitmq_expected.yml` warning/critical thresholds
- Comparison rule: configured metric compared to warning and critical threshold
- PASS: metric is below warning
- WARNING: warning <= metric < critical
- FAIL: metric >= critical
- ERROR: API cannot be queried or metric absent
- Evidence requirement: queues JSON and normalized result
- Parity behavior: dynamic backlog parity is disabled unless explicitly approved

## Rule: rabbitmq.topology

- Actual source of truth: RabbitMQ Management API vhosts, queues, exchanges, bindings
- Expected source/value: `config/rabbitmq_expected.yml`
- Comparison rule: required objects and configured properties must match
- PASS: required object/property exists and matches
- WARNING: only for explicitly configured optional mismatches
- FAIL: required object missing or property mismatch
- ERROR: topology cannot be collected reliably
- Evidence requirement: vhosts, queues, exchanges, bindings JSON
- Parity behavior: compare only configured stable topology fields

## Rule: recording.functional

- Actual source of truth: approved WebApp01/WebApp02 workflow plus backend source
- Expected source/value: `config/recording.yml`
- Comparison rule: exact identity `WEEKEND_TEST_<SITE>_<RUN_ID>` must be created, propagated, and verified
- PASS: exact identity exists, baseline behavior is satisfied, backend validation passes
- WARNING: only if an approved delayed-but-acceptable rule is configured
- FAIL: create/propagation/backend validation fails
- ERROR: workflow cannot be evaluated reliably
- Evidence requirement: screenshots, trace, backend bounded evidence, normalized result
- Parity behavior: none unless explicitly configured

## Rule: recording.cleanup

- Actual source of truth: approved cleanup verification source
- Expected source/value: `config/recording.yml`
- Comparison rule: exact synthetic object is gone and baseline restored where reliable
- PASS: cleanup confirmed
- FAIL: cleanup failed or cannot confirm absence where required
- ERROR: cleanup verification source unavailable
- Evidence requirement: after-delete screenshot/state and normalized result
- Parity behavior: none

## Rule: infrastructure.filesystem.utilization

- Actual source of truth: approved SSH command output, usually `df`
- Expected source/value: `config/servers.yml`
- Comparison rule: utilization compared to warning/critical thresholds
- PASS: utilization < warning
- WARNING: warning <= utilization < critical
- FAIL: utilization >= critical or required mount missing
- ERROR: command/parse cannot be evaluated reliably
- Evidence requirement: full raw command output and normalized parse
- Parity behavior: configured separately; missing mount never passes because parity matches

## Rule: infrastructure.chrony

- Actual source of truth: approved date/timedatectl/chronyc command outputs
- Expected source/value: `config/servers.yml`
- Comparison rule: timezone/source/sync/offset checked against explicit config
- PASS: synchronization and offset satisfy config
- WARNING: offset in configured warning range
- FAIL: unsynchronized, wrong source, or critical offset
- ERROR: commands cannot be evaluated reliably
- Evidence requirement: raw command outputs and normalized parse
- Parity behavior: configured separately

## Rule: database.script_contract

- Actual source of truth: owner-supplied DB test command/script output
- Expected source/value: `config/rules.yml` exit-code/output contract
- Comparison rule: exit code and output semantics match documented contract
- PASS/WARNING/FAIL/ERROR: as defined by approved contract
- Evidence requirement: command, exit code, stdout, stderr, duration, timeout
- Parity behavior: only fields explicitly configured after script semantics are known

## Rule: splunk.dashboard_review

- Actual source of truth: human review of configured Splunk dashboard URL
- Expected source/value: `config/splunk_dashboards.yml`
- Comparison rule: dashboard has stable ID/name/URL and independent note field
- MANUAL_REVIEW: dashboard requires human review
- ERROR: dashboard definition invalid
- Evidence requirement: saved Splunk dashboard note per dashboard
- Parity behavior: not applicable
