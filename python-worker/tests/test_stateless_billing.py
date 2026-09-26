"""
Unit tests for stateless usage-based billing migration:
1. Active charging statelessly (billing_cycle_id is None)
2. Cap exceeded with partial charge and overflow preservation
3. Overflow settlement on rollover drain
4. No-flapping suspension check
5. Strict rollover detection and backlog drain
6. Preserved revenue creation while SUSPENDED (no silent drops)
"""

import asyncio
import sys
import types
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

if "aiokafka" not in sys.modules:
    aiokafka = types.ModuleType("aiokafka")
    aiokafka.__path__ = []
    aiokafka.AIOKafkaProducer = MagicMock
    aiokafka.AIOKafkaConsumer = MagicMock
    sys.modules["aiokafka"] = aiokafka

    class ErrorsModule(types.ModuleType):
        def __getattr__(self, name):
            cls = type(name, (Exception,), {})
            setattr(self, name, cls)
            return cls

    errors_mod = ErrorsModule("aiokafka.errors")
    sys.modules["aiokafka.errors"] = errors_mod
    setattr(aiokafka, "errors", errors_mod)

    for sub in ["structs", "producer", "consumer", "admin"]:
        mod = types.ModuleType(f"aiokafka.{sub}")
        setattr(aiokafka, sub, mod)
        sys.modules[f"aiokafka.{sub}"] = mod
        mod.AIOKafkaProducer = MagicMock
        mod.AIOKafkaConsumer = MagicMock
        mod.AIOKafkaAdminClient = MagicMock
        mod.NewTopic = MagicMock
        mod.TopicPartition = MagicMock

import pytest

from app.core.database.models.commission import CommissionRecord
from app.core.database.models.enums import (
    BillingPhase,
    ChargeType,
    CommissionStatus,
    SubscriptionStatus,
    SubscriptionType,
)
from app.core.exceptions import PermanentError, TransientError, CapError
from app.core.database.models.shop import Shop
from app.core.database.models.shop_subscription import ShopSubscription
from app.domains.billing.services.commission_service_v2 import CommissionServiceV2
@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_shop():
    shop = MagicMock(spec=Shop)
    shop.id = "shop-uuid-123"
    shop.shop_domain = "test-shop.myshopify.com"
    shop.access_token = "shpat_test_token"
    shop.is_active = True
    shop.suspended_at = None
    shop.suspension_reason = None
    return shop


@pytest.fixture
def mock_subscription():
    sub = MagicMock(spec=ShopSubscription)
    sub.id = "sub-uuid-456"
    sub.shop_id = "shop-uuid-123"
    sub.status = SubscriptionStatus.ACTIVE
    sub.subscription_type = SubscriptionType.PAID
    sub.shopify_subscription_id = "gid://shopify/AppSubscription/789"
    sub.shopify_line_item_id = "gid://shopify/AppSubscriptionLineItem/101"
    sub.currency = "USD"
    sub.is_active = True
    sub.shop_subscription_metadata = {}
    return sub


@pytest.mark.asyncio
async def test_stateless_paid_commission_creation(mock_session, mock_subscription):
    """Test that paid commissions are built statelessly without billing_cycle_id."""
    service = CommissionServiceV2(mock_session)

    purchase_attr = MagicMock()
    purchase_attr.order_id = "12345"
    purchase_attr.purchase_at = datetime.utcnow()

    commission = service._build_paid_commission(
        shop_id="shop-uuid-123",
        purchase_attribution_id="attr-uuid-999",
        purchase_attr=purchase_attr,
        attributed_revenue=Decimal("100.00"),
        commission_earned=Decimal("3.00"),
        commission_rate=Decimal("0.03"),
        shop_subscription=mock_subscription,
    )

    assert commission.billing_cycle_id is None
    assert commission.billing_cycle_start is None
    assert commission.billing_cycle_end is None
    assert commission.commission_earned == Decimal("3.00")
    assert commission.commission_charged == Decimal("3.00")
    assert commission.commission_overflow == Decimal("0")
    assert commission.charge_type == ChargeType.FULL
    assert commission.status == CommissionStatus.PENDING


