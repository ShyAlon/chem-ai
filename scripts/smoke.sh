#!/usr/bin/env bash
set -euo pipefail
base="${1:?Base URL required}"
revision="${2:?Release SHA required}"
curl -fsS --max-time 8 "$base/" | grep -F 'id="root"' >/dev/null
curl -fsS --max-time 8 "$base/manifest.webmanifest" | jq -e '.name == "HomeChem"' >/dev/null
curl -fsS --max-time 8 "$base/api/health" | jq -e --arg sha "$revision" '.status == "ok" and .release == $sha' >/dev/null
decision="$(curl -fsS --max-time 8 -H 'Content-Type: application/json' -d \
  '{"surface":"glass_screen","materials":"dry_microfiber_only","confirmed":true}' "$base/api/assess")"
jq -e '.status == "approved" and .source.url != null' <<< "$decision" >/dev/null
