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
from app.core.database.models.shop import Shop
from app.core.database.models.shop_subscription import ShopSubscription
from app.domains.billing.services.commission_service_v2 import CommissionServiceV2
from app.domains.billing.services.rollover_reconciler import (
    drain_pending_commissions,
    reconcile_rollovers_once,
)


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
async def test_record_commission_to_shopify_active_charge(
    mock_session, mock_shop, mock_subscription
):
    """Test initial full charge sends usage record with correct idempotency key and updates status to RECORDED."""
    service = CommissionServiceV2(mock_session)
    service.billing_repository = AsyncMock()
    service.billing_repository.get_shop.return_value = mock_shop
    service.billing_repository.get_shop_subscription.return_value = mock_subscription

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
    service.commission_repository = AsyncMock()
    service.commission_repository.get_by_id.return_value = commission

    mock_shopify = AsyncMock()
    usage_res = MagicMock()
    usage_res.id = "gid://shopify/AppUsageRecord/999"
    usage_res.created_at = "2026-09-12T00:00:00Z"
    usage_res.price = {"amount": "3.00", "currencyCode": "USD"}
    mock_shopify.record_usage.return_value = usage_res

    res = await service.record_commission_to_shopify("comm-1", mock_shopify)

    assert res["success"] is True
    assert commission.status == CommissionStatus.RECORDED
    assert commission.shopify_usage_record_id == "gid://shopify/AppUsageRecord/999"
    assert commission.commission_overflow == Decimal("0")
    assert mock_shopify.record_usage.call_count == 1
    call_kwargs = mock_shopify.record_usage.call_args.kwargs
    assert call_kwargs["idempotency_key"] == f"{mock_shop.id}-comm-1-12345"


@pytest.mark.asyncio
async def test_record_commission_cap_exceeded_partial_charge(
    mock_session, mock_shop, mock_subscription
):
    """Test that cap exceeded attempts a partial charge, records overflow, keeps PENDING, and suspends shop."""
    service = CommissionServiceV2(mock_session)
    service.billing_repository = AsyncMock()
    service.billing_repository.get_shop.return_value = mock_shop
    service.billing_repository.get_shop_subscription.return_value = mock_subscription

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
    service.commission_repository = AsyncMock()
    service.commission_repository.get_by_id.return_value = commission

    mock_shopify = AsyncMock()
    # First call returns cap exceeded
    mock_shopify.record_usage.side_effect = [
        {"error": True, "cap_exceeded": True, "user_errors": ["Capped amount exceeded"]},
        # Second call (partial charge) succeeds with $4.00 remaining
        MagicMock(
            id="gid://shopify/AppUsageRecord/1000",
            created_at="2026-09-12T00:00:00Z",
            price={"amount": "4.00", "currencyCode": "USD"},
        ),
    ]

    # Live Shopify query returns cap $100 and balance $96 ($4 remaining)
    mock_shopify.get_subscription_status.return_value = {
        "lineItems": [
            {
                "plan": {
                    "pricingDetails": {
                        "__typename": "AppUsagePricing",
                        "cappedAmount": {"amount": "100.00"},
                        "balanceUsed": {"amount": "96.00"},
                    }
                }
            }
        ]
    }

    with patch.object(
        service, "_suspend_shop_for_cap_reached", new_callable=AsyncMock
    ) as mock_suspend:
        res = await service.record_commission_to_shopify("comm-2", mock_shopify)

        assert res["success"] is False
        assert res["error"] == "cap_exceeded"
        # Status MUST stay PENDING so rollover drain can settle the overflow
        assert commission.status == CommissionStatus.PENDING
        assert commission.charge_type == ChargeType.PARTIAL
        assert commission.commission_charged == Decimal("4.00")
        assert commission.commission_overflow == Decimal("5.00")  # 9 - 4 = 5
        assert commission.shopify_usage_record_id == "gid://shopify/AppUsageRecord/1000"

        # Suspend was called with recorded live balance
        mock_suspend.assert_called_once_with(
            mock_shop.id, balance_used=Decimal("100.00")
        )


