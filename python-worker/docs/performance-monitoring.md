# Performance Monitoring Documentation

## Overview

This document provides comprehensive guidance on monitoring, debugging, and optimizing the BetterBundle feature computation system. It covers performance metrics, troubleshooting guides, and optimization strategies.

## Monitoring Dashboard

### Key Performance Indicators (KPIs)

#### System Health

- **Pipeline Status**: Overall system health
- **Processing Time**: End-to-end processing duration
- **Success Rate**: Percentage of successful operations
- **Error Rate**: Percentage of failed operations
- **Data Freshness**: Age of processed data

#### Resource Utilization

- **Memory Usage**: Peak memory consumption
- **CPU Usage**: CPU utilization during processing
- **Database Connections**: Active database connections
- **API Rate Limits**: Shopify API usage

#### Data Quality

- **Data Completeness**: Percentage of complete records
- **Feature Quality**: Feature validation scores
- **Sync Success**: Gorse sync success rate
- **Data Consistency**: Data integrity checks

## Performance Metrics

### Processing Metrics

#### Data Collection

```python
# Metrics to track
data_collection_metrics = {
    "total_records_collected": 1500,
    "collection_time_seconds": 45,
    "api_calls_made": 25,
    "rate_limit_hits": 0,
    "error_count": 0,
    "success_rate": 1.0
}
```

#### Normalization

```python
# Metrics to track
normalization_metrics = {
    "records_processed": 1500,
    "processing_time_seconds": 120,
    "validation_errors": 0,
    "database_operations": 1500,
    "success_rate": 1.0
}
```

#### Feature Computation

```python
# Metrics to track
feature_computation_metrics = {
    "features_generated": 1500,
    "computation_time_seconds": 300,
    "batch_processing_time": 60,
    "parallel_workers": 10,
    "success_rate": 1.0
}
```

#### ML Integration

```python
# Metrics to track
ml_integration_metrics = {
    "features_synced": 1500,
    "sync_time_seconds": 90,
    "gorse_api_calls": 15,
    "sync_success_rate": 1.0
}
```

### Resource Metrics

#### Memory Usage

```python
# Memory monitoring
memory_metrics = {
    "peak_memory_mb": 512,
    "average_memory_mb": 256,
    "memory_growth_rate": 0.1,
    "gc_collections": 5,
    "memory_leaks": 0
}
```

#### CPU Usage

```python
# CPU monitoring
cpu_metrics = {
    "peak_cpu_percent": 85,
    "average_cpu_percent": 45,
    "cpu_cores_used": 4,
    "context_switches": 1000,
    "load_average": 2.5
}
```

#### Database Performance

```python
# Database monitoring
database_metrics = {
    "active_connections": 5,
    "query_execution_time_ms": 150,
    "slow_queries": 0,
    "connection_pool_utilization": 0.25,
    "deadlocks": 0
}
```

## Monitoring Implementation

### Logging Strategy

#### Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Feature computation logging
logger.info(
    "Feature computation completed",
    shop_id=shop_id,
    feature_type=feature_type,
    records_processed=count,
    processing_time=duration,
    success_rate=success_rate,
    memory_usage=memory_usage
)
```

#### Log Levels

- **DEBUG**: Detailed processing information
- **INFO**: Processing progress and completion
- **WARNING**: Expected issues (no data available)
- **ERROR**: Actual problems requiring attention

#### Log Aggregation

```python
# Log aggregation configuration
LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO"
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "feature_computation.log",
            "level": "DEBUG"
        },
        "json": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "feature_computation.json",
            "level": "INFO",
            "formatter": "json"
        }
    }
}
```

### Metrics Collection

#### Custom Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Custom metrics
FEATURE_COMPUTATION_TIME = Histogram(
    'feature_computation_duration_seconds',
    'Time spent computing features',
    ['feature_type', 'shop_id']
)

FEATURE_COMPUTATION_COUNT = Counter(
    'feature_computation_total',
    'Total number of feature computations',
    ['feature_type', 'shop_id', 'status']
)

ACTIVE_PROCESSING_JOBS = Gauge(
    'active_processing_jobs',
    'Number of active processing jobs',
    ['job_type']
)
```

#### Health Checks

```python
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": await check_database_health(),
            "redis": await check_redis_health(),
            "kafka": await check_kafka_health(),
            "gorse": await check_gorse_health()
        },
        "metrics": {
            "memory_usage": get_memory_usage(),
            "cpu_usage": get_cpu_usage(),
            "active_jobs": get_active_jobs_count()
        }
    }
```

