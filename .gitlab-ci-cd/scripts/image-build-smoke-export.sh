#!/bin/sh
set -eu

SHORT_SHA="$(printf '%s' "$CI_COMMIT_SHA" | cut -c1-12)"
export SHORT_SHA

test -f TAG || { echo "TAG file is missing" >&2; exit 1; }
IMAGE_VERSION="$(tr -d '\r\n' < TAG)"
export IMAGE_VERSION
printf '%s' "$IMAGE_VERSION" |
  grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$' ||
  { echo "TAG must contain a semantic version such as v1.0.2" >&2; exit 1; }

WEEKEND_REPORT_BUILD_ID="gl-${CI_PIPELINE_ID}-${CI_JOB_ID}"
WEEKEND_REPORT_APP_VERSION="$IMAGE_VERSION"
LOCAL_IMAGE_TAG="weekend-report:ci-${SHORT_SHA}"
RELEASE_IMAGE_TAG="weekend-report:${IMAGE_VERSION}"
ARCHIVE_BASE="weekend-report_${IMAGE_VERSION}"
RUNTIME_BASE_IMAGE="${WEEKEND_REPORT_RUNTIME_BASE_IMAGE:-weekend-report-runtime-base:python314}"
export WEEKEND_REPORT_BUILD_ID WEEKEND_REPORT_APP_VERSION LOCAL_IMAGE_TAG RELEASE_IMAGE_TAG ARCHIVE_BASE

docker build --pull \
  --build-arg "RUNTIME_BASE_IMAGE=${RUNTIME_BASE_IMAGE}" \
  --label "org.opencontainers.image.title=Weekend Report Automation" \
  --label "org.opencontainers.image.version=${IMAGE_VERSION}" \
  --label "org.opencontainers.image.revision=${CI_COMMIT_SHA}" \
  --label "org.opencontainers.image.source=${CI_PROJECT_URL}" \
  --label "io.weekend-report.build-id=${WEEKEND_REPORT_BUILD_ID}" \
  -t "$LOCAL_IMAGE_TAG" .

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$LOCAL_IMAGE_TAG")"
printf '%s\n' "$IMAGE_ID" | tee image-id.txt

python scripts/ci.py image-smoke --image "$LOCAL_IMAGE_TAG"

docker tag "$LOCAL_IMAGE_TAG" "$RELEASE_IMAGE_TAG"

sh .gitlab-ci-cd/scripts/verify-release-image.sh "$RELEASE_IMAGE_TAG"
sh .gitlab-ci-cd/scripts/export-offline-image.sh "$RELEASE_IMAGE_TAG" "$ARCHIVE_BASE"
sh .gitlab-ci-cd/scripts/publish-image.sh "$RELEASE_IMAGE_TAG" "$SHORT_SHA" "$IMAGE_VERSION"
