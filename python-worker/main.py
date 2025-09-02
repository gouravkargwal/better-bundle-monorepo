#!/usr/bin/env python3
"""
Main entry point for the Python Worker
"""

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,  # This will be 8001 from .env
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )
