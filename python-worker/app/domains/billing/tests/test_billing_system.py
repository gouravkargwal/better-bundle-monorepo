"""
Comprehensive Test Suite for Billing System

This test suite covers all components of the billing system including
attribution, fraud detection, notifications, and end-to-end workflows.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any

from prisma import Prisma

from ..services.billing_service import BillingService
from ..services.attribution_engine import AttributionEngine, AttributionContext
from ..services.billing_calculator import BillingCalculator
from ..services.shopify_billing_service import ShopifyBillingService
from ..services.fraud_detection_service import FraudDetectionService
from ..services.notification_service import BillingNotificationService
from ..repositories.billing_repository import BillingRepository
from ..models.attribution_models import PurchaseEvent, AttributionResult


class TestBillingSystem:
    """Test suite for the complete billing system."""

    @pytest.fixture
    async def prisma(self):
        """Mock Prisma client for testing."""
        prisma = Mock(spec=Prisma)
        prisma.userInteraction = Mock()
        prisma.userSession = Mock()
        prisma.purchaseAttribution = Mock()
        prisma.billingPlan = Mock()
        prisma.billingInvoice = Mock()
        prisma.shop = Mock()
        return prisma

    @pytest.fixture
    def billing_service(self, prisma):
        """Billing service instance for testing."""
        return BillingService(prisma)

    @pytest.fixture
    def sample_shop_id(self):
        """Sample shop ID for testing."""
        return "test-shop-123"

    @pytest.fixture
    def sample_customer_id(self):
        """Sample customer ID for testing."""
        return "customer-456"

    @pytest.fixture
    def sample_interactions(self):
        """Sample user interactions for testing."""
        return [
            {
                "id": "interaction-1",
                "sessionId": "session-1",
                "customerId": "customer-456",
                "extension": "venus",
                "action": "recommendation_click",
                "timestamp": datetime.utcnow() - timedelta(hours=2),
                "metadata": {"product_id": "product-123", "recommendation_id": "rec-1"},
            },
            {
                "id": "interaction-2",
                "sessionId": "session-1",
                "customerId": "customer-456",
                "extension": "atlas",
                "action": "view",
                "timestamp": datetime.utcnow() - timedelta(hours=1),
                "metadata": {"product_id": "product-123"},
            },
            {
                "id": "interaction-3",
                "sessionId": "session-2",
                "customerId": "customer-456",
                "extension": "phoenix",
                "action": "click",
                "timestamp": datetime.utcnow() - timedelta(minutes=30),
                "metadata": {"product_id": "product-456"},
            },
        ]

    @pytest.fixture
    def sample_purchase(self):
        """Sample purchase event for testing."""
        return PurchaseEvent(
            order_id="order-789",
            customer_id="customer-456",
            shop_id="test-shop-123",
            total_amount=Decimal("99.99"),
            products=[
                {"id": "product-123", "price": Decimal("49.99"), "quantity": 1},
                {"id": "product-456", "price": Decimal("49.99"), "quantity": 1},
            ],
            created_at=datetime.utcnow(),
        )

    @pytest.fixture
    def sample_billing_period(self):
        """Sample billing period for testing."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        return {"start_date": start_date, "end_date": end_date, "cycle": "monthly"}


