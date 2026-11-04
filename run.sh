#!/usr/bin/env bash
# Starts the agent with the API key from macOS Keychain, so the key never sits in a file the agent could read.
# Any flags are passed on to agent.py, e.g. ./run.sh --disable g1
# No need to activate the venv first, and this works from any folder.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! API_KEY="$(security find-generic-password -a "$USER" -s anthropic-api-key -w 2>/dev/null)"; then
    echo "Couldn't read the API key from Keychain. To store it, run:" >&2
    echo "  security add-generic-password -U -a \"\$USER\" -s anthropic-api-key -w" >&2
    exit 1
fi

# Set for this one process only, then hand over to Python
ANTHROPIC_API_KEY="$API_KEY" exec "$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/agent.py" "$@"
