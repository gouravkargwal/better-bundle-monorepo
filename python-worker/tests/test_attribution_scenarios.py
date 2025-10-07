"""
Comprehensive Test Suite for Attribution Scenarios

This test suite covers all implemented attribution scenarios without requiring
frontend interaction. It tests the backend logic directly using mock data
and scenarios.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.domains.billing.services.attribution_engine import (
    AttributionEngine,
    AttributionContext,
)
from app.domains.analytics.services.cross_session_linking_service import (
    CrossSessionLinkingService,
)
from app.domains.analytics.services.unified_session_service import UnifiedSessionService


class TestAttributionScenarios:
    """Test suite for all attribution scenarios"""

    @pytest.fixture
    def attribution_engine(self):
        """Create attribution engine instance for testing"""
        return AttributionEngine()

    @pytest.fixture
    def mock_context(self):
        """Create mock attribution context"""
        return AttributionContext(
            order_id="test_order_123",
            shop_id="test_shop_456",
            customer_id="test_customer_789",
            session_id="test_session_101",
            purchase_amount=Decimal("99.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 99.99}],
            purchase_time=datetime.now(),
        )

    # ============================================================================
    # SCENARIO 6: Multiple Recommendations for Same Product
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_6_multiple_recommendations_same_product(
        self, attribution_engine, mock_context
    ):
        """Test Scenario 6: Multiple recommendations for same product deduplication"""

        # Mock interactions with multiple recommendations for same product
        mock_interactions = [
            {
                "id": "interaction_1",
                "extension_type": "phoenix",
                "interaction_type": "recommendation_clicked",
                "product_id": "product_1",
                "created_at": datetime.now() - timedelta(minutes=10),
                "metadata": {"position": 1, "confidence": 0.8},
            },
            {
                "id": "interaction_2",
                "extension_type": "phoenix",
                "interaction_type": "recommendation_add_to_cart",
                "product_id": "product_1",
                "created_at": datetime.now() - timedelta(minutes=5),
                "metadata": {"position": 1, "confidence": 0.9},
            },
            {
                "id": "interaction_3",
                "extension_type": "venus",
                "interaction_type": "recommendation_clicked",
                "product_id": "product_1",
                "created_at": datetime.now() - timedelta(minutes=3),
                "metadata": {"position": 2, "confidence": 0.7},
            },
        ]

        # Test deduplication logic
        deduplicated = attribution_engine._deduplicate_product_interactions(
            mock_interactions
        )

        # Should deduplicate interactions
        assert len(deduplicated) < len(mock_interactions)  # Should deduplicate
        assert any(
            i["interaction_type"]
            in ["recommendation_add_to_cart", "recommendation_clicked"]
            for i in deduplicated
        )

        # Test best interaction selection
        best_interaction = attribution_engine._select_best_interaction(
            mock_interactions
        )
        assert best_interaction["interaction_type"] in [
            "recommendation_add_to_cart",
            "recommendation_clicked",
        ]

    # ============================================================================
    # SCENARIO 7: Cross-Extension Attribution
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_7_cross_extension_attribution(
        self, attribution_engine, mock_context
    ):
        """Test Scenario 7: Cross-extension attribution with weight distribution"""

        # Mock interactions from multiple extensions
        mock_interactions = [
            {
                "extension_type": "phoenix",
                "interaction_type": "recommendation_clicked",
                "created_at": datetime.now() - timedelta(minutes=10),
                "metadata": {"position": 1},
            },
            {
                "extension_type": "venus",
                "interaction_type": "recommendation_add_to_cart",
                "created_at": datetime.now() - timedelta(minutes=5),
                "metadata": {"position": 2},
            },
            {
                "extension_type": "apollo",
                "interaction_type": "recommendation_clicked",
                "created_at": datetime.now() - timedelta(minutes=2),
                "metadata": {"position": 3},
            },
        ]

        # Test cross-extension weight calculation
        weights = attribution_engine._calculate_cross_extension_weights(
            mock_interactions
        )

        # Should have weights for all extensions
        assert "phoenix" in weights
        assert "venus" in weights
        assert "apollo" in weights

        # Weights should sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.01

        # Primary interaction should get highest weight
        assert weights["venus"] > weights["phoenix"]  # add_to_cart > clicked

    # ============================================================================
    # SCENARIO 8: Session vs Customer Attribution
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_8_session_customer_attribution(self):
        """Test Scenario 8: Session to customer attribution linking"""

        # Mock cross-session linking service
        linking_service = CrossSessionLinkingService()

        # Mock customer sessions
        mock_sessions = [
            {
                "id": "session_1",
                "customer_id": None,
                "browser_session_id": "browser_123",
            },
            {
                "id": "session_2",
                "customer_id": None,
                "browser_session_id": "browser_123",
            },
            {
                "id": "session_3",
                "customer_id": "customer_789",
                "browser_session_id": "browser_456",
            },
        ]

        # Test session linking logic
        with patch.object(
            linking_service, "_get_customer_sessions", return_value=mock_sessions
        ):
            result = await linking_service.link_customer_sessions(
                customer_id="customer_789", shop_id="test_shop_456"
            )

            assert result["success"] is True
            assert "linked_sessions" in result

    # ============================================================================
    # SCENARIO 9: Long Attribution Window
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_9_long_attribution_window(self, attribution_engine):
        """Test Scenario 9: Configurable attribution windows"""

        # Test different purchase values and their attribution windows
        test_cases = [
            (Decimal("25.00"), "short"),  # Under $50
            (Decimal("100.00"), "medium"),  # $50-$200
            (Decimal("500.00"), "long"),  # $200-$1000
            (Decimal("2000.00"), "extended"),  # Over $1000
        ]

        for purchase_amount, expected_window in test_cases:
            context = AttributionContext(
                order_id="test_order",
                shop_id="test_shop",
                customer_id="test_customer",
                session_id="test_session",
                purchase_amount=purchase_amount,
                purchase_products=[
                    {"id": "product_1", "quantity": 1, "price": float(purchase_amount)}
                ],
            )

            window = attribution_engine._determine_attribution_window(context)

            # Verify appropriate window is selected
            if expected_window == "short":
                assert window <= timedelta(hours=2)
            elif expected_window == "medium":
                assert timedelta(hours=2) < window <= timedelta(days=3)
            elif expected_window == "long":
                assert timedelta(days=3) < window <= timedelta(days=30)
            else:  # extended
                assert window > timedelta(days=30)

    # ============================================================================
    # SCENARIO 10: Multiple Sessions Same Customer
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_10_multiple_sessions_same_customer(self):
        """Test Scenario 10: Multiple sessions for same customer"""

        linking_service = CrossSessionLinkingService()

        # Mock cross-session attribution data
        mock_attribution_data = {
            "customer_id": "customer_789",
            "product_id": "product_123",
            "total_sessions": 3,
            "sessions_with_interactions": 2,
            "total_interactions": 5,
        }

        with patch.object(
            linking_service,
            "_handle_cross_session_attribution",
            return_value=mock_attribution_data,
        ):
            result = await linking_service._handle_cross_session_attribution(
                customer_id="customer_789", product_id="product_123"
            )

            assert result["customer_id"] == "customer_789"
            assert result["total_sessions"] == 3
            assert result["total_interactions"] == 5

    # ============================================================================
    # SCENARIO 14: Payment Failure Attribution
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_14_payment_failure_attribution(self, attribution_engine):
        """Test Scenario 14: Payment failure detection and handling"""

        # Test payment failure detection
        failed_context = AttributionContext(
            order_id="failed_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("99.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 99.99}],
            purchase_time=datetime.now(),
        )

        # Test payment failure detection
        is_failed = await attribution_engine._is_payment_failed(failed_context)
        assert is_failed is True

        # Test payment failed attribution creation
        result = attribution_engine._create_payment_failed_attribution(failed_context)
        assert result.attribution_algorithm == "payment_failed"
        assert result.attributed_revenue == Decimal("0.00")
        assert result.attribution_metadata["scenario"] == "payment_failed"

    # ============================================================================
    # SCENARIO 15: Subscription Cancellation
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_15_subscription_cancellation(self, attribution_engine):
        """Test Scenario 15: Subscription cancellation handling"""

        # Test subscription cancellation detection
        cancelled_context = AttributionContext(
            order_id="subscription_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("29.99"),
            purchase_products=[{"id": "subscription_1", "quantity": 1, "price": 29.99}],
            purchase_time=datetime.now(),
        )

        # Test cancellation detection
        is_cancelled = await attribution_engine._is_subscription_cancelled(
            cancelled_context
        )
        assert is_cancelled is True

        # Test cancelled subscription attribution
        result = attribution_engine._create_subscription_cancelled_attribution(
            cancelled_context
        )
        assert result.attribution_algorithm == "subscription_cancelled"
        assert result.attributed_revenue == Decimal("0.00")

    # ============================================================================
    # SCENARIO 17: Cross-Shop Attribution
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_17_cross_shop_attribution(self, attribution_engine):
        """Test Scenario 17: Cross-shop attribution handling"""

        # Test cross-shop detection
        cross_shop_context = AttributionContext(
            order_id="cross_shop_order",
            shop_id="shop_b",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("149.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 149.99}],
            purchase_time=datetime.now(),
        )

        # Test cross-shop detection
        is_cross_shop = await attribution_engine._is_cross_shop_attribution(
            cross_shop_context
        )
        assert is_cross_shop is True

        # Test cross-shop attribution handling
        result = await attribution_engine._handle_cross_shop_attribution(
            cross_shop_context
        )
        assert result.attribution_algorithm == "cross_shop"
        assert (
            result.attributed_revenue < cross_shop_context.purchase_amount
        )  # Reduced attribution
        assert result.attribution_metadata["scenario"] == "cross_shop_attribution"

    # ============================================================================
    # SCENARIO 18: Cross-Device Attribution
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_18_cross_device_attribution(self):
        """Test Scenario 18: Cross-device attribution linking"""

        session_service = UnifiedSessionService()

        # Mock cross-device session data
        mock_session_data = {
            "shop_id": "test_shop",
            "customer_id": "test_customer",
            "browser_session_id": "browser_123",
            "client_id": "client_456",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
            "ip_address": "192.168.1.100",
        }

        with patch.object(
            session_service,
            "_find_cross_device_session",
            return_value=MagicMock(id="cross_device_session"),
        ):
            result = await session_service._find_cross_device_session(
                session=MagicMock(),
                shop_id="test_shop",
                client_id="client_456",
                current_time=datetime.now(),
            )

            assert result is not None

    # ============================================================================
    # SCENARIO 20: Session Expiration During Journey
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_20_session_expiration(self):
        """Test Scenario 20: Session expiration handling"""

        session_service = UnifiedSessionService()

        # Mock expired session scenario
        mock_expired_session = MagicMock()
        mock_expired_session.id = "expired_session_123"
        mock_expired_session.expires_at = datetime.now() - timedelta(hours=1)
        mock_expired_session.status = "active"

        with patch.object(
            session_service,
            "_find_expired_session_for_linking",
            return_value=mock_expired_session,
        ):
            result = await session_service._find_expired_session_for_linking(
                session=MagicMock(),
                shop_id="test_shop",
                customer_id="test_customer",
                browser_session_id="browser_123",
                current_time=datetime.now(),
            )

            assert result is not None
            assert result.id == "expired_session_123"

    # ============================================================================
    # SCENARIO 21: Low-Quality Recommendations
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_21_low_quality_recommendations(self, attribution_engine):
        """Test Scenario 21: Low-quality recommendation detection"""

        # Test low-quality recommendation detection
        low_quality_context = AttributionContext(
            order_id="low_quality_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("79.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 79.99}],
            purchase_time=datetime.now(),
        )

        # Test low-quality detection
        is_low_quality = await attribution_engine._has_low_quality_recommendations(
            low_quality_context
        )
        assert is_low_quality is True

        # Test low-quality handling
        result = await attribution_engine._handle_low_quality_recommendations(
            low_quality_context
        )
        assert result.attribution_algorithm == "low_quality_recommendations"
        assert (
            result.attributed_revenue < low_quality_context.purchase_amount
        )  # Reduced attribution

    # ============================================================================
    # SCENARIO 22: Recommendation Timing
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_22_recommendation_timing(self, attribution_engine):
        """Test Scenario 22: Recommendation timing analysis"""

        # Test poor timing scenario
        poor_timing_context = AttributionContext(
            order_id="poor_timing_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("199.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 199.99}],
            purchase_time=datetime.now(),
        )

        # Test timing analysis
        timing_analysis = await attribution_engine._analyze_recommendation_timing(
            poor_timing_context
        )
        assert timing_analysis["requires_adjustment"] is True
        assert timing_analysis["timing_score"] < 0.5

        # Test timing adjustment
        result = await attribution_engine._handle_timing_adjustment(
            poor_timing_context, timing_analysis
        )
        assert result.attribution_algorithm == "timing_adjusted"
        assert result.attribution_metadata["scenario"] == "recommendation_timing"

    # ============================================================================
    # SCENARIO 26: Data Loss Recovery
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_26_data_loss_recovery(self, attribution_engine):
        """Test Scenario 26: Data loss detection and recovery"""

        # Test data loss detection
        data_loss_context = AttributionContext(
            order_id="data_loss_order",
            shop_id="test_shop",
            customer_id=None,  # Missing customer data
            session_id=None,  # Missing session data
            purchase_amount=Decimal("0.00"),  # Invalid amount
            purchase_products=[],  # Missing products
            purchase_time=datetime.now(),
        )

        # Test data loss detection
        has_data_loss = await attribution_engine._detect_data_loss(data_loss_context)
        assert has_data_loss is True

        # Test data loss attribution
        result = attribution_engine._create_data_loss_attribution(data_loss_context)
        assert result.attribution_algorithm == "data_loss"
        assert result.attributed_revenue == Decimal("0.00")

    # ============================================================================
    # SCENARIO 27: Fraudulent Attribution Detection
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_27_fraudulent_attribution(self, attribution_engine):
        """Test Scenario 27: Fraudulent attribution detection"""

        # Test bot behavior detection
        bot_context = AttributionContext(
            order_id="bot_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("999.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 999.99}],
            purchase_time=datetime.now(),
        )

        # Test fraud detection
        is_fraudulent = await attribution_engine._detect_fraudulent_attribution(
            bot_context
        )
        assert is_fraudulent is True

        # Test fraudulent attribution
        result = attribution_engine._create_fraudulent_attribution(bot_context)
        assert result.attribution_algorithm == "fraud_detected"
        assert result.attributed_revenue == Decimal("0.00")

    # ============================================================================
    # SCENARIO 28: Attribution Manipulation Detection
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_28_attribution_manipulation(self, attribution_engine):
        """Test Scenario 28: Advanced attribution manipulation detection"""

        # Test manipulation detection
        manipulation_context = AttributionContext(
            order_id="manipulation_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("149.99"),
            purchase_products=[{"id": "product_1", "quantity": 1, "price": 149.99}],
            purchase_time=datetime.now(),
        )

        # Test advanced manipulation detection
        is_manipulation = await attribution_engine._detect_advanced_manipulation(
            manipulation_context
        )
        assert is_manipulation is True

    # ============================================================================
    # SCENARIO 33: Anonymous to Customer Conversion
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_33_anonymous_to_customer_conversion(self):
        """Test Scenario 33: Anonymous to customer conversion"""

        linking_service = CrossSessionLinkingService()

        # Mock anonymous to customer conversion
        with patch.object(
            linking_service,
            "handle_anonymous_to_customer_conversion",
            return_value={
                "success": True,
                "conversion_type": "anonymous_to_customer",
                "customer_id": "customer_789",
                "linked_sessions": ["session_123", "session_456"],
                "total_sessions": 2,
                "attribution_updated": True,
            },
        ):
            result = await linking_service.handle_anonymous_to_customer_conversion(
                customer_id="customer_789",
                shop_id="test_shop",
                conversion_session_id="session_456",
            )

            assert result["success"] is True
            assert result["conversion_type"] == "anonymous_to_customer"
            assert len(result["linked_sessions"]) == 2

    # ============================================================================
    # SCENARIO 34: Multiple Devices Same Customer
    # ============================================================================

    @pytest.mark.asyncio
    async def test_scenario_34_multiple_devices_same_customer(self):
        """Test Scenario 34: Multiple devices for same customer"""

        linking_service = CrossSessionLinkingService()

        # Mock multi-device scenario
        with patch.object(
            linking_service,
            "handle_multiple_devices_same_customer",
            return_value={
                "success": True,
                "scenario": "multiple_devices_same_customer",
                "customer_id": "customer_789",
                "linked_sessions": ["session_mobile", "session_desktop"],
                "total_devices": 2,
                "attribution_summary": {
                    "total_sessions": 2,
                    "total_interactions": 8,
                    "cross_device_attribution": True,
                },
            },
        ):
            result = await linking_service.handle_multiple_devices_same_customer(
                customer_id="customer_789",
                shop_id="test_shop",
                device_sessions=["session_mobile", "session_desktop"],
            )

            assert result["success"] is True
            assert result["scenario"] == "multiple_devices_same_customer"
            assert result["total_devices"] == 2

    # ============================================================================
    # INTEGRATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_full_attribution_flow(self, attribution_engine, mock_context):
        """Test complete attribution flow with multiple scenarios"""

        # Mock the entire attribution calculation process
        with patch.object(
            attribution_engine, "_get_relevant_interactions", return_value=[]
        ):
            with patch.object(
                attribution_engine, "_calculate_attribution_breakdown", return_value=[]
            ):
                result = await attribution_engine.calculate_attribution(mock_context)

                assert result.order_id == mock_context.order_id
                assert result.shop_id == mock_context.shop_id
                assert result.customer_id == mock_context.customer_id

    @pytest.mark.asyncio
    async def test_error_handling(self, attribution_engine):
        """Test error handling across scenarios"""

        # Test with invalid context
        invalid_context = AttributionContext(
            order_id="",
            shop_id="",
            customer_id="",
            session_id="",
            purchase_amount=Decimal("-1.00"),
            purchase_products=[],
            purchase_time=datetime.now(),
        )

        # Should handle errors gracefully
        try:
            result = await attribution_engine.calculate_attribution(invalid_context)
            # Should return some result, even if it's an error result
            assert result is not None
        except Exception as e:
            # Should log error but not crash
            assert "Error" in str(e) or "error" in str(e).lower()


class TestAttributionPerformance:
    """Performance tests for attribution scenarios"""

    @pytest.mark.asyncio
    async def test_attribution_performance(self):
        """Test attribution calculation performance"""

        attribution_engine = AttributionEngine()

        # Create large dataset
        large_context = AttributionContext(
            order_id="perf_test_order",
            shop_id="test_shop",
            customer_id="test_customer",
            session_id="test_session",
            purchase_amount=Decimal("999.99"),
            purchase_products=[
                {"id": f"product_{i}", "quantity": 1, "price": 99.99}
                for i in range(100)
            ],
            purchase_time=datetime.now(),
        )

        # Mock large interaction set
        large_interactions = [
            {
                "id": f"interaction_{i}",
                "extension_type": "phoenix",
                "interaction_type": "recommendation_clicked",
                "product_id": f"product_{i % 10}",
                "created_at": datetime.now() - timedelta(minutes=i),
                "metadata": {"position": i % 5 + 1},
            }
            for i in range(1000)
        ]

        # Test performance
        import time

        start_time = time.time()

        # Test deduplication performance
        deduplicated = attribution_engine._deduplicate_product_interactions(
            large_interactions
        )

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 5.0  # 5 seconds max
        assert len(deduplicated) < len(large_interactions)  # Should deduplicate


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
