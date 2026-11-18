#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
uv sync --locked --python 3.12 --project backend
npm --prefix web ci
