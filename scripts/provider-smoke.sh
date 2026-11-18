#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
base="${1:-http://127.0.0.1:8000}"
samples=(
  'How do I clean my standard-glass Apple Studio Display with water and a microfiber cloth?'
  'איך מנקים Apple Studio Display עם זכוכית רגילה, מים ומטלית מיקרופייבר?'
)
for sample in "${samples[@]}"; do
  payload="$(jq -nc --arg text "$sample" '{text: $text}')"
  curl -fsS --max-time 45 -H 'Content-Type: application/json' --data "$payload" "$base/api/interpret" |
    jq -e '.surface == "studio_display_standard_glass" and .materials == "water_and_microfiber_only"'
done
