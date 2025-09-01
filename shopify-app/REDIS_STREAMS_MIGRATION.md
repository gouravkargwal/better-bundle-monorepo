# Redis Streams Migration Guide

## Overview

This document describes the migration from the old Bull queue system to Redis Streams for event-driven architecture in the BetterBundle Shopify app.

## What Changed

### ❌ Removed (Old System)

- **Bull Queue System**: Bull/BullMQ queues for job processing
- **Fly.io Worker Integration**: Direct HTTP calls to Fly.io worker
- **`FLY_WORKER_URL`**: Environment variable for worker endpoint
- **`api.analysis.complete.tsx`**: Old webhook endpoint for job completion

### ✅ Added (New System)

- **Redis Streams Service**: `app/core/redis/redis-streams.server.ts`
- **Event Publishing**: Direct publishing to Redis streams
- **Stream Consumers**: Python worker consumes from streams
- **New API Endpoints**:
  - `api.redis-health.tsx` - Redis connectivity test
  - `api.analysis.results.tsx` - Read results from streams

## Architecture Changes

### Before (Queue-based)

```
Shopify App → HTTP POST → Fly.io Worker → Bull Queue → Processing
```

### After (Stream-based)

```
Shopify App → Redis Stream → Python Worker → Processing → Results Stream
```

## Redis Streams

### Stream Names

- `betterbundle:data-jobs` - Data collection and analysis jobs
- `betterbundle:ml-training` - ML model training jobs
- `betterbundle:analysis-results` - Analysis completion results
- `betterbundle:user-notifications` - User notification events
- `betterbundle:features-computed` - Feature computation events

### Consumer Groups

- `data-processors` - Data processing consumers
- `ml-processors` - ML training consumers
- `notification-processors` - Notification consumers

## Code Changes

### 1. Analysis Start Endpoint (`api.analysis.start.tsx`)

- Removed axios call to Fly.io worker
- Added Redis Streams job publishing
- Job status updates to indicate queuing

### 2. Analysis Scheduler (`analysis-scheduler.server.ts`)

- Replaced Fly.io worker calls with Redis Streams
- Added scheduled analysis publishing
- Manual analysis trigger via streams

### 3. New Redis Service (`redis-streams.server.ts`)

- Redis connection management
- Stream publishing methods
- Consumer group management
- Health checks and monitoring

## Environment Variables

### Required

```bash
REDIS_HOST=localhost          # Redis server host
REDIS_PORT=6379              # Redis server port
REDIS_PASSWORD=               # Redis password (if any)
REDIS_DB=0                   # Redis database number
```

### Removed

```bash
FLY_WORKER_URL               # No longer needed
```

## Testing

### 1. Test Redis Connection

```bash
cd shopify-app
node scripts/test-redis-streams.js
```

### 2. Test API Endpoints

- `GET /api/redis-health` - Redis connectivity test
- `GET /api/analysis/results` - Read analysis results
- `POST /api/analysis/start` - Start analysis (now uses streams)

### 3. Monitor Streams

```bash
# Using redis-cli
redis-cli xlen betterbundle:data-jobs
redis-cli xlen betterbundle:analysis-results
```

## Benefits

1. **Decoupled Architecture**: No direct HTTP dependencies between services
2. **Scalability**: Multiple consumers can process from same streams
3. **Reliability**: Redis persistence and consumer groups
4. **Monitoring**: Better visibility into event flow
5. **Replay**: Can replay events from streams for debugging

## Migration Steps

1. ✅ **Completed**: Remove Bull queue dependencies
2. ✅ **Completed**: Create Redis Streams service
3. ✅ **Completed**: Update analysis endpoints
4. ✅ **Completed**: Update scheduler
5. ✅ **Completed**: Remove old completion webhook
6. ✅ **Completed**: Add health check endpoints

## Next Steps

1. **Test Integration**: Verify Python worker can consume from streams
2. **Monitor Performance**: Check Redis memory usage and performance
3. **Add Metrics**: Implement stream monitoring and alerting
4. **Error Handling**: Add dead letter queues for failed events
5. **Documentation**: Update API documentation for new endpoints

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify host/port/password in environment
   - Test with `redis-cli ping`

2. **Stream Not Found**
   - Streams are created automatically on first message
   - Check consumer group creation logs

3. **Messages Not Consumed**
   - Verify Python worker is running
   - Check consumer group configuration
   - Monitor pending message counts

### Debug Commands

```bash
# Check stream status
redis-cli xinfo stream betterbundle:data-jobs

# Check consumer groups
redis-cli xinfo groups betterbundle:data-jobs

# Check pending messages
redis-cli xpending betterbundle:data-jobs data-processors
```

## Dependencies

### Added

- `ioredis` - Redis client for Node.js

### Removed

- `bull` - Bull queue system
- `axios` - HTTP client (kept for other uses)

## Performance Considerations

1. **Memory Usage**: Redis streams can grow large, monitor memory
2. **Consumer Groups**: Use multiple consumers for parallel processing
3. **Stream Trimming**: Consider trimming old messages to save memory
4. **Connection Pooling**: Redis connections are pooled automatically