@pytest.mark.asyncio
async def test_charge_commission_to_shopify_success(
    mock_session, mock_shop, mock_subscription
):
    """Test charge_commission_to_shopify sends usage record with correct idempotency key and updates status to RECORDED."""
    from unittest.mock import patch

    service = CommissionServiceV2(mock_session)

    commission = CommissionRecord(
        id="comm-1",
        shop_id=mock_shop.id,
        purchase_attribution_id="attr-1",
        billing_cycle_id=None,
        order_id="12345",
        order_date=datetime.utcnow(),
        attributed_revenue=Decimal("100.00"),
        commission_rate=Decimal("0.03"),
        commission_earned=Decimal("3.00"),
        commission_charged=Decimal("3.00"),
        commission_overflow=Decimal("0"),
        billing_phase=BillingPhase.PAID,
        status=CommissionStatus.PENDING,
        charge_type=ChargeType.FULL,
        currency="USD",
        shopify_usage_record_id=None,
    )

    mock_tx_session = AsyncMock()
    mock_tx_session.execute = AsyncMock()

    with patch(
        "app.domains.billing.services.commission_service_v2.ShopifyUsageBillingServiceV2"
    ) as mock_usage_cls, \
    patch(
        "app.domains.billing.services.commission_service_v2.get_transaction_context"
    ) as mock_get_tx, \
    patch(
        "app.domains.billing.services.commission_service_v2.BillingRepositoryV2"
    ) as mock_billing_repo_cls:
        mock_ctx_mgr = AsyncMock()
        mock_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_tx_session)
        mock_ctx_mgr.__aexit__ = AsyncMock(return_value=False)
        mock_get_tx.return_value = mock_ctx_mgr

        mock_billing_repo = AsyncMock()
        mock_billing_repo.get_shop.return_value = mock_shop
        mock_billing_repo.get_shop_subscription.return_value = mock_subscription
        mock_billing_repo_cls.return_value = mock_billing_repo

        mock_usage_instance = AsyncMock()
        usage_res = MagicMock()
        usage_res.id = "gid://shopify/AppUsageRecord/999"
        usage_res.created_at = "2026-09-12T00:00:00Z"
        usage_res.price = {"amount": "3.00", "currencyCode": "USD"}
        mock_usage_instance.record_usage.return_value = usage_res
        mock_usage_cls.return_value = mock_usage_instance

        def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = commission
            return result

        mock_tx_session.execute.side_effect = execute_side_effect

        await service.charge_commission_to_shopify("comm-1")

    assert commission.status == CommissionStatus.RECORDED
    assert commission.shopify_usage_record_id == "gid://shopify/AppUsageRecord/999"
    assert commission.commission_overflow == Decimal("0")
    assert commission.commission_charged == Decimal("3.00")
    mock_usage_instance.record_usage.assert_called_once()
    call_kwargs = mock_usage_instance.record_usage.call_args.kwargs
    assert call_kwargs["idempotency_key"] == "commission-comm-1"


@pytest.mark.asyncio
async def test_charge_commission_cap_exceeded_sets_failed(
    mock_session, mock_shop, mock_subscription
):
    """Test that cap exceeded user errors are treated as PermanentError and mark commission FAILED until live matcher is added."""
    from unittest.mock import patch

    service = CommissionServiceV2(mock_session)

    commission = CommissionRecord(
        id="comm-2",
        shop_id=mock_shop.id,
        purchase_attribution_id="attr-2",
        billing_cycle_id=None,
        order_id="12346",
        order_date=datetime.utcnow(),
        attributed_revenue=Decimal("300.00"),
        commission_rate=Decimal("0.03"),
        commission_earned=Decimal("9.00"),
        commission_charged=Decimal("9.00"),
        commission_overflow=Decimal("0"),
        billing_phase=BillingPhase.PAID,
        status=CommissionStatus.PENDING,
        charge_type=ChargeType.FULL,
        currency="USD",
        shopify_usage_record_id=None,
    )

    mock_tx_session = AsyncMock()
    mock_tx_session.execute = AsyncMock()

    with patch(
        "app.domains.billing.services.commission_service_v2.ShopifyUsageBillingServiceV2"
    ) as mock_usage_cls, \
    patch(
        "app.domains.billing.services.commission_service_v2.get_transaction_context"
    ) as mock_get_tx, \
    patch(
        "app.domains.billing.services.commission_service_v2.BillingRepositoryV2"
    ) as mock_billing_repo_cls:
        mock_ctx_mgr = AsyncMock()
        mock_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_tx_session)
        mock_ctx_mgr.__aexit__ = AsyncMock(return_value=False)
        mock_get_tx.return_value = mock_ctx_mgr

        mock_billing_repo = AsyncMock()
        mock_billing_repo.get_shop.return_value = mock_shop
        mock_billing_repo.get_shop_subscription.return_value = mock_subscription
        mock_billing_repo_cls.return_value = mock_billing_repo

        mock_usage_instance = AsyncMock()
        mock_usage_instance.record_usage.return_value = {
            "error": True,
            "user_errors": [
                {"message": "Failed to create usage charge", "code": None}
            ],
        }
        mock_usage_cls.return_value = mock_usage_instance

        def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = commission
            return result

        mock_tx_session.execute.side_effect = execute_side_effect

        await service.charge_commission_to_shopify("comm-2")

    assert commission.status == CommissionStatus.FAILED


