#!/usr/bin/env bash
# Start lab stack: Mock EHR + Primary MCP + Secondary MCP + Streamlit
# Usage: ./scripts/start.sh

set -euo pipefail
cd "$(dirname "$0")/.."

export BIND_HOST="${BIND_HOST:-0.0.0.0}"
export PYTHONUNBUFFERED=1
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing at $(pwd)/.env — copy .env.example and add AWS keys."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "Then: export PATH=\"\$HOME/.local/bin:\$PATH\""
  exit 1
fi

echo "Syncing deps (uv sync)…"
uv sync

mkdir -p logs data/reports data/vector_db data/rag_sessions data/processed data/hitl

# Seed intake if empty (P1019–P1024)
if [[ ! -d data/input/doctor_reports ]] || [[ -z "$(ls -A data/input/doctor_reports 2>/dev/null || true)" ]]; then
  if [[ -d Documentation/Data/incoming/doctor_reports ]]; then
    echo "Seeding data/input from Documentation/Data/incoming…"
    mkdir -p data/input/doctor_reports data/input/lab_reports data/input/bills
    cp -R Documentation/Data/incoming/doctor_reports/. data/input/doctor_reports/ 2>/dev/null || true
    cp -R Documentation/Data/incoming/lab_reports/. data/input/lab_reports/ 2>/dev/null || true
    cp -R Documentation/Data/incoming/bills/. data/input/bills/ 2>/dev/null || true
  fi
fi

for p in 8050 8200 8201 8501 8105; do
  pids=$(lsof -ti ":$p" 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
  fi
done
sleep 1

# Detach into a new session so IDE/tool shells don't kill children on exit.
_start() {
  local name="$1"
  shift
  /usr/bin/python3 - "$name" "$@" <<'PY'
import os, sys, subprocess
name, cmd = sys.argv[1], sys.argv[2:]
log = f"logs/{name}.log"
pidfile = f"logs/{name}.pid"
with open(log, "ab", buffering=0) as lf:
    p = subprocess.Popen(
        cmd,
        stdout=lf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=os.getcwd(),
        env=os.environ.copy(),
    )
with open(pidfile, "w", encoding="utf-8") as f:
    f.write(str(p.pid))
print(f"  pid {p.pid} → {log}")
PY
}

echo "Starting Mock EHR :8050 …"
_start mock_ehr uv run python -m mock_ehr

echo "Starting Primary MCP :8200 …"
_start primary_mcp uv run python -m mcp_servers.primary

echo "Starting Secondary MCP :8201 …"
_start secondary_mcp uv run python -m mcp_servers.secondary

echo "Starting Clinical RAG A2A :8105 …"
_start rag uv run python -m rag

echo "Starting Streamlit :8501 …"
_start hitl_dashboard uv run python -m dashboard

echo "Waiting for ports…"
ok=0
for i in $(seq 1 60); do
  ready=0
  for p in 8050 8200 8201 8105 8501; do
    if lsof -ti ":$p" >/dev/null 2>&1; then
      ready=$((ready + 1))
    fi
  done
  if [[ "$ready" -eq 5 ]]; then
    ok=1
    break
  fi
  sleep 0.5
done

echo
if [[ "$ok" -eq 1 ]]; then
  echo "Started OK."
else
  echo "WARNING: not all ports ready — check logs/"
  for f in mock_ehr primary_mcp secondary_mcp rag hitl_dashboard; do
    echo "---- logs/${f}.log (tail) ----"
    tail -n 15 "logs/${f}.log" 2>/dev/null || true
  done
fi
echo "  Streamlit  http://127.0.0.1:8501"
echo "  Mock EHR   http://127.0.0.1:8050"
echo "  Primary    http://127.0.0.1:8200/clinicaltools"
echo "  Secondary  http://127.0.0.1:8201/analyticstools"
echo "  RAG A2A    http://127.0.0.1:8105"
echo "  Logs       ./logs/"
echo "Stop with:   ./scripts/stop.sh"
