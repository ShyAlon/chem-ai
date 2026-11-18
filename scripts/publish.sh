#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
registry="${1:?Registry image prefix required}"
revision="${2:?Release SHA required}"
printf 'RELEASE_SHA=%s\n' "$revision"
for service in api web; do
  image="$registry-$service:$revision"
  docker push "$image" >&2
  digest="$(docker buildx imagetools inspect "$image" --format '{{json .Manifest}}' | jq -er '.digest')"
  printf '%s_IMAGE=%s@%s\n' "$(printf '%s' "$service" | tr '[:lower:]' '[:upper:]')" "${image%:*}" "$digest"
done
