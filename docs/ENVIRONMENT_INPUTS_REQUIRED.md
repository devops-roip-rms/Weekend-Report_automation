# Environment Inputs Required

Production execution is blocked until the owner supplies and approves the values below.

## Portainer

URLs, versions/API contract, authentication, endpoint/environment IDs, expected services, expected replicas, health requirements, image comparison policy, parity fields, timeouts, retries.

## DOCTOR

API/manual mode, API contract if used, auth, schema, expected state, manual review link/instructions, note/acknowledgment policy.

## RabbitMQ

Management API URLs, credentials, vhosts, queues, exchanges, bindings, durability, min consumers, backlog thresholds, alarm policy, parity behavior.

## Recording

WebApp01/WebApp02 URLs, auth, stable selectors or API contract, safe synthetic values, create/delete workflow, propagation timeout, backend source, gateway target, cleanup verification, recovery behavior.

## Infrastructure

Server inventory, SSH account, secret references, host-key policy, approved commands, expected filesystems, NFS mappings, thresholds, timezone, NTP/Chrony sources, offset limits.

## Database

Execution host, script path, command/arguments, environment, credentials, timeout, exit-code contract, stdout/stderr semantics, evidence contract.

## Splunk

Dashboard IDs, names, URLs, order, required review policy, note requirements, human review instructions.

## Authentication

Organization-approved authentication and reviewer authorization model.

## Storage

Evidence root, NFS/object storage approval, retention, backups, read/delete permissions.

## Email/Archive

Enablement, destinations, recipients, sender, subject/body, retention, checksum verification, failure behavior.
