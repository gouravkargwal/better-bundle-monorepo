"""
Analytics consumer for processing business analytics jobs
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import ANALYSIS_RESULTS_STREAM, DATA_PROCESSOR_GROUP
from app.domains.analytics.services import (
    BusinessMetricsService,
    PerformanceAnalyticsService,
    CustomerAnalyticsService,
    ProductAnalyticsService,
    RevenueAnalyticsService,
)
from app.core.logging import get_logger


class AnalyticsConsumer(BaseConsumer):
    """Consumer for processing business analytics jobs"""

    def __init__(
        self,
        business_metrics_service: BusinessMetricsService,
        performance_analytics_service: PerformanceAnalyticsService,
        customer_analytics_service: CustomerAnalyticsService,
        product_analytics_service: ProductAnalyticsService,
        revenue_analytics_service: RevenueAnalyticsService,
    ):
        super().__init__(
            stream_name=ANALYSIS_RESULTS_STREAM,
            consumer_group=DATA_PROCESSOR_GROUP,
            consumer_name="analytics-consumer",
            batch_size=8,  # Process more analytics jobs (they're lightweight)
            poll_timeout=1500,  # 1.5 second timeout
            max_retries=3,
            retry_delay=1.0,
            circuit_breaker_failures=5,  # Less sensitive for analytics
            circuit_breaker_timeout=60,  # 1 minute recovery
        )

        self.business_metrics_service = business_metrics_service
        self.performance_analytics_service = performance_analytics_service
        self.customer_analytics_service = customer_analytics_service
        self.product_analytics_service = product_analytics_service
        self.revenue_analytics_service = revenue_analytics_service

        self.logger = get_logger(__name__)

        # Analytics job tracking
        self.active_analytics_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 900  # 15 minutes for analytics

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single analytics job message"""
        try:
            # Extract message data - Redis streams return data directly
            message_data = message  # No need to get "data" field
            job_id = message_data.get("job_id")
            shop_id = message_data.get("shop_id")
            analytics_type = message_data.get("analytics_type", "business_metrics")
            analysis_config = message_data.get("analysis_config", {})

            if not all([job_id, shop_id]):
                raise ValueError("Missing required job fields: job_id, shop_id")

            self.logger.info(
                f"Processing analytics job",
                job_id=job_id,
                shop_id=shop_id,
                analytics_type=analytics_type,
            )

            # Track active analytics job
            self.active_analytics_jobs[job_id] = {
                "started_at": datetime.utcnow(),
                "shop_id": shop_id,
                "analytics_type": analytics_type,
                "status": "processing",
                "analysis_config": analysis_config,
            }

            # Process based on analytics type
            if analytics_type == "business_metrics":
                await self._process_business_metrics_analysis(
                    job_id, shop_id, analysis_config
                )
            elif analytics_type == "performance_analytics":
                await self._process_performance_analytics(
                    job_id, shop_id, analysis_config
                )
            elif analytics_type == "customer_analytics":
                await self._process_customer_analytics(job_id, shop_id, analysis_config)
            elif analytics_type == "product_analytics":
                await self._process_product_analytics(job_id, shop_id, analysis_config)
            elif analytics_type == "revenue_analytics":
                await self._process_revenue_analytics(job_id, shop_id, analysis_config)
            elif analytics_type == "comprehensive_analysis":
                await self._process_comprehensive_analysis(
                    job_id, shop_id, analysis_config
                )
            else:
                self.logger.warning(f"Unknown analytics type: {analytics_type}")
                await self._mark_analytics_failed(
                    job_id, f"Unknown analytics type: {analytics_type}"
                )

            # Mark job as completed
            await self._mark_analytics_completed(job_id)

        except Exception as e:
            self.logger.error(
                f"Failed to process analytics job",
                job_id=message.get("job_id"),  # Redis streams return data directly
                error=str(e),
            )
            raise

    async def _process_business_metrics_analysis(
        self, job_id: str, shop_id: str, analysis_config: Dict[str, Any]
    ):
        """Process business metrics analysis"""
        try:
            self.logger.info(f"Starting business metrics analysis", job_id=job_id)

            # Get overall business metrics
            overall_metrics = (
                await self.business_metrics_service.compute_overall_metrics(shop_id)
            )

            # Get KPI dashboard
            kpi_dashboard = await self.business_metrics_service.get_kpi_dashboard(
                shop_id
            )

            result = {
                "overall_metrics": overall_metrics,
                "kpi_dashboard": kpi_dashboard,
                "analysis_type": "business_metrics",
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.logger.info(
                f"Business metrics analysis completed",
                job_id=job_id,
                shop_id=shop_id,
                metrics_count=len(overall_metrics) if overall_metrics else 0,
            )

            # Update job tracking
            if job_id in self.active_analytics_jobs:
                self.active_analytics_jobs[job_id]["status"] = "completed"
                self.active_analytics_jobs[job_id]["result"] = result
                self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Business metrics analysis failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_analytics_failed(job_id, str(e))
            raise

    async def _process_performance_analytics(
        self, job_id: str, shop_id: str, analysis_config: Dict[str, Any]
    ):
        """Process performance analytics"""
        try:
            self.logger.info(f"Starting performance analytics", job_id=job_id)

            # Analyze shop performance
            shop_performance = (
                await self.performance_analytics_service.analyze_shop_performance(
                    shop_id
                )
            )

            # Get optimization recommendations
            recommendations = await self.performance_analytics_service.generate_optimization_recommendations(
                shop_id
            )

            result = {
                "shop_performance": shop_performance,
                "optimization_recommendations": recommendations,
                "analysis_type": "performance_analytics",
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.logger.info(
                f"Performance analytics completed",
                job_id=job_id,
                shop_id=shop_id,
                recommendations_count=len(recommendations) if recommendations else 0,
            )

            # Update job tracking
            if job_id in self.active_analytics_jobs:
                self.active_analytics_jobs[job_id]["status"] = "completed"
                self.active_analytics_jobs[job_id]["result"] = result
                self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Performance analytics failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_analytics_failed(job_id, str(e))
            raise

    async def _process_customer_analytics(
        self, job_id: str, shop_id: str, analysis_config: Dict[str, Any]
    ):
        """Process customer analytics"""
        try:
            self.logger.info(f"Starting customer analytics", job_id=job_id)

            # Get customer insights
            customer_insights = (
                await self.customer_analytics_service.get_customer_insights(shop_id)
            )

            result = {
                "customer_insights": customer_insights,
                "analysis_type": "customer_analytics",
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.logger.info(
                f"Customer analytics completed", job_id=job_id, shop_id=shop_id
            )

            # Update job tracking
            if job_id in self.active_analytics_jobs:
                self.active_analytics_jobs[job_id]["status"] = "completed"
                self.active_analytics_jobs[job_id]["result"] = result
                self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Customer analytics failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_analytics_failed(job_id, str(e))
            raise

    async def _process_product_analytics(
        self, job_id: str, shop_id: str, analysis_config: Dict[str, Any]
    ):
        """Process product analytics"""
        try:
            self.logger.info(f"Starting product analytics", job_id=job_id)

            # Get product insights
            product_insights = (
                await self.product_analytics_service.get_product_recommendations(
                    shop_id
                )
            )

            result = {
                "product_insights": product_insights,
                "analysis_type": "product_analytics",
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.logger.info(
                f"Product analytics completed", job_id=job_id, shop_id=shop_id
            )

            # Update job tracking
            if job_id in self.active_analytics_jobs:
                self.active_analytics_jobs[job_id]["status"] = "completed"
                self.active_analytics_jobs[job_id]["result"] = result
                self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Product analytics failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_analytics_failed(job_id, str(e))
            raise

    async def _process_revenue_analytics(
        self, job_id: str, shop_id: str, analysis_config: Dict[str, Any]
    ):
        """Process revenue analytics"""
        try:
            self.logger.info(f"Starting revenue analytics", job_id=job_id)

            # Get revenue insights
            revenue_insights = (
                await self.revenue_analytics_service.get_revenue_insights(shop_id)
            )

            result = {
                "revenue_insights": revenue_insights,
                "analysis_type": "revenue_analytics",
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.logger.info(
                f"Revenue analytics completed", job_id=job_id, shop_id=shop_id
            )

            # Update job tracking
            if job_id in self.active_analytics_jobs:
                self.active_analytics_jobs[job_id]["status"] = "completed"
                self.active_analytics_jobs[job_id]["result"] = result
                self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Revenue analytics failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_analytics_failed(job_id, str(e))
            raise

    async def _process_comprehensive_analysis(
        self, job_id: str, shop_id: str, analysis_config: Dict[str, Any]
    ):
        """Process comprehensive analytics analysis"""
        try:
            self.logger.info(
                f"Starting comprehensive analytics analysis", job_id=job_id
            )

            # Run all analytics in parallel
            tasks = [
                self.business_metrics_service.compute_overall_metrics(shop_id),
                self.performance_analytics_service.analyze_shop_performance(shop_id),
                self.customer_analytics_service.get_customer_insights(shop_id),
                self.product_analytics_service.get_product_recommendations(shop_id),
                self.revenue_analytics_service.get_revenue_insights(shop_id),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            comprehensive_result = {
                "business_metrics": (
                    results[0] if not isinstance(results[0], Exception) else None
                ),
                "performance_analytics": (
                    results[1] if not isinstance(results[1], Exception) else None
                ),
                "customer_analytics": (
                    results[2] if not isinstance(results[2], Exception) else None
                ),
                "product_analytics": (
                    results[3] if not isinstance(results[3], Exception) else None
                ),
                "revenue_analytics": (
                    results[4] if not isinstance(results[4], Exception) else None
                ),
                "analysis_type": "comprehensive_analysis",
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.logger.info(
                f"Comprehensive analytics analysis completed",
                job_id=job_id,
                shop_id=shop_id,
            )

            # Update job tracking
            if job_id in self.active_analytics_jobs:
                self.active_analytics_jobs[job_id]["status"] = "completed"
                self.active_analytics_jobs[job_id]["result"] = comprehensive_result
                self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Comprehensive analytics analysis failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_analytics_failed(job_id, str(e))
            raise

    async def _mark_analytics_completed(self, job_id: str):
        """Mark analytics job as completed"""
        if job_id in self.active_analytics_jobs:
            self.active_analytics_jobs[job_id]["status"] = "completed"
            self.active_analytics_jobs[job_id]["completed_at"] = datetime.utcnow()

        self.logger.info(f"Analytics job completed successfully", job_id=job_id)

    async def _mark_analytics_failed(self, job_id: str, error_message: str):
        """Mark analytics job as failed"""
        if job_id in self.active_analytics_jobs:
            self.active_analytics_jobs[job_id]["status"] = "failed"
            self.active_analytics_jobs[job_id]["error"] = error_message
            self.active_analytics_jobs[job_id]["failed_at"] = datetime.utcnow()

        self.logger.error(f"Analytics job failed", job_id=job_id, error=error_message)

    async def cleanup_old_jobs(self):
        """Clean up old completed/failed analytics jobs"""
        now = datetime.utcnow()
        jobs_to_remove = []

        for job_id, job_data in self.active_analytics_jobs.items():
            if job_data["status"] in ["completed", "failed"]:
                # Check if job is old enough to remove
                if "completed_at" in job_data:
                    age = (now - job_data["completed_at"]).total_seconds()
                elif "failed_at" in job_data:
                    age = (now - job_data["failed_at"]).total_seconds()
                else:
                    continue

                if age > self.job_timeout:
                    jobs_to_remove.append(job_id)

        # Remove old jobs
        for job_id in jobs_to_remove:
            del self.active_analytics_jobs[job_id]

        if jobs_to_remove:
            self.logger.info(f"Cleaned up {len(jobs_to_remove)} old analytics jobs")

    def get_analytics_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific analytics job"""
        return self.active_analytics_jobs.get(job_id)

    def get_all_analytics_jobs_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all active analytics jobs"""
        return self.active_analytics_jobs.copy()

    async def _health_check(self):
        """Extended health check for analytics consumer"""
        await super()._health_check()

        # Clean up old jobs periodically
        await self.cleanup_old_jobs()

        # Log analytics job statistics
        active_count = len(
            [
                j
                for j in self.active_analytics_jobs.values()
                if j["status"] == "processing"
            ]
        )
        completed_count = len(
            [
                j
                for j in self.active_analytics_jobs.values()
                if j["status"] == "completed"
            ]
        )
        failed_count = len(
            [j for j in self.active_analytics_jobs.values() if j["status"] == "failed"]
        )

        self.logger.info(
            f"Analytics consumer job status",
            active_jobs=active_count,
            completed_jobs=completed_count,
            failed_jobs=failed_count,
            total_jobs=len(self.active_analytics_jobs),
        )
