"""
Completion handler for processing ML training completion events
"""

import asyncio
from app.core.logger import get_logger
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.database import get_database
from app.core.redis_client import get_redis_client, streams_manager
from app.services.heuristic_service import heuristic_service

logger = get_logger(__name__)


class CompletionHandler:
    """Handles ML training completion events"""

    def __init__(self):
        self.db = None
        self.redis = None
        self._consumer_task = None

    async def initialize(self):
        """Initialize database and Redis connections"""
        self.db = await get_database()
        self.redis = await get_redis_client()
        await streams_manager.initialize()
        await heuristic_service.initialize()

    async def start_consumer(self):
        """Start the consumer in a separate task"""
        if self._consumer_task and not self._consumer_task.done():
            logger.warning("Completion handler consumer is already running")
            return

        self._consumer_task = asyncio.create_task(
            self.consume_ml_completion_events(), name="completion-handler-consumer"
        )

    async def stop_consumer(self):
        """Stop the consumer task"""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def handle_ml_training_completion(
        self, event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle ML training completion event"""
        try:
            job_id = event_data.get("job_id")
            shop_id = event_data.get("shop_id")
            shop_domain = event_data.get("shop_domain")
            event_type = event_data.get("event_type")
            success = event_data.get("success", False)
            error = event_data.get("error")
            analysis_result = event_data.get("analysis_result")
            skipped = event_data.get("skipped", False)
            skipped_reason = event_data.get("skipped_reason")
            
            # Handle different event types
            if event_type == "GORSE_TRAINING_TIMEOUT":
                return await self._handle_training_timeout(event_data)
            elif event_type == "GORSE_TRAINING_FAILED":
                return await self._handle_training_failure(event_data)
            elif event_type == "GORSE_TRAINING_COMPLETED":
                return await self._handle_training_success(event_data)
            elif event_type in ["ML_TRAINING_COMPLETED", "ML_TRAINING_SKIPPED", "ML_TRAINING_FAILED"]:
                # Handle legacy ML training events
                pass
            else:
                logger.warning(f"Unknown event type: {event_type}")
                return {"success": False, "error": f"Unknown event type: {event_type}"}

            # Step 1: Update job status
            await self._update_job_status(job_id, success, error)

            # Step 2: Update shop's last analysis timestamp
            await self._update_shop_analysis_timestamp(shop_id)

            if success:
                if skipped:
                    # Handle skipped training case

                    # Step 3: Schedule next analysis using heuristic (even for skipped)
                    schedule_result = await self._schedule_next_analysis(
                        shop_id, analysis_result
                    )

                    # Step 4: Skip email notification for internal ML training
                    email_result = {
                        "success": True,
                        "skipped": True,
                        "reason": "No email sent for internal ML training",
                    }

                    # Step 5: Publish heuristic decision requested event
                    await self._publish_heuristic_decision_requested(
                        event_data, schedule_result
                    )

                    return {
                        "success": True,
                        "job_id": job_id,
                        "shop_id": shop_id,
                        "skipped": True,
                        "reason": skipped_reason,
                        "schedule_result": schedule_result,
                        "email_result": email_result,
                    }
                else:
                    # Handle successful training case
                    # Step 3: Schedule next analysis using heuristic
                    schedule_result = await self._schedule_next_analysis(
                        shop_id, analysis_result
                    )

                    # Step 4: Skip email notification for internal ML training
                    email_result = {
                        "success": True,
                        "skipped": True,
                        "reason": "No email sent for internal ML training",
                    }

                    # Step 5: Publish heuristic decision requested event
                    await self._publish_heuristic_decision_requested(
                        event_data, schedule_result
                    )

                    return {
                        "success": True,
                        "job_id": job_id,
                        "shop_id": shop_id,
                        "schedule_result": schedule_result,
                        "email_result": email_result,
                    }
            else:
                # Step 3: Skip email notification for internal ML training failures
                email_result = {
                    "success": True,
                    "skipped": True,
                    "reason": "No email sent for internal ML training failure",
                }

                # Step 4: Publish failure event
                await self._publish_completion_event(event_data, None)

                logger.error(
                    "❌ ML training failed",
                    job_id=job_id,
                    shop_id=shop_id,
                    error=error,
                    email_sent=email_result.get("success"),
                )

                return {
                    "success": False,
                    "job_id": job_id,
                    "shop_id": shop_id,
                    "error": error,
                    "email_result": email_result,
                }

        except Exception as e:
            logger.error("Error handling ML training completion", error=str(e))
            return {"success": False, "error": str(e)}

    async def _handle_training_timeout(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle training timeout event"""
        try:
            job_id = event_data.get("job_id")
            shop_id = event_data.get("shop_id")
            shop_domain = event_data.get("shop_domain")
            monitoring_duration = event_data.get("monitoring_duration")
            reason = event_data.get("reason", "Monitoring timeout")

            logger.warning(
                "⏰ ML training monitoring timeout",
                job_id=job_id,
                shop_id=shop_id,
                monitoring_duration=monitoring_duration,
                reason=reason,
            )

            # Update job status to indicate timeout
            await self._update_job_status(job_id, False, f"Monitoring timeout: {reason}")

            # Update shop's last analysis timestamp
            await self._update_shop_analysis_timestamp(shop_id)

            # Schedule next analysis using heuristic
            schedule_result = await self._schedule_next_analysis(shop_id, None)

            # Publish heuristic decision requested event
            await self._publish_heuristic_decision_requested(
                event_data, schedule_result
            )

            return {
                "success": False,
                "job_id": job_id,
                "shop_id": shop_id,
                "error": f"Monitoring timeout: {reason}",
                "monitoring_duration": monitoring_duration,
                "schedule_result": schedule_result,
                "message": "Training monitoring timed out, but training may still be in progress",
            }

        except Exception as e:
            logger.error("Error handling training timeout", error=str(e))
            return {"success": False, "error": str(e)}

    async def _handle_training_failure(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle training failure event"""
        try:
            job_id = event_data.get("job_id")
            shop_id = event_data.get("shop_id")
            shop_domain = event_data.get("shop_domain")
            error = event_data.get("error")
            monitoring_duration = event_data.get("monitoring_duration")

            logger.error(
                "❌ Gorse training failed",
                job_id=job_id,
                shop_id=shop_id,
                error=error,
                monitoring_duration=monitoring_duration,
            )

            # Update job status
            await self._update_job_status(job_id, False, error)

            # Update shop's last analysis timestamp
            await self._update_shop_analysis_timestamp(shop_id)

            # Schedule next analysis using heuristic
            schedule_result = await self._schedule_next_analysis(shop_id, None)

            # Publish heuristic decision requested event
            await self._publish_heuristic_decision_requested(
                event_data, schedule_result
            )

            return {
                "success": False,
                "job_id": job_id,
                "shop_id": shop_id,
                "error": error,
                "monitoring_duration": monitoring_duration,
                "schedule_result": schedule_result,
                "message": "Gorse training failed, scheduled next analysis",
            }

        except Exception as e:
            logger.error("Error handling training failure", error=str(e))
            return {"success": False, "error": str(e)}

    async def _handle_training_success(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle training success event"""
        try:
            job_id = event_data.get("job_id")
            shop_id = event_data.get("shop_id")
            shop_domain = event_data.get("shop_domain")
            progress = event_data.get("progress", {})
            monitoring_duration = event_data.get("monitoring_duration")

            logger.info(
                "✅ Gorse training completed successfully",
                job_id=job_id,
                shop_id=shop_id,
                monitoring_duration=monitoring_duration,
                completion_score=progress.get("completion_score"),
            )

            # Update job status
            await self._update_job_status(job_id, True, None)

            # Update shop's last analysis timestamp
            await self._update_shop_analysis_timestamp(shop_id)

            # Schedule next analysis using heuristic
            schedule_result = await self._schedule_next_analysis(shop_id, None)

            # Publish heuristic decision requested event
            await self._publish_heuristic_decision_requested(
                event_data, schedule_result
            )

            return {
                "success": True,
                "job_id": job_id,
                "shop_id": shop_id,
                "monitoring_duration": monitoring_duration,
                "progress": progress,
                "schedule_result": schedule_result,
                "message": "Gorse training completed successfully",
            }

        except Exception as e:
            logger.error("Error handling training success", error=str(e))
            return {"success": False, "error": str(e)}

    async def _update_job_status(
        self, job_id: str, success: bool, error: Optional[str] = None
    ):
        """Update analysis job status"""
        try:
            update_data = {
                "status": "completed" if success else "failed",
                "progress": 100 if success else 0,
                "completedAt": datetime.now(),
            }

            if error:
                update_data["error"] = error

            await self.db.analysisjob.update(where={"jobId": job_id}, data=update_data)

        except Exception as e:
            logger.error("Error updating job status", job_id=job_id, error=str(e))

    async def _update_shop_analysis_timestamp(self, shop_id: str):
        """Update shop's last analysis timestamp"""
        try:
            await self.db.shop.update(
                where={"id": shop_id}, data={"lastAnalysisAt": datetime.now()}
            )

        except Exception as e:
            logger.error(
                "Error updating shop analysis timestamp", shop_id=shop_id, error=str(e)
            )

    async def _schedule_next_analysis(
        self, shop_id: str, analysis_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Schedule next analysis using heuristic"""
        try:
            result = await heuristic_service.schedule_next_analysis(
                shop_id, analysis_result
            )

            return result

        except Exception as e:
            logger.error(
                "Error scheduling next analysis", shop_id=shop_id, error=str(e)
            )
            return {"success": False, "error": str(e)}

    async def _send_completion_email(
        self,
        shop_domain: str,
        success: bool,
        job_id: str,
        analysis_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        skipped: bool = False,
        skipped_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send completion email notification"""
        try:
            # Get shop info for email
            shop = await self.db.shop.find_unique(
                where={"shopDomain": shop_domain},
                select={"email": True, "shopDomain": True},
            )

            if not shop or not shop.email:
                logger.warning("No email found for shop", shop_domain=shop_domain)
                return {"success": False, "error": "No email found"}

            if success:
                if skipped:
                    # Send skipped email
                    email_result = await self.email_service.send_analysis_skipped_email(
                        to_email=shop.email,
                        shop_domain=shop_domain,
                        job_id=job_id,
                        skipped_reason=skipped_reason,
                    )
                else:
                    # Send success email
                    email_result = (
                        await self.email_service.send_analysis_complete_email(
                            to_email=shop.email,
                            shop_domain=shop_domain,
                            job_id=job_id,
                            analysis_result=analysis_result,
                        )
                    )
            else:
                # Send failure email
                email_result = await self.email_service.send_analysis_failed_email(
                    to_email=shop.email,
                    shop_domain=shop_domain,
                    job_id=job_id,
                    error=error,
                )

            return email_result

        except Exception as e:
            logger.error(
                "Error sending completion email", shop_domain=shop_domain, error=str(e)
            )
            return {"success": False, "error": str(e)}

    async def _publish_completion_event(
        self, event_data: Dict[str, Any], schedule_result: Optional[Dict[str, Any]]
    ):
        """Publish completion event to completion-results stream (separate from consumption stream)"""
        try:
            completion_event = {
                **event_data,
                "completion_timestamp": datetime.now(timezone.utc).isoformat(),
                "schedule_result": schedule_result,
            }

            from app.core.config import settings

            message_id = await streams_manager.publish_event(
                settings.COMPLETION_RESULTS_STREAM, completion_event
            )

        except Exception as e:
            logger.error("Error publishing completion event", error=str(e))

    async def _publish_heuristic_decision_requested(
        self, event_data: Dict[str, Any], schedule_result: Optional[Dict[str, Any]]
    ):
        """Publish heuristic decision requested event"""
        try:
            from app.core.config import settings

            heuristic_event = {
                "event_type": "HEURISTIC_DECISION_REQUESTED",
                "job_id": event_data.get("job_id"),
                "shop_id": event_data.get("shop_id"),
                "shop_domain": event_data.get("shop_domain"),
                "training_result": event_data.get("result"),
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "schedule_result": {
                    "success": schedule_result.get("success") if schedule_result else False,
                    "next_scheduled_time": schedule_result.get("next_scheduled_time").isoformat() if schedule_result and schedule_result.get("next_scheduled_time") else None,
                    "error": schedule_result.get("error") if schedule_result else None,
                } if schedule_result else None,
            }

            message_id = await streams_manager.publish_event(
                settings.HEURISTIC_DECISION_REQUESTED_STREAM, heuristic_event
            )

        except Exception as e:
            logger.error(
                "Error publishing heuristic decision requested event", error=str(e)
            )

    async def consume_ml_completion_events(self):
        """Consumer loop for ML training completion events"""
        consumer_name = (
            f"completion-handler-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )

        while True:
            try:
                # Consume events from ML training completion stream
                from app.core.config import settings

                events = await streams_manager.consume_events(
                    stream_name=settings.COMPLETION_EVENTS_STREAM,
                    consumer_group=settings.COMPLETION_HANDLER_GROUP,
                    consumer_name=consumer_name,
                    count=settings.CONSUMER_BATCH_SIZE,
                    block=10000,  # 10 seconds (increased from 5 seconds)
                )

                for event in events:
                    try:

                        # Handle the completion
                        result = await self.handle_ml_training_completion(event)

                        # Acknowledge successful processing
                        await streams_manager.acknowledge_event(
                            stream_name="betterbundle:ml-training-complete",
                            consumer_group="completion-handlers",
                            message_id=event["_message_id"],
                        )

                    except Exception as e:
                        logger.error(
                            "Error processing ML completion event",
                            message_id=event.get("_message_id"),
                            error=str(e),
                        )

                        # Acknowledge even failed events to avoid infinite retries
                        await streams_manager.acknowledge_event(
                            stream_name="betterbundle:ml-training-complete",
                            consumer_group="completion-handlers",
                            message_id=event["_message_id"],
                        )

            except Exception as e:
                logger.error("Error in ML completion consumer", error=str(e))
                # Wait before retrying
                await asyncio.sleep(5)


# Global instance
completion_handler = CompletionHandler()
