# 🧪 BetterBundle Redis Testing Commands

This file contains all the Redis commands needed to test the BetterBundle event-driven architecture.

## 📋 Prerequisites

1. **Redis CLI installed** or access to Redis instance
2. **BetterBundle Python Worker running** on port 8000
3. **Development store information** (replace placeholders with your actual values)

## 🔧 Development Store Information

Replace these placeholders with your actual development store details:

```bash
# Your development store details (replace with actual values)
DEV_SHOP_ID="cmf1d6ies0000v3qnz2ey0luz"
DEV_SHOP_DOMAIN="vnsaid.myshopify.com"
DEV_ACCESS_TOKEN="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"
```

## 🌐 Redis Connection

```bash
# Connect to Redis (adjust host/port/password as needed)
redis-cli -h your-redis-host -p 6379 -a your-redis-password

# Or if using local Redis
redis-cli
```

## 📊 Stream Information

### List All Streams

```bash
# List all streams in the system
KEYS betterbundle:*

# Expected streams:
# - betterbundle:data-jobs
# - betterbundle:ml-training
# - betterbundle:analysis-results
# - betterbundle:user-notifications
# - betterbundle:features-computed
# - betterbundle:ml-training-complete
```

### Check Stream Lengths

```bash
# Check how many messages are in each stream
XLEN betterbundle:data-jobs
XLEN betterbundle:ml-training
XLEN betterbundle:analysis-results
XLEN betterbundle:user-notifications
XLEN betterbundle:features-computed
```

## 🚀 Test Data Job Event (Analysis)

### Publish Analysis Job Event

```bash
# Trigger a complete analysis job
XADD betterbundle:data-jobs * \
  jobId "test_analysis_$(date +%s)" \
  shopId "cmf1d6ies0000v3qnz2ey0luz" \
  shopDomain "vnsaid.myshopify.com" \
  accessToken "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" \
  type "analysis" \
  priority "normal" \
  timestamp $(date +%s)000 \
  source "manual_test"
```

### Publish Analysis Job Event (Alternative Format)

```bash
# Alternative format with snake_case fields
XADD betterbundle:data-jobs * \
  job_id "test_analysis_$(date +%s)" \
  shop_id "cmf1d6ies0000v3qnz2ey0luz" \
  shop_domain "vnsaid.myshopify.com" \
  access_token "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" \
  job_type "complete" \
  priority "normal" \
  timestamp $(date +%s)000 \
  source "manual_test"
```

## 🔄 Test ML Training Event

### Publish ML Training Event

```bash
# Trigger ML training after data collection
XADD betterbundle:ml-training * \
  job_id "test_ml_training_$(date +%s)" \
  shop_id "cmf1d6ies0000v3qnz2ey0luz" \
  shop_domain "vnsaid.myshopify.com" \
  data_collection_completed "true" \
  training_status "queued" \
  timestamp $(date +%s)000 \
  source "manual_test"
```

## 📈 Test Analysis Results Event

### Publish Analysis Results

```bash
# Publish analysis completion results
XADD betterbundle:analysis-results * \
  job_id "test_analysis_$(date +%s)" \
  shop_id "cmf1d6ies0000v3qnz2ey0luz" \
  status "completed" \
  results '{"bundles_found": 15, "confidence": 0.85, "revenue_potential": 1250.50}' \
  timestamp $(date +%s)000 \
  source "manual_test"
```

## 🔔 Test User Notification Event

### Publish User Notification

```bash
# Send a notification to the user
XADD betterbundle:user-notifications * \
  shop_id "cmf1d6ies0000v3qnz2ey0luz" \
  notification_type "analysis_complete" \
  message "Your bundle analysis is complete! 15 bundles found with $1,250 revenue potential." \
  data '{"bundles_count": 15, "revenue_potential": 1250.50}' \
  timestamp $(date +%s)000 \
  source "manual_test"
```

## ⚙️ Test Features Computed Event

### Publish Features Computed

```bash
# Indicate that features have been computed
XADD betterbundle:features-computed * \
  job_id "test_features_$(date +%s)" \
  shop_id "cmf1d6ies0000v3qnz2ey0luz" \
  features_ready "true" \
  metadata '{"feature_count": 25, "computation_time": 45.2}' \
  timestamp $(date +%s)000 \
  source "manual_test"
```

## 👥 Consumer Group Management

### Create Consumer Groups

```bash
# Create consumer groups for each stream
XGROUP CREATE betterbundle:data-jobs data-processors $ MKSTREAM
XGROUP CREATE betterbundle:ml-training data-processors $ MKSTREAM
XGROUP CREATE betterbundle:analysis-results data-processors $ MKSTREAM
XGROUP CREATE betterbundle:user-notifications notification-processors $ MKSTREAM
XGROUP CREATE betterbundle:features-computed data-processors $ MKSTREAM
```

### Check Consumer Groups

