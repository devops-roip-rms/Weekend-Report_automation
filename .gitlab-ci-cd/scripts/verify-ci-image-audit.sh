#!/bin/sh
set -eu

EVIDENCE_DIR="/usr/local/share/weekend-report-ci"

for file in requirements.sha256 requirements-dev.sha256 pip-audit.json pip-audit-passed-at; do
  test -s "${EVIDENCE_DIR}/${file}" || {
    echo "Missing CI audit evidence: ${EVIDENCE_DIR}/${file}" >&2
    exit 1
  }
done

CURRENT_RUNTIME_HASH="$(sha256sum requirements.txt | cut -d ' ' -f 1)"
BAKED_RUNTIME_HASH="$(cat "${EVIDENCE_DIR}/requirements.sha256")"

if [ "$CURRENT_RUNTIME_HASH" != "$BAKED_RUNTIME_HASH" ]; then
  echo "requirements.txt differs from the dependency set audited in weekend-report-ci:python314" >&2
  echo "Rebuild and transfer Dockerfile.ci before using this source revision in closed GitLab." >&2
  exit 1
fi

CURRENT_DEV_HASH="$(sha256sum requirements-dev.txt | cut -d ' ' -f 1)"
BAKED_DEV_HASH="$(cat "${EVIDENCE_DIR}/requirements-dev.sha256")"

if [ "$CURRENT_DEV_HASH" != "$BAKED_DEV_HASH" ]; then
  echo "requirements-dev.txt differs from the tooling set baked into weekend-report-ci:python314" >&2
  echo "Rebuild and transfer Dockerfile.ci before using this source revision in closed GitLab." >&2
  exit 1
fi

python - <<'PY'
import json
from pathlib import Path
p = Path('/usr/local/share/weekend-report-ci/pip-audit.json')
json.loads(p.read_text(encoding='utf-8'))
PY

printf 'PASS: CI image dependency audit evidence verified (%s)\n' "$(cat "${EVIDENCE_DIR}/pip-audit-passed-at")"
