#!/usr/bin/env sh
# Run a tool from apps/api/.venv, creating or refreshing the virtualenv when needed,
# so `npm run dev` / `npm test` work straight after a clone with only Python 3.12+ installed.
set -eu
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ] || [ pyproject.toml -nt .venv/.installed ]; then
  PY=$(command -v python3.12 || command -v python3.13 || command -v python3 || true)
  if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    echo "GridShift API needs Python 3.12 or newer on PATH." >&2
    exit 1
  fi
  [ -x .venv/bin/python ] || "$PY" -m venv .venv
  echo "Installing API dependencies into apps/api/.venv ..." >&2
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -e ".[dev]"
  touch .venv/.installed
fi

tool="$1"; shift
exec ".venv/bin/$tool" "$@"
