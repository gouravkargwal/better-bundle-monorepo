"""
Scheduler service for triggering analysis based on heuristic logic
This service is called by GitHub Actions cron jobs
"""

import structlog
from datetime import datetime
from typing import List, Dict, Any

from app.core.database import get_database
from app.core.redis_client import get_redis_client, streams_manager
from app.services.heuristic_service import heuristic_service

logger = structlog.get_logger(__name__)


class SchedulerService:
    """Service for scheduling and triggering analysis jobs"""

    def __init__(self):
        self.db = None
        self.redis = None

    async def initialize(self):
        """Initialize database and Redis connections"""
        self.db = await get_database()
        self.redis = await get_redis_client()
        await streams_manager.initialize()
        await heuristic_service.initialize()

    async def check_and_trigger_scheduled_analyses(self) -> Dict[str, Any]:
        """Check for shops due for analysis and trigger them"""
        try:
            logger.info("🔍 Checking for shops due for analysis")

            # Get shops due for analysis
            shops_due = await heuristic_service.get_shops_due_for_analysis()

            if not shops_due:
                logger.info("✅ No shops due for analysis")
                return {
                    "success": True,
                    "message": "No shops due for analysis",
                    "shops_processed": 0,
                    "shops_failed": 0,
                }

            logger.info(f"📋 Found {len(shops_due)} shops due for analysis")

            processed_count = 0
            failed_count = 0
            results = []

            for shop_config in shops_due:
                try:
                    shop = shop_config.shop
                    logger.info(f"🚀 Triggering analysis for shop: {shop.shopDomain}")

                    # Create analysis job
                    job_id = f"scheduled_{int(datetime.now().timestamp())}_{shop.id}"

                    analysis_job = await self.db.analysisjob.create(
                        {
                            "data": {
                                "jobId": job_id,
                                "shopId": shop.id,
                                "status": "queued",
                                "progress": 0,
                                "createdAt": datetime.now(),
                            }
                        }
                    )

                    # Publish to Redis Streams
                    message_id = await streams_manager.publish_data_job_event(
                        job_id=job_id,
                        shop_id=shop.id,
                        shop_domain=shop.shopDomain,
                        access_token=shop.accessToken,
                        job_type="scheduled"
                    )

                    logger.info(
                        f"✅ Scheduled analysis triggered for {shop.shopDomain}: {message_id}"
                    )

                    processed_count += 1
                    results.append(
                        {
                            "shop_id": shop.id,
                            "shop_domain": shop.shopDomain,
                            "job_id": job_id,
                            "message_id": message_id,
                            "status": "queued",
                        }
                    )

                except Exception as e:
                    logger.error(
                        f"❌ Failed to trigger analysis for shop {shop_config.shop.shopDomain}: {str(e)}"
                    )
                    failed_count += 1
                    results.append(
                        {
                            "shop_id": (
                                shop_config.shop.id if shop_config.shop else None
                            ),
                            "shop_domain": (
                                shop_config.shop.shopDomain
                                if shop_config.shop
                                else "unknown"
                            ),
                            "error": str(e),
                            "status": "failed",
                        }
                    )

            logger.info(
                f"✅ Scheduler completed: {processed_count} processed, {failed_count} failed"
            )

            return {
                "success": True,
                "message": f"Processed {processed_count} shops, {failed_count} failed",
                "shops_processed": processed_count,
                "shops_failed": failed_count,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("❌ Error in scheduler service", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "shops_processed": 0,
                "shops_failed": 0,
                "timestamp": datetime.now().isoformat(),
            }

    async def trigger_manual_analysis(self, shop_id: str) -> Dict[str, Any]:
        """Trigger manual analysis for a specific shop"""
        try:
            logger.info(f"🚀 Triggering manual analysis for shop: {shop_id}")

            # Get shop data
            shop = await self.db.shop.find_unique(
                where={"id": shop_id},
                select={"id": True, "shopDomain": True, "accessToken": True},
            )

            if not shop:
                return {"success": False, "error": f"Shop not found: {shop_id}"}

            # Create analysis job
            job_id = f"manual_{int(datetime.now().timestamp())}_{shop.id}"

            analysis_job = await self.db.analysisjob.create(
                {
                    "data": {
                        "jobId": job_id,
                        "shopId": shop.id,
                        "status": "queued",
                        "progress": 0,
                        "createdAt": datetime.now(),
                    }
                }
            )

            # Publish to Redis Streams
            message_id = await streams_manager.publish_data_job_event(
                job_id=job_id,
                shop_id=shop.id,
                shop_domain=shop.shopDomain,
                access_token=shop.accessToken,
                job_type="manual"
            )

            logger.info(
                f"✅ Manual analysis triggered for {shop.shopDomain}: {message_id}"
            )

            return {
                "success": True,
                "job_id": job_id,
                "message_id": message_id,
                "shop_domain": shop.shopDomain,
                "status": "queued",
            }

        except Exception as e:
            logger.error(
                f"❌ Error triggering manual analysis for shop {shop_id}: {str(e)}"
            )
            return {"success": False, "error": str(e)}

    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status and statistics"""
        try:
            # Get shops due for analysis
            shops_due = await heuristic_service.get_shops_due_for_analysis()

            # Get total shops with auto-analysis enabled
            total_shops = await self.db.shopanalysisconfig.count(
                where={"autoAnalysisEnabled": True}
            )

            # Get upcoming scheduled analyses (next 7 days)
            seven_days_from_now = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            seven_days_from_now = seven_days_from_now.replace(
                day=seven_days_from_now.day + 7
            )

            upcoming_analyses = await self.db.shopanalysisconfig.find_many(
                where={
                    "autoAnalysisEnabled": True,
                    "nextScheduledAnalysis": {
                        "gte": datetime.now(),
                        "lte": seven_days_from_now,
                    },
                },
                include={"shop": {"select": {"shopDomain": True}}},
                order={"nextScheduledAnalysis": "asc"},
                take=10,
            )

            return {
                "success": True,
                "status": "active",
                "shops_due_for_analysis": len(shops_due),
                "total_shops_with_auto_analysis": total_shops,
                "upcoming_analyses": [
                    {
                        "shop_domain": analysis.shop.shopDomain,
                        "scheduled_time": (
                            analysis.nextScheduledAnalysis.isoformat()
                            if analysis.nextScheduledAnalysis
                            else None
                        ),
                    }
                    for analysis in upcoming_analyses
                ],
                "last_check": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("❌ Error getting scheduler status", error=str(e))
            return {"success": False, "error": str(e), "status": "error"}

    async def update_analysis_schedule(
        self, shop_id: str, analysis_result: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Update analysis schedule for a shop after analysis completion"""
        try:
            logger.info(f"📅 Updating analysis schedule for shop: {shop_id}")

            # Schedule next analysis using heuristic
            result = await heuristic_service.schedule_next_analysis(
                shop_id, analysis_result
            )

            if result["success"]:
                logger.info(f"✅ Analysis schedule updated for shop {shop_id}")
                return result
            else:
                logger.error(
                    f"❌ Failed to update analysis schedule for shop {shop_id}: {result.get('error')}"
                )
                return result

        except Exception as e:
            logger.error(
                f"❌ Error updating analysis schedule for shop {shop_id}: {str(e)}"
            )
            return {"success": False, "error": str(e)}


# Global instance
scheduler_service = SchedulerService()
