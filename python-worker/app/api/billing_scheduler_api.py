"""
Billing Scheduler API Endpoints

This module provides API endpoints for the billing scheduler service,
including GitHub Actions webhook integration.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.billing_scheduler_service import BillingSchedulerService
from app.core.logging import get_logger
from app.core.config.settings import settings

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/billing-scheduler", tags=["billing-scheduler"])

# Global scheduler service instance
_scheduler_service: Optional[BillingSchedulerService] = None


async def get_scheduler_service() -> BillingSchedulerService:
    """Get or create the billing scheduler service"""
    global _scheduler_service

    if _scheduler_service is None:
        _scheduler_service = BillingSchedulerService()
        await _scheduler_service.initialize()

    return _scheduler_service


# Pydantic models for request/response
class BillingProcessRequest(BaseModel):
    shop_ids: Optional[List[str]] = Field(
        None, description="List of shop IDs to process (None for all active shops)"
    )
    period_start: Optional[str] = Field(
        None, description="Billing period start date (ISO format)"
    )
    period_end: Optional[str] = Field(
        None, description="Billing period end date (ISO format)"
    )
    dry_run: bool = Field(
        False, description="If True, calculate but don't create invoices"
    )
    trigger_source: str = Field(
        "api", description="Source that triggered the billing process"
    )


class BillingProcessResponse(BaseModel):
    status: str
    message: str
    processed_shops: int
    successful_shops: int
    failed_shops: int
    total_revenue: float
    total_fees: float
    shop_results: List[Dict[str, Any]]
    errors: List[Dict[str, str]]
    started_at: str
    completed_at: Optional[str] = None
    dry_run: bool


class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload for billing trigger"""

    action: str
    repository: Dict[str, Any]
    sender: Dict[str, Any]
    ref: Optional[str] = None
    workflow_run: Optional[Dict[str, Any]] = None


class BillingStatusResponse(BaseModel):
    status: str
    active_shops: int
    shops_with_billing_plans: int
    pending_invoices: int
    last_updated: str


# API Endpoints


