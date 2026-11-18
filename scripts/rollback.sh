#!/usr/bin/env bash
set -euo pipefail
revision="${1:?Release SHA required}"
stack="${2:?Deployment directory required}"
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
exec "$stack/bin/deploy.sh" "$stack/releases/$revision/release.env" "$stack"