class TestAttributionEngine(TestBillingSystem):
    """Test attribution engine functionality."""

    async def test_direct_attribution(
        self, billing_service, sample_purchase, sample_interactions
    ):
        """Test direct attribution calculation."""
        # Mock recent interactions
        billing_service.prisma.userInteraction.findMany = AsyncMock(
            return_value=sample_interactions
        )

        # Create attribution context
        context = AttributionContext(
            shop_id=sample_purchase.shop_id,
            customer_id=sample_purchase.customer_id,
            purchase_amount=sample_purchase.total_amount,
            purchase_products=sample_purchase.products,
            purchase_time=sample_purchase.created_at,
        )

        # Calculate attribution
        result = billing_service.attribution_engine.calculate_attribution(context)

        # Verify attribution result
        assert result is not None
        assert result.total_attributed_revenue > 0
        assert len(result.attribution_breakdown) > 0

        # Check that recent interactions are attributed
        venus_attribution = next(
            (
                attr
                for attr in result.attribution_breakdown
                if attr.extension == "venus"
            ),
            None,
        )
        assert venus_attribution is not None
        assert venus_attribution.attributed_revenue > 0

    async def test_cross_extension_attribution(self, billing_service, sample_purchase):
        """Test cross-extension attribution."""
        # Mock interactions from multiple extensions
        multi_extension_interactions = [
            {
                "id": "interaction-1",
                "sessionId": "session-1",
                "customerId": "customer-456",
                "extension": "venus",
                "action": "recommendation_click",
                "timestamp": datetime.utcnow() - timedelta(hours=1),
                "metadata": {"product_id": "product-123"},
            },
            {
                "id": "interaction-2",
                "sessionId": "session-1",
                "customerId": "customer-456",
                "extension": "atlas",
                "action": "view",
                "timestamp": datetime.utcnow() - timedelta(minutes=30),
                "metadata": {"product_id": "product-123"},
            },
        ]

        billing_service.prisma.userInteraction.findMany = AsyncMock(
            return_value=multi_extension_interactions
        )

        context = AttributionContext(
            shop_id=sample_purchase.shop_id,
            customer_id=sample_purchase.customer_id,
            purchase_amount=sample_purchase.total_amount,
            purchase_products=sample_purchase.products,
            purchase_time=sample_purchase.created_at,
        )

        result = billing_service.attribution_engine.calculate_attribution(context)

        # Verify cross-extension attribution
        assert len(result.attribution_breakdown) >= 2

        # Check that both extensions get attribution
        venus_attr = next(
            (
                attr
                for attr in result.attribution_breakdown
                if attr.extension == "venus"
            ),
            None,
        )
        atlas_attr = next(
            (
                attr
                for attr in result.attribution_breakdown
                if attr.extension == "atlas"
            ),
            None,
        )

        assert venus_attr is not None
        assert atlas_attr is not None

        # Primary extension should get more attribution
        assert venus_attr.attributed_revenue > atlas_attr.attributed_revenue


