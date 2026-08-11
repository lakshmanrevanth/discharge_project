#!/usr/bin/env bash
# Stop lab stack started by ./scripts/start.sh
# Usage: ./scripts/stop.sh

set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p logs

stop_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid=$(cat "$file" 2>/dev/null || true)
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      # Kill process group / children best-effort
      kill "$pid" 2>/dev/null || true
      sleep 0.4
      kill -9 "$pid" 2>/dev/null || true
      echo "Stopped pid $pid ($file)"
    fi
    rm -f "$file"
  fi
}

stop_pid_file logs/mock_ehr.pid
stop_pid_file logs/primary_mcp.pid
stop_pid_file logs/secondary_mcp.pid
stop_pid_file logs/rag.pid
stop_pid_file logs/hitl_dashboard.pid

for p in 8050 8200 8201 8105 8501; do
  pids=$(lsof -ti ":$p" 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
    echo "Cleared :$p"
  fi
done

echo "All stopped."