@router.post("/process-monthly-billing", response_model=BillingProcessResponse)
async def process_monthly_billing(
    request: BillingProcessRequest,
    background_tasks: BackgroundTasks,
    scheduler_service: BillingSchedulerService = Depends(get_scheduler_service),
):
    """
    Process monthly billing for specified shops or all active shops.

    This endpoint can be triggered by:
    - GitHub Actions webhook
    - Manual API calls
    - Cron jobs
    - Internal scheduling
    """
    try:
        logger.info(
            f"Processing monthly billing - trigger_source={request.trigger_source}, dry_run={request.dry_run}"
        )

        # Parse billing period if provided
        period = None
        if request.period_start and request.period_end:
            try:
                period_start = datetime.fromisoformat(
                    request.period_start.replace("Z", "+00:00")
                )
                period_end = datetime.fromisoformat(
                    request.period_end.replace("Z", "+00:00")
                )
                from app.domains.billing.repositories.billing_repository import (
                    BillingPeriod,
                )

                period = BillingPeriod(
                    start_date=period_start, end_date=period_end, cycle="monthly"
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

        # Process billing
        result = await scheduler_service.process_monthly_billing(
            shop_ids=request.shop_ids, period=period, dry_run=request.dry_run
        )

        # Log the results
        logger.info(
            f"Billing process completed: {result['successful_shops']} successful, {result['failed_shops']} failed"
        )

        return BillingProcessResponse(**result)

    except Exception as e:
        logger.error(f"Error processing monthly billing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-shop-billing/{shop_id}")
async def process_shop_billing(
    shop_id: str,
    dry_run: bool = False,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    scheduler_service: BillingSchedulerService = Depends(get_scheduler_service),
):
    """
    Process billing for a specific shop.
    """
    try:
        logger.info(f"Processing billing for shop {shop_id} - dry_run={dry_run}")

        # Parse billing period if provided
        period = None
        if period_start and period_end:
            try:
                period_start_dt = datetime.fromisoformat(
                    period_start.replace("Z", "+00:00")
                )
                period_end_dt = datetime.fromisoformat(
                    period_end.replace("Z", "+00:00")
                )
                from app.domains.billing.repositories.billing_repository import (
                    BillingPeriod,
                )

                period = BillingPeriod(
                    start_date=period_start_dt, end_date=period_end_dt, cycle="monthly"
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

        # Process billing for the shop
        result = await scheduler_service.process_shop_billing(
            shop_id=shop_id, period=period, dry_run=dry_run
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Billing processing failed")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing billing for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(
    scheduler_service: BillingSchedulerService = Depends(get_scheduler_service),
):
    """
    Get current billing status and statistics.
    """
    try:
        status = await scheduler_service.get_billing_status()
        return BillingStatusResponse(**status)

    except Exception as e:
        logger.error(f"Error getting billing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/github-webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    scheduler_service: BillingSchedulerService = Depends(get_scheduler_service),
):
    """
    GitHub webhook endpoint for triggering billing processes.

    This endpoint can be called by GitHub Actions to trigger billing calculations.
    """
    try:
        # Get the webhook payload
        payload = await request.json()

        # Verify the webhook (optional - add your secret verification here)
        # webhook_secret = settings.GITHUB_WEBHOOK_SECRET
        # if webhook_secret:
        #     signature = request.headers.get("X-Hub-Signature-256")
        #     if not verify_github_webhook(payload, signature, webhook_secret):
        #         raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Parse the webhook payload
        try:
            webhook_data = GitHubWebhookPayload(**payload)
        except Exception as e:
            logger.warning(f"Invalid webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid webhook payload")

        # Check if this is a workflow run completion
        if webhook_data.action == "completed" and webhook_data.workflow_run:
            workflow_name = webhook_data.workflow_run.get("name", "")

            # Only process billing for specific workflow completions
            if "billing" in workflow_name.lower():
                logger.info(
                    f"GitHub webhook triggered billing process for workflow: {workflow_name}"
                )

                # Process billing in background
                background_tasks.add_task(
                    _process_billing_from_webhook, scheduler_service, webhook_data
                )

                return JSONResponse(
                    status_code=202,
                    content={
                        "message": "Billing process triggered",
                        "workflow": workflow_name,
                        "status": "accepted",
                    },
                )

        # For other webhook events, just acknowledge
        return JSONResponse(
            status_code=200,
            content={
                "message": "Webhook received",
                "action": webhook_data.action,
                "status": "acknowledged",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _process_billing_from_webhook(
    scheduler_service: BillingSchedulerService, webhook_data: GitHubWebhookPayload
):
    """Process billing triggered by GitHub webhook"""
    try:
        logger.info("Processing billing from GitHub webhook")

        # Process monthly billing for all active shops
        result = await scheduler_service.process_monthly_billing(
            shop_ids=None,  # Process all active shops
            period=None,  # Use previous month
            dry_run=False,  # Create actual invoices
        )

        logger.info(
            f"GitHub webhook billing process completed: {result['successful_shops']} successful, {result['failed_shops']} failed"
        )

    except Exception as e:
        logger.error(f"Error processing billing from GitHub webhook: {e}")


@router.post("/trigger-billing")
async def trigger_billing(
    background_tasks: BackgroundTasks,
    dry_run: bool = False,
    shop_ids: Optional[List[str]] = None,
    scheduler_service: BillingSchedulerService = Depends(get_scheduler_service),
):
    """
    Trigger billing process (convenience endpoint for testing and manual triggers).
    """
    try:
        logger.info(f"Triggering billing process - dry_run={dry_run}")

        # Process billing in background
        background_tasks.add_task(
            _process_billing_background, scheduler_service, shop_ids, dry_run
        )

        return JSONResponse(
            status_code=202,
            content={
                "message": "Billing process triggered",
                "dry_run": dry_run,
                "shop_ids": shop_ids,
                "status": "accepted",
            },
        )

    except Exception as e:
        logger.error(f"Error triggering billing process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _process_billing_background(
    scheduler_service: BillingSchedulerService,
    shop_ids: Optional[List[str]],
    dry_run: bool,
):
    """Process billing in background"""
    try:
        result = await scheduler_service.process_monthly_billing(
            shop_ids=shop_ids, period=None, dry_run=dry_run  # Use previous month
        )

        logger.info(
            f"Background billing process completed: {result['successful_shops']} successful, {result['failed_shops']} failed"
        )

    except Exception as e:
        logger.error(f"Error in background billing process: {e}")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint for the billing scheduler service"""
    return {
        "status": "healthy",
        "service": "billing-scheduler",
        "timestamp": datetime.utcnow().isoformat(),
    }
