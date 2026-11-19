#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="${1:-$root/backend/.venv/bin/python}"
target="${2:-$root/backend/.nltk-data}"
"$python" - "$target" <<'PY'
import sys

import nltk

nltk.download("wordnet", download_dir=sys.argv[1], quiet=True, raise_on_error=True)
PY
chmod 0644 "$target/corpora/wordnet.zip"