## Troubleshooting Guide

### Common Issues

#### 1. Low Feature Counts

**Symptoms:**

- Only 1 product feature instead of 350
- Only 1 user feature instead of 381
- Missing feature records

**Causes:**

- Feature computation not processing all data
- Batch size too small
- Watermark issues
- Data quality problems

**Solutions:**

```python
# Check data availability
async def diagnose_low_feature_counts(shop_id: str):
    # Check main table counts
    product_count = await get_product_count(shop_id)
    customer_count = await get_customer_count(shop_id)

    # Check feature table counts
    product_features_count = await get_product_features_count(shop_id)
    user_features_count = await get_user_features_count(shop_id)

    # Check watermarks
    watermarks = await get_watermarks(shop_id)

    return {
        "product_count": product_count,
        "customer_count": customer_count,
        "product_features_count": product_features_count,
        "user_features_count": user_features_count,
        "watermarks": watermarks
    }
```

#### 2. Processing Timeouts

**Symptoms:**

- Processing jobs timing out
- Long-running operations
- Memory issues

**Causes:**

- Large datasets
- Inefficient queries
- Memory leaks
- Resource constraints

**Solutions:**

```python
# Optimize batch processing
async def optimize_processing(shop_id: str):
    # Increase batch sizes for historical processing
    batch_sizes = {
        "products": 10000,
        "customers": 10000,
        "collections": 1000
    }

    # Process in parallel
    await process_parallel(shop_id, batch_sizes)

    # Monitor memory usage
    monitor_memory_usage()
```

#### 3. Database Performance Issues

**Symptoms:**

- Slow queries
- Connection timeouts
- Deadlocks

**Causes:**

- Missing indexes
- Inefficient queries
- Connection pool exhaustion
- Lock contention

**Solutions:**

```python
# Database optimization
async def optimize_database():
    # Add missing indexes
    await add_database_indexes()

    # Optimize queries
    await optimize_queries()

    # Increase connection pool
    await increase_connection_pool()

    # Monitor query performance
    await monitor_query_performance()
```

#### 4. API Rate Limiting

**Symptoms:**

- API rate limit errors
- Slow data collection
- Failed API calls

**Causes:**

- Too many API calls
- Burst requests
- Inefficient API usage

**Solutions:**

```python
# Rate limiting optimization
async def optimize_api_usage():
    # Implement exponential backoff
    await implement_backoff_strategy()

    # Batch API calls
    await batch_api_calls()

    # Use webhooks instead of polling
    await enable_webhooks()

    # Monitor API usage
    await monitor_api_usage()
```

### Debugging Tools

#### Data Quality Checker

```python
async def check_data_quality(shop_id: str) -> Dict[str, Any]:
    return {
        "missing_fields": await check_missing_fields(shop_id),
        "invalid_data": await check_invalid_data(shop_id),
        "duplicate_records": await check_duplicates(shop_id),
        "foreign_key_violations": await check_foreign_keys(shop_id),
        "data_freshness": await check_data_freshness(shop_id)
    }
```

#### Performance Profiler

```python
import cProfile
import pstats

def profile_feature_computation(shop_id: str):
    profiler = cProfile.Profile()
    profiler.enable()

    # Run feature computation
    asyncio.run(compute_features(shop_id))

    profiler.disable()

    # Generate report
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
```

#### Memory Profiler

```python
import tracemalloc

def profile_memory_usage():
    tracemalloc.start()

    # Run feature computation
    asyncio.run(compute_features(shop_id))

    # Get memory usage
    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage: {current / 1024 / 1024:.2f} MB")
    print(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")

    # Get top memory allocations
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    for stat in top_stats[:10]:
        print(stat)
```

## Optimization Strategies

### Performance Optimization

#### Batch Processing Optimization

```python
# Optimize batch sizes based on data volume
def get_optimal_batch_size(data_type: str, total_records: int) -> int:
    if total_records < 1000:
        return total_records
    elif total_records < 10000:
        return 1000
    else:
        return 10000

# Process in optimal batches
async def process_optimally(shop_id: str, data_type: str):
    total_records = await get_record_count(shop_id, data_type)
    batch_size = get_optimal_batch_size(data_type, total_records)

    await process_in_batches(shop_id, data_type, batch_size)
```

