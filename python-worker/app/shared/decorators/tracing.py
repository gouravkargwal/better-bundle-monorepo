"""
Distributed tracing decorator — wraps functions in OpenTelemetry spans.

Use @trace_func() on any function that should appear as a child span in
OpenObserve (or any OTLP-compatible backend).  Both sync and async variants
are provided.
"""

from functools import wraps
from typing import Any, Callable, Optional

from opentelemetry import trace

_tracer = trace.get_tracer(__name__)


def trace_func(name: Optional[str] = None):
    """Decorator that wraps a synchronous function in an OpenTelemetry span.

    The span name defaults to ``{module}.{function_name}`` and can be
    overridden with the *name* argument.

    Usage::

        @trace_func()
        def my_method(...): ...

        @trace_func("custom.span.name")
        def my_method(...): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            span_name = name or f"{func.__module__}.{func.__qualname__}"
            with _tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                return func(*args, **kwargs)

        return wrapper

    return decorator


def async_trace_func(name: Optional[str] = None):
    """Decorator that wraps an asynchronous function in an OpenTelemetry span.

    Usage::

        @async_trace_func()
        async def my_method(...): ...

        @async_trace_func("custom.span.name")
        async def my_method(...): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            span_name = name or f"{func.__module__}.{func.__qualname__}"
            with _tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                return await func(*args, **kwargs)

        return wrapper

    return decorator
