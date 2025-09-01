"""
Completion handler for processing ML training completion events
"""

import structlog
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.database import get_database
from app.core.redis_client import get_redis_client, redis_streams_manager
from app.services.heuristic_service import heuristic_service
from app.utils.sendpulse_email import SendPulseEmailService

logger = structlog.get_logger(__name__)


class CompletionHandler:
    """Handles ML training completion events"""
    
    def __init__(self):
        self.db = None
        self.redis = None
        self.email_service = None
    
    async def initialize(self):
        """Initialize database and Redis connections"""
        self.db = await get_database()
        self.redis = await get_redis_client()
        await redis_streams_manager.initialize()
        await heuristic_service.initialize()
        self.email_service = SendPulseEmailService()
    
    async def handle_ml_training_completion(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ML training completion event"""
        try:
            job_id = event_data.get("job_id")
            shop_id = event_data.get("shop_id")
            shop_domain = event_data.get("shop_domain")
            success = event_data.get("success", False)
            error = event_data.get("error")
            analysis_result = event_data.get("analysis_result")
            
            logger.info(
                "Handling ML training completion",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
                success=success
            )
            
            # Step 1: Update job status
            await self._update_job_status(job_id, success, error)
            
            # Step 2: Update shop's last analysis timestamp
            await self._update_shop_analysis_timestamp(shop_id)
            
            if success:
                # Step 3: Schedule next analysis using heuristic
                schedule_result = await self._schedule_next_analysis(shop_id, analysis_result)
                
                # Step 4: Send success email notification
                email_result = await self._send_completion_email(
                    shop_domain, 
                    success=True, 
                    job_id=job_id,
                    analysis_result=analysis_result
                )
                
                # Step 5: Publish completion event to results stream
                await self._publish_completion_event(event_data, schedule_result)
                
                logger.info(
                    "✅ ML training completion handled successfully",
                    job_id=job_id,
                    shop_id=shop_id,
                    schedule_result=schedule_result.get("success"),
                    email_sent=email_result.get("success")
                )
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "shop_id": shop_id,
                    "schedule_result": schedule_result,
                    "email_result": email_result
                }
            else:
                # Step 3: Send failure email notification
                email_result = await self._send_completion_email(
                    shop_domain, 
                    success=False, 
                    job_id=job_id,
                    error=error
                )
                
                # Step 4: Publish failure event
                await self._publish_completion_event(event_data, None)
                
                logger.error(
                    "❌ ML training failed",
                    job_id=job_id,
                    shop_id=shop_id,
                    error=error,
                    email_sent=email_result.get("success")
                )
                
                return {
                    "success": False,
                    "job_id": job_id,
                    "shop_id": shop_id,
                    "error": error,
                    "email_result": email_result
                }
                
        except Exception as e:
            logger.error("Error handling ML training completion", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _update_job_status(self, job_id: str, success: bool, error: Optional[str] = None):
        """Update analysis job status"""
        try:
            update_data = {
                "status": "completed" if success else "failed",
                "progress": 100 if success else 0,
                "completedAt": datetime.now(),
            }
            
            if error:
                update_data["error"] = error
            
            await self.db.analysisjob.update(
                where={"jobId": job_id},
                data=update_data
            )
            
            logger.info("Job status updated", job_id=job_id, success=success)
            
        except Exception as e:
            logger.error("Error updating job status", job_id=job_id, error=str(e))
    
    async def _update_shop_analysis_timestamp(self, shop_id: str):
        """Update shop's last analysis timestamp"""
        try:
            await self.db.shop.update(
                where={"id": shop_id},
                data={"lastAnalysisAt": datetime.now()}
            )
            
            logger.info("Shop analysis timestamp updated", shop_id=shop_id)
            
        except Exception as e:
            logger.error("Error updating shop analysis timestamp", shop_id=shop_id, error=str(e))
    
    async def _schedule_next_analysis(self, shop_id: str, analysis_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Schedule next analysis using heuristic"""
        try:
            result = await heuristic_service.schedule_next_analysis(shop_id, analysis_result)
            
            if result["success"]:
                logger.info(
                    "Next analysis scheduled",
                    shop_id=shop_id,
                    next_hours=result["heuristic_result"].next_analysis_hours
                )
            else:
                logger.error("Failed to schedule next analysis", shop_id=shop_id, error=result.get("error"))
            
            return result
            
        except Exception as e:
            logger.error("Error scheduling next analysis", shop_id=shop_id, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_completion_email(
        self, 
        shop_domain: str, 
        success: bool, 
        job_id: str,
        analysis_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send completion email notification"""
        try:
            # Get shop info for email
            shop = await self.db.shop.find_unique(
                where={"shopDomain": shop_domain},
                select={"email": True, "shopDomain": True}
            )
            
            if not shop or not shop.email:
                logger.warning("No email found for shop", shop_domain=shop_domain)
                return {"success": False, "error": "No email found"}
            
            if success:
                # Send success email
                email_result = await self.email_service.send_analysis_complete_email(
                    to_email=shop.email,
                    shop_domain=shop_domain,
                    job_id=job_id,
                    analysis_result=analysis_result
                )
            else:
                # Send failure email
                email_result = await self.email_service.send_analysis_failed_email(
                    to_email=shop.email,
                    shop_domain=shop_domain,
                    job_id=job_id,
                    error=error
                )
            
            logger.info(
                "Completion email sent",
                shop_domain=shop_domain,
                success=success,
                email_result=email_result.get("success")
            )
            
            return email_result
            
        except Exception as e:
            logger.error("Error sending completion email", shop_domain=shop_domain, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _publish_completion_event(self, event_data: Dict[str, Any], schedule_result: Optional[Dict[str, Any]]):
        """Publish completion event to results stream"""
        try:
            completion_event = {
                **event_data,
                "completion_timestamp": datetime.now().isoformat(),
                "schedule_result": schedule_result
            }
            
            message_id = await redis_streams_manager.publish_analysis_results_event(completion_event)
            
            logger.info("Completion event published", message_id=message_id)
            
        except Exception as e:
            logger.error("Error publishing completion event", error=str(e))
    
    async def consume_ml_completion_events(self):
        """Consumer loop for ML training completion events"""
        consumer_name = f"completion-handler-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.info(
            "Starting ML completion event consumer",
            consumer_name=consumer_name
        )
        
        while True:
            try:
                # Consume events from ML training completion stream
                events = await redis_streams_manager.consume_events(
                    stream_name="betterbundle:ml-training-complete",
                    consumer_group="completion-handlers",
                    consumer_name=consumer_name,
                    count=1,
                    block=5000  # 5 seconds
                )
                
                for event in events:
                    try:
                        logger.info(
                            "Processing ML completion event",
                            message_id=event.get("_message_id"),
                            job_id=event.get("job_id")
                        )
                        
                        # Handle the completion
                        result = await self.handle_ml_training_completion(event)
                        
                        # Acknowledge successful processing
                        await redis_streams_manager.acknowledge_event(
                            stream_name="betterbundle:ml-training-complete",
                            consumer_group="completion-handlers",
                            message_id=event["_message_id"]
                        )
                        
                        logger.info(
                            "ML completion event processed",
                            message_id=event.get("_message_id"),
                            success=result.get("success")
                        )
                        
                    except Exception as e:
                        logger.error(
                            "Error processing ML completion event",
                            message_id=event.get("_message_id"),
                            error=str(e)
                        )
                        
                        # Acknowledge even failed events to avoid infinite retries
                        await redis_streams_manager.acknowledge_event(
                            stream_name="betterbundle:ml-training-complete",
                            consumer_group="completion-handlers",
                            message_id=event["_message_id"]
                        )
                
            except Exception as e:
                logger.error("Error in ML completion consumer", error=str(e))
                # Wait before retrying
                await asyncio.sleep(5)


# Global instance
completion_handler = CompletionHandler()
