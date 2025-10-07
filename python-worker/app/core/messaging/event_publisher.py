"""
Event publisher for publishing domain events
"""

import logging
import time
from typing import Dict, Any, Optional, List
from .interfaces import MessageProducer, Message
from ..kafka.producer import KafkaProducer
from ..kafka.strategies import ShopBasedPartitioning

logger = logging.getLogger(__name__)


class EventPublisher:
    """Event publisher for domain events"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._producer: Optional[KafkaProducer] = None
        self._initialized = False

    async def initialize(self):
        """Initialize event publisher"""
        try:
            self._producer = KafkaProducer(
                self.config, partitioning_strategy=ShopBasedPartitioning()
            )
            await self._producer.initialize()
            self._initialized = True
            logger.info("Event publisher initialized")
        except Exception as e:
            logger.error(f"Failed to initialize event publisher: {e}")
            raise

    async def publish_shopify_event(self, event_data: Dict[str, Any]) -> str:
        """Publish Shopify event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        event_with_metadata = {
            **event_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "shopify_webhook",
        }

        # Determine key for partitioning
        key = event_data.get("shop_id") or event_data.get("shopify_id")

        try:
            message_id = await self._producer.send(
                "shopify-events", event_with_metadata, key
            )

            logger.info(
                f"Shopify event published: {event_data.get('event_type')} for shop {event_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish Shopify event: {e}")
            raise

    async def publish_data_job_event(self, job_data: Dict[str, Any]) -> str:
        """Publish data collection job event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        job_with_metadata = {
            **job_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "data_collection",
        }

        key = job_data.get("shop_id")

        try:
            # Pre-publish diagnostic logging
            logger.info(
                "Publishing data collection job",
                extra={
                    "topic": "data-collection-jobs",
                    "job_type": job_data.get("job_type"),
                    "shop_id": job_data.get("shop_id"),
                    "shop_domain": job_data.get("shop_domain"),
                    "data_types": job_data.get("data_types"),
                    "include_products": job_data.get("include_products"),
                    "include_orders": job_data.get("include_orders"),
                    "include_customers": job_data.get("include_customers"),
                    "include_collections": job_data.get("include_collections"),
                    "key": key,
                    "payload_keys": list(job_with_metadata.keys()),
                },
            )

            message_id = await self._producer.send(
                "data-collection-jobs", job_with_metadata, key
            )

            # Post-publish confirmation logging
            logger.info(
                "Data collection job published",
                extra={
                    "topic": "data-collection-jobs",
                    "message_id": message_id,
                    "job_type": job_data.get("job_type"),
                    "shop_id": job_data.get("shop_id"),
                    "data_types": job_data.get("data_types"),
                },
            )
            return message_id

        except Exception as e:
            # Failure logging with minimal payload echo
            logger.error(
                f"Failed to publish data job: {e}",
                extra={
                    "topic": "data-collection-jobs",
                    "job_type": job_data.get("job_type"),
                    "shop_id": job_data.get("shop_id"),
                },
            )
            raise

    async def publish_ml_training_event(self, training_data: Dict[str, Any]) -> str:
        """Publish ML training event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        training_with_metadata = {
            **training_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "ml_training",
        }

        key = training_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "ml-training", training_with_metadata, key
            )

            logger.info(
                f"ML training event published for shop {training_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish ML training event: {e}")
            raise

    async def publish_billing_event(self, billing_data: Dict[str, Any]) -> str:
        """Publish billing event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        billing_with_metadata = {
            **billing_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "billing",
        }

        key = billing_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "billing-events", billing_with_metadata, key
            )

            logger.info(
                f"Billing event published: {billing_data.get('event_type')} for shop {billing_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish billing event: {e}")
            raise

    async def publish_access_control_event(self, access_data: Dict[str, Any]) -> str:
        """Publish access control event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        access_with_metadata = {
            **access_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "access_control",
        }

        key = access_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "access-control", access_with_metadata, key
            )

            logger.info(
                f"Access control event published: {access_data.get('event_type')} for shop {access_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish access control event: {e}")
            raise

    async def publish_normalization_event(
        self, normalization_data: Dict[str, Any]
    ) -> str:
        """Publish normalization job event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        norm_with_metadata = {
            **normalization_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "normalization",
        }

        key = normalization_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "normalization-jobs", norm_with_metadata, key
            )

            logger.info(
                f"Normalization job published: {normalization_data.get('event_type')} for shop {normalization_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish normalization event: {e}")
            raise

    async def publish_behavioral_event(self, behavioral_data: Dict[str, Any]) -> str:
        """Publish behavioral event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        behavioral_with_metadata = {
            **behavioral_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "behavioral_events",
        }

        key = behavioral_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "behavioral-events", behavioral_with_metadata, key
            )

            logger.info(
                f"Behavioral event published: {behavioral_data.get('event_type')} for shop {behavioral_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish behavioral event: {e}")
            raise

    async def publish_analytics_event(self, analytics_data: Dict[str, Any]) -> str:
        """Publish analytics event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        analytics_with_metadata = {
            **analytics_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "analytics",
        }

        key = analytics_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "analytics-events", analytics_with_metadata, key
            )

            logger.info(
                f"Analytics event published: {analytics_data.get('event_type')} for shop {analytics_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish analytics event: {e}")
            raise

    async def publish_notification_event(
        self, notification_data: Dict[str, Any]
    ) -> str:
        """Publish notification event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        notification_with_metadata = {
            **notification_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "notifications",
        }

        key = notification_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "notification-events", notification_with_metadata, key
            )

            logger.info(
                f"Notification event published: {notification_data.get('event_type')} for shop {notification_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish notification event: {e}")
            raise

    async def publish_integration_event(self, integration_data: Dict[str, Any]) -> str:
        """Publish integration event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        integration_with_metadata = {
            **integration_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "integrations",
        }

        key = integration_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "integration-events", integration_with_metadata, key
            )

            logger.info(
                f"Integration event published: {integration_data.get('event_type')} for shop {integration_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish integration event: {e}")
            raise

    async def publish_audit_event(self, audit_data: Dict[str, Any]) -> str:
        """Publish audit event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        audit_with_metadata = {
            **audit_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "audit",
        }

        key = audit_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "audit-events", audit_with_metadata, key
            )

            logger.info(
                f"Audit event published: {audit_data.get('event_type')} for shop {audit_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish audit event: {e}")
            raise

    async def publish_feature_computation_event(
        self, feature_data: Dict[str, Any]
    ) -> str:
        """Publish feature computation event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        feature_with_metadata = {
            **feature_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "feature_computation",
        }

        key = feature_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "feature-computation-jobs", feature_with_metadata, key
            )

            logger.info(
                f"Feature computation event published: {feature_data.get('event_type')} for shop {feature_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish feature computation event: {e}")
            raise

    async def publish_customer_linking_event(self, linking_data: Dict[str, Any]) -> str:
        """Publish customer linking event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        linking_with_metadata = {
            **linking_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "customer_linking",
        }

        key = linking_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "customer-linking-jobs", linking_with_metadata, key
            )

            logger.info(
                f"Customer linking event published: {linking_data.get('event_type')} for shop {linking_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish customer linking event: {e}")
            raise

    async def publish_purchase_attribution_event(
        self, attribution_data: Dict[str, Any]
    ) -> str:
        """Publish purchase attribution event"""
        if not self._initialized:
            await self.initialize()

        # Add metadata
        attribution_with_metadata = {
            **attribution_data,
            "timestamp": int(time.time() * 1000),
            "worker_id": self.config.get("worker_id", "unknown"),
            "source": "purchase_attribution",
        }

        key = attribution_data.get("shop_id")

        try:
            message_id = await self._producer.send(
                "purchase-attribution-jobs", attribution_with_metadata, key
            )

            logger.info(
                f"Purchase attribution event published: {attribution_data.get('event_type')} for shop {attribution_data.get('shop_id')}"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish purchase attribution event: {e}")
            raise

    async def publish_batch(self, events: List[Dict[str, Any]]) -> List[str]:
        """Publish multiple events"""
        if not self._initialized:
            await self.initialize()

        batch_messages = []
        for event in events:
            batch_messages.append(
                {
                    "topic": event.get("topic", "shopify-events"),
                    "data": event,
                    "key": event.get("shop_id") or event.get("key"),
                }
            )

        try:
            results = await self._producer.send_batch(batch_messages)
            logger.info(
                f"Batch published: {len([r for r in results if r is not None])}/{len(events)} events"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to publish batch: {e}")
            raise

    async def close(self):
        """Close event publisher"""
        if self._producer:
            await self._producer.close()
        self._initialized = False
        logger.info("Event publisher closed")
