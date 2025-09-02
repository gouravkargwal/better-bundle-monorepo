"""
Health check endpoints
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

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


@router.get("/consumer-status")
async def get_consumer_status():
    """Get the status of the Redis streams consumer process"""
    try:
        import psutil

        # Look for the consumer process
        consumer_process = None
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["name"] == "python" and any(
                    "redis-consumer-worker" in str(cmd) for cmd in proc.info["cmdline"]
                ):
                    consumer_process = proc
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if consumer_process:
            consumer_status = {
                "consumer_running": True,
                "consumer_pid": consumer_process.pid,
                "consumer_name": consumer_process.name(),
                "consumer_status": consumer_process.status(),
                "consumer_cpu_percent": consumer_process.cpu_percent(),
                "consumer_memory_mb": round(
                    consumer_process.memory_info().rss / 1024 / 1024, 2
                ),
                "consumer_create_time": consumer_process.create_time(),
            }
        else:
            consumer_status = {
                "consumer_running": False,
                "consumer_pid": None,
                "consumer_name": None,
                "consumer_status": "not_found",
                "consumer_cpu_percent": 0,
                "consumer_memory_mb": 0,
                "consumer_create_time": None,
            }

        return {
            "success": True,
            "consumer_status": consumer_status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting consumer status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get consumer status: {str(e)}"
        )
