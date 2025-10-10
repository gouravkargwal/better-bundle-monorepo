"""
Gorse API Client
Handles all communication with the Gorse REST API for data insertion and retrieval
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class GorseApiClient:
    """
    Client for interacting with Gorse REST API
    Handles batch data insertion which automatically triggers training
    """

    def __init__(
        self, base_url: str = "http://localhost:8088", api_key: Optional[str] = None
    ):
        """
        Initialize Gorse API client

        Args:
            base_url: Gorse master server URL
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        # Configurable timeout and basic retry settings to improve resilience
        self.timeout = httpx.Timeout(20.0)
        self.max_retries = 3
        self.retry_backoff = 0.5

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BetterBundle-GorseClient/1.0",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def insert_users_batch(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert a batch of users to Gorse with enhanced error handling
        This automatically triggers user-based model training

        Args:
            users: List of user dictionaries already in Gorse format (UserId, Labels, etc.)

        Returns:
            API response dictionary
        """
        if not users:
            return {"success": True, "message": "No users to insert", "count": 0}

        try:
            # Only validate, don't transform (data is already in correct format)
            valid_users = [u for u in users if "UserId" in u and u["UserId"]]

            if not valid_users:
                logger.warning("No valid users with UserId found")
                return {"success": False, "error": "No valid users", "count": 0}

            url = f"{self.base_url}/api/users"

            # Retry loop
            attempt = 0
            response = None
            while attempt <= self.max_retries:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            url, json=valid_users, headers=self._get_headers()
                        )
                    break  # Success - exit retry loop
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RemoteProtocolError,
                ) as e:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise
                    logger.warning(
                        f"Gorse users batch attempt {attempt} failed: {e}; retrying..."
                    )
                    await asyncio.sleep(self.retry_backoff * attempt)

            # Check HTTP status
            if response and response.status_code == 200:
                result = response.json()
                row_affected = result.get("RowAffected", 0)

                return {
                    "success": True,
                    "count": row_affected,
                    "total_sent": len(valid_users),
                    "response": result,
                    "timestamp": now_utc(),
                }
            else:
                error_msg = (
                    f"HTTP {response.status_code}: {response.text}"
                    if response
                    else "No response"
                )
                logger.error(f"HTTP error inserting users batch: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "count": 0,
                }

        except httpx.TimeoutException:
            logger.error("Timeout inserting users batch")
            return {"success": False, "error": "Request timeout", "count": 0}
        except httpx.ConnectError:
            logger.error("Connection error inserting users batch")
            return {"success": False, "error": "Connection error", "count": 0}
        except Exception as e:
            logger.error(f"Failed to insert users batch: {str(e)}")
            return {"success": False, "error": str(e), "count": 0}

    async def insert_items_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert a batch of items to Gorse
        This automatically triggers item-based model training

        Args:
            items: List of item dictionaries already in Gorse format (ItemId, Labels, etc.)

        Returns:
            API response dictionary
        """
        if not items:
            return {"success": True, "message": "No items to insert", "count": 0}

        try:
            # Only validate, don't transform (data is already in correct format)
            valid_items = [i for i in items if "ItemId" in i and i["ItemId"]]

            if not valid_items:
                logger.warning("No valid items with ItemId found")
                return {"success": False, "error": "No valid items", "count": 0}

            url = f"{self.base_url}/api/items"

            # Retry loop
            attempt = 0
            response = None
            while attempt <= self.max_retries:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            url, json=valid_items, headers=self._get_headers()
                        )
                    break  # Success - exit retry loop
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RemoteProtocolError,
                ) as e:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise
                    logger.warning(
                        f"Gorse items batch attempt {attempt} failed: {e}; retrying..."
                    )
                    await asyncio.sleep(self.retry_backoff * attempt)

            # Check HTTP status
            if response and response.status_code == 200:
                result = response.json()
                row_affected = result.get("RowAffected", 0)

                return {
                    "success": True,
                    "count": row_affected,
                    "total_sent": len(valid_items),
                    "response": result,
                    "timestamp": now_utc(),
                }
            else:
                error_msg = (
                    f"HTTP {response.status_code}: {response.text}"
                    if response
                    else "No response"
                )
                logger.error(f"HTTP error inserting items batch: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "count": 0,
                }

        except httpx.TimeoutException:
            logger.error("Timeout inserting items batch")
            return {"success": False, "error": "Request timeout", "count": 0}
        except httpx.ConnectError:
            logger.error("Connection error inserting items batch")
            return {"success": False, "error": "Connection error", "count": 0}
        except Exception as e:
            logger.error(f"Failed to insert items batch: {str(e)}")
            return {"success": False, "error": str(e), "count": 0}

    async def insert_feedback_batch(
        self, feedback: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Insert a batch of feedback to Gorse
        This automatically triggers feedback-based model training

        Args:
            feedback: List of feedback dictionaries already in Gorse format

        Returns:
            API response dictionary
        """
        if not feedback:
            return {"success": True, "message": "No feedback to insert", "count": 0}

        try:
            # Only validate, don't transform (data is already in correct format)
            valid_feedback = [
                f
                for f in feedback
                if "FeedbackType" in f and "UserId" in f and "ItemId" in f
            ]

            if not valid_feedback:
                logger.warning("No valid feedback found")
                return {"success": False, "error": "No valid feedback", "count": 0}

            url = f"{self.base_url}/api/feedback"

            # Retry loop
            attempt = 0
            response = None
            while attempt <= self.max_retries:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            url, json=valid_feedback, headers=self._get_headers()
                        )
                    break  # Success - exit retry loop
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.RemoteProtocolError,
                ) as e:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise
                    logger.warning(
                        f"Gorse feedback batch attempt {attempt} failed: {e}; retrying..."
                    )
                    await asyncio.sleep(self.retry_backoff * attempt)

            # Check HTTP status
            if response and response.status_code == 200:
                result = response.json()
                row_affected = result.get("RowAffected", 0)

                return {
                    "success": True,
                    "count": row_affected,
                    "total_sent": len(valid_feedback),
                    "response": result,
                    "timestamp": now_utc(),
                }
            else:
                error_msg = (
                    f"HTTP {response.status_code}: {response.text}"
                    if response
                    else "No response"
                )
                logger.error(f"HTTP error inserting feedback batch: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "count": 0,
                }

        except httpx.TimeoutException:
            logger.error("Timeout inserting feedback batch")
            return {"success": False, "error": "Request timeout", "count": 0}
        except httpx.ConnectError:
            logger.error("Connection error inserting feedback batch")
            return {"success": False, "error": "Connection error", "count": 0}
        except Exception as e:
            logger.error(f"Failed to insert feedback batch: {str(e)}")
            return {"success": False, "error": str(e), "count": 0}

    async def get_recommendations(
        self,
        user_id: str,
        n: int = 10,
        category: Optional[str] = None,
        exclude_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get recommendations for a user from Gorse

        Args:
            user_id: User ID to get recommendations for
            n: Number of recommendations to return
            category: Optional category filter
            exclude_items: Optional list of item IDs to exclude from recommendations

        Returns:
            Recommendations response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category
            if exclude_items:
                # Gorse supports filtering by excluding items
                params["filter"] = f"not item_id in ({','.join(exclude_items)})"

            url = f"{self.base_url}/api/recommend/{user_id}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return {
                    "success": True,
                    "recommendations": result,
                    "user_id": user_id,
                    "count": len(result) if isinstance(result, list) else 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting recommendations: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "recommendations": [],
            }
        except Exception as e:
            logger.error(f"Failed to get recommendations: {str(e)}")
            return {"success": False, "error": str(e), "recommendations": []}

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if Gorse API is healthy and accessible

        Returns:
            Health check response
        """
        try:
            # Use the correct Gorse health check endpoint
            url = f"{self.base_url}/api/health/ready"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()

                return {
                    "success": True,
                    "status": "healthy",
                    "response": response.json() if response.content else {},
                }

        except Exception as e:
            logger.error(f"Gorse health check failed: {str(e)}")
            return {"success": False, "status": "unhealthy", "error": str(e)}

    async def get_item_neighbors(
        self,
        item_id: str,
        n: int = 10,
        category: Optional[str] = None,
        exclude_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get similar items (neighbors) for a given item

        Args:
            item_id: Item ID to get neighbors for
            n: Number of neighbors to return
            category: Optional category filter
            exclude_items: Optional list of item IDs to exclude from neighbors

        Returns:
            Item neighbors response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category
            if exclude_items:
                # Gorse supports filtering by excluding items
                params["filter"] = f"not item_id in ({','.join(exclude_items)})"

            url = f"{self.base_url}/api/item/{item_id}/neighbors"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return {
                    "success": True,
                    "neighbors": result,
                    "item_id": item_id,
                    "count": len(result) if isinstance(result, list) else 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting item neighbors: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "neighbors": [],
            }
        except Exception as e:
            logger.error(f"Failed to get item neighbors: {str(e)}")
            return {"success": False, "error": str(e), "neighbors": []}

    async def get_latest_items(
        self, n: int = 10, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get latest items from Gorse

        Args:
            n: Number of items to return
            category: Optional category filter

        Returns:
            Latest items response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category

            url = f"{self.base_url}/api/latest"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return {
                    "success": True,
                    "items": result,
                    "count": len(result) if isinstance(result, list) else 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting latest items: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "items": [],
            }
        except Exception as e:
            logger.error(f"Failed to get latest items: {str(e)}")
            return {"success": False, "error": str(e), "items": []}

    async def get_popular_items(
        self, n: int = 10, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get popular items from Gorse

        Args:
            n: Number of items to return
            category: Optional category filter

        Returns:
            Popular items response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category

            url = f"{self.base_url}/api/popular"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return {
                    "success": True,
                    "items": result,
                    "count": len(result) if isinstance(result, list) else 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting popular items: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "items": [],
            }
        except Exception as e:
            logger.error(f"Failed to get popular items: {str(e)}")
            return {"success": False, "error": str(e), "items": []}

    async def get_user_neighbors(self, user_id: str, n: int = 10) -> Dict[str, Any]:
        """
        Get similar users (neighbors) for a given user

        Args:
            user_id: User ID to get neighbors for
            n: Number of neighbors to return

        Returns:
            User neighbors response
        """
        try:
            params = {"n": n}
            url = f"{self.base_url}/api/user/{user_id}/neighbors"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return {
                    "success": True,
                    "neighbors": result,
                    "user_id": user_id,
                    "count": len(result) if isinstance(result, list) else 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting user neighbors: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "neighbors": [],
            }
        except Exception as e:
            logger.error(f"Failed to get user neighbors: {str(e)}")
            return {"success": False, "error": str(e), "neighbors": []}

    async def get_session_recommendations(
        self,
        session_data: List[Dict[str, Any]],
        n: int = 10,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get session-based recommendations from Gorse

        Args:
            session_data: List of feedback objects for the session
            n: Number of recommendations to return
            category: Optional category filter

        Returns:
            Session recommendations response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category

            url = f"{self.base_url}/api/session/recommend"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=session_data, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return {
                    "success": True,
                    "recommendations": result,
                    "count": len(result) if isinstance(result, list) else 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting session recommendations: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "recommendations": [],
            }
        except Exception as e:
            logger.error(f"Failed to get session recommendations: {str(e)}")
            return {"success": False, "error": str(e), "recommendations": []}

    async def get_user_neighbors(self, user_id: str, n: int = 10) -> Dict[str, Any]:
        """
        Get similar users (user neighbors) for collaborative filtering

        Args:
            user_id: User ID to find neighbors for
            n: Number of neighbors to return

        Returns:
            Dict with success status and neighbor user data
        """
        try:
            logger.debug(f"Getting user neighbors for user {user_id}")

            url = f"{self.base_url}/api/user/{user_id}/neighbors"
            params = {"n": n}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, params=params, headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()

            # Gorse returns a list of user IDs with scores
            if isinstance(result, list):
                return {
                    "success": True,
                    "neighbors": result,
                    "count": len(result),
                }
            else:
                logger.warning(
                    f"Unexpected response format for user neighbors: {result}"
                )
                return {
                    "success": False,
                    "error": "Unexpected response format",
                    "neighbors": [],
                    "count": 0,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error getting user neighbors: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "neighbors": [],
            }
        except Exception as e:
            logger.error(f"Failed to get user neighbors: {str(e)}")
            return {"success": False, "error": str(e), "neighbors": []}
