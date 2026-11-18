#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
cd backend
.venv/bin/python -m pytest "${@}"
