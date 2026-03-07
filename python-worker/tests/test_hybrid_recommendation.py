"""
Tests for HybridRecommendationService
Tests cover: BLENDING_RATIOS, _build_session_data, _deduplicate_and_blend,
and blend_recommendations.
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Module-level patching: the hybrid module instantiates a gorse_client at
# import time, so we must patch settings and GorseApiClient before import.
# ---------------------------------------------------------------------------

_mock_gorse_client = MagicMock()
_mock_gorse_client.get_item_neighbors = AsyncMock()
_mock_gorse_client.get_recommendations = AsyncMock()
_mock_gorse_client.get_session_recommendations = AsyncMock()
_mock_gorse_client.get_popular_items = AsyncMock()
_mock_gorse_client.get_latest_items = AsyncMock()


@pytest.fixture(autouse=True)
def _patch_hybrid_module(monkeypatch):
    """Patch the module-level gorse_client before every test."""
    import app.recommandations.hybrid as hybrid_mod

    monkeypatch.setattr(hybrid_mod, "gorse_client", _mock_gorse_client)
    # Reset all mocks between tests
    _mock_gorse_client.reset_mock()
    _mock_gorse_client.get_item_neighbors.reset_mock()
    _mock_gorse_client.get_recommendations.reset_mock()
    _mock_gorse_client.get_session_recommendations.reset_mock()
    _mock_gorse_client.get_popular_items.reset_mock()
    _mock_gorse_client.get_latest_items.reset_mock()


from app.recommandations.hybrid import HybridRecommendationService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHOP_ID = "42"
USER_ID = "cust_123"
SESSION_ID = "sess_abc"
LIMIT = 6


@pytest.fixture
def service():
    svc = HybridRecommendationService()
    # Ensure it uses the mocked client
    svc.gorse_client = _mock_gorse_client
    return svc


# ---------------------------------------------------------------------------
# BLENDING_RATIOS
# ---------------------------------------------------------------------------


class TestBlendingRatios:
    def test_all_contexts_defined(self):
        expected = [
            "product_page",
            "homepage",
            "cart",
            "profile",
            "checkout",
            "order_history",
            "order_status",
            "collection_page",
            "post_purchase",
        ]
        for ctx in expected:
            assert ctx in HybridRecommendationService.BLENDING_RATIOS, (
                f"Missing context: {ctx}"
            )

    def test_ratios_sum_to_approximately_one(self):
        for ctx, ratios in HybridRecommendationService.BLENDING_RATIOS.items():
            total = sum(ratios.values())
            assert abs(total - 1.0) < 0.05, (
                f"Ratios for '{ctx}' sum to {total}, expected ~1.0"
            )

    def test_product_page_correct_values(self):
        pp = HybridRecommendationService.BLENDING_RATIOS["product_page"]
        assert pp["item_neighbors"] == pytest.approx(0.7)
        assert pp["user_recommendations"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# _build_session_data
# ---------------------------------------------------------------------------


class TestBuildSessionData:
    def test_cart_contents_creates_entries(self, service):
        metadata = {"cart_contents": ["p1", "p2"]}
        result = service._build_session_data(
            session_id=SESSION_ID,
            user_id=f"shop_{SHOP_ID}_{USER_ID}",
            metadata=metadata,
            shop_id=SHOP_ID,
        )
        cart_entries = [fb for fb in result if "cart_item_" in fb["Comment"]]
        assert len(cart_entries) == 2
        assert cart_entries[0]["ItemId"] == f"shop_{SHOP_ID}_p1"
        assert cart_entries[0]["FeedbackType"] == "cart_add"

    def test_recent_views_creates_entries(self, service):
        metadata = {"recent_views": ["v1", "v2", "v3"]}
        result = service._build_session_data(
            session_id=SESSION_ID,
            user_id=f"shop_{SHOP_ID}_{USER_ID}",
            metadata=metadata,
            shop_id=SHOP_ID,
        )
        view_entries = [fb for fb in result if "recent_view_" in fb["Comment"]]
        assert len(view_entries) == 3
        assert view_entries[0]["ItemId"] == f"shop_{SHOP_ID}_v1"
        assert view_entries[0]["FeedbackType"] == "view"

    def test_empty_metadata_returns_empty_for_user(self, service):
        """With user_id but no meaningful metadata, returns [] because ItemId is empty."""
        result = service._build_session_data(
            session_id=SESSION_ID,
            user_id=f"shop_{SHOP_ID}_{USER_ID}",
            metadata={},
            shop_id=SHOP_ID,
        )
        # Should return empty list since no items and the minimal feedback has no ItemId
        assert result == []

    def test_no_user_no_metadata_returns_base_feedback(self, service):
        """Without user_id and without metadata, returns a single base feedback."""
        result = service._build_session_data(
            session_id=SESSION_ID,
            user_id=None,
            metadata=None,
            shop_id=SHOP_ID,
        )
        # Falls into the else branch: no user_id and no cart contents
        assert len(result) == 1
        assert result[0]["Comment"] == f"session_{SESSION_ID}"


# ---------------------------------------------------------------------------
# _deduplicate_and_blend
# ---------------------------------------------------------------------------


class TestDeduplicateAndBlend:
    def test_removes_duplicates_by_id(self, service):
        items = [
            {"Id": "a", "_ratio": 0.5, "_source": "s1"},
            {"Id": "a", "_ratio": 0.3, "_source": "s2"},
            {"Id": "b", "_ratio": 0.4, "_source": "s1"},
        ]
        result = service._deduplicate_and_blend(items, limit=10)
        ids = [r["Id"] for r in result]
        assert ids.count("a") == 1
        assert "b" in ids

    def test_shop_prefix_dedup(self, service):
        """shop_42_p1 and p1 should be treated as the same item."""
        items = [
            {"Id": "shop_42_p1", "_ratio": 0.7, "_source": "s1"},
            {"Id": "p1", "_ratio": 0.3, "_source": "s2"},
        ]
        result = service._deduplicate_and_blend(items, limit=10)
        assert len(result) == 1

    def test_sorts_by_ratio_descending(self, service):
        items = [
            {"Id": "low", "_ratio": 0.1, "_source": "s1"},
            {"Id": "high", "_ratio": 0.9, "_source": "s2"},
            {"Id": "mid", "_ratio": 0.5, "_source": "s3"},
        ]
        result = service._deduplicate_and_blend(items, limit=10)
        ratios = [r["_ratio"] for r in result]
        assert ratios == sorted(ratios, reverse=True)

    def test_respects_limit(self, service):
        items = [
            {"Id": f"item_{i}", "_ratio": 0.5, "_source": "s"} for i in range(20)
        ]
        result = service._deduplicate_and_blend(items, limit=5)
        assert len(result) == 5

    def test_skips_empty_ids(self, service):
        items = [
            {"Id": "", "_ratio": 0.5, "_source": "s1"},
            {"Id": "  ", "_ratio": 0.5, "_source": "s2"},
            {"Id": "valid", "_ratio": 0.5, "_source": "s3"},
        ]
        result = service._deduplicate_and_blend(items, limit=10)
        assert len(result) == 1
        assert result[0]["Id"] == "valid"


# ---------------------------------------------------------------------------
# blend_recommendations
# ---------------------------------------------------------------------------


class TestBlendRecommendations:
    @pytest.mark.asyncio
    async def test_source_is_hybrid(self, service):
        """Result source should always be 'hybrid'."""
        _mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["item1"],
        }
        _mock_gorse_client.get_item_neighbors.return_value = {
            "success": True,
            "neighbors": [{"Id": "n1", "Score": 0.9}],
        }
        _mock_gorse_client.get_recommendations.return_value = {
            "success": True,
            "recommendations": ["r1"],
        }
        result = await service.blend_recommendations(
            context="product_page",
            shop_id=SHOP_ID,
            product_ids=["p1"],
            user_id=USER_ID,
            limit=LIMIT,
        )
        assert result["source"] == "hybrid"
        assert result["success"] is True
        assert "blending_info" in result

    @pytest.mark.asyncio
    async def test_handles_source_failure_gracefully(self, service):
        """If one source fails, others should still contribute."""
        _mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["pop1"],
        }
        _mock_gorse_client.get_latest_items.return_value = {
            "success": False,
            "items": [],
        }
        _mock_gorse_client.get_recommendations.return_value = {
            "success": False,
            "recommendations": [],
        }
        with patch(
            "app.recommandations.hybrid.UserNeighborsService"
        ) as MockUNS:
            mock_uns = MagicMock()
            mock_uns.get_neighbor_recommendations = AsyncMock(
                return_value={"success": False, "items": []}
            )
            MockUNS.return_value = mock_uns

            result = await service.blend_recommendations(
                context="homepage",
                shop_id=SHOP_ID,
                user_id=USER_ID,
                limit=LIMIT,
            )
        # Should still succeed because popular returned items
        assert result["success"] is True
        assert result["source"] == "hybrid"

    @pytest.mark.asyncio
    async def test_unknown_context_defaults_to_popular(self, service):
        """Unknown context should fall back to {'popular': 1.0}."""
        _mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["fallback_item"],
        }
        result = await service.blend_recommendations(
            context="totally_unknown_context",
            shop_id=SHOP_ID,
            limit=LIMIT,
        )
        assert result["success"] is True
        assert result["source"] == "hybrid"
        # Only popular should have been queried
        _mock_gorse_client.get_popular_items.assert_called()
        _mock_gorse_client.get_item_neighbors.assert_not_called()
        _mock_gorse_client.get_recommendations.assert_not_called()
