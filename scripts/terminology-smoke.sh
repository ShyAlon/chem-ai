#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
PYTHONPATH=backend backend/.venv/bin/python - "${1:-sodium chloride}" <<'PY'
import asyncio
import sys
from homechem.terminology import create_terminology_client, lookup_terms
async def main():
    result = await lookup_terms(create_terminology_client(), sys.argv[1])
    assert result.items, 'OLS returned no candidates'
    for item in result.items:
        print(f'{item.curie}: {", ".join(item.label)} — {item.iri}')
asyncio.run(main())
PY
