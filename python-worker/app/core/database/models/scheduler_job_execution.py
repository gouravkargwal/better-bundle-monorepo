"""
SchedulerJobExecution model — tracks every run of every scheduled/background job.

Single source of truth for when jobs ran, their duration, success/failure, and any
error messages. The Django admin reads from this table to show the scheduler UI.
"""

from sqlalchemy import Column, String, Boolean, Integer, BigInteger, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from .base import Base


class SchedulerJobExecution(Base):
    """Tracks a single execution of a scheduled job."""

    __tablename__ = "scheduler_job_executions"

    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Job identity
    job_name = Column(String(100), nullable=False, index=True)
    job_group = Column(String(100), nullable=True, index=True)  # e.g. billing, reconciler, linking

    # Timing
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Outcome
    status = Column(
        String(20),
        nullable=False,
        default="RUNNING",
        index=True,
    )  # RUNNING, SUCCESS, FAILED, SKIPPED
    success = Column(Boolean, nullable=True)

    # Details
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)  # Full traceback

    # Execution metadata
    triggered_by = Column(
        String(20), nullable=False, default="scheduled"
    )  # scheduled, manual
    attempt_number = Column(Integer, nullable=False, default=1)
    items_processed = Column(Integer, nullable=True)  # e.g. number of commissions reconciled
    metadata_json = Column(JSONB, nullable=True)  # Additional structured data

    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
        server_default=func.timezone("UTC", func.current_timestamp()),
    )

    def __repr__(self) -> str:
        return (
            f"<SchedulerJobExecution(id={self.id}, job_name={self.job_name}, "
            f"status={self.status}, started_at={self.started_at})>"
        )
