"""
Caching decorators for BetterBundle Python Worker
"""

import functools
import hashlib
import json
from typing import Any, Callable, Optional, Union
from datetime import datetime, timedelta


def cache(ttl_seconds: int = 300):
    """Simple in-memory cache decorator"""
    def decorator(func: Callable) -> Callable:
        cache_data = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
            
            # Check cache
            if cache_key in cache_data:
                cached_result, timestamp = cache_data[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=ttl_seconds):
                    return cached_result
                else:
                    del cache_data[cache_key]
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_data[cache_key] = (result, datetime.now())
            
            return result
        
        return wrapper
    return decorator


def async_cache(ttl_seconds: int = 300):
    """Async cache decorator"""
    def decorator(func: Callable) -> Callable:
        cache_data = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
            
            # Check cache
            if cache_key in cache_data:
                cached_result, timestamp = cache_data[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=ttl_seconds):
                    return cached_result
                else:
                    del cache_data[cache_key]
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache_data[cache_key] = (result, datetime.now())
            
            return result
        
        return wrapper
    return decorator
