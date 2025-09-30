"""
Feature repository for handling all database operations related to ML features
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import select, insert, update, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.core.database.session import get_session_context
from app.core.database.models import (
    ProductData,
    OrderData,
    LineItemData,
    CustomerData,
    CollectionData,
    Shop,
    UserInteraction,
    UserSession,
    PurchaseAttribution,
    ProductFeatures,
    UserFeatures,
    CollectionFeatures,
    InteractionFeatures,
    SessionFeatures,
    CustomerBehaviorFeatures,
    ProductPairFeatures,
    SearchProductFeatures,
)

logger = get_logger(__name__)


class IFeatureRepository(ABC):
    """Interface for feature repository operations"""

    @abstractmethod
    async def bulk_upsert_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product features"""
        pass

    @abstractmethod
    async def bulk_upsert_user_features(self, batch_data: List[Dict[str, Any]]) -> int:
        """Bulk upsert user features"""
        pass

    @abstractmethod
    async def bulk_upsert_collection_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert collection features"""
        pass

    @abstractmethod
    async def bulk_upsert_interaction_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert interaction features"""
        pass

    @abstractmethod
    async def bulk_upsert_session_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert session features"""
        pass

    @abstractmethod
    async def bulk_upsert_customer_behavior_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert customer behavior features"""
        pass

    @abstractmethod
    async def bulk_upsert_product_pair_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product pair features"""
        pass

    @abstractmethod
    async def bulk_upsert_search_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert search product features"""
        pass

    @abstractmethod
    async def get_products_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of products for a shop"""
        pass

    @abstractmethod
    async def get_orders_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders for a shop"""
        pass

    @abstractmethod
    async def get_customers_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers for a shop"""
        pass

    @abstractmethod
    async def get_collections_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections for a shop"""
        pass

    @abstractmethod
    async def get_events_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of events for a shop"""
        pass

    @abstractmethod
    async def get_last_feature_computation_time(self, shop_id: str) -> str:
        """Get the last feature computation timestamp for a shop"""
        pass

    @abstractmethod
    async def get_shop_data(self, shop_id: str) -> Dict[str, Any]:
        """Get shop data for processing"""
        pass

    @abstractmethod
    async def get_behavioral_events_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of behavioral events for a shop"""
        pass


