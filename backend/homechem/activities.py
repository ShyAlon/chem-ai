"""Request-scoped operation records for the UI, correlated with OpenTelemetry."""

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import re
from time import monotonic, perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from opentelemetry import trace
from pydantic import BaseModel, Field

type ActivityKind = Literal["model", "translation", "normalization", "policy", "calculation", "mcp", "cache", "retrieval"]


class ActivityRecord(BaseModel):
    id: str
    parent_id: str | None = None
    name: str
    kind: ActivityKind
    status: Literal["success", "error", "running"] = "running"
    started_ms: float
    duration_ms: float = 0
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    debug: dict[str, str | list[str]] = Field(default_factory=dict)


class ActivityTrace(BaseModel):
    request_id: str
    trace_id: str | None
    duration_ms: float
    status: Literal["running", "success", "error"]
    activities: list[ActivityRecord]


@dataclass
class Collection:
    request_id: str
    started: float = field(default_factory=perf_counter)
    records: list[ActivityRecord] = field(default_factory=list)
    status: Literal["running", "success", "error"] = "running"
    trace_id: str | None = None
    duration_ms: float | None = None
    requests: list[dict] = field(default_factory=list)
    logs: list[dict] = field(default_factory=list)


current: ContextVar[Collection | None] = ContextVar("activity_collection", default=None)
parent: ContextVar[str | None] = ContextVar("activity_parent", default=None)
# Unpredictable capability URLs expire after ten minutes; memory is bounded.
stored: OrderedDict[str, tuple[float, Collection]] = OrderedDict()
TTL = 600
MAX_TRACES = 500
router = APIRouter(prefix="/api/activities")


@contextmanager
def activity(kind: ActivityKind, name: str, **details):
    collection = current.get()
    started = perf_counter()
    record = ActivityRecord(
        id=uuid4().hex, parent_id=parent.get(), name=name, kind=kind,
        started_ms=round((started - collection.started) * 1000, 2) if collection else 0,
        details=details,
    )
    if collection and len(collection.records) < 100:
        collection.records.append(record)
    token = parent.set(record.id)
    with trace.get_tracer(__name__).start_as_current_span(name, record_exception=False) as span:
        span.set_attribute("activity.kind", kind)
        try:
            yield record
            record.status = "success"
        except BaseException as error:
            record.status = "error"
            record.details["error_type"] = type(error).__name__
            span.set_status(trace.StatusCode.ERROR, type(error).__name__)
            raise
        finally:
            record.duration_ms = round((perf_counter() - started) * 1000, 2)
            for key, value in record.details.items():
                if value is not None:
                    span.set_attribute(f"activity.{key}", value)
            parent.reset(token)


def annotate(**details):
    collection = current.get()
    if collection:
        record = next((item for item in reversed(collection.records) if item.id == parent.get()), None)
        if record:
            record.details.update(details)


def begin(collection: Collection, requested_key: str | None = None) -> str:
    now = monotonic()
    for key in list(stored):
        if now - stored[key][0] > TTL:
            del stored[key]
    context = trace.get_current_span().get_span_context()
    collection.trace_id = f"{context.trace_id:032x}" if context.is_valid else None
    key = uuid4().hex
    if requested_key and re.fullmatch(r"[a-f0-9]{32}", requested_key) and requested_key not in stored:
        key = requested_key
    stored[key] = (now, collection)
    while len(stored) > MAX_TRACES:
        stored.popitem(last=False)
    return key


def finish(collection: Collection, success: bool):
    collection.duration_ms = round((perf_counter() - collection.started) * 1000, 2)
    collection.status = "success" if success else "error"


@router.get("/{key}", operation_id="activity_trace")
def get_trace(key: str) -> ActivityTrace:
    entry = stored.get(key)
    if entry is None or monotonic() - entry[0] > TTL:
        stored.pop(key, None)
        raise HTTPException(404, "Activity trace unavailable or expired")
    collection = entry[1]
    return ActivityTrace(
        request_id=collection.request_id, trace_id=collection.trace_id,
        duration_ms=collection.duration_ms if collection.duration_ms is not None else round((perf_counter() - collection.started) * 1000, 2),
        status=collection.status, activities=collection.records,
    )


@router.get("/{key}/download", operation_id="activity_download", response_class=Response, responses={200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}})
def download_trace(key: str):
    from .debug_bundle import build_bundle

    snapshot = get_trace(key)  # Same capability and expiry as the trace view.
    if snapshot.status == "running":
        raise HTTPException(409, "Activity is still running")
    return Response(
        build_bundle(snapshot, stored[key][1]), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="homechem-debug-{snapshot.request_id}.zip"'},
    )
