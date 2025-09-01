#!/bin/bash

echo "🚀 Gorse Deployment Script for Render"
echo "======================================"

echo ""
echo "📋 Prerequisites:"
echo "1. Create a PostgreSQL database on Render"
echo "2. Create a Redis database on Upstash"
echo "3. Push this code to your GitHub repository"
echo "4. Connect your repository to Render"
echo ""

echo "🔧 Environment Variables to set in Render:"
echo "DATABASE_URL=postgresql://username:password@host:port/database"
echo "REDIS_URL=redis://username:password@host:port/database"
echo ""

echo "📝 Next steps:"
echo "1. Go to your Render dashboard"
echo "2. Create a new Web Service"
echo "3. Connect your GitHub repository"
echo "4. Set the environment variables above"
echo "5. Deploy!"
echo ""

echo "✅ Your Gorse service will be available at:"
echo "https://your-app-name.onrender.com"
echo ""

echo "📊 Dashboard will be at:"
echo "https://your-app-name.onrender.com"
echo ""

echo "🔗 API endpoints:"
echo "- GET /api/recommend/{user_id}?n=10"
echo "- POST /api/feedback"
echo "- GET /api/items"
echo "- GET /api/users"
