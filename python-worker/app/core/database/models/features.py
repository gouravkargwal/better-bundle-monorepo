"""
Feature models for SQLAlchemy

Represents computed features for machine learning and analytics.
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
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

    # Customer metrics
    total_purchases = Column(Integer, default=0, nullable=False)
    total_spent = Column(Float, default=0, nullable=False, index=True)
    avg_order_value = Column(Float, default=0, nullable=False)
    lifetime_value = Column(Float, default=0, nullable=False)

    # Temporal features
    days_since_first_order = Column(Integer, nullable=True)
    days_since_last_order = Column(Integer, nullable=True, index=True)
    avg_days_between_orders = Column(Float, nullable=True)
    order_frequency_per_month = Column(Float, nullable=True)

    # Product diversity
    distinct_products_purchased = Column(Integer, default=0, nullable=False)
    distinct_categories_purchased = Column(Integer, default=0, nullable=False)
    preferred_category = Column(String(100), nullable=True)
    preferred_vendor = Column(String(255), nullable=True)
    price_point_preference = Column(String(20), nullable=True)

    # Discount behavior
    orders_with_discount_count = Column(Integer, default=0, nullable=False)
    discount_sensitivity = Column(Float, nullable=True)
    avg_discount_amount = Column(Float, nullable=True)

    # Customer attributes
    customer_state = Column(String(50), nullable=True, index=True)
    is_verified_email = Column(Boolean, default=False, nullable=False, index=True)
    customer_age = Column(Integer, nullable=True)
    has_default_address = Column(Boolean, default=False, nullable=False)
    geographic_region = Column(String(100), nullable=True)
    currency_preference = Column(String(10), nullable=True)

    # Health and risk scores
    customer_health_score = Column(Integer, default=0, nullable=False)
    refunded_orders = Column(Integer, default=0, nullable=False)
    refund_rate = Column(Float, default=0.0, nullable=False, index=True)
    total_refunded_amount = Column(Float, default=0.0, nullable=False)
    net_lifetime_value = Column(Float, default=0.0, nullable=False, index=True)

    # Customer demographic data
    customer_email = Column(String(255), nullable=True)
    customer_first_name = Column(String(100), nullable=True)
    customer_last_name = Column(String(100), nullable=True)
    customer_location = Column(JSON, default={}, nullable=True)
    customer_tags = Column(JSON, default=[], nullable=True)
    customer_created_at_shopify = Column(DateTime, nullable=True)
    customer_last_order_id = Column(String(100), nullable=True)
    customer_metafields = Column(JSON, default=[], nullable=True)
    customer_verified_email = Column(Boolean, default=False, nullable=False)
    customer_tax_exempt = Column(Boolean, default=False, nullable=False)
    customer_default_address = Column(JSON, default={}, nullable=True)
    customer_addresses = Column(JSON, default=[], nullable=True)
    customer_currency_code = Column(String(10), nullable=True)
    customer_locale = Column(String(10), nullable=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

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
        Index("ix_user_features_shop_id_total_spent", "shop_id", "total_spent"),
        Index(
            "ix_user_features_shop_id_days_since_last_order",
            "shop_id",
            "days_since_last_order",
        ),
        Index("ix_user_features_shop_id_refund_rate", "shop_id", "refund_rate"),
        Index(
            "ix_user_features_shop_id_net_lifetime_value",
            "shop_id",
            "net_lifetime_value",
        ),
        Index(
            "ix_user_features_shop_id_lifetime_value_days_since_last_order",
            "shop_id",
            "lifetime_value",
            "days_since_last_order",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserFeatures(shop_id={self.shop_id}, customer_id={self.customer_id})>"


class ProductFeatures(BaseModel, ShopMixin, ProductMixin):
    """Product features model for product analytics"""

    __tablename__ = "product_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Engagement metrics (30-day)
    view_count_30d = Column(Integer, default=0, nullable=False)
    unique_viewers_30d = Column(Integer, default=0, nullable=False)
    cart_add_count_30d = Column(Integer, default=0, nullable=False)
    cart_view_count_30d = Column(Integer, default=0, nullable=False)
    cart_remove_count_30d = Column(Integer, default=0, nullable=False)
    purchase_count_30d = Column(Integer, default=0, nullable=False)
    unique_purchasers_30d = Column(Integer, default=0, nullable=False)

    # Conversion rates
    view_to_cart_rate = Column(Float, nullable=True)
    cart_to_purchase_rate = Column(Float, nullable=True)
    overall_conversion_rate = Column(Float, nullable=True)
    cart_abandonment_rate = Column(Float, nullable=True)
    cart_modification_rate = Column(Float, nullable=True)
    cart_view_to_purchase_rate = Column(Float, nullable=True)

    # Temporal features
    last_viewed_at = Column(DateTime, nullable=True)
    last_purchased_at = Column(DateTime, nullable=True)
    first_purchased_at = Column(DateTime, nullable=True)
    days_since_first_purchase = Column(Integer, nullable=True)
    days_since_last_purchase = Column(Integer, nullable=True)

    # Pricing features
    avg_selling_price = Column(Float, nullable=True)
    price_variance = Column(Float, nullable=True)
    total_inventory = Column(Integer, nullable=True)
    inventory_turnover = Column(Float, nullable=True)
    stock_velocity = Column(Float, nullable=True)
    price_tier = Column(String(20), nullable=True)

    # Content features
    variant_complexity = Column(Float, nullable=True)
    image_richness = Column(Float, nullable=True)
    tag_diversity = Column(Float, nullable=True)
    metafield_utilization = Column(Float, nullable=True)
    media_richness = Column(Float, nullable=True)
    seo_optimization = Column(Float, nullable=True)
    seo_title_length = Column(Integer, nullable=True)
    seo_description_length = Column(Integer, nullable=True)

    # Media features
    has_video_content = Column(Boolean, default=False, nullable=False)
    has_3d_content = Column(Boolean, default=False, nullable=False)
    media_count = Column(Integer, default=0, nullable=False)
    has_online_store_url = Column(Boolean, default=False, nullable=False)
    has_preview_url = Column(Boolean, default=False, nullable=False)
    has_custom_template = Column(Boolean, default=False, nullable=False)

    # Performance scores
    popularity_score = Column(Float, default=0, nullable=False, index=True)
    trending_score = Column(Float, default=0, nullable=False, index=True)

    # Refund metrics
    refunded_orders = Column(Integer, default=0, nullable=False)
    refund_rate = Column(Float, default=0.0, nullable=False, index=True)
    total_refunded_amount = Column(Float, default=0.0, nullable=False)
    net_revenue = Column(Float, default=0.0, nullable=False, index=True)
    refund_risk_score = Column(Float, default=0.0, nullable=False, index=True)

    # Enhanced content features
    content_richness_score = Column(Integer, default=0, nullable=False)
    description_length = Column(Integer, default=0, nullable=False)
    description_html_length = Column(Integer, default=0, nullable=False)
    product_age = Column(Integer, nullable=True)
    last_updated_days = Column(Integer, nullable=True)
    update_frequency = Column(Float, nullable=True)
    product_type = Column(String(100), nullable=True)
    category_complexity = Column(Float, nullable=True)
    availability_score = Column(Float, nullable=True)
    status_stability = Column(Float, nullable=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

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
            "ix_product_features_shop_id_popularity_score",
            "shop_id",
            "popularity_score",
        ),
        Index(
            "ix_product_features_shop_id_trending_score", "shop_id", "trending_score"
        ),
        Index(
            "ix_product_features_shop_id_view_count_30d", "shop_id", "view_count_30d"
        ),
        Index(
            "ix_product_features_shop_id_purchase_count_30d",
            "shop_id",
            "purchase_count_30d",
        ),
        Index("ix_product_features_shop_id_refund_rate", "shop_id", "refund_rate"),
        Index(
            "ix_product_features_shop_id_refund_risk_score",
            "shop_id",
            "refund_risk_score",
        ),
        Index("ix_product_features_shop_id_net_revenue", "shop_id", "net_revenue"),
        Index(
            "ix_product_features_shop_id_popularity_trending",
            "shop_id",
            "popularity_score",
            "trending_score",
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

    # Basic metrics
    product_count = Column(Integer, default=0, nullable=False, index=True)
    is_automated = Column(Boolean, default=False, nullable=False)

    # Engagement metrics
    view_count_30d = Column(Integer, default=0, nullable=False)
    unique_viewers_30d = Column(Integer, default=0, nullable=False)

    # Performance metrics
    click_through_rate = Column(Float, nullable=True)
    bounce_rate = Column(Float, nullable=True)
    avg_product_price = Column(Float, nullable=True)
    min_product_price = Column(Float, nullable=True)
    max_product_price = Column(Float, nullable=True)
    price_range = Column(Float, nullable=True)
    price_variance = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    revenue_contribution = Column(Float, nullable=True)

    # Top performers
    top_products = Column(JSON, default=[], nullable=False)
    top_vendors = Column(JSON, default=[], nullable=False)

    # Scores
    performance_score = Column(Float, default=0, nullable=False, index=True)
    seo_score = Column(Integer, default=0, nullable=False)
    image_score = Column(Integer, default=0, nullable=False)

    # Enhanced features
    handle_quality = Column(Float, nullable=True)
    template_score = Column(Integer, default=0, nullable=False)
    seo_optimization_score = Column(Float, nullable=True)
    collection_age = Column(Integer, nullable=True)
    update_frequency = Column(Float, nullable=True)
    lifecycle_stage = Column(String(50), nullable=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

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
            "ix_collection_features_shop_id_product_count", "shop_id", "product_count"
        ),
        Index(
            "ix_collection_features_shop_id_performance_score",
            "shop_id",
            "performance_score",
        ),
        Index(
            "ix_collection_features_shop_id_view_count_30d_performance",
            "shop_id",
            "view_count_30d",
            "performance_score",
        ),
    )

    def __repr__(self) -> str:
        return f"<CollectionFeatures(shop_id={self.shop_id}, collection_id={self.collection_id})>"


class InteractionFeatures(BaseModel, ShopMixin, CustomerMixin, ProductMixin):
    """Interaction features model for customer-product interactions"""

    __tablename__ = "interaction_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Interaction counts
    view_count = Column(Integer, default=0, nullable=False)
    cart_add_count = Column(Integer, default=0, nullable=False)
    cart_view_count = Column(Integer, default=0, nullable=False)
    cart_remove_count = Column(Integer, default=0, nullable=False)
    purchase_count = Column(Integer, default=0, nullable=False)

    # Temporal features
    first_view_date = Column(DateTime, nullable=True)
    last_view_date = Column(DateTime, nullable=True)
    first_purchase_date = Column(DateTime, nullable=True)
    last_purchase_date = Column(DateTime, nullable=True)
    view_to_purchase_days = Column(Integer, nullable=True)
    interaction_span_days = Column(Integer, nullable=True)

    # Scores
    interaction_score = Column(Float, default=0, nullable=False, index=True)
    affinity_score = Column(Float, nullable=True)

    # Refund metrics
    refunded_purchases = Column(Integer, default=0, nullable=False)
    refund_rate = Column(Float, default=0.0, nullable=False, index=True)
    total_refunded_amount = Column(Float, default=0.0, nullable=False)
    net_purchase_value = Column(Float, default=0.0, nullable=False, index=True)
    refund_risk_score = Column(Float, default=0.0, nullable=False, index=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    shop = relationship("Shop", back_populates="interaction_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_interaction_features_shop_id_customer_id_product_id",
            "shop_id",
            "customer_id",
            "product_id",
            unique=True,
        ),
        Index("ix_interaction_features_shop_id_customer_id", "shop_id", "customer_id"),
        Index("ix_interaction_features_shop_id_product_id", "shop_id", "product_id"),
        Index(
            "ix_interaction_features_shop_id_interaction_score",
            "shop_id",
            "interaction_score",
        ),
        Index("ix_interaction_features_shop_id_refund_rate", "shop_id", "refund_rate"),
        Index(
            "ix_interaction_features_shop_id_refund_risk_score",
            "shop_id",
            "refund_risk_score",
        ),
        Index(
            "ix_interaction_features_shop_id_net_purchase_value",
            "shop_id",
            "net_purchase_value",
        ),
        Index(
            "ix_interaction_features_shop_id_customer_id_interaction_score",
            "shop_id",
            "customer_id",
            "interaction_score",
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
    session_id = Column(String, nullable=False, unique=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    duration_seconds = Column(Integer, nullable=False)

    # Event counts
    event_count = Column(Integer, default=0, nullable=False)
    page_view_count = Column(Integer, default=0, nullable=False)
    product_view_count = Column(Integer, default=0, nullable=False)
    collection_view_count = Column(Integer, default=0, nullable=False)
    search_count = Column(Integer, default=0, nullable=False)
    cart_add_count = Column(Integer, default=0, nullable=False)
    cart_view_count = Column(Integer, default=0, nullable=False)
    cart_remove_count = Column(Integer, default=0, nullable=False)

    # Conversion tracking
    checkout_started = Column(Boolean, default=False, nullable=False)
    checkout_completed = Column(Boolean, default=False, nullable=False, index=True)
    order_value = Column(Float, nullable=True)
    cart_viewed = Column(Boolean, default=False, nullable=False)
    cart_abandoned = Column(Boolean, default=False, nullable=False)

    # Device and referrer information
    device_type = Column(String(20), nullable=True)
    referrer_domain = Column(String(255), nullable=True)
    landing_page = Column(String(500), nullable=True)
    exit_page = Column(String(500), nullable=True)

    # Enhanced device and location features
    browser_type = Column(String(50), nullable=True)
    os_type = Column(String(50), nullable=True)
    screen_resolution = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    referrer_type = Column(String(50), nullable=True)
    traffic_source = Column(String(50), nullable=True)
    device_consistency = Column(Float, nullable=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

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
        Index("ix_session_features_shop_id_customer_id", "shop_id", "customer_id"),
        Index("ix_session_features_shop_id_start_time", "shop_id", "start_time"),
        Index(
            "ix_session_features_shop_id_checkout_completed",
            "shop_id",
            "checkout_completed",
        ),
        Index(
            "ix_session_features_shop_id_start_time_checkout_completed",
            "shop_id",
            "start_time",
            "checkout_completed",
        ),
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

    # Co-occurrence metrics
    co_purchase_count = Column(Integer, default=0, nullable=False, index=True)
    co_view_count = Column(Integer, default=0, nullable=False)
    co_cart_count = Column(Integer, default=0, nullable=False)
    co_cart_views = Column(Integer, default=0, nullable=False)
    co_cart_removes = Column(Integer, default=0, nullable=False)

    # Association metrics
    support_score = Column(Float, nullable=True)
    lift_score = Column(Float, nullable=True)
    last_co_occurrence = Column(DateTime, nullable=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    shop = relationship("Shop", back_populates="product_pair_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_product_pair_features_shop_id_product_id1_product_id2",
            "shop_id",
            "product_id1",
            "product_id2",
            unique=True,
        ),
        Index("ix_product_pair_features_shop_id_product_id1", "shop_id", "product_id1"),
        Index("ix_product_pair_features_shop_id_product_id2", "shop_id", "product_id2"),
        Index(
            "ix_product_pair_features_shop_id_co_purchase_count",
            "shop_id",
            "co_purchase_count",
        ),
        Index(
            "ix_product_pair_features_shop_id_product_id1_co_purchase_count",
            "shop_id",
            "product_id1",
            "co_purchase_count",
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

    # Search metrics
    impression_count = Column(Integer, default=0, nullable=False)
    click_count = Column(Integer, default=0, nullable=False)
    purchase_count = Column(Integer, default=0, nullable=False)
    avg_position = Column(Float, nullable=True)

    # Performance metrics
    click_through_rate = Column(Float, nullable=True, index=True)
    conversion_rate = Column(Float, nullable=True)
    last_occurrence = Column(DateTime, nullable=True)

    # Computation tracking
    last_computed_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    shop = relationship("Shop", back_populates="search_product_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_search_product_features_shop_id_search_query_product_id",
            "shop_id",
            "search_query",
            "product_id",
            unique=True,
        ),
        Index(
            "ix_search_product_features_shop_id_search_query", "shop_id", "search_query"
        ),
        Index("ix_search_product_features_shop_id_product_id", "shop_id", "product_id"),
        Index(
            "ix_search_product_features_shop_id_click_through_rate",
            "shop_id",
            "click_through_rate",
        ),
        Index(
            "ix_search_product_features_shop_id_search_query_ctr",
            "shop_id",
            "search_query",
            "click_through_rate",
        ),
    )

    def __repr__(self) -> str:
        return f"<SearchProductFeatures(shop_id={self.shop_id}, search_query={self.search_query}, product_id={self.product_id})>"


class CustomerBehaviorFeatures(BaseModel, ShopMixin, CustomerMixin):
    """Customer behavior features model for behavioral analytics"""

    __tablename__ = "customer_behavior_features"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Session metrics
    session_count = Column(Integer, default=0, nullable=False)
    avg_events_per_session = Column(Float, nullable=True)
    total_event_count = Column(Integer, default=0, nullable=False)

    # Event type counts
    product_view_count = Column(Integer, default=0, nullable=False)
    collection_view_count = Column(Integer, default=0, nullable=False)
    cart_add_count = Column(Integer, default=0, nullable=False)
    cart_view_count = Column(Integer, default=0, nullable=False)
    cart_remove_count = Column(Integer, default=0, nullable=False)
    search_count = Column(Integer, default=0, nullable=False)
    checkout_start_count = Column(Integer, default=0, nullable=False)
    purchase_count = Column(Integer, default=0, nullable=False)

    # Temporal features
    days_since_first_event = Column(Integer, default=0, nullable=False)
    days_since_last_event = Column(Integer, default=0, nullable=False, index=True)
    most_active_hour = Column(Integer, nullable=True)
    most_active_day = Column(Integer, nullable=True)

    # Diversity metrics
    unique_products_viewed = Column(Integer, default=0, nullable=False)
    unique_collections_viewed = Column(Integer, default=0, nullable=False)
    search_terms = Column(JSON, default=[], nullable=False)
    top_categories = Column(JSON, default=[], nullable=False)

    # Device and referrer information
    device_type = Column(String(20), nullable=True)
    primary_referrer = Column(String(255), nullable=True)

    # Conversion rates
    browse_to_cart_rate = Column(Float, nullable=True)
    cart_to_purchase_rate = Column(Float, nullable=True)
    search_to_purchase_rate = Column(Float, nullable=True)

    # Behavioral scores
    engagement_score = Column(Float, default=0, nullable=False, index=True)
    recency_score = Column(Float, default=0, nullable=False)
    diversity_score = Column(Float, default=0, nullable=False)
    behavioral_score = Column(Float, default=0, nullable=False, index=True)

    # Session analytics
    total_unified_sessions = Column(Integer, default=0, nullable=False, index=True)
    cross_session_span_days = Column(Integer, default=0, nullable=False)
    session_frequency_score = Column(Float, default=0, nullable=False)
    device_diversity = Column(Integer, default=0, nullable=False)
    avg_session_duration = Column(Float, nullable=True)

    # Extension engagement
    phoenix_interaction_count = Column(Integer, default=0, nullable=False)
    apollo_interaction_count = Column(Integer, default=0, nullable=False)
    venus_interaction_count = Column(Integer, default=0, nullable=False)
    atlas_interaction_count = Column(Integer, default=0, nullable=False)
    extension_engagement_score = Column(Float, default=0, nullable=False, index=True)

    # Recommendation and upsell metrics
    recommendation_click_rate = Column(Float, default=0, nullable=False)
    upsell_interaction_count = Column(Integer, default=0, nullable=False)
    total_interactions_in_sessions = Column(Integer, default=0, nullable=False)
    avg_interactions_per_session = Column(Float, default=0, nullable=False)
    session_engagement_score = Column(Float, default=0, nullable=False)

    # Attribution analytics
    multi_touch_attribution_score = Column(Float, default=0, nullable=False, index=True)
    attribution_revenue = Column(Float, default=0, nullable=False)
    conversion_path_length = Column(Integer, default=0, nullable=False)

    # Enhanced device and location features
    browser_type = Column(String(50), nullable=True)
    os_type = Column(String(50), nullable=True)
    screen_resolution = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    referrer_type = Column(String(50), nullable=True)
    traffic_source = Column(String(50), nullable=True)
    device_consistency = Column(Float, nullable=True)

    # Computation tracking
    last_computed_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=func.now()
    )

    # Relationships
    shop = relationship("Shop", back_populates="customer_behavior_features")

    # Indexes
    __table_args__ = (
        Index(
            "ix_customer_behavior_features_shop_id_customer_id",
            "shop_id",
            "customer_id",
            unique=True,
        ),
        Index(
            "ix_customer_behavior_features_shop_id_engagement_score",
            "shop_id",
            "engagement_score",
        ),
        Index(
            "ix_customer_behavior_features_shop_id_behavioral_score",
            "shop_id",
            "behavioral_score",
        ),
        Index(
            "ix_customer_behavior_features_shop_id_days_since_last_event",
            "shop_id",
            "days_since_last_event",
        ),
        Index(
            "ix_customer_behavior_features_shop_id_total_unified_sessions",
            "shop_id",
            "total_unified_sessions",
        ),
        Index(
            "ix_customer_behavior_features_shop_id_ext_engagement",
            "shop_id",
            "extension_engagement_score",
        ),
        Index(
            "ix_customer_behavior_features_shop_id_multi_touch_attr",
            "shop_id",
            "multi_touch_attribution_score",
        ),
        Index(
            "ix_customer_behavior_features_shop_id_engagement_behavioral",
            "shop_id",
            "engagement_score",
            "behavioral_score",
        ),
    )

    def __repr__(self) -> str:
        return f"<CustomerBehaviorFeatures(shop_id={self.shop_id}, customer_id={self.customer_id})>"
