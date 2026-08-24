#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${project_root}/epaper_photo_frame/app"

python -m compileall -q \
  "${project_root}/epaper_photo_frame/app" \
  "${project_root}/tests"
python -m unittest discover -s "${project_root}/tests" -v

