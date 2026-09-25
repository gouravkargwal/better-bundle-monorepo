"""
OpenTelemetry tracing configuration for BetterBundle Python Worker
Exports spans to OpenObserve via OTLP HTTP protocol
"""

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

if TYPE_CHECKING:
    from app.core.config.settings import Settings


def init_otel_tracing(settings: "Settings") -> TracerProvider:
    """Initialize OpenTelemetry tracing SDK with OTLP exporter for OpenObserve.

    Must run before any instrumentor is applied and before the first span is
    opened — anything that calls ``trace.get_tracer()`` earlier binds to the
    no-op provider for the life of the process and its spans are discarded.

    Returns the ``TracerProvider`` so callers can shut it down gracefully.
    """
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

    base = settings.OPENOBSERVE_ENDPOINT.rstrip("/")
    endpoint = f"{base}/api/{settings.OPENOBSERVE_ORG}/v1/traces"

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=(("Authorization", f"Basic {settings.OPENOBSERVE_API_KEY}"),),
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    return provider
