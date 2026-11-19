#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
exec backend/.venv/bin/python -m uvicorn homechem.knowledge_server:app --app-dir backend --host 127.0.0.1 --port "${1:-8002}" --no-access-log
