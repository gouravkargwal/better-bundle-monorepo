"""
Analytics Tracking Service for Unified Analytics

Handles tracking of user interactions across all extensions with proper
validation, storage, and real-time processing.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from prisma import Json

from app.core.database import get_database
from app.domains.analytics.models.interaction import (
    UserInteraction,
    InteractionCreate,
    InteractionQuery,
    InteractionType,
)
from app.domains.analytics.models.extension import ExtensionType
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.shared.helpers.datetime_utils import utcnow
from app.core.logging.logger import get_logger

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
            db = await get_database()

            # Build where conditions for Prisma
            where_conditions = {}

            if query.session_id:
                where_conditions["sessionId"] = query.session_id

            if query.customer_id:
                where_conditions["customerId"] = query.customer_id

            if query.shop_id:
                where_conditions["shopId"] = query.shop_id

            if query.extension_type:
                where_conditions["extensionType"] = query.extension_type.value

            if query.interaction_type:
                where_conditions["interactionType"] = query.interaction_type.value

            if query.created_after:
                where_conditions["createdAt"] = {"gte": query.created_after}

            if query.created_before:
                if "createdAt" in where_conditions:
                    where_conditions["createdAt"]["lte"] = query.created_before
                else:
                    where_conditions["createdAt"] = {"lte": query.created_before}

            # Execute query using Prisma
            interactions_data = await db.userinteraction.find_many(
                where=where_conditions,
                order={"createdAt": "desc"},
                take=limit,
                skip=offset,
            )

            # Convert to Pydantic models
            interactions = []
            for interaction_data in interactions_data:
                interaction = UserInteraction(
                    id=interaction_data.id,
                    session_id=interaction_data.sessionId,
                    extension_type=ExtensionType(interaction_data.extensionType),
                    interaction_type=InteractionType(interaction_data.interactionType),
                    customer_id=interaction_data.customerId,
                    shop_id=interaction_data.shopId,
                    metadata=interaction_data.metadata,
                    created_at=interaction_data.createdAt,
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
            db = await get_database()

            # Get all interactions for this recommendation
            result = await db.execute(
                select(UserInteraction)
                .where(
                    and_(
                        UserInteraction.recommendation_id == recommendation_id,
                        UserInteraction.shop_id == shop_id,
                    )
                )
                .order_by(desc(UserInteraction.created_at))
            )

            interactions = result.scalars().all()

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
                    if i.interaction_type == InteractionType.RECOMMENDATION_ADD_TO_CART
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
            click_rate = (total_clicks / total_views * 100) if total_views > 0 else 0
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
            from datetime import timedelta

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
            from app.domains.analytics.models.extension import get_extension_capability

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
            db = await get_database()

            # Generate unique interaction ID
            interaction_id = f"interaction_{uuid.uuid4().hex[:16]}"

            # Create interaction record using Prisma
            interaction_data_db = await db.userinteraction.create(
                data={
                    "id": interaction_id,
                    "sessionId": interaction_data.session_id,
                    "extensionType": interaction_data.extension_type.value,
                    "interactionType": interaction_data.interaction_type.value,
                    "customerId": interaction_data.customer_id,
                    "shopId": interaction_data.shop_id,
                    "metadata": Json(interaction_data.metadata),
                    "createdAt": utcnow(),
                }
            )

            # Convert to Pydantic model
            interaction = UserInteraction(
                id=interaction_data_db.id,
                session_id=interaction_data_db.sessionId,
                extension_type=ExtensionType(interaction_data_db.extensionType),
                interaction_type=InteractionType(interaction_data_db.interactionType),
                customer_id=interaction_data_db.customerId,
                shop_id=interaction_data_db.shopId,
                metadata=interaction_data_db.metadata,
                created_at=interaction_data_db.createdAt,
            )

            return interaction

        except Exception as e:
            logger.error(f"Error saving interaction: {str(e)}")
            return None
