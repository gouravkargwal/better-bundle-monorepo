# Feature Engineering Pipeline Documentation

## Overview

The Feature Engineering Pipeline is the core system that transforms raw Shopify data into machine learning features. This document explains the complete pipeline architecture, processing modes, and optimization strategies.

## Pipeline Architecture

### High-Level Flow

```
Raw Data → Normalization → Feature Computation → ML Integration
    ↓           ↓              ↓                ↓
Shopify API → Main Tables → Feature Tables → Gorse Sync
```

### Detailed Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FEATURE ENGINEERING PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data          │───▶│  Normalization   │───▶│  Feature        │
│   Collection    │    │  Service         │    │  Computation    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ • Products      │    │ • Canonical      │    │ • Product       │
│ • Orders        │    │   Models         │    │   Features      │
│ • Customers     │    │ • Data           │    │ • User          │
│ • Collections   │    │   Validation     │    │   Features      │
│ • Interactions  │    │ • Database       │    │ • Collection    │
│                 │    │   Storage        │    │   Features      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  ML Integration │
                                               │                 │
                                               │ • Gorse Sync    │
                                               │ • Recommendations│
                                               │ • Analytics     │
                                               └─────────────────┘
```

## Processing Modes

### 1. Historical Processing

#### When to Use

- **Onboarding**: New shop setup
- **Data Refresh**: Full data reload
- **System Recovery**: After data corruption
- **Manual Triggers**: Admin-initiated full processing

#### Behavior

- **Watermarks**: Reset to start from beginning
- **Data Scope**: Process ALL available data
- **Batch Size**: Large (1,000-10,000 records)
- **Processing Time**: 5-15 minutes for full shop
- **Memory Usage**: High (loads all data)

#### Implementation

```python
# Reset watermarks for historical processing
await reset_watermarks_for_historical_processing(shop_id)

# Process all data without watermark constraints
await process_normalization_window(
    shop_id=shop_id,
    data_types=["products", "orders", "customers", "collections"],
    mode="historical"
)
```

### 2. Incremental Processing

#### When to Use

- **Webhooks**: Real-time data updates
- **Scheduled Updates**: Regular maintenance
- **API Polling**: Periodic data sync
- **Manual Updates**: Specific data refresh

#### Behavior

- **Watermarks**: Used to track last processed timestamp
- **Data Scope**: Process only NEW/CHANGED data
- **Batch Size**: Small (100-500 records)
- **Processing Time**: 30 seconds to 2 minutes
- **Memory Usage**: Low (loads only changed data)

#### Implementation

```python
# Process only changed data using watermarks
await process_normalization_window(
    shop_id=shop_id,
    data_types=["products", "orders", "customers", "collections"],
    mode="incremental"
)
```

## Pipeline Components

### 1. Data Collection Service

#### Responsibilities

- **API Integration**: Shopify GraphQL/REST API calls
- **Rate Limiting**: Respect API rate limits
- **Error Handling**: Retry failed requests
- **Data Pagination**: Handle large datasets

#### Implementation

```python
class DataCollectionService:
    async def collect_all_data(self, shop_id: str, mode: str = "incremental"):
        # Collect products, orders, customers, collections
        # Handle pagination and rate limiting
        # Return raw data for normalization
```

### 2. Normalization Service

#### Responsibilities

- **Data Transformation**: Raw API data → Canonical models
- **Data Validation**: Ensure data quality
- **Database Storage**: Store in main tables
- **Watermark Management**: Track processing progress

#### Implementation

```python
class NormalizationService:
    async def process_normalization_window(self, shop_id: str, data_types: List[str], mode: str):
        # Transform raw data to canonical models
        # Validate data quality
        # Store in database
        # Update watermarks
        # Trigger feature computation
```

### 3. Feature Engineering Service

#### Responsibilities

- **Feature Computation**: Generate ML features
- **Batch Processing**: Process data in batches
- **Parallel Processing**: Concurrent feature generation
- **Database Storage**: Store computed features

#### Implementation

```python
class FeatureEngineeringService:
    async def run_comprehensive_pipeline_for_shop(self, shop_id: str, batch_size: int, incremental: bool):
        # Load data from main tables
        # Generate features for all types
        # Store features in database
        # Trigger Gorse sync
```

### 4. ML Integration Service

#### Responsibilities

- **Gorse Sync**: Sync features to recommendation engine
- **Data Validation**: Ensure feature quality
- **Performance Monitoring**: Track sync performance
- **Error Handling**: Handle sync failures

#### Implementation

```python
class UnifiedGorseService:
    async def sync_all_features_for_shop(self, shop_id: str):
        # Load features from database
        # Transform to Gorse format
        # Sync to Gorse API
        # Monitor sync performance
```

## Feature Computation Architecture

### Batch Processing Strategy

#### Historical Mode

```python
# Large batches for historical processing
batch_sizes = {
    "products": 10000,
    "customers": 10000,
    "collections": 1000,
    "orders": 5000
}
```

#### Incremental Mode

```python
# Small batches for incremental processing
batch_sizes = {
    "products": 500,
    "customers": 500,
    "collections": 100,
    "orders": 1000
}
```

### Parallel Processing

#### Feature Type Parallelization

```python
# Process different feature types in parallel
async def compute_all_features_parallel(shop_id: str):
    tasks = [
        compute_product_features(shop_id),
        compute_user_features(shop_id),
        compute_collection_features(shop_id),
        compute_product_pair_features(shop_id)
    ]
    await asyncio.gather(*tasks)
