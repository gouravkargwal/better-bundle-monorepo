"""
TFRS-based recommendation engine for BetterBundle.

Two-tower deep learning model with rich features:
- Product: text embeddings, image embeddings, price signals, tags, collections, inventory
- User: purchase history, customer tier, location
- Context: time of day, day of week, placement context
"""

from .config import TfrsConfig
from .features import FeatureTransformer
from .model import BetterBundleModel, QueryTower, CandidateTower
from .trainer import TfrsTrainer
from .serving import TfrsServing
from .embeddings import VertexAIEmbeddings
from .llm_enricher import LLMEnricher

__all__ = [
    "TfrsConfig",
    "FeatureTransformer",
    "BetterBundleModel",
    "QueryTower",
    "CandidateTower",
    "TfrsTrainer",
    "TfrsServing",
    "VertexAIEmbeddings",
    "LLMEnricher",
]
