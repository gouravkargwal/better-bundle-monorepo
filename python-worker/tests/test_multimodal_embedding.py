"""
Tests for multimodal embeddings, ingestion edge, resolution edge, and visual similarity.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.database.models.product_data import ProductData
from app.recommandations.edges.embedding import (
    EMBEDDING_MODEL,
    VECTOR_DIM,
    ProductEmbedder,
    build_multimodal_hash,
)
from app.recommandations.edges.resolution import CategoryResolver
from app.recommandations.edges.serving import get_visually_similar


def test_product_data_image_url():
    # 1. From images dict with 'url'
    p1 = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Sneakers",
        handle="sneakers",
        images=[{"url": "https://cdn.shopify.com/s/files/sneakers.jpg"}],
    )
    assert p1.image_url == "https://cdn.shopify.com/s/files/sneakers.jpg"

    # 2. From images dict with 'src'
    p2 = ProductData(
        shop_id="shop1",
        product_id="p2",
        title="Boots",
        handle="boots",
        images=[{"src": "https://cdn.shopify.com/s/files/boots.jpg"}],
    )
    assert p2.image_url == "https://cdn.shopify.com/s/files/boots.jpg"

    # 3. From images list with plain string
    p3 = ProductData(
        shop_id="shop1",
        product_id="p3",
        title="Hat",
        handle="hat",
        images=["https://cdn.shopify.com/s/files/hat.jpg"],
    )
    assert p3.image_url == "https://cdn.shopify.com/s/files/hat.jpg"

    # 4. From media with nested 'image'
    p4 = ProductData(
        shop_id="shop1",
        product_id="p4",
        title="Jacket",
        handle="jacket",
        images=[],
        media=[{"image": {"url": "https://cdn.shopify.com/s/files/jacket.jpg"}}],
    )
    assert p4.image_url == "https://cdn.shopify.com/s/files/jacket.jpg"

    # 5. None when no images or media
    p5 = ProductData(
        shop_id="shop1",
        product_id="p5",
        title="Socks",
        handle="socks",
    )
    assert p5.image_url is None


def test_build_multimodal_hash():
    p1 = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Leather Boots",
        product_type="Footwear",
        handle="boots",
        images=[{"url": "https://example.com/img1.jpg"}],
    )
    h1 = build_multimodal_hash(p1)
    assert len(h1) == 32

    # Same content gives same hash
    p1_same = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Leather Boots",
        product_type="Footwear",
        handle="boots",
        images=[{"url": "https://example.com/img1.jpg"}],
    )
    assert build_multimodal_hash(p1_same) == h1

    # Image change triggers new hash
    p1_new_img = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Leather Boots",
        product_type="Footwear",
        handle="boots",
        images=[{"url": "https://example.com/img2.jpg"}],
    )
    assert build_multimodal_hash(p1_new_img) != h1

    # Title change triggers new hash
    p1_new_title = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Suede Boots",
        product_type="Footwear",
        handle="boots",
        images=[{"url": "https://example.com/img1.jpg"}],
    )
    assert build_multimodal_hash(p1_new_title) != h1


def _make_predict_response(vector):
    response = MagicMock()
    prediction = MagicMock()
    prediction.__getitem__ = lambda self, key: (
        vector if key in ("imageEmbedding", "textEmbedding") else None
    )
    prediction.get = lambda key, default=None: vector if key in ("imageEmbedding", "textEmbedding") else default
    prediction.keys = lambda: ["imageEmbedding", "textEmbedding"]
    response.predictions = [prediction]
    return response


@pytest.mark.asyncio
async def test_product_embedder_encode_multimodal():
    fake_vector = [0.1] * VECTOR_DIM
    mock_client = MagicMock()
    mock_client.predict = AsyncMock(return_value=_make_predict_response(fake_vector))

    embedder = ProductEmbedder(
        project_id="test-proj",
        location="us-central1",
        model_name=EMBEDDING_MODEL,
        client=mock_client,
    )

    product = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Running Shoes",
        product_type="Footwear",
        handle="shoes",
        images=[{"url": "https://example.com/shoes.jpg"}],
    )

    fake_image_bytes = b"fake-jpeg-data"
    mock_http_response = MagicMock()
    mock_http_response.status_code = 200
    mock_http_response.content = fake_image_bytes

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_http_response

        vectors = await embedder._encode_multimodal([product])

    assert len(vectors) == 1
    assert len(vectors[0]) == VECTOR_DIM
    assert vectors[0] == fake_vector
    mock_client.predict.assert_called_once()


@pytest.mark.asyncio
async def test_product_embedder_encode_multimodal_no_image():
    fake_vector = [0.2] * VECTOR_DIM
    mock_client = MagicMock()
    mock_client.predict = AsyncMock(return_value=_make_predict_response(fake_vector))

    embedder = ProductEmbedder(
        project_id="test-proj",
        location="us-central1",
        model_name=EMBEDDING_MODEL,
        client=mock_client,
    )

    product = ProductData(
        shop_id="shop1",
        product_id="p1",
        title="Running Shoes",
        product_type="Footwear",
        handle="shoes",
        images=[],
    )

    vectors = await embedder._encode_multimodal([product])

    assert len(vectors) == 1
    assert len(vectors[0]) == VECTOR_DIM
    assert vectors[0] == fake_vector
    mock_client.predict.assert_called_once()


def test_category_resolver_embed():
    fake_vector = [0.2] * VECTOR_DIM
    mock_client = MagicMock()
    mock_client.predict = MagicMock(return_value=_make_predict_response(fake_vector))

    resolver = CategoryResolver(
        project_id="test-proj",
        location="us-central1",
        model_name=EMBEDDING_MODEL,
        client=mock_client,
    )

    vectors = resolver.embed(["leather boots"])
    assert len(vectors) == 1
    assert vectors[0] == fake_vector
    assert mock_client.predict.call_count == 1


@pytest.mark.asyncio
async def test_category_resolver_async_embed():
    fake_vector = [0.3] * VECTOR_DIM
    mock_client = MagicMock()
    mock_client.predict = AsyncMock(return_value=_make_predict_response(fake_vector))

    resolver = CategoryResolver(
        project_id="test-proj",
        location="us-central1",
        model_name=EMBEDDING_MODEL,
        async_client=mock_client,
    )

    vectors = await resolver.async_embed(["leather boots"])
    assert len(vectors) == 1
    assert vectors[0] == fake_vector
    assert mock_client.predict.call_count == 1


@pytest.mark.asyncio
async def test_get_visually_similar():
    mock_session = AsyncMock()

    # Case 1: Target vector found
    fake_vector = [0.1] * VECTOR_DIM
    target_result = MagicMock()
    target_result.scalar_one_or_none.return_value = fake_vector

    query_result = MagicMock()
    Row = MagicMock
    query_result.all.return_value = [
        Row(product_id="p2"),
        Row(product_id="p3"),
    ]

    mock_session.execute.side_effect = [target_result, query_result]

    similar = await get_visually_similar(
        session=mock_session,
        shop_id="shop1",
        target_product_id="p1",
        limit=2,
    )
    assert similar == ["p2", "p3"]

    # Case 2: Target product has no vector yet
    mock_session.reset_mock()
    target_none = MagicMock()
    target_none.scalar_one_or_none.return_value = None
    mock_session.execute.side_effect = [target_none]

    similar_empty = await get_visually_similar(
        session=mock_session,
        shop_id="shop1",
        target_product_id="p1",
    )
    assert similar_empty == []
