"""
Base consumer class with enterprise-grade features
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.shared.decorators import async_timing, monitor


class ConsumerStatus(Enum):
    """Consumer status enumeration"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ConsumerMetrics:
    """Consumer performance metrics"""

    messages_processed: int = 0
    messages_failed: int = 0
    processing_time_total: float = 0.0
    processing_time_avg: float = 0.0
    last_message_time: Optional[datetime] = None
    consecutive_failures: int = 0
    circuit_breaker_state: str = "CLOSED"
    uptime_seconds: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)

    def update_processing_time(self, processing_time: float):
        """Update processing time metrics"""
        self.processing_time_total += processing_time
        self.messages_processed += 1
        self.processing_time_avg = self.processing_time_total / self.messages_processed
        self.last_message_time = datetime.utcnow()
        self.consecutive_failures = 0

    def update_failure(self):
        """Update failure metrics"""
        self.messages_failed += 1
        self.consecutive_failures += 1
        self.last_message_time = datetime.utcnow()

    def get_success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.messages_processed + self.messages_failed
        if total == 0:
            return 100.0
        return (self.messages_processed / total) * 100


class CircuitBreaker:
    """Circuit breaker pattern implementation"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    async def acall(self, func: Callable, *args, **kwargs):
        """Execute async function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful execution"""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if self.last_failure_time is None:
            return True

        return (
            datetime.utcnow() - self.last_failure_time
        ).seconds >= self.recovery_timeout

    def reset(self):
        """Manually reset the circuit breaker"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"


