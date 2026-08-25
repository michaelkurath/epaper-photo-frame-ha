#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
test_binary="$(mktemp)"
trap 'rm -f "${test_binary}"' EXIT

g++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  "${project_root}/firmware/tests/test_firmware_core.cpp" \
  -o "${test_binary}"
"${test_binary}"
