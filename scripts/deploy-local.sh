#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/mounted-home-assistant-local_apps" >&2
  exit 2
fi

addons_root="$1"
if [[ ! -d "${addons_root}" ]]; then
  echo "Target directory does not exist: ${addons_root}" >&2
  exit 2
fi

project_root="$(cd "$(dirname "$0")/.." && pwd)"
target="${addons_root%/}/epaper_photo_frame"
mkdir -p "${target}"
cp -R "${project_root}/epaper_photo_frame/." "${target}/"

echo "Copied App to ${target}"
echo "Refresh the local Apps section in Home Assistant, then rebuild the App."
