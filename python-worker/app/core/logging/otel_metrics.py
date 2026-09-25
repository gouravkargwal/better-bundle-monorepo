"""
OpenTelemetry metrics configuration for BetterBundle Python Worker
Exports metrics to OpenObserve via OTLP HTTP protocol
"""

from typing import TYPE_CHECKING

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

if TYPE_CHECKING:
    from app.core.config.settings import Settings


def init_otel_metrics(settings: "Settings") -> MeterProvider:
    """Initialize OpenTelemetry metrics SDK with OTLP exporter for OpenObserve.

    Configures resource attributes, creates an OTLP HTTP metric exporter
    with a 30-second export interval, and sets the global meter provider.

    Returns the ``MeterProvider`` so callers can shut it down gracefully.
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
    endpoint = f"{base}/api/{settings.OPENOBSERVE_ORG}/v1/metrics"

    exporter = OTLPMetricExporter(
        endpoint=endpoint,
        headers=(("Authorization", f"Basic {settings.OPENOBSERVE_API_KEY}"),),
    )

    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=30_000)

    provider = MeterProvider(
        resource=resource,
        metric_readers=[reader],
    )

    metrics.set_meter_provider(provider)
    return provider