```bash
# List consumer groups for each stream
XINFO GROUPS betterbundle:data-jobs
XINFO GROUPS betterbundle:ml-training
XINFO GROUPS betterbundle:analysis-results
XINFO GROUPS betterbundle:user-notifications
XINFO GROUPS betterbundle:features-computed
```

### Check Consumer Group Info

```bash
# Get detailed info about consumer groups
XINFO GROUP betterbundle:data-jobs data-processors
XINFO GROUP betterbundle:ml-training data-processors
```

## 📖 Reading Streams

### Read All Messages from a Stream

```bash
# Read all messages from data-jobs stream
XREAD COUNT 100 STREAMS betterbundle:data-jobs 0

# Read all messages from ml-training stream
XREAD COUNT 100 STREAMS betterbundle:ml-training 0
```

### Read Messages from Consumer Group

```bash
# Read pending messages from consumer group
XREADGROUP GROUP data-processors test-consumer COUNT 10 STREAMS betterbundle:data-jobs >

# Read specific message range
XREADGROUP GROUP data-processors test-consumer COUNT 10 STREAMS betterbundle:data-jobs 0
```

## 🔍 Stream Analysis

### Get Stream Info

```bash
# Get detailed information about each stream
XINFO STREAM betterbundle:data-jobs
XINFO STREAM betterbundle:ml-training
XINFO STREAM betterbundle:analysis-results
```

### Check Pending Messages

```bash
# Check pending messages in consumer groups
XPENDING betterbundle:data-jobs data-processors
XPENDING betterbundle:ml-training data-processors
```

## 🧹 Cleanup Commands

### Clear Specific Streams

```bash
# Clear all messages from a stream (use with caution!)
DEL betterbundle:data-jobs
DEL betterbundle:ml-training
DEL betterbundle:analysis-results
```

### Clear All BetterBundle Streams

```bash
# Clear all BetterBundle streams (use with caution!)
DEL betterbundle:data-jobs betterbundle:ml-training betterbundle:analysis-results betterbundle:user-notifications betterbundle:features-computed
```

## 🚀 Complete Testing Workflow

### 1. Test Basic Connectivity

```bash
# Connect to Redis
redis-cli -h your-redis-host -p 6379 -a your-redis-password

# Test connection
PING

# Should return: PONG
```

### 2. Check Existing Streams

```bash
# List all streams
KEYS betterbundle:*

# Check stream lengths
XLEN betterbundle:data-jobs
XLEN betterbundle:ml-training
```

### 3. Trigger Analysis Job

```bash
# Publish analysis job event (all on one line)
XADD betterbundle:data-jobs * jobId "test_analysis_$(date +%s)" shopId "cmf1d6ies0000v3qnz2ey0luz" shopDomain "vnsaid.myshopify.com" accessToken "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" type "analysis" priority "normal" timestamp $(date +%s)000 source "manual_test"

# Or use the API endpoint instead:
curl -X POST http://localhost:8000/api/v1/data-jobs/queue \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "cmf1d6ies0000v3qnz2ey0luz",
    "shop_domain": "vnsaid.myshopify.com",
    "access_token": "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",
    "job_type": "complete"
  }'
```

### 4. Monitor Progress

```bash
# Check if message was added
XLEN betterbundle:data-jobs

# Read the message
XREAD COUNT 1 STREAMS betterbundle:data-jobs 0
```

### 5. Check Worker Processing

```bash
# Monitor the worker console for processing logs
# You should see:
# - "Processing data job from stream"
# - "Data job processing completed successfully"
# - "Shop onboarding status updated"
```

## 🔧 Troubleshooting

### Common Issues

1. **Connection Failed**

   ```bash
   # Check Redis connection
   redis-cli -h your-redis-host -p 6379 -a your-redis-password PING
   ```

2. **Stream Not Found**

   ```bash
   # Create stream if it doesn't exist
   XADD betterbundle:data-jobs * test "value"
   ```

3. **Consumer Group Issues**

   ```bash
   # Recreate consumer group
   XGROUP DESTROY betterbundle:data-jobs data-processors
   XGROUP CREATE betterbundle:data-jobs data-processors $ MKSTREAM
   ```

4. **Authentication Issues**
   ```bash
   # Check if password is required
   redis-cli -h your-redis-host -p 6379
   # If password needed:
   AUTH your-redis-password
   ```

## 📝 Notes

- **Message IDs**: Use `*` for auto-generated IDs or specify custom IDs
- **Timestamps**: Use `$(date +%s)000` for current timestamp in milliseconds
- **Field Names**: The system handles both camelCase and snake_case field names
- **Consumer Groups**: Multiple workers can consume from the same consumer group
- **Stream Persistence**: Messages are stored until explicitly deleted

## 🎯 Next Steps

After testing Redis streams:

1. **Check Python Worker logs** for processing status
2. **Monitor database** for job status updates
3. **Verify onboarding status** changes in the shop table
4. **Test the complete flow** from analysis to widget setup

Happy testing! 🚀
