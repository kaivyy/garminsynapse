#!/usr/bin/env bash
set -e

# Disable core dump generation to prevent disk exhaustion on crashes
ulimit -c 0

# Enforce isolated virtualenv Python
VENV_DIR="/root/garminsynapse/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtualenv not found at $VENV_DIR" >&2
    exit 1
fi

export PATH="$VENV_DIR/bin:$PATH"
exec "$VENV_DIR/bin/python" "$@"
