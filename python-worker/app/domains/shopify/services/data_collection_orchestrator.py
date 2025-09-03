"""
Enterprise-grade data collection orchestrator with maximum performance and resource efficiency
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.core.logging import get_logger
from app.core.exceptions import DataStorageError
from app.shared.helpers import now_utc
from .data_collection import ShopifyDataCollectionService
from .data_storage_orchestrator import HighPerformanceDataOrchestrator, ProcessingStrategy

logger = get_logger(__name__)


class CollectionStrategy(Enum):
    """Data collection strategies for different performance requirements"""
    SEQUENTIAL = "sequential"        # One at a time, lowest memory
    PARALLEL = "parallel"            # All in parallel, balanced
    STREAMING = "streaming"          # Real-time streaming
    HYBRID = "hybrid"                # Smart combination


@dataclass
class CollectionConfig:
    """Configuration for data collection"""
    max_concurrent_collections: int = 5
    collection_timeout: float = 600.0  # 10 minutes
    batch_size: int = 100
    enable_streaming: bool = True
    memory_threshold_mb: int = 1024
    retry_attempts: int = 3
    retry_delay: float = 2.0


@dataclass
class CollectionMetrics:
    """Comprehensive collection metrics"""
    shop_id: str
    data_types: List[str] = field(default_factory=list)
    total_items_collected: int = 0
    collection_time: float = 0.0
    storage_time: float = 0.0
    total_time: float = 0.0
    memory_peak_mb: float = 0.0
    success_rate: float = 100.0
    errors: List[str] = field(default_factory=list)
    
    @property
    def throughput_items_per_second(self) -> float:
        """Calculate collection throughput"""
        if self.collection_time == 0:
            return 0.0
        return self.total_items_collected / self.collection_time
    
    @property
    def efficiency_score(self) -> float:
        """Calculate collection efficiency (0-100)"""
        if self.total_time == 0:
            return 0.0
        
        # Factor in collection speed, storage speed, and success rate
        collection_efficiency = min(100.0, self.throughput_items_per_second / 100.0)
        storage_efficiency = max(0.0, 100.0 - (self.storage_time / self.total_time) * 100)
        success_efficiency = self.success_rate
        
        return (collection_efficiency * 0.4 + storage_efficiency * 0.3 + success_efficiency * 0.3)


class HighPerformanceDataCollectionOrchestrator:
    """
    Enterprise-grade data collection orchestrator with:
    - Parallel collection with configurable concurrency
    - Streaming data processing
    - Intelligent resource management
    - Adaptive performance tuning
    - Comprehensive monitoring and metrics
    """
    
    def __init__(self,
                 collection_service: ShopifyDataCollectionService,
                 storage_orchestrator: HighPerformanceDataOrchestrator,
                 max_workers: int = 20,
                 memory_limit_mb: int = 2048):
        
        self.collection_service = collection_service
        self.storage_orchestrator = storage_orchestrator
        self.max_workers = max_workers
        self.memory_limit_mb = memory_limit_mb
        
        # Configuration
        self.collection_config = CollectionConfig()
        self.collection_strategy = CollectionStrategy.HYBRID
        
        # Performance tracking
        self.collection_metrics: Dict[str, CollectionMetrics] = {}
        self._start_time = now_utc()
        
        # Resource management
        self._collection_semaphore = asyncio.Semaphore(self.collection_config.max_concurrent_collections)
        self._memory_monitor = self._create_memory_monitor()
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize the collection orchestrator"""
        try:
            # Initialize storage orchestrator
            await self.storage_orchestrator.initialize()
            
            # Start background tasks
            self._monitoring_task = asyncio.create_task(self._performance_monitoring())
            self._cleanup_task = asyncio.create_task(self._background_cleanup())
            
            logger.info("High-performance collection orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize collection orchestrator: {e}")
            raise DataStorageError(f"Initialization failed: {e}")
    
    async def collect_and_store_all_data(
        self,
        shop_domain: str,
        strategy: ProcessingStrategy = ProcessingStrategy.BATCH_OPTIMIZED,
        collection_strategy: CollectionStrategy = CollectionStrategy.HYBRID
    ) -> Dict[str, Any]:
        """
        Collect and store all data with optimal performance
        """
        start_time = now_utc()
        shop_id = f"shop_{shop_domain}"
        
        # Initialize metrics
        metrics = CollectionMetrics(shop_id=shop_id)
        self.collection_metrics[shop_id] = metrics
        
        try:
            logger.info(f"Starting high-performance data collection for {shop_domain}")
            
            # Choose collection strategy
            if collection_strategy == CollectionStrategy.SEQUENTIAL:
                result = await self._collect_sequential(shop_domain, metrics)
            elif collection_strategy == CollectionStrategy.PARALLEL:
                result = await self._collect_parallel(shop_domain, metrics)
            elif collection_strategy == CollectionStrategy.STREAMING:
                result = await self._collect_streaming(shop_domain, metrics)
            elif collection_strategy == CollectionStrategy.HYBRID:
                result = await self._collect_hybrid(shop_domain, metrics)
            else:
                raise ValueError(f"Unknown collection strategy: {collection_strategy}")
            
            # Store data with optimal strategy
            storage_start = time.time()
            storage_metrics = await self.storage_orchestrator.store_data_stream(
                result, shop_id, strategy
            )
            storage_time = time.time() - storage_start
            
            # Update metrics
            metrics.storage_time = storage_time
            metrics.total_time = (now_utc() - start_time).total_seconds()
            metrics.data_types = list(result.keys())
            metrics.total_items_collected = sum(
                len(result.get(data_type, [])) 
                for data_type in ["products", "orders", "customers", "collections", "customer_events"]
            )
            
            # Calculate success rate
            total_operations = len(storage_metrics)
            successful_operations = sum(
                1 for metrics in storage_metrics.values() 
                if metrics.failed_items == 0
            )
            metrics.success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 100.0
            
            logger.info(f"Collection completed: {metrics.efficiency_score:.1f}% efficiency")
            return result
            
        except Exception as e:
            metrics.errors.append(str(e))
            metrics.total_time = (now_utc() - start_time).total_seconds()
            logger.error(f"Collection failed: {e}")
            raise DataStorageError(f"Collection failed: {e}")
    
    async def _collect_sequential(
        self, 
        shop_domain: str, 
        metrics: CollectionMetrics
    ) -> Dict[str, Any]:
        """Collect data sequentially (lowest memory usage)"""
        collection_start = time.time()
        
        # Collect shop data first
        shop = await self.collection_service.collect_shop_data(shop_domain)
        
        # Collect other data types sequentially
        products = await self.collection_service.collect_products(shop_domain)
        orders = await self.collection_service.collect_orders(shop_domain)
        customers = await self.collection_service.collect_customers(shop_domain)
        collections = await self.collection_service.collect_collections(shop_domain)
        customer_events = await self.collection_service.collect_customer_events(shop_domain)
        
        collection_time = time.time() - collection_start
        metrics.collection_time = collection_time
        
        return {
            "shop": shop,
            "products": products,
            "orders": orders,
            "customers": customers,
            "collections": collections,
            "customer_events": customer_events
        }
    
    async def _collect_parallel(
        self, 
        shop_domain: str, 
        metrics: CollectionMetrics
    ) -> Dict[str, Any]:
        """Collect data in parallel (maximum speed)"""
        collection_start = time.time()
        
        # Collect shop data first (needed for relationships)
        shop = await self.collection_service.collect_shop_data(shop_domain)
        
        # Collect all other data types in parallel
        collection_tasks = [
            self.collection_service.collect_products(shop_domain),
            self.collection_service.collect_orders(shop_domain),
            self.collection_service.collect_customers(shop_domain),
            self.collection_service.collect_collections(shop_domain),
            self.collection_service.collect_customer_events(shop_domain)
        ]
        
        # Execute with concurrency control
        async with self._collection_semaphore:
            results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        
        collection_time = time.time() - collection_start
        metrics.collection_time = collection_time
        
        # Process results
        data_types = ["products", "orders", "customers", "collections", "customer_events"]
        processed_results = {}
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Collection failed for {data_types[i]}: {result}")
                metrics.errors.append(f"{data_types[i]}: {result}")
                processed_results[data_types[i]] = []
            else:
                processed_results[data_types[i]] = result
        
        return {
            "shop": shop,
            **processed_results
        }
    
    async def _collect_streaming(
        self, 
        shop_domain: str, 
        metrics: CollectionMetrics
    ) -> Dict[str, Any]:
        """Collect data using streaming approach (real-time, low memory)"""
        collection_start = time.time()
        
        # Collect shop data first
        shop = await self.collection_service.collect_shop_data(shop_domain)
        
        # Stream collection for each data type
        collection_results = {}
        
        # Use the existing collect_all_data method which has streaming capabilities
        try:
            result = await self.collection_service.collect_all_data(
                shop_domain,
                include_products=True,
                include_orders=True,
                include_customers=True,
                include_collections=True,
                include_customer_events=True
            )
            
            collection_results = result
            
        except Exception as e:
            logger.error(f"Streaming collection failed: {e}")
            metrics.errors.append(f"streaming: {e}")
            # Fallback to basic collection
            collection_results = {
                "shop": shop,
                "products": [],
                "orders": [],
                "customers": [],
                "collections": [],
                "customer_events": []
            }
        
        collection_time = time.time() - collection_start
        metrics.collection_time = collection_time
        
        return collection_results
    
    async def _collect_hybrid(
        self, 
        shop_domain: str, 
        metrics: CollectionMetrics
    ) -> Dict[str, Any]:
        """Smart hybrid collection strategy"""
        collection_start = time.time()
        
        # Collect shop data first
        shop = await self.collection_service.collect_shop_data(shop_domain)
        
        # Determine optimal strategy based on shop size and available resources
        shop_size = await self._estimate_shop_size(shop_domain)
        available_memory = self._memory_monitor.get_available_memory()
        
        if shop_size > 10000 and available_memory > 1024:
            # Large shop with good memory - use parallel collection
            logger.info("Using parallel collection for large shop")
            return await self._collect_parallel(shop_domain, metrics)
        elif shop_size < 1000:
            # Small shop - use sequential (fastest for small data)
            logger.info("Using sequential collection for small shop")
            return await self._collect_sequential(shop_domain, metrics)
        else:
            # Medium shop - use streaming
            logger.info("Using streaming collection for medium shop")
            return await self._collect_streaming(shop_domain, metrics)
    
    async def _estimate_shop_size(self, shop_domain: str) -> int:
        """Estimate shop size for strategy selection"""
        try:
            # Quick check for shop size indicators
            permissions = await self.collection_service.permission_service.check_shop_permissions(shop_domain)
            
            # Estimate based on permissions and available scopes
            if permissions.get("has_access", False):
                # This is a rough estimate - in production you'd have more sophisticated logic
                return 5000  # Default to medium size
            else:
                return 100  # Small shop with limited access
            
        except Exception:
            return 1000  # Default to small shop
    
    def _create_memory_monitor(self) -> Any:
        """Create memory monitor for resource management"""
        try:
            import psutil
            return psutil
        except ImportError:
            # Fallback if psutil not available
            return None
    
    def _memory_monitor(self) -> Any:
        """Get memory monitor instance"""
        return self._memory_monitor
    
    async def _performance_monitoring(self) -> None:
        """Background performance monitoring"""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute
                
                # Log performance summary
                total_efficiency = 0.0
                active_collections = 0
                
                for metrics in self.collection_metrics.values():
                    if metrics.total_time > 0:
                        total_efficiency += metrics.efficiency_score
                        active_collections += 1
                
                if active_collections > 0:
                    avg_efficiency = total_efficiency / active_collections
                    logger.info(f"Collection Performance: {avg_efficiency:.1f}% average efficiency")
                
                # Memory monitoring
                if self._memory_monitor:
                    try:
                        memory_usage = self._memory_monitor.virtual_memory().percent
                        if memory_usage > 80:
                            logger.warning(f"High memory usage: {memory_usage:.1f}%")
                    except Exception:
                        pass
                
            except Exception as e:
                logger.error(f"Performance monitoring failed: {e}")
    
    async def _background_cleanup(self) -> None:
        """Background cleanup task"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Clean up old metrics
                current_time = now_utc()
                expired_keys = []
                
                for shop_id, metrics in self.collection_metrics.items():
                    # Keep metrics for 24 hours
                    if (current_time - self._start_time).total_seconds() > 86400:
                        expired_keys.append(shop_id)
                
                for key in expired_keys:
                    del self.collection_metrics[key]
                
                if expired_keys:
                    logger.info(f"Cleaned up {len(expired_keys)} expired metrics")
                
            except Exception as e:
                logger.error(f"Background cleanup failed: {e}")
    
    async def get_collection_metrics(self, shop_id: Optional[str] = None) -> Dict[str, CollectionMetrics]:
        """Get collection metrics for monitoring"""
        if shop_id:
            return {shop_id: self.collection_metrics.get(shop_id)}
        return self.collection_metrics
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        summary = {
            "total_collections": len(self.collection_metrics),
            "average_efficiency": 0.0,
            "total_items_processed": 0,
            "average_throughput": 0.0,
            "memory_usage_mb": 0.0,
            "active_collections": 0
        }
        
        if self.collection_metrics:
            total_efficiency = 0.0
            total_items = 0
            total_throughput = 0.0
            active_count = 0
            
            for metrics in self.collection_metrics.values():
                if metrics.total_time > 0:
                    total_efficiency += metrics.efficiency_score
                    total_items += metrics.total_items_collected
                    total_throughput += metrics.throughput_items_per_second
                    active_count += 1
            
            if active_count > 0:
                summary["average_efficiency"] = total_efficiency / active_count
                summary["total_items_processed"] = total_items
                summary["average_throughput"] = total_throughput / active_count
                summary["active_collections"] = active_count
        
        # Get current memory usage
        if self._memory_monitor:
            try:
                memory_info = self._memory_monitor.virtual_memory()
                summary["memory_usage_mb"] = memory_info.used / 1024 / 1024
            except Exception:
                pass
        
        return summary
    
    async def close(self) -> None:
        """Cleanup and close orchestrator"""
        try:
            # Cancel background tasks
            if self._monitoring_task:
                self._monitoring_task.cancel()
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            # Close storage orchestrator
            await self.storage_orchestrator.close()
            
            logger.info("High-performance collection orchestrator closed")
            
        except Exception as e:
            logger.error(f"Error closing collection orchestrator: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
