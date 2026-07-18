"""
Monitoring decorators for BetterBundle Python Worker
"""

import functools
import time
from typing import Any, Callable, Optional
from datetime import datetime

from app.core.logging import get_logger
from app.core.metrics import get_meter

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# OTel instruments — created once at module level
# ---------------------------------------------------------------------------
_monitor_meter = get_meter()
_monitor_calls = _monitor_meter.create_counter(
    "function.calls",
    description="Total function calls",
    unit="1",
)
_monitor_errors = _monitor_meter.create_counter(
    "function.errors",
    description="Total function errors",
    unit="1",
)


def monitor(func_name: Optional[str] = None):
    """Monitor function execution with timing and logging"""

    def decorator(func: Callable) -> Callable:
        name = func_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_datetime = datetime.now()

            try:

                result = func(*args, **kwargs)

                execution_time = time.time() - start_time

                _monitor_calls.add(
                    1,
                    {
                        "function": func.__name__,
                        "module": func.__module__,
                        "status": "success",
                    },
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                _monitor_errors.add(
                    1,
                    {
                        "function": func.__name__,
                        "module": func.__module__,
                        "error_type": type(e).__name__,
                    },
                )
                logger.error(
                    f"Failed {name}",
                    extra={
                        "function": name,
                        "execution_time": execution_time,
                        "status": "error",
                        "error": str(e),
                    },
                )
                raise

        return wrapper

    return decorator


def async_monitor(func_name: Optional[str] = None):
    """Monitor async function execution with timing and logging"""

    def decorator(func: Callable) -> Callable:
        name = func_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            start_datetime = datetime.now()

            try:

                result = await func(*args, **kwargs)

                execution_time = time.time() - start_time

                _monitor_calls.add(
                    1,
                    {
                        "function": func.__name__,
                        "module": func.__module__,
                        "status": "success",
                    },
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                _monitor_errors.add(
                    1,
                    {
                        "function": func.__name__,
                        "module": func.__module__,
                        "error_type": type(e).__name__,
                    },
                )
                logger.error(
                    f"Failed {name}",
                    extra={
                        "function": name,
                        "execution_time": execution_time,
                        "status": "error",
                        "error": str(e),
                    },
                )
                raise

        return wrapper

    return decorator
