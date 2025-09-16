#!/usr/bin/env python3
"""
Simple test to verify the field extractor handles refund payloads correctly
"""

import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.domains.shopify.services.field_extractor import FieldExtractorService
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_refund_extraction():
    """Test the field extractor with a refund payload"""

    # Create a refund payload
    refund_payload = {
        "id": 890088186047892319,  # Refund ID
        "order_id": 6075126841483,  # Order ID
        "created_at": datetime.now().isoformat(),
        "note": "Test refund - customer requested return",
        "user_id": 548380009,
        "processed_at": datetime.now().isoformat(),
        "refunds": [
            {
                "id": 890088186047892319,
                "note": "Test refund - customer requested return",
                "transactions": [
                    {
                        "id": 245135271310201194,
                        "amount": "155.575",
                        "kind": "refund",
                        "status": "success",
                    }
                ],
            }
        ],
    }

    logger.info("🧪 Testing field extractor with refund payload...")
    logger.info(f"Refund payload keys: {list(refund_payload.keys())}")

    # Test the field extractor
    field_extractor = FieldExtractorService()

    try:
        result = field_extractor.extract_order_fields(
            refund_payload, "test-shop-123", "webhook"
        )

        if result:
            logger.info("✅ Field extraction successful!")
            logger.info(f"   Order ID: {result.get('orderId')}")
            logger.info(f"   Shop ID: {result.get('shopId')}")
            logger.info(
                f"   Total Refunded Amount: ${result.get('totalRefundedAmount', 0)}"
            )
            logger.info(f"   Financial Status: {result.get('financialStatus', 'None')}")
            logger.info(f"   Note: {result.get('note', 'None')}")

            # Verify the results
            if result.get("orderId") == "6075126841483":
                logger.info("✅ Order ID extraction correct!")
            else:
                logger.error(
                    f"❌ Order ID extraction wrong! Expected: 6075126841483, Got: {result.get('orderId')}"
                )

            if result.get("totalRefundedAmount") == 155.575:
                logger.info("✅ Refund amount extraction correct!")
            else:
                logger.error(
                    f"❌ Refund amount extraction wrong! Expected: 155.575, Got: {result.get('totalRefundedAmount')}"
                )

            if result.get("financialStatus") == "refunded":
                logger.info("✅ Financial status extraction correct!")
            else:
                logger.error(
                    f"❌ Financial status extraction wrong! Expected: refunded, Got: {result.get('financialStatus')}"
                )

        else:
            logger.error("❌ Field extraction failed - no result returned")

    except Exception as e:
        logger.error(f"❌ Field extraction failed with error: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    test_refund_extraction()
