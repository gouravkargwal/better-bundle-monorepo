# Gorse Integration with Python Worker

This document explains how the Python Worker integrates with the Gorse recommendation engine.

## Overview

The Python Worker now includes a Gorse service that:

1. **Automatically sends data to Gorse** after feature computation
2. **Triggers model training** by sending data to Gorse APIs
3. **Serves recommendations** through Gorse APIs
4. **Handles feedback** for continuous learning

## How It Works

### 1. Automatic Data Flow

```
Data Collection → Feature Computation → Gorse Training → ML Training Event
```

When a data job completes:

1. Data is collected from Shopify
2. Features are computed and stored
3. **Data is automatically sent to Gorse** (if enabled)
4. Gorse starts training automatically
5. ML training event is published to Redis Streams

### 2. Gorse Training Process

The Gorse service:

- Checks if shop has enough data for training
- Prepares training data (items, users, feedback)
- Sends data to Gorse via REST APIs
- Gorse automatically starts training when new data arrives

### 3. Recommendation Serving

After training, the service can:

- Get user-based recommendations
- Get item-based recommendations
- Get popular items
- Filter by categories
- Handle confidence thresholds

## Configuration

### Environment Variables

```bash
# Enable Gorse integration
ENABLE_GORSE_SYNC=true

# Gorse service URL
GORSE_BASE_URL=http://localhost:8088

# API keys
GORSE_API_KEY=your_api_key
GORSE_MASTER_KEY=your_master_key

# Training thresholds
MIN_ORDERS_FOR_TRAINING=50
MIN_PRODUCTS_FOR_TRAINING=20
MAX_RECOMMENDATIONS=10
MIN_CONFIDENCE_THRESHOLD=0.3
```

### Gorse Service Requirements

- **Minimum Orders**: 50 orders required for training
- **Minimum Products**: 20 products required for training
- **Data Quality**: Orders must have customer IDs and line items

## API Endpoints

### Training

- `POST /api/v1/gorse/train` - Manually trigger training
- `GET /api/v1/gorse/status/{shop_id}` - Check training status

### Recommendations

- `GET /api/v1/gorse/recommendations/{shop_id}` - Get recommendations
- `GET /api/v1/gorse/recommendations/{shop_id}/popular` - Get popular items
- `GET /api/v1/gorse/recommendations/{shop_id}/user/{user_id}` - User recommendations
- `GET /api/v1/gorse/recommendations/{shop_id}/item/{item_id}` - Item recommendations

### Feedback

- `POST /api/v1/gorse/feedback` - Submit user feedback

### Health

- `GET /api/v1/gorse/health` - Check Gorse service health

## Data Format

### Items for Gorse

```json
{
  "ItemId": "product_id",
  "Timestamp": "2024-01-01T00:00:00Z",
  "Categories": ["category"],
  "Tags": [],
  "Labels": [],
  "Comment": "Product title"
}
```

### Users for Gorse

```json
{
  "UserId": "customer_id",
  "Labels": [],
  "Subscribe": "true",
  "Comment": "Customer from shop_id"
}
```

### Feedback for Gorse

```json
{
  "FeedbackType": "star",
  "UserId": "customer_id",
  "ItemId": "product_id",
  "Timestamp": "2024-01-01T00:00:00Z",
  "Comment": "Purchase from order_id"
}
```

## Integration Points

### 1. Data Processor

The `DataProcessor` automatically calls Gorse after feature computation:

```python
# Step 5.5: Send data to Gorse for automatic training
if settings.ENABLE_GORSE_SYNC:
    gorse_result = await gorse_service.train_model_for_shop(
        shop_id=request.shop_id,
        shop_domain=request.shop_domain
    )
```

### 2. Redis Streams

Gorse training is triggered as part of the data processing pipeline:

- `features-computed` event published
- Gorse training initiated
- `ml-training` event published
- User notification sent

### 3. Error Handling

- Gorse failures don't stop the main data processing
- Errors are logged and warnings are sent
- Training continues with ML training event

## Deployment

### 1. Gorse Service

Deploy Gorse separately (not part of this worker):

```bash
# Example: Deploy to your server
docker run -d --name gorse \
  -p 8088:8088 \
  -v /var/lib/gorse:/var/lib/gorse \
  gorse/gorse:latest
```

### 2. Python Worker

The worker will automatically connect to Gorse when:

- `ENABLE_GORSE_SYNC=true`
- `GORSE_BASE_URL` is accessible
- Valid API keys are provided

### 3. Health Checks

Monitor Gorse health via:

- `GET /api/v1/gorse/health`
- Worker health endpoint includes Gorse status
- Logs show Gorse training results

## Monitoring

### Logs

Look for these log messages:

- "Data sent to Gorse successfully"
- "Gorse training failed"
- "Failed to send data to Gorse"

### Metrics

- Training duration
- Data counts (items, users, feedback)
- Success/failure rates
- API response times

## Troubleshooting

### Common Issues

1. **Gorse Connection Failed**

   - Check `GORSE_BASE_URL` is accessible
   - Verify API keys are correct
   - Check network connectivity

2. **Training Data Insufficient**

   - Ensure shop has enough orders/products
   - Check data quality (customer IDs, line items)
   - Verify data collection completed successfully

3. **API Errors**
   - Check Gorse service logs
   - Verify API endpoint responses
   - Check authentication headers

### Debug Steps

1. Check Gorse health: `GET /api/v1/gorse/health`
2. Verify data requirements: Check logs for data counts
3. Test manual training: `POST /api/v1/gorse/train`
4. Check Gorse service logs for errors

## Future Enhancements

- **Training Metadata**: Store training history and results
- **Model Versioning**: Track different model versions
- **Performance Metrics**: Monitor recommendation quality
- **A/B Testing**: Compare different recommendation strategies
- **Real-time Updates**: Stream data changes to Gorse
