"""
Retry decorators for handling transient failures
"""

import asyncio
import functools
import time
from typing import Callable, Any, Optional, Type, Union, Tuple
from functools import wraps

from app.core.logging import get_logger

logger = get_logger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable] = None,
):
    """
    Retry decorator for synchronous functions

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay on each retry
        exceptions: Exception types to retry on
        on_retry: Optional callback function called before each retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {current_delay}s",
                            function=func.__name__,
                            error=str(e),
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                        )

                        if on_retry:
                            try:
                                on_retry(attempt + 1, e, current_delay)
                            except Exception as retry_error:
                                logger.warning(
                                    "Retry callback failed",
                                    callback=on_retry.__name__,
                                    error=str(retry_error),
                                )

                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed",
                            function=func.__name__,
                            final_error=str(e),
                        )

            # If we get here, all attempts failed
            raise last_exception

        return wrapper

    return decorator


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable] = None,
):
    """
    Retry decorator with exponential backoff and jitter

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exceptions: Exception types to retry on
        on_retry: Optional callback function called before each retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        # Calculate delay with exponential backoff and jitter
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = delay * 0.1 * (2 * time.time() % 1 - 1)  # ±10% jitter
                        final_delay = max(0.1, delay + jitter)

                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {final_delay:.2f}s",
                            function=func.__name__,
                            error=str(e),
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=final_delay,
                        )

                        if on_retry:
                            try:
                                on_retry(attempt + 1, e, final_delay)
                            except Exception as retry_error:
                                logger.warning(
                                    "Retry callback failed",
                                    callback=on_retry.__name__,
                                    error=str(retry_error),
                                )

                        time.sleep(final_delay)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed",
                            function=func.__name__,
                            final_error=str(e),
                        )

            # If we get here, all attempts failed
            raise last_exception

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    on_retry: Optional[Callable] = None,
):
    """
    Retry decorator for asynchronous functions

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay on each retry
        exceptions: Exception types to retry on
        on_retry: Optional callback function called before each retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {current_delay}s",
                            function=func.__name__,
                            error=str(e),
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                        )

                        if on_retry:
                            try:
                                if asyncio.iscoroutinefunction(on_retry):
                                    await on_retry(attempt + 1, e, current_delay)
                                else:
                                    on_retry(attempt + 1, e, current_delay)
                            except Exception as retry_error:
                                logger.warning(
                                    "Retry callback failed",
                                    callback=on_retry.__name__,
                                    error=str(retry_error),
                                )

                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed",
                            function=func.__name__,
                            final_error=str(e),
                        )

            # If we get here, all attempts failed
            raise last_exception

        return wrapper

    return decorator


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
):
    """
    Async retry decorator with exponential backoff for database operations

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exceptions: Exception types to retry on
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"Operation {func.__name__} failed after {max_retries} retries: {str(e)}"
                        )
                        raise e

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)

                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay}s",
                        function=func.__name__,
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                    )

                    await asyncio.sleep(delay)

            # If we get here, all attempts failed
            raise last_exception

        return wrapper

    return decorator
