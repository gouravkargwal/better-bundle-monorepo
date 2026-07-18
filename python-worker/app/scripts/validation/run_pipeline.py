"""
Trigger the feature computation + Gorse sync pipeline for the validation shop.

This calls the same pipeline that runs automatically on a schedule.

Usage:
  uv run python-worker/app/scripts/validation/run_pipeline.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.domains.ml.services.feature_engineering import FeatureEngineeringService
from app.core.logging import get_logger

SHOP_ID = "validation_test_shop"
logger = get_logger(__name__)


async def run_pipeline():
    print("=" * 60)
    print("Running feature computation + Gorse sync pipeline")
    print("=" * 60)
    print(f"\n🏪 Shop ID: {SHOP_ID}")

    service = FeatureEngineeringService()
    result = await service.run_comprehensive_pipeline_for_shop(SHOP_ID)

    success = result.get("success", False)
    if success:
        print("   ✅ Pipeline complete!")
        sync = result.get("sync_result", {})
        print(f"   • Synced: {sync.get('total_items_synced', 0)} items")
        errors = sync.get("errors", [])
        if errors:
            print(f"   • {len(errors)} sync errors: {errors[:3]}")
    else:
        print(f"   ❌ Pipeline failed: {result.get('error', 'Unknown')}")

    print()
    print("Gorse will now train models (~45m for collaborative filtering).")
    print("Check dashboard: http://localhost:8088")
    print("Run: uv run python-worker/app/scripts/validation/validate_recommendations.py")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