class TestFraudDetection(TestBillingSystem):
    """Test fraud detection functionality."""

    async def test_excessive_interactions_detection(
        self, billing_service, sample_shop_id
    ):
        """Test detection of excessive interactions."""
        # Mock excessive interactions (more than threshold)
        excessive_interactions = []
        for i in range(1500):  # Exceeds 1000 per hour threshold
            excessive_interactions.append(
                {
                    "id": f"interaction-{i}",
                    "sessionId": f"session-{i}",
                    "customerId": f"customer-{i}",
                    "extension": "venus",
                    "action": "click",
                    "timestamp": datetime.utcnow() - timedelta(minutes=i),
                    "metadata": {},
                    "session": {
                        "id": f"session-{i}",
                        "ipAddress": "192.168.1.1",
                        "userAgent": "Mozilla/5.0",
                        "duration": 30,
                    },
                }
            )

        billing_service.prisma.userInteraction.findMany = AsyncMock(
            return_value=excessive_interactions
        )
        billing_service.prisma.purchaseAttribution.findMany = AsyncMock(return_value=[])

        # Run fraud detection
        result = await billing_service.fraud_detection_service.analyze_shop_fraud_risk(
            sample_shop_id, datetime.utcnow() - timedelta(days=1), datetime.utcnow()
        )

        # Verify fraud detection
        assert result.risk_level.value in ["medium", "high", "critical"]
        assert "excessive_interactions" in [ft.value for ft in result.fraud_types]
        assert result.confidence_score > 0.5

    async def test_rapid_fire_clicks_detection(self, billing_service, sample_shop_id):
        """Test detection of rapid-fire clicks."""
        # Mock rapid-fire clicks (more than 50 per minute)
        rapid_clicks = []
        base_time = datetime.utcnow()
        for i in range(60):  # 60 clicks in one minute
            rapid_clicks.append(
                {
                    "id": f"click-{i}",
                    "sessionId": "session-1",
                    "customerId": "customer-1",
                    "extension": "venus",
                    "action": "click",
                    "timestamp": base_time - timedelta(seconds=i),
                    "metadata": {},
                    "session": {
                        "id": "session-1",
                        "ipAddress": "192.168.1.1",
                        "userAgent": "Mozilla/5.0",
                        "duration": 1,
                    },
                }
            )

        billing_service.prisma.userInteraction.findMany = AsyncMock(
            return_value=rapid_clicks
        )
        billing_service.prisma.purchaseAttribution.findMany = AsyncMock(return_value=[])

        # Run fraud detection
        result = await billing_service.fraud_detection_service.analyze_shop_fraud_risk(
            sample_shop_id, datetime.utcnow() - timedelta(hours=1), datetime.utcnow()
        )

        # Verify rapid-fire detection
        assert "rapid_fire_clicks" in [ft.value for ft in result.fraud_types]
        assert result.suspicious_metrics["rapid_fire_clicks"]["detected"] is True

    async def test_bot_traffic_detection(self, billing_service, sample_shop_id):
        """Test detection of bot traffic."""
        # Mock bot-like traffic (same IP, short sessions)
        bot_interactions = []
        for i in range(200):  # Many interactions from same IP
            bot_interactions.append(
                {
                    "id": f"bot-{i}",
                    "sessionId": f"session-{i}",
                    "customerId": f"customer-{i}",
                    "extension": "venus",
                    "action": "view",
                    "timestamp": datetime.utcnow() - timedelta(minutes=i),
                    "metadata": {},
                    "session": {
                        "id": f"session-{i}",
                        "ipAddress": "192.168.1.100",  # Same IP
                        "userAgent": "Bot/1.0",  # Bot user agent
                        "duration": 1,  # Very short sessions
                    },
                }
            )

        billing_service.prisma.userInteraction.findMany = AsyncMock(
            return_value=bot_interactions
        )
        billing_service.prisma.purchaseAttribution.findMany = AsyncMock(return_value=[])

        # Run fraud detection
        result = await billing_service.fraud_detection_service.analyze_shop_fraud_risk(
            sample_shop_id, datetime.utcnow() - timedelta(hours=1), datetime.utcnow()
        )

        # Verify bot detection
        assert "bot_traffic" in [ft.value for ft in result.fraud_types]
        assert result.suspicious_metrics["bot_traffic"]["detected"] is True


class TestBillingCalculator(TestBillingSystem):
    """Test billing calculator functionality."""

    async def test_performance_tier_calculation(
        self, billing_service, sample_shop_id, sample_billing_period
    ):
        """Test performance tier fee calculation."""
        # Mock billing plan with performance tiers
        billing_plan = Mock()
        billing_plan.id = "plan-123"
        billing_plan.type = "revenue_share"
        billing_plan.configuration = {
            "performance_tiers": [
                {"name": "Tier 1", "min_revenue": 0, "max_revenue": 5000, "rate": 0.03},
                {
                    "name": "Tier 2",
                    "min_revenue": 5000,
                    "max_revenue": 25000,
                    "rate": 0.025,
                },
                {
                    "name": "Tier 3",
                    "min_revenue": 25000,
                    "max_revenue": None,
                    "rate": 0.02,
                },
            ]
        }

        billing_service.billing_repository.get_billing_plan = AsyncMock(
            return_value=billing_plan
        )

        # Test different revenue levels
        test_cases = [
            {"revenue": 3000, "expected_rate": 0.03},  # Tier 1
            {"revenue": 10000, "expected_rate": 0.025},  # Tier 2
            {"revenue": 50000, "expected_rate": 0.02},  # Tier 3
        ]

        for case in test_cases:
            metrics_data = {
                "attributed_revenue": case["revenue"],
                "total_interactions": 1000,
                "total_conversions": 50,
                "conversion_rate": 0.05,
                "average_order_value": case["revenue"] / 50,
            }

            result = await billing_service.billing_calculator.calculate_billing_fee(
                sample_shop_id, sample_billing_period, metrics_data
            )

            # Verify tier calculation
            assert (
                result["calculation"]["base_fee"]
                == case["revenue"] * case["expected_rate"]
            )
            assert result["plan_id"] == "plan-123"

    async def test_fraud_adjustment(
        self, billing_service, sample_shop_id, sample_billing_period
    ):
        """Test fraud adjustment in billing calculation."""
        # Mock billing plan
        billing_plan = Mock()
        billing_plan.id = "plan-123"
        billing_plan.type = "revenue_share"
        billing_plan.configuration = {"revenue_share_rate": 0.03}

        billing_service.billing_repository.get_billing_plan = AsyncMock(
            return_value=billing_plan
        )

        # Test with fraud adjustment
        metrics_data = {
            "attributed_revenue": 10000,
            "fraud_adjustment": 0.5,  # 50% reduction
            "fraud_risk_level": "high",
            "total_interactions": 1000,
            "total_conversions": 50,
            "conversion_rate": 0.05,
            "average_order_value": 200,
        }

        result = await billing_service.billing_calculator.calculate_billing_fee(
            sample_shop_id, sample_billing_period, metrics_data
        )

        # Verify fraud adjustment
        expected_fee = 10000 * 0.03 * 0.5  # 50% reduction
        assert result["calculation"]["final_fee"] == expected_fee
        assert result["metrics"]["fraud_adjustment"] == 0.5