@pytest.mark.asyncio
async def test_record_commission_overflow_settlement_on_replay(
    mock_session, mock_shop, mock_subscription
):
    """Test that replaying an overflow commission charges the overflow, suffixes idempotency key, and marks RECORDED."""
    service = CommissionServiceV2(mock_session)
    service.billing_repository = AsyncMock()
    service.billing_repository.get_shop.return_value = mock_shop
    service.billing_repository.get_shop_subscription.return_value = mock_subscription

    # Commission already had a partial charge of $4.00 and has $5.00 overflow
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
        commission_charged=Decimal("4.00"),
        commission_overflow=Decimal("5.00"),
        billing_phase=BillingPhase.PAID,
        status=CommissionStatus.PENDING,
        charge_type=ChargeType.PARTIAL,
        currency="USD",
        shopify_usage_record_id="gid://shopify/AppUsageRecord/1000",
        shopify_response=[
            {"id": "gid://shopify/AppUsageRecord/1000", "type": "partial"}
        ],
    )
    service.commission_repository = AsyncMock()
    service.commission_repository.get_by_id.return_value = commission

    mock_shopify = AsyncMock()
    usage_res = MagicMock()
    usage_res.id = "gid://shopify/AppUsageRecord/2000"
    usage_res.created_at = "2026-09-12T00:00:00Z"
    usage_res.price = {"amount": "5.00", "currencyCode": "USD"}
    mock_shopify.record_usage.return_value = usage_res

    res = await service.record_commission_to_shopify("comm-2", mock_shopify)

    assert res["success"] is True
    assert commission.status == CommissionStatus.RECORDED
    assert commission.charge_type == ChargeType.FULL
    assert commission.commission_charged == Decimal("9.00")
    assert commission.commission_overflow == Decimal("0")
    # First usage record id remains the primary anchor
    assert commission.shopify_usage_record_id == "gid://shopify/AppUsageRecord/1000"

    # Idempotency key must have '-overflow' suffix
    call_kwargs = mock_shopify.record_usage.call_args.kwargs
    assert call_kwargs["idempotency_key"] == f"{mock_shop.id}-comm-2-12346-overflow"
    assert call_kwargs["amount"] == Decimal("5.00")


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


@pytest.mark.asyncio
async def test_rollover_reconciler_no_flapping():
    """Test that if Shopify balanceUsed has NOT dropped, shop remains SUSPENDED (no flapping)."""
    sub = MagicMock(spec=ShopSubscription)
    sub.id = "sub-1"
    sub.shop_id = "shop-1"
    sub.status = SubscriptionStatus.SUSPENDED
    sub.shopify_subscription_id = "gid://shopify/AppSubscription/1"
    sub.is_active = True
    # Suspended at $98.00 balance
    sub.shop_subscription_metadata = {"suspended_balance_used": 98.0}

    shop = MagicMock(spec=Shop)
    shop.id = "shop-1"
    shop.shop_domain = "test.myshopify.com"
    shop.access_token = "token"
    shop.is_active = False

    result_mock = MagicMock()
    result_mock.all.return_value = [(sub, shop)]

    mock_db_session = AsyncMock()
    mock_db_session.execute.return_value = result_mock
    mock_db_session.get.side_effect = lambda model, id_: sub if model == ShopSubscription else shop

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context") as mock_ctx, \
         patch("app.domains.billing.services.rollover_reconciler.ShopifyUsageBillingServiceV2") as mock_usage_cls:
        mock_ctx.return_value.__aenter__.return_value = mock_db_session

        usage_instance = AsyncMock()
        mock_usage_cls.return_value = usage_instance
        # Shopify balance is still 98.00 (or higher) -> NO ROLLOVER
        usage_instance.get_subscription_status.return_value = {
            "lineItems": [{
                "plan": {
                    "pricingDetails": {
                        "__typename": "AppUsagePricing",
                        "cappedAmount": {"amount": "100.00"},
                        "balanceUsed": {"amount": "98.00"},
                    }
                }
            }]
        }

        res = await reconcile_rollovers_once()
        assert res["checked"] == 1
        assert res["reactivated"] == 0
        # Status MUST still be SUSPENDED
        assert sub.status == SubscriptionStatus.SUSPENDED


@pytest.mark.asyncio
async def test_rollover_reconciler_strict_rollover_reactivates_and_drains():
    """Test that when Shopify balanceUsed drops, shop is reactivated, audit logged, and pending commissions drained."""
    sub = MagicMock(spec=ShopSubscription)
    sub.id = "sub-1"
    sub.shop_id = "shop-1"
    sub.status = SubscriptionStatus.SUSPENDED
    sub.shopify_subscription_id = "gid://shopify/AppSubscription/1"
    sub.is_active = True
    sub.shop_subscription_metadata = {"suspended_balance_used": 98.0}

    shop = MagicMock(spec=Shop)
    shop.id = "shop-1"
    shop.shop_domain = "test.myshopify.com"
    shop.access_token = "token"
    shop.is_active = False

    result_mock = MagicMock()
    result_mock.all.return_value = [(sub, shop)]

    mock_db_session = AsyncMock()
    mock_db_session.execute.return_value = result_mock
    mock_db_session.get.side_effect = lambda model, id_: sub if model == ShopSubscription else shop

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context") as mock_ctx, \
         patch("app.domains.billing.services.rollover_reconciler.ShopifyUsageBillingServiceV2") as mock_usage_cls, \
         patch("app.domains.billing.services.rollover_reconciler.drain_pending_commissions", new_callable=AsyncMock) as mock_drain:
        mock_ctx.return_value.__aenter__.return_value = mock_db_session
        mock_drain.return_value = 2

        usage_instance = AsyncMock()
        mock_usage_cls.return_value = usage_instance
        # Shopify balance dropped from $98 to $0.00 -> TRUE ROLLOVER!
        usage_instance.get_subscription_status.return_value = {
            "lineItems": [{
                "plan": {
                    "pricingDetails": {
                        "__typename": "AppUsagePricing",
                        "cappedAmount": {"amount": "100.00"},
                        "balanceUsed": {"amount": "0.00"},
                    }
                }
            }]
        }

        res = await reconcile_rollovers_once()
        assert res["checked"] == 1
        assert res["reactivated"] == 1
        assert res["drained_commissions"] == 2
        # Shop & sub reactivated
        assert sub.status == SubscriptionStatus.ACTIVE
        assert shop.is_active is True
        assert "suspended_balance_used" not in sub.shop_subscription_metadata
        mock_drain.assert_called_once_with("shop-1")


