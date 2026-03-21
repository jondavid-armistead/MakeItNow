#!/usr/bin/env sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m makeitnow.installer "$@"
