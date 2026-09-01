#!/bin/sh
set -eu

AUDIT_DIR="/opt/weekend-report-ci"
REQUIREMENTS_FILE="requirements.txt"

ACTUAL_HASH="$(sha256sum "$REQUIREMENTS_FILE" | cut -d ' ' -f 1)"
AUDITED_HASH="$(cat "$AUDIT_DIR/requirements.sha256")"

if [ "$ACTUAL_HASH" != "$AUDITED_HASH" ]; then
    echo "ERROR: requirements.txt does not match the dependency set audited in the CI image."
    echo "Rebuild the CI image on the Internet-connected build machine."
    exit 1
fi

if [ ! -s "$AUDIT_DIR/pip-audit.json" ]; then
    echo "ERROR: baked pip-audit report is missing."
    exit 1
fi

if [ ! -s "$AUDIT_DIR/pip-audit-passed-at" ]; then
    echo "ERROR: baked pip-audit success marker is missing."
    exit 1
fi

echo "Offline dependency audit verification passed."
echo "Online vulnerability audit completed at:"
cat "$AUDIT_DIR/pip-audit-passed-at"