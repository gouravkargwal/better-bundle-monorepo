"""
Unit tests for GorseApiClient

Tests cover:
1. Batch insert methods (users, items, feedback) — empty input, validation, success, retry, errors
2. GET recommendation/neighbor/listing methods — URL construction, params, error handling
3. Health check
4. Header construction with and without API key
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.shared.gorse_api_client import GorseApiClient
from tests.conftest import SHOP_ID, USER_ID, PRODUCT_IDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code=200, json_data=None, text="", content=b"ok"):
    """Create a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        http_error = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
        resp.raise_for_status.side_effect = http_error
    return resp


# ============================================================
# TestGorseApiClient
# ============================================================


class TestGorseApiClient:
    """Tests for GorseApiClient"""

    BASE_URL = "http://gorse-test:8088"
    API_KEY = "test-api-key-123"

    @pytest.fixture
    def client_with_key(self):
        return GorseApiClient(base_url=self.BASE_URL, api_key=self.API_KEY)

    @pytest.fixture
    def client_no_key(self):
        return GorseApiClient(base_url=self.BASE_URL, api_key=None)

    @pytest.fixture
    def mock_http(self):
        """Return an AsyncMock that stands in for httpx.AsyncClient."""
        return AsyncMock()

    # ---- Headers -----------------------------------------------------------

    def test_headers_include_api_key(self, client_with_key):
        headers = client_with_key._get_headers()
        assert headers["X-API-Key"] == self.API_KEY
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers

    def test_headers_omit_api_key_when_none(self, client_no_key):
        headers = client_no_key._get_headers()
        assert "X-API-Key" not in headers
        assert headers["Content-Type"] == "application/json"

    # ---- insert_users_batch ------------------------------------------------

    @pytest.mark.asyncio
    async def test_insert_users_empty_list(self, client_with_key):
        result = await client_with_key.insert_users_batch([])
        assert result["success"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_insert_users_filters_invalid(self, client_with_key, mock_http):
        """Entries without 'UserId' are filtered; if none remain, returns error."""
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_users_batch(
                [{"name": "no-id"}, {"UserId": ""}]
            )
        assert result["success"] is False
        assert result["count"] == 0
        mock_http.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_insert_users_success(self, client_with_key, mock_http):
        mock_http.post.return_value = _make_response(
            200, json_data={"RowAffected": 2}
        )
        users = [{"UserId": "u1"}, {"UserId": "u2"}]
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_users_batch(users)

        assert result["success"] is True
        assert result["count"] == 2
        assert result["total_sent"] == 2
        mock_http.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_users_http_error(self, client_with_key, mock_http):
        mock_http.post.return_value = _make_response(
            500, text="Internal Server Error"
        )
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_users_batch([{"UserId": "u1"}])

        assert result["success"] is False
        assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_insert_users_retry_then_success(self, client_with_key, mock_http):
        """ConnectError on first call, success on second."""
        mock_http.post.side_effect = [
            httpx.ConnectError("connection refused"),
            _make_response(200, json_data={"RowAffected": 1}),
        ]
        client_with_key.retry_backoff = 0  # speed up test
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_users_batch([{"UserId": "u1"}])

        assert result["success"] is True
        assert mock_http.post.await_count == 2

    @pytest.mark.asyncio
    async def test_insert_users_retries_exhausted(self, client_with_key, mock_http):
        """After max_retries ConnectErrors the outer except catches the raised error."""
        mock_http.post.side_effect = httpx.ConnectError("down")
        client_with_key.retry_backoff = 0
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_users_batch([{"UserId": "u1"}])

        assert result["success"] is False
        assert "onnection" in result["error"]

    @pytest.mark.asyncio
    async def test_insert_users_timeout(self, client_with_key, mock_http):
        mock_http.post.side_effect = httpx.TimeoutException("read timed out")
        client_with_key.retry_backoff = 0
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_users_batch([{"UserId": "u1"}])

        assert result["success"] is False
        assert result["error"] == "Request timeout"

    # ---- insert_items_batch ------------------------------------------------

    @pytest.mark.asyncio
    async def test_insert_items_empty_list(self, client_with_key):
        result = await client_with_key.insert_items_batch([])
        assert result["success"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_insert_items_filters_invalid(self, client_with_key, mock_http):
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_items_batch(
                [{"Labels": ["a"]}, {"ItemId": ""}]
            )
        assert result["success"] is False
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_insert_items_success(self, client_with_key, mock_http):
        mock_http.post.return_value = _make_response(
            200, json_data={"RowAffected": 3}
        )
        items = [{"ItemId": pid} for pid in PRODUCT_IDS]
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_items_batch(items)

        assert result["success"] is True
        assert result["count"] == 3
        assert result["total_sent"] == 3

    @pytest.mark.asyncio
    async def test_insert_items_retry_then_success(self, client_with_key, mock_http):
        mock_http.post.side_effect = [
            httpx.ConnectError("refused"),
            _make_response(200, json_data={"RowAffected": 1}),
        ]
        client_with_key.retry_backoff = 0
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_items_batch([{"ItemId": "i1"}])

        assert result["success"] is True
        assert mock_http.post.await_count == 2

    # ---- insert_feedback_batch ---------------------------------------------

    @pytest.mark.asyncio
    async def test_insert_feedback_empty_list(self, client_with_key):
        result = await client_with_key.insert_feedback_batch([])
        assert result["success"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_insert_feedback_filters_invalid(self, client_with_key, mock_http):
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_feedback_batch(
                [{"FeedbackType": "view", "UserId": "u1"}]  # missing ItemId
            )
        assert result["success"] is False
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_insert_feedback_success(self, client_with_key, mock_http):
        mock_http.post.return_value = _make_response(
            200, json_data={"RowAffected": 1}
        )
        feedback = [
            {"FeedbackType": "purchase", "UserId": USER_ID, "ItemId": PRODUCT_IDS[0]}
        ]
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_feedback_batch(feedback)

        assert result["success"] is True
        assert result["count"] == 1
        assert result["total_sent"] == 1

    @pytest.mark.asyncio
    async def test_insert_feedback_http_error(self, client_with_key, mock_http):
        mock_http.post.return_value = _make_response(422, text="Unprocessable")
        feedback = [
            {"FeedbackType": "view", "UserId": USER_ID, "ItemId": PRODUCT_IDS[0]}
        ]
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.insert_feedback_batch(feedback)

        assert result["success"] is False
        assert "422" in result["error"]

    # ---- get_recommendations -----------------------------------------------

    @pytest.mark.asyncio
    async def test_get_recommendations_success(self, client_with_key, mock_http):
        recs = [{"Id": "item_1", "Score": 0.9}, {"Id": "item_2", "Score": 0.8}]
        mock_http.get.return_value = _make_response(200, json_data=recs)
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_recommendations(USER_ID, n=5)

        assert result["success"] is True
        assert result["count"] == 2
        assert result["user_id"] == USER_ID
        # Verify correct URL
        call_args = mock_http.get.call_args
        assert f"/api/recommend/{USER_ID}" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_get_recommendations_with_category_and_exclude(
        self, client_with_key, mock_http
    ):
        mock_http.get.return_value = _make_response(200, json_data=[])
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_recommendations(
                USER_ID, n=3, category="electronics", exclude_items=["ex1", "ex2"]
            )

        assert result["success"] is True
        call_kwargs = mock_http.get.call_args.kwargs
        params = call_kwargs["params"]
        assert params["n"] == 3
        assert params["category"] == "electronics"
        assert "filter" in params

    @pytest.mark.asyncio
    async def test_get_recommendations_http_error(self, client_with_key, mock_http):
        mock_http.get.return_value = _make_response(404, text="Not Found")
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_recommendations(USER_ID)

        assert result["success"] is False
        assert "404" in result["error"]

    # ---- get_item_neighbors ------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_item_neighbors_success(self, client_with_key, mock_http):
        neighbors = [{"Id": "n1", "Score": 0.95}]
        mock_http.get.return_value = _make_response(200, json_data=neighbors)
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_item_neighbors("item_42", n=5)

        assert result["success"] is True
        assert result["item_id"] == "item_42"
        assert result["count"] == 1
        assert f"/api/item/item_42/neighbors" in mock_http.get.call_args.args[0]

    @pytest.mark.asyncio
    async def test_get_item_neighbors_exception(self, client_with_key, mock_http):
        mock_http.get.side_effect = Exception("network failure")
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_item_neighbors("item_42")

        assert result["success"] is False
        assert "network failure" in result["error"]

    # ---- get_latest_items --------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_latest_items_success(self, client_with_key, mock_http):
        items = [{"Id": "i1"}, {"Id": "i2"}]
        mock_http.get.return_value = _make_response(200, json_data=items)
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_latest_items(n=2, category="shoes")

        assert result["success"] is True
        assert result["count"] == 2
        call_kwargs = mock_http.get.call_args.kwargs
        assert call_kwargs["params"]["category"] == "shoes"

    # ---- get_popular_items -------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_popular_items_success(self, client_with_key, mock_http):
        items = [{"Id": "pop1"}]
        mock_http.get.return_value = _make_response(200, json_data=items)
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_popular_items(n=1)

        assert result["success"] is True
        assert result["count"] == 1
        assert "/api/popular" in mock_http.get.call_args.args[0]

    # ---- get_session_recommendations ---------------------------------------

    @pytest.mark.asyncio
    async def test_get_session_recommendations_success(
        self, client_with_key, mock_http
    ):
        recs = [{"Id": "sr1", "Score": 0.7}]
        mock_http.post.return_value = _make_response(200, json_data=recs)
        session_data = [
            {"FeedbackType": "view", "UserId": "", "ItemId": "item_1"}
        ]
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_session_recommendations(
                session_data, n=5, category="tops"
            )

        assert result["success"] is True
        assert result["count"] == 1
        call_kwargs = mock_http.post.call_args.kwargs
        assert call_kwargs["params"]["category"] == "tops"

    @pytest.mark.asyncio
    async def test_get_session_recommendations_error(
        self, client_with_key, mock_http
    ):
        mock_http.post.return_value = _make_response(500, text="Server Error")
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.get_session_recommendations([], n=5)

        assert result["success"] is False
        assert "500" in result["error"]

    # ---- health_check ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_success(self, client_with_key, mock_http):
        mock_http.get.return_value = _make_response(
            200, json_data={"ready": True}, content=b'{"ready": true}'
        )
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.health_check()

        assert result["success"] is True
        assert result["status"] == "healthy"
        assert "/api/health/ready" in mock_http.get.call_args.args[0]

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client_with_key, mock_http):
        mock_http.get.side_effect = httpx.ConnectError("refused")
        with patch.object(client_with_key, "_get_client", return_value=mock_http):
            result = await client_with_key.health_check()

        assert result["success"] is False
        assert result["status"] == "unhealthy"
