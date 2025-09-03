"""
Enhanced Resource-Efficient Gorse Training Monitor
Uses Redis Keyspace Notifications to detect training completion without polling
Enhanced with better key patterns, error handling, and progress detection
"""

import asyncio
import redis.asyncio as redis
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, List
from app.core.logger import get_logger
from app.core.redis_client import streams_manager
from app.core.config import settings

logger = get_logger("gorse-training-monitor")


class GorseTrainingMonitor:
    """Enhanced resource-efficient monitor for Gorse training completion"""

    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._monitoring_configs: Dict[str, Dict[str, Any]] = {}
        
        # Enhanced Redis key patterns for better training detection
        self._training_key_patterns = [
            # Core training artifacts
            "__keyspace@*__:item_neighbors_digest/*",
            "__keyspace@*__:global_meta/*",
            "__keyspace@*__:popular_items",
            "__keyspace@*__:latest_items",
            
            # Additional training indicators
            "__keyspace@*__:item_neighbors/*",
            "__keyspace@*__:user_neighbors/*",
            "__keyspace@*__:collaborative_filtering/*",
            "__keyspace@*__:matrix_factorization/*",
            
            # Training metadata
            "__keyspace@*__:training_status/*",
            "__keyspace@*__:model_version/*",
            "__keyspace@*__:last_training/*",
            
            # Cache keys that indicate training completion
            "__keyspace@*__:recommendation_cache/*",
            "__keyspace@*__:similarity_cache/*",
        ]

    async def initialize(self):
        """Initialize Redis connection with better error handling"""
        try:
            # Use settings for Redis connection instead of hardcoded localhost
            self._redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                ssl=settings.REDIS_TLS,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=30,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            
            # Test connection
            await self._redis_client.ping()
            logger.info("Enhanced Gorse training monitor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise

    async def start_monitoring_shop(
        self, shop_id: str, job_id: str, callback: Callable
    ):
        """Start monitoring Gorse training for a specific shop with enhanced configuration"""
        if shop_id in self._monitoring_tasks:
            logger.warning(f"Already monitoring shop {shop_id}")
            return

        # Store callback for this shop
        self._callbacks[shop_id] = callback

        # Create monitoring configuration for this shop
        self._monitoring_configs[shop_id] = {
            "job_id": job_id,
            "started_at": datetime.now(timezone.utc),
            "last_progress": None,
            "progress_count": 0,
            "key_changes": set(),
            "monitoring_active": True,
        }

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_shop_training(shop_id, job_id),
            name=f"enhanced-gorse-monitor-{shop_id}",
        )
        self._monitoring_tasks[shop_id] = task

        logger.info(f"Started enhanced monitoring for shop {shop_id} (job: {job_id})")

    async def stop_monitoring_shop(self, shop_id: str):
        """Stop monitoring a specific shop"""
        if shop_id in self._monitoring_tasks:
            task = self._monitoring_tasks[shop_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            del self._monitoring_tasks[shop_id]
            if shop_id in self._callbacks:
                del self._callbacks[shop_id]
            if shop_id in self._monitoring_configs:
                del self._monitoring_configs[shop_id]

            logger.info(f"Stopped monitoring shop {shop_id}")

    async def _monitor_shop_training(self, shop_id: str, job_id: str):
        """Enhanced monitoring using Redis keyspace notifications with better error handling"""
        pubsub = None
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries and self._monitoring_configs.get(shop_id, {}).get("monitoring_active", False):
            try:
                # Get initial state
                initial_state = await self._get_enhanced_gorse_state()
                
                # Create new pubsub connection for this monitoring session
                pubsub = self._redis_client.pubsub()
                
                # Subscribe to enhanced key patterns
                await pubsub.psubscribe(*self._training_key_patterns)
                
                logger.info(f"Enhanced monitoring active for shop {shop_id} with {len(self._training_key_patterns)} key patterns")

                # Monitor for changes with enhanced detection
                async for message in pubsub.listen():
                    if not self._monitoring_configs.get(shop_id, {}).get("monitoring_active", False):
                        break
                        
                    if message["type"] == "pmessage":
                        # Key change detected!
                        current_state = await self._get_enhanced_gorse_state()
                        
                        # Enhanced progress detection
                        progress = self._detect_enhanced_progress(shop_id, initial_state, current_state)
                        
                        if progress["has_progress"]:
                            logger.info(
                                f"Training progress detected for shop {shop_id}: {progress}"
                            )
                            
                            # Update monitoring state
                            self._update_monitoring_state(shop_id, progress)
                            
                            # Update initial state for next comparison
                            initial_state = current_state
                            
                            # Notify callback
                            if shop_id in self._callbacks:
                                try:
                                    await self._callbacks[shop_id](progress)
                                except Exception as e:
                                    logger.error(f"Callback error for shop {shop_id}: {e}")
                            
                            # Check if training is complete
                            if progress["is_complete"]:
                                logger.info(f"Training appears complete for shop {shop_id}")
                                
                                # Publish completion event
                                await self._publish_completion_event(
                                    shop_id, job_id, progress
                                )
                                
                                # Stop monitoring this shop
                                await self.stop_monitoring_shop(shop_id)
                                break
                                
                        # Check for timeout conditions
                        if await self._should_timeout_monitoring(shop_id):
                            logger.warning(f"Monitoring timeout for shop {shop_id}, publishing timeout event")
                            await self._publish_timeout_event(shop_id, job_id)
                            await self.stop_monitoring_shop(shop_id)
                            break

            except redis.ConnectionError as e:
                retry_count += 1
                logger.warning(f"Redis connection error for shop {shop_id} (attempt {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries:
                    await asyncio.sleep(5 * retry_count)  # Exponential backoff
                    continue
                else:
                    logger.error(f"Max Redis connection retries exceeded for shop {shop_id}")
                    await self._publish_failure_event(shop_id, job_id, f"Redis connection failed after {max_retries} attempts: {e}")
                    break
                    
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for shop {shop_id}")
                break
                
            except Exception as e:
                logger.error(f"Unexpected error monitoring shop {shop_id}: {e}")
                await self._publish_failure_event(shop_id, job_id, str(e))
                break
                
            finally:
                if pubsub:
                    try:
                        await pubsub.close()
                    except Exception as e:
                        logger.warning(f"Error closing pubsub for shop {shop_id}: {e}")

    async def _get_enhanced_gorse_state(self) -> Dict[str, Any]:
        """Get enhanced current state of Gorse Redis keys with better error handling"""
        try:
            # Use pipeline for better performance
            pipe = self._redis_client.pipeline()
            
            # Core training keys
            pipe.keys("item_neighbors_digest/*")
            pipe.keys("global_meta/*")
            pipe.keys("item_neighbors/*")
            pipe.keys("user_neighbors/*")
            pipe.keys("collaborative_filtering/*")
            pipe.keys("matrix_factorization/*")
            
            # Training metadata
            pipe.keys("training_status/*")
            pipe.keys("model_version/*")
            pipe.keys("last_training/*")
            
            # Cache keys
            pipe.keys("recommendation_cache/*")
            pipe.keys("similarity_cache/*")
            
            # Existence checks
            pipe.exists("popular_items")
            pipe.exists("latest_items")
            pipe.exists("training_complete")
            pipe.exists("model_ready")
            
            # Execute pipeline
            results = await pipe.execute()
            
            return {
                "item_neighbors_digest_count": len(results[0]),
                "global_meta_count": len(results[1]),
                "item_neighbors_count": len(results[2]),
                "user_neighbors_count": len(results[3]),
                "collaborative_filtering_count": len(results[4]),
                "matrix_factorization_count": len(results[5]),
                "training_status_count": len(results[6]),
                "model_version_count": len(results[7]),
                "last_training_count": len(results[8]),
                "recommendation_cache_count": len(results[9]),
                "similarity_cache_count": len(results[10]),
                "has_popular_items": bool(results[11]),
                "has_latest_items": bool(results[12]),
                "has_training_complete": bool(results[13]),
                "has_model_ready": bool(results[14]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced Gorse state: {e}")
            # Return minimal state on error
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _detect_enhanced_progress(self, shop_id: str, initial: Dict, current: Dict) -> Dict[str, Any]:
        """Enhanced progress detection with multiple indicators"""
        if "error" in current:
            return {
                "has_progress": False,
                "is_complete": False,
                "error": current["error"],
                "initial_state": initial,
                "current_state": current,
            }
        
        has_progress = False
        is_complete = False
        progress_indicators = []
        
        # Check for new keys in various categories
        key_categories = [
            ("item_neighbors_digest", "item_neighbors_digest_count"),
            ("global_meta", "global_meta_count"),
            ("item_neighbors", "item_neighbors_count"),
            ("user_neighbors", "user_neighbors_count"),
            ("collaborative_filtering", "collaborative_filtering_count"),
            ("matrix_factorization", "matrix_factorization_count"),
            ("training_status", "training_status_count"),
            ("model_version", "model_version_count"),
            ("recommendation_cache", "recommendation_cache_count"),
            ("similarity_cache", "similarity_cache_count"),
        ]
        
        for category, count_key in key_categories:
            if current.get(count_key, 0) > initial.get(count_key, 0):
                has_progress = True
                new_count = current.get(count_key, 0) - initial.get(count_key, 0)
                progress_indicators.append(f"{category}: +{new_count}")
        
        # Check for new boolean flags
        boolean_flags = [
            "has_popular_items",
            "has_latest_items", 
            "has_training_complete",
            "has_model_ready"
        ]
        
        for flag in boolean_flags:
            if current.get(flag, False) and not initial.get(flag, False):
                has_progress = True
                progress_indicators.append(f"{flag}: True")
        
        # Enhanced completion detection
        completion_conditions = [
            current.get("item_neighbors_digest_count", 0) > 0,
            current.get("global_meta_count", 0) > 0,
            current.get("has_popular_items", False),
            current.get("has_latest_items", False),
        ]
        
        # Additional completion indicators
        if current.get("has_training_complete", False) or current.get("has_model_ready", False):
            completion_conditions.append(True)
        
        # Training is complete if most conditions are met
        if sum(completion_conditions) >= 4:  # At least 4 out of 6 conditions
            is_complete = True
        
        return {
            "has_progress": has_progress,
            "is_complete": is_complete,
            "progress_indicators": progress_indicators,
            "completion_score": sum(completion_conditions),
            "total_conditions": len(completion_conditions),
            "initial_state": initial,
            "current_state": current,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _update_monitoring_state(self, shop_id: str, progress: Dict[str, Any]):
        """Update monitoring state for a shop"""
        if shop_id in self._monitoring_configs:
            config = self._monitoring_configs[shop_id]
            config["last_progress"] = progress
            config["progress_count"] += 1
            config["key_changes"].add(progress.get("timestamp", "unknown"))

    async def _should_timeout_monitoring(self, shop_id: str) -> bool:
        """Check if monitoring should timeout"""
        if shop_id not in self._monitoring_configs:
            return False
            
        config = self._monitoring_configs[shop_id]
        started_at = config["started_at"]
        now = datetime.now(timezone.utc)
        
        # Timeout after 30 minutes of monitoring
        timeout_duration = 30 * 60  # 30 minutes in seconds
        if (now - started_at).total_seconds() > timeout_duration:
            return True
            
        # Timeout if no progress for 10 minutes
        if config["last_progress"]:
            last_progress_time = datetime.fromisoformat(config["last_progress"]["timestamp"].replace('Z', '+00:00'))
            if (now - last_progress_time).total_seconds() > 600:  # 10 minutes
                return True
                
        return False

    async def _publish_completion_event(
        self, shop_id: str, job_id: str, progress: Dict
    ):
        """Publish training completion event"""
        completion_event = {
            "event_type": "GORSE_TRAINING_COMPLETED",
            "job_id": job_id,
            "shop_id": shop_id,
            "progress": progress,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "detection_method": "enhanced_redis_keyspace_notifications",
            "monitoring_duration": self._get_monitoring_duration(shop_id),
        }

        await streams_manager.publish_event(
            "betterbundle:gorse-training-complete", completion_event
        )

        logger.info(f"Published enhanced training completion event for shop {shop_id}")

    async def _publish_timeout_event(self, shop_id: str, job_id: str):
        """Publish monitoring timeout event"""
        timeout_event = {
            "event_type": "GORSE_TRAINING_TIMEOUT",
            "job_id": job_id,
            "shop_id": shop_id,
            "timeout_at": datetime.now(timezone.utc).isoformat(),
            "detection_method": "enhanced_redis_keyspace_notifications",
            "monitoring_duration": self._get_monitoring_duration(shop_id),
            "reason": "Monitoring timeout - training may still be in progress",
        }

        await streams_manager.publish_event(
            "betterbundle:gorse-training-complete", timeout_event
        )

        logger.info(f"Published monitoring timeout event for shop {shop_id}")

    async def _publish_failure_event(self, shop_id: str, job_id: str, error: str):
        """Publish training failure event"""
        failure_event = {
            "event_type": "GORSE_TRAINING_FAILED",
            "job_id": job_id,
            "shop_id": shop_id,
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "detection_method": "enhanced_redis_keyspace_notifications",
            "monitoring_duration": self._get_monitoring_duration(shop_id),
        }

        await streams_manager.publish_event(
            "betterbundle:gorse-training-complete", failure_event
        )

        logger.info(f"Published enhanced training failure event for shop {shop_id}")

    def _get_monitoring_duration(self, shop_id: str) -> Optional[float]:
        """Get monitoring duration for a shop in seconds"""
        if shop_id in self._monitoring_configs:
            started_at = self._monitoring_configs[shop_id]["started_at"]
            now = datetime.now(timezone.utc)
            return (now - started_at).total_seconds()
        return None

    async def shutdown(self):
        """Shutdown the monitor"""
        # Stop all monitoring tasks
        for shop_id in list(self._monitoring_tasks.keys()):
            await self.stop_monitoring_shop(shop_id)

        if self._redis_client:
            await self._redis_client.close()

        logger.info("Enhanced Gorse training monitor shutdown complete")


# Global instance
gorse_training_monitor = GorseTrainingMonitor()
