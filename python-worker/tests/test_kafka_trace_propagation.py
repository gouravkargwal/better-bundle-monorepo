"""Kafka W3C trace-context propagation must survive the header round trip.

If this breaks, Node->Kafka->Python traces silently split into two
unrelated traces and nobody notices until someone asks why end-to-end
latency cannot be measured.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.kafka.producer import inject_trace_headers
from app.core.kafka.consumer import extract_trace_context


def test_trace_id_survives_kafka_headers():
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("producer-side") as span:
        expected_trace_id = span.get_span_context().trace_id
        headers = inject_trace_headers()

    assert any(k == "traceparent" for k, _ in headers), headers

    ctx = extract_trace_context({k: v for k, v in headers})
    restored = trace.get_current_span(ctx).get_span_context()

    assert restored.trace_id == expected_trace_id


def test_extract_tolerates_missing_headers():
    ctx = extract_trace_context({})
    assert trace.get_current_span(ctx).get_span_context().trace_id == 0