@pytest.mark.asyncio
async def test_legacy_rollover_records_baseline_when_balance_positive():
    """Test that a legacy suspended shop with balance > 0 is NOT prematurely reactivated."""
    sub = MagicMock(spec=ShopSubscription)
    sub.id = "sub-legacy-1"
    sub.shop_id = "shop-legacy-1"
    sub.status = SubscriptionStatus.SUSPENDED
    sub.shopify_subscription_id = "gid://shopify/AppSubscription/legacy"
    sub.is_active = True
    sub.shop_subscription_metadata = {}  # No baseline recorded

    shop = MagicMock(spec=Shop)
    shop.id = "shop-legacy-1"
    shop.shop_domain = "legacy.myshopify.com"
    shop.access_token = "token"
    shop.is_active = False

    result_mock = MagicMock()
    result_mock.all.return_value = [(sub, shop)]

    mock_db_session = AsyncMock()
    mock_db_session.execute.return_value = result_mock
    mock_db_session.get.side_effect = lambda model, id_: sub if model == ShopSubscription else shop

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context") as mock_ctx, \
         patch("app.domains.billing.services.rollover_reconciler.ShopifyUsageBillingServiceV2") as mock_usage_cls:
        mock_ctx.return_value.__aenter__.return_value = mock_db_session

        usage_instance = AsyncMock()
        mock_usage_cls.return_value = usage_instance
        # Shopify balance is $95 on a $100 cap -> capacity available, but NOT a reset!
        usage_instance.get_subscription_status.return_value = {
            "lineItems": [{
                "plan": {
                    "pricingDetails": {
                        "__typename": "AppUsagePricing",
                        "cappedAmount": {"amount": "100.00"},
                        "balanceUsed": {"amount": "95.00"},
                    }
                }
            }]
        }

        res = await reconcile_rollovers_once()
        assert res["checked"] == 1
        assert res["reactivated"] == 0
        assert sub.status == SubscriptionStatus.SUSPENDED
        # Baseline must have been saved into metadata
        assert sub.shop_subscription_metadata["suspended_balance_used"] == 95.0


@pytest.mark.asyncio
async def test_legacy_rollover_reactivates_when_balance_zero():
    """Test that a legacy suspended shop with balance == 0.00 reactivates immediately."""
    sub = MagicMock(spec=ShopSubscription)
    sub.id = "sub-legacy-2"
    sub.shop_id = "shop-legacy-2"
    sub.status = SubscriptionStatus.SUSPENDED
    sub.shopify_subscription_id = "gid://shopify/AppSubscription/legacy2"
    sub.is_active = True
    sub.shop_subscription_metadata = {}  # No baseline recorded

    shop = MagicMock(spec=Shop)
    shop.id = "shop-legacy-2"
    shop.shop_domain = "legacy2.myshopify.com"
    shop.access_token = "token"
    shop.is_active = False

    result_mock = MagicMock()
    result_mock.all.return_value = [(sub, shop)]

    mock_db_session = AsyncMock()
    mock_db_session.execute.return_value = result_mock
    mock_db_session.get.side_effect = lambda model, id_: sub if model == ShopSubscription else shop

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context") as mock_ctx, \
         patch("app.domains.billing.services.rollover_reconciler.ShopifyUsageBillingServiceV2") as mock_usage_cls, \
         patch("app.domains.billing.services.rollover_reconciler.drain_pending_commissions", new_callable=AsyncMock) as mock_drain:
        mock_ctx.return_value.__aenter__.return_value = mock_db_session
        mock_drain.return_value = 0

        usage_instance = AsyncMock()
        mock_usage_cls.return_value = usage_instance
        # Shopify balance is $0.00 -> true rollover!
        usage_instance.get_subscription_status.return_value = {
            "lineItems": [{
                "plan": {
                    "pricingDetails": {
                        "__typename": "AppUsagePricing",
                        "cappedAmount": {"amount": "100.00"},
                        "balanceUsed": {"amount": "0.00"},
                    }
                }
            }]
        }

        res = await reconcile_rollovers_once()
        assert res["checked"] == 1
        assert res["reactivated"] == 1
        assert sub.status == SubscriptionStatus.ACTIVE
        assert shop.is_active is True
