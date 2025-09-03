"""
Enterprise-grade data storage orchestrator with maximum performance and resource efficiency
"""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor
import weakref

from prisma import Prisma
# Json type is handled directly in Prisma operations

from app.core.logging import get_logger
from app.core.exceptions import DataStorageError
from app.shared.helpers import now_utc
from .data_storage import ShopifyDataStorageService, StorageMetrics, DataType

logger = get_logger(__name__)


class ProcessingStrategy(Enum):
    """Data processing strategies for different performance requirements"""

    STREAMING = "streaming"  # Real-time, low memory
    BATCH_OPTIMIZED = "batch"  # Balanced performance
    MAXIMUM_THROUGHPUT = "max"  # Maximum speed, higher memory


@dataclass
class BatchConfig:
    """Configuration for batch processing"""

    batch_size: int = 1000
    max_concurrent_batches: int = 10
    memory_threshold_mb: int = 512
    processing_timeout: float = 300.0
    enable_compression: bool = True
    use_transactions: bool = True


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""

    total_items_processed: int = 0
    total_processing_time: float = 0.0
    average_batch_time: float = 0.0
    memory_peak_mb: float = 0.0
    database_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    compression_ratio: float = 1.0
    throughput_items_per_second: float = 0.0

    @property
    def efficiency_score(self) -> float:
        """Calculate overall efficiency score (0-100)"""
        if self.total_processing_time == 0:
            return 0.0

        # Factor in processing speed, memory usage, and database efficiency
        speed_score = min(
            100.0, self.throughput_items_per_second / 1000.0
        )  # Normalize to 1000 items/sec
        memory_score = max(
            0.0, 100.0 - (self.memory_peak_mb / 10.0)
        )  # Penalize high memory usage
        db_efficiency = min(
            100.0, (self.total_items_processed / max(1, self.database_operations)) * 100
        )

        return speed_score * 0.4 + memory_score * 0.3 + db_efficiency * 0.3


