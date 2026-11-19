#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
cd backend
exec .venv/bin/python -m pytest "$@"
