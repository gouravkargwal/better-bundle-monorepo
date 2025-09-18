"""
Enterprise-level scheduler service for managing analysis scheduling via GitHub cron
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import yaml
import croniter

from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.shared.decorators import async_timing, monitor, retry
from app.shared.helpers import now_utc
from app.shared.constants.redis import (
    NEXT_ANALYSIS_SCHEDULED_STREAM,
    HEURISTIC_DECISION_MADE_STREAM,
    ML_TRAINING_STREAM,
)
from app.domains.analytics.services import HeuristicService


class ScheduleStatus(Enum):
    """Schedule status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class SchedulePriority(Enum):
    """Schedule priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ScheduledAnalysis:
    """Scheduled analysis job"""

    id: str
    shop_id: str
    analysis_types: List[str]
    scheduled_time: datetime
    priority: SchedulePriority
    trigger_type: str
    status: ScheduleStatus
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=now_utc)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_overdue(self) -> bool:
        """Check if the scheduled analysis is overdue"""
        return self.status == ScheduleStatus.PENDING and now_utc() > self.scheduled_time

    def can_retry(self) -> bool:
        """Check if the analysis can be retried"""
        return self.retry_count < self.max_retries and self.status in [
            ScheduleStatus.FAILED,
            ScheduleStatus.OVERDUE,
        ]

    def mark_started(self):
        """Mark the analysis as started"""
        self.status = ScheduleStatus.RUNNING
        self.started_at = now_utc()

    def mark_completed(self):
        """Mark the analysis as completed"""
        self.status = ScheduleStatus.COMPLETED
        self.completed_at = now_utc()

    def mark_failed(self, error_message: str):
        """Mark the analysis as failed"""
        self.status = ScheduleStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1


@dataclass
class CronSchedule:
    """Cron schedule configuration"""

    name: str
    cron_expression: str
    analysis_types: List[str]
    priority: SchedulePriority
    enabled: bool = True
    timezone: str = "UTC"
    metadata: Dict[str, Any] = field(default_factory=dict)


class SchedulerService:
    """Enterprise-level scheduler service for analysis management"""

    def __init__(self, heuristic_service: HeuristicService):
        self.logger = get_logger(__name__)
        self.heuristic_service = heuristic_service

        # Configuration
        self.config_file = Path("config/scheduler.yml")
        self.default_timezone = "UTC"
        self.max_concurrent_jobs = 10
        self.job_timeout = 3600  # 1 hour
        self.overdue_threshold = 300  # 5 minutes

        # State management
        self.scheduled_analyses: Dict[str, ScheduledAnalysis] = {}
        self.cron_schedules: Dict[str, CronSchedule] = {}
        self.running_jobs: Set[str] = set()
        self._shutdown_event = asyncio.Event()
        self._scheduler_task: Optional[asyncio.Task] = None

        # Performance metrics
        self.jobs_scheduled = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.jobs_overdue = 0

        # Health monitoring
        self.last_health_check = now_utc()
        self.health_check_interval = 60  # 1 minute

        # Initialize the service
        self._initialize_service()

    def _initialize_service(self):
        """Initialize the scheduler service"""
        try:
            # Load configuration
            self._load_configuration()

            # Initialize Redis connection
            self._ensure_redis_connection()

            # Setup signal handlers
            self._setup_signal_handlers()

            self.logger.info("Scheduler service initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize scheduler service: {e}")
            raise

    def _load_configuration(self):
        """Load scheduler configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    config = yaml.safe_load(f)

                # Load cron schedules
                cron_configs = config.get("cron_schedules", [])
                for cron_config in cron_configs:
                    cron_schedule = CronSchedule(
                        name=cron_config["name"],
                        cron_expression=cron_config["cron_expression"],
                        analysis_types=cron_config["analysis_types"],
                        priority=SchedulePriority(cron_config["priority"]),
                        enabled=cron_config.get("enabled", True),
                        timezone=cron_config.get("timezone", self.default_timezone),
                        metadata=cron_config.get("metadata", {}),
                    )
                    self.cron_schedules[cron_schedule.name] = cron_schedule

                self.logger.info(f"Loaded {len(self.cron_schedules)} cron schedules")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_file}")
                self._create_default_configuration()

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self._create_default_configuration()

    def _create_default_configuration(self):
        """Create default configuration if none exists"""
        try:
            default_config = {
                "cron_schedules": [
                    {
                        "name": "hourly_business_metrics",
                        "cron_expression": "0 * * * *",
                        "analysis_types": ["business_metrics"],
                        "priority": "medium",
                        "enabled": True,
                        "timezone": "UTC",
                    },
                    {
                        "name": "daily_performance_analytics",
                        "cron_expression": "0 2 * * *",
                        "analysis_types": [
                            "performance_analytics",
                            "customer_analytics",
                        ],
                        "priority": "medium",
                        "enabled": True,
                        "timezone": "UTC",
                    },
                    {
                        "name": "weekly_ml_retraining",
                        "cron_expression": "0 3 * * 0",
                        "analysis_types": ["ml_model_retraining"],
                        "priority": "high",
                        "enabled": True,
                        "timezone": "UTC",
                    },
                ]
            }

            # Ensure config directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, "w") as f:
                yaml.dump(default_config, f, default_flow_style=False)

            self.logger.info("Created default configuration file")

            # Load the default configuration
            self._load_configuration()

        except Exception as e:
            self.logger.error(f"Failed to create default configuration: {e}")

    def _ensure_redis_connection(self):
        """Ensure Redis connection is available"""
        try:
            # This would initialize Redis connection in a real implementation
            pass
        except Exception as e:
            self.logger.error(f"Failed to ensure Redis connection: {e}")
            raise

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        import signal

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self):
        """Start the scheduler service"""
        if self._scheduler_task and not self._scheduler_task.done():
            self.logger.warning("Scheduler service is already running")
            return

        try:
            self.logger.info("Starting scheduler service...")

            # Start the main scheduler loop
            self._scheduler_task = asyncio.create_task(
                self._scheduler_loop(), name="scheduler-main-loop"
            )

            self.logger.info("Scheduler service started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start scheduler service: {e}")
            raise

    async def stop(self):
        """Stop the scheduler service"""
        try:
            self.logger.info("Stopping scheduler service...")

            # Signal shutdown
            self._shutdown_event.set()

            # Wait for scheduler task to complete
            if self._scheduler_task and not self._scheduler_task.done():
                await asyncio.wait_for(self._scheduler_task, timeout=30.0)

            self.logger.info("Scheduler service stopped successfully")

        except Exception as e:
            self.logger.error(f"Failed to stop scheduler service: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        await self.stop()

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        self.logger.info("Starting scheduler main loop")

        while not self._shutdown_event.is_set():
            try:
                # Process cron schedules
                await self._process_cron_schedules()

                # Process scheduled analyses
                await self._process_scheduled_analyses()

                # Process overdue jobs
                await self._process_overdue_jobs()

                # Health check
                await self._health_check()

                # Wait before next iteration
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                self.logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

        self.logger.info("Scheduler main loop stopped")

    async def _process_cron_schedules(self):
        """Process cron schedules and create scheduled analyses"""
        try:
            current_time = now_utc()

            for schedule_name, cron_schedule in self.cron_schedules.items():
                if not cron_schedule.enabled:
                    continue

                # Check if it's time to run this schedule
                if self._should_run_cron_schedule(cron_schedule, current_time):
                    # Create scheduled analysis
                    await self._create_scheduled_analysis_from_cron(
                        cron_schedule, current_time
                    )

        except Exception as e:
            self.logger.error(f"Failed to process cron schedules: {e}")

    def _should_run_cron_schedule(
        self, cron_schedule: CronSchedule, current_time: datetime
    ) -> bool:
        """Check if a cron schedule should run"""
        try:
            # Parse cron expression
            cron = croniter.croniter(cron_schedule.cron_expression, current_time)

            # Get next run time
            next_run = cron.get_next(datetime)

            # Check if it's time to run (within 30 seconds of current time)
            time_diff = abs((next_run - current_time).total_seconds())

            return time_diff <= 30

        except Exception as e:
            self.logger.error(
                f"Failed to check cron schedule {cron_schedule.name}: {e}"
            )
            return False

    async def _create_scheduled_analysis_from_cron(
        self, cron_schedule: CronSchedule, current_time: datetime
    ):
        """Create a scheduled analysis from a cron schedule"""
        try:
            # Generate unique ID
            analysis_id = f"cron_{cron_schedule.name}_{int(current_time.timestamp())}"

            # Create scheduled analysis
            scheduled_analysis = ScheduledAnalysis(
                id=analysis_id,
                shop_id="*",  # Wildcard for all shops
                analysis_types=cron_schedule.analysis_types,
                scheduled_time=current_time,
                priority=cron_schedule.priority,
                trigger_type="cron_schedule",
                status=ScheduleStatus.PENDING,
                metadata={
                    "cron_schedule": cron_schedule.name,
                    "cron_expression": cron_schedule.cron_expression,
                    "timezone": cron_schedule.timezone,
                },
            )

            # Add to scheduled analyses
            self.scheduled_analyses[analysis_id] = scheduled_analysis
            self.jobs_scheduled += 1

            self.logger.info(
                f"Created scheduled analysis from cron",
                analysis_id=analysis_id,
                cron_schedule=cron_schedule.name,
                analysis_types=cron_schedule.analysis_types,
            )

        except Exception as e:
            self.logger.error(f"Failed to create scheduled analysis from cron: {e}")

    async def _process_scheduled_analyses(self):
        """Process scheduled analyses that are ready to run"""
        try:
            current_time = now_utc()
            ready_analyses = []

            # Find analyses ready to run
            for analysis_id, analysis in self.scheduled_analyses.items():
                if (
                    analysis.status == ScheduleStatus.PENDING
                    and analysis.scheduled_time <= current_time
                    and len(self.running_jobs) < self.max_concurrent_jobs
                ):
                    ready_analyses.append(analysis)

            # Process ready analyses
            for analysis in ready_analyses:
                await self._execute_scheduled_analysis(analysis)

        except Exception as e:
            self.logger.error(f"Failed to process scheduled analyses: {e}")

    async def _process_overdue_jobs(self):
        """Process overdue jobs"""
        try:
            current_time = now_utc()
            overdue_analyses = []

            # Find overdue analyses
            for analysis_id, analysis in self.scheduled_analyses.items():
                if analysis.is_overdue():
                    overdue_analyses.append(analysis)

            # Process overdue analyses
            for analysis in overdue_analyses:
                analysis.status = ScheduleStatus.OVERDUE
                self.jobs_overdue += 1

                self.logger.warning(
                    f"Analysis is overdue",
                    analysis_id=analysis.id,
                    scheduled_time=analysis.scheduled_time.isoformat(),
                    overdue_minutes=int(
                        (current_time - analysis.scheduled_time).total_seconds() / 60
                    ),
                )

                # Try to execute if possible
                if len(self.running_jobs) < self.max_concurrent_jobs:
                    await self._execute_scheduled_analysis(analysis)

        except Exception as e:
            self.logger.error(f"Failed to process overdue jobs: {e}")

    async def _execute_scheduled_analysis(self, analysis: ScheduledAnalysis):
        """Execute a scheduled analysis"""
        try:
            # Mark as started
            analysis.mark_started()
            self.running_jobs.add(analysis.id)

            self.logger.info(
                f"Executing scheduled analysis",
                analysis_id=analysis.id,
                shop_id=analysis.shop_id,
                analysis_types=analysis.analysis_types,
            )

            # Execute the analysis
            if analysis.shop_id == "*":
                # Wildcard - execute for all active shops
                await self._execute_for_all_shops(analysis)
            else:
                # Specific shop
                await self._execute_for_single_shop(analysis)

            # Mark as completed
            analysis.mark_completed()
            self.jobs_completed += 1

            # Remove from running jobs
            self.running_jobs.discard(analysis.id)

            self.logger.info(
                f"Scheduled analysis completed",
                analysis_id=analysis.id,
                shop_id=analysis.shop_id,
            )

        except Exception as e:
            self.logger.error(
                f"Failed to execute scheduled analysis: {e}", analysis_id=analysis.id
            )

            # Mark as failed
            analysis.mark_failed(str(e))
            self.jobs_failed += 1

            # Remove from running jobs
            self.running_jobs.discard(analysis.id)

            # Retry if possible
            if analysis.can_retry():
                await self._schedule_retry(analysis)

    async def _execute_for_all_shops(self, analysis: ScheduledAnalysis):
        """Execute analysis for all active shops"""
        try:
            # Get list of active shops (this would come from database/Redis)
            active_shops = await self._get_active_shops()

            # Execute for each shop
            execution_tasks = []
            for shop_id in active_shops:
                task = self._execute_for_single_shop(analysis, shop_id)
                execution_tasks.append(task)

            # Wait for all executions to complete
            await asyncio.gather(*execution_tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f"Failed to execute for all shops: {e}")
            raise

    async def _execute_for_single_shop(
        self, analysis: ScheduledAnalysis, shop_id: Optional[str] = None
    ):
        """Execute analysis for a single shop"""
        try:
            target_shop_id = shop_id or analysis.shop_id

            # Publish analysis job to Redis stream
            for analysis_type in analysis.analysis_types:
                job_data = {
                    "job_id": f"{analysis.id}_{analysis_type}",
                    "shop_id": target_shop_id,
                    "analysis_type": analysis_type,
                    "priority": analysis.priority.value,
                    "trigger_type": analysis.trigger_type,
                    "scheduled_time": analysis.scheduled_time.isoformat(),
                    "metadata": analysis.metadata,
                    "timestamp": now_utc().isoformat(),
                }

                # Publish to appropriate stream based on analysis type
                # Use stream manager to route to appropriate stream
                from app.core.stream_manager import stream_manager, StreamType

                if analysis_type in ["ml_model_retraining", "ml_training"]:
                    await streams_manager.publish_event(ML_TRAINING_STREAM, job_data)
                    stream_name = ML_TRAINING_STREAM
                else:
                    # Route data collection jobs to data collection stream
                    await stream_manager.publish_to_domain(
                        StreamType.DATA_COLLECTION, job_data
                    )
                    stream_name = "betterbundle:data-collection-jobs"

                self.logger.info(
                    f"Published analysis job",
                    job_id=job_data["job_id"],
                    shop_id=target_shop_id,
                    analysis_type=analysis_type,
                    stream=stream_name,
                )

        except Exception as e:
            self.logger.error(
                f"Failed to execute for single shop: {e}", shop_id=target_shop_id
            )
            raise

    async def _schedule_retry(self, analysis: ScheduledAnalysis):
        """Schedule a retry for a failed analysis"""
        try:
            # Calculate retry time (exponential backoff)
            retry_delay = min(300 * (2**analysis.retry_count), 3600)  # Max 1 hour
            retry_time = now_utc() + timedelta(seconds=retry_delay)

            # Create retry analysis
            retry_analysis = ScheduledAnalysis(
                id=f"{analysis.id}_retry_{analysis.retry_count}",
                shop_id=analysis.shop_id,
                analysis_types=analysis.analysis_types,
                scheduled_time=retry_time,
                priority=analysis.priority,
                trigger_type=f"{analysis.trigger_type}_retry",
                status=ScheduleStatus.PENDING,
                metadata={
                    **analysis.metadata,
                    "retry_of": analysis.id,
                    "retry_count": analysis.retry_count,
                    "original_error": analysis.error_message,
                },
            )

            # Add to scheduled analyses
            self.scheduled_analyses[retry_analysis.id] = retry_analysis

            self.logger.info(
                f"Scheduled retry analysis",
                original_id=analysis.id,
                retry_id=retry_analysis.id,
                retry_time=retry_time.isoformat(),
                retry_delay=retry_delay,
            )

        except Exception as e:
            self.logger.error(f"Failed to schedule retry: {e}", analysis_id=analysis.id)

    async def _get_active_shops(self) -> List[str]:
        """Get list of active shops"""
        # Mock implementation - in real implementation, fetch from database/Redis
        return ["shop_123", "shop_456", "shop_789"]

    async def _health_check(self):
        """Perform health check"""
        current_time = now_utc()
        if (
            current_time - self.last_health_check
        ).total_seconds() >= self.health_check_interval:
            self.last_health_check = current_time

            # Log health status
            self.logger.info(
                f"Scheduler service health check",
                jobs_scheduled=self.jobs_scheduled,
                jobs_completed=self.jobs_completed,
                jobs_failed=self.jobs_failed,
                jobs_overdue=self.jobs_overdue,
                running_jobs=len(self.running_jobs),
                scheduled_analyses=len(self.scheduled_analyses),
                cron_schedules=len(self.cron_schedules),
            )

    # Public API methods
    async def schedule_analysis(
        self,
        shop_id: str,
        analysis_types: List[str],
        scheduled_time: datetime,
        priority: SchedulePriority = SchedulePriority.MEDIUM,
        trigger_type: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Schedule a new analysis"""
        try:
            # Generate unique ID
            analysis_id = f"manual_{shop_id}_{int(now_utc().timestamp())}"

            # Create scheduled analysis
            scheduled_analysis = ScheduledAnalysis(
                id=analysis_id,
                shop_id=shop_id,
                analysis_types=analysis_types,
                scheduled_time=scheduled_time,
                priority=priority,
                trigger_type=trigger_type,
                status=ScheduleStatus.PENDING,
                metadata=metadata or {},
            )

            # Add to scheduled analyses
            self.scheduled_analyses[analysis_id] = scheduled_analysis
            self.jobs_scheduled += 1

            self.logger.info(
                f"Manually scheduled analysis",
                analysis_id=analysis_id,
                shop_id=shop_id,
                analysis_types=analysis_types,
                scheduled_time=scheduled_time.isoformat(),
            )

            return analysis_id

        except Exception as e:
            self.logger.error(f"Failed to schedule analysis: {e}", shop_id=shop_id)
            raise

    async def cancel_analysis(self, analysis_id: str) -> bool:
        """Cancel a scheduled analysis"""
        try:
            if analysis_id not in self.scheduled_analyses:
                return False

            analysis = self.scheduled_analyses[analysis_id]

            # Only allow cancellation of pending analyses
            if analysis.status != ScheduleStatus.PENDING:
                return False

            # Mark as cancelled
            analysis.status = ScheduleStatus.CANCELLED

            self.logger.info(f"Cancelled scheduled analysis", analysis_id=analysis_id)

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to cancel analysis: {e}", analysis_id=analysis_id
            )
            return False

    def get_scheduled_analyses(
        self, shop_id: Optional[str] = None, status: Optional[ScheduleStatus] = None
    ) -> List[Dict[str, Any]]:
        """Get scheduled analyses with optional filtering"""
        analyses = []

        for analysis in self.scheduled_analyses.values():
            # Apply filters
            if shop_id and analysis.shop_id != shop_id:
                continue
            if status and analysis.status != status:
                continue

            analyses.append(
                {
                    "id": analysis.id,
                    "shop_id": analysis.shop_id,
                    "analysis_types": analysis.analysis_types,
                    "scheduled_time": analysis.scheduled_time.isoformat(),
                    "priority": analysis.priority.value,
                    "trigger_type": analysis.trigger_type,
                    "status": analysis.status.value,
                    "retry_count": analysis.retry_count,
                    "created_at": analysis.created_at.isoformat(),
                    "started_at": (
                        analysis.started_at.isoformat() if analysis.started_at else None
                    ),
                    "completed_at": (
                        analysis.completed_at.isoformat()
                        if analysis.completed_at
                        else None
                    ),
                    "error_message": analysis.error_message,
                    "metadata": analysis.metadata,
                }
            )

        return analyses

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler service status"""
        return {
            "status": "running" if not self._shutdown_event.is_set() else "stopped",
            "jobs_scheduled": self.jobs_scheduled,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "jobs_overdue": self.jobs_overdue,
            "running_jobs": len(self.running_jobs),
            "scheduled_analyses": len(self.scheduled_analyses),
            "cron_schedules": len(self.cron_schedules),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "last_health_check": self.last_health_check.isoformat(),
        }

    def get_cron_schedules(self) -> List[Dict[str, Any]]:
        """Get all cron schedules"""
        schedules = []

        for schedule in self.cron_schedules.values():
            schedules.append(
                {
                    "name": schedule.name,
                    "cron_expression": schedule.cron_expression,
                    "analysis_types": schedule.analysis_types,
                    "priority": schedule.priority.value,
                    "enabled": schedule.enabled,
                    "timezone": schedule.timezone,
                    "metadata": schedule.metadata,
                }
            )

        return schedules

    async def update_cron_schedule(
        self, schedule_name: str, updates: Dict[str, Any]
    ) -> bool:
        """Update a cron schedule"""
        try:
            if schedule_name not in self.cron_schedules:
                return False

            schedule = self.cron_schedules[schedule_name]

            # Apply updates
            for key, value in updates.items():
                if hasattr(schedule, key):
                    if key == "priority":
                        setattr(schedule, key, SchedulePriority(value))
                    else:
                        setattr(schedule, key, value)

            # Save configuration
            await self._save_configuration()

            self.logger.info(
                f"Updated cron schedule", schedule_name=schedule_name, updates=updates
            )

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to update cron schedule: {e}", schedule_name=schedule_name
            )
            return False

    async def _save_configuration(self):
        """Save current configuration to file"""
        try:
            config = {"cron_schedules": []}

            for schedule in self.cron_schedules.values():
                config["cron_schedules"].append(
                    {
                        "name": schedule.name,
                        "cron_expression": schedule.cron_expression,
                        "analysis_types": schedule.analysis_types,
                        "priority": schedule.priority.value,
                        "enabled": schedule.enabled,
                        "timezone": schedule.timezone,
                        "metadata": schedule.metadata,
                    }
                )

            with open(self.config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            self.logger.info("Configuration saved successfully")

        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")


# Global scheduler service instance
scheduler_service = SchedulerService(
    heuristic_service=None
)  # Will be set when service is initialized
