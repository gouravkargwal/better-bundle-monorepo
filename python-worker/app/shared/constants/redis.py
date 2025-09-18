"""
Redis-specific constants
"""

# Redis Stream Names - Organized by Domain
# ===========================================
# Data Collection Streams
DATA_COLLECTION_STREAM = "betterbundle:data-collection-jobs"

# Normalization Streams
NORMALIZATION_STREAM = "betterbundle:normalization-jobs"

# Attribution Streams
PURCHASE_ATTRIBUTION_STREAM = "betterbundle:purchase-attribution-jobs"
REFUND_ATTRIBUTION_STREAM = "betterbundle:refund-attribution-jobs"

# Refund Processing Streams
REFUND_NORMALIZATION_STREAM = "betterbundle:refund-normalization-jobs"

# Shopify Events Stream
SHOPIFY_EVENTS_STREAM = "betterbundle:shopify-events"

# Legacy Streams - REMOVED (use specific streams above)

# ML and Analytics Streams
ML_TRAINING_STREAM = "betterbundle:ml-training"
ANALYSIS_RESULTS_STREAM = "betterbundle:analysis-results"
USER_NOTIFICATIONS_STREAM = "betterbundle:user-notifications"
FEATURES_COMPUTED_STREAM = "betterbundle:features-computed"
ML_TRAINING_COMPLETE_STREAM = "betterbundle:ml-training-complete"
HEURISTIC_DECISION_REQUESTED_STREAM = "betterbundle:heuristic-decision-requested"
HEURISTIC_DECISION_MADE_STREAM = "betterbundle:heuristic-decision-made"
HEURISTIC_DECISION_STREAM = "betterbundle:heuristic-decision-requested"
NEXT_ANALYSIS_SCHEDULED_STREAM = "betterbundle:next-analysis-scheduled"
COMPLETION_RESULTS_STREAM = "betterbundle:completion-results"
COMPLETION_EVENTS_STREAM = "betterbundle:ml-training-complete"
BEHAVIORAL_EVENTS_STREAM = "betterbundle:behavioral-events"
GORSE_SYNC_STREAM = "betterbundle:gorse-sync"
CUSTOMER_LINKING_STREAM = "betterbundle:customer-linking"

# Consumer Group Names - Organized by Domain
# ===========================================
# Data Collection Groups
DATA_COLLECTION_GROUP = "data-collection-processors"

# Normalization Groups
NORMALIZATION_GROUP = "normalization-processors"

# Attribution Groups
PURCHASE_ATTRIBUTION_GROUP = "purchase-attribution-processors"
REFUND_ATTRIBUTION_GROUP = "refund-attribution-processors"

# Refund Processing Groups
REFUND_NORMALIZATION_GROUP = "refund-normalization-processors"

# Shopify Events Groups
SHOPIFY_EVENTS_GROUP = "shopify-events-processors"

# Legacy Groups - REMOVED (use specific groups above)
MAIN_TABLE_PROCESSOR_GROUP = "main-table-processors"

# ML and Analytics Groups
ML_TRAINING_GROUP = "ml-training-consumers"
FEATURES_CONSUMER_GROUP = "features-consumers"
HEURISTIC_DECISION_GROUP = "heuristic-decision-processors"
COMPLETION_HANDLER_GROUP = "completion-handlers"
GORSE_SYNC_GROUP = "gorse-sync-processors"
CUSTOMER_LINKING_GROUP = "customer-linking-processors"

# Redis Configuration
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_REDIS_TLS = True
DEFAULT_REDIS_TIMEOUT = 60
DEFAULT_REDIS_HEALTH_CHECK_INTERVAL = 30

# Redis Stream Configuration
DEFAULT_STREAM_MAX_LEN = 1000
DEFAULT_STREAM_APPROX_MAX_LEN = True
DEFAULT_STREAM_IDLE_TIME = 300000  # 5 minutes in milliseconds

__all__ = [
    # New Domain-Specific Streams
    "DATA_COLLECTION_STREAM",
    "NORMALIZATION_STREAM",
    "PURCHASE_ATTRIBUTION_STREAM",
    "REFUND_ATTRIBUTION_STREAM",
    "REFUND_NORMALIZATION_STREAM",
    "SHOPIFY_EVENTS_STREAM",
    # New Domain-Specific Groups
    "DATA_COLLECTION_GROUP",
    "NORMALIZATION_GROUP",
    "PURCHASE_ATTRIBUTION_GROUP",
    "REFUND_ATTRIBUTION_GROUP",
    "REFUND_NORMALIZATION_GROUP",
    "SHOPIFY_EVENTS_GROUP",
    # ML and Analytics Streams
    "ML_TRAINING_STREAM",
    "ANALYSIS_RESULTS_STREAM",
    "USER_NOTIFICATIONS_STREAM",
    "FEATURES_COMPUTED_STREAM",
    "ML_TRAINING_COMPLETE_STREAM",
    "HEURISTIC_DECISION_REQUESTED_STREAM",
    "HEURISTIC_DECISION_MADE_STREAM",
    "HEURISTIC_DECISION_STREAM",
    "NEXT_ANALYSIS_SCHEDULED_STREAM",
    "COMPLETION_RESULTS_STREAM",
    "COMPLETION_EVENTS_STREAM",
    "BEHAVIORAL_EVENTS_STREAM",
    "GORSE_SYNC_STREAM",
    "CUSTOMER_LINKING_STREAM",
    # Legacy Groups - REMOVED
    "MAIN_TABLE_PROCESSOR_GROUP",
    # ML and Analytics Groups
    "FEATURES_CONSUMER_GROUP",
    "ML_TRAINING_GROUP",
    "HEURISTIC_DECISION_GROUP",
    "COMPLETION_HANDLER_GROUP",
    "GORSE_SYNC_GROUP",
    "CUSTOMER_LINKING_GROUP",
    # Redis Configuration
    "DEFAULT_REDIS_PORT",
    "DEFAULT_REDIS_DB",
    "DEFAULT_REDIS_TLS",
    "DEFAULT_REDIS_TIMEOUT",
    "DEFAULT_REDIS_HEALTH_CHECK_INTERVAL",
    "DEFAULT_STREAM_MAX_LEN",
    "DEFAULT_STREAM_APPROX_MAX_LEN",
    "DEFAULT_STREAM_IDLE_TIME",
]