class TestNotificationService(TestBillingSystem):
    """Test notification service functionality."""

    @patch("httpx.AsyncClient")
    async def test_invoice_notification(
        self, mock_client, billing_service, sample_shop_id
    ):
        """Test invoice notification sending."""
        # Mock successful email response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Mock shop data
        billing_service.prisma.shop.find_unique = AsyncMock(
            return_value=Mock(email="test@example.com")
        )

        # Test invoice notification
        invoice_data = {
            "invoice_number": "INV-001",
            "total": 150.00,
            "due_date": "2024-02-01",
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
        }

        result = await billing_service.notification_service.send_invoice_notification(
            sample_shop_id, invoice_data, "test@example.com"
        )

        assert result is True

    @patch("httpx.AsyncClient")
    async def test_fraud_alert_notification(
        self, mock_client, billing_service, sample_shop_id
    ):
        """Test fraud alert notification sending."""
        # Mock successful email response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Test fraud alert
        fraud_data = {
            "risk_level": "high",
            "fraud_types": ["excessive_interactions", "bot_traffic"],
            "confidence_score": 0.85,
            "recommendations": ["Implement rate limiting", "Block suspicious IPs"],
        }

        result = await billing_service.notification_service.send_fraud_alert(
            sample_shop_id, fraud_data, "test@example.com"
        )

        assert result is True


