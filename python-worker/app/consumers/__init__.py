"""
Consumers package for BetterBundle Python Worker
"""

from .data_collection_consumer import DataCollectionConsumer

# ShopifyEventsConsumer removed - replaced by NormalizationConsumer

__all__ = [
    "DataCollectionConsumer",
]
