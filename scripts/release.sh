#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
: "${DEPLOY_HOST:?}" "${DEPLOY_USER:?}" "${DEPLOY_SSH_KEY:?}" "${DEPLOY_KNOWN_HOSTS:?}"
stack="${DEPLOY_DIR:-/opt/homechem}"
[[ "$stack" =~ ^/[a-zA-Z0-9/_.-]+$ ]]
temp="$(mktemp -d)"
trap 'rm -rf "$temp"' EXIT
umask 077
printf '%s\n' "$DEPLOY_SSH_KEY" > "$temp/key"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$temp/hosts"
options=(-i "$temp/key" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$temp/hosts")
target="$DEPLOY_USER@$DEPLOY_HOST"

if [[ -n "${ROLLBACK_SHA:-}" ]]; then
  [[ "$ROLLBACK_SHA" =~ ^[a-f0-9]{40}$ ]]
  ssh "${options[@]}" "$target" "$stack/bin/rollback.sh '$ROLLBACK_SHA' '$stack'"
  exit
fi

registry="ghcr.io/$(printf '%s' "$GITHUB_REPOSITORY" | tr '[:upper:]' '[:lower:]')"
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io --username "$GITHUB_ACTOR" --password-stdin
scripts/build.sh "$registry" "$GITHUB_SHA" "${DEPLOY_PLATFORM:-linux/amd64}"
scripts/publish.sh "$registry" "$GITHUB_SHA" > "$temp/release.env"

incoming="$stack/incoming/$GITHUB_SHA"
ssh "${options[@]}" "$target" "mkdir -p '$stack/bin' '$incoming'"
scp "${options[@]}" scripts/{deploy,smoke,rollback}.sh "$target:$stack/bin/"
scp "${options[@]}" "$temp/release.env" infra/compose.yaml "$target:$incoming/"
ssh "${options[@]}" "$target" "$stack/bin/deploy.sh '$incoming/release.env' '$stack'"
