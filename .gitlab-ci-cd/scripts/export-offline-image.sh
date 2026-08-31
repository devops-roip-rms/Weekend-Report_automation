#!/bin/sh
set -e
set -o pipefail

RELEASE_IMAGE_TAG="$1"
ARCHIVE_BASE="$2"

mkdir -p dist

docker save "$RELEASE_IMAGE_TAG" | gzip -1 > "dist/${ARCHIVE_BASE}.tar.gz"

cd dist
sha256sum "${ARCHIVE_BASE}.tar.gz" > "${ARCHIVE_BASE}.tar.gz.sha256"
cd ..

cp image-id.txt dist/image-id.txt
cp release-image-id.txt dist/release-image-id.txt
