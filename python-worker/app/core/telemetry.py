"""
OpenTelemetry instrumentation for BetterBundle Python Worker.

Instruments FastAPI, aiokafka, and SQLAlchemy to produce
distributed traces sent to OpenObserve via OTLP.
Also exports Python log records via OTLP for centralized logging.

All OTel imports are lazy (inside functions) so that missing
dependencies don't crash the worker at import time.
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


def init_telemetry():
    """Initialize OpenTelemetry tracing AND logging for the Python worker.

    Sets up:
      - TracerProvider with OTLP span exporter (traces)
      - LoggerProvider with OTLP log exporter (logs)
      - Python logging handler that ships all logs via OTLP
      - aiokafka instrumentation for trace propagation

    All OTel imports are inside this function so that
    missing dependencies are caught gracefully.
    """
    try:
        # ── Lazy imports — safe inside try/except ──
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import \
            OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.instrumentation.aiokafka import \
            AIOKafkaInstrumentor

        service_name = os.getenv("OTEL_SERVICE_NAME", "python-worker")
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

        # Instrument aiokafka for trace propagation across Kafka messages
        AIOKafkaInstrumentor().instrument()

        logger.info("OpenTelemetry tracing initialized",
                     extra={"service": service_name})

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
            from opentelemetry.exporter.otlp.proto.http._log_exporter \
                import OTLPLogExporter as OTLPHttpLogExporter
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

            # Attach OTel LoggingHandler to the root Python logger
            # This intercepts ALL Python logging calls and sends them via OTLP
            otel_handler = LoggingHandler(
                level=logging.NOTSET,
                logger_provider=log_provider,
            )
            root_logger = logging.getLogger()
            root_logger.addHandler(otel_handler)

            # Instrument logging for trace context injection
            # (trace_id/span_id automatically added to log records)
            LoggingInstrumentor().instrument(set_logging_format=True)

            logger.info("OpenTelemetry logging initialized",
                         extra={"service": service_name})

        except Exception as log_err:
            logger.warning(
                f"Failed to initialize OTel log export: {log_err}"
            )
            logger.warning(
                "Application will continue with stdout logs only"
            )

    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry: {e}")
        logger.warning(
            "Application will continue without distributed tracing"
        )


def instrument_fastapi(app):
    """Instrument a FastAPI application for tracing.

    Call this after the FastAPI app is created and all routers
    have been included.
    """
    try:
        from opentelemetry.instrumentation.fastapi import \
            FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented for OpenTelemetry tracing")
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")


def instrument_sqlalchemy(engine=None):
    """Instrument SQLAlchemy for tracing database queries.

    Call this after the SQLAlchemy async engine is created.
    Pass engine.sync_engine for better async engine support.

    Args:
        engine: Optional sync SQLAlchemy engine to instrument.
                For async engines, pass engine.sync_engine.
    """
    try:
        from opentelemetry.instrumentation.sqlalchemy import \
            SQLAlchemyInstrumentor

        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumented with engine reference")
        else:
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumented (global)")
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")
