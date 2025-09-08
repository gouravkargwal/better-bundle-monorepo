"""
Shopify Webhook Signature Verification for security and authenticity.

This module provides secure webhook signature verification to ensure
that incoming requests are genuinely from Shopify and haven't been
tampered with.
"""

import hmac
import hashlib
import base64
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database

logger = get_logger(__name__)


class ShopifyWebhookVerifier:
    """
    Shopify webhook signature verification for security.

    Features:
    - HMAC-SHA256 signature verification
    - Timestamp validation to prevent replay attacks
    - Shop-specific webhook secrets
    - Comprehensive error handling
    """

    def __init__(self, max_timestamp_age_seconds: int = 300):  # 5 minutes
        self.max_timestamp_age_seconds = max_timestamp_age_seconds

    async def verify_webhook_signature(
        self,
        shop_domain: str,
        payload: bytes,
        signature: str,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify Shopify webhook signature

        Args:
            shop_domain: Shop domain from the request
            payload: Raw request body
            signature: X-Shopify-Hmac-Sha256 header value
            timestamp: X-Shopify-Timestamp header value (optional)

        Returns:
            Verification result with status and details
        """
        try:
            # Get shop webhook secret
            webhook_secret = await self._get_webhook_secret(shop_domain)
            if not webhook_secret:
                return {
                    "verified": False,
                    "error": "Webhook secret not found for shop",
                    "shop_domain": shop_domain,
                }

            # Verify timestamp if provided
            if timestamp:
                timestamp_result = self._verify_timestamp(timestamp)
                if not timestamp_result["valid"]:
                    return {
                        "verified": False,
                        "error": "Invalid timestamp",
                        "details": timestamp_result["error"],
                    }

            # Verify signature
            expected_signature = self._calculate_signature(payload, webhook_secret)

            if not hmac.compare_digest(signature, expected_signature):
                return {
                    "verified": False,
                    "error": "Signature verification failed",
                    "shop_domain": shop_domain,
                }

            return {
                "verified": True,
                "shop_domain": shop_domain,
                "timestamp": timestamp,
                "message": "Webhook signature verified successfully",
            }

        except Exception as e:
            logger.error(f"Webhook verification failed for shop {shop_domain}: {e}")
            return {
                "verified": False,
                "error": "Verification process failed",
                "details": str(e),
            }

    async def _get_webhook_secret(self, shop_domain: str) -> Optional[str]:
        """
        Get webhook secret for a shop from database

        Args:
            shop_domain: Shop domain

        Returns:
            Webhook secret or None if not found
        """
        try:
            db = await get_database()

            # Get shop by domain
            shop = await db.shop.find_unique(
                where={"shopDomain": shop_domain}, select={"webhookSecret": True}
            )

            if shop and shop.webhookSecret:
                return shop.webhookSecret

            logger.warning(f"No webhook secret found for shop {shop_domain}")
            return None

        except Exception as e:
            logger.error(f"Failed to get webhook secret for shop {shop_domain}: {e}")
            return None

    def _verify_timestamp(self, timestamp: str) -> Dict[str, Any]:
        """
        Verify webhook timestamp to prevent replay attacks

        Args:
            timestamp: ISO timestamp string

        Returns:
            Verification result
        """
        try:
            # Parse timestamp
            webhook_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            current_time = datetime.now(timezone.utc)

            # Check if timestamp is within acceptable range
            time_diff = abs((current_time - webhook_time).total_seconds())

            if time_diff > self.max_timestamp_age_seconds:
                return {
                    "valid": False,
                    "error": f"Timestamp too old: {time_diff:.1f}s > {self.max_timestamp_age_seconds}s",
                }

            return {"valid": True, "time_diff_seconds": time_diff}

        except ValueError as e:
            return {"valid": False, "error": f"Invalid timestamp format: {e}"}
        except Exception as e:
            return {"valid": False, "error": f"Timestamp verification failed: {e}"}

    def _calculate_signature(self, payload: bytes, secret: str) -> str:
        """
        Calculate expected HMAC-SHA256 signature

        Args:
            payload: Raw request body
            secret: Webhook secret

        Returns:
            Base64-encoded signature
        """
        signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()

        return base64.b64encode(signature).decode("utf-8")

    async def verify_behavioral_event_signature(
        self,
        shop_domain: str,
        event_data: Dict[str, Any],
        signature: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify behavioral event signature (for Web Pixel events)

        Note: Web Pixel events may not always have signatures,
        so this is more lenient than webhook verification.

        Args:
            shop_domain: Shop domain
            event_data: Event data dictionary
            signature: Optional signature
            timestamp: Optional timestamp

        Returns:
            Verification result
        """
        try:
            # For behavioral events, we're more lenient since they come from
            # the client-side and may not always have signatures

            if signature:
                # If signature is provided, verify it
                payload = str(event_data).encode("utf-8")
                return await self.verify_webhook_signature(
                    shop_domain, payload, signature, timestamp
                )
            else:
                # No signature provided - check if shop exists and is valid
                db = await get_database()
                shop = await db.shop.find_unique(
                    where={"shopDomain": shop_domain},
                    select={"id": True, "isActive": True},
                )

                if not shop:
                    return {
                        "verified": False,
                        "error": "Shop not found",
                        "shop_domain": shop_domain,
                    }

                if not shop.isActive:
                    return {
                        "verified": False,
                        "error": "Shop is not active",
                        "shop_domain": shop_domain,
                    }

                return {
                    "verified": True,
                    "shop_domain": shop_domain,
                    "message": "Behavioral event accepted (no signature verification)",
                }

        except Exception as e:
            logger.error(
                f"Behavioral event verification failed for shop {shop_domain}: {e}"
            )
            return {
                "verified": False,
                "error": "Verification process failed",
                "details": str(e),
            }

    async def update_webhook_secret(
        self, shop_domain: str, secret: str
    ) -> Dict[str, Any]:
        """
        Update webhook secret for a shop

        Args:
            shop_domain: Shop domain
            secret: New webhook secret

        Returns:
            Update result
        """
        try:
            db = await get_database()

            # Update shop webhook secret
            updated_shop = await db.shop.update(
                where={"shopDomain": shop_domain}, data={"webhookSecret": secret}
            )

            logger.info(f"Updated webhook secret for shop {shop_domain}")

            return {
                "status": "success",
                "shop_domain": shop_domain,
                "message": "Webhook secret updated successfully",
            }

        except Exception as e:
            logger.error(f"Failed to update webhook secret for shop {shop_domain}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_webhook_secret_status(self, shop_domain: str) -> Dict[str, Any]:
        """
        Get webhook secret status for a shop

        Args:
            shop_domain: Shop domain

        Returns:
            Secret status information
        """
        try:
            db = await get_database()

            shop = await db.shop.find_unique(
                where={"shopDomain": shop_domain},
                select={
                    "id": True,
                    "shopDomain": True,
                    "webhookSecret": True,
                    "isActive": True,
                },
            )

            if not shop:
                return {
                    "status": "error",
                    "message": "Shop not found",
                    "shop_domain": shop_domain,
                }

            return {
                "status": "success",
                "shop_domain": shop_domain,
                "has_secret": bool(shop.webhookSecret),
                "is_active": shop.isActive,
                "secret_length": len(shop.webhookSecret) if shop.webhookSecret else 0,
            }

        except Exception as e:
            logger.error(
                f"Failed to get webhook secret status for shop {shop_domain}: {e}"
            )
            return {"status": "error", "message": str(e)}
