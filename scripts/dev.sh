#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
export LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
export OTEL_TRACES_EXPORTER="${OTEL_TRACES_EXPORTER:-console}"
scripts/serve-knowledge.sh 8002 &
knowledge_pid=$!
backend/.venv/bin/python -m uvicorn homechem.main:app --app-dir backend --host 127.0.0.1 --reload --reload-dir backend/homechem &
backend_pid=$!
trap 'kill "$backend_pid" "$knowledge_pid" 2>/dev/null || true' EXIT
npm --prefix web run dev
