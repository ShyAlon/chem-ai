#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
base="${1:-http://127.0.0.1:8000}"
samples=(
  'How do I clean my glass screen with a dry microfiber cloth?'
  'איך מנקים מסך זכוכית במטלית מיקרופייבר יבשה?'
)
for sample in "${samples[@]}"; do
  payload="$(jq -nc --arg text "$sample" '{text: $text}')"
  curl -fsS --retry 2 --max-time 45 -H 'Content-Type: application/json' --data "$payload" "$base/api/interpret" |
    jq -e '.method == "dictionary" and .surface == "glass_screen" and .materials == "dry_microfiber_only"'
done

curl -fsS --retry 2 --max-time 45 -H 'Content-Type: application/json' \
  --data '{"text":"How do I clean the transparent surface on my dining furniture?"}' "$base/api/interpret" |
  jq -e '.method == "model" and (.surface | type) == "string" and .materials == "unknown"'
