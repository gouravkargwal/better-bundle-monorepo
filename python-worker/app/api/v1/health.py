"""
Health check endpoints
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import check_database_health
from app.core.redis_client import check_redis_health
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str
    service: str
    version: str
    timestamp: float
    checks: dict


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        timestamp=asyncio.get_event_loop().time(),
        checks={},
    )


@router.get("/detailed", response_model=HealthResponse)
async def detailed_health_check():
    """Detailed health check with database and Redis status"""

    start_time = asyncio.get_event_loop().time()
    checks = {}
    overall_status = "healthy"

    # Check database health
    try:
        db_start = asyncio.get_event_loop().time()
        db_healthy = await asyncio.wait_for(
            check_database_health(), timeout=settings.HEALTH_CHECK_TIMEOUT
        )
        db_duration = (asyncio.get_event_loop().time() - db_start) * 1000

        checks["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "duration_ms": db_duration,
        }

        if not db_healthy:
            overall_status = "unhealthy"

    except asyncio.TimeoutError:
        checks["database"] = {
            "status": "timeout",
            "duration_ms": settings.HEALTH_CHECK_TIMEOUT * 1000,
        }
        overall_status = "unhealthy"
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall_status = "unhealthy"

    # Check Redis health
    try:
        redis_start = asyncio.get_event_loop().time()
        redis_healthy = await asyncio.wait_for(
            check_redis_health(), timeout=settings.HEALTH_CHECK_TIMEOUT
        )
        redis_duration = (asyncio.get_event_loop().time() - redis_start) * 1000

        checks["redis"] = {
            "status": "healthy" if redis_healthy else "unhealthy",
            "duration_ms": redis_duration,
        }

        if not redis_healthy:
            overall_status = "unhealthy"

    except asyncio.TimeoutError:
        checks["redis"] = {
            "status": "timeout",
            "duration_ms": settings.HEALTH_CHECK_TIMEOUT * 1000,
        }
        overall_status = "unhealthy"
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        overall_status = "unhealthy"

    total_duration = (asyncio.get_event_loop().time() - start_time) * 1000

    response = HealthResponse(
        status=overall_status,
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        timestamp=asyncio.get_event_loop().time(),
        checks=checks,
    )

    if overall_status != "healthy":
        raise HTTPException(status_code=503, detail=response.dict())

    return response


@router.get("/ready")
async def readiness_check():
    """Readiness check for container orchestration"""

    # Simple readiness check - just verify we can respond
    return {
        "status": "ready",
        "service": settings.PROJECT_NAME,
        "timestamp": asyncio.get_event_loop().time(),
    }


@router.get("/live")
async def liveness_check():
    """Liveness check for container orchestration"""

    # Simple liveness check
    return {
        "status": "alive",
        "service": settings.PROJECT_NAME,
        "timestamp": asyncio.get_event_loop().time(),
    }