class FeatureRepository(IFeatureRepository):
    """Repository for handling all feature-related database operations"""

    def __init__(self):
        pass

    async def _bulk_upsert_dict_generic(
        self,
        table_name: str,
        batch_data: List[Dict[str, Any]],
        unique_key_fields: List[str],
    ) -> int:
        """Generic bulk upsert method using SQLAlchemy"""
        try:
            if not batch_data:
                return 0

            # Map table names to SQLAlchemy models
            model_mapping = {
                "ProductFeatures": ProductFeatures,
                "UserFeatures": UserFeatures,
                "CollectionFeatures": CollectionFeatures,
                "InteractionFeatures": InteractionFeatures,
                "SessionFeatures": SessionFeatures,
                "CustomerBehaviorFeatures": CustomerBehaviorFeatures,
                "ProductPairFeatures": ProductPairFeatures,
                "SearchProductFeatures": SearchProductFeatures,
            }

            model_class = model_mapping.get(table_name)
            if not model_class:
                raise ValueError(f"No model mapping found for table: {table_name}")

            async with get_session_context() as session:
                # Prepare data for bulk upsert (ensure plain Python values only)
                def _coerce_plain(value):
                    # Convert SQLAlchemy/decimal/numpy and other non-plain types to plain Python
                    try:
                        from sqlalchemy.orm.attributes import InstrumentedAttribute
                        from sqlalchemy.sql.schema import Column
                        from sqlalchemy.sql.elements import ClauseElement
                    except Exception:
                        InstrumentedAttribute = tuple()
                        Column = tuple()
                        ClauseElement = tuple()

                    try:
                        import decimal
                    except Exception:
                        decimal = None

                    try:
                        import numpy as np
                    except Exception:
                        np = None

                    if isinstance(
                        value, (InstrumentedAttribute, Column, ClauseElement)
                    ):
                        return None
                    if decimal and isinstance(value, decimal.Decimal):
                        return float(value)
                    if np is not None:
                        if isinstance(value, (np.floating,)):
                            return float(value)
                        if isinstance(value, (np.integer,)):
                            return int(value)
                        if isinstance(value, (np.ndarray,)):
                            return value.tolist()
                    return value

                prepared_data = []
                for record in batch_data:
                    # Only keep keys that exist on the model table to avoid accidental Column refs
                    model_columns = {c.name for c in model_class.__table__.columns}
                    sanitized = {
                        k: _coerce_plain(v)
                        for k, v in record.items()
                        if k in model_columns
                    }
                    sanitized["last_computed_at"] = datetime.utcnow()
                    prepared_data.append(sanitized)

                # Use PostgreSQL's ON CONFLICT for efficient upsert
                stmt = pg_insert(model_class).values(prepared_data)

                # Define the update clause for conflict resolution (exclude immutable keys)
                update_dict = {
                    col.name: stmt.excluded[col.name]
                    for col in model_class.__table__.columns
                    if col.name not in ["id", "created_at"]
                }

                # Set unique constraint based on the unique key fields
                if len(unique_key_fields) == 1:
                    constraint_elements = unique_key_fields
                else:
                    constraint_elements = unique_key_fields

                stmt = stmt.on_conflict_do_update(
                    index_elements=constraint_elements, set_=update_dict
                )

                result = await session.execute(stmt)
                await session.commit()

                return len(prepared_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert {table_name}: {str(e)}")
            return 0

    async def bulk_upsert_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product features using SQLAlchemy"""
        if not batch_data:
            return 0

        try:
            async with get_session_context() as session:
                # Data is already in snake_case format
                prepared_data = []
                for record in batch_data:
                    record["last_computed_at"] = datetime.utcnow()
                    prepared_data.append(record)

                # Use PostgreSQL's ON CONFLICT for efficient upsert
                stmt = pg_insert(ProductFeatures).values(prepared_data)

                # Define the update clause for conflict resolution
                update_dict = {
                    col.name: stmt.excluded[col.name]
                    for col in ProductFeatures.__table__.columns
                    if col.name not in ["id", "shop_id", "product_id", "created_at"]
                }

                stmt = stmt.on_conflict_do_update(
                    index_elements=["shop_id", "product_id"], set_=update_dict
                )

                result = await session.execute(stmt)
                await session.commit()
                return len(prepared_data)

        except Exception as e:
            logger.error(
                f"Failed to bulk upsert product features: {str(e)}", exc_info=True
            )
            return 0

    async def bulk_upsert_user_features(self, batch_data: List[Dict[str, Any]]) -> int:
        """Bulk upsert user features using SQLAlchemy"""
        if not batch_data:
            return 0

        try:
            async with get_session_context() as session:
                # Data is already in snake_case format
                prepared_data = []
                for record in batch_data:
                    record["last_computed_at"] = datetime.utcnow()
                    prepared_data.append(record)

                # Use PostgreSQL's ON CONFLICT for efficient upsert
                stmt = pg_insert(UserFeatures).values(prepared_data)

                # Define the update clause for conflict resolution
                update_dict = {
                    col.name: stmt.excluded[col.name]
                    for col in UserFeatures.__table__.columns
                    if col.name not in ["id", "shop_id", "customer_id", "created_at"]
                }

                stmt = stmt.on_conflict_do_update(
                    index_elements=["shop_id", "customer_id"], set_=update_dict
                )

                result = await session.execute(stmt)
                await session.commit()

                return len(prepared_data)

        except Exception as e:
            logger.error(
                f"Failed to bulk upsert user features: {str(e)}", exc_info=True
            )
            return 0

    async def bulk_upsert_collection_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert collection features using SQLAlchemy"""
        if not batch_data:
            return 0

        try:
            async with get_session_context() as session:
                # Data is already in snake_case format
                prepared_data = []
                for record in batch_data:
                    record["last_computed_at"] = datetime.utcnow()
                    prepared_data.append(record)

                # Use PostgreSQL's ON CONFLICT for efficient upsert
                stmt = pg_insert(CollectionFeatures).values(prepared_data)

                # Define the update clause for conflict resolution
                update_dict = {
                    col.name: stmt.excluded[col.name]
                    for col in CollectionFeatures.__table__.columns
                    if col.name not in ["id", "shop_id", "collection_id", "created_at"]
                }

                stmt = stmt.on_conflict_do_update(
                    index_elements=["shop_id", "collection_id"], set_=update_dict
                )

                result = await session.execute(stmt)
                await session.commit()

                return len(prepared_data)

        except Exception as e:
            logger.error(
                f"Failed to bulk upsert collection features: {str(e)}", exc_info=True
            )
            return 0

    async def bulk_upsert_interaction_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert interaction features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="InteractionFeatures",
            batch_data=batch_data,
            unique_key_fields=["shop_id", "customer_id", "product_id"],
        )

    async def bulk_upsert_session_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert session features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="SessionFeatures",
            batch_data=batch_data,
            unique_key_fields=["shop_id", "session_id"],
        )

    async def bulk_upsert_customer_behavior_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert customer behavior features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="CustomerBehaviorFeatures",
            batch_data=batch_data,
            unique_key_fields=["shop_id", "customer_id"],
        )

    async def bulk_upsert_product_pair_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product pair features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="ProductPairFeatures",
            batch_data=batch_data,
            unique_key_fields=["shop_id", "product_id1", "product_id2"],
        )

    async def bulk_upsert_search_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert search product features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="SearchProductFeatures",
            batch_data=batch_data,
            unique_key_fields=["shop_id", "search_query", "product_id"],
        )

    async def get_products_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of products for a shop from main table using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(ProductData)
                    .where(ProductData.shop_id == shop_id)
                    .order_by(ProductData.id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                products = result.scalars().all()

                # Convert to dictionaries
                return [product.to_dict() for product in products]

        except Exception as e:
            logger.error(
                f"Failed to get products batch for shop {shop_id}: {str(e)}",
                exc_info=True,
            )
            return []

    async def get_orders_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders for a shop from main table using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(OrderData)
                    .where(OrderData.shop_id == shop_id)
                    .order_by(OrderData.id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                orders = result.scalars().all()

                # Convert to dictionaries and include line items
                orders_data = []
                for order in orders:
                    order_dict = order.to_dict()

                    # Get line items for this order
                    line_items_stmt = select(LineItemData).where(
                        LineItemData.order_id == order.id
                    )
                    line_items_result = await session.execute(line_items_stmt)
                    line_items = line_items_result.scalars().all()

                    order_dict["line_items"] = [
                        line_item.to_dict() for line_item in line_items
                    ]
                    orders_data.append(order_dict)

                return orders_data

        except Exception as e:
            logger.error(
                f"Failed to get orders batch for shop {shop_id}: {str(e)}",
                exc_info=True,
            )
            return []

    async def get_customers_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers for a shop from main table using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(CustomerData)
                    .where(CustomerData.shop_id == shop_id)
                    .order_by(CustomerData.id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                customers = result.scalars().all()

                # Convert to dictionaries
                return [customer.to_dict() for customer in customers]

        except Exception as e:
            logger.error(
                f"Failed to get customers batch for shop {shop_id}: {str(e)}",
                exc_info=True,
            )
            return []

    async def get_collections_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections for a shop from main table using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(CollectionData)
                    .where(CollectionData.shop_id == shop_id)
                    .order_by(CollectionData.id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                collections = result.scalars().all()

                # Convert to dictionaries
                return [collection.to_dict() for collection in collections]

        except Exception as e:
            logger.error(
                f"Failed to get collections batch for shop {shop_id}: {str(e)}",
                exc_info=True,
            )
            return []

    async def get_events_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of user interactions for a shop using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(UserInteraction)
                    .where(UserInteraction.shop_id == shop_id)
                    .order_by(UserInteraction.id)
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                interactions = result.scalars().all()

                # Convert to dictionaries
                return [interaction.to_dict() for interaction in interactions]

        except Exception as e:
            logger.error(
                f"Failed to get events batch for shop {shop_id}: {str(e)}",
                exc_info=True,
            )
            return []

    async def get_last_feature_computation_time(self, shop_id: str) -> str:
        """Get the last feature computation timestamp for a shop by checking feature tables using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                latest_timestamp = None

                # Get the most recent feature computation time from all feature tables
                feature_models = [
                    ProductFeatures,
                    CustomerBehaviorFeatures,
                    CollectionFeatures,
                    UserFeatures,
                    InteractionFeatures,
                    SessionFeatures,
                    ProductPairFeatures,
                    SearchProductFeatures,
                ]

                for model_class in feature_models:
                    try:
                        # Get the most recent record for this shop based on last_computed_at
                        stmt = (
                            select(model_class.last_computed_at)
                            .where(model_class.shop_id == shop_id)
                            .order_by(model_class.last_computed_at.desc())
                            .limit(1)
                        )
                        result = await session.execute(stmt)
                        record_timestamp = result.scalar()

                        if record_timestamp:
                            if (
                                latest_timestamp is None
                                or record_timestamp > latest_timestamp
                            ):
                                latest_timestamp = record_timestamp
                    except Exception as e:
                        logger.warning(
                            f"Could not check feature table {model_class.__tablename__}: {str(e)}"
                        )
                        continue

                if latest_timestamp:
                    return latest_timestamp.isoformat()

        except Exception as e:
            logger.error(
                f"Failed to get last computation time for shop {shop_id}: {str(e)}"
            )
            return "1970-01-01T00:00:00Z"

    async def get_shop_data(self, shop_id: str) -> Dict[str, Any]:
        """Get shop data for processing using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = select(Shop).where(Shop.id == shop_id)
                result = await session.execute(stmt)
                shop = result.scalar_one_or_none()
                return shop.to_dict() if shop else None
        except Exception as e:
            logger.error(f"Failed to get shop data for shop {shop_id}: {str(e)}")
            return None

    async def get_behavioral_events_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of behavioral events for a shop using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(UserInteraction)
                    .where(UserInteraction.shop_id == shop_id)
                    .order_by(UserInteraction.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                interactions = result.scalars().all()
                return [interaction.to_dict() for interaction in interactions]
        except Exception as e:
            logger.error(
                f"Failed to get behavioral events batch for shop {shop_id}: {str(e)}"
            )
            return []

    # Incremental data loading methods
    async def get_products_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get products modified since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(ProductData)
                    .where(
                        ProductData.shop_id == shop_id,
                        ProductData.updated_at > since_dt,
                    )
                    .order_by(ProductData.updated_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                products = result.scalars().all()
                return [product.to_dict() for product in products]
        except Exception as e:
            logger.error(
                f"Failed to get products batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_customers_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get customers modified since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(CustomerData)
                    .where(
                        CustomerData.shop_id == shop_id,
                        CustomerData.updated_at > since_dt,
                    )
                    .order_by(CustomerData.updated_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                customers = result.scalars().all()
                return [customer.to_dict() for customer in customers]
        except Exception as e:
            logger.error(
                f"Failed to get customers batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_orders_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get orders modified since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(OrderData)
                    .where(
                        OrderData.shop_id == shop_id,
                        OrderData.updated_at > since_dt,
                    )
                    .order_by(OrderData.updated_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                orders = result.scalars().all()

                # Convert to dictionaries and include line items
                orders_data = []
                for order in orders:
                    order_dict = order.to_dict()

                    # Get line items for this order
                    line_items_stmt = select(LineItemData).where(
                        LineItemData.order_id == order.id
                    )
                    line_items_result = await session.execute(line_items_stmt)
                    line_items = line_items_result.scalars().all()

                    order_dict["line_items"] = [
                        line_item.to_dict() for line_item in line_items
                    ]
                    orders_data.append(order_dict)

                return orders_data
        except Exception as e:
            logger.error(
                f"Failed to get orders batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_collections_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get collections modified since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(CollectionData)
                    .where(
                        CollectionData.shop_id == shop_id,
                        CollectionData.updated_at > since_dt,
                    )
                    .order_by(CollectionData.updated_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                collections = result.scalars().all()
                return [collection.to_dict() for collection in collections]
        except Exception as e:
            logger.error(
                f"Failed to get collections batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_behavioral_events_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get behavioral events since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(UserInteraction)
                    .where(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.created_at > since_dt,
                    )
                    .order_by(UserInteraction.created_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                interactions = result.scalars().all()
                return [interaction.to_dict() for interaction in interactions]
        except Exception as e:
            logger.error(
                f"Failed to get behavioral events batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    # Unified Analytics Data Loading Methods
    async def get_user_interactions_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of user interactions for a shop using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(UserInteraction)
                    .where(UserInteraction.shop_id == shop_id)
                    .order_by(UserInteraction.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                interactions = result.scalars().all()
                return [interaction.to_dict() for interaction in interactions]
        except Exception as e:
            logger.error(
                f"Failed to get user interactions batch for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_user_interactions_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user interactions since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(UserInteraction)
                    .where(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.created_at > since_dt,
                    )
                    .order_by(UserInteraction.created_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                interactions = result.scalars().all()
                return [interaction.to_dict() for interaction in interactions]
        except Exception as e:
            logger.error(
                f"Failed to get user interactions batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_user_sessions_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of user sessions for a shop using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(UserSession)
                    .where(UserSession.shop_id == shop_id)
                    .order_by(UserSession.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                sessions = result.scalars().all()
                return [session.to_dict() for session in sessions]
        except Exception as e:
            logger.error(
                f"Failed to get user sessions batch for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_user_sessions_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user sessions since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(UserSession)
                    .where(
                        UserSession.shop_id == shop_id,
                        UserSession.created_at > since_dt,
                    )
                    .order_by(UserSession.created_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                sessions = result.scalars().all()
                return [session.to_dict() for session in sessions]
        except Exception as e:
            logger.error(
                f"Failed to get user sessions batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_purchase_attributions_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of purchase attributions for a shop using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                stmt = (
                    select(PurchaseAttribution)
                    .where(PurchaseAttribution.shop_id == shop_id)
                    .order_by(PurchaseAttribution.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                attributions = result.scalars().all()
                return [attribution.to_dict() for attribution in attributions]
        except Exception as e:
            logger.error(
                f"Failed to get purchase attributions batch for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_purchase_attributions_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get purchase attributions since a specific timestamp for incremental processing using SQLAlchemy"""
        try:
            # Convert string timestamp to datetime object
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            async with get_session_context() as session:
                stmt = (
                    select(PurchaseAttribution)
                    .where(
                        PurchaseAttribution.shop_id == shop_id,
                        PurchaseAttribution.created_at > since_dt,
                    )
                    .order_by(PurchaseAttribution.created_at.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                attributions = result.scalars().all()
                return [attribution.to_dict() for attribution in attributions]
        except Exception as e:
            logger.error(
                f"Failed to get purchase attributions batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_feature_counts_for_shop(self, shop_id: str) -> Dict[str, int]:
        """Get counts of existing features for a shop to determine if incremental processing is needed using SQLAlchemy"""
        try:
            async with get_session_context() as session:
                counts = {}
                total_count = 0

                # Count features across all feature tables using SQLAlchemy
                feature_models = [
                    ("product_features", ProductFeatures),
                    ("user_features", UserFeatures),
                    ("collection_features", CollectionFeatures),
                    ("customer_behavior_features", CustomerBehaviorFeatures),
                    ("session_features", SessionFeatures),
                    ("interaction_features", InteractionFeatures),
                    ("product_pair_features", ProductPairFeatures),
                    ("search_product_features", SearchProductFeatures),
                ]

                for table_name, model_class in feature_models:
                    try:
                        stmt = select(func.count(model_class.id)).where(
                            model_class.shop_id == shop_id
                        )
                        result = await session.execute(stmt)
                        count = result.scalar() or 0
                        counts[table_name] = count
                        total_count += count
                    except Exception as e:
                        logger.warning(
                            f"Failed to count features in {table_name}: {str(e)}"
                        )
                        counts[table_name] = 0

                counts["total"] = total_count
                return counts

        except Exception as e:
            logger.error(f"Failed to get feature counts for shop {shop_id}: {str(e)}")
            return {"total": 0}
