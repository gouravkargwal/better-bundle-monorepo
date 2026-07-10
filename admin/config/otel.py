"""
OpenTelemetry instrumentation for Django Admin.

Instruments Django to produce distributed traces sent to OpenObserve,
and exports Django log records via OTLP for centralized logging.

Usage in settings.py:
    from config.otel import setup_otel
    setup_otel()
"""

import os
import logging

logger = logging.getLogger(__name__)


def _build_otlp_headers():
    """Build OTLP headers with Basic Auth from env vars."""
    openobserve_email = os.getenv("OPENOBSERVE_EMAIL", "")
    openobserve_password = os.getenv("OPENOBSERVE_PASSWORD", "")
    otlp_headers = {}
    if openobserve_email and openobserve_password:
        import base64
        auth_str = f"{openobserve_email}:{openobserve_password}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        otlp_headers["Authorization"] = f"Basic {encoded}"
    return otlp_headers


def setup_otel():
    """Initialize OpenTelemetry tracing AND logging for Django admin.

    All OTel imports are inside this function so that
    missing dependencies are caught gracefully.
    """
    try:
        # Lazy imports — safe inside try/except
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.instrumentation.django import DjangoInstrumentor

        service_name = os.getenv("OTEL_SERVICE_NAME", "django-admin")
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://openobserve:5080"
        )
        openobserve_org_id = os.getenv("OPENOBSERVE_ORG_ID", "default")
        otlp_headers = _build_otlp_headers()

        # Create resource with service name
        resource = Resource.create({
            SERVICE_NAME: service_name,
            "service.namespace": "betterbundle",
        })

        # ═══════════════════════════════════════════
        #  TRACING — TracerProvider + OTLP exporter
        # ═══════════════════════════════════════════
        tracer_provider = TracerProvider(resource=resource)

        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=(
                f"{otlp_endpoint.rstrip('/')}"
                f"/api/{openobserve_org_id}/v1/traces"
            ),
            headers=otlp_headers,
        )
        tracer_provider.add_span_processor(
            BatchSpanProcessor(otlp_trace_exporter)
        )
        trace.set_tracer_provider(tracer_provider)

        # Instrument Django
        DjangoInstrumentor().instrument()

        logger.info(
            "OpenTelemetry tracing initialized for Django admin",
            extra={"service": service_name},
        )

        # ═══════════════════════════════════════════
        #  LOGGING — LoggerProvider + OTLP exporter
        # ═══════════════════════════════════════════
        try:
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.sdk._logs import (
                LoggerProvider,
                LoggingHandler,
            )
            from opentelemetry.sdk._logs.export import (
                BatchLogRecordProcessor,
            )
            from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                OTLPLogExporter as OTLPHttpLogExporter,
            )
            from opentelemetry.instrumentation.logging import (
                LoggingInstrumentor,
            )

            # Create LoggerProvider
            log_provider = LoggerProvider(resource=resource)
            set_logger_provider(log_provider)

            # OTLP log exporter -> OpenObserve
            otlp_log_exporter = OTLPHttpLogExporter(
                endpoint=(
                    f"{otlp_endpoint.rstrip('/')}"
                    f"/api/{openobserve_org_id}/v1/logs"
                ),
                headers=otlp_headers,
            )
            log_provider.add_log_record_processor(
                BatchLogRecordProcessor(otlp_log_exporter)
            )

            # Attach OTel LoggingHandler to the root Django logger
            otel_handler = LoggingHandler(
                level=logging.NOTSET,
                logger_provider=log_provider,
            )
            logging.getLogger().addHandler(otel_handler)

            # Instrument logging for trace context injection
            LoggingInstrumentor().instrument(set_logging_format=True)

            logger.info(
                "OpenTelemetry logging initialized for Django admin",
                extra={"service": service_name},
            )

        except Exception as log_err:
            logger.warning(
                f"Failed to initialize OTel log export: {log_err}"
            )

    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry: {e}")
        logger.warning(
            "Application will continue without distributed tracing"
        )
