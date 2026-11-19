#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
uv sync --locked --python 3.12 --project backend
scripts/download-nlp-data.sh
npm --prefix web ci
