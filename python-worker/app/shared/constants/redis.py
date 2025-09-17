"""
Redis-specific constants
"""

# Redis Stream Names
DATA_JOB_STREAM = "betterbundle:data-jobs"
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

# Consumer Group Names
DATA_PROCESSOR_GROUP = "data-processors"
MAIN_TABLE_PROCESSOR_GROUP = "main-table-processors"
FEATURES_CONSUMER_GROUP = "data-processors"
ML_TRAINING_GROUP = "ml-training-consumers"
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
    "DATA_JOB_STREAM",
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
    "DATA_PROCESSOR_GROUP",
    "MAIN_TABLE_PROCESSOR_GROUP",
    "FEATURES_CONSUMER_GROUP",
    "ML_TRAINING_GROUP",
    "HEURISTIC_DECISION_GROUP",
    "COMPLETION_HANDLER_GROUP",
    "GORSE_SYNC_GROUP",
    "CUSTOMER_LINKING_GROUP",
    "DEFAULT_REDIS_PORT",
    "DEFAULT_REDIS_DB",
    "DEFAULT_REDIS_TLS",
    "DEFAULT_REDIS_TIMEOUT",
    "DEFAULT_REDIS_HEALTH_CHECK_INTERVAL",
    "DEFAULT_STREAM_MAX_LEN",
    "DEFAULT_STREAM_APPROX_MAX_LEN",
    "DEFAULT_STREAM_IDLE_TIME",
]