```

#### Record Parallelization

```python
# Process multiple records in parallel within each feature type
async def process_entities_batch(entities: List[Dict], generator: BaseFeatureGenerator, context: Dict):
    # Process entities in parallel batches
    semaphore = asyncio.Semaphore(10)  # Limit concurrent processing

    async def process_entity(entity):
        async with semaphore:
            return await generator.generate_features(entity, context)

    tasks = [process_entity(entity) for entity in entities]
    return await asyncio.gather(*tasks)
```

## Performance Optimization

### Database Optimization

#### Bulk Operations

```python
# Use bulk upsert for efficient database operations
async def bulk_upsert_features(features: List[Dict], table: Table):
    stmt = pg_insert(table).values(features)
    stmt = stmt.on_conflict_do_update(
        index_elements=["shop_id", "entity_id"],
        set_=update_dict
    )
    await session.execute(stmt)
```

#### Connection Pooling

```python
# Use connection pooling for database efficiency
engine = create_async_engine(
    database_url,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)
```

### Memory Optimization

#### Streaming Processing

```python
# Process data in streams to reduce memory usage
async def process_data_stream(data_source: AsyncIterator, batch_size: int):
    async for batch in data_source:
        yield await process_batch(batch)
```

#### Garbage Collection

```python
# Explicit garbage collection for large datasets
import gc

async def process_large_dataset(data: List[Dict]):
    # Process data
    result = await compute_features(data)

    # Clean up
    del data
    gc.collect()

    return result
```

### Caching Strategy

#### Feature Caching

```python
# Cache computed features to avoid recomputation
@lru_cache(maxsize=1000)
async def get_cached_features(shop_id: str, entity_id: str, feature_type: str):
    return await compute_features(shop_id, entity_id, feature_type)
```

#### Context Caching

```python
# Cache context data for feature computation
class FeatureContextCache:
    def __init__(self):
        self.cache = {}

    async def get_context(self, shop_id: str) -> Dict:
        if shop_id not in self.cache:
            self.cache[shop_id] = await load_context_data(shop_id)
        return self.cache[shop_id]
```

## Error Handling & Recovery

### Error Types

#### Data Errors

- **Missing Fields**: Required fields not present
- **Invalid Data**: Data type mismatches
- **Corrupted Data**: Malformed JSON or data

#### Processing Errors

- **Timeout Errors**: Long-running operations
- **Memory Errors**: Insufficient memory
- **Database Errors**: Connection or query failures

#### API Errors

- **Rate Limiting**: API rate limit exceeded
- **Authentication**: Invalid API credentials
- **Network Errors**: Connection failures

### Recovery Strategies

#### Retry Logic

```python
async def retry_operation(operation: Callable, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

#### Partial Recovery

```python
async def process_with_recovery(shop_id: str, data_types: List[str]):
    results = {}
    for data_type in data_types:
        try:
            results[data_type] = await process_data_type(shop_id, data_type)
        except Exception as e:
            logger.error(f"Failed to process {data_type}: {e}")
            results[data_type] = {"error": str(e)}
    return results
```

## Monitoring & Observability

### Key Metrics

#### Processing Metrics

- **Processing Time**: Time to complete pipeline
- **Throughput**: Records processed per second
- **Success Rate**: Percentage of successful operations
- **Error Rate**: Percentage of failed operations

#### Resource Metrics

- **Memory Usage**: Peak memory consumption
- **CPU Usage**: CPU utilization during processing
- **Database Connections**: Active database connections
- **API Calls**: Number of API requests made

#### Quality Metrics

- **Data Completeness**: Percentage of complete records
- **Feature Quality**: Feature validation scores
- **Sync Success**: Gorse sync success rate
- **Data Freshness**: Age of processed data

### Logging Strategy

#### Log Levels

- **DEBUG**: Detailed processing information
- **INFO**: Processing progress and completion
- **WARNING**: Expected issues (no data available)
- **ERROR**: Actual problems requiring attention

#### Log Structure

```python
logger.info(
    "Feature computation completed",
    extra={
        "shop_id": shop_id,
        "feature_type": feature_type,
        "records_processed": count,
        "processing_time": duration,
        "success_rate": success_rate
    }
)
```

### Health Checks

#### Pipeline Health

```python
async def check_pipeline_health(shop_id: str) -> Dict[str, Any]:
    return {
        "data_collection": await check_data_collection_health(shop_id),
        "normalization": await check_normalization_health(shop_id),
        "feature_computation": await check_feature_computation_health(shop_id),
        "ml_integration": await check_ml_integration_health(shop_id)
    }
```

#### Data Quality Health

```python
async def check_data_quality_health(shop_id: str) -> Dict[str, Any]:
    return {
        "completeness": await check_data_completeness(shop_id),
        "freshness": await check_data_freshness(shop_id),
        "consistency": await check_data_consistency(shop_id),
        "accuracy": await check_data_accuracy(shop_id)
    }
```

## Configuration & Tuning

### Pipeline Configuration

```python
PIPELINE_CONFIG = {
    "batch_sizes": {
        "historical": {
            "products": 10000,
            "customers": 10000,
            "collections": 1000,
            "orders": 5000
        },
        "incremental": {
            "products": 500,
            "customers": 500,
            "collections": 100,
            "orders": 1000
        }
    },
    "timeouts": {
        "data_collection": 300,  # 5 minutes
        "normalization": 600,    # 10 minutes
        "feature_computation": 900,  # 15 minutes
        "ml_integration": 300    # 5 minutes
    },
    "retry_config": {
        "max_retries": 3,
        "backoff_factor": 2,
        "max_backoff": 60
    }
}
```

### Performance Tuning

```python
PERFORMANCE_CONFIG = {
    "parallel_workers": 10,
    "database_pool_size": 20,
    "cache_size": 1000,
    "memory_limit": "2GB",
    "cpu_limit": "4 cores"
}
```

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
