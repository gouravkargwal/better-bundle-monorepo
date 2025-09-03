"""
Validation decorators for BetterBundle Python Worker
"""

import functools
from typing import Any, Callable, Dict, List, Optional, Type, Union
from inspect import signature


def validate_input(validation_rules: Optional[Dict[str, Any]] = None):
    """Validate function input parameters"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            sig = signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Apply validation rules if provided
            if validation_rules:
                for param_name, rule in validation_rules.items():
                    if param_name in bound_args.arguments:
                        value = bound_args.arguments[param_name]
                        if not _validate_value(value, rule):
                            raise ValueError(f"Validation failed for parameter '{param_name}'")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_output(validation_rules: Optional[Dict[str, Any]] = None):
    """Validate function output"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Apply validation rules if provided
            if validation_rules:
                if not _validate_value(result, validation_rules):
                    raise ValueError("Output validation failed")
            
            return result
        
        return wrapper
    return decorator


def _validate_value(value: Any, rule: Any) -> bool:
    """Internal validation helper"""
    if rule is None:
        return True
    
    if isinstance(rule, type):
        return isinstance(value, rule)
    
    if callable(rule):
        return rule(value)
    
    if isinstance(rule, (list, tuple)):
        return value in rule
    
    if isinstance(rule, dict):
        if "type" in rule:
            if not isinstance(value, rule["type"]):
                return False
        
        if "min" in rule and hasattr(value, "__len__"):
            if len(value) < rule["min"]:
                return False
        
        if "max" in rule and hasattr(value, "__len__"):
            if len(value) > rule["max"]:
                return False
    
    return True
