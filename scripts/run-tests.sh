#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Run both unit-test suites and emit one machine-readable summary line.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "/c/Users/yuezh/miniforge3/envs/py312/python.exe" ]]; then
  PYTHON_BIN="/c/Users/yuezh/miniforge3/envs/py312/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  PYTHON_BIN=""
fi

python_exit=127
node_exit=127

if [[ -n "$PYTHON_BIN" ]]; then
  (cd "$ROOT" && "$PYTHON_BIN" -B -m pytest packages/pypi/tests -q)
  python_exit=$?
else
  echo "error: no Python interpreter found; set PYTHON or install python3" >&2
fi

if command -v node >/dev/null 2>&1; then
  (cd "$ROOT/packages/npm" && node --test)
  node_exit=$?
else
  echo "error: node was not found on PATH" >&2
fi

status="fail"
exit_code=1
if [[ $python_exit -eq 0 && $node_exit -eq 0 ]]; then
  status="pass"
  exit_code=0
fi

printf '{"event":"test-summary","status":"%s","python_exit":%d,"node_exit":%d}\n' \
  "$status" "$python_exit" "$node_exit"
exit "$exit_code"
