#!/usr/bin/env sh
# Run a tool from apps/api/.venv, creating or refreshing the virtualenv when needed,
# so `npm run dev` / `npm test` work straight after a clone with only Python 3.12+ installed.
#
# Turborepo runs a `setup` task first, but tools can also be started by hand in parallel,
# so setup takes a lock: two processes creating the same venv at once fail with
# "File exists" (found by testing a fresh clone).
set -eu
cd "$(dirname "$0")/.."

needs_setup() { [ ! -x .venv/bin/python ] || [ pyproject.toml -nt .venv/.installed ]; }

if needs_setup; then
  lock=.venv.lock
  waited=0
  until mkdir "$lock" 2>/dev/null; do
    waited=$((waited + 1))
    if [ "$waited" -gt 600 ]; then
      echo "Timed out waiting for $lock; remove it if no other setup is running." >&2
      exit 1
    fi
    sleep 1
  done
  trap 'rmdir "$lock" 2>/dev/null || true' EXIT INT TERM

  if needs_setup; then # another process may have finished it while we waited
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

  rmdir "$lock"
  trap - EXIT INT TERM
fi

tool="$1"
shift
exec ".venv/bin/$tool" "$@"
