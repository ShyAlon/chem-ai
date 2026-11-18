#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
schema="$(mktemp)"
trap 'rm -f "$schema"' EXIT
PYTHONPATH=backend backend/.venv/bin/python -c 'import json; from homechem.main import app; print(json.dumps(app.openapi()))' > "$schema"
output="${1:-web/src/schema.d.ts}"
web/node_modules/.bin/openapi-typescript "$schema" --output "$output"
