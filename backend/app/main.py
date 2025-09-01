"""
Main FastAPI application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import get_prisma_client, close_prisma_client
from app.api.v1 import bundles, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    setup_logging()
    await get_prisma_client()
    yield
    # Shutdown
    await close_prisma_client()


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Machine Learning API for bundle analysis and cosine similarity calculations",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Include API routers
app.include_router(
    bundles.router,
    prefix=f"{settings.API_V1_STR}/bundle-analysis",
    tags=["bundle-analysis"],
)

app.include_router(health.router, prefix="/health", tags=["health"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"{settings.PROJECT_NAME} is running",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