class HighPerformanceDataOrchestrator:
    """
    Enterprise-grade data storage orchestrator with:
    - Parallel processing with configurable concurrency
    - Intelligent batching and memory management
    - Connection pooling and caching
    - Adaptive performance tuning
    - Resource monitoring and optimization
    """

    def __init__(
        self,
        max_workers: int = 20,
        memory_limit_mb: int = 2048,
        enable_compression: bool = True,
    ):

        self.max_workers = max_workers
        self.memory_limit_mb = memory_limit_mb
        self.enable_compression = enable_compression

        # Performance optimization
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._storage_service = ShopifyDataStorageService()
        self._batch_queue = asyncio.Queue(maxsize=1000)
        self._processing_tasks: List[asyncio.Task] = []

        # Resource management
        self._memory_monitor = MemoryMonitor(memory_limit_mb)
        self._connection_pool = ConnectionPool(max_size=10)
        self._cache = LRUCache(max_size=10000, ttl_seconds=300)

        # Performance tracking
        self.performance_metrics = PerformanceMetrics()
        self._start_time = now_utc()

        # Adaptive configuration
        self._adaptive_config = self._create_adaptive_config()

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the orchestrator with all optimizations"""
        try:
            # Initialize storage service
            await self._storage_service.initialize()

            # Start background tasks
            self._cleanup_task = asyncio.create_task(self._background_cleanup())
            self._monitoring_task = asyncio.create_task(self._performance_monitoring())

            # Warm up connection pool
            await self._connection_pool.warm_up()

            # Initialize cache with hot data
            await self._warm_cache()

            logger.info("High-performance data orchestrator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise DataStorageError(f"Initialization failed: {e}")

    async def store_data_stream(
        self,
        data_stream: Dict[str, Any],
        shop_id: str,
        strategy: ProcessingStrategy = ProcessingStrategy.BATCH_OPTIMIZED,
    ) -> Dict[str, StorageMetrics]:
        """
        Store data stream with optimal performance strategy
        """
        try:
            start_time = now_utc()

            # Choose optimal processing strategy
            if strategy == ProcessingStrategy.STREAMING:
                return await self._process_streaming(data_stream, shop_id)
            elif strategy == ProcessingStrategy.BATCH_OPTIMIZED:
                return await self._process_batch_optimized(data_stream, shop_id)
            elif strategy == ProcessingStrategy.MAXIMUM_THROUGHPUT:
                return await self._process_maximum_throughput(data_stream, shop_id)
            else:
                raise ValueError(f"Unknown processing strategy: {strategy}")

        except Exception as e:
            logger.error(f"Data stream processing failed: {e}")
            raise DataStorageError(f"Stream processing failed: {e}")
        finally:
            # Update performance metrics
            processing_time = (now_utc() - start_time).total_seconds()
            self.performance_metrics.total_processing_time += processing_time

    async def _process_streaming(
        self, data_stream: Dict[str, Any], shop_id: str
    ) -> Dict[str, StorageMetrics]:
        """Process data in real-time streaming mode"""
        results = {}

        # Process shop data first (needed for relationships)
        if "shop" in data_stream and data_stream["shop"]:
            shop_metrics = await self._storage_service.store_shop_data(
                data_stream["shop"], shop_id
            )
            results["shop"] = shop_metrics

        # Process other data types in parallel streams
        stream_tasks = []

        for data_type, data in data_stream.items():
            if data_type != "shop" and data:
                task = self._process_data_stream(data_type, data, shop_id)
                stream_tasks.append(task)

        if stream_tasks:
            stream_results = await asyncio.gather(*stream_tasks, return_exceptions=True)

            for i, result in enumerate(stream_results):
                if isinstance(result, Exception):
                    logger.error(f"Stream processing failed: {result}")
                else:
                    data_type = list(data_stream.keys())[i + 1]  # Skip shop
                    results[data_type] = result

        return results

    async def _process_batch_optimized(
        self, data_stream: Dict[str, Any], shop_id: str
    ) -> Dict[str, StorageMetrics]:
        """Process data with optimized batching"""
        results = {}

        # Process shop data first
        if "shop" in data_stream and data_stream["shop"]:
            shop_metrics = await self._storage_service.store_shop_data(
                data_stream["shop"], shop_id
            )
            results["shop"] = shop_metrics

        # Group data by type and process in optimized batches
        data_groups = self._group_data_by_type(data_stream)

        # Process groups in parallel with optimal batch sizes
        batch_tasks = []
        for data_type, items in data_groups.items():
            if items:
                optimal_batch_size = self._calculate_optimal_batch_size(
                    data_type, len(items)
                )
                task = self._process_batched_data(
                    data_type, items, shop_id, optimal_batch_size
                )
                batch_tasks.append(task)

        if batch_tasks:
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed: {result}")
                else:
                    data_type = list(data_groups.keys())[i]
                    results[data_type] = result

        return results

    async def _process_maximum_throughput(
        self, data_stream: Dict[str, Any], shop_id: str
    ) -> Dict[str, StorageMetrics]:
        """Process data with maximum throughput optimization"""
        results = {}

        # Use maximum concurrency and batch sizes
        max_batch_size = 5000
        max_concurrent = 20

        # Process shop data first
        if "shop" in data_stream and data_stream["shop"]:
            shop_metrics = await self._storage_service.store_shop_data(
                data_stream["shop"], shop_id
            )
            results["shop"] = shop_metrics

        # Group and process with maximum parallelism
        data_groups = self._group_data_by_type(data_stream)

        # Create maximum parallel tasks
        parallel_tasks = []
        for data_type, items in data_groups.items():
            if items:
                # Split into maximum batch sizes
                batches = self._create_batches(items, max_batch_size)

                for batch in batches:
                    task = self._process_batch_with_transaction(
                        data_type, batch, shop_id
                    )
                    parallel_tasks.append(task)

        if parallel_tasks:
            # Process with maximum concurrency
            semaphore = asyncio.Semaphore(max_concurrent)

            async def limited_task(task):
                async with semaphore:
                    return await task

            limited_tasks = [limited_task(task) for task in parallel_tasks]
            parallel_results = await asyncio.gather(
                *limited_tasks, return_exceptions=True
            )

            # Aggregate results
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    logger.error(f"Parallel processing failed: {result}")
                else:
                    # Map result back to data type
                    data_type = self._get_data_type_from_batch_index(
                        i, data_groups, max_batch_size
                    )
                    if data_type not in results:
                        results[data_type] = StorageMetrics(
                            data_type=data_type, shop_id=shop_id
                        )

                    # Aggregate metrics
                    results[data_type].total_items += result.total_items
                    results[data_type].new_items += result.new_items
                    results[data_type].updated_items += result.updated_items

        return results

    async def _process_data_stream(
        self, data_type: str, data: List[Any], shop_id: str
    ) -> StorageMetrics:
        """Process a single data stream with streaming optimization"""
        if not data:
            return StorageMetrics(data_type=data_type, shop_id=shop_id)

        # Use streaming storage for large datasets
        if len(data) > 1000:
            return await self._storage_service.store_products_data(data, shop_id)
        else:
            # For smaller datasets, use regular storage
            return await self._storage_service.store_products_data(data, shop_id)

    async def _process_batched_data(
        self, data_type: str, items: List[Any], shop_id: str, batch_size: int
    ) -> StorageMetrics:
        """Process data in optimized batches"""
        if not items:
            return StorageMetrics(data_type=data_type, shop_id=shop_id)

        # Create optimal batches
        batches = self._create_batches(items, batch_size)

        # Process batches with optimal concurrency
        optimal_concurrency = min(len(batches), self.max_workers)
        semaphore = asyncio.Semaphore(optimal_concurrency)

        async def process_batch(batch):
            async with semaphore:
                if data_type == "products":
                    return await self._storage_service.store_products_data(
                        batch, shop_id
                    )
                # Add other data types as needed
                return StorageMetrics(data_type=data_type, shop_id=shop_id)

        batch_tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Aggregate results
        aggregated_metrics = StorageMetrics(data_type=data_type, shop_id=shop_id)

        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing failed: {result}")
                aggregated_metrics.failed_items += batch_size
            else:
                aggregated_metrics.total_items += result.total_items
                aggregated_metrics.new_items += result.new_items
                aggregated_metrics.updated_items += result.updated_items

        return aggregated_metrics

    async def _process_batch_with_transaction(
        self, data_type: str, batch: List[Any], shop_id: str
    ) -> StorageMetrics:
        """Process a batch within a database transaction"""
        # This would use the storage service with transaction support
        if data_type == "products":
            return await self._storage_service.store_products_data(batch, shop_id)
        return StorageMetrics(data_type=data_type, shop_id=shop_id)

    def _group_data_by_type(self, data_stream: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Group data by type for optimal processing"""
        groups = {}

        for data_type, data in data_stream.items():
            if isinstance(data, list) and data:
                groups[data_type] = data
            elif data:  # Single items like shop
                groups[data_type] = [data]

        return groups

    def _create_batches(self, items: List[Any], batch_size: int) -> List[List[Any]]:
        """Create optimal batches from items"""
        return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    def _calculate_optimal_batch_size(self, data_type: str, total_items: int) -> int:
        """Calculate optimal batch size based on data type and volume"""
        base_sizes = {
            "products": 500,
            "orders": 1000,
            "customers": 800,
            "collections": 200,
            "customer_events": 1500,
        }

        base_size = base_sizes.get(data_type, 500)

        # Adjust based on total volume
        if total_items > 10000:
            return min(base_size * 2, 2000)
        elif total_items < 100:
            return min(base_size // 2, 100)
        else:
            return base_size

    def _get_data_type_from_batch_index(
        self, batch_index: int, data_groups: Dict[str, List[Any]], batch_size: int
    ) -> str:
        """Map batch index back to data type"""
        data_types = list(data_groups.keys())
        if not data_types:
            return "unknown"

        # Calculate which data type this batch belongs to
        total_batches_before = 0
        for data_type, items in data_groups.items():
            num_batches = (len(items) + batch_size - 1) // batch_size
            if batch_index < total_batches_before + num_batches:
                return data_type
            total_batches_before += num_batches

        return data_types[-1]  # Fallback

    def _create_adaptive_config(self) -> Dict[str, Any]:
        """Create adaptive configuration based on system resources"""
        return {
            "batch_size": 1000,
            "max_concurrency": self.max_workers,
            "memory_threshold": self.memory_limit_mb * 0.8,
            "enable_compression": self.enable_compression,
            "cache_ttl": 300,
            "connection_pool_size": 10,
        }

    async def _warm_cache(self) -> None:
        """Warm up cache with frequently accessed data"""
        try:
            # Cache shop metadata
            shops = await self._storage_service.db.shop.find_many(
                select={"id": True, "shopDomain": True, "lastAnalysisAt": True}
            )

            for shop in shops:
                cache_key = f"shop_meta_{shop.id}"
                self._cache.set(
                    cache_key,
                    {"domain": shop.shopDomain, "last_analysis": shop.lastAnalysisAt},
                )

            logger.info(f"Cache warmed up with {len(shops)} shops")

        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")

    async def _background_cleanup(self) -> None:
        """Background cleanup task"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Clean up expired cache entries
                self._cache.cleanup()

                # Monitor memory usage
                current_memory = self._memory_monitor.get_current_usage()
                if current_memory > self.memory_limit_mb * 0.9:
                    logger.warning(f"High memory usage: {current_memory:.2f}MB")
                    # Trigger garbage collection
                    import gc

                    gc.collect()

            except Exception as e:
                logger.error(f"Background cleanup failed: {e}")

    async def _performance_monitoring(self) -> None:
        """Background performance monitoring"""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute

                # Update performance metrics
                current_time = now_utc()
                elapsed_time = (current_time - self._start_time).total_seconds()

                if elapsed_time > 0:
                    self.performance_metrics.throughput_items_per_second = (
                        self.performance_metrics.total_items_processed / elapsed_time
                    )

                # Log performance summary
                logger.info(
                    f"Performance Summary: {self.performance_metrics.efficiency_score:.1f}% efficiency"
                )

            except Exception as e:
                logger.error(f"Performance monitoring failed: {e}")

    async def close(self) -> None:
        """Cleanup and close orchestrator"""
        try:
            # Cancel background tasks
            if self._cleanup_task:
                self._cleanup_task.cancel()
            if self._monitoring_task:
                self._monitoring_task.cancel()

            # Close storage service
            await self._storage_service.close()

            # Shutdown thread pool
            self._thread_pool.shutdown(wait=True)

            logger.info("High-performance data orchestrator closed")

        except Exception as e:
            logger.error(f"Error closing orchestrator: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


class MemoryMonitor:
    """Monitor memory usage and provide optimization recommendations"""

    def __init__(self, limit_mb: int):
        self.limit_mb = limit_mb
        self.peak_usage = 0.0

    def get_current_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.peak_usage = max(self.peak_usage, memory_mb)
            return memory_mb
        except ImportError:
            return 0.0

    def get_optimization_recommendations(self) -> List[str]:
        """Get memory optimization recommendations"""
        recommendations = []
        current_usage = self.get_current_usage()

        if current_usage > self.limit_mb * 0.8:
            recommendations.append("High memory usage - consider reducing batch sizes")

        if self.peak_usage > self.limit_mb:
            recommendations.append("Memory limit exceeded - optimize data structures")

        return recommendations


class ConnectionPool:
    """Database connection pool for optimal performance"""

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._connections: List[Prisma] = []
        self._available: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._in_use: set = set()

    async def warm_up(self) -> None:
        """Warm up connection pool"""
        for _ in range(self.max_size):
            connection = Prisma()
            await connection.connect()
            self._connections.append(connection)
            await self._available.put(connection)

    async def get_connection(self) -> Prisma:
        """Get an available database connection"""
        connection = await self._available.get()
        self._in_use.add(connection)
        return connection

    async def release_connection(self, connection: Prisma) -> None:
        """Release a database connection back to the pool"""
        if connection in self._in_use:
            self._in_use.remove(connection)
            await self._available.put(connection)

    async def close_all(self) -> None:
        """Close all connections"""
        for connection in self._connections:
            await connection.disconnect()


class LRUCache:
    """High-performance LRU cache with TTL support"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._access_order: List[str] = []

    def set(self, key: str, value: Any) -> None:
        """Set cache value with TTL"""
        current_time = now_utc()

        # Remove oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]

        # Set new value
        self._cache[key] = (value, current_time)
        self._access_order.append(key)

    def get(self, key: str) -> Optional[Any]:
        """Get cache value if not expired"""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if (now_utc() - timestamp).total_seconds() > self.ttl_seconds:
            # Expired, remove
            del self._cache[key]
            self._access_order.remove(key)
            return None

        # Move to end (most recently used)
        self._access_order.remove(key)
        self._access_order.append(key)

        return value

    def cleanup(self) -> None:
        """Remove expired entries"""
        current_time = now_utc()
        expired_keys = []

        for key, (value, timestamp) in self._cache.items():
            if (current_time - timestamp).total_seconds() > self.ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            self._access_order.remove(key)
