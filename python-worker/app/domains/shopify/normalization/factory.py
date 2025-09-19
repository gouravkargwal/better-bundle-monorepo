from __future__ import annotations

from typing import Dict, Tuple, Type

from .base_adapter import BaseAdapter
from .rest.orders import RestOrderAdapter
from .rest.products import RestProductAdapter
from .rest.collections import RestCollectionAdapter
from .rest.customers import RestCustomerAdapter
from .rest.refunds import RestRefundAdapter
from .graphql.orders import GraphQLOrderAdapter
from .graphql.products import GraphQLProductAdapter
from .graphql.collections import GraphQLCollectionAdapter
from .graphql.customers import GraphQLCustomerAdapter
from .graphql.refunds import GraphQLRefundAdapter


_REGISTRY: Dict[Tuple[str, str], Type[BaseAdapter]] = {
    ("rest", "orders"): RestOrderAdapter,
    ("graphql", "orders"): GraphQLOrderAdapter,
    ("rest", "products"): RestProductAdapter,
    ("graphql", "products"): GraphQLProductAdapter,
    ("rest", "collections"): RestCollectionAdapter,
    ("graphql", "collections"): GraphQLCollectionAdapter,
    ("rest", "customers"): RestCustomerAdapter,
    ("graphql", "customers"): GraphQLCustomerAdapter,
    ("rest", "refunds"): RestRefundAdapter,
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
