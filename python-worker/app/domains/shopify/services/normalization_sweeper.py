"""
Normalization Sweeper Service

Periodically publishes normalize_scan events to catch any missed normalization jobs.
This acts as a safety net to ensure all raw data eventually gets normalized.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.core.redis_client import streams_manager

logger = get_logger(__name__)


class NormalizationSweeperService:
    """Service to periodically sweep for unnormalized raw data."""

    def __init__(self, sweep_interval_hours: int = 24):
        self.sweep_interval_hours = sweep_interval_hours
        self.data_types = ["orders", "products", "customers", "collections"]

    async def run_sweep(self) -> Dict[str, Any]:
        """
        Run a full sweep across all shops and data types.
        Publishes normalize_scan events for shops that haven't been normalized recently.
        """
        logger.info("Starting normalization sweep")

        db = await get_database()
        sweep_results = {
            "scans_triggered": 0,
            "shops_processed": 0,
            "data_types_processed": [],
            "errors": [],
        }

        try:
            # Get all unique shop IDs from raw tables
            shops = await self._get_active_shops(db)
            sweep_results["shops_processed"] = len(shops)

            for shop_id in shops:
                for data_type in self.data_types:
                    try:
                        should_scan = await self._should_trigger_scan(
                            db, shop_id, data_type
                        )

                        if should_scan:
                            await streams_manager.publish_shopify_event(
                                {
                                    "event_type": "normalize_scan",
                                    "shop_id": shop_id,
                                    "data_type": data_type,
                                    "page_size": 100,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )

                            sweep_results["scans_triggered"] += 1
                            if data_type not in sweep_results["data_types_processed"]:
                                sweep_results["data_types_processed"].append(data_type)

                            logger.info(
                                f"Triggered sweep scan",
                                shop_id=shop_id,
                                data_type=data_type,
                            )

                    except Exception as e:
                        error_msg = f"Failed to process sweep for {shop_id}/{data_type}: {str(e)}"
                        sweep_results["errors"].append(error_msg)
                        logger.error(error_msg)

            logger.info("Normalization sweep completed", results=sweep_results)
            return sweep_results

        except Exception as e:
            logger.error(f"Normalization sweep failed: {str(e)}")
            sweep_results["errors"].append(str(e))
            return sweep_results

    async def _get_active_shops(self, db) -> List[str]:
        """Get list of shop IDs that have raw data."""
        shop_ids = set()

        # Query each raw table for unique shop IDs
        for data_type in self.data_types:
            table = getattr(db, f"raw{data_type[:-1]}")  # raworder, rawproduct, etc.

            # Get shops that have data from the last week (to avoid very old/inactive shops)
            cutoff = datetime.now() - timedelta(days=7)

            shops = await table.find_many(
                where={"receivedAt": {"gte": cutoff}},
                select={"shopId": True},
                distinct=["shopId"],
            )

            shop_ids.update([shop.shopId for shop in shops])

        return list(shop_ids)

    async def _should_trigger_scan(self, db, shop_id: str, data_type: str) -> bool:
        """
        Determine if a scan should be triggered for this shop/data_type combination.

        Triggers scan if:
        1. No watermark exists (never normalized)
        2. Watermark is older than sweep_interval_hours
        3. There's raw data newer than the watermark
        """
        try:
            # Check watermark
            watermark = await db.normalizationwatermark.find_unique(
                where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}}
            )

            cutoff_time = datetime.now() - timedelta(hours=self.sweep_interval_hours)

            # No watermark = never normalized, trigger scan
            if not watermark:
                return await self._has_raw_data(db, shop_id, data_type)

            # Watermark too old, trigger scan
            if watermark.lastNormalizedAt < cutoff_time:
                return await self._has_raw_data(db, shop_id, data_type)

            # Check if there's newer raw data than watermark
            return await self._has_newer_raw_data(
                db, shop_id, data_type, watermark.lastNormalizedAt
            )

        except Exception as e:
            logger.error(
                f"Error checking scan trigger for {shop_id}/{data_type}: {str(e)}"
            )
            return False

    async def _has_raw_data(self, db, shop_id: str, data_type: str) -> bool:
        """Check if there's any raw data for this shop/data_type."""
        table = getattr(db, f"raw{data_type[:-1]}")

        count = await table.count(where={"shopId": shop_id})
        return count > 0

    async def _has_newer_raw_data(
        self, db, shop_id: str, data_type: str, watermark_time: datetime
    ) -> bool:
        """Check if there's raw data newer than the watermark."""
        table = getattr(db, f"raw{data_type[:-1]}")

        count = await table.count(
            where={"shopId": shop_id, "shopifyUpdatedAt": {"gt": watermark_time}}
        )
        return count > 0


# Convenience function for running sweeps
async def run_normalization_sweep(sweep_interval_hours: int = 24) -> Dict[str, Any]:
    """Run a normalization sweep with the specified interval."""
    sweeper = NormalizationSweeperService(sweep_interval_hours)
    return await sweeper.run_sweep()
