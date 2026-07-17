"""
Async HTTP client for BentoML TFRS serving.

Replaces in-process TensorFlow inference with an async HTTP call
to the bentoml-serving container. This keeps TensorFlow out of the
FastAPI process, preserving event loop responsiveness.
"""

from typing import Dict, Any, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class BentoMLClient:
    """Async client for BentoML TFRS serving."""

    def __init__(self, base_url: str = "http://tfrs-serving:5000"):
        self.base_url = base_url
        self.http = httpx.AsyncClient(timeout=60.0)

    async def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send batch features to BentoML for scoring.

        Args:
            features: Dict of feature arrays (same structure as model expects).
                See service.py in tfrs-serving/ for the full schema.

        Returns:
            Dict with scores, user_embeddings, item_embeddings

        Raises:
            httpx.TimeoutException: If BentoML doesn't respond in 60s.
            httpx.HTTPStatusError: If BentoML returns an error.
        """
        try:
            resp = await self.http.post(
                f"{self.base_url}/predict",
                json={"features": features},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.error("BentoML serving request timed out")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"BentoML serving returned {e.response.status_code}: "
                f"{e.response.text[:500]}"
            )
            raise

    async def health(self) -> bool:
        """Check if BentoML service is healthy."""
        try:
            resp = await self.http.post(f"{self.base_url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close the underlying HTTP client."""
        await self.http.aclose()
