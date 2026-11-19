#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
PYTHONPATH=backend exec backend/.venv/bin/python -m homechem.catalog_import procedures "$@"
