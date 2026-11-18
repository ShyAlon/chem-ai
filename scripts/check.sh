#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
for script in scripts/*.sh; do
  bash -n "$script"
done
generated="$(mktemp)"
trap 'rm -f "$generated"' EXIT
scripts/generate-client.sh "$generated"
diff -u web/src/schema.d.ts "$generated"
npm --prefix web run check
