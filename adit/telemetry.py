"""OpenTelemetry configuration for ADIT.

This module sets up OpenTelemetry instrumentation for traces, metrics, and logs,
exporting to an OTLP-compatible backend (e.g., OpenObserve).

Telemetry is disabled if OTEL_EXPORTER_OTLP_ENDPOINT is not set.
"""

import base64
import logging
import os
import socket

logger = logging.getLogger(__name__)


class RegisteredLoggerFilter(logging.Filter):
    """Allow all logs from registered loggers, ERROR+ from others.

    This filter prevents noisy third-party libraries from flooding logs while ensuring
    our application logs reach both console and OTLP handlers.
    """

    REGISTERED_PREFIXES = ("adit", "django", "pydicom", "pynetdicom")

    def filter(self, record: logging.LogRecord) -> bool:
        # Always allow ERROR and above from any logger
        if record.levelno >= logging.ERROR:
            return True
        # Allow lower levels only from registered loggers
        return record.name.startswith(self.REGISTERED_PREFIXES)


_telemetry_initialized = False
_logger_provider = None


def setup_opentelemetry() -> None:
    """Initialize OpenTelemetry instrumentation.

    This function should be called once at application startup, before Django loads.
    It configures trace, metric, and log exporters to send data to the OTLP endpoint.

    If OTEL_EXPORTER_OTLP_ENDPOINT is not set, telemetry is disabled.
    """
    global _telemetry_initialized, _logger_provider

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
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = os.environ.get("OTEL_SERVICE_NAME") or socket.gethostname() or "adit"

    # Build auth header for OpenObserve
    auth_header = _build_auth_header()
    headers = {"Authorization": auth_header} if auth_header else {}

    # Create resource with service name
    resource = Resource.create({"service.name": service_name})

    # Setup tracing
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{endpoint}/v1/traces",
        headers=headers,
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Setup metrics
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{endpoint}/v1/metrics",
        headers=headers,
    )
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Setup logging
    log_exporter = OTLPLogExporter(
        endpoint=f"{endpoint}/v1/logs",
        headers=headers,
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    # Store logger_provider for OTLPLoggingHandler to use
    # The handler is configured in Django's LOGGING dict to survive dictConfig()
    _logger_provider = logger_provider

    # Instrument Django
    DjangoInstrumentor().instrument()

    # Instrument psycopg (PostgreSQL)
    PsycopgInstrumentor().instrument()

    # Instrument logging to add trace context
    LoggingInstrumentor().instrument(set_logging_format=True)

    _telemetry_initialized = True
    logger.info("OpenTelemetry initialized for service: %s", service_name)


def _build_auth_header() -> str | None:
    """Build Basic auth header from OpenObserve credentials.

    Returns the Authorization header value, or None if credentials are not set.
    """
    username = os.environ.get("ZO_ROOT_USER_EMAIL")
    password = os.environ.get("ZO_ROOT_USER_PASSWORD")

    if not username or not password:
        return None

    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


class OTLPLoggingHandler(logging.Handler):
    """Logging handler that exports to OTLP.

    This handler can be configured via Django's LOGGING dict. It retrieves
    the logger_provider from the module-level variable set by setup_opentelemetry().

    This approach ensures the handler survives Django's logging.config.dictConfig()
    call which would otherwise remove handlers added before Django loads.
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._otlp_handler: logging.Handler | None = None

    def _get_otlp_handler(self) -> logging.Handler | None:
        if self._otlp_handler is None and _logger_provider is not None:
            from opentelemetry.sdk._logs import LoggingHandler

            self._otlp_handler = LoggingHandler(
                level=self.level,
                logger_provider=_logger_provider,
            )
        return self._otlp_handler

    def emit(self, record: logging.LogRecord) -> None:
        handler = self._get_otlp_handler()
        if handler is not None:
            handler.emit(record)

    def flush(self) -> None:
        handler = self._get_otlp_handler()
        if handler is not None:
            handler.flush()
