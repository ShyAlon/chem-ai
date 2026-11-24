#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
PYTHONPATH=backend backend/.venv/bin/python - "$@" <<'PY'
import asyncio
import json
import sys
import httpx
from homechem.object_materials import ObjectMaterialClient
async def main():
    async with httpx.AsyncClient(timeout=6) as http:
        client = ObjectMaterialClient(http)
        for query in sys.argv[1:] or ['Apple Watch', 'spoon', 'steel wool']:
            result = await client.compare(query)
            print(result.model_dump_json())
asyncio.run(main())
PY
