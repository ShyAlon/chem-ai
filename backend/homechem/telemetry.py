import json
import logging
import os
from datetime import UTC, datetime

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


RELEASE = os.getenv("RELEASE_SHA", "local")
log = logging.getLogger("homechem")
log.setLevel(logging.INFO)
log.propagate = False
log.addHandler(logging.StreamHandler())


def configure() -> tuple[TracerProvider, MeterProvider]:
    resource = Resource.create({
        "service.name": "homechem", "service.version": RELEASE,
    })
    provider = TracerProvider(resource=resource)
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    elif os.getenv("OTEL_TRACES_EXPORTER") == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    readers = []
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"):
        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(meter_provider)
    return provider, meter_provider


def event(name: str, **fields: object) -> None:
    context = trace.get_current_span().get_span_context()
    log.info(json.dumps({
        "time": datetime.now(UTC).isoformat(), "event": name, "release": RELEASE,
        "trace_id": f"{context.trace_id:032x}" if context.is_valid else None,
        **fields,
    }))
