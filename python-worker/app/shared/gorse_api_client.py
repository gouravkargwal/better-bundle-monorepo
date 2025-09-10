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
        self.timeout = httpx.Timeout(30.0)  # 30 second timeout for API calls

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
            users: List of user dictionaries with userId, labels, etc.

        Returns:
            API response dictionary
        """
        if not users:
            return {"success": True, "message": "No users to insert", "count": 0}

        try:
            # Transform users to Gorse format
            gorse_users = []
            for user in users:
                # Convert labels dict to list format as per Gorse API
                labels = user.get("labels", {})
                if isinstance(labels, dict):
                    # Convert dict to list of key-value pairs or just keys
                    labels_list = (
                        [f"{k}:{v}" for k, v in labels.items()] if labels else []
                    )
                else:
                    labels_list = labels if isinstance(labels, list) else []

                gorse_user = {
                    "UserId": user["userId"],
                    "Labels": labels_list,
                    "Subscribe": user.get("subscribe", []),
                    "Comment": user.get("comment", ""),
                }
                gorse_users.append(gorse_user)

            url = f"{self.base_url}/api/users"

            # Log detailed payload information
            logger.info(f"=== USERS PAYLOAD DEBUG ===")
            logger.info(f"URL: {url}")
            logger.info(f"Total users to send: {len(gorse_users)}")
            logger.info(f"Headers: {self._get_headers()}")

            # Log sample of first few users (truncated for readability)
            for i, user in enumerate(gorse_users[:3]):  # Show first 3 users
                logger.info(f"User {i+1} payload: {json.dumps(user, indent=2)}")

            if len(gorse_users) > 3:
                logger.info(f"... and {len(gorse_users) - 3} more users")
            logger.info(f"=== END USERS PAYLOAD DEBUG ===")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=gorse_users, headers=self._get_headers()
                )

                # Check HTTP status
                if response.status_code == 200:
                    result = response.json()
                    row_affected = result.get("RowAffected", 0)

                    logger.info(
                        f"Successfully inserted {row_affected} users to Gorse (sent {len(gorse_users)})"
                    )

                    return {
                        "success": True,
                        "count": row_affected,
                        "total_sent": len(gorse_users),
                        "response": result,
                        "timestamp": now_utc(),
                    }
                else:
                    # HTTP error
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.error(f"HTTP error inserting users batch: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "count": 0,
                    }

        except httpx.TimeoutException:
            error_msg = "Request timeout"
            logger.error(f"Timeout inserting users batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}
        except httpx.ConnectError:
            error_msg = "Connection error"
            logger.error(f"Connection error inserting users batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to insert users batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}

    async def insert_items_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert a batch of items to Gorse
        This automatically triggers item-based model training

        Args:
            items: List of item dictionaries with itemId, categories, labels, etc.

        Returns:
            API response dictionary
        """
        if not items:
            return {"success": True, "message": "No items to insert", "count": 0}

        try:
            # Transform items to Gorse format
            gorse_items = []
            for item in items:
                # Convert labels dict to list format as per Gorse API
                labels = item.get("labels", {})
                if isinstance(labels, dict):
                    # Convert dict to list of key-value pairs
                    labels_list = (
                        [f"{k}:{v}" for k, v in labels.items()] if labels else []
                    )
                else:
                    labels_list = labels if isinstance(labels, list) else []

                gorse_item = {
                    "ItemId": item["itemId"],
                    "Categories": item.get("categories", []),
                    "Labels": labels_list,
                    "IsHidden": item.get("isHidden", False),
                    "Timestamp": item.get("timestamp", now_utc().isoformat()),
                    "Comment": item.get("comment", ""),
                }
                gorse_items.append(gorse_item)

            url = f"{self.base_url}/api/items"

            # Log detailed payload information
            logger.info(f"=== ITEMS PAYLOAD DEBUG ===")
            logger.info(f"URL: {url}")
            logger.info(f"Total items to send: {len(gorse_items)}")
            logger.info(f"Headers: {self._get_headers()}")

            # Log sample of first few items (truncated for readability)
            for i, item in enumerate(gorse_items[:3]):  # Show first 3 items
                logger.info(f"Item {i+1} payload: {json.dumps(item, indent=2)}")

            if len(gorse_items) > 3:
                logger.info(f"... and {len(gorse_items) - 3} more items")
            logger.info(f"=== END ITEMS PAYLOAD DEBUG ===")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=gorse_items, headers=self._get_headers()
                )

                # Check HTTP status
                if response.status_code == 200:
                    result = response.json()
                    row_affected = result.get("RowAffected", 0)

                    logger.info(
                        f"Successfully inserted {row_affected} items to Gorse (sent {len(gorse_items)})"
                    )

                    return {
                        "success": True,
                        "count": row_affected,
                        "total_sent": len(gorse_items),
                        "response": result,
                        "timestamp": now_utc(),
                    }
                else:
                    # HTTP error
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.error(f"HTTP error inserting items batch: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "count": 0,
                    }

        except httpx.TimeoutException:
            error_msg = "Request timeout"
            logger.error(f"Timeout inserting items batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}
        except httpx.ConnectError:
            error_msg = "Connection error"
            logger.error(f"Connection error inserting items batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to insert items batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}

    async def insert_feedback_batch(
        self, feedback: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Insert a batch of feedback to Gorse
        This automatically triggers feedback-based model training

        Args:
            feedback: List of feedback dictionaries with feedbackType, userId, itemId, etc.

        Returns:
            API response dictionary
        """
        if not feedback:
            return {"success": True, "message": "No feedback to insert", "count": 0}

        try:
            # Transform feedback to Gorse format
            gorse_feedback = []
            for fb in feedback:
                gorse_fb = {
                    "FeedbackType": fb["feedbackType"],
                    "UserId": fb["userId"],
                    "ItemId": fb["itemId"],
                    "Timestamp": (
                        fb["timestamp"].isoformat()
                        if isinstance(fb["timestamp"], datetime)
                        else fb["timestamp"]
                    ),
                    "Value": fb.get("value", 1.0),
                    "Comment": fb.get("comment", ""),
                }
                gorse_feedback.append(gorse_fb)

            url = f"{self.base_url}/api/feedback"

            # Log detailed payload information
            logger.info(f"=== FEEDBACK PAYLOAD DEBUG ===")
            logger.info(f"URL: {url}")
            logger.info(f"Total feedback records to send: {len(gorse_feedback)}")
            logger.info(f"Headers: {self._get_headers()}")

            # Log sample of first few feedback records (truncated for readability)
            for i, feedback in enumerate(
                gorse_feedback[:3]
            ):  # Show first 3 feedback records
                logger.info(f"Feedback {i+1} payload: {json.dumps(feedback, indent=2)}")

            if len(gorse_feedback) > 3:
                logger.info(f"... and {len(gorse_feedback) - 3} more feedback records")
            logger.info(f"=== END FEEDBACK PAYLOAD DEBUG ===")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=gorse_feedback, headers=self._get_headers()
                )

                # Check HTTP status
                if response.status_code == 200:
                    result = response.json()
                    row_affected = result.get("RowAffected", 0)

                    logger.info(
                        f"Successfully inserted {row_affected} feedback records to Gorse (sent {len(gorse_feedback)})"
                    )

                    return {
                        "success": True,
                        "count": row_affected,
                        "total_sent": len(gorse_feedback),
                        "response": result,
                        "timestamp": now_utc(),
                    }
                else:
                    # HTTP error
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.error(f"HTTP error inserting feedback batch: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "count": 0,
                    }

        except httpx.TimeoutException:
            error_msg = "Request timeout"
            logger.error(f"Timeout inserting feedback batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}
        except httpx.ConnectError:
            error_msg = "Connection error"
            logger.error(f"Connection error inserting feedback batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to insert feedback batch: {error_msg}")
            return {"success": False, "error": error_msg, "count": 0}

    async def get_recommendations(
        self, user_id: str, n: int = 10, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recommendations for a user from Gorse

        Args:
            user_id: User ID to get recommendations for
            n: Number of recommendations to return
            category: Optional category filter

        Returns:
            Recommendations response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category

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
        self, item_id: str, n: int = 10, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get similar items (neighbors) for a given item

        Args:
            item_id: Item ID to get neighbors for
            n: Number of neighbors to return
            category: Optional category filter

        Returns:
            Item neighbors response
        """
        try:
            params = {"n": n}
            if category:
                params["category"] = category

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
        self, session_data: Dict[str, Any], n: int = 10, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get session-based recommendations from Gorse

        Args:
            session_data: Session data including user interactions
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

            response = await self.client.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()

            # Gorse returns a list of user IDs with scores
            if isinstance(result, list):
                logger.info(f"Found {len(result)} user neighbors for user {user_id}")
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
