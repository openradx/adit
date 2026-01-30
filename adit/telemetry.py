"""OpenTelemetry configuration for ADIT.

This module sets up OpenTelemetry instrumentation for traces, metrics, and logs,
exporting to an OTLP-compatible backend (e.g., otel-collector -> OpenObserve).

Telemetry is disabled if OTEL_EXPORTER_OTLP_ENDPOINT is not set.
"""

import logging
import os
import socket

logger = logging.getLogger(__name__)


_telemetry_initialized = False


def setup_opentelemetry() -> None:
    """Initialize OpenTelemetry instrumentation for traces, metrics, and logs.

    This function should be called once at application startup, before Django loads.
    It configures trace, metric, and log exporters to send data to the OTLP endpoint
    (typically otel-collector).

    If OTEL_EXPORTER_OTLP_ENDPOINT is not set, telemetry is disabled.
    """
    global _telemetry_initialized

    if _telemetry_initialized:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set, telemetry disabled")
        _telemetry_initialized = True
        return

    # Import OpenTelemetry modules only when needed
    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = os.environ.get("OTEL_SERVICE_NAME") or socket.gethostname() or "adit"

    # Create resource with service name
    resource = Resource.create({"service.name": service_name})

    # Setup tracing - otel-collector handles authentication to OpenObserve
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{endpoint}/v1/traces",
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Setup metrics
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{endpoint}/v1/metrics",
    )
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Setup logging - export structured logs via OTLP
    log_exporter = OTLPLogExporter(endpoint=f"{endpoint}/v1/logs")
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    # Instrument Django
    DjangoInstrumentor().instrument()

    # Instrument psycopg (PostgreSQL)
    PsycopgInstrumentor().instrument()

    _telemetry_initialized = True
    logger.info("OpenTelemetry initialized for service: %s", service_name)
