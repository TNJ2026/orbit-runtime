#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# Workspace Runtimes deliberately run from the target project. Keep the PromptaFlow
# checkout they may patch explicit rather than letting that cwd stand in for it.
export PROMPTAFLOW_SOURCE_ROOT="$ROOT_DIR"

PROMPTAFLOW_CLI="${PROMPTAFLOW_CLI:-}"
if [ -n "$PROMPTAFLOW_CLI" ]; then
  [ -x "$PROMPTAFLOW_CLI" ] || { echo "PROMPTAFLOW_CLI is not executable: $PROMPTAFLOW_CLI" >&2; exit 127; }
  PROMPTAFLOW=("$PROMPTAFLOW_CLI")
elif [ -x "$ROOT_DIR/.venv/bin/paf" ]; then
  PROMPTAFLOW=("$ROOT_DIR/.venv/bin/paf")
elif [ -x "$ROOT_DIR/.venv/Scripts/paf.exe" ]; then
  PROMPTAFLOW=("$ROOT_DIR/.venv/Scripts/paf.exe")
elif command -v uv >/dev/null 2>&1; then
  PROMPTAFLOW=(uv run --project "$ROOT_DIR" paf)
else
  echo "PromptaFlow cannot start: no project virtualenv or uv executable was found." >&2
  exit 127
fi

# Internal modes let the Agent App manifest and MCP configuration use this
# same portable launcher without exposing more user-facing scripts.
if [ "${1:-}" = "--hub-service" ]; then
  shift
  exec "${PROMPTAFLOW[@]}" hub serve "$@"
fi
if [ "${1:-}" = "--mcp-proxy" ]; then
  shift
  if [ -n "${PROMPTAFLOW_AGENT_APP_WORKSPACE:-}" ]; then
    workspace="$(cd "$PROMPTAFLOW_AGENT_APP_WORKSPACE" && pwd -P)"
    exec "${PROMPTAFLOW[@]}" agent-app mcp-proxy "$ROOT_DIR/agent-app.json" --workspace "$workspace" "$@"
  fi
  exec "${PROMPTAFLOW[@]}" agent-app mcp-proxy "$ROOT_DIR/agent-app.json" "$@"
fi

if [ "$#" -gt 1 ]; then
  echo "usage: ./start-promptaflow.sh [PROJECT_PATH]" >&2
  exit 2
fi
workspace_input="${1:-$PWD}"
if [ ! -d "$workspace_input" ]; then
  echo "PromptaFlow project path is not a directory: $workspace_input" >&2
  exit 2
fi
workspace="$(cd "$workspace_input" && pwd -P)"
"${PROMPTAFLOW[@]}" agent-app ensure "$ROOT_DIR/agent-app.json" >/dev/null
exec "${PROMPTAFLOW[@]}" hub register "$workspace"
