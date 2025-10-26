"""
JWT Service for BetterBundle
Handles all JWT token operations including creation, validation, and refresh
Following industry best practices for microservices authentication
"""

import jwt
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TokenType(Enum):
    """JWT token types"""

    SHOP_ACCESS = "shop_access"
    ADMIN_ACCESS = "admin_access"
    API_ACCESS = "api_access"


class ShopStatus(Enum):
    """Shop status values"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL_COMPLETED = "trial_completed"
    CANCELLED = "cancelled"


@dataclass
class ShopTokenPayload:
    """Shop JWT token payload structure"""

    shop_id: str
    shop_domain: str
    shop_status: str
    subscription_status: str
    permissions: List[str]
    exp: datetime
    iat: datetime
    type: str = TokenType.SHOP_ACCESS.value


@dataclass
class TokenValidationResult:
    """Result of token validation"""

    is_valid: bool
    payload: Optional[ShopTokenPayload] = None
    error: Optional[str] = None


class JWTService:
    """
    JWT Service for handling all JWT operations

    This service follows industry best practices:
    - Stateless token validation
    - Embedded permissions and status
    - Configurable expiration times
    - Secure token generation
    - Comprehensive error handling
    """

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"

        # Token expiration times (configurable)
        self.shop_token_expire = timedelta(hours=1)  # 1 hour for shop tokens
        self.admin_token_expire = timedelta(hours=8)  # 8 hours for admin tokens
        self.api_token_expire = timedelta(days=30)  # 30 days for API tokens

        # Token refresh threshold (refresh 5 minutes before expiry)
        self.refresh_threshold = timedelta(minutes=5)

    def create_shop_token(
        self,
        shop_id: str,
        shop_domain: str,
        shop_status: str,
        subscription_status: str,
        permissions: Optional[List[str]] = None,
    ) -> str:
        """
        Create JWT token for shop access

        Args:
            shop_id: Unique shop identifier
            shop_domain: Shop domain name
            shop_status: Current shop status (active, suspended, etc.)
            subscription_status: Current subscription status
            permissions: List of permissions for this shop

        Returns:
            JWT token string
        """
        try:
            now = datetime.utcnow()
            payload = {
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "shop_status": shop_status,
                "subscription_status": subscription_status,
                "permissions": permissions or ["read", "write"],
                "exp": now + self.shop_token_expire,
                "iat": now,
                "type": TokenType.SHOP_ACCESS.value,
                "iss": "betterbundle",  # Issuer
                "aud": "shopify-extensions",  # Audience
            }

            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

            logger.debug(
                f"🔑 Created shop token for {shop_domain} (status: {shop_status})"
            )
            return token

        except Exception as e:
            logger.error(f"❌ Failed to create shop token for {shop_domain}: {e}")
            raise ValueError(f"Token creation failed: {str(e)}")

    def validate_shop_token(self, token: str) -> TokenValidationResult:
        """
        Validate shop JWT token

        Args:
            token: JWT token string

        Returns:
            TokenValidationResult with validation status and payload
        """
        try:
            # Decode and validate token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_signature": True,
                },
            )

            # Validate token type
            if payload.get("type") != TokenType.SHOP_ACCESS.value:
                return TokenValidationResult(is_valid=False, error="Invalid token type")

            # Validate required fields
            required_fields = ["shop_id", "shop_domain", "shop_status", "exp", "iat"]
            for field in required_fields:
                if field not in payload:
                    return TokenValidationResult(
                        is_valid=False, error=f"Missing required field: {field}"
                    )

            # Create payload object
            shop_payload = ShopTokenPayload(
                shop_id=payload["shop_id"],
                shop_domain=payload["shop_domain"],
                shop_status=payload["shop_status"],
                subscription_status=payload.get("subscription_status", "unknown"),
                permissions=payload.get("permissions", []),
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                type=payload["type"],
            )

            logger.debug(f"✅ Valid shop token for {shop_payload.shop_domain}")
            return TokenValidationResult(is_valid=True, payload=shop_payload)

        except jwt.ExpiredSignatureError:
            logger.debug("⏰ Shop token expired")
            return TokenValidationResult(is_valid=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            logger.debug(f"❌ Invalid shop token: {e}")
            return TokenValidationResult(
                is_valid=False, error=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ Token validation error: {e}")
            return TokenValidationResult(
                is_valid=False, error=f"Validation error: {str(e)}"
            )

    def is_token_expiring_soon(self, token: str) -> bool:
        """
        Check if token is expiring soon (within refresh threshold)

        Args:
            token: JWT token string

        Returns:
            True if token expires within refresh threshold
        """
        try:
            # Decode without verification to get expiration
            payload = jwt.decode(token, options={"verify_signature": False})
            exp_timestamp = payload.get("exp")

            if not exp_timestamp:
                return True  # Treat as expiring if no expiration

            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            now = datetime.utcnow()

            return (exp_datetime - now) <= self.refresh_threshold

        except Exception as e:
            logger.debug(f"Error checking token expiration: {e}")
            return True  # Treat as expiring on error

    def extract_shop_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Extract shop information from token without full validation

        Args:
            token: JWT token string

        Returns:
            Dictionary with shop information or None if invalid
        """
        try:
            # Decode without verification to extract info
            payload = jwt.decode(token, options={"verify_signature": False})

            return {
                "shop_id": payload.get("shop_id"),
                "shop_domain": payload.get("shop_domain"),
                "shop_status": payload.get("shop_status"),
                "subscription_status": payload.get("subscription_status"),
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp"),
                "type": payload.get("type"),
            }

        except Exception as e:
            logger.debug(f"Error extracting shop info: {e}")
            return None

    def create_admin_token(self, admin_id: str, permissions: List[str]) -> str:
        """
        Create JWT token for admin access

        Args:
            admin_id: Admin user identifier
            permissions: List of admin permissions

        Returns:
            JWT token string
        """
        try:
            now = datetime.utcnow()
            payload = {
                "admin_id": admin_id,
                "permissions": permissions,
                "exp": now + self.admin_token_expire,
                "iat": now,
                "type": TokenType.ADMIN_ACCESS.value,
                "iss": "betterbundle",
                "aud": "admin-panel",
            }

            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"🔑 Created admin token for {admin_id}")
            return token

        except Exception as e:
            logger.error(f"❌ Failed to create admin token: {e}")
            raise ValueError(f"Admin token creation failed: {str(e)}")

    def create_api_token(self, api_key: str, permissions: List[str]) -> str:
        """
        Create JWT token for API access

        Args:
            api_key: API key identifier
            permissions: List of API permissions

        Returns:
            JWT token string
        """
        try:
            now = datetime.utcnow()
            payload = {
                "api_key": api_key,
                "permissions": permissions,
                "exp": now + self.api_token_expire,
                "iat": now,
                "type": TokenType.API_ACCESS.value,
                "iss": "betterbundle",
                "aud": "api-clients",
            }

            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"🔑 Created API token for {api_key}")
            return token

        except Exception as e:
            logger.error(f"❌ Failed to create API token: {e}")
            raise ValueError(f"API token creation failed: {str(e)}")

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """
        Get token expiration time

        Args:
            token: JWT token string

        Returns:
            Expiration datetime or None if invalid
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
        Get remaining time until token expiration

        Args:
            token: JWT token string

        Returns:
            Remaining time as timedelta or None if invalid
        """
        exp_time = self.get_token_expiration(token)
        if exp_time:
            now = datetime.utcnow()
            remaining = exp_time - now
            return remaining if remaining.total_seconds() > 0 else timedelta(0)

        return None


# Global JWT service instance
jwt_service = JWTService()
