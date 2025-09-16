from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAdapter(ABC):
    """Abstract base for source-specific normalization adapters.

    Implementations map a raw Shopify payload into a canonical entity dict
    that complies with canonical Pydantic models in canonical_models.py.
    """

    @abstractmethod
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        """Convert raw payload to canonical dict."""
        raise NotImplementedError
