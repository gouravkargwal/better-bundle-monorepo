"""
Health check API endpoints
"""

from fastapi import APIRouter, Depends
from prisma import Prisma
from app.core.database import get_db, health_check
from app.models.responses import HealthCheckResponse
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
async def health_check_endpoint() -> HealthCheckResponse:
    """
    Health check endpoint

    Returns:
        HealthCheckResponse with service status
    """
    try:
        # Check database health
        db_healthy = await health_check()

        return HealthCheckResponse(
            success=True,
            message="Service is healthy",
            status="healthy" if db_healthy else "degraded",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
            database=db_healthy,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthCheckResponse(
            success=False,
            message="Service health check failed",
            status="unhealthy",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
            database=False,
        )


@router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes

    Returns:
        Ready status
    """
    try:
        # Check if database is accessible
        db_healthy = await health_check()

        if db_healthy:
            return {"status": "ready"}
        else:
            return {"status": "not ready", "reason": "Database connection failed"}

    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return {"status": "not ready", "reason": str(e)}


@router.get("/live")
async def liveness_check():
    """
    Liveness check endpoint for Kubernetes

    Returns:
        Live status
    """
    return {"status": "alive"}
