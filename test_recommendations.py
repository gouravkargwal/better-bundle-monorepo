#!/usr/bin/env python3
"""
Test script for Gorse Recommendation API
Tests various recommendation endpoints and functionality
"""

import requests
import json
import time
from typing import Dict, List, Any, Optional

# Configuration
GORSE_BASE_URL = "http://localhost:8088"  # Using master port since server has issues
API_KEY = "local_dev_key"  # From local.env
SHOP_ID = "cmfctc6jf0000v3jhopnas0wa"  # Your test shop ID


class GorseRecommendationTester:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def test_health(self) -> bool:
        """Test if Gorse is healthy"""
        try:
            response = requests.get(f"{self.base_url}/api/health/ready", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print("✅ Gorse Health Check:")
                print(f"   Ready: {health_data.get('Ready', False)}")
                print(
                    f"   DataStore Connected: {health_data.get('DataStoreConnected', False)}"
                )
                print(
                    f"   CacheStore Connected: {health_data.get('CacheStoreConnected', False)}"
                )
                return health_data.get("Ready", False)
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

    def get_users(self, limit: int = 10) -> List[Dict]:
        """Get list of users from Gorse"""
        try:
            response = requests.get(
                f"{self.base_url}/api/users",
                headers=self.headers,
                params={"limit": limit},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                users = data.get("Users", []) if isinstance(data, dict) else data
                print(f"✅ Found {len(users)} users in Gorse")
                return users
            else:
                print(
                    f"❌ Failed to get users: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting users: {e}")
            return []

    def get_items(self, limit: int = 10) -> List[Dict]:
        """Get list of items from Gorse"""
        try:
            response = requests.get(
                f"{self.base_url}/api/items",
                headers=self.headers,
                params={"limit": limit},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                items = data.get("Items", []) if isinstance(data, dict) else data
                print(f"✅ Found {len(items)} items in Gorse")
                return items
            else:
                print(
                    f"❌ Failed to get items: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting items: {e}")
            return []

    def get_feedback(self, limit: int = 10) -> List[Dict]:
        """Get feedback data from Gorse"""
        try:
            response = requests.get(
                f"{self.base_url}/api/feedback",
                headers=self.headers,
                params={"limit": limit},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                feedback = data.get("Feedback", []) if isinstance(data, dict) else data
                print(f"✅ Found {len(feedback)} feedback records in Gorse")
                return feedback
            else:
                print(
                    f"❌ Failed to get feedback: {response.status_code} - {response.text}"
                )
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
                print(
                    f"✅ Got {len(recommendations)} recommendations for user {user_id}"
                )
                return recommendations
            else:
                print(
                    f"❌ Failed to get recommendations for user {user_id}: {response.status_code} - {response.text}"
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
                print(f"✅ Got {len(recommendations)} similar items for item {item_id}")
                return recommendations
            else:
                print(
                    f"❌ Failed to get similar items for item {item_id}: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting similar items for item {item_id}: {e}")
            return []

    def get_popular_items(self, n: int = 10) -> List[str]:
        """Get popular items"""
        try:
            response = requests.get(
                f"{self.base_url}/api/popular",
                headers=self.headers,
                params={"n": n},
                timeout=10,
            )
            if response.status_code == 200:
                popular = response.json()
                print(f"✅ Got {len(popular)} popular items")
                return popular
            else:
                print(
                    f"❌ Failed to get popular items: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting popular items: {e}")
            return []

    def get_latest_items(self, n: int = 10) -> List[str]:
        """Get latest items"""
        try:
            response = requests.get(
                f"{self.base_url}/api/latest",
                headers=self.headers,
                params={"n": n},
                timeout=10,
            )
            if response.status_code == 200:
                latest = response.json()
                print(f"✅ Got {len(latest)} latest items")
                return latest
            else:
                print(
                    f"❌ Failed to get latest items: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting latest items: {e}")
            return []

    def get_user_neighbors(self, user_id: str, n: int = 10) -> List[str]:
        """Get similar users for a specific user"""
        try:
            response = requests.get(
                f"{self.base_url}/api/user/{user_id}/neighbors",
                headers=self.headers,
                params={"n": n},
                timeout=10,
            )
            if response.status_code == 200:
                neighbors = response.json()
                print(f"✅ Got {len(neighbors)} similar users for user {user_id}")
                return neighbors
            else:
                print(
                    f"❌ Failed to get similar users for user {user_id}: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"❌ Error getting similar users for user {user_id}: {e}")
            return []

    def test_all_recommendations(self):
        """Test all recommendation endpoints"""
        print("🚀 Starting Gorse Recommendation API Tests")
        print("=" * 50)

        # Test health
        if not self.test_health():
            print("❌ Gorse is not healthy, stopping tests")
            return

        print("\n📊 Data Overview:")
        print("-" * 30)

        # Get data overview
        users = self.get_users(5)
        items = self.get_items(5)
        feedback = self.get_feedback(5)

        print(f"Debug - users: {len(users)} users found")
        print(f"Debug - items: {len(items)} items found")
        print(f"Debug - feedback: {len(feedback)} feedback records found")

        if not users or not items:
            print("❌ No users or items found, cannot test recommendations")
            return

        print("\n🎯 Testing Recommendation Endpoints:")
        print("-" * 40)

        # Test popular items
        print("\n1. Popular Items:")
        popular = self.get_popular_items(5)
        if popular:
            print(f"   Popular items: {popular}")

        # Test latest items
        print("\n2. Latest Items:")
        latest = self.get_latest_items(5)
        if latest:
            print(f"   Latest items: {latest}")

        # Test user recommendations
        print("\n3. User Recommendations:")
        for user in users[:3]:  # Test first 3 users
            user_id = user.get("UserId", "")
            if user_id:
                recommendations = self.get_user_recommendations(user_id, 5)
                if recommendations:
                    print(f"   User {user_id}: {recommendations}")

        # Test item recommendations
        print("\n4. Similar Items:")
        for item in items[:3]:  # Test first 3 items
            item_id = item.get("ItemId", "")
            if item_id:
                similar = self.get_item_recommendations(item_id, 5)
                if similar:
                    print(f"   Item {item_id}: {similar}")

        # Test user neighbors
        print("\n5. Similar Users:")
        for user in users[:2]:  # Test first 2 users
            user_id = user.get("UserId", "")
            if user_id:
                neighbors = self.get_user_neighbors(user_id, 5)
                if neighbors:
                    print(f"   User {user_id}: {neighbors}")

        print("\n✅ Recommendation API tests completed!")


def main():
    """Main test function"""
    tester = GorseRecommendationTester(GORSE_BASE_URL, API_KEY)
    tester.test_all_recommendations()


if __name__ == "__main__":
    main()
