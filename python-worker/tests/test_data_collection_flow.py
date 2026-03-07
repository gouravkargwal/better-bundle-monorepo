"""
Unit tests for the Data Collection Flow (Flow 1)

Tests cover:
1. ShopifyDataCollectionService — core collection logic
2. DataCollectionKafkaConsumer — Kafka message handling, retry, DLQ
3. Data Collection API endpoint — HTTP trigger
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict, Any, List


# ============================================================
# 1. TestDataCollectionService
# ============================================================


class TestDataCollectionService:
    """Tests for ShopifyDataCollectionService"""

    @pytest.fixture
    def mock_api_client(self):
        client = AsyncMock()
        client.connect = AsyncMock()
        client.set_access_token = AsyncMock()
        client.get_products = AsyncMock(return_value=[{"id": f"prod_{i}"} for i in range(5)])
        client.get_orders = AsyncMock(return_value=[{"id": f"order_{i}"} for i in range(3)])
        client.get_customers = AsyncMock(return_value=[{"id": f"cust_{i}"} for i in range(2)])
        client.get_collections = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_permission_service(self):
        service = AsyncMock()
        service.check_shop_permissions = AsyncMock(
            return_value={
                "products": True,
                "orders": True,
                "customers": True,
                "collections": True,
            }
        )
        return service

    @pytest.fixture
    def mock_data_storage(self):
        storage = AsyncMock()
        storage.store_products_data = AsyncMock()
        storage.store_orders_data = AsyncMock()
        storage.store_customers_data = AsyncMock()
        storage.store_collections_data = AsyncMock()
        return storage

    @pytest.fixture
    def service(self, mock_api_client, mock_permission_service, mock_data_storage):
        from app.domains.shopify.services.data_collection import (
            ShopifyDataCollectionService,
        )

        svc = ShopifyDataCollectionService(
            api_client=mock_api_client,
            permission_service=mock_permission_service,
            data_storage=mock_data_storage,
        )
        return svc

    @pytest.mark.asyncio
    async def test_collect_all_data_success(self, service):
        """collect_all_data returns correct per-type counts"""
        # Mock _collect_data_by_type to return predictable data per type
        async def mock_collect(data_type, *args, **kwargs):
            data = {
                "products": [{"id": f"prod_{i}"} for i in range(5)],
                "orders": [{"id": f"order_{i}"} for i in range(3)],
                "customers": [{"id": f"cust_{i}"} for i in range(2)],
            }
            return data.get(data_type, [])

        with patch.object(
            service, "_collect_data_by_type", side_effect=mock_collect
        ), patch.object(
            service, "_trigger_normalization_for_results", new_callable=AsyncMock
        ):
            result = await service.collect_all_data(
                shop_domain="test.myshopify.com",
                access_token="shpat_test",
                shop_id="shop_123",
                collection_payload={"data_types": ["products", "orders", "customers"]},
            )

        assert result["success"] is True
        assert result["products_collected"] == 5
        assert result["orders_collected"] == 3
        assert result["customers_collected"] == 2
        assert result["total_items"] == 10

    @pytest.mark.asyncio
    async def test_collect_all_data_no_permissions(
        self, service, mock_permission_service
    ):
        """Returns failure when no permissions are available"""
        mock_permission_service.check_shop_permissions.return_value = {
            "products": False,
            "orders": False,
            "customers": False,
            "collections": False,
        }

        with patch.object(
            service, "_trigger_normalization_for_results", new_callable=AsyncMock
        ):
            result = await service.collect_all_data(
                shop_domain="test.myshopify.com",
                access_token="shpat_test",
                shop_id="shop_123",
                collection_payload={"data_types": ["products", "orders"]},
            )

        assert result["success"] is False

    def test_create_success_response_counts(self, service):
        """_create_success_response correctly counts items per data type"""
        session_info = {
            "session_id": "test_session",
            "start_time": datetime.now(timezone.utc),
        }
        collection_results = {
            "collected_data": {
                "products": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}],
                "orders": [{"id": "o1"}],
                "customers": [],
            },
            "processed_types": ["products", "orders"],
        }

        result = service._create_success_response(
            session_info, collection_results, {"data_types": ["products", "orders"]}
        )

        assert result["products_collected"] == 3
        assert result["orders_collected"] == 1
        assert result["customers_collected"] == 0
        assert result["total_items"] == 4

    def test_prepare_collection_payload_defaults(self, service):
        """When payload is None, defaults to all 4 data types"""
        result = service._prepare_collection_payload(None)

        assert "data_types" in result
        assert set(result["data_types"]) == {
            "products",
            "orders",
            "customers",
            "collections",
        }

    def test_determine_collectable_data_filters_by_permissions(self, service):
        """Only data types with permissions are returned"""
        permissions = {
            "products": True,
            "orders": False,
            "customers": True,
            "collections": False,
        }
        payload = {"data_types": ["products", "orders", "customers", "collections"]}

        result = service._determine_collectable_data(permissions, payload)

        assert "products" in result
        assert "customers" in result
        assert "orders" not in result
        assert "collections" not in result


# ============================================================
# 2. TestDataCollectionConsumer
# ============================================================


class TestDataCollectionConsumer:
    """Tests for DataCollectionKafkaConsumer"""

    @pytest.fixture
    def mock_shopify_service(self):
        service = AsyncMock()
        service.collect_all_data = AsyncMock(
            return_value={"success": True, "total_items": 10}
        )
        return service

    @pytest.fixture
    def mock_shop_repo(self):
        repo = AsyncMock()
        mock_shop = MagicMock()
        mock_shop.id = "shop_123"
        mock_shop.shop_domain = "test.myshopify.com"
        mock_shop.access_token = "shpat_test"
        mock_shop.is_active = True
        repo.get_active_by_id = AsyncMock(return_value=mock_shop)
        return repo

    @pytest.fixture
    def consumer(self, mock_shopify_service, mock_shop_repo):
        from app.consumers.kafka.data_collection_consumer import (
            DataCollectionKafkaConsumer,
        )

        c = DataCollectionKafkaConsumer(shopify_service=mock_shopify_service)
        c.shop_repo = mock_shop_repo
        c.dlq_service = AsyncMock()
        c.consumer = AsyncMock()
        c.consumer.commit = AsyncMock()
        return c

    @pytest.mark.asyncio
    async def test_handle_data_collection_job_success(
        self, consumer, mock_shopify_service
    ):
        """Happy path: message triggers collect_all_data with correct args"""
        event = {
            "event_type": "data_collection",
            "shop_id": "shop_123",
            "job_id": "job_001",
            "collection_payload": {"data_types": ["products"]},
        }

        await consumer._handle_message(event)

        mock_shopify_service.collect_all_data.assert_called_once()
        call_kwargs = mock_shopify_service.collect_all_data.call_args
        assert call_kwargs.kwargs["shop_domain"] == "test.myshopify.com"
        assert call_kwargs.kwargs["shop_id"] == "shop_123"

    @pytest.mark.asyncio
    async def test_handle_data_collection_job_retry_on_failure(
        self, consumer, mock_shopify_service
    ):
        """Service failure triggers retries then DLQ"""
        mock_shopify_service.collect_all_data.side_effect = Exception("API error")

        event = {
            "event_type": "data_collection",
            "shop_id": "shop_123",
            "job_id": "job_002",
            "collection_payload": {},
        }

        # Patch sleep to avoid waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await consumer._handle_message(event)

        # 3 retry attempts
        assert mock_shopify_service.collect_all_data.call_count == 3

        # Sent to DLQ after exhausting retries
        consumer.dlq_service.send_to_dlq.assert_called_once()
        dlq_call = consumer.dlq_service.send_to_dlq.call_args
        assert dlq_call.kwargs["reason"] == "data_collection_failed"

    @pytest.mark.asyncio
    async def test_handle_data_collection_job_no_shop(
        self, consumer, mock_shop_repo, mock_shopify_service
    ):
        """Missing shop returns early without calling collect"""
        mock_shop_repo.get_active_by_id.return_value = None

        event = {
            "event_type": "data_collection",
            "shop_id": "nonexistent",
            "job_id": "job_003",
            "collection_payload": {},
        }

        await consumer._handle_message(event)

        mock_shopify_service.collect_all_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_webhook_event_routes_correctly(self, consumer):
        """product_updated creates correct collection payload"""
        # Mock shop cache for webhook path
        mock_shop_data = {
            "id": "shop_123",
            "domain": "test.myshopify.com",
            "access_token": "shpat_test",
            "is_active": True,
        }

        with patch.object(
            consumer, "_resolve_shop_data", new_callable=AsyncMock, return_value=mock_shop_data
        ), patch.object(
            consumer, "_process_data_collection_job", new_callable=AsyncMock
        ) as mock_process:
            event = {
                "event_type": "product_updated",
                "shop_domain": "test.myshopify.com",
                "shopify_id": "gid://shopify/Product/123",
                "timestamp": "2026-01-01T00:00:00Z",
            }

            await consumer._handle_message(event)

            mock_process.assert_called_once()
            call_args = mock_process.call_args
            collection_payload = call_args.args[2]  # third positional arg
            assert collection_payload["data_types"] == ["products"]
            assert "gid://shopify/Product/123" in collection_payload["specific_ids"]["products"]

    @pytest.mark.asyncio
    async def test_handle_deletion_event(self, consumer):
        """product_deleted calls normalization deletion handler"""
        mock_shop_data = {
            "id": "shop_123",
            "domain": "test.myshopify.com",
            "access_token": "shpat_test",
            "is_active": True,
        }

        mock_norm = MagicMock()
        mock_norm.deletion_service.handle_entity_deletion = AsyncMock()

        with patch.object(
            consumer, "_resolve_shop_data", new_callable=AsyncMock, return_value=mock_shop_data
        ), patch(
            "app.domains.shopify.services.normalisation_service.NormalizationService",
            return_value=mock_norm,
        ):
            event = {
                "event_type": "product_deleted",
                "shop_domain": "test.myshopify.com",
                "shopify_id": "gid://shopify/Product/456",
            }

            await consumer._handle_message(event)

            mock_norm.deletion_service.handle_entity_deletion.assert_called_once()

    @pytest.mark.asyncio
    async def test_suspended_shop_sent_to_dlq(self, consumer):
        """Inactive shop sends message to DLQ"""
        mock_shop_data = {
            "id": "shop_123",
            "domain": "test.myshopify.com",
            "access_token": "shpat_test",
            "is_active": False,
        }

        with patch.object(
            consumer, "_resolve_shop_data", new_callable=AsyncMock, return_value=mock_shop_data
        ):
            message = {
                "value": {
                    "event_type": "data_collection",
                    "shop_id": "shop_123",
                    "job_id": "job_004",
                }
            }

            await consumer._handle_message(message)

            consumer.dlq_service.send_to_dlq.assert_called_once()
            dlq_call = consumer.dlq_service.send_to_dlq.call_args
            assert dlq_call.kwargs["reason"] == "shop_suspended"


# ============================================================
# 3. TestDataCollectionAPI
# ============================================================


class TestDataCollectionAPI:
    """Tests for POST /api/v1/data-collection/trigger endpoint"""

    @pytest.fixture
    def mock_shop(self):
        shop = MagicMock()
        shop.id = "shop_123"
        shop.shop_domain = "test.myshopify.com"
        shop.access_token = "shpat_test"
        shop.is_active = True
        return shop

    def _make_ctx_mock(self, shop):
        """Create a properly mocked async context manager for get_transaction_context"""
        mock_session = AsyncMock()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = shop
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    @pytest.mark.asyncio
    async def test_trigger_success(self, mock_shop):
        """Valid request returns correct response with item counts"""
        from app.api.v1.data_collection import trigger_data_collection, DataCollectionRequest
        from fastapi import BackgroundTasks

        request = DataCollectionRequest(
            shop_id="shop_123",
            data_types=["products", "orders"],
            since_hours=24,
        )

        mock_result = {
            "success": True,
            "total_items": 8,
            "orders_collected": 3,
            "products_collected": 5,
            "customers_collected": 0,
        }

        mock_svc_instance = AsyncMock()
        mock_svc_instance.collect_all_data = AsyncMock(return_value=mock_result)

        with patch(
            "app.api.v1.data_collection.get_transaction_context",
            return_value=self._make_ctx_mock(mock_shop),
        ), patch.dict(
            "app.domains.shopify.services.__dict__",
            {"ShopifyAPIClient": MagicMock(), "ShopifyPermissionService": MagicMock()},
        ), patch(
            "app.api.v1.data_collection.ShopifyDataCollectionService",
            return_value=mock_svc_instance,
        ):
            response = await trigger_data_collection(request, BackgroundTasks())

        assert response.success is True
        assert response.orders_collected == 3
        assert response.products_collected == 5

    @pytest.mark.asyncio
    async def test_trigger_shop_not_found(self):
        """Invalid shop_id raises 404 HTTPException"""
        from app.api.v1.data_collection import trigger_data_collection, DataCollectionRequest
        from fastapi import BackgroundTasks, HTTPException

        request = DataCollectionRequest(shop_id="nonexistent")

        with patch(
            "app.api.v1.data_collection.get_transaction_context",
            return_value=self._make_ctx_mock(None),
        ), pytest.raises(HTTPException) as exc_info:
            await trigger_data_collection(request, BackgroundTasks())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_trigger_inactive_shop(self, mock_shop):
        """Inactive shop raises 400 HTTPException"""
        from app.api.v1.data_collection import trigger_data_collection, DataCollectionRequest
        from fastapi import BackgroundTasks, HTTPException

        mock_shop.is_active = False
        request = DataCollectionRequest(shop_id="shop_123")

        with patch(
            "app.api.v1.data_collection.get_transaction_context",
            return_value=self._make_ctx_mock(mock_shop),
        ), pytest.raises(HTTPException) as exc_info:
            await trigger_data_collection(request, BackgroundTasks())

        assert exc_info.value.status_code == 400
        assert "not active" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_trigger_dry_run(self, mock_shop):
        """dry_run returns without collecting data"""
        from app.api.v1.data_collection import trigger_data_collection, DataCollectionRequest
        from fastapi import BackgroundTasks

        request = DataCollectionRequest(
            shop_id="shop_123",
            dry_run=True,
        )

        with patch(
            "app.api.v1.data_collection.get_transaction_context",
            return_value=self._make_ctx_mock(mock_shop),
        ):
            response = await trigger_data_collection(request, BackgroundTasks())

        assert response.success is True
        assert "dry run" in response.message.lower()
        assert response.orders_collected == 0
        assert response.products_collected == 0
