"""
Feature models for SQLAlchemy

Represents computed features for machine learning and analytics.
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Integer,
    ForeignKey,
    Index,
    func,
)

from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin, CustomerMixin, ProductMixin


class UserFeatures(BaseModel, ShopMixin, CustomerMixin):
    """User features model for customer analytics"""

    __tablename__ = "user_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    total_purchases = Column(Integer, default=0, nullable=False)
    total_interactions = Column(Integer, default=0, nullable=False)
    lifetime_value = Column(Float, default=0, nullable=False)
    avg_order_value = Column(Float, default=0, nullable=False)
    purchase_frequency_score = Column(Float, default=0, nullable=False)
    interaction_diversity_score = Column(Float, default=0, nullable=False)
    days_since_last_purchase = Column(Integer, nullable=True)
    recency_score = Column(Float, default=0, nullable=False)
    conversion_rate = Column(Float, default=0, nullable=False)
    primary_category = Column(String(100), nullable=True)
    category_diversity = Column(Integer, default=0, nullable=False)
    user_lifecycle_stage = Column(String(100), nullable=True)
    churn_risk_score = Column(Float, default=1.0, nullable=False)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="user_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_user_features_shop_id_customer_id",
            "shop_id",
            "customer_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<UserFeatures(shop_id={self.shop_id}, customer_id={self.customer_id})>"


class ProductFeatures(BaseModel, ShopMixin, ProductMixin):
    """Product features model for product analytics"""

    __tablename__ = "product_features"

    interaction_volume_score = Column(Float, nullable=False)
    purchase_velocity_score = Column(Float, nullable=False)
    engagement_quality_score = Column(Float, nullable=False)
    price_tier = Column(String(20), nullable=False)
    revenue_potential_score = Column(Float, nullable=False)
    conversion_efficiency = Column(Float, nullable=False)
    days_since_last_purchase = Column(Integer, nullable=True)
    activity_recency_score = Column(Float, nullable=False)
    trending_momentum = Column(Float, nullable=False)
    product_lifecycle_stage = Column(String(100), nullable=False)
    inventory_health_score = Column(Float, nullable=False)
    product_category = Column(String(100), nullable=True)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="product_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_product_features_shop_id_product_id",
            "shop_id",
            "product_id",
            unique=True,
        ),
        Index(
            "ix_product_features_shop_id_interaction_volume_score",
            "shop_id",
            "interaction_volume_score",
        ),
        Index(
            "ix_product_features_shop_id_purchase_velocity_score",
            "shop_id",
            "purchase_velocity_score",
        ),
        Index(
            "ix_product_features_shop_id_engagement_quality_score",
            "shop_id",
            "engagement_quality_score",
        ),
        Index(
            "ix_product_features_shop_id_price_tier",
            "shop_id",
            "price_tier",
        ),
        Index(
            "ix_product_features_shop_id_revenue_potential_score",
            "shop_id",
            "revenue_potential_score",
        ),
        Index(
            "ix_product_features_shop_id_conversion_efficiency",
            "shop_id",
            "conversion_efficiency",
        ),
        Index(
            "ix_product_features_shop_id_activity_recency_score",
            "shop_id",
            "activity_recency_score",
        ),
        Index(
            "ix_product_features_shop_id_trending_momentum",
            "shop_id",
            "trending_momentum",
        ),
        Index(
            "ix_product_features_shop_id_product_lifecycle_stage",
            "shop_id",
            "product_lifecycle_stage",
        ),
        Index(
            "ix_product_features_shop_id_inventory_health_score",
            "shop_id",
            "inventory_health_score",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProductFeatures(shop_id={self.shop_id}, product_id={self.product_id})>"
        )


class CollectionFeatures(BaseModel, ShopMixin):
    """Collection features model for collection analytics"""

    __tablename__ = "collection_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Collection identification
    collection_id = Column(String, nullable=False)
    collection_engagement_score = Column(Float, nullable=False)
    collection_conversion_rate = Column(Float, nullable=False)
    collection_popularity_score = Column(Float, nullable=False)
    avg_product_value = Column(Float, nullable=True)
    collection_revenue_potential = Column(Float, nullable=False)
    product_diversity_score = Column(Float, nullable=False)
    collection_size_tier = Column(String(100), nullable=False)
    days_since_last_interaction = Column(Integer, nullable=True)
    collection_recency_score = Column(Float, nullable=False)
    is_curated_collection = Column(Boolean, nullable=False)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="collection_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_collection_features_shop_id_collection_id",
            "shop_id",
            "collection_id",
            unique=True,
        ),
        Index(
            "ix_collection_features_shop_id_collection_engagement_score",
            "shop_id",
            "collection_engagement_score",
        ),
        Index(
            "ix_collection_features_shop_id_collection_conversion_rate",
            "shop_id",
            "collection_conversion_rate",
        ),
        Index(
            "ix_collection_features_shop_id_collection_popularity_score",
            "shop_id",
            "collection_popularity_score",
        ),
    )

    def __repr__(self) -> str:
        return f"<CollectionFeatures(shop_id={self.shop_id}, collection_id={self.collection_id})>"


class InteractionFeatures(BaseModel, ShopMixin, CustomerMixin, ProductMixin):
    """Interaction features model for customer-product interactions"""

    __tablename__ = "interaction_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    interaction_strength_score = Column(Float, nullable=False)
    customer_product_affinity = Column(Float, nullable=False)
    engagement_progression_score = Column(Float, nullable=False)
    conversion_likelihood = Column(Float, nullable=False)
    purchase_intent_score = Column(Float, nullable=False)
    interaction_recency_score = Column(Float, nullable=False)
    relationship_maturity = Column(String(100), nullable=False)
    interaction_frequency_score = Column(Float, nullable=False)
    customer_product_loyalty = Column(Float, nullable=False)
    total_interaction_value = Column(Float, nullable=False)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="interaction_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_int_features_shop_cust_prod",
            "shop_id",
            "customer_id",
            "product_id",
            unique=True,
        ),
        Index(
            "ix_int_features_shop_cust_strength",
            "shop_id",
            "customer_id",
            "interaction_strength_score",
        ),
        Index(
            "ix_int_features_shop_cust_affinity",
            "shop_id",
            "customer_id",
            "customer_product_affinity",
        ),
        Index(
            "ix_int_features_shop_cust_engagement",
            "shop_id",
            "customer_id",
            "engagement_progression_score",
        ),
        Index(
            "ix_int_features_shop_cust_conv_likelihood",
            "shop_id",
            "customer_id",
            "conversion_likelihood",
        ),
        Index(
            "ix_int_features_shop_cust_intent",
            "shop_id",
            "customer_id",
            "purchase_intent_score",
        ),
        Index(
            "ix_int_features_shop_cust_recency",
            "shop_id",
            "customer_id",
            "interaction_recency_score",
        ),
        Index(
            "ix_int_features_shop_cust_maturity",
            "shop_id",
            "customer_id",
            "relationship_maturity",
        ),
        Index(
            "ix_int_features_shop_cust_frequency",
            "shop_id",
            "customer_id",
            "interaction_frequency_score",
        ),
    )

    def __repr__(self) -> str:
        return f"<InteractionFeatures(shop_id={self.shop_id}, customer_id={self.customer_id}, product_id={self.product_id})>"


class SessionFeatures(BaseModel, ShopMixin, CustomerMixin):
    """Session features model for session analytics"""

    __tablename__ = "session_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Session identification
    session_id = Column(String, nullable=False, unique=True, index=True)
    session_duration_minutes = Column(Integer, nullable=False)
    interaction_count = Column(Integer, nullable=False)
    interaction_intensity = Column(Float, nullable=False)
    unique_products_viewed = Column(Integer, nullable=False)
    browse_depth_score = Column(Float, nullable=False)
    conversion_funnel_stage = Column(String(100), nullable=False)
    purchase_intent_score = Column(Float, nullable=False)
    session_value = Column(Float, nullable=False)
    session_type = Column(String(100), nullable=False)
    bounce_session = Column(Boolean, nullable=False)
    traffic_source = Column(String(100), nullable=False)
    returning_visitor = Column(Boolean, nullable=False)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="session_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_session_features_shop_id_session_id",
            "shop_id",
            "session_id",
            unique=True,
        ),
        Index("ix_session_features_shop_cust", "shop_id", "customer_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SessionFeatures(shop_id={self.shop_id}, session_id={self.session_id})>"
        )


class ProductPairFeatures(BaseModel, ShopMixin, ProductMixin):
    """Product pair features model for product co-occurrence analytics"""

    __tablename__ = "product_pair_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Product pair identification
    product_id1 = Column(String, nullable=False, index=True)
    product_id2 = Column(String, nullable=False, index=True)
    co_purchase_strength = Column(Float, nullable=False)
    co_engagement_score = Column(Float, nullable=False)
    pair_affinity_score = Column(Float, nullable=False)
    total_pair_revenue = Column(Float, nullable=False)
    pair_frequency_score = Column(Float, nullable=False)
    days_since_last_co_occurrence = Column(Integer, nullable=True)
    pair_recency_score = Column(Float, nullable=False)
    pair_confidence_level = Column(String(100), nullable=False)
    cross_sell_potential = Column(Float, nullable=False)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="product_pair_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_pp_features_shop_p1_p2",
            "shop_id",
            "product_id1",
            "product_id2",
            unique=True,
        ),
        Index("ix_pp_features_shop_p1", "shop_id", "product_id1"),
        Index("ix_pp_features_shop_p2", "shop_id", "product_id2"),
        Index(
            "ix_pp_features_shop_co_purchase",
            "shop_id",
            "co_purchase_strength",
        ),
        Index(
            "ix_pp_features_shop_p1_co_purchase",
            "shop_id",
            "product_id1",
            "co_purchase_strength",
        ),
        Index(
            "ix_pp_features_shop_p2_co_purchase",
            "shop_id",
            "product_id2",
            "co_purchase_strength",
        ),
        Index(
            "ix_pp_features_shop_affinity",
            "shop_id",
            "pair_affinity_score",
        ),
        Index(
            "ix_pp_features_shop_revenue",
            "shop_id",
            "total_pair_revenue",
        ),
        Index(
            "ix_pp_features_shop_frequency",
            "shop_id",
            "pair_frequency_score",
        ),
        Index(
            "ix_pp_features_shop_days_co_occur",
            "shop_id",
            "days_since_last_co_occurrence",
        ),
        Index(
            "ix_pp_features_shop_recency",
            "shop_id",
            "pair_recency_score",
        ),
        Index(
            "ix_pp_features_shop_confidence",
            "shop_id",
            "pair_confidence_level",
        ),
        Index(
            "ix_pp_features_shop_cross_sell",
            "shop_id",
            "cross_sell_potential",
        ),
    )

    def __repr__(self) -> str:
        return f"<ProductPairFeatures(shop_id={self.shop_id}, product_id1={self.product_id1}, product_id2={self.product_id2})>"


class SearchProductFeatures(BaseModel, ShopMixin, ProductMixin):
    """Search product features model for search analytics"""

    __tablename__ = "search_product_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Search identification
    search_query = Column(String(500), nullable=False, index=True)
    search_click_rate = Column(Float, nullable=False)
    search_conversion_rate = Column(Float, nullable=False)
    search_relevance_score = Column(Float, nullable=False)
    total_search_interactions = Column(Integer, default=0, nullable=False)
    search_to_purchase_count = Column(Integer, default=0, nullable=False)
    days_since_last_search_interaction = Column(Integer, nullable=True)
    search_recency_score = Column(Float, nullable=False)
    semantic_match_score = Column(Float, nullable=False)
    search_intent_alignment = Column(String(100), nullable=False)

    # Computation tracking
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="search_product_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_sp_features_shop_query_prod",
            "shop_id",
            "search_query",
            "product_id",
            unique=True,
        ),
        Index("ix_sp_features_shop_query", "shop_id", "search_query"),
        Index("ix_sp_features_shop_prod", "shop_id", "product_id"),
        Index(
            "ix_sp_features_shop_click_rate",
            "shop_id",
            "search_click_rate",
        ),
        Index(
            "ix_sp_features_shop_query_click",
            "shop_id",
            "search_query",
            "search_click_rate",
        ),
    )

    def __repr__(self) -> str:
        return f"<SearchProductFeatures(shop_id={self.shop_id}, search_query={self.search_query}, product_id={self.product_id})>"


class CustomerBehaviorFeatures(BaseModel, ShopMixin, CustomerMixin):
    """Customer behavior features model for behavioral analytics"""

    __tablename__ = "customer_behavior_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    user_lifecycle_stage = Column(String(100), nullable=True)
    purchase_frequency_score = Column(Float, default=0, nullable=False)
    interaction_diversity_score = Column(Float, default=0, nullable=False)
    category_diversity = Column(Integer, default=0, nullable=False)
    primary_category = Column(String(100), nullable=True)
    conversion_rate = Column(Float, default=0, nullable=False)
    avg_order_value = Column(Float, default=0, nullable=False)
    lifetime_value = Column(Float, default=0, nullable=False)
    recency_score = Column(Float, default=0, nullable=False)
    churn_risk_score = Column(Float, default=1.0, nullable=False)
    total_interactions = Column(Integer, default=0, nullable=False)
    days_since_last_purchase = Column(Integer, nullable=True)
    last_computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )

    # Relationships
    shop = relationship("Shop", back_populates="customer_behavior_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_cb_features_shop_cust",
            "shop_id",
            "customer_id",
            unique=True,
        ),
        Index(
            "ix_cb_features_shop_user_lifecycle_stage",
            "shop_id",
            "user_lifecycle_stage",
        ),
        Index(
            "ix_cb_features_shop_purchase_frequency_score",
            "shop_id",
            "purchase_frequency_score",
        ),
        Index(
            "ix_cb_features_shop_interaction_diversity_score",
            "shop_id",
            "interaction_diversity_score",
        ),
        Index(
            "ix_cb_features_shop_category_diversity", "shop_id", "category_diversity"
        ),
        Index("ix_cb_features_shop_primary_category", "shop_id", "primary_category"),
        Index("ix_cb_features_shop_conversion_rate", "shop_id", "conversion_rate"),
        Index("ix_cb_features_shop_avg_order_value", "shop_id", "avg_order_value"),
        Index("ix_cb_features_shop_lifetime_value", "shop_id", "lifetime_value"),
        Index("ix_cb_features_shop_recency_score", "shop_id", "recency_score"),
        Index("ix_cb_features_shop_churn_risk_score", "shop_id", "churn_risk_score"),
        Index(
            "ix_cb_features_shop_total_interactions", "shop_id", "total_interactions"
        ),
        Index(
            "ix_cb_features_shop_days_since_last_purchase",
            "shop_id",
            "days_since_last_purchase",
        ),
    )

    def __repr__(self) -> str:
        return f"<CustomerBehaviorFeatures(shop_id={self.shop_id}, customer_id={self.customer_id})>"
