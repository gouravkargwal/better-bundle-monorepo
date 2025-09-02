"""
Centralized logging system for BetterBundle Python Worker
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class BetterBundleLogger:
    """Centralized logger for BetterBundle with clean, readable formatting"""
    
    def __init__(self, name: str = "betterbundle"):
        self.name = name
        
        # Create logs directory if it doesn't exist
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create logger instance
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup handlers for different log levels with clean formatting"""
        
        # Console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        # Main application log - clean, readable format
        app_handler = logging.FileHandler(self.logs_dir / "app.log")
        app_handler.setLevel(logging.INFO)
        app_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        app_handler.setFormatter(app_formatter)
        
        # Error log - detailed format for debugging
        error_handler = logging.FileHandler(self.logs_dir / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        
        # Consumer-specific log - focused on Redis operations
        consumer_handler = logging.FileHandler(self.logs_dir / "consumer.log")
        consumer_handler.setLevel(logging.INFO)
        consumer_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        consumer_handler.setFormatter(consumer_formatter)
        
        # Add handlers to this specific logger (not root)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(app_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(consumer_handler)
        
        # Prevent propagation to root logger to avoid duplication
        self.logger.propagate = False
    
    def info(self, message: str, **kwargs):
        """Log info message with structured data"""
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.info(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured data"""
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.debug(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured data"""
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        """Log error message with structured data"""
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.error(message)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with structured data"""
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.critical(message)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.exception(message)
    
    def _format_kwargs(self, kwargs: Dict[str, Any]) -> str:
        """Format keyword arguments into a readable string"""
        formatted = []
        for key, value in kwargs.items():
            if isinstance(value, (dict, list)):
                formatted.append(f"{key}={str(value)[:100]}...")
            else:
                formatted.append(f"{key}={value}")
        return " | ".join(formatted)
    
    def log_consumer_event(self, event_type: str, **kwargs):
        """Log consumer-specific events with structured data"""
        message = f"CONSUMER: {event_type}"
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.info(message)
    
    def log_redis_operation(self, operation: str, **kwargs):
        """Log Redis operations with structured data"""
        message = f"REDIS: {operation}"
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.info(message)
    
    def log_job_processing(self, job_id: str, stage: str, **kwargs):
        """Log job processing stages with structured data"""
        message = f"JOB[{job_id}]: {stage}"
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.info(message)
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics with structured data"""
        message = f"PERF: {operation} ({duration_ms:.2f}ms)"
        if kwargs:
            message = f"{message} | {self._format_kwargs(kwargs)}"
        self.logger.info(message)

# Global logger instance
logger = BetterBundleLogger()

def get_logger(name: str = None) -> BetterBundleLogger:
    """Get a logger instance"""
    if name:
        return BetterBundleLogger(name)
    return logger

# Convenience functions for backward compatibility
def log_info(message: str, **kwargs):
    """Log info message"""
    logger.info(message, **kwargs)

def log_debug(message: str, **kwargs):
    """Log debug message"""
    logger.debug(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Log warning message"""
    logger.warning(message, **kwargs)

def log_error(message: str, **kwargs):
    """Log error message"""
    logger.error(message, **kwargs)

def log_exception(message: str, **kwargs):
    """Log exception with traceback"""
    logger.exception(message, **kwargs)
