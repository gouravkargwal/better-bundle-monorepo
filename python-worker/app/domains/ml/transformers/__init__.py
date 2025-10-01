"""
Gorse Transformers Package - OPTIMIZED VERSION

Transforms ML features to Gorse-compatible formats with research-backed labels.

Key Optimization Principles:
1. Categorical labels only (no numeric values)
2. Max 15 labels per entity (Gorse best practice)
3. Actionable segments (RFM, intent, lifecycle)
4. Performance-based tiers
5. Behavioral patterns over raw metrics

Based on:
- Gorse collaborative filtering research
- E-commerce recommendation best practices
- Real-world deployment learnings
"""

from .gorse_user_transformer import GorseUserTransformer
from .gorse_item_transformer import GorseItemTransformer
from .gorse_feedback_transformer import GorseFeedbackTransformer
from .gorse_collection_transformer import GorseCollectionTransformer
from .gorse_transformer_factory import GorseTransformerFactory

__all__ = [
    "GorseUserTransformer",
    "GorseItemTransformer",
    "GorseFeedbackTransformer",
    "GorseCollectionTransformer",
    "GorseTransformerFactory",
]

# Version info
__version__ = "2.0.0"
__author__ = "BetterBundle ML Team"
__optimization_date__ = "2025-01-27"
