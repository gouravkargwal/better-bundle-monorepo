#!/bin/bash

# Gorse Production Deployment Script
# This script deploys Gorse services for production use

set -e

echo "🚀 Starting Gorse Production Deployment..."

# Load environment variables
if [ -f "env.production" ]; then
    echo "📋 Loading production environment variables..."
    export $(cat env.production | grep -v '^#' | xargs)
else
    echo "❌ Production environment file not found: env.production"
    exit 1
fi

# Validate required environment variables
if [ -z "$GORSE_CACHE_STORE" ] || [ -z "$GORSE_DATA_STORE" ]; then
    echo "❌ Required environment variables not set:"
    echo "   GORSE_CACHE_STORE: $GORSE_CACHE_STORE"
    echo "   GORSE_DATA_STORE: $GORSE_DATA_STORE"
    exit 1
fi

echo "✅ Environment variables loaded successfully"

# Stop existing services
echo "🛑 Stopping existing Gorse services..."
docker-compose -f docker-compose.production.yml down --remove-orphans

# Clean up old volumes (optional - uncomment if needed)
# echo "🧹 Cleaning up old volumes..."
# docker volume rm gorse_worker_data gorse_server_data gorse_master_data gorse_log 2>/dev/null || true

# Start production services
echo "🚀 Starting Gorse production services..."
docker-compose -f docker-compose.production.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🏥 Checking service health..."
for service in gorse-master gorse-server gorse-worker; do
    if docker ps | grep -q "$service"; then
        echo "✅ $service is running"
    else
        echo "❌ $service failed to start"
        docker logs "gorse-$service-1" | tail -20
        exit 1
    fi
done

# Test Gorse API endpoints
echo "🧪 Testing Gorse API endpoints..."
MASTER_URL="http://localhost:8088"
SERVER_URL="http://localhost:8087"

# Test master status
if curl -s "$MASTER_URL/api/status" > /dev/null; then
    echo "✅ Gorse Master API responding"
else
    echo "❌ Gorse Master API not responding"
    exit 1
fi

# Test server health
if curl -s "$SERVER_URL/api/health" > /dev/null; then
    echo "✅ Gorse Server API responding"
else
    echo "❌ Gorse Server API not responding"
    exit 1
fi

echo "🎉 Gorse Production Deployment Completed Successfully!"
echo ""
echo "📊 Service Status:"
echo "   Master: http://localhost:8088"
echo "   Server: http://localhost:8087"
echo "   Worker: http://localhost:8089"
echo ""
echo "🔗 API Endpoints:"
echo "   Status: $MASTER_URL/api/status"
echo "   Health: $SERVER_URL/api/health"
echo ""
echo "📝 Next Steps:"
echo "   1. Test feature export: curl -X POST http://localhost:8001/api/v1/gorse/export-features/{shop_id}"
echo "   2. Trigger training: curl -X POST http://localhost:8001/api/v1/gorse/train/{shop_id}"
echo "   3. Get recommendations: curl http://localhost:8001/api/v1/gorse/recommendations/{shop_id}/{user_id}"
