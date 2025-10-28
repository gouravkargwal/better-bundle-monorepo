"""
Authentication API endpoints
Handles JWT token generation and validation for BetterBundle services
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from app.services.jwt_service import jwt_service, TokenValidationResult, ShopStatus
from app.middleware.suspension_middleware import suspension_middleware
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


# Request/Response Models
class ShopTokenRequest(BaseModel):
    """Request model for shop token generation"""

    shop_domain: Optional[str] = None
    customer_id: Optional[str] = None
    force_refresh: bool = False


class ShopTokenResponse(BaseModel):
    """Response model for shop token generation"""

    token: str
    expires_in: int  # seconds
    shop_id: str
    shop_domain: str
    shop_status: str
    subscription_status: str
    permissions: list


class TokenValidationRequest(BaseModel):
    """Request model for token validation"""

    token: str


class TokenValidationResponse(BaseModel):
    """Response model for token validation"""

    is_valid: bool
    shop_id: Optional[str] = None
    shop_domain: Optional[str] = None
    shop_status: Optional[str] = None
    subscription_status: Optional[str] = None
    permissions: Optional[list] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


class TokenRefreshRequest(BaseModel):
    """Request model for token refresh"""

    token: str


class TokenRefreshResponse(BaseModel):
    """Response model for token refresh"""

    token: str
    expires_in: int
    refreshed: bool


# Helper Functions
async def get_shop_domain_from_customer(customer_id: str) -> Optional[str]:
    """
    Get shop domain from customer ID by looking up the customer's shop

    Args:
        customer_id: Customer ID to look up

    Returns:
        Shop domain if found, None otherwise
    """
    try:
        from app.recommandations.shop_lookup_service import ShopLookupService

        shop_lookup_service = ShopLookupService()
        shop_domain = await shop_lookup_service.get_shop_domain_from_customer_id(
            customer_id
        )

        if shop_domain:
            logger.info(f"Found shop domain {shop_domain} for customer {customer_id}")
        else:
            logger.warning(f"No shop domain found for customer {customer_id}")

        return shop_domain

    except Exception as e:
        logger.error(f"Error looking up shop domain for customer {customer_id}: {e}")
        return None


async def get_shop_status_for_token(shop_domain: str) -> Dict[str, Any]:
    """
    Get shop status information for token generation

    Args:
        shop_domain: Shop domain to get status for

    Returns:
        Dictionary with shop status information
    """
    try:
        # Get shop status from suspension middleware
        status = await suspension_middleware.check_shop_suspension(shop_domain)

        # Get additional shop info from database
        from app.core.database.session import get_session_context
        from app.core.database.models.shop import Shop
        from sqlalchemy import select

        shopify_plus = False
        shop_id = "unknown"

        try:
            async with get_session_context() as session:
                result = await session.execute(
                    select(Shop).where(Shop.shop_domain == shop_domain)
                )
                shop = result.scalar_one_or_none()
                if shop:
                    shopify_plus = shop.shopify_plus
                    shop_id = shop.id
        except Exception as db_error:
            logger.warning(
                f"Could not fetch shop details for {shop_domain}: {db_error}"
            )

        return {
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "shop_status": (
                "active" if not status.get("isSuspended", True) else "suspended"
            ),
            "subscription_status": status.get("subscription_status", "unknown"),
            "shopify_plus": shopify_plus,
            "permissions": (
                ["read", "write"] if not status.get("isSuspended", True) else ["read"]
            ),
        }

    except Exception as e:
        logger.error(f"Error getting shop status for {shop_domain}: {e}")
        # Return default suspended status on error
        return {
            "shop_id": "unknown",
            "shop_domain": shop_domain,
            "shop_status": "suspended",
            "subscription_status": "unknown",
            "shopify_plus": False,
            "permissions": ["read"],
        }


# API Endpoints
@router.post("/shop-token", response_model=ShopTokenResponse)
async def generate_shop_token(request: ShopTokenRequest):
    """
    Generate JWT token for shop access

    This endpoint creates a JWT token with embedded shop status and permissions.
    The token is stateless and contains all necessary information for authorization.

    Can be called with either:
    - shop_domain: Direct shop domain
    - customer_id: Look up shop domain from customer's session history
    """
    try:
        # Determine shop domain
        shop_domain = request.shop_domain

        if not shop_domain and request.customer_id:
            logger.info(f"🔍 Looking up shop domain for customer {request.customer_id}")
            shop_domain = await get_shop_domain_from_customer(request.customer_id)

            if not shop_domain:
                raise HTTPException(
                    status_code=404,
                    detail=f"No shop domain found for customer {request.customer_id}",
                )

        if not shop_domain:
            raise HTTPException(
                status_code=400,
                detail="Either shop_domain or customer_id must be provided",
            )

        logger.info(f"🔑 Generating shop token for {shop_domain}")

        # Get shop status information
        shop_info = await get_shop_status_for_token(shop_domain)

        # Create JWT token
        token = jwt_service.create_shop_token(
            shop_id=shop_info["shop_id"],
            shop_domain=shop_info["shop_domain"],
            shop_status=shop_info["shop_status"],
            subscription_status=shop_info["subscription_status"],
            shopify_plus=shop_info["shopify_plus"],
            permissions=shop_info["permissions"],
        )

        # Get token expiration info
        expires_in = jwt_service.shop_token_expire.total_seconds()

        logger.info(
            f"✅ Generated shop token for {shop_domain} (status: {shop_info['shop_status']})"
        )

        return ShopTokenResponse(
            token=token,
            expires_in=int(expires_in),
            shop_id=shop_info["shop_id"],
            shop_domain=shop_info["shop_domain"],
            shop_status=shop_info["shop_status"],
            subscription_status=shop_info["subscription_status"],
            permissions=shop_info["permissions"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate shop token: {e}")
        raise HTTPException(
            status_code=500, detail=f"Token generation failed: {str(e)}"
        )


@router.post("/validate-token", response_model=TokenValidationResponse)
async def validate_token(request: TokenValidationRequest):
    """
    Validate JWT token and return payload information

    This endpoint validates a JWT token and returns the embedded
    shop information without requiring database queries.
    """
    try:
        logger.debug(f"🔍 Validating token")

        # Validate token
        result = jwt_service.validate_shop_token(request.token)

        if not result.is_valid:
            logger.debug(f"❌ Token validation failed: {result.error}")
            return TokenValidationResponse(is_valid=False, error=result.error)

        # Extract information from payload
        payload = result.payload
        expires_at = jwt_service.get_token_expiration(request.token)

        logger.debug(f"✅ Token validated for {payload.shop_domain}")

        return TokenValidationResponse(
            is_valid=True,
            shop_id=payload.shop_id,
            shop_domain=payload.shop_domain,
            shop_status=payload.shop_status,
            subscription_status=payload.subscription_status,
            permissions=payload.permissions,
            expires_at=expires_at,
        )

    except Exception as e:
        logger.error(f"❌ Token validation error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Token validation failed: {str(e)}"
        )


@router.post("/refresh-token", response_model=TokenRefreshResponse)
async def refresh_token(request: TokenRefreshRequest):
    """
    Refresh JWT token if it's expiring soon

    This endpoint checks if a token is expiring soon and generates
    a new token with updated shop status information.
    """
    try:
        logger.debug(f"🔄 Checking token for refresh")

        # Check if token is expiring soon
        if not jwt_service.is_token_expiring_soon(request.token):
            logger.debug("Token not expiring soon, returning original")
            return TokenRefreshResponse(
                token=request.token,
                expires_in=int(jwt_service.shop_token_expire.total_seconds()),
                refreshed=False,
            )

        # Extract shop domain from current token
        shop_info = jwt_service.extract_shop_info(request.token)
        if not shop_info:
            raise HTTPException(status_code=400, detail="Invalid token format")

        shop_domain = shop_info["shop_domain"]
        logger.info(f"🔄 Refreshing token for {shop_domain}")

        # Get updated shop status
        updated_shop_info = await get_shop_status_for_token(shop_domain)

        # Create new token
        new_token = jwt_service.create_shop_token(
            shop_id=updated_shop_info["shop_id"],
            shop_domain=updated_shop_info["shop_domain"],
            shop_status=updated_shop_info["shop_status"],
            subscription_status=updated_shop_info["subscription_status"],
            permissions=updated_shop_info["permissions"],
        )

        logger.info(
            f"✅ Token refreshed for {shop_domain} (status: {updated_shop_info['shop_status']})"
        )

        return TokenRefreshResponse(
            token=new_token,
            expires_in=int(jwt_service.shop_token_expire.total_seconds()),
            refreshed=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token refresh error: {e}")
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


@router.get("/token-info")
async def get_token_info(authorization: str = Header(None)):
    """
    Get information about the current token from Authorization header

    This endpoint extracts token information without full validation,
    useful for debugging and monitoring.
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401, detail="Missing or invalid Authorization header"
            )

        token = authorization.split(" ")[1]

        # Extract token information
        shop_info = jwt_service.extract_shop_info(token)
        if not shop_info:
            raise HTTPException(status_code=400, detail="Invalid token format")

        # Get remaining time
        remaining_time = jwt_service.get_token_remaining_time(token)
        expires_at = jwt_service.get_token_expiration(token)

        return {
            "shop_id": shop_info["shop_id"],
            "shop_domain": shop_info["shop_domain"],
            "shop_status": shop_info["shop_status"],
            "subscription_status": shop_info["subscription_status"],
            "permissions": shop_info["permissions"],
            "expires_at": expires_at.isoformat() if expires_at else None,
            "remaining_seconds": (
                int(remaining_time.total_seconds()) if remaining_time else 0
            ),
            "is_expiring_soon": jwt_service.is_token_expiring_soon(token),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token info error: {e}")
        raise HTTPException(status_code=500, detail=f"Token info failed: {str(e)}")


@router.get("/health")
async def auth_health_check():
    """
    Health check for authentication service

    This endpoint verifies that the JWT service is working correctly.
    """
    try:
        # Test token creation and validation
        test_token = jwt_service.create_shop_token(
            shop_id="test-shop-id",
            shop_domain="test-shop.myshopify.com",
            shop_status="active",
            subscription_status="active",
            permissions=["read", "write"],
        )

        result = jwt_service.validate_shop_token(test_token)

        if not result.is_valid:
            raise Exception("Token validation failed")

        return {
            "status": "healthy",
            "service": "jwt-auth",
            "timestamp": datetime.utcnow().isoformat(),
            "test_token_valid": True,
        }

    except Exception as e:
        logger.error(f"❌ Auth health check failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Authentication service unhealthy: {str(e)}"
        )
