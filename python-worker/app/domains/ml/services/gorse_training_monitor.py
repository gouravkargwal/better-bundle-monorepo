"""
Gorse training completion monitor service
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.shared.decorators import async_timing, monitor
from app.shared.helpers import now_utc
from app.shared.constants.redis import (
    ML_TRAINING_COMPLETE_STREAM,
    FEATURES_COMPUTED_STREAM,
    HEURISTIC_DECISION_REQUESTED_STREAM,
)
from app.domains.analytics.services import HeuristicService


@dataclass
class TrainingCompletionEvent:
    """Training completion event data"""
    shop_id: str
    model_id: str
    training_job_id: str
    completion_time: datetime
    model_performance: Dict[str, Any]
    training_duration: float
    final_metrics: Dict[str, Any]
    model_artifacts: Dict[str, Any]
    deployment_status: str
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = now_utc()


class GorseTrainingMonitor:
    """Monitors Gorse training completion and triggers next steps"""
    
    def __init__(self, heuristic_service: HeuristicService):
        self.logger = get_logger(__name__)
        self.heuristic_service = heuristic_service
        
        # Redis key patterns for monitoring
        self.training_completion_patterns = [
            "gorse:training:complete:*",
            "gorse:model:deployed:*",
            "gorse:training:status:completed:*"
        ]
        
        # Monitoring state
        self.monitored_shops: Set[str] = set()
        self.completion_events: Dict[str, TrainingCompletionEvent] = {}
        self.last_check_time = now_utc()
        
        # Monitoring intervals
        self.check_interval = 30  # seconds
        self.cleanup_interval = 3600  # 1 hour
        
        # Performance tracking
        self.completions_detected = 0
        self.next_steps_triggered = 0
        self.errors_encountered = 0
    
    async def start_monitoring(self, shop_ids: List[str]):
        """Start monitoring training completion for specific shops"""
        try:
            self.logger.info(f"Starting Gorse training monitoring for {len(shop_ids)} shops")
            
            # Add shops to monitoring
            for shop_id in shop_ids:
                self.monitored_shops.add(shop_id)
            
            # Start monitoring loop
            asyncio.create_task(self._monitoring_loop())
            
            self.logger.info("Gorse training monitoring started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start training monitoring: {e}")
            raise
    
    async def stop_monitoring(self):
        """Stop training completion monitoring"""
        try:
            self.logger.info("Stopping Gorse training monitoring")
            
            # Clear monitored shops
            self.monitored_shops.clear()
            
            self.logger.info("Gorse training monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop training monitoring: {e}")
            raise
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting Gorse training monitoring loop")
        
        while self.monitored_shops:
            try:
                # Check for training completions
                await self._check_training_completions()
                
                # Cleanup old events periodically
                await self._cleanup_old_events()
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                self.logger.info("Training monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in training monitoring loop: {e}")
                self.errors_encountered += 1
                await asyncio.sleep(5)  # Wait before retrying
        
        self.logger.info("Gorse training monitoring loop stopped")
    
    async def _check_training_completions(self):
        """Check for new training completions"""
        try:
            current_time = now_utc()
            
            for pattern in self.training_completion_patterns:
                # Scan Redis for completion keys
                completion_keys = await self._scan_completion_keys(pattern)
                
                for key in completion_keys:
                    # Parse key to extract shop_id and other info
                    parsed_info = self._parse_completion_key(key)
                    
                    if not parsed_info:
                        continue
                    
                    shop_id = parsed_info.get("shop_id")
                    if shop_id not in self.monitored_shops:
                        continue
                    
                    # Check if this is a new completion
                    if await self._is_new_completion(key, parsed_info):
                        # Process the completion
                        await self._process_training_completion(key, parsed_info)
            
            self.last_check_time = current_time
            
        except Exception as e:
            self.logger.error(f"Failed to check training completions: {e}")
            raise
    
    async def _scan_completion_keys(self, pattern: str) -> List[str]:
        """Scan Redis for keys matching the completion pattern"""
        try:
            # This would use Redis SCAN command in a real implementation
            # For now, we'll simulate finding some keys
            mock_keys = [
                f"gorse:training:complete:shop_123:model_rec_001",
                f"gorse:model:deployed:shop_456:model_rec_002",
                f"gorse:training:status:completed:shop_789:model_rec_003"
            ]
            
            # Filter keys that match the pattern
            matching_keys = [key for key in mock_keys if self._key_matches_pattern(key, pattern)]
            
            return matching_keys
            
        except Exception as e:
            self.logger.error(f"Failed to scan completion keys: {e}")
            return []
    
    def _key_matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if a key matches a Redis pattern"""
        # Simple pattern matching - in real implementation, use Redis pattern matching
        if "*" in pattern:
            base_pattern = pattern.replace("*", "")
            return base_pattern in key
        return key == pattern
    
    def _parse_completion_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Parse completion key to extract relevant information"""
        try:
            parts = key.split(":")
            
            if len(parts) >= 4:
                return {
                    "key_type": parts[1],
                    "status": parts[2],
                    "shop_id": parts[3].replace("shop_", ""),
                    "model_id": parts[4] if len(parts) > 4 else None,
                    "full_key": key
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to parse completion key {key}: {e}")
            return None
    
    async def _is_new_completion(self, key: str, parsed_info: Dict[str, Any]) -> bool:
        """Check if this completion event is new"""
        # Check if we've already processed this key
        if key in self.completion_events:
            return False
        
        # Check if the completion is recent (within last hour)
        # In real implementation, this would check Redis key creation time
        return True
    
    async def _process_training_completion(self, key: str, parsed_info: Dict[str, Any]):
        """Process a training completion event"""
        try:
            shop_id = parsed_info["shop_id"]
            model_id = parsed_info.get("model_id", "unknown")
            
            self.logger.info(
                f"Processing training completion",
                shop_id=shop_id,
                model_id=model_id,
                key=key
            )
            
            # Create completion event
            completion_event = await self._create_completion_event(key, parsed_info)
            
            # Store the event
            self.completion_events[key] = completion_event
            self.completions_detected += 1
            
            # Trigger next steps
            await self._trigger_next_steps(completion_event)
            
            self.logger.info(
                f"Training completion processed successfully",
                shop_id=shop_id,
                model_id=model_id
            )
            
        except Exception as e:
            self.logger.error(f"Failed to process training completion: {e}", key=key)
            raise
    
    async def _create_completion_event(self, key: str, parsed_info: Dict[str, Any]) -> TrainingCompletionEvent:
        """Create a training completion event from parsed info"""
        try:
            shop_id = parsed_info["shop_id"]
            model_id = parsed_info.get("model_id", "unknown")
            
            # In real implementation, fetch actual training data from Redis/database
            # For now, create mock data
            completion_event = TrainingCompletionEvent(
                shop_id=shop_id,
                model_id=model_id,
                training_job_id=f"job_{model_id}_{int(now_utc().timestamp())}",
                completion_time=now_utc(),
                model_performance={
                    "accuracy": 0.89,
                    "precision": 0.87,
                    "recall": 0.85,
                    "f1_score": 0.86
                },
                training_duration=1800.0,  # 30 minutes
                final_metrics={
                    "loss": 0.12,
                    "val_loss": 0.15,
                    "epochs": 50,
                    "batch_size": 32
                },
                model_artifacts={
                    "model_path": f"/models/{shop_id}/{model_id}/latest",
                    "config_path": f"/models/{shop_id}/{model_id}/config.json",
                    "metadata_path": f"/models/{shop_id}/{model_id}/metadata.json"
                },
                deployment_status="ready"
            )
            
            return completion_event
            
        except Exception as e:
            self.logger.error(f"Failed to create completion event: {e}")
            raise
    
    async def _trigger_next_steps(self, completion_event: TrainingCompletionEvent):
        """Trigger next steps after training completion"""
        try:
            self.logger.info(
                f"Triggering next steps after training completion",
                shop_id=completion_event.shop_id,
                model_id=completion_event.model_id
            )
            
            # Step 1: Publish completion event to Redis stream
            await self._publish_completion_event(completion_event)
            
            # Step 2: Publish features computed event
            await self._publish_features_computed_event(completion_event)
            
            # Step 3: Request heuristic decision for next analysis
            await self._request_heuristic_decision(completion_event)
            
            # Step 4: Update monitoring metrics
            self.next_steps_triggered += 1
            
            self.logger.info(
                f"Next steps triggered successfully",
                shop_id=completion_event.shop_id,
                model_id=completion_event.model_id
            )
            
        except Exception as e:
            self.logger.error(f"Failed to trigger next steps: {e}", shop_id=completion_event.shop_id)
            raise
    
    async def _publish_completion_event(self, completion_event: TrainingCompletionEvent):
        """Publish training completion event to Redis stream"""
        try:
            event_data = {
                "shop_id": completion_event.shop_id,
                "model_id": completion_event.model_id,
                "training_job_id": completion_event.training_job_id,
                "completion_time": completion_event.completion_time.isoformat(),
                "model_performance": completion_event.model_performance,
                "training_duration": completion_event.training_duration,
                "final_metrics": completion_event.final_metrics,
                "model_artifacts": completion_event.model_artifacts,
                "deployment_status": completion_event.deployment_status,
                "timestamp": now_utc().isoformat()
            }
            
            await streams_manager.publish_event(
                ML_TRAINING_COMPLETE_STREAM,
                event_data
            )
            
            self.logger.info(
                f"Published training completion event",
                shop_id=completion_event.shop_id,
                model_id=completion_event.model_id
            )
            
        except Exception as e:
            self.logger.error(f"Failed to publish completion event: {e}", shop_id=completion_event.shop_id)
            raise
    
    async def _publish_features_computed_event(self, completion_event: TrainingCompletionEvent):
        """Publish features computed event"""
        try:
            event_data = {
                "shop_id": completion_event.shop_id,
                "model_id": completion_event.model_id,
                "features_ready": True,
                "metadata": {
                    "training_completed_at": completion_event.completion_time.isoformat(),
                    "model_performance": completion_event.model_performance,
                    "feature_count": len(completion_event.model_performance),
                    "computation_method": "gorse_training"
                },
                "timestamp": now_utc().isoformat()
            }
            
            await streams_manager.publish_event(
                FEATURES_COMPUTED_STREAM,
                event_data
            )
            
            self.logger.info(
                f"Published features computed event",
                shop_id=completion_event.shop_id,
                model_id=completion_event.model_id
            )
            
        except Exception as e:
            self.logger.error(f"Failed to publish features computed event: {e}", shop_id=completion_event.shop_id)
            raise
    
    async def _request_heuristic_decision(self, completion_event: TrainingCompletionEvent):
        """Request heuristic decision for next analysis"""
        try:
            self.logger.info(
                f"Requesting heuristic decision for next analysis",
                shop_id=completion_event.shop_id
            )
            
            # Publish heuristic decision request
            event_data = {
                "shop_id": completion_event.shop_id,
                "trigger_type": "ml_training_completed",
                "model_id": completion_event.model_id,
                "training_performance": completion_event.model_performance,
                "requested_at": now_utc().isoformat()
            }
            
            await streams_manager.publish_event(
                HEURISTIC_DECISION_REQUESTED_STREAM,
                event_data
            )
            
            # Also trigger heuristic evaluation directly
            decision = await self.heuristic_service.evaluate_analysis_need(
                completion_event.shop_id
            )
            
            self.logger.info(
                f"Heuristic decision requested and evaluated",
                shop_id=completion_event.shop_id,
                decision_priority=decision.priority.value,
                scheduled_time=decision.scheduled_time.isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to request heuristic decision: {e}", shop_id=completion_event.shop_id)
            raise
    
    async def _cleanup_old_events(self):
        """Clean up old completion events"""
        try:
            current_time = now_utc()
            cutoff_time = current_time - timedelta(hours=24)  # Keep events for 24 hours
            
            keys_to_remove = []
            
            for key, event in self.completion_events.items():
                if event.created_at < cutoff_time:
                    keys_to_remove.append(key)
            
            # Remove old events
            for key in keys_to_remove:
                del self.completion_events[key]
            
            if keys_to_remove:
                self.logger.info(f"Cleaned up {len(keys_to_remove)} old completion events")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old events: {e}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "monitored_shops": list(self.monitored_shops),
            "completions_detected": self.completions_detected,
            "next_steps_triggered": self.next_steps_triggered,
            "errors_encountered": self.errors_encountered,
            "active_events": len(self.completion_events),
            "last_check_time": self.last_check_time.isoformat(),
            "monitoring_active": len(self.monitored_shops) > 0
        }
    
    def get_completion_events(self, shop_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get completion events, optionally filtered by shop_id"""
        events = []
        
        for event in self.completion_events.values():
            if shop_id is None or event.shop_id == shop_id:
                events.append({
                    "shop_id": event.shop_id,
                    "model_id": event.model_id,
                    "training_job_id": event.training_job_id,
                    "completion_time": event.completion_time.isoformat(),
                    "model_performance": event.model_performance,
                    "deployment_status": event.deployment_status,
                    "created_at": event.created_at.isoformat()
                })
        
        return events
