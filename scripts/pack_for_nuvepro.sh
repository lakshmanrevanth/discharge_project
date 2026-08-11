#!/usr/bin/env bash
# Build a clean zip for NuvePro upload (excludes .venv, caches, old reports).
# Usage:  ./scripts/pack_for_nuvepro.sh
# Output: ../cap_proj_nuvepro.zip (sibling of the repo folder)

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
OUT="${1:-../cap_proj_nuvepro.zip}"

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing. Copy .env.example → .env and put AWS Bedrock keys in it BEFORE packing."
  exit 1
fi
if ! grep -q '^AWS_ACCESS_KEY_ID=.\+' .env; then
  echo "ERROR: AWS_ACCESS_KEY_ID empty in .env — Bedrock will not work on NuvePro."
  exit 1
fi

echo "Packing $ROOT → $OUT"
rm -f "$OUT"

# macOS zip; exclude heavy/ephemeral paths
zip -r "$OUT" . \
  -x './.venv/*' \
  -x './venv/*' \
  -x './.git/*' \
  -x './__pycache__/*' \
  -x '*/__pycache__/*' \
  -x './.pytest_cache/*' \
  -x './.mypy_cache/*' \
  -x './.ruff_cache/*' \
  -x './.cursor/*' \
  -x './logs/*' \
  -x './data/reports/*' \
  -x './data/vector_db/*' \
  -x './data/rag_sessions/*' \
  -x './data/processed/*' \
  -x './data/hitl/*' \
  -x '*.pyc' \
  -x '.DS_Store' \
  -x '*/.DS_Store'

# Keep placeholders inside the zip
zip "$OUT" data/reports/.gitkeep data/vector_db/.gitkeep data/rag_sessions/.gitkeep data/processed/.gitkeep 2>/dev/null || true

echo
echo "Done: $OUT"
echo "Size: $(du -h "$OUT" | awk '{print $1}')"
echo
echo "On NuvePro after upload/extract:"
echo "  chmod +x scripts/start.sh scripts/stop.sh && ./scripts/start.sh"
echo "Then open Streamlit on port 8501."
