#!/bin/sh
set -eu

AUDIT_DIR=".gitlab-ci-cd/audit"
REQUIREMENTS_FILE="requirements.txt"

REQUIREMENTS_HASH_FILE="$AUDIT_DIR/requirements.sha256"
AUDIT_REPORT="$AUDIT_DIR/pip-audit.json"
AUDIT_TIMESTAMP="$AUDIT_DIR/pip-audit-passed-at"

for file in \
    "$REQUIREMENTS_HASH_FILE" \
    "$AUDIT_REPORT" \
    "$AUDIT_TIMESTAMP"
do
    if [ ! -s "$file" ]; then
        echo "ERROR: required offline audit evidence is missing: $file"
        exit 1
    fi
done

ACTUAL_HASH="$(sha256sum "$REQUIREMENTS_FILE" | cut -d ' ' -f 1)"
AUDITED_HASH="$(tr -d '\r\n' < "$REQUIREMENTS_HASH_FILE")"

if [ "$ACTUAL_HASH" != "$AUDITED_HASH" ]; then
    echo "ERROR: requirements.txt has changed since the online dependency audit."
    echo "Regenerate .gitlab-ci-cd/audit on the Internet-connected machine."
    exit 1
fi

python - "$AUDIT_REPORT" <<'PY'
import json
import sys

report_path = sys.argv[1]

with open(report_path, encoding="utf-8") as handle:
    report = json.load(handle)

# pip-audit JSON is normally a top-level dependency list.
# Accept the object form as well for compatibility with other/newer report layouts.
if isinstance(report, list):
    dependencies = report
elif isinstance(report, dict) and isinstance(report.get("dependencies"), list):
    dependencies = report["dependencies"]
else:
    raise SystemExit("ERROR: unexpected pip-audit JSON report structure")

vulnerabilities = []

for dependency in dependencies:
    if not isinstance(dependency, dict):
        continue

    package = dependency.get("name", "<unknown>")

    for vulnerability in dependency.get("vulns") or []:
        if isinstance(vulnerability, dict):
            vulnerability_id = vulnerability.get("id", "<unknown>")
        else:
            vulnerability_id = "<unknown>"

        vulnerabilities.append((package, vulnerability_id))

if vulnerabilities:
    print("ERROR: dependency audit contains known vulnerabilities:")
    for package, vulnerability_id in vulnerabilities:
        print(f"  {package}: {vulnerability_id}")
    raise SystemExit(1)

print("Audit report contains no known vulnerabilities.")
PY

echo "requirements.txt matches the audited dependency set."
echo "Online dependency audit completed at:"
cat "$AUDIT_TIMESTAMP"
echo
echo "Offline dependency audit verification passed."