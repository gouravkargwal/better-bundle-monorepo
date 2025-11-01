from fastapi import APIRouter
from app.controllers.auth_controller import auth_controller
from app.models.auth_models import (
    GenerateTokenRequest,
    GenerateTokenResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/generate-token", response_model=GenerateTokenResponse)
async def generate_access_token(request: GenerateTokenRequest):
    return await auth_controller.generate_shop_token(request)


@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh_access_token(request: RefreshTokenRequest):
    return await auth_controller.refresh_access_token(request)
