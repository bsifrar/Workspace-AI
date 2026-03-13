#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/env.sh"
load_workspace_env

WORKSPACE_HOST="${WORKSPACE_HOST:-127.0.0.1}"
WORKSPACE_PORT="${WORKSPACE_PORT:-8091}"
WORKSPACE_ADAPTER_MODE="${WORKSPACE_ADAPTER_MODE:-null}"
WORKSPACE_EXTERNAL_BASE_URL="${WORKSPACE_EXTERNAL_BASE_URL:-http://127.0.0.1:8080}"

fetch() {
    local label="$1"
    local url="$2"
    echo "== $label =="
    if curl -fsS "$url" 2>/dev/null; then
        echo ""
    else
        echo "unreachable"
    fi
    echo ""
}

echo "Workspace Status"
echo "Workspace host:   $WORKSPACE_HOST"
echo "Workspace port:   $WORKSPACE_PORT"
echo "Adapter mode:  $WORKSPACE_ADAPTER_MODE"
if [[ "$WORKSPACE_ADAPTER_MODE" == "null" ]]; then
    echo "Mode note:     local-only development mode (no external dependency required)"
fi
echo ""

if [[ "$WORKSPACE_ADAPTER_MODE" == "external" ]]; then
    fetch "External Service Root" "$WORKSPACE_EXTERNAL_BASE_URL/"
    fetch "External Service Memory Status" "$WORKSPACE_EXTERNAL_BASE_URL/smb/status"
fi

fetch "Workspace UI Health" "http://${WORKSPACE_HOST}:${WORKSPACE_PORT}/health"
fetch "Workspace Status" "http://${WORKSPACE_HOST}:${WORKSPACE_PORT}/workspace/status"
fetch "Workspace Adapter Status" "http://${WORKSPACE_HOST}:${WORKSPACE_PORT}/workspace/adapter/status"
fetch "Workspace Settings" "http://${WORKSPACE_HOST}:${WORKSPACE_PORT}/workspace/settings"
