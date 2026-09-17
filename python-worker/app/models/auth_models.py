from pydantic import BaseModel, field_validator
from typing import Any, Optional


class GenerateTokenRequest(BaseModel):
    shop_domain: str
    customer_id: Optional[str] = None
    force_refresh: bool = False

    @field_validator("customer_id", mode="before")
    @classmethod
    def coerce_customer_id(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class GenerateTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    needs_refresh: bool


class RefreshTokenRequest(BaseModel):
    refresh_token: str  # Changed from 'token' to match controller usage
    is_service_active: Optional[bool] = (
        None  # Optional service active status for valid token refresh
    )
    shopify_plus: Optional[bool] = False  # Optional shopify_plus flag


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = (
        None  # Only included when refresh token was regenerated
    )
    expires_in: int
    refresh_expires_in: Optional[int] = (
        None  # Only included when refresh token was regenerated
    )
