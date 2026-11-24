#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
exec scripts/browser-test.sh --config playwright.sanity.config.ts "$@"
