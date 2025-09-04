#!/usr/bin/env python3
"""
Script to trigger feature computation for a specific shop ID
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.domains.ml.services.feature_engineering import FeatureEngineeringService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def trigger_feature_computation(shop_id: str, batch_size: int = 100):
    """Trigger feature computation for a specific shop"""
    try:
        logger.info(f"Starting feature computation for shop: {shop_id}")

        # Initialize the feature engineering service
        feature_service = FeatureEngineeringService()

        # Run the feature pipeline
        result = await feature_service.run_feature_pipeline_for_shop(
            shop_id=shop_id, batch_size=batch_size
        )

        if result["success"]:
            logger.info(
                f"✅ Feature computation completed successfully for shop {shop_id}"
            )
            logger.info("Results:")
            for feature_type, feature_result in result["results"].items():
                logger.info(f"  {feature_type}: {feature_result}")
        else:
            logger.error(
                f"❌ Feature computation failed for shop {shop_id}: {result.get('error', 'Unknown error')}"
            )

        return result

    except Exception as e:
        logger.error(f"❌ Error during feature computation: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


async def main():
    """Main function"""
    shop_id = "cmf4uf3tr0000v3rsmi68lnrj"
    batch_size = 100

    logger.info(f"🚀 Triggering feature computation for shop: {shop_id}")
    logger.info(f"📊 Using batch size: {batch_size}")

    result = await trigger_feature_computation(shop_id, batch_size)

    if result["success"]:
        print(f"\n✅ SUCCESS: Feature computation completed for shop {shop_id}")
        print("📈 Feature computation results:")
        for feature_type, feature_result in result["results"].items():
            print(f"  • {feature_type}: {feature_result}")
    else:
        print(f"\n❌ FAILED: Feature computation failed for shop {shop_id}")
        print(f"Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
