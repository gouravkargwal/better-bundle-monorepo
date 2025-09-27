from __future__ import annotations

from typing import Dict, Tuple, Type

from .base_adapter import BaseAdapter

# REST adapters removed - using unified GraphQL data collection
from .graphql.orders import GraphQLOrderAdapter
from .graphql.products import GraphQLProductAdapter
from .graphql.collections import GraphQLCollectionAdapter
from .graphql.customers import GraphQLCustomerAdapter
from .graphql.refunds import GraphQLRefundAdapter


_REGISTRY: Dict[Tuple[str, str], Type[BaseAdapter]] = {
    # Only GraphQL adapters - REST adapters removed due to unified data collection
    ("graphql", "orders"): GraphQLOrderAdapter,
    ("graphql", "products"): GraphQLProductAdapter,
    ("graphql", "collections"): GraphQLCollectionAdapter,
    ("graphql", "customers"): GraphQLCustomerAdapter,
    ("graphql", "refunds"): GraphQLRefundAdapter,
}


def get_adapter(format: str, data_type: str) -> BaseAdapter:
    key = (format, data_type)
    adapter_cls = _REGISTRY.get(key)
    if not adapter_cls:
        raise ValueError(
            f"No adapter registered for format={format}, data_type={data_type}"
        )
    return adapter_cls()
