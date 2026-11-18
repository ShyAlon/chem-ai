#!/usr/bin/env bash
set -euo pipefail
release="$(realpath "${1:?Release file required}")"
stack="$(cd "${2:?Deployment directory required}" && pwd -P)"
smoke="$stack/bin/smoke.sh"

# Keep the Compose project name and runtime credentials stable across releases.
cd "$stack"
revision="$(sed -n 's/^RELEASE_SHA=//p' "$release")"
host="$(sed -n 's/^PUBLIC_HOST=//p' "$stack/.env")"
[[ "$revision" =~ ^[0-9a-f]{40}$ && "$host" =~ ^[a-zA-Z0-9.-]+$ ]]
grep -Ex 'API_IMAGE=ghcr\.io/[a-z0-9/._-]+@sha256:[a-f0-9]{64}' "$release" >/dev/null
grep -Ex 'WEB_IMAGE=ghcr\.io/[a-z0-9/._-]+@sha256:[a-f0-9]{64}' "$release" >/dev/null

compose() {
  local config="$1"
  shift
  docker compose --project-name homechem --env-file "$stack/.env" --env-file "$config/release.env" \
    --file "$config/compose.yaml" "$@"
}

verify_release() {
  local revision="$1"
  for attempt in {1..12}; do
    if "$smoke" "https://$host" "$revision"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

deploy_dir="$stack/releases/$revision"
mkdir -p "$deploy_dir"
if [[ "$release" != "$deploy_dir/release.env" ]]; then
  cp "$release" "$deploy_dir/release.env"
  cp "$(dirname "$release")/compose.yaml" "$deploy_dir/compose.yaml"
fi
ln -sf "$stack/runtime.env" "$deploy_dir/runtime.env"

previous=""
if [[ -f "$stack/current" ]]; then
  previous="$(cat "$stack/current")"
fi
compose "$deploy_dir" pull
if compose "$deploy_dir" up -d --remove-orphans && verify_release "$revision"; then
  printf '%s\n' "$revision" > "$stack/current.tmp"
  mv "$stack/current.tmp" "$stack/current"
  exit 0
fi

echo "Deployment failed for $revision" >&2
if [[ -n "$previous" && "$previous" != "$revision" ]]; then
  compose "$stack/releases/$previous" up -d --remove-orphans
  verify_release "$previous"
elif [[ -z "$previous" ]]; then
  compose "$deploy_dir" down
fi
exit 1
