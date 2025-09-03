"""
Timing decorators for performance monitoring
"""

import time
import asyncio
import functools
from typing import Callable, Any, Optional
from functools import wraps

from app.core.logging import get_logger

logger = get_logger(__name__)


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

                logger.info(
                    f"Performance metrics",
                    operation=op_name,
                    wall_time_ms=wall_time,
                    cpu_time_ms=cpu_time,
                    efficiency_percent=(
                        (cpu_time / wall_time * 100) if wall_time > 0 else 0
                    ),
                )

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

                logger.info(
                    f"Async performance metrics",
                    operation=op_name,
                    wall_time_ms=wall_time,
                    cpu_time_ms=cpu_time,
                    efficiency_percent=(
                        (cpu_time / wall_time * 100) if wall_time > 0 else 0
                    ),
                )

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

        return wrapper

    return decorator
