"""
TFRS-based recommendation engine for BetterBundle.

Replaces Gorse as the primary recommendation engine.
Uses TensorFlow Recommenders two-tower architecture to leverage
all product features, user features, and interaction data that
Gorse could not consume.
"""

from .config import TfrsConfig
from .features import FeatureTransformer
from .model import BetterBundleModel
from .trainer import TfrsTrainer
from .serving import TfrsServing

__all__ = [
    "TfrsConfig",
    "FeatureTransformer",
    "BetterBundleModel",
    "TfrsTrainer",
    "TfrsServing",
]
