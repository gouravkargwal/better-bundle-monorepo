from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.services.jwt_service import jwt_service
from app.core.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer()

@dataclass
class StorefrontAuthContext:
    """Returned by get_storefront_authorization dependency"""
    is_authorized: bool
    shop_id: Optional[str]
    shop_domain: Optional[str]
    fail_reason: Optional[str]


async def get_storefront_authorization(request: Request) -> StorefrontAuthContext:
    """
    Dependency for Storefront (Theme App Extension) endpoints.
    
    Storefront extensions must NEVER return 401/403 errors when suspended,
    because those errors print in bright red in the shopper's browser console
    and violate Shopify App guidelines.
    
    This dependency validates the JWT and checks for suspension, but never raises
    an HTTPException. It returns an auth context that the route handler can use
    to gracefully fail silent (e.g., returning an empty recommendation array).
    """
    authorization = request.headers.get("Authorization")
    
    if not authorization or not authorization.startswith("Bearer "):
        return StorefrontAuthContext(
            is_authorized=False, 
            shop_id=None, 
            shop_domain=None,
            fail_reason="missing_auth_header"
        )
        
    token = authorization.split("Bearer ")[1]
    
    try:
        validation_result = jwt_service.validate_access_token(token)
        
        if not validation_result.get("is_valid"):
            logger.warning(f"Storefront token invalid: {validation_result.get('error')}")
            return StorefrontAuthContext(
                is_authorized=False, 
                shop_id=None, 
                shop_domain=None,
                fail_reason="invalid_token"
            )
            
        shop_id = validation_result.get("shop_id")
        shop_domain = validation_result.get("shop_domain")
        
        # Check if service is inactive in the token (e.g. Trial Completed but no billing setup)
        if not validation_result.get("is_service_active", True):
            logger.info(f"Storefront silent suppression: Service inactive for shop {shop_id}")
            return StorefrontAuthContext(
                is_authorized=False, 
                shop_id=shop_id, 
                shop_domain=shop_domain,
                fail_reason="service_suspended"
            )
            
        # Check real-time Redis cache for instant suspensions (e.g. monthly cap hit)
        try:
            from app.core.redis_client import get_redis_client
            redis = await get_redis_client()
            is_suspended = await redis.exists(f"suspension:{shop_id}")
            if is_suspended:
                logger.info(f"Storefront silent suppression: Shop {shop_id} in active suspension cache")
                return StorefrontAuthContext(
                    is_authorized=False, 
                    shop_id=shop_id, 
                    shop_domain=shop_domain,
                    fail_reason="service_suspended"
                )
        except Exception as cache_err:
            logger.debug(f"Redis check failed during storefront auth: {cache_err}")

        # Fully authorized
        return StorefrontAuthContext(
            is_authorized=True,
            shop_id=shop_id,
            shop_domain=shop_domain,
            fail_reason=None
        )

    except Exception as e:
        logger.error(f"Storefront authorization dependency error: {str(e)}")
        return StorefrontAuthContext(
            is_authorized=False, 
            shop_id=None, 
            shop_domain=None,
            fail_reason="auth_error"
        )


async def get_shop_authorization(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Dependency to validate JWT access token and extract shop authorization

    Returns:
        Dict containing validated shop info and token metadata

    Raises:
        HTTPException: 401 if token invalid or expired
        HTTPException: 403 if token type incorrect
    """
    token = credentials.credentials

    try:
        # Validate access token
        validation_result = jwt_service.validate_access_token(token)

        if not validation_result.get("is_valid"):
            error_msg = validation_result.get("error", "Invalid token")
            logger.warning(f"Token validation failed: {error_msg}")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract shop info
        shop_auth = {
            "shop_id": validation_result["shop_id"],
            "shop_domain": validation_result["shop_domain"],
            "is_service_active": validation_result.get("is_service_active", False),
            "shopify_plus": validation_result.get("shopify_plus", False),
            "jwt_token": token,
            "needs_refresh": validation_result.get("needs_refresh", False),
        }

        # Check if service is active (simple boolean check)
        if not validation_result.get("is_service_active", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Services suspended",
                    "message": "This shop's services are currently inactive",
                    "is_service_active": False,
                },
            )

        logger.debug(f"Shop authorized: {shop_auth['shop_id']}")
        return shop_auth

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authorization dependency error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
