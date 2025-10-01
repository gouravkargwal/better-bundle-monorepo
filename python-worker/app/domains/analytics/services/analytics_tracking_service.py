"""
Analytics Tracking Service for Unified Analytics

Handles tracking of user interactions across all extensions with proper
validation, storage, and real-time processing.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.core.database.session import get_transaction_context
from app.core.database.models.user_interaction import (
    UserInteraction as UserInteractionModel,
)
from app.core.database.models.user_session import UserSession as UserSessionModel
from app.core.database.models.shop import Shop
from sqlalchemy import select, and_, or_, desc, func
from app.domains.analytics.models.interaction import (
    UserInteraction,
    InteractionCreate,
    InteractionQuery,
    InteractionType,
)

# Removed complex constants - keeping it simple
from app.domains.analytics.models.extension import (
    ExtensionType,
    get_extension_capability,
)
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.shared.helpers.datetime_utils import utcnow
from app.core.logging.logger import get_logger
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings

logger = get_logger(__name__)


class AnalyticsTrackingService:
    """Service for tracking user interactions across all extensions"""

    def __init__(self):
        self.session_service = UnifiedSessionService()

    async def track_interaction(
        self,
        session_id: str,
        extension_type: ExtensionType,
        interaction_type: InteractionType,
        shop_id: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserInteraction]:
        """
        Track a user interaction across any extension

        Args:
            session_id: Unified session identifier
            extension_type: Extension that generated the interaction
            interaction_type: Type of interaction
            shop_id: Shop identifier
            customer_id: Customer identifier (optional)
            metadata: Additional metadata (optional)

        Returns:
            UserInteraction: Created interaction record
        """
        try:
            # Validate session exists and is active
            session = await self.session_service.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found or expired")
                return None

            # Validate extension can run in this context
            if not self._validate_extension_context(extension_type):
                logger.warning(f"Extension {extension_type} cannot run in context")
                return None

            logger.info(f"Metadata: {metadata}")
            # Create interaction record
            interaction_data = InteractionCreate(
                session_id=session_id,
                extension_type=extension_type,
                interaction_type=interaction_type,
                customer_id=customer_id,
                shop_id=shop_id,
                metadata=metadata or {},
            )

            # Save interaction to database
            interaction = await self._save_interaction(interaction_data)

            if interaction:
                # Update session with extension usage and interaction count
                await self.session_service.add_extension_to_session(
                    session_id, extension_type.value
                )
                await self.session_service.increment_session_interactions(session_id)

                # Handle customer linking for CUSTOMER_LINKED interactions
                if interaction_type == InteractionType.CUSTOMER_LINKED and customer_id:
                    logger.info(
                        f"🔗 CUSTOMER_LINKED detected - shop_id: {shop_id}, session_id: {session_id}, customer_id: {customer_id}"
                    )
                    await self._trigger_customer_linking(
                        shop_id, session_id, customer_id
                    )

                # Fire feature computation event for ML pipeline
                try:
                    await self.fire_feature_computation_event(
                        shop_id=shop_id,
                        trigger_source=f"{extension_type.value}_interaction",
                        interaction_id=interaction.id,
                        incremental=True,
                    )
                    logger.debug(
                        f"Feature computation event fired for interaction {interaction.id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to fire feature computation event: {str(e)}"
                    )

                logger.info(
                    f"Tracked interaction: {interaction_type} from {extension_type} in"
                )

            return interaction

        except Exception as e:
            logger.error(f"Error tracking interaction: {str(e)}")
            return None

    async def get_interactions(
        self, query: InteractionQuery, limit: int = 100, offset: int = 0
    ) -> List[UserInteraction]:
        """Get interactions based on query criteria"""
        try:
            async with get_transaction_context() as session:
                # Build where conditions for SQLAlchemy
                where_conditions = []

                if query.session_id:
                    where_conditions.append(
                        UserInteractionModel.session_id == query.session_id
                    )

                if query.customer_id:
                    where_conditions.append(
                        UserInteractionModel.customer_id == query.customer_id
                    )

                if query.shop_id:
                    where_conditions.append(
                        UserInteractionModel.shop_id == query.shop_id
                    )

                if query.extension_type:
                    where_conditions.append(
                        UserInteractionModel.extension_type
                        == query.extension_type.value
                    )

                if query.interaction_type:
                    where_conditions.append(
                        UserInteractionModel.interaction_type
                        == query.interaction_type.value
                    )

                if query.created_after:
                    where_conditions.append(
                        UserInteractionModel.created_at >= query.created_after
                    )

                if query.created_before:
                    where_conditions.append(
                        UserInteractionModel.created_at <= query.created_before
                    )

                # Execute query using SQLAlchemy
                stmt = select(UserInteractionModel)
                if where_conditions:
                    stmt = stmt.where(and_(*where_conditions))
                stmt = (
                    stmt.order_by(desc(UserInteractionModel.created_at))
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                interactions_data = result.scalars().all()

                # Convert to Pydantic models
                interactions = []
                for interaction_data in interactions_data:
                    interaction = UserInteraction(
                        id=interaction_data.id,
                        session_id=interaction_data.session_id,
                        extension_type=ExtensionType(interaction_data.extension_type),
                        interaction_type=InteractionType(
                            interaction_data.interaction_type
                        ),
                        customer_id=interaction_data.customer_id,
                        shop_id=interaction_data.shop_id,
                        interaction_metadata=interaction_data.metadata,
                        created_at=interaction_data.created_at,
                    )
                    interactions.append(interaction)

                return interactions

        except Exception as e:
            logger.error(f"Error getting interactions: {str(e)}")
            return []

    async def get_session_interactions(
        self, session_id: str, limit: int = 100
    ) -> List[UserInteraction]:
        """Get all interactions for a specific session"""
        try:
            query = InteractionQuery(session_id=session_id)
            return await self.get_interactions(query, limit=limit)

        except Exception as e:
            logger.error(f"Error getting session interactions: {str(e)}")
            return []

    async def get_customer_interactions(
        self, customer_id: str, shop_id: str, limit: int = 100
    ) -> List[UserInteraction]:
        """Get all interactions for a specific customer"""
        try:
            query = InteractionQuery(customer_id=customer_id, shop_id=shop_id)
            return await self.get_interactions(query, limit=limit)

        except Exception as e:
            logger.error(f"Error getting customer interactions: {str(e)}")
            return []

    async def get_product_interactions(
        self, shop_id: str, limit: int = 100
    ) -> List[UserInteraction]:
        """Get all interactions for a specific product"""
        try:
            query = InteractionQuery(shop_id=shop_id)
            return await self.get_interactions(query, limit=limit)

        except Exception as e:
            logger.error(f"Error getting product interactions: {str(e)}")
            return []

    async def get_recommendation_performance(
        self, recommendation_id: str, shop_id: str
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific recommendation"""
        try:
            async with get_transaction_context() as session:
                # Get all interactions for this recommendation
                stmt = (
                    select(UserInteractionModel)
                    .where(
                        and_(
                            UserInteractionModel.shop_id == shop_id,
                            # Note: recommendation_id would need to be stored in metadata
                            # This is a simplified version - you might need to adjust based on your schema
                        )
                    )
                    .order_by(desc(UserInteractionModel.created_at))
                )

                result = await session.execute(stmt)
                interactions_data = result.scalars().all()

                # Convert to Pydantic models for processing
                interactions = []
                for interaction_data in interactions_data:
                    interaction = UserInteraction(
                        id=interaction_data.id,
                        session_id=interaction_data.session_id,
                        extension_type=ExtensionType(interaction_data.extension_type),
                        interaction_type=InteractionType(
                            interaction_data.interaction_type
                        ),
                        customer_id=interaction_data.customer_id,
                        shop_id=interaction_data.shop_id,
                        interaction_metadata=interaction_data.metadata,
                        created_at=interaction_data.created_at,
                    )
                    interactions.append(interaction)

                # Calculate metrics
                total_views = len(
                    [
                        i
                        for i in interactions
                        if i.interaction_type == InteractionType.RECOMMENDATION_VIEW
                    ]
                )
                total_clicks = len(
                    [
                        i
                        for i in interactions
                        if i.interaction_type == InteractionType.RECOMMENDATION_CLICK
                    ]
                )
                total_adds = len(
                    [
                        i
                        for i in interactions
                        if i.interaction_type
                        == InteractionType.RECOMMENDATION_ADD_TO_CART
                    ]
                )
                total_purchases = len(
                    [
                        i
                        for i in interactions
                        if i.interaction_type == InteractionType.RECOMMENDATION_PURCHASE
                    ]
                )

                # Calculate conversion rates
                click_rate = (
                    (total_clicks / total_views * 100) if total_views > 0 else 0
                )
                add_rate = (total_adds / total_views * 100) if total_views > 0 else 0
                purchase_rate = (
                    (total_purchases / total_views * 100) if total_views > 0 else 0
                )

                return {
                    "recommendation_id": recommendation_id,
                    "total_views": total_views,
                    "total_clicks": total_clicks,
                    "total_adds": total_adds,
                    "total_purchases": total_purchases,
                    "click_rate": round(click_rate, 2),
                    "add_rate": round(add_rate, 2),
                    "purchase_rate": round(purchase_rate, 2),
                    "interactions": interactions,
                }

        except Exception as e:
            logger.error(f"Error getting recommendation performance: {str(e)}")
            return {}

    async def get_extension_performance(
        self, extension_type: ExtensionType, shop_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific extension"""
        try:

            # Calculate date range
            end_date = utcnow()
            start_date = end_date - timedelta(days=days)

            query = InteractionQuery(
                extension_type=extension_type,
                shop_id=shop_id,
                created_after=start_date,
                created_before=end_date,
            )

            interactions = await self.get_interactions(query, limit=1000)

            # Calculate metrics
            total_interactions = len(interactions)
            unique_sessions = len(set(i.session_id for i in interactions))
            unique_customers = len(
                set(i.customer_id for i in interactions if i.customer_id)
            )

            # Group by interaction type
            interactions_by_type = {}
            for interaction in interactions:
                interaction_type = interaction.interaction_type
                if interaction_type not in interactions_by_type:
                    interactions_by_type[interaction_type] = 0
                interactions_by_type[interaction_type] += 1

            # Group by context
            interactions_by_context = {}
            for interaction in interactions:
                context = interaction.extension_type.value
                if context not in interactions_by_context:
                    interactions_by_context[context] = 0
                interactions_by_context[context] += 1

            return {
                "extension_type": extension_type.value,
                "period_days": days,
                "total_interactions": total_interactions,
                "unique_sessions": unique_sessions,
                "unique_customers": unique_customers,
                "interactions_by_type": interactions_by_type,
                "interactions_by_context": interactions_by_context,
                "avg_interactions_per_session": (
                    round(total_interactions / unique_sessions, 2)
                    if unique_sessions > 0
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting extension performance: {str(e)}")
            return {}

    def _validate_extension_context(self, extension_type: ExtensionType) -> bool:
        """Validate that extension can run in the specified context"""
        try:
            capability = get_extension_capability(extension_type)
            return True

        except Exception as e:
            logger.error(f"Error validating extension context: {str(e)}")
            return False

    async def _save_interaction(
        self, interaction_data: InteractionCreate
    ) -> Optional[UserInteraction]:
        """Save interaction to database"""
        try:
            async with get_transaction_context() as session:
                # Validate shop exists before creating interaction
                shop_result = await session.execute(
                    select(Shop).where(Shop.id == interaction_data.shop_id)
                )
                shop = shop_result.scalar_one_or_none()

                if not shop:
                    logger.error(f"Shop not found for ID: {interaction_data.shop_id}")
                    return None

                if not shop.is_active:
                    logger.error(f"Shop is inactive for ID: {interaction_data.shop_id}")
                    return None

                # Generate unique interaction ID
                interaction_id = f"interaction_{uuid.uuid4().hex[:16]}"

                logger.info(f"Interaction data: {interaction_data}")
                logger.info(
                    f"Interaction data metadata: {interaction_data.model_dump()}"
                )

                # Create interaction record using SQLAlchemy
                interaction_model = UserInteractionModel(
                    id=interaction_id,
                    session_id=interaction_data.session_id,
                    extension_type=interaction_data.extension_type.value,
                    interaction_type=interaction_data.interaction_type.value,
                    customer_id=interaction_data.customer_id,
                    shop_id=interaction_data.shop_id,
                    interaction_metadata=interaction_data.metadata,
                    created_at=utcnow(),
                )

                logger.info(f"Interaction model: {interaction_model}")

                session.add(interaction_model)
                await session.commit()
                await session.refresh(interaction_model)

                # Convert to Pydantic model
                interaction = UserInteraction(
                    id=interaction_model.id,
                    session_id=interaction_model.session_id,
                    extension_type=ExtensionType(interaction_model.extension_type),
                    interaction_type=InteractionType(
                        interaction_model.interaction_type
                    ),
                    customer_id=interaction_model.customer_id,
                    shop_id=interaction_model.shop_id,
                    interaction_metadata=interaction_model.interaction_metadata,
                    created_at=interaction_model.created_at,
                )

                return interaction

        except Exception as e:
            logger.error(f"Error saving interaction: {str(e)}")
            return None

    async def fire_feature_computation_event(
        self,
        shop_id: str,
        trigger_source: str,
        interaction_id: Optional[str] = None,
        batch_size: int = 50,
        incremental: bool = True,
    ) -> Optional[str]:
        """
        Fire a feature computation event to trigger incremental ML pipeline

        Args:
            shop_id: The shop ID to compute features for
            trigger_source: Source that triggered the computation (e.g., "venus_interaction")
            interaction_id: Optional interaction ID that triggered the computation
            batch_size: Batch size for feature processing
            incremental: Whether to run incremental processing

        Returns:
            Event ID if successful, None if failed
        """
        try:

            # Generate a unique job ID
            job_id = f"analytics_triggered_{shop_id}_{int(utcnow().timestamp())}"

            # Prepare event metadata
            metadata = {
                "batch_size": batch_size,
                "incremental": incremental,
                "trigger_source": trigger_source,
                "interaction_id": interaction_id,
                "timestamp": utcnow().isoformat(),
                "processed_count": 0,
            }

            # Create feature computation event for Kafka
            feature_event = {
                "job_id": job_id,
                "shop_id": shop_id,
                "features_ready": False,  # Need to be computed
                "metadata": metadata,
                "event_type": "feature_computation",
                "data_type": "interactions",
                "timestamp": utcnow().isoformat(),
                "source": "analytics_tracking",
            }

            # Publish the feature computation event to Kafka
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()

            try:
                event_id = await publisher.publish_feature_computation_event(
                    feature_event
                )

                logger.info(
                    f"Fired feature computation event from {trigger_source} via Kafka",
                    job_id=job_id,
                    shop_id=shop_id,
                    interaction_id=interaction_id,
                    event_id=event_id,
                )

                return event_id
            finally:
                await publisher.close()

        except Exception as e:
            logger.error(f"Failed to fire feature computation event: {str(e)}")
            return None

    async def _trigger_customer_linking(
        self, shop_id: str, session_id: str, customer_id: str
    ):
        """
        Trigger customer linking for cross-session linking and backfilling

        This method publishes a customer linking event to the consumer
        which will handle cross-session linking and UserInteraction backfilling.
        """
        try:
            logger.info(
                f"🚀 Starting customer linking trigger - shop_id: {shop_id}, session_id: {session_id}, customer_id: {customer_id}"
            )

            # Generate job ID for the customer linking event
            job_id = f"customer_linking_{shop_id}_{customer_id}_{session_id}"
            logger.info(f"📝 Generated job_id: {job_id}")

            # Publish the customer linking event to Kafka
            logger.info(f"📤 Publishing customer linking event to Kafka...")

            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()

            try:
                linking_event = {
                    "job_id": job_id,
                    "shop_id": shop_id,
                    "customer_id": customer_id,
                    "event_type": "customer_linking",
                    "trigger_session_id": session_id,
                    "linked_sessions": None,
                    "metadata": {
                        "session_id": session_id,
                        "source": "analytics_tracking_service",
                    },
                }

                event_id = await publisher.publish_customer_linking_event(linking_event)
            finally:
                await publisher.close()

            logger.info(
                f"✅ Published customer linking event - event_id: {event_id}, customer: {customer_id}, session: {session_id}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to trigger customer linking: {e}")
            raise
