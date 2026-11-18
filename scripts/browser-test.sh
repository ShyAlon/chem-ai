#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
npm --prefix web run build
cd web
exec node_modules/.bin/playwright test "$@"
