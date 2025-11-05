from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from app.services.jwt_service import jwt_service
from app.core.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer()


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