class BaseConsumer(ABC):
    """Base consumer class with enterprise-grade features"""

    def __init__(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        batch_size: int = 10,
        poll_timeout: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_failures: int = 5,
        circuit_breaker_timeout: int = 60,
    ):
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.poll_timeout = poll_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_failures,
            recovery_timeout=circuit_breaker_timeout,
        )

        # State management
        self.status = ConsumerStatus.STOPPED
        self._shutdown_event = asyncio.Event()
        self._consumer_task: Optional[asyncio.Task] = None

        # Metrics
        self.metrics = ConsumerMetrics()

        # Logging
        self.logger = get_logger(f"{self.__class__.__name__}")

        # Error handling
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10

        # Health check
        self.last_health_check = datetime.utcnow()
        self.health_check_interval = 30  # seconds

    async def start(self):
        """Start the consumer"""
        if self.status != ConsumerStatus.STOPPED:
            self.logger.warning(
                f"Consumer {self.consumer_name} is already {self.status.value}"
            )
            return

        try:
            self.status = ConsumerStatus.STARTING
            self.logger.info(f"Starting consumer {self.consumer_name}")

            # Initialize Redis connection
            await streams_manager.initialize()

            # Create consumer group
            await self._ensure_consumer_group()

            # Start consumer task
            self._consumer_task = asyncio.create_task(
                self._consume_loop(), name=f"{self.consumer_name}-consumer"
            )

            self.status = ConsumerStatus.RUNNING
            self.logger.info(f"Consumer {self.consumer_name} started successfully")

        except Exception as e:
            self.status = ConsumerStatus.ERROR
            self.logger.error(f"Failed to start consumer {self.consumer_name}: {e}")
            raise

    async def stop(self):
        """Stop the consumer gracefully"""
        if self.status == ConsumerStatus.STOPPED:
            return

        try:
            self.status = ConsumerStatus.STOPPING
            self.logger.info(f"Stopping consumer {self.consumer_name}")

            # Signal shutdown
            self._shutdown_event.set()

            # Wait for consumer task to complete
            if self._consumer_task and not self._consumer_task.done():
                await asyncio.wait_for(self._consumer_task, timeout=30.0)

            self.status = ConsumerStatus.STOPPED
            self.logger.info(f"Consumer {self.consumer_name} stopped successfully")

        except Exception as e:
            self.status = ConsumerStatus.ERROR
            self.logger.error(f"Failed to stop consumer {self.consumer_name}: {e}")
            raise

    async def _consume_loop(self):
        """Main consumption loop"""
        self.logger.info(f"Starting consumption loop for {self.consumer_name}")

        while not self._shutdown_event.is_set():
            try:
                # Health check
                await self._health_check()

                # Consume messages
                messages = await self._consume_messages()

                if messages:
                    await self._process_messages(messages)
                else:
                    # No messages, wait a bit
                    await asyncio.sleep(0.1)

                # Reset consecutive failures on success
                self.consecutive_failures = 0

            except asyncio.CancelledError:
                self.logger.info(f"Consumer {self.consumer_name} cancelled")
                break
            except Exception as e:
                self.consecutive_failures += 1
                self.logger.error(f"Error in consumption loop: {e}")

                # Circuit breaker check
                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.logger.error(
                        f"Too many consecutive failures, stopping consumer"
                    )
                    self.status = ConsumerStatus.ERROR
                    break

                # Wait before retrying
                await asyncio.sleep(self.retry_delay)

        self.logger.info(f"Consumption loop stopped for {self.consumer_name}")

    async def _consume_messages(self) -> List[Dict[str, Any]]:
        """Consume messages from Redis stream"""
        # Check circuit breaker state before consuming
        if self.circuit_breaker.state == "OPEN":
            # Don't consume messages when circuit breaker is open
            # Wait a bit before checking again to avoid tight loops
            self.logger.info(
                f"Circuit breaker is OPEN for {self.consumer_name}, "
                f"waiting {self.circuit_breaker.recovery_timeout} seconds before retry. "
                f"Failure count: {self.circuit_breaker.failure_count}"
            )
            await asyncio.sleep(5)
            return []

        try:
            messages = await streams_manager.consume_events(
                stream_name=self.stream_name,
                consumer_group=self.consumer_group,
                consumer_name=self.consumer_name,
                count=self.batch_size,
                block=self.poll_timeout,
            )
            return messages
        except Exception as e:
            self.logger.error(f"Failed to consume messages: {e}")
            return []

    async def _process_messages(self, messages: List[Dict[str, Any]]):
        """Process a batch of messages"""
        for message in messages:
            try:
                start_time = time.time()

                # Process message with circuit breaker
                await self.circuit_breaker.acall(self._process_single_message, message)

                # Update metrics
                processing_time = time.time() - start_time
                self.metrics.update_processing_time(processing_time)

                # Acknowledge message
                await self._acknowledge_message(message)

            except Exception as e:
                self.logger.error(f"Failed to process message: {e}")
                self.metrics.update_failure()

                # Retry logic
                await self._handle_message_failure(message, e)

    @abstractmethod
    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single message - to be implemented by subclasses"""
        pass

    async def _acknowledge_message(self, message: Dict[str, Any]):
        """Acknowledge message processing"""
        try:
            # Redis streams return message_id as _message_id
            message_id = message.get("_message_id")
            if message_id:
                await streams_manager.acknowledge_event(
                    self.stream_name, self.consumer_group, message_id
                )
        except Exception as e:
            self.logger.error(f"Failed to acknowledge message: {e}")

    async def _handle_message_failure(self, message: Dict[str, Any], error: Exception):
        """Handle message processing failure"""
        # Log failure details
        self.logger.error(
            f"Message processing failed",
            message_id=message.get("_message_id"),
            error=str(error),
            message_data=message,  # Redis streams return data directly
        )

        # Could implement dead letter queue here
        # For now, just log and continue

    async def _ensure_consumer_group(self):
        """Ensure consumer group exists"""
        try:
            # This is handled by the streams_manager.consume_events method
            pass
        except Exception as e:
            self.logger.error(f"Failed to ensure consumer group: {e}")
            raise

    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker and consecutive failures"""
        self.circuit_breaker.reset()
        self.consecutive_failures = 0
        self.logger.info(f"Circuit breaker and consecutive failures reset for {self.consumer_name}")

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "state": self.circuit_breaker.state,
            "failure_count": self.circuit_breaker.failure_count,
            "last_failure_time": (
                self.circuit_breaker.last_failure_time.isoformat()
                if self.circuit_breaker.last_failure_time
                else None
            ),
            "recovery_timeout": self.circuit_breaker.recovery_timeout,
        }

    async def _health_check(self):
        """Perform health check"""
        now = datetime.utcnow()
        if (now - self.last_health_check).seconds >= self.health_check_interval:
            self.last_health_check = now

            # Update uptime
            self.metrics.uptime_seconds = (
                now - self.metrics.start_time
            ).total_seconds()

            # Log health status
            self.logger.info(
                f"Consumer health check",
                status=self.status.value,
                messages_processed=self.metrics.messages_processed,
                messages_failed=self.metrics.messages_failed,
                success_rate=self.metrics.get_success_rate(),
                circuit_breaker_state=self.circuit_breaker.state,
                uptime_seconds=self.metrics.uptime_seconds,
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        return {
            "status": self.status.value,
            "consumer_name": self.consumer_name,
            "stream_name": self.stream_name,
            "consumer_group": self.consumer_group,
            "metrics": {
                "messages_processed": self.metrics.messages_processed,
                "messages_failed": self.metrics.messages_failed,
                "processing_time_avg": self.metrics.processing_time_avg,
                "success_rate": self.metrics.get_success_rate(),
                "consecutive_failures": self.metrics.consecutive_failures,
                "uptime_seconds": self.metrics.uptime_seconds,
            },
            "circuit_breaker": {
                "state": self.circuit_breaker.state,
                "failure_count": self.circuit_breaker.failure_count,
            },
            "last_health_check": self.last_health_check.isoformat(),
        }
