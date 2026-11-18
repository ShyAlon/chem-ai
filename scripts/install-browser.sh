#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
cd web
exec node_modules/.bin/playwright install "$@" chromium
