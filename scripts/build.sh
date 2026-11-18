#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
if [[ $# -eq 0 ]]; then
  exec npm --prefix web run build
fi
registry="${1:?Registry image prefix required}"
revision="${2:?Release SHA required}"
platform="${3:-linux/amd64}"
for service in api web; do
  docker buildx build --load --platform "$platform" \
    --file "infra/$service.Dockerfile" --tag "$registry-$service:$revision" .
done
