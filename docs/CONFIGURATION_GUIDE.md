# Configuration Guide

Use `.env` or approved secrets for runtime URLs, credentials, and secret references. Use YAML files for expected state, topology, thresholds, parity rules, dashboard definitions, module policy, and validation semantics.

Controlled placeholders:

- `"<TBD>"`: required information not supplied.
- `"<TO_VERIFY>"`: candidate value not verified.
- `"<NOT_APPLICABLE>"`: only where schema explicitly permits.

Enabled required validators with `"<TBD>"` or `"<TO_VERIFY>"` fail preflight. The default `config/` directory is a production template and is expected to fail until completed. Use `tests/fixtures/config_valid` only for local safe tests.
