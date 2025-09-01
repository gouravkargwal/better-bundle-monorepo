#!/bin/bash

# Test script for Gorse API endpoints
# Replace YOUR_APP_URL with your actual Render app URL

APP_URL="${1:-http://localhost:8088}"

echo "🧪 Testing Gorse API at: $APP_URL"
echo "=================================="

echo ""
echo "1. Testing health check..."
curl -s "$APP_URL/" | head -5

echo ""
echo "2. Testing API endpoints..."

echo "   - Getting items..."
curl -s "$APP_URL/api/items" | head -5

echo ""
echo "   - Getting users..."
curl -s "$APP_URL/api/users" | head -5

echo ""
echo "3. Testing feedback insertion..."
curl -X POST "$APP_URL/api/feedback" \
  -H 'Content-Type: application/json' \
  -d '[
    {"FeedbackType": "star", "UserId": "test_user", "ItemId": "test_item", "Timestamp": "2024-01-01"}
  ]' | head -5

echo ""
echo "4. Testing recommendation..."
curl -s "$APP_URL/api/recommend/test_user?n=5" | head -5

echo ""
echo "✅ API tests completed!"