#### Parallel Processing Optimization

```python
# Optimize parallel workers based on system resources
def get_optimal_workers() -> int:
    cpu_count = os.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)

    # Use 75% of CPU cores, but limit by memory
    workers = int(cpu_count * 0.75)
    max_workers_by_memory = int(memory_gb / 2)  # 2GB per worker

    return min(workers, max_workers_by_memory)

# Process with optimal parallelism
async def process_parallel_optimally(shop_id: str):
    workers = get_optimal_workers()
    semaphore = asyncio.Semaphore(workers)

    async def process_with_semaphore(task):
        async with semaphore:
            return await task

    tasks = [process_with_semaphore(task) for task in tasks]
    await asyncio.gather(*tasks)
```

#### Database Optimization

```python
# Optimize database queries
async def optimize_database_queries():
    # Add missing indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_product_features_shop_id_product_id ON product_features(shop_id, product_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_features_shop_id_customer_id ON user_features(shop_id, customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_collection_features_shop_id_collection_id ON collection_features(shop_id, collection_id)"
    ]

    for index in indexes:
        await execute_sql(index)

    # Optimize query plans
    await analyze_tables()
```

### Memory Optimization

#### Streaming Processing

```python
# Process data in streams to reduce memory usage
async def process_data_stream(data_source: AsyncIterator, batch_size: int):
    async for batch in data_source:
        yield await process_batch(batch)
        # Explicitly delete batch to free memory
        del batch
        gc.collect()
```

#### Lazy Loading

```python
# Load data lazily to reduce memory usage
class LazyDataLoader:
    def __init__(self, shop_id: str):
        self.shop_id = shop_id
        self._data = None

    async def get_data(self):
        if self._data is None:
            self._data = await load_data(self.shop_id)
        return self._data
```

### Caching Optimization

#### Feature Caching

```python
# Cache computed features to avoid recomputation
from functools import lru_cache

@lru_cache(maxsize=1000)
async def get_cached_features(shop_id: str, entity_id: str, feature_type: str):
    return await compute_features(shop_id, entity_id, feature_type)
```

#### Context Caching

```python
# Cache context data for feature computation
class FeatureContextCache:
    def __init__(self, ttl: int = 3600):
        self.cache = {}
        self.ttl = ttl

    async def get_context(self, shop_id: str) -> Dict:
        if shop_id in self.cache:
            context, timestamp = self.cache[shop_id]
            if time.time() - timestamp < self.ttl:
                return context

        context = await load_context_data(shop_id)
        self.cache[shop_id] = (context, time.time())
        return context
```

## Alerting & Notifications

### Alert Configuration

```python
# Alert thresholds
ALERT_THRESHOLDS = {
    "processing_time_minutes": 30,
    "error_rate_percent": 5,
    "memory_usage_percent": 90,
    "cpu_usage_percent": 95,
    "database_connections_percent": 80
}

# Alert conditions
async def check_alert_conditions():
    metrics = await get_current_metrics()

    alerts = []

    if metrics["processing_time"] > ALERT_THRESHOLDS["processing_time_minutes"]:
        alerts.append("Processing time exceeded threshold")

    if metrics["error_rate"] > ALERT_THRESHOLDS["error_rate_percent"]:
        alerts.append("Error rate exceeded threshold")

    if metrics["memory_usage"] > ALERT_THRESHOLDS["memory_usage_percent"]:
        alerts.append("Memory usage exceeded threshold")

    return alerts
```

### Notification System

```python
# Send notifications for alerts
async def send_notifications(alerts: List[str]):
    for alert in alerts:
        await send_slack_notification(alert)
        await send_email_notification(alert)
        await log_alert(alert)
```

## Monitoring Dashboard

### Real-time Metrics

```python
# Real-time monitoring dashboard
class MonitoringDashboard:
    def __init__(self):
        self.metrics = {}
        self.alerts = []

    async def update_metrics(self):
        self.metrics = {
            "processing_time": await get_processing_time(),
            "success_rate": await get_success_rate(),
            "memory_usage": await get_memory_usage(),
            "active_jobs": await get_active_jobs()
        }

    async def check_alerts(self):
        self.alerts = await check_alert_conditions()

    def get_dashboard_data(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics,
            "alerts": self.alerts,
            "timestamp": datetime.utcnow().isoformat()
        }
```

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
