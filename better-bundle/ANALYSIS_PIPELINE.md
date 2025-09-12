# Analysis Pipeline Integration

This document explains how the analysis pipeline is integrated with the Shopify app installation process.

## Overview

When a shop installs the BetterBundle app, the system automatically triggers a comprehensive analysis pipeline that:

1. **Collects Data** - Gathers products, customers, orders, and behavioral events from Shopify
2. **Processes Data** - Transforms raw data into structured formats for analysis
3. **Computes Features** - Generates ML features for recommendation algorithms
4. **Trains Models** - Builds personalized recommendation models
5. **Sets Up Monitoring** - Establishes ongoing analysis and retraining schedules

## Architecture

```
Shopify App Installation
         ↓
   afterAuth Hook
         ↓
AnalysisPipelineService
         ↓
Python Worker API
         ↓
Redis Stream (DATA_JOB_STREAM)
         ↓
Data Collection Consumer
         ↓
ML Pipeline Processing
```

## Components

### 1. AnalysisPipelineService (`app/services/analysis-pipeline.service.ts`)

A dedicated service class that handles communication with the Python worker:

- `triggerInitialAnalysis()` - Triggers the initial data collection pipeline
- `triggerScheduledAnalysis()` - Triggers scheduled analysis jobs
- `checkWorkerHealth()` - Verifies Python worker availability

### 2. Shopify Integration (`app/shopify.server.ts`)

The `afterAuth` hook automatically triggers the analysis pipeline when:

- A new shop installs the app
- An existing shop re-authenticates

### 3. Manual Trigger Route (`app/routes/app.trigger-analysis.tsx`)

Provides a REST endpoint for manually triggering the analysis pipeline:

- `POST /app/trigger-analysis` - Manually trigger analysis for the current shop

## Configuration

### Environment Variables

Set the following environment variable to configure the Python worker URL:

```bash
PYTHON_WORKER_URL=http://localhost:8000  # Development
PYTHON_WORKER_URL=https://your-worker-url.com  # Production
```

### Python Worker Endpoints

The service communicates with these Python worker endpoints:

- `POST /api/data-collection/trigger` - Triggers data collection jobs
- `GET /health` - Health check endpoint

## Usage

### Automatic Triggering

The analysis pipeline is automatically triggered during app installation. No manual intervention required.

### Manual Triggering

You can manually trigger the analysis pipeline using the REST endpoint:

```bash
curl -X POST https://your-app-url.com/app/trigger-analysis \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-session-token"
```

### Response Format

```json
{
  "success": true,
  "message": "Analysis pipeline triggered successfully",
  "jobId": "data_collection_shop123_1234567890",
  "eventId": "1234567890-0"
}
```

## Error Handling

The service includes comprehensive error handling:

- **Network Errors** - Graceful handling of connection failures
- **API Errors** - Detailed error logging with status codes
- **Validation Errors** - Input validation for required parameters
- **Timeout Handling** - Configurable timeouts for health checks

## Monitoring

### Logs

The service provides detailed logging:

```
🚀 Triggering initial analysis pipeline { shopDomain: "example.myshopify.com", shopId: "example" }
✅ Analysis pipeline triggered successfully { jobId: "data_collection_example_1234567890", eventId: "1234567890-0" }
```

### Health Checks

Use the health check method to verify Python worker availability:

```typescript
const isHealthy = await AnalysisPipelineService.checkWorkerHealth();
```

## Development

### Testing

1. **Local Development**: Set `PYTHON_WORKER_URL=http://localhost:8000`
2. **Manual Testing**: Use the `/app/trigger-analysis` endpoint
3. **Health Checks**: Verify Python worker is running before testing

### Debugging

Enable detailed logging by checking the console output during app installation or manual triggers.

## Production Considerations

1. **Environment Variables**: Ensure `PYTHON_WORKER_URL` is set correctly
2. **Error Handling**: Monitor logs for failed pipeline triggers
3. **Performance**: The pipeline runs asynchronously and doesn't block app installation
4. **Retry Logic**: Built-in retry mechanisms handle temporary failures

## Related Files

- `app/services/analysis-pipeline.service.ts` - Main service implementation
- `app/shopify.server.ts` - Shopify app configuration and afterAuth hook
- `app/routes/app.trigger-analysis.tsx` - Manual trigger endpoint
- `python-worker/app/main.py` - Python worker API endpoints
- `python-worker/app/consumers/data_collection_consumer.py` - Data collection consumer
