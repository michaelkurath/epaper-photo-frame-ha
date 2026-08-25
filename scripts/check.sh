#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${project_root}/epaper_photo_frame/app"

python -m compileall -q \
  "${project_root}/epaper_photo_frame/app" \
  "${project_root}/tests"
python -m unittest discover -s "${project_root}/tests" -v

if command -v g++ >/dev/null 2>&1; then
  bash "${project_root}/scripts/check-firmware.sh"
fi

if command -v node >/dev/null 2>&1; then
  javascript_file="$(mktemp --suffix=.js)"
  trap 'rm -f "${javascript_file}"' EXIT
  sed -n '/<script>/,/<\/script>/p' \
    "${project_root}/epaper_photo_frame/app/frame_app/static/index.html" \
    | sed '1d;$d' > "${javascript_file}"
  node --check "${javascript_file}"
fi
