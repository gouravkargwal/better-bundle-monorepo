"""
Kafka-based customer linking consumer for processing customer identity resolution and backfill jobs
"""

from typing import Dict, Any, Optional
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.domains.analytics.services.customer_identity_resolution_service import (
    CustomerIdentityResolutionService,
)
from app.domains.analytics.services.cross_session_linking_service import (
    CrossSessionLinkingService,
)
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class CustomerLinkingKafkaConsumer:
    """Kafka consumer for customer linking jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.identity_resolution_service = CustomerIdentityResolutionService()
        self.cross_session_linking_service = CrossSessionLinkingService()
        self._initialized = False
        self.shop_repo = ShopRepository()
        self.dlq_service = DLQService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["customer-linking-jobs"],
                group_id="customer-linking-processors",
            )

            self._initialized = True
            logger.info("Customer linking Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize customer linking consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting customer linking consumer...")
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing customer linking message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in customer linking consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        logger.info("Customer linking consumer closed")

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual customer linking messages"""
        try:
            logger.info(f"🔄 Processing customer linking message: {message}")

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            # Extract message data
            job_id = payload.get("job_id")
            shop_id = payload.get("shop_id")
            customer_id = payload.get("customer_id")
            trigger_session_id = payload.get("trigger_session_id")
            linked_sessions = payload.get("linked_sessions", [])
            event_type = payload.get("event_type", "customer_linking")

            logger.info(
                f"📨 Received customer linking message - job_id: {job_id}, shop_id: {shop_id}, customer_id: {customer_id}, event_type: {event_type}"
            )

            if not job_id or not shop_id or not customer_id:
                logger.error("❌ Invalid message: missing required fields")
                return

            logger.info(
                f"🔄 Processing customer linking job - job_id: {job_id}, shop_id: {shop_id}, customer_id: {customer_id}, event_type: {event_type}"
            )

            if not await self.shop_repo.is_shop_active(shop_id):
                logger.warning(
                    "Shop is not active for customer linking",
                    shop_id=shop_id,
                )
                await self.dlq_service.send_to_dlq(
                    original_message=payload,
                    reason="shop_suspended",
                    original_topic="customer-linking-jobs",
                    error_details=f"Shop suspended at {datetime.utcnow().isoformat()}",
                )
                await self.consumer.commit(message)
                logger.info(f"✅ Shop {shop_id} is suspended")
                return

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
                logger.warning(f"Unknown event type: {event_type}")

            logger.info(
                f"Customer linking job completed", job_id=job_id, shop_id=shop_id
            )

        except Exception as e:
            logger.error(f"Error processing customer linking message: {str(e)}")
            raise

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
            logger.info(
                f"🔍 Processing customer identity resolution for customer {customer_id} with trigger_session_id: {trigger_session_id}"
            )

            # Run cross-session linking to find more sessions
            logger.info(
                f"🔗 Starting cross-session linking for customer {customer_id}..."
            )
            linking_result = (
                await self.cross_session_linking_service.link_customer_sessions(
                    customer_id=customer_id,
                    shop_id=shop_id,
                    trigger_session_id=trigger_session_id,
                )
            )

            logger.info(f"📊 Cross-session linking result: {linking_result}")

            if linking_result.get("success"):
                linked_sessions = linking_result.get("linked_sessions", [])
                logger.info(
                    f"✅ Cross-session linking completed: {len(linked_sessions)} sessions linked - {linked_sessions}"
                )

                # Always include trigger_session_id in backfill
                sessions_to_backfill = []

                if trigger_session_id:
                    sessions_to_backfill.append(trigger_session_id)

                # Add any additional linked sessions
                if linked_sessions:
                    sessions_to_backfill.extend(linked_sessions)

                # Remove duplicates
                sessions_to_backfill = list(set(sessions_to_backfill))

                # Trigger backfill
                if sessions_to_backfill:
                    logger.info(
                        f"🔄 Starting backfill for {len(sessions_to_backfill)} sessions: {sessions_to_backfill}"
                    )
                    await self._process_interaction_backfill(
                        job_id, shop_id, customer_id, sessions_to_backfill
                    )
                else:
                    logger.warning(
                        f"⚠️ No sessions to backfill for customer {customer_id}"
                    )
            else:
                logger.warning(
                    f"❌ Cross-session linking failed: {linking_result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"❌ Error in customer linking: {str(e)}")
            raise

    async def _process_cross_session_linking(
        self, job_id: str, shop_id: str, customer_id: str
    ):
        """Process cross-session linking for a customer"""
        try:
            logger.info(f"Processing cross-session linking for customer {customer_id}")

            # Run cross-session linking
            result = await self.cross_session_linking_service.link_customer_sessions(
                customer_id=customer_id, shop_id=shop_id
            )

            if result.get("success"):
                logger.info(
                    f"Cross-session linking completed: {result.get('linked_sessions', 0)} sessions linked"
                )
            else:
                logger.warning(
                    f"Cross-session linking failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"Error in cross-session linking: {str(e)}")
            raise

    async def _process_interaction_backfill(
        self, job_id: str, shop_id: str, customer_id: str, linked_sessions: list
    ):
        """Process backfill of customer interactions"""
        try:
            from sqlalchemy import select
            from app.core.database.session import get_session_context
            from app.core.database.models.user_interaction import (
                UserInteraction as SAUserInteraction,
            )

            logger.info(
                f"🔄 Processing interaction backfill for customer {customer_id} with {len(linked_sessions)} sessions: {linked_sessions}"
            )

            # Get all session IDs that need backfill
            all_session_ids = linked_sessions
            total_backfilled = 0

            # Update all interactions in these sessions with missing customer_id
            for session_id in all_session_ids:
                logger.info(
                    f"🔍 Backfilling session {session_id} for customer {customer_id}..."
                )

                async with get_session_context() as session:
                    stmt = select(SAUserInteraction).where(
                        SAUserInteraction.session_id == session_id,
                        SAUserInteraction.customer_id.is_(None),
                    )
                    result = await session.execute(stmt)
                    interactions = result.scalars().all()

                    for interaction in interactions:
                        interaction.customer_id = customer_id
                    await session.commit()

                    backfilled_count = len(interactions)

                logger.info(
                    f"✅ Backfilled {backfilled_count} interactions for session {session_id}"
                )
                total_backfilled += backfilled_count

            logger.info(f"📊 Total interactions backfilled: {total_backfilled}")

            # Fire feature computation event for updated interactions
            try:
                logger.info(
                    f"🚀 Firing feature computation event for shop {shop_id}..."
                )
                await self.identity_resolution_service.fire_feature_computation_event(
                    shop_id=shop_id,
                    trigger_source="customer_linking_backfill",
                    interaction_id=None,
                    batch_size=100,
                    incremental=True,
                )
                logger.info(f"✅ Feature computation event fired successfully")
            except Exception as e:
                logger.warning(f"⚠️ Failed to fire feature computation event: {str(e)}")

            logger.info(
                f"✅ Interaction backfill completed for customer {customer_id} - {total_backfilled} interactions updated"
            )

        except Exception as e:
            logger.error(f"❌ Error in interaction backfill: {str(e)}")
            raise
