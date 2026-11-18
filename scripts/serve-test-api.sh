#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
export LLM_PROVIDER=fixture
exec backend/.venv/bin/python -m uvicorn homechem.main:app --app-dir backend --host 127.0.0.1 --no-access-log
