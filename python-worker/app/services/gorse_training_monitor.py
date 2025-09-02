"""
Resource-Efficient Gorse Training Monitor
Uses Redis Keyspace Notifications to detect training completion without polling
"""

import asyncio
import redis.asyncio as redis
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from app.core.logger import get_logger
from app.core.redis_client import streams_manager

logger = get_logger("gorse-training-monitor")


class GorseTrainingMonitor:
    """Resource-efficient monitor for Gorse training completion"""

    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}

    async def initialize(self):
        """Initialize Redis connection"""
        self._redis_client = redis.Redis(
            host="localhost", port=6379, decode_responses=True
        )
        await self._redis_client.ping()
        logger.info("Gorse training monitor initialized")

    async def start_monitoring_shop(
        self, shop_id: str, job_id: str, callback: Callable
    ):
        """Start monitoring Gorse training for a specific shop"""
        if shop_id in self._monitoring_tasks:
            logger.warning(f"Already monitoring shop {shop_id}")
            return

        # Store callback for this shop
        self._callbacks[shop_id] = callback

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_shop_training(shop_id, job_id),
            name=f"gorse-monitor-{shop_id}",
        )
        self._monitoring_tasks[shop_id] = task

        logger.info(f"Started monitoring Gorse training for shop {shop_id}")

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

            logger.info(f"Stopped monitoring shop {shop_id}")

    async def _monitor_shop_training(self, shop_id: str, job_id: str):
        """Monitor Gorse training progress for a shop using Redis keyspace notifications"""
        try:
            # Get initial state
            initial_state = await self._get_gorse_state()

            # Subscribe to keyspace notifications for Gorse-related keys
            pubsub = self._redis_client.pubsub()

            # Watch for new keys being created
            await pubsub.psubscribe(
                "__keyspace@*__:item_neighbors_digest/*",
                "__keyspace@*__:global_meta/*",
                "__keyspace@*__:popular_items",
                "__keyspace@*__:latest_items",
            )

            logger.info(f"Monitoring Redis keyspace for shop {shop_id}")

            # Monitor for changes
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    # Key change detected!
                    current_state = await self._get_gorse_state()

                    # Check if training has progressed
                    progress = self._detect_progress(initial_state, current_state)

                    if progress["has_progress"]:
                        logger.info(
                            f"Training progress detected for shop {shop_id}: {progress}"
                        )

                        # Update initial state
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

        except asyncio.CancelledError:
            logger.info(f"Monitoring cancelled for shop {shop_id}")
        except Exception as e:
            logger.error(f"Error monitoring shop {shop_id}: {e}")
            # Publish failure event
            await self._publish_failure_event(shop_id, job_id, str(e))
        finally:
            if pubsub:
                await pubsub.close()

    async def _get_gorse_state(self) -> Dict[str, Any]:
        """Get current state of Gorse Redis keys"""
        return {
            "item_neighbors_count": len(
                await self._redis_client.keys("item_neighbors_digest/*")
            ),
            "global_meta_count": len(await self._redis_client.keys("global_meta/*")),
            "has_popular_items": await self._redis_client.exists("popular_items"),
            "has_latest_items": await self._redis_client.exists("latest_items"),
            "timestamp": datetime.now().isoformat(),
        }

    def _detect_progress(self, initial: Dict, current: Dict) -> Dict[str, Any]:
        """Detect if training has progressed"""
        has_progress = False
        is_complete = False

        # Check for new keys
        if current["item_neighbors_count"] > initial["item_neighbors_count"]:
            has_progress = True

        if current["global_meta_count"] > initial["global_meta_count"]:
            has_progress = True

        # Check if training appears complete
        if (
            current["item_neighbors_count"] > 0
            and current["global_meta_count"] > 0
            and current["has_popular_items"]
            and current["has_latest_items"]
        ):
            is_complete = True

        return {
            "has_progress": has_progress,
            "is_complete": is_complete,
            "initial_state": initial,
            "current_state": current,
            "new_item_neighbors": current["item_neighbors_count"]
            - initial["item_neighbors_count"],
            "new_global_meta": current["global_meta_count"]
            - initial["global_meta_count"],
        }

    async def _publish_completion_event(
        self, shop_id: str, job_id: str, progress: Dict
    ):
        """Publish training completion event"""
        completion_event = {
            "event_type": "GORSE_TRAINING_COMPLETED",
            "job_id": job_id,
            "shop_id": shop_id,
            "progress": progress,
            "completed_at": datetime.now().isoformat(),
            "detection_method": "redis_keyspace_notifications",
        }

        await streams_manager.publish_event(
            "betterbundle:gorse-training-complete", completion_event
        )

        logger.info(f"Published training completion event for shop {shop_id}")

    async def _publish_failure_event(self, shop_id: str, job_id: str, error: str):
        """Publish training failure event"""
        failure_event = {
            "event_type": "GORSE_TRAINING_FAILED",
            "job_id": job_id,
            "shop_id": shop_id,
            "error": error,
            "failed_at": datetime.now().isoformat(),
            "detection_method": "redis_keyspace_notifications",
        }

        await streams_manager.publish_event(
            "betterbundle:gorse-training-complete", failure_event
        )

        logger.info(f"Published training failure event for shop {shop_id}")

    async def shutdown(self):
        """Shutdown the monitor"""
        # Stop all monitoring tasks
        for shop_id in list(self._monitoring_tasks.keys()):
            await self.stop_monitoring_shop(shop_id)

        if self._redis_client:
            await self._redis_client.close()

        logger.info("Gorse training monitor shutdown complete")


# Global instance
gorse_training_monitor = GorseTrainingMonitor()
