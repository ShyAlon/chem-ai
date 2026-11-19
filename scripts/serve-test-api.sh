#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
export LLM_PROVIDER=fixture
export QUESTION_COOLDOWN_SECONDS=0
export TRANSLATION_PROVIDER=llm
knowledge_port="$((${TEST_API_PORT:-8011} + 100))"
export MCP_DATA_URL="http://127.0.0.1:$knowledge_port/mcp"
KNOWLEDGE_MODE=fixture scripts/serve-knowledge.sh "$knowledge_port" &
knowledge_pid=$!
backend/.venv/bin/python -m uvicorn homechem.main:app --app-dir backend --host 127.0.0.1 --port "${TEST_API_PORT:-8011}" --no-access-log &
backend_pid=$!
cleanup() {
  kill "$backend_pid" "$knowledge_pid" 2>/dev/null || true
  wait "$backend_pid" "$knowledge_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait "$backend_pid"
