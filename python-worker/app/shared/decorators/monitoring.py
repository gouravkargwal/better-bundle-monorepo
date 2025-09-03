"""
Monitoring decorators for BetterBundle Python Worker
"""

import functools
import time
import logging
from typing import Any, Callable, Optional
from datetime import datetime


def monitor(func_name: Optional[str] = None):
    """Monitor function execution with timing and logging"""
    def decorator(func: Callable) -> Callable:
        name = func_name or func.__name__
        logger = logging.getLogger(__name__)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_datetime = datetime.now()
            
            try:
                logger.info(f"Starting {name}", extra={
                    "function": name,
                    "start_time": start_datetime.isoformat(),
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                })
                
                result = func(*args, **kwargs)
                
                execution_time = time.time() - start_time
                logger.info(f"Completed {name}", extra={
                    "function": name,
                    "execution_time": execution_time,
                    "status": "success"
                })
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Failed {name}", extra={
                    "function": name,
                    "execution_time": execution_time,
                    "status": "error",
                    "error": str(e)
                })
                raise
        
        return wrapper
    return decorator


def async_monitor(func_name: Optional[str] = None):
    """Monitor async function execution with timing and logging"""
    def decorator(func: Callable) -> Callable:
        name = func_name or func.__name__
        logger = logging.getLogger(__name__)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            start_datetime = datetime.now()
            
            try:
                logger.info(f"Starting {name}", extra={
                    "function": name,
                    "start_time": start_datetime.isoformat(),
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                })
                
                result = await func(*args, **kwargs)
                
                execution_time = time.time() - start_time
                logger.info(f"Completed {name}", extra={
                    "function": name,
                    "execution_time": execution_time,
                    "status": "success"
                })
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Failed {name}", extra={
                    "function": name,
                    "execution_time": execution_time,
                    "status": "error",
                    "error": str(e)
                })
                raise
        
        return wrapper
    return decorator
