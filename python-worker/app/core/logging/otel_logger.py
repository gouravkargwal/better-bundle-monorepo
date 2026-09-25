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

from .sampling import InfoSampler, rate_for

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
            # `deployment.environment.name`, not `deployment.environment`.
            # The latter is the DEPRECATED pre-1.27 spelling. The Node SDK in
            # better-bundle uses ATTR_DEPLOYMENT_ENVIRONMENT_NAME and so writes
            # the new one, which meant the two services landed in the same
            # stream under two different column names: a
            # `WHERE deployment_environment = 'production'` filter matched
            # python-worker and silently dropped every remix-app record.
            "deployment.environment.name": settings.ENVIRONMENT,
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

    # The sampler sits on THIS handler, not on the root logger, so it governs
    # only what is shipped. Console output stays complete: `docker logs` on a
    # production container still shows every line, and local development is
    # untouched.
    sample_rate = rate_for(settings)
    otel_handler.addFilter(InfoSampler(sample_rate))

    root_logger = logging.getLogger()
    root_logger.addHandler(otel_handler)

    if sample_rate < 1.0:
        # At WARNING so this survives its own sampler and any level raise —
        # a reader seeing thin INFO volume needs to find this line.
        root_logger.warning(
            "INFO log sampling active: %.0f%% of DEBUG/INFO records are shipped "
            "to OpenObserve. WARNING and above are never sampled. Kept records "
            "carry log_sample_rate; multiply counts by 1/rate.",
            sample_rate * 100,
        )

    return provider
