"""
Timing decorators for performance monitoring
"""

import time
import asyncio
import functools
from typing import Callable, Any, Optional
from functools import wraps

from app.core.logging import get_logger
from app.core.metrics import get_meter

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# OTel instruments — created once at module level
# ---------------------------------------------------------------------------
_timing_meter = get_meter()
_timing_histogram = _timing_meter.create_histogram(
    "function.duration",
    description="Function execution duration in seconds",
    unit="s",
)
_timing_threshold_exceeded = _timing_meter.create_counter(
    "function.threshold_exceeded",
    description="Count of function executions exceeding threshold",
    unit="1",
)

_perf_meter = get_meter()
_perf_wall_time = _perf_meter.create_histogram(
    "performance.wall_time",
    description="Wall-clock execution time in seconds",
    unit="s",
)
_perf_cpu_time = _perf_meter.create_histogram(
    "performance.cpu_time",
    description="CPU execution time in seconds",
    unit="s",
)


def timing(threshold_ms: Optional[float] = None):
    """
    Timing decorator for synchronous functions

    Args:
        threshold_ms: Log warning if execution time exceeds this threshold (in milliseconds)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000

                if threshold_ms and execution_time > threshold_ms:
                    logger.warning(
                        f"Function execution time exceeded threshold",
                        function=func.__name__,
                        execution_time_ms=execution_time,
                        threshold_ms=threshold_ms,
                    )
                else:
                    logger.debug(
                        f"Function execution completed",
                        function=func.__name__,
                        execution_time_ms=execution_time,
                    )

                return result

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"Function execution failed",
                    function=func.__name__,
                    execution_time_ms=execution_time,
                    error=str(e),
                )
                raise
            finally:
                duration = time.time() - start_time
                _timing_histogram.record(
                    duration,
                    {"function": func.__name__, "module": func.__module__},
                )
                if threshold_ms and duration * 1000 > threshold_ms:
                    _timing_threshold_exceeded.add(
                        1,
                        {
                            "function": func.__name__,
                            "module": func.__module__,
                            "threshold_ms": str(threshold_ms),
                            "duration_ms": str(round(duration * 1000, 2)),
                        },
                    )

        return wrapper

    return decorator


def async_timing(threshold_ms: Optional[float] = None):
    """
    Timing decorator for asynchronous functions

    Args:
        threshold_ms: Log warning if execution time exceeds this threshold (in milliseconds)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000

                if threshold_ms and execution_time > threshold_ms:
                    logger.warning(
                        f"Async function execution time exceeded threshold",
                        function=func.__name__,
                        execution_time_ms=execution_time,
                        threshold_ms=threshold_ms,
                    )
                else:
                    logger.debug(
                        f"Async function execution completed",
                        function=func.__name__,
                        execution_time_ms=execution_time,
                    )

                return result

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"Async function execution failed",
                    function=func.__name__,
                    execution_time_ms=execution_time,
                    error=str(e),
                )
                raise
            finally:
                duration = time.time() - start_time
                _timing_histogram.record(
                    duration,
                    {"function": func.__name__, "module": func.__module__},
                )
                if threshold_ms and duration * 1000 > threshold_ms:
                    _timing_threshold_exceeded.add(
                        1,
                        {
                            "function": func.__name__,
                            "module": func.__module__,
                            "threshold_ms": str(threshold_ms),
                            "duration_ms": str(round(duration * 1000, 2)),
                        },
                    )

        return wrapper

    return decorator


def performance_monitor(operation_name: Optional[str] = None):
    """
    Performance monitoring decorator that tracks execution time and logs performance metrics

    Args:
        operation_name: Custom name for the operation (defaults to function name)
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            start_cpu = time.process_time()

            try:
                result = func(*args, **kwargs)

                wall_time = (time.time() - start_time) * 1000
                cpu_time = (time.process_time() - start_cpu) * 1000

                return result

            except Exception as e:
                wall_time = (time.time() - start_time) * 1000
                cpu_time = (time.process_time() - start_cpu) * 1000

                logger.error(
                    f"Performance metrics (failed)",
                    operation=op_name,
                    wall_time_ms=wall_time,
                    cpu_time_ms=cpu_time,
                    error=str(e),
                )
                raise
            finally:
                labels = {"function": func.__name__, "module": func.__module__}
                _perf_wall_time.record(time.time() - start_time, labels)
                _perf_cpu_time.record(time.process_time() - start_cpu, labels)

        return wrapper

    return decorator


def async_performance_monitor(operation_name: Optional[str] = None):
    """
    Performance monitoring decorator for asynchronous functions

    Args:
        operation_name: Custom name for the operation (defaults to function name)
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            start_cpu = time.process_time()

            try:
                result = await func(*args, **kwargs)

                wall_time = (time.time() - start_time) * 1000
                cpu_time = (time.process_time() - start_cpu) * 1000

                return result

            except Exception as e:
                wall_time = (time.time() - start_time) * 1000
                cpu_time = (time.process_time() - start_cpu) * 1000

                logger.error(
                    f"Async performance metrics (failed)",
                    operation=op_name,
                    wall_time_ms=wall_time,
                    cpu_time_ms=cpu_time,
                    error=str(e),
                )
                raise
            finally:
                labels = {"function": func.__name__, "module": func.__module__}
                _perf_wall_time.record(time.time() - start_time, labels)
                _perf_cpu_time.record(time.process_time() - start_cpu, labels)

        return wrapper

    return decorator
