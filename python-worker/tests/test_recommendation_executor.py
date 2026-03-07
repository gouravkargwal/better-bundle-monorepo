"""
Tests for RecommendationExecutor
Tests cover: _extract_numeric_id, execute_recommendation_level (all levels),
execute_fallback_chain, and _get_default_fallback_levels.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

SHOP_ID = "42"
USER_ID = "cust_123"
SESSION_ID = "sess_abc"
PRODUCT_IDS = ["gid://shopify/Product/111", "gid://shopify/Product/222"]
CATEGORY = "shoes"
LIMIT = 6


@pytest.fixture
def mock_gorse_client():
    client = MagicMock()
    client.get_item_neighbors = AsyncMock()
    client.get_recommendations = AsyncMock()
    client.get_session_recommendations = AsyncMock()
    client.get_popular_items = AsyncMock()
    client.get_latest_items = AsyncMock()
    return client


@pytest.fixture
def executor(mock_gorse_client):
    with patch(
        "app.recommandations.recommendation_executor.UserNeighborsService"
    ) as MockUNS:
        mock_uns_instance = MagicMock()
        mock_uns_instance.get_neighbor_recommendations = AsyncMock()
        MockUNS.return_value = mock_uns_instance
        from app.recommandations.recommendation_executor import RecommendationExecutor

        exc = RecommendationExecutor(gorse_client=mock_gorse_client)
        # Expose the mock so tests can configure it
        exc._mock_uns = mock_uns_instance
        yield exc


# ---------------------------------------------------------------------------
# _extract_numeric_id
# ---------------------------------------------------------------------------


class TestExtractNumericId:
    def test_gid_format(self, executor):
        assert executor._extract_numeric_id("gid://shopify/Product/12345") == "12345"

    def test_plain_id(self, executor):
        assert executor._extract_numeric_id("99999") == "99999"

    def test_empty_string(self, executor):
        assert executor._extract_numeric_id("") is None

    def test_none_value(self, executor):
        assert executor._extract_numeric_id(None) is None


# ---------------------------------------------------------------------------
# execute_recommendation_level — individual levels
# ---------------------------------------------------------------------------


class TestItemNeighbors:
    @pytest.mark.asyncio
    async def test_correct_prefix_and_call(self, executor, mock_gorse_client):
        mock_gorse_client.get_item_neighbors.return_value = {
            "success": True,
            "neighbors": [{"Id": "shop_42_222", "Score": 0.9}],
        }
        result = await executor.execute_recommendation_level(
            level="item_neighbors",
            shop_id=SHOP_ID,
            product_ids=PRODUCT_IDS,
            limit=LIMIT,
        )
        assert result["success"] is True
        assert result["source"] == "gorse_item_neighbors"
        assert result["items"] == [{"Id": "shop_42_222", "Score": 0.9}]
        # Verify the prefixed item id was passed
        call_kwargs = mock_gorse_client.get_item_neighbors.call_args
        assert call_kwargs.kwargs["item_id"] == "shop_42_111"

    @pytest.mark.asyncio
    async def test_missing_product_ids_returns_none(self, executor, mock_gorse_client):
        result = await executor.execute_recommendation_level(
            level="item_neighbors",
            shop_id=SHOP_ID,
            product_ids=None,
            limit=LIMIT,
        )
        assert result["success"] is False
        assert result["source"] == "none"


class TestUserRecommendations:
    @pytest.mark.asyncio
    async def test_correct_prefix_and_filters_empty(self, executor, mock_gorse_client):
        mock_gorse_client.get_recommendations.return_value = {
            "success": True,
            "recommendations": ["shop_42_p1", "", "shop_42_p2", "  "],
        }
        result = await executor.execute_recommendation_level(
            level="user_recommendations",
            shop_id=SHOP_ID,
            user_id=USER_ID,
            limit=LIMIT,
        )
        assert result["success"] is True
        assert result["source"] == "gorse_user_recommendations"
        assert result["items"] == ["shop_42_p1", "shop_42_p2"]
        call_kwargs = mock_gorse_client.get_recommendations.call_args
        assert call_kwargs.kwargs["user_id"] == f"shop_{SHOP_ID}_{USER_ID}"

    @pytest.mark.asyncio
    async def test_missing_user_id_returns_none(self, executor, mock_gorse_client):
        result = await executor.execute_recommendation_level(
            level="user_recommendations",
            shop_id=SHOP_ID,
            user_id=None,
            limit=LIMIT,
        )
        assert result["success"] is False
        assert result["source"] == "none"


class TestSessionRecommendations:
    @pytest.mark.asyncio
    async def test_builds_feedback_from_metadata(self, executor, mock_gorse_client):
        metadata = {
            "cart_contents": ["p1", "p2"],
            "recent_views": ["p3"],
        }
        mock_gorse_client.get_session_recommendations.return_value = {
            "success": True,
            "recommendations": ["shop_42_r1"],
        }
        result = await executor.execute_recommendation_level(
            level="session_recommendations",
            shop_id=SHOP_ID,
            user_id=USER_ID,
            session_id=SESSION_ID,
            metadata=metadata,
            limit=LIMIT,
        )
        assert result["success"] is True
        assert result["source"] == "gorse_session_recommendations"
        # Verify feedback objects were built and passed
        call_kwargs = mock_gorse_client.get_session_recommendations.call_args
        session_data = call_kwargs.kwargs["session_data"]
        # 2 cart + 1 view = 3 feedback objects
        assert len(session_data) == 3
        assert any("cart_item_p1" in obj["Comment"] for obj in session_data)
        assert any("recent_view_p3" in obj["Comment"] for obj in session_data)


class TestPopularLatestTrending:
    @pytest.mark.asyncio
    async def test_popular_source_string(self, executor, mock_gorse_client):
        mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["item1"],
        }
        result = await executor.execute_recommendation_level(
            level="popular", shop_id=SHOP_ID, limit=LIMIT
        )
        assert result["source"] == "gorse_popular"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_latest_source_string(self, executor, mock_gorse_client):
        mock_gorse_client.get_latest_items.return_value = {
            "success": True,
            "items": ["item1"],
        }
        result = await executor.execute_recommendation_level(
            level="latest", shop_id=SHOP_ID, limit=LIMIT
        )
        assert result["source"] == "gorse_latest"

    @pytest.mark.asyncio
    async def test_trending_source_string(self, executor, mock_gorse_client):
        mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["item1"],
        }
        result = await executor.execute_recommendation_level(
            level="trending", shop_id=SHOP_ID, limit=LIMIT
        )
        assert result["source"] == "gorse_trending"

    @pytest.mark.asyncio
    async def test_popular_category_source_string(self, executor, mock_gorse_client):
        mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["item1"],
        }
        result = await executor.execute_recommendation_level(
            level="popular_category", shop_id=SHOP_ID, limit=LIMIT
        )
        assert result["source"] == "gorse_popular_category"


class TestMissingParamsAndErrors:
    @pytest.mark.asyncio
    async def test_unknown_level_returns_none(self, executor):
        result = await executor.execute_recommendation_level(
            level="nonexistent_level", shop_id=SHOP_ID, limit=LIMIT
        )
        assert result["success"] is False
        assert result["source"] == "none"

    @pytest.mark.asyncio
    async def test_exception_returns_error_source(self, executor, mock_gorse_client):
        mock_gorse_client.get_popular_items.side_effect = RuntimeError("boom")
        result = await executor.execute_recommendation_level(
            level="popular", shop_id=SHOP_ID, limit=LIMIT
        )
        assert result["success"] is False
        assert result["source"] == "error"


# ---------------------------------------------------------------------------
# execute_fallback_chain
# ---------------------------------------------------------------------------


class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_stops_at_first_success(self, executor, mock_gorse_client):
        """Fallback chain should return the first level that succeeds with items."""
        mock_gorse_client.get_popular_items.return_value = {
            "success": True,
            "items": ["item_a"],
        }
        # First level fails, second succeeds
        custom_levels = {"test_ctx": ["latest", "popular"]}
        mock_gorse_client.get_latest_items.return_value = {
            "success": False,
            "items": [],
        }
        result = await executor.execute_fallback_chain(
            context="test_ctx",
            shop_id=SHOP_ID,
            limit=LIMIT,
            fallback_levels=custom_levels,
        )
        assert result["success"] is True
        assert result["source"] == "gorse_popular"

    @pytest.mark.asyncio
    async def test_all_fail_returns_all_failed(self, executor, mock_gorse_client):
        mock_gorse_client.get_popular_items.return_value = {
            "success": False,
            "items": [],
        }
        mock_gorse_client.get_latest_items.return_value = {
            "success": False,
            "items": [],
        }
        custom_levels = {"ctx": ["popular", "latest"]}
        result = await executor.execute_fallback_chain(
            context="ctx",
            shop_id=SHOP_ID,
            limit=LIMIT,
            fallback_levels=custom_levels,
        )
        assert result["success"] is False
        assert result["source"] == "all_failed"

    @pytest.mark.asyncio
    async def test_custom_levels_override_defaults(self, executor, mock_gorse_client):
        """When fallback_levels is provided, it should be used instead of defaults."""
        mock_gorse_client.get_latest_items.return_value = {
            "success": True,
            "items": ["new_item"],
        }
        custom_levels = {"homepage": ["latest"]}
        result = await executor.execute_fallback_chain(
            context="homepage",
            shop_id=SHOP_ID,
            limit=LIMIT,
            fallback_levels=custom_levels,
        )
        assert result["success"] is True
        assert result["source"] == "gorse_latest"
        # The default homepage chain has user_recommendations first, but
        # our custom chain only has latest — verify popular was NOT called
        mock_gorse_client.get_popular_items.assert_not_called()


# ---------------------------------------------------------------------------
# _get_default_fallback_levels
# ---------------------------------------------------------------------------


class TestDefaultFallbackLevels:
    def test_structure(self, executor):
        levels = executor._get_default_fallback_levels()
        expected_contexts = [
            "product_page",
            "homepage",
            "cart",
            "profile",
            "checkout",
            "order_history",
            "order_status",
            "post_purchase",
            "collection_page",
        ]
        for ctx in expected_contexts:
            assert ctx in levels, f"Missing context: {ctx}"
            assert isinstance(levels[ctx], list)
            assert len(levels[ctx]) > 0
