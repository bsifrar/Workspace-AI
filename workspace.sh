#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT_DIR/workspace_ai"

ensure_safe_repo_root() {
  local repo_root
  repo_root="$(git -C "$ROOT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "$repo_root" && "$repo_root" == "$HOME" && "${WORKSPACE_ALLOW_HOME_REPO:-0}" != "1" ]]; then
    echo "Error: Git repo root resolves to your home directory: $repo_root" >&2
    echo "This is almost certainly accidental. Refusing to run Workspace from a home-level repo." >&2
    echo "If you really intend this, rerun with WORKSPACE_ALLOW_HOME_REPO=1" >&2
    exit 1
  fi
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  install)
    exec "$APP_DIR/scripts/install.sh" "$@"
    ;;
  start|status|smoke)
    ensure_safe_repo_root
    export WORKSPACE_ADAPTER_MODE="${WORKSPACE_ADAPTER_MODE:-null}"
    case "$cmd" in
      start) exec "$APP_DIR/scripts/start.sh" "$@" ;;
      status) exec "$APP_DIR/scripts/status.sh" "$@" ;;
      smoke) exec "$APP_DIR/scripts/smoke_test.sh" "$@" ;;
    esac
    ;;
  start-external|status-external|smoke-external)
    ensure_safe_repo_root
    export WORKSPACE_ADAPTER_MODE=external
    case "$cmd" in
      start-external) exec "$APP_DIR/scripts/start.sh" "$@" ;;
      status-external) exec "$APP_DIR/scripts/status.sh" "$@" ;;
      smoke-external) exec "$APP_DIR/scripts/smoke_test.sh" "$@" ;;
    esac
    ;;
  stop)
    exec "$APP_DIR/scripts/stop.sh" "$@"
    ;;
  secrets)
    exec "$APP_DIR/scripts/check_secrets.sh" "$@"
    ;;
  help|-h|--help)
    cat <<'EOF'
Workspace-AI launcher

Usage:
  ./workspace.sh install
  ./workspace.sh start
  ./workspace.sh stop
  ./workspace.sh status
  ./workspace.sh smoke
  ./workspace.sh secrets
  ./workspace.sh start-external
  ./workspace.sh status-external
  ./workspace.sh smoke-external

Defaults:
  start/status/smoke run in local null mode unless you explicitly set WORKSPACE_ADAPTER_MODE=external.
EOF
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    exec "$0" help
    ;;
esac
