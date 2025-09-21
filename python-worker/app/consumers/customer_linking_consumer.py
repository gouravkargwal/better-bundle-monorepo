"""
Customer Linking Consumer for processing customer identity resolution and backfill jobs
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import CUSTOMER_LINKING_STREAM
from app.domains.analytics.services.customer_identity_resolution_service import (
    CustomerIdentityResolutionService,
)
from app.domains.analytics.services.cross_session_linking_service import (
    CrossSessionLinkingService,
)
from app.core.logging import get_logger


class CustomerLinkingConsumer(BaseConsumer):
    """Consumer for processing customer linking and backfill jobs"""

    def __init__(self):
        super().__init__(
            stream_name=CUSTOMER_LINKING_STREAM,
            consumer_group="customer-linking-consumer-group",
            consumer_name="customer-linking-consumer",
            batch_size=10,  # Process multiple linking jobs
            poll_timeout=5000,  # 5 second timeout
            max_retries=3,
            retry_delay=2.0,
            circuit_breaker_failures=5,
            circuit_breaker_timeout=60,  # 1 minute recovery
        )

        self.logger.info(
            "CustomerLinkingConsumer: Initializing customer linking services"
        )
        self.identity_resolution_service = CustomerIdentityResolutionService()
        self.cross_session_linking_service = CrossSessionLinkingService()
        self.logger = get_logger(__name__)

        # Customer linking job tracking
        self.active_linking_jobs = {}
        self.job_timeout = 300  # 5 minutes for customer linking

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single customer linking job message"""
        try:
            # Extract message data
            job_id = message.get("job_id")
            shop_id = message.get("shop_id")
            customer_id = message.get("customer_id")
            trigger_session_id = message.get("trigger_session_id")
            linked_sessions = message.get("linked_sessions", [])
            event_type = message.get("event_type", "customer_linking")

            self.logger.info(
                f"📨 Received customer linking message - job_id: {job_id}, shop_id: {shop_id}, customer_id: {customer_id}, event_type: {event_type}"
            )

            if not job_id or not shop_id or not customer_id:
                self.logger.error("❌ Invalid message: missing required fields")
                return

            self.logger.info(
                f"🔄 Processing customer linking job - job_id: {job_id}, shop_id: {shop_id}, customer_id: {customer_id}, event_type: {event_type}"
            )

            # Track the job
            self.active_linking_jobs[job_id] = {
                "shop_id": shop_id,
                "customer_id": customer_id,
                "started_at": datetime.utcnow(),
                "status": "processing",
            }

            # Process based on event type
            if event_type == "customer_linking":
                await self._process_customer_linking(
                    job_id, shop_id, customer_id, trigger_session_id, linked_sessions
                )
            elif event_type == "cross_session_linking":
                await self._process_cross_session_linking(job_id, shop_id, customer_id)
            elif event_type == "backfill_interactions":
                await self._process_interaction_backfill(
                    job_id, shop_id, customer_id, linked_sessions
                )
            else:
                self.logger.warning(f"Unknown event type: {event_type}")

            # Mark job as completed
            if job_id in self.active_linking_jobs:
                self.active_linking_jobs[job_id]["status"] = "completed"
                self.active_linking_jobs[job_id]["completed_at"] = datetime.utcnow()

            self.logger.info(
                f"Customer linking job completed", job_id=job_id, shop_id=shop_id
            )

        except Exception as e:
            self.logger.error(f"Error processing customer linking message: {str(e)}")
            if job_id in self.active_linking_jobs:
                self.active_linking_jobs[job_id]["status"] = "failed"
                self.active_linking_jobs[job_id]["error"] = str(e)

    async def _process_customer_linking(
        self,
        job_id: str,
        shop_id: str,
        customer_id: str,
        trigger_session_id: Optional[str],
        linked_sessions: list,
    ):
        """Process customer identity resolution and linking"""
        try:
            self.logger.info(
                f"🔍 Processing customer identity resolution for customer {customer_id} with trigger_session_id: {trigger_session_id}"
            )

            # Run cross-session linking to find more sessions
            self.logger.info(
                f"🔗 Starting cross-session linking for customer {customer_id}..."
            )
            linking_result = (
                await self.cross_session_linking_service.link_customer_sessions(
                    customer_id=customer_id,
                    shop_id=shop_id,
                    trigger_session_id=trigger_session_id,
                )
            )

            self.logger.info(f"📊 Cross-session linking result: {linking_result}")

            if linking_result.get("success"):
                linked_sessions = linking_result.get("linked_sessions", [])
                self.logger.info(
                    f"✅ Cross-session linking completed: {len(linked_sessions)} sessions linked - {linked_sessions}"
                )

                # Trigger backfill for all linked sessions
                if linked_sessions:
                    self.logger.info(
                        f"🔄 Starting backfill for {len(linked_sessions)} sessions..."
                    )
                    await self._process_interaction_backfill(
                        job_id, shop_id, customer_id, linked_sessions
                    )
                else:
                    self.logger.warning(
                        f"⚠️ No sessions to backfill for customer {customer_id}"
                    )
            else:
                self.logger.warning(
                    f"❌ Cross-session linking failed: {linking_result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"❌ Error in customer linking: {str(e)}")
            raise

    async def _process_cross_session_linking(
        self, job_id: str, shop_id: str, customer_id: str
    ):
        """Process cross-session linking for a customer"""
        try:
            self.logger.info(
                f"Processing cross-session linking for customer {customer_id}"
            )

            # Run cross-session linking
            result = await self.cross_session_linking_service.link_customer_sessions(
                customer_id=customer_id, shop_id=shop_id
            )

            if result.get("success"):
                self.logger.info(
                    f"Cross-session linking completed: {result.get('linked_sessions', 0)} sessions linked"
                )
            else:
                self.logger.warning(
                    f"Cross-session linking failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(f"Error in cross-session linking: {str(e)}")
            raise

    async def _process_interaction_backfill(
        self, job_id: str, shop_id: str, customer_id: str, linked_sessions: list
    ):
        """Process backfill of customer interactions"""
        try:
            from app.core.database import get_database

            self.logger.info(
                f"🔄 Processing interaction backfill for customer {customer_id} with {len(linked_sessions)} sessions: {linked_sessions}"
            )

            db = await get_database()

            # Get all session IDs that need backfill
            all_session_ids = linked_sessions
            total_backfilled = 0

            # Update all interactions in these sessions with customer_id
            for session_id in all_session_ids:
                self.logger.info(
                    f"🔍 Backfilling session {session_id} for customer {customer_id}..."
                )

                result = await db.userinteraction.update_many(
                    where={
                        "sessionId": session_id,
                        "customerId": None,  # Only update interactions without customer_id
                    },
                    data={"customerId": customer_id},
                )

                self.logger.info(
                    f"✅ Backfilled {result} interactions for session {session_id}"
                )
                total_backfilled += result

            self.logger.info(f"📊 Total interactions backfilled: {total_backfilled}")

            # Fire feature computation event for updated interactions
            try:
                self.logger.info(
                    f"🚀 Firing feature computation event for shop {shop_id}..."
                )
                await self.identity_resolution_service.fire_feature_computation_event(
                    shop_id=shop_id,
                    trigger_source="customer_linking_backfill",
                    interaction_id=None,
                    batch_size=100,
                    incremental=True,
                )
                self.logger.info(f"✅ Feature computation event fired successfully")
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Failed to fire feature computation event: {str(e)}"
                )

            self.logger.info(
                f"✅ Interaction backfill completed for customer {customer_id} - {total_backfilled} interactions updated"
            )

        except Exception as e:
            self.logger.error(f"❌ Error in interaction backfill: {str(e)}")
            raise

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a customer linking job"""
        return self.active_linking_jobs.get(job_id)

    async def get_all_job_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all customer linking jobs"""
        return self.active_linking_jobs.copy()

    async def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Clean up completed jobs older than max_age_hours"""
        try:
            current_time = datetime.utcnow()
            jobs_to_remove = []

            for job_id, job_data in self.active_linking_jobs.items():
                if job_data.get("status") in ["completed", "failed"]:
                    completed_at = job_data.get("completed_at")
                    if completed_at:
                        age_hours = (current_time - completed_at).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self.active_linking_jobs[job_id]

            if jobs_to_remove:
                self.logger.info(f"Cleaned up {len(jobs_to_remove)} completed jobs")

        except Exception as e:
            self.logger.error(f"Error cleaning up completed jobs: {str(e)}")
