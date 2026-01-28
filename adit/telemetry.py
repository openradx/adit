"""OpenTelemetry configuration for ADIT.

This module sets up OpenTelemetry instrumentation for traces and metrics,
exporting to an OTLP-compatible backend (e.g., otel-collector -> OpenObserve).

Logs are collected by otel-collector from Docker container log files,
not via OTLP export. This simplifies the logging pipeline and leverages
Docker's native log handling.

Telemetry is disabled if OTEL_EXPORTER_OTLP_ENDPOINT is not set.
"""

import json
import logging
import os
import socket
import traceback
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RegisteredLoggerFilter(logging.Filter):
    """Allow all logs from registered loggers, ERROR+ from others.

    This filter prevents noisy third-party libraries from flooding logs while ensuring
    our application logs reach the console handler.
    """

    REGISTERED_PREFIXES = ("adit", "django", "pydicom", "pynetdicom")

    def filter(self, record: logging.LogRecord) -> bool:
        # Always allow ERROR and above from any logger
        if record.levelno >= logging.ERROR:
            return True
        # Allow lower levels only from registered loggers
        return record.name.startswith(self.REGISTERED_PREFIXES)


class JsonLogFormatter(logging.Formatter):
    """Format log records as JSON for collection by otel-collector.

    This formatter outputs structured JSON logs that can be parsed by the
    otel-collector filelog receiver to extract fields like timestamp, level,
    logger name, and message.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "message",
                "taskName",
            ):
                try:
                    json.dumps(value)  # Check if value is JSON serializable
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data)


_telemetry_initialized = False


def setup_opentelemetry() -> None:
    """Initialize OpenTelemetry instrumentation for traces and metrics.

    This function should be called once at application startup, before Django loads.
    It configures trace and metric exporters to send data to the OTLP endpoint
    (typically otel-collector).

    Logs are NOT exported via OTLP; they are collected by otel-collector from
    Docker container log files. This simplifies the logging pipeline.

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
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
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

    # Instrument Django
    DjangoInstrumentor().instrument()

    # Instrument psycopg (PostgreSQL)
    PsycopgInstrumentor().instrument()

    _telemetry_initialized = True
    logger.info("OpenTelemetry initialized for service: %s", service_name)
