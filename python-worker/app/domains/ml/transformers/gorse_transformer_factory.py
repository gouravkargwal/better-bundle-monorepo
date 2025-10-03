"""
Gorse Transformer Factory
Provides a single point to access all Gorse transformers
Uses singleton pattern for efficient memory usage
"""

from typing import Optional
from .gorse_user_transformer import GorseUserTransformer
from .gorse_item_transformer import GorseItemTransformer
from .gorse_feedback_transformer import GorseFeedbackTransformer
from .gorse_collection_transformer import GorseCollectionTransformer
from .gorse_interaction_transformer import GorseInteractionTransformer

from app.core.logging import get_logger

logger = get_logger(__name__)


class GorseTransformerFactory:
    """
    Factory to create and manage Gorse transformers

    Uses singleton pattern to reuse transformer instances
    """

    _user_transformer: Optional[GorseUserTransformer] = None
    _item_transformer: Optional[GorseItemTransformer] = None
    _feedback_transformer: Optional[GorseFeedbackTransformer] = None
    _collection_transformer: Optional[GorseCollectionTransformer] = None
    _interaction_transformer: Optional[GorseInteractionTransformer] = None

    @classmethod
    def get_user_transformer(cls) -> GorseUserTransformer:
        """
        Get or create user transformer (singleton)

        Returns:
            GorseUserTransformer instance
        """
        if cls._user_transformer is None:
            cls._user_transformer = GorseUserTransformer()
            logger.debug("Created new GorseUserTransformer instance")
        return cls._user_transformer

    @classmethod
    def get_item_transformer(cls) -> GorseItemTransformer:
        """
        Get or create item transformer (singleton)

        Returns:
            GorseItemTransformer instance
        """
        if cls._item_transformer is None:
            cls._item_transformer = GorseItemTransformer()
            logger.debug("Created new GorseItemTransformer instance")
        return cls._item_transformer

    @classmethod
    def get_feedback_transformer(cls) -> GorseFeedbackTransformer:
        """
        Get or create feedback transformer (singleton)

        Returns:
            GorseFeedbackTransformer instance
        """
        if cls._feedback_transformer is None:
            cls._feedback_transformer = GorseFeedbackTransformer()
            logger.debug("Created new GorseFeedbackTransformer instance")
        return cls._feedback_transformer

    @classmethod
    def get_collection_transformer(cls) -> GorseCollectionTransformer:
        """
        Get or create collection transformer (singleton)

        Returns:
            GorseCollectionTransformer instance
        """
        if cls._collection_transformer is None:
            cls._collection_transformer = GorseCollectionTransformer()
            logger.debug("Created new GorseCollectionTransformer instance")
        return cls._collection_transformer

    @classmethod
    def get_interaction_transformer(cls) -> GorseInteractionTransformer:
        """
        Get or create interaction transformer (singleton)

        Returns:
            GorseInteractionTransformer instance
        """
        if cls._interaction_transformer is None:
            cls._interaction_transformer = GorseInteractionTransformer()
            logger.debug("Created new GorseInteractionTransformer instance")
        return cls._interaction_transformer

    @classmethod
    def reset_transformers(cls):
        """
        Reset all transformer instances
        Useful for testing or when configuration changes
        """
        cls._user_transformer = None
        cls._item_transformer = None
        cls._feedback_transformer = None
        cls._collection_transformer = None
        cls._interaction_transformer = None
        logger.debug("Reset all transformer instances")
