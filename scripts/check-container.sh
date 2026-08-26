#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
image_name="epaper-photo-frame-ha:ci"
container_name="epaper-photo-frame-ha-ci"
host_port="18080"

cleanup() {
  docker rm -f "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build \
  --build-arg BUILD_ARCH=amd64 \
  --tag "${image_name}" \
  "${project_root}/epaper_photo_frame"

docker run --detach \
  --name "${container_name}" \
  --publish "127.0.0.1:${host_port}:8080" \
  --env EPAPER_ALBUM_URL="https://photos.google.com/share/ci?key=test" \
  --env EPAPER_API_TOKEN="0123456789abcdef" \
  "${image_name}" >/dev/null

for _ in $(seq 1 45); do
  if curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/health" \
    | grep --quiet '"status":"ok"'; then
    exit 0
  fi
  sleep 1
done

docker logs "${container_name}"
exit 1
