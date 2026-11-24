"""Bounded, request-scoped diagnostic capture and portable ZIP export."""

from datetime import UTC, datetime
from io import BytesIO
import json
import re
from time import perf_counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from mcp.shared._httpx_utils import create_mcp_http_client

from .activities import ActivityTrace, Collection, current

BODY_LIMIT = 32768
MAX_REQUESTS = 30
MAX_LOGS = 100
TOKEN_LIST_KEYS = {"tokens", "normalized_tokens", "unrecognized_tokens"}
TOKEN_COUNT_KEYS = {"input_tokens", "output_tokens", "total_tokens"}
SECRET = re.compile(r"authorization|cookie|password|secret|token|api.?key|signature|credential", re.I)


def secret_key(key: str, value=None, path: tuple[str, ...] = ()) -> bool:
    name = key.casefold()
    if (name in TOKEN_LIST_KEYS and path and path[-1] == "diagnostics"
            and isinstance(value, list) and all(isinstance(item, str) for item in value)):
        return False
    if name in TOKEN_COUNT_KEYS and isinstance(value, int) and not isinstance(value, bool):
        return False
    return bool(SECRET.search(key))


def redact(value, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        return {key: "[redacted]" if secret_key(key, item, path) else redact(item, (*path, key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, path) for item in value]
    return value


def json_body(content: bytes) -> dict:
    if len(content) > BODY_LIMIT:
        return {"omitted": "body_limit", "bytes": len(content)}
    try:
        return {"json": redact(json.loads(content))}
    except (ValueError, UnicodeDecodeError):
        return {"omitted": "non_json", "bytes": len(content)}


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    query = urlencode([(key, "[redacted]" if SECRET.search(key) else value) for key, value in parse_qsl(parts.query)])
    return urlunsplit((parts.scheme, host, parts.path, query, ""))


def append_request(collection: Collection, record: dict):
    if len(collection.requests) < MAX_REQUESTS:
        collection.requests.append(record)


async def outbound_request(request: httpx.Request):
    collection = current.get()
    if not collection:
        return
    record = {"direction": "outbound", "method": request.method, "url": safe_url(str(request.url)), "status": None}
    # MCP tool arguments are already represented in activity debug metadata.
    # Raw model prompts, provider bodies, and authentication headers are not retained.
    append_request(collection, record)
    request.extensions["homechem_debug"] = (record, perf_counter())


async def outbound_response(response: httpx.Response):
    entry = response.request.extensions.get("homechem_debug")
    if entry:
        record, started = entry
        record.update(status=response.status_code, elapsed_ms=round((perf_counter() - started) * 1000, 2))


HTTP_HOOKS = {"request": [outbound_request], "response": [outbound_response]}


def mcp_http_client(headers=None, timeout=None, auth=None):
    client = create_mcp_http_client(headers=headers, timeout=timeout, auth=auth)
    for name, hooks in HTTP_HOOKS.items():
        client.event_hooks[name].extend(hooks)
    return client


def capture_log(collection: Collection | None, record: dict):
    if collection and len(collection.logs) < MAX_LOGS:
        collection.logs.append(redact(record))


def build_bundle(snapshot: ActivityTrace, collection: Collection) -> bytes:
    from .telemetry import RELEASE

    buffer = BytesIO()
    manifest = {
        "format_version": 1, "created_at": datetime.now(UTC).isoformat(), "release": RELEASE,
        "request_id": snapshot.request_id, "trace_id": snapshot.trace_id,
        "scope": "selected API request and its child operations",
        "limits": {"body_bytes": BODY_LIMIT, "requests": MAX_REQUESTS, "logs": MAX_LOGS},
        "exclusions": ["credentials and authentication headers", "raw model prompts and provider bodies",
                       "remote service process logs", "unrelated requests and activity polling"],
        "notes": "Includes original user input. Outbound requests contain HTTP metadata; activity records contain tool/provider diagnostics. A null outbound status means no response headers were received.",
    }
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in {"manifest.json": manifest, "trace.json": snapshot.model_dump(), "requests.json": collection.requests}.items():
            archive.writestr(name, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("logs.jsonl", "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in collection.logs))
    return buffer.getvalue()