class TestEndToEndBilling(TestBillingSystem):
    """Test end-to-end billing workflows."""

    async def test_complete_monthly_billing_workflow(
        self, billing_service, sample_shop_id
    ):
        """Test complete monthly billing workflow."""
        # Mock all dependencies
        billing_plan = Mock()
        billing_plan.id = "plan-123"
        billing_plan.type = "revenue_share"
        billing_plan.configuration = {"revenue_share_rate": 0.03}

        billing_service.billing_repository.get_billing_plan = AsyncMock(
            return_value=billing_plan
        )
        billing_service.billing_repository.get_shop_attribution_data = AsyncMock(
            return_value={
                "attributed_revenue": 10000,
                "total_interactions": 5000,
                "total_conversions": 100,
                "conversion_rate": 0.02,
                "average_order_value": 100,
            }
        )

        # Mock fraud detection (low risk)
        fraud_result = Mock()
        fraud_result.risk_level.value = "low"
        fraud_result.fraud_types = []
        fraud_result.confidence_score = 0.1
        fraud_result.recommendations = []
        fraud_result.suspicious_metrics = {}

        billing_service.fraud_detection_service.analyze_shop_fraud_risk = AsyncMock(
            return_value=fraud_result
        )

        # Run monthly billing
        result = await billing_service.calculate_monthly_billing(sample_shop_id)

        # Verify billing result
        assert result["shop_id"] == sample_shop_id
        assert result["calculation"]["final_fee"] == 300.0  # 10000 * 0.03
        assert result["metrics"]["attributed_revenue"] == 10000
        assert result["plan_id"] == "plan-123"
        assert "error" not in result

    async def test_high_fraud_risk_billing_workflow(
        self, billing_service, sample_shop_id
    ):
        """Test billing workflow with high fraud risk."""
        # Mock billing plan
        billing_plan = Mock()
        billing_plan.id = "plan-123"
        billing_plan.type = "revenue_share"
        billing_plan.configuration = {"revenue_share_rate": 0.03}

        billing_service.billing_repository.get_billing_plan = AsyncMock(
            return_value=billing_plan
        )
        billing_service.billing_repository.get_shop_attribution_data = AsyncMock(
            return_value={
                "attributed_revenue": 10000,
                "total_interactions": 5000,
                "total_conversions": 100,
                "conversion_rate": 0.02,
                "average_order_value": 100,
            }
        )

        # Mock high fraud risk
        fraud_result = Mock()
        fraud_result.risk_level.value = "high"
        fraud_result.fraud_types = [Mock(value="excessive_interactions")]
        fraud_result.confidence_score = 0.8
        fraud_result.recommendations = ["Implement rate limiting"]
        fraud_result.suspicious_metrics = {"excessive_interactions": {"detected": True}}

        billing_service.fraud_detection_service.analyze_shop_fraud_risk = AsyncMock(
            return_value=fraud_result
        )
        billing_service._send_fraud_alert_notification = AsyncMock()

        # Run monthly billing
        result = await billing_service.calculate_monthly_billing(sample_shop_id)

        # Verify fraud adjustment
        assert result["metrics"]["fraud_adjustment"] == 0.5
        assert result["metrics"]["fraud_risk_level"] == "high"
        assert result["calculation"]["final_fee"] == 150.0  # 50% reduction

        # Verify fraud alert was sent
        billing_service._send_fraud_alert_notification.assert_called_once()

    async def test_shopify_integration_workflow(self, billing_service, sample_shop_id):
        """Test billing workflow with Shopify integration."""
        # Mock all dependencies
        billing_plan = Mock()
        billing_plan.id = "plan-123"
        billing_plan.type = "revenue_share"
        billing_plan.configuration = {"revenue_share_rate": 0.03}

        billing_service.billing_repository.get_billing_plan = AsyncMock(
            return_value=billing_plan
        )
        billing_service.billing_repository.get_shop_attribution_data = AsyncMock(
            return_value={
                "attributed_revenue": 10000,
                "total_interactions": 5000,
                "total_conversions": 100,
                "conversion_rate": 0.02,
                "average_order_value": 100,
            }
        )

        # Mock fraud detection (low risk)
        fraud_result = Mock()
        fraud_result.risk_level.value = "low"
        fraud_result.fraud_types = []
        fraud_result.confidence_score = 0.1
        fraud_result.recommendations = []
        fraud_result.suspicious_metrics = {}

        billing_service.fraud_detection_service.analyze_shop_fraud_risk = AsyncMock(
            return_value=fraud_result
        )

        # Mock Shopify charge creation
        shopify_charge = Mock()
        shopify_charge.id = "charge-123"
        shopify_charge.status = "pending"
        shopify_charge.amount = Decimal("300.00")
        shopify_charge.currency = "USD"
        shopify_charge.description = "Better Bundle - 2024-01"
        shopify_charge.created_at = datetime.utcnow()

        billing_service.shopify_billing_service.create_monthly_billing_charge = (
            AsyncMock(return_value=shopify_charge)
        )

        # Mock shop data
        shop = Mock()
        shop.domain = "test-shop.myshopify.com"
        shop.accessToken = "access-token-123"

        billing_service.prisma.shop.find_unique = AsyncMock(return_value=shop)

        # Run billing with Shopify integration
        result = await billing_service.process_monthly_billing_with_shopify(
            sample_shop_id
        )

        # Verify Shopify integration
        assert result["shopify_charge"]["id"] == "charge-123"
        assert result["shopify_charge"]["status"] == "pending"
        assert result["shopify_charge"]["amount"] == 300.0

        # Verify Shopify charge was created
        billing_service.shopify_billing_service.create_monthly_billing_charge.assert_called_once()


