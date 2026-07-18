"""
OpenTelemetry logging configuration for BetterBundle Python Worker
Sends logs to OpenObserve via OTLP HTTP protocol
"""

import logging
from typing import TYPE_CHECKING

from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource

if TYPE_CHECKING:
    from app.core.config.settings import Settings


def init_otel_logger(settings: "Settings") -> LoggerProvider:
    """Initialize OpenTelemetry SDK with OTLP exporter for OpenObserve.

    Configures resource attributes, creates an OTLP HTTP log exporter,
    and attaches a ``LoggingHandler`` to the root Python logger.

    Returns the ``LoggerProvider`` so callers can shut it down gracefully.
    """
    # --- resource attributes ---
    resource = Resource.create(
        {
            "service.name": "python-worker",
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    # --- OTLP HTTP endpoint for logs ---
    base = settings.OPENOBSERVE_ENDPOINT.rstrip("/")
    endpoint = f"{base}/api/{settings.OPENOBSERVE_ORG}/v1/logs"

    exporter = OTLPLogExporter(
        endpoint=endpoint,
        headers=(("Authorization", f"Basic {settings.OPENOBSERVE_API_KEY}"),),
    )

    # --- provider & processor ---
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    _logs.set_logger_provider(provider)

    # --- attach OTel handler to root logger ---
    otel_handler = LoggingHandler(logger_provider=provider)
    root_logger = logging.getLogger()
    root_logger.addHandler(otel_handler)

    return provider
