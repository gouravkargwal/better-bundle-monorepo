import jwt
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TokenValidationResult:
    """Result of token validation"""

    is_valid: bool
    payload: Optional[Any] = None
    error: Optional[str] = None


class ShopStatus:
    """Shop status constants"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    UNKNOWN = "unknown"


class JWTService:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire = timedelta(minutes=30)  # 30 minutes
        self.refresh_token_expire = timedelta(minutes=90)  # 90 minutes
        self.shop_token_expire = timedelta(hours=2)  # 2 hours for shop tokens
        self.refresh_threshold = timedelta(minutes=15)  # Refresh 15 min before expiry

    def create_shop_token(
        self,
        shop_id: str,
        shop_domain: str,
        shop_status: str = "active",
        subscription_status: str = "unknown",
        shopify_plus: bool = False,
        permissions: Optional[List[str]] = None,
    ) -> str:
        """
        Create a comprehensive shop token with embedded shop status and permissions.

        Args:
            shop_id: Unique shop identifier
            shop_domain: Shopify shop domain
            shop_status: Current shop status (active/suspended/trial)
            subscription_status: Subscription status
            shopify_plus: Whether the shop is Shopify Plus
            permissions: List of permissions (e.g., ["read", "write"])

        Returns:
            Encoded JWT token string
        """
        try:
            now = datetime.utcnow()
            payload = {
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "shop_status": shop_status,
                "subscription_status": subscription_status,
                "shopify_plus": shopify_plus,
                "permissions": permissions or ["read"],
                "token_type": "shop",
                "exp": now + self.shop_token_expire,
                "iat": now,
            }

            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        except Exception as e:
            logger.error(f"Failed to create shop token: {e}")
            raise ValueError(f"Token creation failed: {str(e)}")

    def validate_shop_token(self, token: str) -> TokenValidationResult:
        """
        Validate a shop token and return structured result.

        Args:
            token: JWT token string

        Returns:
            TokenValidationResult with is_valid, payload, and error fields
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("token_type") != "shop":
                return TokenValidationResult(
                    is_valid=False,
                    error="Invalid token type",
                )

            return TokenValidationResult(
                is_valid=True,
                payload=payload,
            )

        except jwt.ExpiredSignatureError:
            return TokenValidationResult(
                is_valid=False,
                error="Token expired",
            )
        except jwt.InvalidTokenError:
            return TokenValidationResult(
                is_valid=False,
                error="Invalid token",
            )
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return TokenValidationResult(
                is_valid=False,
                error="Validation failed",
            )

    def extract_shop_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Extract shop information from a token without full validation.

        Args:
            token: JWT token string

        Returns:
            Dictionary with shop info or None if extraction fails
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})

            return {
                "shop_id": payload.get("shop_id", "unknown"),
                "shop_domain": payload.get("shop_domain"),
                "shop_status": payload.get("shop_status", "unknown"),
                "subscription_status": payload.get("subscription_status", "unknown"),
                "permissions": payload.get("permissions", []),
            }

        except Exception as e:
            logger.error(f"Failed to extract shop info: {e}")
            return None

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """
        Get the expiration datetime of a token.

        Args:
            token: JWT token string

        Returns:
            Datetime when the token expires, or None on error
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp)
            return None
        except Exception as e:
            logger.debug(f"Error getting token expiration: {e}")
            return None

    def get_token_remaining_time(self, token: str) -> Optional[timedelta]:
        """
        Get the remaining time before a token expires.

        Args:
            token: JWT token string

        Returns:
            timedelta representing remaining time, or None on error
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                return None

            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            now = datetime.utcnow()
            remaining = exp_datetime - now

            return remaining if remaining.total_seconds() > 0 else timedelta(0)

        except Exception as e:
            logger.debug(f"Error getting remaining token time: {e}")
            return None

    def create_access_token(
        self,
        shop_id: str,
        shop_domain: str,
        is_service_active: bool = True,
        shopify_plus: bool = False,
    ) -> str:
        """Create access token for shop"""
        try:
            now = datetime.utcnow()
            payload = {
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "is_service_active": is_service_active,
                "shopify_plus": shopify_plus,
                "token_type": "access",
                "exp": now + self.access_token_expire,
                "iat": now,
            }

            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise ValueError(f"Token creation failed: {str(e)}")

    def create_refresh_token(
        self,
        shop_id: str,
        shop_domain: str,
        is_service_active: bool = True,
        shopify_plus: bool = False,
    ) -> str:
        """Create refresh token (longer expiry, includes service status for token refresh)"""
        try:
            now = datetime.utcnow()
            payload = {
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "is_service_active": is_service_active,
                "shopify_plus": shopify_plus,
                "token_type": "refresh",
                "exp": now + self.refresh_token_expire,
                "iat": now,
            }

            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise ValueError(f"Refresh token creation failed: {str(e)}")

    def create_token_pair(
        self,
        shop_id: str,
        shop_domain: str,
        is_service_active: bool = True,
        shopify_plus: bool = False,
    ) -> Dict[str, str]:
        """Create both access and refresh tokens"""
        access_token = self.create_access_token(
            shop_id, shop_domain, is_service_active, shopify_plus
        )
        refresh_token = self.create_refresh_token(
            shop_id, shop_domain, is_service_active, shopify_plus
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": int(self.access_token_expire.total_seconds()),
        }

    def validate_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate access token and return shop info"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("token_type") != "access":
                return {"is_valid": False, "error": "Invalid token type"}

            # Return shop info if valid
            return {
                "shop_id": payload["shop_id"],
                "shop_domain": payload["shop_domain"],
                "is_service_active": payload.get("is_service_active", False),
                "shopify_plus": payload.get("shopify_plus", False),
                "is_valid": True,
                "needs_refresh": self.is_token_expiring_soon(token),
            }

        except jwt.ExpiredSignatureError:
            return {"is_valid": False, "error": "Token expired"}
        except jwt.InvalidTokenError:
            return {"is_valid": False, "error": "Invalid token"}
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return {"is_valid": False, "error": "Validation failed"}

    def validate_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate refresh token.

        If token is expired, extracts shop_id and shop_domain from payload
        without verification so we can regenerate tokens from DB.

        Returns:
            Dict with is_valid, shop_id, shop_domain, and error_code if applicable
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("token_type") != "refresh":
                return {
                    "is_valid": False,
                    "error": "Invalid refresh token",
                    "error_code": "INVALID_TOKEN_TYPE",
                }

            return {
                "shop_id": payload["shop_id"],
                "shop_domain": payload["shop_domain"],
                "is_service_active": payload.get("is_service_active", True),
                "shopify_plus": payload.get("shopify_plus", False),
                "is_valid": True,
            }

        except jwt.ExpiredSignatureError:
            # Token expired - extract shop info without verification
            logger.debug("Refresh token expired, attempting to extract shop info")
            payload = self.decode_token_without_verification(token)

            if payload and payload.get("token_type") == "refresh":
                # Successfully extracted shop info from expired token
                logger.info(
                    f"Extracted shop info from expired refresh token: "
                    f"shop_id={payload.get('shop_id')}"
                )
                return {
                    "is_valid": False,
                    "error": "Refresh token expired",
                    "error_code": "REFRESH_TOKEN_EXPIRED",
                    "shop_id": payload.get("shop_id"),
                    "shop_domain": payload.get("shop_domain"),
                }
            else:
                # Failed to extract info from expired token
                logger.warning("Could not extract shop info from expired refresh token")
                return {
                    "is_valid": False,
                    "error": "Refresh token expired - cannot extract shop info",
                    "error_code": "REFRESH_TOKEN_EXPIRED",
                }

        except jwt.InvalidTokenError:
            return {
                "is_valid": False,
                "error": "Invalid refresh token",
                "error_code": "INVALID_TOKEN",
            }
        except Exception as e:
            logger.error(f"Refresh token validation error: {e}")
            return {
                "is_valid": False,
                "error": "Validation failed",
                "error_code": "VALIDATION_ERROR",
            }

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Create new access token using refresh token"""

        # Validate refresh token
        refresh_result = self.validate_refresh_token(refresh_token)
        if not refresh_result.get("is_valid"):
            return None

        # Create new access token
        new_access_token = self.create_access_token(
            refresh_result["shop_id"],
            refresh_result["shop_domain"],
            refresh_result.get("is_service_active", True),
            refresh_result.get("shopify_plus", False),
        )

        return {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": int(self.access_token_expire.total_seconds()),
        }

    def decode_token_without_verification(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode JWT token without verification to extract payload.

        Used when token is expired but we need to extract shop_id and shop_domain
        from the payload for token regeneration.

        Args:
            token: JWT token string

        Returns:
            Token payload dictionary if decode succeeds, None otherwise
        """
        try:
            # Decode without signature verification to get payload even from expired tokens
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            logger.error(f"Failed to decode token without verification: {e}")
            return None

    def is_token_expiring_soon(self, token: str) -> bool:
        """
        Check if token expires within refresh threshold.

        Verifies the signature first to prevent token expiration bypass attacks.
        """
        try:
            # H3 FIX: Verify signature first, then check expiry
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            exp_timestamp = payload.get("exp")

            if not exp_timestamp:
                return True

            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            now = datetime.utcnow()

            return (exp_datetime - now) <= self.refresh_threshold

        except jwt.ExpiredSignatureError:
            # Token is already expired — treat as expiring
            return True
        except jwt.InvalidTokenError:
            # Token signature is invalid
            logger.warning("Invalid token when checking expiration")
            return True
        except Exception as e:
            logger.debug(f"Error checking token expiration: {e}")
            return True  # Treat as expiring on error


# Global instance
jwt_service = JWTService()