class TestBillingRepository(TestBillingSystem):
    """Test billing repository functionality."""

    async def test_billing_plan_creation(self, billing_service, sample_shop_id):
        """Test billing plan creation."""
        # Mock plan creation
        created_plan = Mock()
        created_plan.id = "plan-123"
        created_plan.name = "Pay-as-Performance Plan"
        created_plan.type = "revenue_share"
        created_plan.status = "active"
        created_plan.configuration = {"revenue_share_rate": 0.03}
        created_plan.createdAt = datetime.utcnow()

        billing_service.billing_repository.create_billing_plan = AsyncMock(
            return_value=created_plan
        )

        # Create billing plan
        result = await billing_service.create_default_billing_plan(
            sample_shop_id, "test-shop.myshopify.com"
        )

        # Verify plan creation
        assert result["plan_id"] == "plan-123"
        assert result["name"] == "Pay-as-Performance Plan"
        assert result["type"] == "revenue_share"
        assert result["status"] == "active"


# Integration test runner
async def run_integration_tests():
    """Run all integration tests."""
    print("🧪 Running Billing System Integration Tests...")

    # Initialize test suite
    test_suite = TestBillingSystem()
    prisma = await test_suite.prisma()
    billing_service = test_suite.billing_service(prisma)

    # Run attribution tests
    print("📊 Testing Attribution Engine...")
    attribution_tests = TestAttributionEngine()
    await attribution_tests.test_direct_attribution(
        billing_service, test_suite.sample_purchase(), test_suite.sample_interactions()
    )
    await attribution_tests.test_cross_extension_attribution(
        billing_service, test_suite.sample_purchase()
    )
    print("✅ Attribution Engine tests passed")

    # Run fraud detection tests
    print("🛡️ Testing Fraud Detection...")
    fraud_tests = TestFraudDetection()
    await fraud_tests.test_excessive_interactions_detection(
        billing_service, test_suite.sample_shop_id()
    )
    await fraud_tests.test_rapid_fire_clicks_detection(
        billing_service, test_suite.sample_shop_id()
    )
    await fraud_tests.test_bot_traffic_detection(
        billing_service, test_suite.sample_shop_id()
    )
    print("✅ Fraud Detection tests passed")

    # Run billing calculator tests
    print("💰 Testing Billing Calculator...")
    calculator_tests = TestBillingCalculator()
    await calculator_tests.test_performance_tier_calculation(
        billing_service, test_suite.sample_shop_id(), test_suite.sample_billing_period()
    )
    await calculator_tests.test_fraud_adjustment(
        billing_service, test_suite.sample_shop_id(), test_suite.sample_billing_period()
    )
    print("✅ Billing Calculator tests passed")

    # Run notification tests
    print("📧 Testing Notification Service...")
    notification_tests = TestNotificationService()
    await notification_tests.test_invoice_notification(
        billing_service, test_suite.sample_shop_id()
    )
    await notification_tests.test_fraud_alert_notification(
        billing_service, test_suite.sample_shop_id()
    )
    print("✅ Notification Service tests passed")

    # Run end-to-end tests
    print("🔄 Testing End-to-End Workflows...")
    e2e_tests = TestEndToEndBilling()
    await e2e_tests.test_complete_monthly_billing_workflow(
        billing_service, test_suite.sample_shop_id()
    )
    await e2e_tests.test_high_fraud_risk_billing_workflow(
        billing_service, test_suite.sample_shop_id()
    )
    await e2e_tests.test_shopify_integration_workflow(
        billing_service, test_suite.sample_shop_id()
    )
    print("✅ End-to-End Workflow tests passed")

    # Run repository tests
    print("🗄️ Testing Billing Repository...")
    repository_tests = TestBillingRepository()
    await repository_tests.test_billing_plan_creation(
        billing_service, test_suite.sample_shop_id()
    )
    print("✅ Billing Repository tests passed")

    print("🎉 All billing system tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())
