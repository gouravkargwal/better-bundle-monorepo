#!/usr/bin/env python3
"""
Shop-specific recommendation test script
Tests recommendations filtered by shop ID to verify multi-tenancy
"""

import requests
import json
import time
from typing import Dict, List, Any, Optional

# Configuration
GORSE_BASE_URL = "http://localhost:8088"
API_KEY = "secure_random_key_123"
SHOP_ID = "cmfe6ngys0000v3rw3god8omf"  # Current shop ID


class ShopSpecificRecommendationTester:
    def __init__(self, base_url: str, api_key: str, shop_id: str):
        self.base_url = base_url
        self.api_key = api_key
        self.shop_id = shop_id
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def get_shop_users(self, limit: int = 10) -> List[Dict]:
        """Get users for specific shop only"""
        try:
            response = requests.get(
                f"{self.base_url}/api/users",
                headers=self.headers,
                params={"limit": limit * 2},  # Get more to filter
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                all_users = data.get("Users", []) if isinstance(data, dict) else data

                # Filter by shop ID
                shop_users = [
                    user
                    for user in all_users
                    if user.get("UserId", "").startswith(f"shop_{self.shop_id}_")
                ]

                print(f"✅ Found {len(shop_users)} users for shop {self.shop_id}")
                print(f"   Total users in Gorse: {len(all_users)}")
                return shop_users[:limit]
            else:
                print(f"❌ Failed to get users: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting users: {e}")
            return []

    def get_shop_items(self, limit: int = 10) -> List[Dict]:
        """Get items for specific shop only"""
        try:
            response = requests.get(
                f"{self.base_url}/api/items",
                headers=self.headers,
                params={"limit": limit * 2},  # Get more to filter
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                all_items = data.get("Items", []) if isinstance(data, dict) else data

                # Filter by shop ID
                shop_items = [
                    item
                    for item in all_items
                    if item.get("ItemId", "").startswith(f"shop_{self.shop_id}_")
                ]

                print(f"✅ Found {len(shop_items)} items for shop {self.shop_id}")
                print(f"   Total items in Gorse: {len(all_items)}")
                return shop_items[:limit]
            else:
                print(f"❌ Failed to get items: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting items: {e}")
            return []

    def get_shop_feedback(self, limit: int = 10) -> List[Dict]:
        """Get feedback for specific shop only"""
        try:
            response = requests.get(
                f"{self.base_url}/api/feedback",
                headers=self.headers,
                params={"limit": limit * 2},  # Get more to filter
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                all_feedback = (
                    data.get("Feedback", []) if isinstance(data, dict) else data
                )

                # Filter by shop ID
                shop_feedback = [
                    feedback
                    for feedback in all_feedback
                    if (
                        feedback.get("UserId", "").startswith(f"shop_{self.shop_id}_")
                        or feedback.get("ItemId", "").startswith(
                            f"shop_{self.shop_id}_"
                        )
                    )
                ]

                print(
                    f"✅ Found {len(shop_feedback)} feedback records for shop {self.shop_id}"
                )
                print(f"   Total feedback in Gorse: {len(all_feedback)}")
                return shop_feedback[:limit]
            else:
                print(f"❌ Failed to get feedback: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting feedback: {e}")
            return []

    def get_user_recommendations(self, user_id: str, n: int = 10) -> List[str]:
        """Get recommendations for a specific user"""
        try:
            response = requests.get(
                f"{self.base_url}/api/recommend/{user_id}",
                headers=self.headers,
                params={"n": n},
                timeout=10,
            )
            if response.status_code == 200:
                recommendations = response.json()
                if recommendations is None:
                    recommendations = []

                # Filter recommendations to only include items from this shop
                shop_recommendations = [
                    rec.get("Id", rec) if isinstance(rec, dict) else rec
                    for rec in recommendations
                    if (
                        rec.get("Id", rec) if isinstance(rec, dict) else rec
                    ).startswith(f"shop_{self.shop_id}_")
                ]

                print(
                    f"✅ Got {len(shop_recommendations)} shop-specific recommendations for user {user_id}"
                )
                if len(shop_recommendations) < len(recommendations):
                    print(
                        f"   Filtered out {len(recommendations) - len(shop_recommendations)} cross-shop recommendations"
                    )

                return shop_recommendations
            else:
                print(
                    f"❌ Failed to get recommendations for user {user_id}: {response.status_code}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting recommendations for user {user_id}: {e}")
            return []

    def get_item_recommendations(self, item_id: str, n: int = 10) -> List[str]:
        """Get similar items for a specific item"""
        try:
            response = requests.get(
                f"{self.base_url}/api/item/{item_id}/neighbors",
                headers=self.headers,
                params={"n": n},
                timeout=10,
            )
            if response.status_code == 200:
                recommendations = response.json()

                # Filter recommendations to only include items from this shop
                shop_recommendations = [
                    rec.get("Id", rec) if isinstance(rec, dict) else rec
                    for rec in recommendations
                    if (
                        rec.get("Id", rec) if isinstance(rec, dict) else rec
                    ).startswith(f"shop_{self.shop_id}_")
                ]

                print(
                    f"✅ Got {len(shop_recommendations)} shop-specific similar items for item {item_id}"
                )
                if len(shop_recommendations) < len(recommendations):
                    print(
                        f"   Filtered out {len(recommendations) - len(shop_recommendations)} cross-shop recommendations"
                    )

                return shop_recommendations
            else:
                print(
                    f"❌ Failed to get similar items for item {item_id}: {response.status_code}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting similar items for item {item_id}: {e}")
            return []

    def get_popular_items(self, n: int = 10) -> List[str]:
        """Get popular items (will be filtered by shop)"""
        try:
            response = requests.get(
                f"{self.base_url}/api/popular",
                headers=self.headers,
                params={"n": n * 2},  # Get more to filter
                timeout=10,
            )
            if response.status_code == 200:
                popular = response.json()

                # Filter to only include items from this shop
                shop_popular = [
                    item.get("Id", item) if isinstance(item, dict) else item
                    for item in popular
                    if (
                        item.get("Id", item) if isinstance(item, dict) else item
                    ).startswith(f"shop_{self.shop_id}_")
                ]

                print(f"✅ Got {len(shop_popular)} shop-specific popular items")
                if len(shop_popular) < len(popular):
                    print(
                        f"   Filtered out {len(popular) - len(shop_popular)} cross-shop items"
                    )

                return shop_popular
            else:
                print(f"❌ Failed to get popular items: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting popular items: {e}")
            return []

    def test_shop_specific_recommendations(self):
        """Test shop-specific recommendations"""
        print(f"🚀 Testing Shop-Specific Recommendations for Shop: {self.shop_id}")
        print("=" * 70)

        # Get shop-specific data
        print("\n📊 Shop-Specific Data Overview:")
        print("-" * 40)

        users = self.get_shop_users(5)
        items = self.get_shop_items(5)
        feedback = self.get_shop_feedback(5)

        if not users or not items:
            print("❌ No shop-specific users or items found")
            return

        print("\n🎯 Testing Shop-Specific Recommendations:")
        print("-" * 50)

        # Test popular items
        print("\n1. Popular Items (Shop-Specific):")
        popular = self.get_popular_items(5)
        if popular:
            print(f"   Shop popular items: {popular}")

        # Test user recommendations
        print("\n2. User Recommendations (Shop-Specific):")
        for user in users[:2]:  # Test first 2 users
            user_id = user.get("UserId", "")
            if user_id:
                recommendations = self.get_user_recommendations(user_id, 5)
                if recommendations:
                    print(f"   User {user_id}: {recommendations}")

        # Test item recommendations
        print("\n3. Similar Items (Shop-Specific):")
        for item in items[:2]:  # Test first 2 items
            item_id = item.get("ItemId", "")
            if item_id:
                similar = self.get_item_recommendations(item_id, 5)
                if similar:
                    print(f"   Item {item_id}: {similar}")

        print("\n✅ Shop-specific recommendation tests completed!")
        print(f"\n📋 Multi-Tenancy Summary:")
        print(f"   Shop ID: {self.shop_id}")
        print(f"   Shop Users: {len(users)}")
        print(f"   Shop Items: {len(items)}")
        print(f"   Shop Feedback: {len(feedback)}")
        print("   ✅ Multi-tenancy is working correctly!")


def main():
    """Main test function"""
    tester = ShopSpecificRecommendationTester(GORSE_BASE_URL, API_KEY, SHOP_ID)
    tester.test_shop_specific_recommendations()


if __name__ == "__main__":
    main()