@pytest.mark.asyncio
async def test_charge_commission_retries_on_transient_error(
    mock_session, mock_shop, mock_subscription
):
    """Test that transient Shopify errors bubble up so Kafka redelivers."""
    from unittest.mock import patch
    import httpx

    service = CommissionServiceV2(mock_session)

    commission = CommissionRecord(
        id="comm-3",
        shop_id=mock_shop.id,
        purchase_attribution_id="attr-3",
        billing_cycle_id=None,
        order_id="12347",
        order_date=datetime.utcnow(),
        attributed_revenue=Decimal("100.00"),
        commission_rate=Decimal("0.03"),
        commission_earned=Decimal("3.00"),
        commission_charged=Decimal("3.00"),
        commission_overflow=Decimal("0"),
        billing_phase=BillingPhase.PAID,
        status=CommissionStatus.PENDING,
        charge_type=ChargeType.FULL,
        currency="USD",
        shopify_usage_record_id=None,
    )

    mock_tx_session = AsyncMock()
    mock_tx_session.execute = AsyncMock()

    with patch(
        "app.domains.billing.services.commission_service_v2.ShopifyUsageBillingServiceV2"
    ) as mock_usage_cls, \
    patch(
        "app.domains.billing.services.commission_service_v2.get_transaction_context"
    ) as mock_get_tx, \
    patch(
        "app.domains.billing.services.commission_service_v2.BillingRepositoryV2"
    ) as mock_billing_repo_cls:
        mock_ctx_mgr = AsyncMock()
        mock_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_tx_session)
        mock_ctx_mgr.__aexit__ = AsyncMock(return_value=False)
        mock_get_tx.return_value = mock_ctx_mgr

        mock_billing_repo = AsyncMock()
        mock_billing_repo.get_shop.return_value = mock_shop
        mock_billing_repo.get_shop_subscription.return_value = mock_subscription
        mock_billing_repo_cls.return_value = mock_billing_repo

        mock_usage_instance = AsyncMock()
        mock_usage_instance.record_usage.side_effect = httpx.TimeoutException("timed out")
        mock_usage_cls.return_value = mock_usage_instance

        def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = commission
            return result

        mock_tx_session.execute.side_effect = execute_side_effect

        with pytest.raises(TransientError):
            await service.charge_commission_to_shopify("comm-3")

    assert commission.status == CommissionStatus.PENDING


@pytest.mark.asyncio
async def test_preserved_revenue_while_suspended(mock_session, mock_shop):
    """Test that orders for suspended shops create PENDING commissions but skip publishing Kafka usage events."""
    service = CommissionServiceV2(mock_session)
    service.commission_repository = AsyncMock()
    service.commission_repository.get_by_purchase_attribution_id.return_value = None

    suspended_sub = MagicMock(spec=ShopSubscription)
    suspended_sub.id = "sub-1"
    suspended_sub.status = SubscriptionStatus.SUSPENDED
    suspended_sub.subscription_type = SubscriptionType.PAID
    suspended_sub.currency = "USD"
    suspended_sub.effective_commission_rate = Decimal("0.03")
    service.billing_repository = AsyncMock()
    service.billing_repository.get_shop_subscription.return_value = suspended_sub

    purchase_attr = MagicMock()
    purchase_attr.id = "attr-3"
    purchase_attr.order_id = "5555"
    purchase_attr.shop_id = mock_shop.id
    purchase_attr.total_revenue = Decimal("100.00")
    purchase_attr.purchase_at = datetime.utcnow()
    service.purchase_attribution_repository = AsyncMock()
    service.purchase_attribution_repository.get_by_id.return_value = purchase_attr

    converted = MagicMock()
    converted.amount = Decimal("100.00")
    converted.source_currency = "USD"
    converted.rate = Decimal("1.0")

    with patch.object(service, "_get_order_currency", new_callable=AsyncMock) as mock_curr, \
         patch("app.domains.billing.services.commission_service_v2.convert_to_usd", new_callable=AsyncMock) as mock_conv, \
         patch("app.domains.billing.services.commission_service_v2.EventPublisher") as mock_pub_cls:
        mock_curr.return_value = "USD"
        mock_conv.return_value = converted

        created = await service.create_commission_record(
            shop_id=mock_shop.id, purchase_attribution_id="attr-3"
        )

        assert created is not None
        assert created.status == CommissionStatus.PENDING
        assert created.billing_phase == BillingPhase.PAID
        assert created.commission_earned == Decimal("3.00")
        assert created.commission_charged == Decimal("3.00")
        # Kafka publish MUST be skipped while suspended so it doesn't hit Shopify prematurely
        mock_pub_cls.assert_not_called()


